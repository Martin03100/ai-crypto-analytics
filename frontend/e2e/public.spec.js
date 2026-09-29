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

test("unknown share link shows a clear message", async ({ page }) => {
  await page.goto("/share/this-link-does-not-exist-123");
  await expect(page.getByText("This forecast does not exist or is no longer shared.")).toBeVisible();
});
