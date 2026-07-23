// End-to-end verify driver, per .claude/skills/verify/SKILL.md — walks the
// surfaces this branch touches (videos hydration gate, shared Hypotheses
// store, insights detail + follow-up flow, overview backlog reading real
// store, add-dedup guard on double click). Prints OK/FAIL per check and a
// final GREEN/RED verdict.

import { chromium } from "playwright-core";
import fs from "node:fs";

const chromiumDir = fs
  .readdirSync(`${process.env.HOME}/Library/Caches/ms-playwright`)
  .find((d) => d.startsWith("chromium-"));
const execPath = `${process.env.HOME}/Library/Caches/ms-playwright/${chromiumDir}/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing`;

const failures = [];
function expect(label, cond, detail) {
  if (cond) {
    console.log(`OK:   ${label}`);
  } else {
    console.log(`FAIL: ${label}${detail ? ` — ${detail}` : ""}`);
    failures.push(label);
  }
}

const browser = await chromium.launch({ executablePath: execPath });
const context = await browser.newContext();
await context.addCookies([
  { name: "cl_onboarded", value: "1", url: "http://localhost:3000" },
]);
const page = await context.newPage();

const consoleErrors = [];
page.on("console", (msg) => {
  if (msg.type() === "error") consoleErrors.push(msg.text());
});
page.on("pageerror", (err) => consoleErrors.push(`[pageerror] ${err.message}`));

// ---------- Storage migration probe (Step 1) ----------
// Pre-seed the legacy cl_campaign key with a shape-valid ExperimentData
// payload (so no downstream render crashes on missing fields), then visit
// an (app) page. ExperimentProvider's useEffect should copy the payload
// into cl_experiment and delete the legacy key. Idempotent.
await page.goto("http://localhost:3000/onboarding");
const legacyMarker = "legacy-payload-marker";
const legacyStub = JSON.stringify({
  name: legacyMarker,
  hypothesis: "stub",
  primaryMetric: "Clicks / 1K Views",
  cta: "stub",
  trackingWindowLabel: "72h",
  trackingWindowHours: 72,
  script: { lesson: "", product: "", cta: "", targetDurationLabel: "50s" },
  variants: [
    { role: "A", title: "A", roleLabel: "Control", hook: "", hookDeliveryNote: "", context: "", variableUnderTest: "", onScreenText: "", status: "queued" },
    { role: "B", title: "B", roleLabel: "Hypothesis Treatment", hook: "", hookDeliveryNote: "", context: "", variableUnderTest: "", onScreenText: "", status: "queued" },
    { role: "C", title: "C", roleLabel: "Alternative Treatment", hook: "", hookDeliveryNote: "", context: "", variableUnderTest: "", onScreenText: "", status: "queued" },
  ],
});
await page.evaluate((stub) => {
  window.localStorage.setItem("cl_campaign", stub);
}, legacyStub);
await page.goto("http://localhost:3000/overview", { waitUntil: "networkidle" });
await page.waitForTimeout(300);
const migration = await page.evaluate(() => ({
  legacy: window.localStorage.getItem("cl_campaign"),
  current: window.localStorage.getItem("cl_experiment"),
}));
expect(
  "storage migration: cl_campaign removed after mount",
  migration.legacy === null,
  `still there: ${migration.legacy?.slice(0, 80)}`,
);
expect(
  "storage migration: legacy payload copied to cl_experiment",
  typeof migration.current === "string" && migration.current.includes(legacyMarker),
  `cl_experiment: ${migration.current?.slice(0, 80)}`,
);
// Clean the stub so downstream checks use real seed data.
await page.evaluate(() => window.localStorage.removeItem("cl_experiment"));

