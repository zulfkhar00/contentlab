---
name: verify
description: Build/launch/drive recipe for verifying Content Lab changes end-to-end in a real browser.
---

# Verifying Content Lab

Next.js 16 (Turbopack) app, client-rendered `(app)` shell, no backend yet
(state is localStorage-backed React Context). Surface is the browser.

## Launch

```bash
npm run build   # optional — also catches missing Suspense boundaries around
                 # useSearchParams, which dev mode won't
npm run dev      # http://localhost:3000
```

## Bypass onboarding gate

`src/proxy.ts` redirects every `(app)` route to `/onboarding` unless the
`cl_onboarded` cookie equals `"1"`. Set it before hitting any real page:

```js
await context.addCookies([{ name: "cl_onboarded", value: "1", url: "http://localhost:3000" }]);
```

## Driving it headlessly

No Playwright browser binaries are installed via the `playwright` package,
but `playwright-core` is a devDependency and a Chromium build already exists
at `~/Library/Caches/ms-playwright/chromium-<rev>/`. Point `chromium.launch`
at it directly:

```js
import { chromium } from "playwright-core";
import fs from "node:fs";

const dir = fs.readdirSync(`${process.env.HOME}/Library/Caches/ms-playwright`)
  .find(d => d.startsWith("chromium-"));
const execPath = `${process.env.HOME}/Library/Caches/ms-playwright/${dir}/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing`;
const browser = await chromium.launch({ executablePath: execPath });
```

Run any driver script from inside `content-lab/` (not `/tmp`) so
`playwright-core` resolves from `node_modules`.

## Gotchas found so far

- All `(app)` pages gate their real render on a `loaded` flag from
  `useExperiment()`/`useHypotheses()` (false until a `useEffect` reads
  localStorage on mount). Server-rendered/curl'd HTML will look empty —
  you need a real browser context, curl won't show the actual page content.
- Client state mutators exposed by the context providers
  (`lib/experiment.tsx`, `lib/hypotheses.tsx`) do **not** dedupe by id — two
  back-to-back clicks before React re-renders can both read a stale
  "not yet added" check and insert two entries with the same id. Worth
  re-probing after any change to an "add once" button (double-click via
  raw DOM `btn.click(); btn.click();` in `page.evaluate`, not two
  Playwright `.click()` calls, which serialize more than a real double
  click would).
- Fresh `browser.newContext()` per script run gives a clean localStorage
  slate — no manual clearing needed between runs.
