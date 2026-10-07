import { expect, test } from "@playwright/test";
import { ownerSession, prepare, register } from "./helpers";

test.beforeEach(async ({ page }) => prepare(page));

test("coin index lists 20 coins and opens a coin page in each language", async ({ page }) => {
  await page.goto("/prediction");
  await expect(page.getByRole("heading", { name: "Crypto price predictions" })).toBeVisible();
  await expect(page.locator(".coin-tile")).toHaveCount(20);
  await page.locator(".coin-tile", { hasText: "Ethereum" }).click();
  await expect(page).toHaveURL(/\/prediction\/ethereum$/);
  await expect(page.getByRole("heading", { name: "Ethereum (ETH) price prediction" })).toBeVisible();

  await page.goto("/sk/predikcia/bitcoin");
  await expect(page.getByRole("heading", { name: "Predikcia ceny Bitcoin (BTC)" })).toBeVisible();
  await page.goto("/cs/predikce/neexistuje");
  await expect(page).toHaveURL(/\/cs\/predikce$/);
  await expect(page.getByRole("heading", { name: "Predikce cen kryptoměn" })).toBeVisible();
});

test("landing footer links to the coin pages", async ({ page }) => {
  await page.goto("/");
  await page.locator(".landing-footer").getByRole("link", { name: "Crypto price predictions" }).click();
  await expect(page).toHaveURL(/\/prediction$/);
});

const ROUND = {
  week: "2026-W41", coin: "SOL", start_price: 150, ai_price: 155, open: true, entries: 3, my_price: null,
  deadline: "2026-10-08T00:00:00Z", ends_at: "2026-10-12T00:00:00Z",
};

test("weekly challenge card is on the dashboard and accepts a tip", async ({ page }) => {
  // Live prices are not reachable from CI, so the round itself is mocked; the UI flow is real.
  await page.route("**/api/challenge", (route) => route.fulfill({ json: { current: ROUND, last: null, my_wins: 0 } }));
  await page.route("**/api/challenge/entry", (route) => route.fulfill({ json: { current: { ...ROUND, my_price: 160, entries: 4 }, last: null, my_wins: 0 } }));
  await register(page);
  await page.goto("/dashboard");
  await expect(page.getByText("Beat the AI — weekly challenge")).toBeVisible({ timeout: 30_000 });
  await page.getByPlaceholder("SOL price on Sunday").fill("160");
  await page.getByRole("button", { name: "Send tip" }).click();
  await expect(page.getByText("Your tip: $160")).toBeVisible();
});

test("status page shows 30-day availability bars", async ({ page }) => {
  const days = Array.from({ length: 30 }, (_, i) => ({ day: `2026-09-${String(i + 1).padStart(2, "0")}`, uptime_pct: i === 3 ? 95 : 100 }));
  await page.route("**/api/public/status/history", (route) => route.fulfill({ json: { services: [{ id: "backend", uptime_pct: 99.8, days }] } }));
  await page.goto("/status");
  await expect(page.locator(".uptime-bars").first()).toBeVisible({ timeout: 30_000 });
  await expect(page.locator(".uptime-bar")).toHaveCount(30);
  await expect(page.getByText("99.8 % in 30 days")).toBeVisible();
});

test("admin backup downloads compressed JSON and is admin-only", async ({ request }) => {
  const anon = await request.get("/api/admin/backup");
  expect([401, 403]).toContain(anon.status());
  const { ctx } = await ownerSession();
  const res = await ctx.get("/api/admin/backup");
  expect(res.ok()).toBeTruthy();
  expect(res.headers()["content-disposition"]).toContain(".json.gz");
  await ctx.dispose();
});