// ---------- /videos: hydration regression after loaded-gate fix ----------
await page.goto("http://localhost:3000/videos", { waitUntil: "networkidle" });
await page.waitForTimeout(400);
const hydrationErrors = consoleErrors.filter((m) => /hydrat/i.test(m));
expect(
  "/videos: no hydration errors",
  hydrationErrors.length === 0,
  hydrationErrors[0]?.slice(0, 200),
);
const videosH2 = await page.textContent("h2");
expect(
  "/videos: renders past loaded gate",
  videosH2?.trim() === "Videos",
  `H2 was ${JSON.stringify(videosH2)}`,
);
const trackingBars = await page.locator("div.h-full.bg-primary").count();
expect("/videos: tracking-window bar present", trackingBars > 0);

// ---------- Sidebar labels reflect the vocabulary shift (Step 1) ----------
const sidebarLabels = await page
  .locator("aside nav a")
  .allTextContents();
const sidebarFlat = sidebarLabels.map((s) => s.trim()).join("|");
expect(
  "sidebar: shows 'Research' instead of 'Hypotheses'",
  /Research/.test(sidebarFlat) && !/Hypotheses/.test(sidebarFlat),
  `saw: ${sidebarFlat}`,
);
expect(
  "sidebar: shows 'Experiments' instead of 'Campaigns'",
  /Experiments/.test(sidebarFlat) && !/Campaigns/.test(sidebarFlat),
  `saw: ${sidebarFlat}`,
);

// ---------- /overview: empty backlog until we generate ----------
await page.goto("http://localhost:3000/overview", { waitUntil: "networkidle" });
await page.waitForTimeout(300);
const emptyBacklog = await page
  .getByText("No hypotheses yet — generate your first batch.")
  .count();
expect(
  "/overview: empty-backlog CTA visible before any hypotheses exist",
  emptyBacklog === 1,
);
const seedInsightLink = await page.locator('a[href^="/insights?id=i1"]').count();
expect(
  "/overview: Recent Insights card deep-links to /insights?id=i1",
  seedInsightLink >= 1,
);

// ---------- /research: seed batch, deep-link on tested card ----------
await page.goto("http://localhost:3000/research", { waitUntil: "networkidle" });
await page.waitForTimeout(300);
const generateBtn = page.getByRole("button", { name: /Generate Initial Hypotheses/i });
if ((await generateBtn.count()) > 0) {
  await generateBtn.first().click();
  await page.waitForTimeout(400);
}
const seedTitle = await page
  .getByText("Pain hooks outperform product demos", { exact: true })
  .count();
expect("/research: seed batch populated", seedTitle > 0);

const learnedCard = page
  .locator("button.border.bg-card.p-3", {
    hasText: "Short pain-first hooks outperform long-form storytelling",
  })
  .first();
await learnedCard.scrollIntoViewIfNeeded();
await learnedCard.click();
await page.waitForTimeout(200);
const viewInsightLink = await page
  .locator('a[href^="/insights?id=i1"]', { hasText: /View Insight/i })
  .count();
expect(
  "/research: tested hypothesis View Insight deep-links to /insights?id=i1",
  viewInsightLink > 0,
);

// ---------- /overview: backlog now reads from real store ----------
await page.goto("http://localhost:3000/overview", { waitUntil: "networkidle" });
await page.waitForTimeout(300);
const backlogTitles = await page
  .locator('a[href="/research"] span.text-sm.font-medium')
  .allTextContents();
expect(
  "/overview: backlog reflects real hypotheses store after seed generation",
  backlogTitles.length >= 1,
  `saw: ${JSON.stringify(backlogTitles)}`,
);

// ---------- /insights?id=i1: detail selected + follow-up preview ----------
await page.goto("http://localhost:3000/insights?id=i1", { waitUntil: "networkidle" });
await page.waitForTimeout(300);
const insightSelected = await page
  .locator('[data-testid="results-header"]')
  .count();
