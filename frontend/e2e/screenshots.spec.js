/**
 * Visual review helper, not a test: captures every page with demo data on desktop and phone.
 * Run: SCREENSHOTS_DIR=<folder> npx playwright test e2e/screenshots.spec.js
 */

import { test } from "@playwright/test";
import { prepare, register } from "./helpers";

const DIR = process.env.SCREENSHOTS_DIR;
test.skip(!DIR, "set SCREENSHOTS_DIR to capture screenshots");
test.setTimeout(180_000);

const PAGES = [
  ["dashboard", "/dashboard"], ["forecast", "/forecast"], ["history", "/forecast?tab=history"], ["schedule", "/forecast?tab=schedule"],
  ["portfolio", "/portfolio"], ["market", "/market"], ["account", "/account"], ["settings", "/settings"],
];

for (const [device, viewport] of [["desktop", { width: 1440, height: 900 }], ["phone", { width: 390, height: 844 }]]) {
  test(`screens ${device}`, async ({ page }) => {
    await page.setViewportSize(viewport);
    await page.emulateMedia({ colorScheme: process.env.SCREENSHOTS_SCHEME === "light" ? "light" : "dark" });
    await prepare(page);
    for (const [name, path] of [["landing", "/"], ["auth", "/auth"]]) {
      await page.goto(path);
      await page.waitForTimeout(800);
      await page.screenshot({ path: `${DIR}/${device}-${name}.png`, fullPage: true });
    }
    await register(page);
    await page.goto("/settings");
    await page.getByRole("button", { name: "Load demo data" }).click();
    await page.getByText(/Created \d+ forecasts/).waitFor();
    for (const [name, path] of PAGES) {
      await page.goto(path);
      await page.waitForLoadState("networkidle").catch(() => {});
      await page.waitForTimeout(1200);
      await page.screenshot({ path: `${DIR}/${device}-${name}.png`, fullPage: true });
    }
  });
}
