import { chromium } from "playwright-core";
import fs from "node:fs";

const chromiumDir = fs.readdirSync(`${process.env.HOME}/Library/Caches/ms-playwright`).find(d => d.startsWith("chromium-"));
const execPath = `${process.env.HOME}/Library/Caches/ms-playwright/${chromiumDir}/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing`;

const browser = await chromium.launch({ executablePath: execPath });
const context = await browser.newContext();
await context.addCookies([{ name: "cl_onboarded", value: "1", url: "http://localhost:3000" }]);
const page = await context.newPage();

const consoleErrors = [];
page.on("console", (msg) => {
  if (msg.type() === "error") consoleErrors.push(msg.text());
});
page.on("pageerror", (err) => consoleErrors.push(`[pageerror] ${err.message}`));

// A real fresh navigation (not client-side nav) forces an actual SSR + hydrate
// cycle, which is required to observe a hydration mismatch at all.
await page.goto("http://localhost:3000/videos", { waitUntil: "networkidle" });
await page.waitForTimeout(800);

const hydrationErrors = consoleErrors.filter((m) => /hydrat/i.test(m));

console.log("Total console errors:", consoleErrors.length);
console.log("Hydration-related errors:", hydrationErrors.length);
if (hydrationErrors.length) {
  console.log("\n--- First hydration error ---");
  console.log(hydrationErrors[0].slice(0, 500));
}
console.log(hydrationErrors.length > 0 ? "RED (bug reproduced)" : "GREEN (no hydration error)");

await browser.close();
