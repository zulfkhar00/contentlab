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

// ---------- /hypotheses: seed batch, deep-link on tested card ----------
await page.goto("http://localhost:3000/hypotheses", { waitUntil: "networkidle" });
await page.waitForTimeout(300);
const generateBtn = page.getByRole("button", { name: /Generate Initial Hypotheses/i });
if ((await generateBtn.count()) > 0) {
  await generateBtn.first().click();
  await page.waitForTimeout(400);
}
const seedTitle = await page
  .locator("h4", { hasText: "Pain hooks outperform product demos" })
  .count();
expect("/hypotheses: seed batch populated", seedTitle > 0);

const h5Card = page
  .locator("div", {
    has: page.locator("h4", {
      hasText: "Short pain-first hooks outperform long-form storytelling",
    }),
  })
  .first();
await h5Card.scrollIntoViewIfNeeded();
await h5Card.click();
await page.waitForTimeout(150);
const viewInsightLink = await page
  .locator('a[href^="/insights?id=i1"]', { hasText: /View Insight/i })
  .count();
expect(
  "/hypotheses: tested hypothesis View Insight deep-links to /insights?id=i1",
  viewInsightLink > 0,
);

// ---------- /overview: backlog now reads from real store ----------
await page.goto("http://localhost:3000/overview", { waitUntil: "networkidle" });
await page.waitForTimeout(300);
const backlogTitles = await page
  .locator('a[href="/hypotheses"] h5')
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
  .locator("h3", { hasText: "Short Hook vs Long-Form Story" })
  .count();
expect("/insights?id=i1: correct insight selected via query param", insightSelected > 0);
const followUpPreview = await page
  .locator("h3", { hasText: /Follow-up Hypothesis Preview/i })
  .count();
expect("/insights: follow-up preview section present", followUpPreview > 0);

// ---------- Add to Hypotheses under double-click (dedup) ----------
// Two raw DOM clicks in one page.evaluate — not two Playwright .click() calls
// which serialize too much. SKILL documents this explicitly.
const addResult = await page.evaluate(() => {
  const btn = [...document.querySelectorAll("button")].find(
    (b) => b.textContent?.trim() === "Add to Hypotheses",
  );
  if (!btn) return { found: false };
  btn.click();
  btn.click();
  return { found: true };
});
expect("/insights: Add to Hypotheses button found", addResult.found);
await page.waitForTimeout(300);

const toggled = await page
  .getByRole("button", { name: /View in Hypotheses/i })
  .count();
expect("/insights: button toggles to 'View in Hypotheses' after add", toggled === 1);

const stored = await page.evaluate(() => {
  const raw = window.localStorage.getItem("cl_hypotheses");
  if (!raw) return { total: 0, followups: 0 };
  const list = JSON.parse(raw);
  return {
    total: list.length,
    followups: list.filter((h) => h.id === "i1-followup").length,
  };
});
expect(
  `add-dedup: exactly one i1-followup in localStorage under double click (saw ${stored.followups})`,
  stored.followups === 1,
);

// ---------- /hypotheses: follow-up shows 'Follow-up of' lineage ----------
await page.goto("http://localhost:3000/hypotheses", { waitUntil: "networkidle" });
await page.waitForTimeout(300);
const lineageNote = await page.locator("p", { hasText: /^Follow-up of:/i }).count();
expect(
  "/hypotheses: follow-up card renders 'Follow-up of: …' lineage note",
  lineageNote >= 1,
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
