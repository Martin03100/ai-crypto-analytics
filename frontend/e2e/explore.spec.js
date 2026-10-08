import { expect, test } from "@playwright/test";
import { ownerSession, prepare, register } from "./helpers";

test.beforeEach(async ({ page }) => prepare(page));

const SCANNER = {
  rows: [
    { coin: "BTC", price: 65000, market_cap: 1.3e12, change_24h: 2.4, change_7d: -1.2, expected_24h_pct: 0.8, signal: "bullish" },
    { coin: "ETH", price: 3200, market_cap: 3.8e11, change_24h: -3.1, change_7d: 4.0, expected_24h_pct: -0.9, signal: "bearish" },
    { coin: "SOL", price: 150, market_cap: 7e10, change_24h: 0.2, change_7d: 1.0, expected_24h_pct: 0.1, signal: "neutral" },
  ],
  locked: 0,
};

test("glossary search and changelog badge", async ({ page }) => {
  await page.goto("/glossary");
  await expect(page.getByRole("heading", { name: "Glossary" })).toBeVisible();
  await page.getByPlaceholder("Search terms").fill("halving");
  await expect(page.locator(".glossary-item")).toHaveCount(1);
  await page.goto("/changelog");
  await expect(page.getByRole("heading", { name: "What's new" })).toBeVisible();
  await expect(page.locator(".changelog-entry").first()).toContainText("Beginner view");
});

test("public calendar lists macro events; reminders need an account", async ({ page }) => {
  await page.goto("/calendar");
  await expect(page.getByRole("heading", { name: "Event calendar" })).toBeVisible();
  await expect(page.locator(".calendar-item").first()).toBeVisible({ timeout: 30_000 });
  await page.getByRole("radio", { name: "Macro" }).click();
  await expect(page.locator(".calendar-item").first()).toContainText(/Fed|inflation|jobs/);
  await expect(page.getByText("Sign in to get a reminder before an event")).toBeVisible();
});

test("signed-in user sets a calendar reminder", async ({ page }) => {
  await register(page);
  await page.goto("/calendar");
  const first = page.locator(".calendar-item").first();
  await expect(first).toBeVisible({ timeout: 30_000 });
  await first.getByRole("button", { name: /Remind me/ }).click();
  await expect(page.getByText("We'll remind you an hour before.")).toBeVisible();
  await expect(first.getByRole("button", { name: /Cancel reminder/ })).toHaveAttribute("aria-pressed", "true");
  await page.reload();
  await expect(page.locator(".calendar-item").first().getByRole("button", { name: /Cancel reminder/ })).toBeVisible({ timeout: 30_000 });
});

test("command palette jumps to a page and a coin", async ({ page }) => {
  await register(page);
  await page.goto("/dashboard");
  await expect(page.locator(".sidebar .palette-trigger")).toBeVisible();
  await page.keyboard.press("Control+k");
  const input = page.getByPlaceholder("Type a page, coin or action…");
  await expect(input).toBeFocused();
  await input.fill("glossary");
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/glossary$/);
  await page.goto("/dashboard");
  await page.locator(".sidebar .palette-trigger").click();
  await page.getByPlaceholder("Type a page, coin or action…").fill("eth forecast");
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/forecast\?coin=ETH$/);
});

test("beginner view shows traffic lights and the forecast verdict", async ({ page }) => {
  await page.route("**/api/tools/scanner", (route) => route.fulfill({ json: SCANNER }));
  await register(page);
  await page.goto("/dashboard");
  await page.getByRole("button", { name: "Beginner view" }).click();
  await expect(page.getByText("Your coins at a glance")).toBeVisible();
  await expect(page.getByText("BTC is more likely to rise a little in the next 24 h (+0.8 %).")).toBeVisible();
  await expect(page.locator(".traffic-red").first()).toBeVisible();
  await page.reload();
  await expect(page.getByText("Your coins at a glance")).toBeVisible();      // stored on the account
  await page.getByRole("button", { name: "Show the full view" }).click();
  await expect(page.getByText("Your coins at a glance")).toHaveCount(0);
});

test("market heatmap and what-if calculator", async ({ page }) => {
  await page.route("**/api/tools/scanner", (route) => route.fulfill({ json: SCANNER }));
  const curve = Array.from({ length: 31 }, (_, i) => ({ date: `2026-09-${String(i + 1).padStart(2, "0")}`.replace("09-31", "10-01"),
    strategy: 1000 + i * 5, hold: 1000 + i * 2 }));
  await page.route("**/api/tools/what-if**", (route) => route.fulfill({ json: {
    coin: "BTC", days: 30, amount: 1000, fee_pct: 0.1, signal_today: "up", curve,
    strategy: { final: 1150, return_pct: 15, max_drawdown_pct: -3, trades: 4, exposure_pct: 70 },
    hold: { final: 1060, return_pct: 6, max_drawdown_pct: -8 } } }));
  await register(page);
  await page.goto("/market");
  await expect(page.locator(".heat-tile")).toHaveCount(3);
  await expect(page.locator(".heat-tile").first()).toContainText("BTC");
  await page.locator(".card", { hasText: "Market heatmap" }).getByRole("radio", { name: "7 days" }).click();
  await expect(page.locator(".heat-tile").first()).toContainText("-1.2%");
  await page.getByRole("button", { name: "Calculate" }).click();
  await expect(page.getByText("Over 30 days, following the model on BTC would have made about $90 more than holding.")).toBeVisible();
});

test("settings: notifications, CSV export, German", async ({ page }) => {
  await register(page);
  await page.goto("/settings");
  await expect(page.getByText("Browser notifications on this device").or(page.getByText("This browser does not support notifications."))).toBeVisible();
  await page.getByLabel("The AI changed its mind").uncheck();
  await expect(page.getByLabel("The AI changed its mind")).not.toBeChecked();
  const csv = await page.request.get("/api/account/export/forecasts.csv");
  expect(csv.ok()).toBeTruthy();
  expect(csv.headers()["content-type"]).toContain("text/csv");
  await page.getByRole("button", { name: "Deutsch" }).click();
  await expect(page.getByRole("heading", { name: "Einstellungen" })).toBeVisible();
});

test("feedback reaches the admin; tipster profiles are public", async ({ page }) => {
  await register(page);
  await page.goto("/dashboard");
  await page.locator(".sidebar .feedback-btn").click({ force: true });
  await page.getByRole("radio", { name: "Idea" }).click();
  await page.getByLabel("Your message").fill("Please add a dark mode for charts");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByText("Thank you! Your message was sent.")).toBeVisible();
  const { ctx } = await ownerSession();
  const list = await (await ctx.get("/api/admin/feedback")).json();
  expect(list.items.some((f) => f.message === "Please add a dark mode for charts" && f.kind === "idea")).toBeTruthy();
  await ctx.dispose();

  await page.goto("/tipster/nobody-here");
  await expect(page.getByText("This profile does not exist or is not public.")).toBeVisible();
});

test("quick view lists followed coins", async ({ page }) => {
  await page.route("**/api/tools/scanner", (route) => route.fulfill({ json: SCANNER }));
  await register(page);
  await page.goto("/quick");
  await expect(page.getByRole("heading", { name: "Quick view" })).toBeVisible();
  await expect(page.locator(".quick-row").first()).toContainText("BTC");
});