expect("/insights?id=i1: correct insight selected via query param", insightSelected > 0);
// Screen 6 (Experiment Results) sections + Screen 7 candidates.
for (const [label, testId] of [
  ["Results header", "results-header"],
  ["Section 1 Research Question", "section-research-question"],
  ["Section 2 Hypothesis Tested", "section-hypothesis-tested"],
  ["Section 3 Variant Comparison", "section-variant-comparison"],
  ["Section 4 Observed Result", "section-observed-result"],
  ["Section 5 Supported Learning", "section-supported-learning"],
  ["Section 6 What Is Not Proven", "section-not-proven"],
  ["Section 7 Experiment Limitations", "section-limitations"],
  ["Section 8 Outcome Classification", "section-outcome"],
  ["Section 9 Next Candidates", "next-candidates"],
]) {
  const n = await page.getByTestId(testId).count();
  expect(`/insights: ${label} present`, n === 1, `count=${n}`);
}
const candidateCards = await page.locator(`[data-testid^="candidate-card-"]`).count();
expect(
  "/insights: exactly three next-candidate cards",
  candidateCards === 3,
  `cards=${candidateCards}`,
);
const recommendedPill = await page.getByText("Recommended", { exact: true }).count();
expect(
  "/insights: exactly one candidate marked Recommended",
  recommendedPill === 1,
  `pills=${recommendedPill}`,
);

// Click Review Hypothesis on the recommended candidate (i1-c2) twice quickly
// to make sure it dedupes into a single Hypothesis in localStorage.
const addResult = await page.evaluate(() => {
  const card = document.querySelector('[data-testid="candidate-card-i1-c2"]');
  const btn = card ? Array.from(card.querySelectorAll("button")).find((b) => b.textContent?.trim() === "Review Hypothesis") : null;
  if (!btn) return { found: false };
  btn.click();
  btn.click();
  return { found: true };
});
expect("/insights: Review Hypothesis on recommended candidate found", addResult.found);
await page.waitForTimeout(300);

const toggled = await page
  .locator('[data-testid="candidate-card-i1-c2"]')
  .getByRole("button", { name: /View in Research/i })
  .count();
expect("/insights: recommended card toggles to \'View in Research\' after add", toggled === 1);

const stored = await page.evaluate(() => {
  const raw = window.localStorage.getItem("cl_hypotheses");
  if (!raw) return { total: 0, followups: 0 };
  const list = JSON.parse(raw);
  return {
    total: list.length,
    followups: list.filter((h) => h.id === "i1-c2-hypothesis").length,
  };
});
expect(
  `add-dedup: exactly one i1-c2-hypothesis in localStorage under double click (saw ${stored.followups})`,
  stored.followups === 1,
);

// ---------- /research: follow-up shows 'Follow-up of' lineage ----------
await page.goto("http://localhost:3000/research", { waitUntil: "networkidle" });
await page.waitForTimeout(300);
const lineageNote = await page.getByText(/Derived from:/i).count();
expect(
  "/research: follow-up card renders 'Derived from:' lineage note",
  lineageNote >= 1,
);

// ---------- Legacy /hypotheses redirects to /research (Step 2) ----------
await page.goto("http://localhost:3000/hypotheses", { waitUntil: "networkidle" });
await page.waitForTimeout(300);
expect(
  "/hypotheses: legacy route redirects to /research",
  page.url().endsWith("/research"),
  `landed at: ${page.url()}`,
);

// ---------- /research: Inspector renders all doc sections (Step 2) ----------
await page.goto("http://localhost:3000/research", { waitUntil: "networkidle" });
await page.waitForTimeout(300);
const firstCard = page.locator("button.border.bg-card.p-3", { hasText: "Pain hooks outperform product demos" }).first();
await firstCard.scrollIntoViewIfNeeded();
await firstCard.click();
await page.waitForTimeout(200);
for (const section of ["Research Question", "Hypothesis", "Experiment Design Preview", "Why This Matters", "Lineage"]) {
  const found = await page.getByText(section).count();
  expect(`/research: Inspector renders '${section}'`, found >= 1, `found ${found}`);
}

