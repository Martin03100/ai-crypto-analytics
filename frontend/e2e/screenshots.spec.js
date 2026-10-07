/**
 * Visual review helper, not a test: captures every page with demo data on desktop and phone.
 * Run: SCREENSHOTS_DIR=<folder> npx playwright test e2e/screenshots.spec.js (SCREENSHOTS_PREMIUM=1: Premium mode on, Premium user)
 */

import { test } from "@playwright/test";
import { grantPremium, prepare, register, setAppSettings } from "./helpers";

const DIR = process.env.SCREENSHOTS_DIR;
test.skip(!DIR, "set SCREENSHOTS_DIR to capture screenshots");
test.setTimeout(300_000);

const PAGES = [
  ["dashboard", "/dashboard"], ["forecast", "/forecast"], ["history", "/forecast?tab=history"], ["schedule", "/forecast?tab=schedule"],
  ["portfolio", "/portfolio"], ["market", "/market"], ["account", "/account"], ["settings", "/settings"],
];
const PREMIUM = process.env.SCREENSHOTS_PREMIUM === "1";
const PREMIUM_PAGES = [["simulator", "/forecast?tab=simulator"], ["mystats", "/forecast?tab=mystats"], ["premium", "/premium"]];

test.beforeAll(async () => { if (DIR) await setAppSettings({ premium_mode: PREMIUM }); });
test.afterAll(async () => { if (DIR && PREMIUM) await setAppSettings({ premium_mode: false }); });

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
    const username = await register(page);
    if (PREMIUM) await grantPremium(username);
    await page.goto("/settings");
    await page.getByRole("button", { name: "Load demo data" }).click();
    await page.getByText(/Created \d+ forecasts/).waitFor();
    for (const [name, path] of PREMIUM ? [...PAGES, ...PREMIUM_PAGES] : PAGES) {
      await page.goto(path);
      await page.waitForLoadState("networkidle").catch(() => {});
      await page.waitForTimeout(1200);
      await page.screenshot({ path: `${DIR}/${device}-${name}.png`, fullPage: true });
    }
    if (PREMIUM) {
      await page.goto("/portfolio");
      await page.getByRole("button", { name: "P&L tracker" }).click();
      for (const [coin, amount, price] of [["BTC", "0.4", "62000"], ["ETH", "3", "3900"], ["SOL", "40", "170"]]) {
        await page.locator(".tracker-form select").selectOption(coin);
        await page.getByLabel("Amount").fill(amount);
        await page.getByLabel("Avg. buy price (USD)").fill(price);
        await page.getByRole("button", { name: "Save", exact: true }).click();
        await page.getByRole("cell", { name: coin, exact: true }).waitFor();
      }
      await page.waitForTimeout(800);
      await page.screenshot({ path: `${DIR}/${device}-tracker.png`, fullPage: true });
    }
  });
}
