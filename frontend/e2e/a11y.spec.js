import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { prepare, register } from "./helpers";

test.beforeEach(async ({ page }) => prepare(page));

const SCANNER = { rows: [
  { coin: "BTC", price: 65000, market_cap: 1.3e12, change_24h: 2.4, change_7d: -1.2, expected_24h_pct: 0.8, signal: "bullish" },
  { coin: "ETH", price: 3200, market_cap: 3.8e11, change_24h: -3.1, change_7d: 4.0, expected_24h_pct: -0.9, signal: "bearish" },
], locked: 0 };

async function audit(page) {
  const result = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  const serious = result.violations.filter((v) => ["serious", "critical"].includes(v.impact));
  expect(serious.map((v) => `${v.id}: ${v.nodes.slice(0, 3).map((n) => n.target.join(" ")).join(" | ")}`)).toEqual([]);
}

for (const theme of ["dark", "light"]) {
  test(`public pages are accessible (${theme})`, async ({ page }) => {
    await page.addInitScript((t) => localStorage.setItem("aca_theme", t), theme);
    for (const path of ["/", "/calendar", "/glossary", "/changelog", "/track-record", "/prediction/bitcoin"]) {
      await page.goto(path);
      await page.waitForLoadState("networkidle").catch(() => {});
      await page.waitForTimeout(500);
      await audit(page);
    }
  });

  test(`app pages are accessible (${theme})`, async ({ page }) => {
    await page.addInitScript((t) => localStorage.setItem("aca_theme", t), theme);
    await page.route("**/api/tools/scanner", (route) => route.fulfill({ json: SCANNER }));
    await register(page);
    for (const path of ["/dashboard", "/market", "/quick", "/settings"]) {
      await page.goto(path);
      await page.waitForTimeout(1200);
      await audit(page);
    }
    await page.goto("/dashboard");
    await page.getByRole("button", { name: "Beginner view" }).click();
    await page.waitForTimeout(600);
    await audit(page);
  });
}