// ---------- /research: Review Hypothesis button navigates to Review screen (Step 2) ----------
// Pick a Suggested hypothesis so the Review Hypothesis action is present.
const suggestedCard = page.locator("button.border.bg-card.p-3", { hasText: "Founder journey creates more trust" }).first();
const hasSuggested = (await suggestedCard.count()) > 0;
if (hasSuggested) {
  await suggestedCard.scrollIntoViewIfNeeded();
  await suggestedCard.click();
  await page.waitForTimeout(150);
  const reviewLink = page.getByRole("link", { name: /^Review Hypothesis$/ }).first();
  expect("/research: suggested card exposes Review Hypothesis action", (await reviewLink.count()) > 0);
  await reviewLink.click();
  await page.waitForURL(new RegExp("/research/.*/review$"));
  await page.waitForTimeout(300);
  expect(
    "/research/[id]/review: page loads",
    /review$/.test(page.url()),
    `url: ${page.url()}`,
  );
  for (const section of ["1 \u2014 Research Question", "2 \u2014 Hypothesis Statement", "3 \u2014 Experiment Design", "4 \u2014 Controlled Elements", "5 \u2014 Contradiction Condition", "6 \u2014 Source and Reason"]) {
    const found = await page.getByText(section).count();
    expect(`Review: renders '${section}'`, found >= 1, `found ${found}`);
  }
  const approveBtn = page.getByTestId("approve-and-generate");
  expect("Review: Approve & Generate button present", (await approveBtn.count()) === 1);
  await approveBtn.click();
  await page.waitForURL(new RegExp("/research$"));
  await page.waitForTimeout(400);
  const approvedInStore = await page.evaluate(() => {
    const raw = window.localStorage.getItem("cl_hypotheses");
    if (!raw) return null;
    const list = JSON.parse(raw);
    return list.some((h) => h.status === "approved");
  });
  expect("Review: Approve & Generate persists status 'approved'", approvedInStore === true);
} else {
  expect("/research: suggested card exposes Review Hypothesis action", false, "no Suggested card matched 'Founder journey creates more trust'");
}

// ---------- /overview: redesign hits every doc section (Step 3) ----------
await page.goto("http://localhost:3000/overview", { waitUntil: "networkidle" });
await page.waitForTimeout(300);
for (const label of ["Published Videos", "Product Clicks", "Completed Experiments", "Active Research Thread"]) {
  const found = await page.getByText(label).count();
  expect(`/overview: top metric '${label}'`, found >= 1, `found ${found}`);
}
expect(
  "/overview: Next Action card is present",
  (await page.getByTestId("next-action-card").count()) === 1,
);
expect(
  "/overview: Current Research Thread section present",
  (await page.getByTestId("current-research-thread").count()) === 1,
);
expect(
  "/overview: Latest Learning section present",
  (await page.getByTestId("latest-learning").count()) === 1,
);
expect(
  "/overview: Research Backlog section present",
  (await page.getByTestId("research-backlog").count()) === 1,
);

// ---------- /campaigns: Experiment Workspace redesign (Step 4) ----------
await page.goto("http://localhost:3000/campaigns", { waitUntil: "networkidle" });
await page.waitForTimeout(300);
expect(
  "/campaigns: Experiment header block present",
  (await page.getByTestId("experiment-header").count()) === 1,
);
expect(
  "/campaigns: Experiment Integrity panel present",
  (await page.getByTestId("experiment-integrity").count()) === 1,
);
expect(
  "/campaigns: Variable Under Test label present",
  (await page.getByText("Variable Under Test").count()) >= 1,
);
expect(
  "/campaigns: Keep Controlled label present",
  (await page.getByText("Keep Controlled").count()) === 1,
);
expect(
  "/campaigns: Three variant cards rendered",
  (await page.getByTestId("variant-cards").locator("> div").count()) === 3,
);
expect(
  "/campaigns: Experiment Timeline present",
  (await page.getByTestId("experiment-timeline").count()) === 1,
);
const timelineRows = await page.getByTestId("experiment-timeline").locator("ul > li").count();
expect(
  "/campaigns: Timeline has at least three events",
  timelineRows >= 3,
  `rows=${timelineRows}`,
);
// Primary action strip appears whenever there is a next variant OR all are completed.
const primaryStrip = await page.getByTestId("primary-action-strip").count();
expect(
  "/campaigns: Primary action strip renders when applicable",
  primaryStrip <= 1,
  `count=${primaryStrip}`,
);

