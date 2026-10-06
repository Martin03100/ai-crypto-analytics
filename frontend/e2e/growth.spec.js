import { expect, test } from "@playwright/test";
import { prepare } from "./helpers";

test.beforeEach(async ({ page }) => prepare(page));

test("track record is public and reachable from the landing page", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: "See the live track record" }).click();
  await expect(page).toHaveURL(/\/track-record$/);
  await expect(page.getByRole("heading", { name: "Public track record" })).toBeVisible();
  await expect(page.getByText("Forecasts checked")).toBeVisible();
  await expect(page.getByText("Not financial advice.")).toBeVisible();
});

test("a visitor can join the Premium waitlist without an account", async ({ page }) => {
  await page.goto("/?utm_source=tiktok");
  const form = page.locator("#waitlist");
  await form.getByPlaceholder("your@email.com").fill(`fan${Date.now()}@example.com`);
  await form.getByRole("button", { name: "Join the waitlist" }).click();
  await expect(form.getByRole("status")).toHaveText("You're on the list! We'll email you when Premium launches.");
});

test("links page offers the app, the track record and the waitlist", async ({ page }) => {
  await page.goto("/links");
  await expect(page.getByRole("heading", { name: "AI Crypto Analytics" })).toBeVisible();
  await page.getByRole("link", { name: "Join the Premium waitlist" }).click();
  await expect(page.locator("#waitlist")).toBeInViewport();
});

test("privacy policy describes analytics and the waitlist", async ({ page }) => {
  await page.goto("/privacy");
  await expect(page.getByRole("heading", { name: "Analytics" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Premium waitlist" })).toBeVisible();
});
