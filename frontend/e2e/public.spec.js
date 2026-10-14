import { expect, test } from "@playwright/test";
import { prepare } from "./helpers";

test.beforeEach(async ({ page }) => prepare(page));

test("landing page links to the About page", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: "About the project" }).click();
  await expect(page).toHaveURL(/\/about$/);
  await expect(page.getByRole("heading", { name: "About the project" })).toBeVisible();
  await expect(page.getByText("Architecture")).toBeVisible();
});

test("status page reports the backend and database", async ({ page }) => {
  await page.goto("/status");
  await expect(page.getByRole("heading", { name: "Service status" })).toBeVisible();
  await expect(page.getByTestId("status-backend")).toContainText("Operational", { timeout: 30_000 });
  await expect(page.getByTestId("status-database")).toContainText("Operational");
});

test("protected pages redirect to sign-in", async ({ page }) => {
  await page.goto("/forecast");
  await expect(page).toHaveURL(/\/auth$/);
});

test("an unknown address shows a not-found page with a way home", async ({ page }) => {
  await page.goto("/this-page-does-not-exist");
  await expect(page.getByRole("heading", { name: "Page not found" })).toBeVisible();
  await expect(page.locator('meta[name="robots"][content="noindex"]')).toHaveCount(1);
  await page.getByRole("link", { name: "Go to the home page" }).click();
  await expect(page).toHaveURL(/\/$/);
});

test("FAQ answers open on click, carry structured data and link the security page", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: "FAQ" }).click();
  await expect(page.getByRole("heading", { name: "Frequently asked questions" })).toBeVisible();
  await page.getByText("Do I need an AI API key?").click();
  await expect(page.getByText("A free statistical model gives real forecasts right away")).toBeVisible();
  const jsonLd = await page.locator('script[type="application/ld+json"]').last().textContent();
  expect(JSON.parse(jsonLd)["@type"]).toBe("FAQPage");
  await expect(page.locator("body")).not.toContainText("Premium");
  await page.getByText("How do I report a bug or a security problem?").click();
  await page.getByRole("link", { name: "Security and vulnerability reports" }).click();
  await expect(page.getByRole("heading", { name: "How to report" })).toBeVisible();
});

test("unknown share link shows a clear message", async ({ page }) => {
  await page.goto("/share/this-link-does-not-exist-123");
  await expect(page.getByText("This forecast does not exist or is no longer shared.")).toBeVisible();
});

test("coin page accuracy table fits a phone screen and marks small samples", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await page.route("**/api/public/coin/BTC", (route) => route.fulfill({ json: {
    coin: "BTC", name: "Bitcoin", price: 65000, change_24h: 1.2, change_7d: -2.5, change_30d: 4.1, rsi: 55, signal: "neutral",
    outlook: [], signals: [], balance: null, updated_at: null,
    accuracy: [{ provider: "Statistical model", forecasts: 4, hit_pct: 25 }, { provider: "Gemini", forecasts: 40, hit_pct: 55 }],
  } }));
  await page.goto("/de/prognose/bitcoin");
  await expect(page.locator("table.lb-table")).toBeVisible();
  await expect(page.getByTestId("small-sample-note")).toBeVisible();
  await expect(page.locator("table.lb-table tr", { hasText: "25%" }).locator(".few-data")).toHaveCount(1);   // 4 forecasts
  await expect(page.locator("table.lb-table tr", { hasText: "55%" }).locator(".few-data")).toHaveCount(0);   // 40
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);
});