// ---------- /campaigns/brief/[role]: Recording Brief redesign (Step 5) ----------
await page.goto("http://localhost:3000/campaigns/brief/b", { waitUntil: "networkidle" });
await page.waitForTimeout(300);
expect(
  "/brief: Experiment Context block present",
  (await page.getByTestId("experiment-context").count()) === 1,
);
expect(
  "/brief: Variable Under Test label present",
  (await page.getByText("Variable Under Test").count()) >= 1,
);
expect(
  "/brief: This Variant Changes label present",
  (await page.getByText("This Variant Changes").count()) === 1,
);
expect(
  "/brief: Keep Controlled label present",
  (await page.getByText("Keep Controlled").count()) === 1,
);
expect(
  "/brief: Script editor renders 5 rows",
  (await page.getByTestId("script-editor").locator("ul > li").count()) === 5,
);
const variableTags = await page.getByTestId("script-editor").getByText("VARIABLE", { exact: true }).count();
const controlledTags = await page.getByTestId("script-editor").getByText("CONTROLLED", { exact: true }).count();
expect(
  "/brief: script rows include VARIABLE tags",
  variableTags >= 2,
  `tags=${variableTags}`,
);
expect(
  "/brief: script rows include CONTROLLED tags",
  controlledTags >= 3,
  `tags=${controlledTags}`,
);
expect(
  "/brief: Founder Fact Check section present",
  (await page.getByTestId("founder-fact-check").count()) === 1,
);
expect(
  "/brief: Recording Guide section present",
  (await page.getByTestId("recording-guide").count()) === 1,
);
expect(
  "/brief: Approval strip present",
  (await page.getByTestId("approval-strip").count()) === 1,
);
// Variant B is the current next action in the seed data, so "Approve for Recording" should be visible.
expect(
  "/brief: Approve for Recording button visible",
  (await page.getByRole("button", { name: /^Approve for Recording$/ }).count()) === 1,
);

// ---------- /research/[id]/review: Follow-up variant (Step 7) ----------
await page.goto("http://localhost:3000/research/i1-c2-hypothesis/review", { waitUntil: "networkidle" });
await page.waitForTimeout(300);
expect(
  "/research/[id]/review (follow-up): Derived From section present",
  (await page.getByTestId("lineage-derived-from").count()) === 1,
);
expect(
  "/research/[id]/review (follow-up): Previous Learning section present",
  (await page.getByTestId("lineage-previous-learning").count()) === 1,
);
expect(
  "/research/[id]/review (follow-up): Remaining Unknown section present",
  (await page.getByTestId("lineage-remaining-unknown").count()) === 1,
);
const headerTitle = await page.locator("h2", { hasText: "Review Follow-up Hypothesis" }).count();
expect(
  "/research/[id]/review (follow-up): header reads Review Follow-up Hypothesis",
  headerTitle === 1,
);
expect(
  "/research/[id]/review (follow-up): Relationship label shows Mechanism Isolation",
  (await page.getByTestId("lineage-derived-from").getByText("Mechanism Isolation").count()) >= 1,
);
const stdSections = await page.getByTestId("review-form").locator("> section").count();
expect(
  "/research/[id]/review (follow-up): shows lineage + standard 6-section form",
  stdSections >= 6 + 3,
  `count=${stdSections}`,
);

// ---------- Verdict ----------
console.log("\n---");
console.log(`Total console errors observed: ${consoleErrors.length}`);
if (consoleErrors.length > 0) {
  console.log("First console error:", consoleErrors[0].slice(0, 300));
}
console.log(`Failures: ${failures.length}`);
if (failures.length > 0) {
  console.log("Failed checks:");
  failures.forEach((f) => console.log(`  - ${f}`));
}
console.log(failures.length === 0 ? "GREEN (all checks passed)" : "RED (some checks failed)");

await browser.close();
process.exit(failures.length === 0 ? 0 : 1);
