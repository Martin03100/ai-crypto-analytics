import { expect, test } from "@playwright/test";
import { prepare, register } from "./helpers";

test.beforeEach(async ({ page }) => prepare(page));

test("a scheduled forecast appears in the list and on the dashboard", async ({ page }) => {
  await register(page);
  await page.goto("/forecast?tab=schedule");
  await page.getByRole("radio", { name: "Daily" }).click();
  await page.getByLabel("Cryptocurrency").selectOption("ETH");
  await page.getByRole("button", { name: "Create schedule" }).click();
  await expect(page.getByText("Forecast scheduled.")).toBeVisible();
  await expect(page.getByText(/Every day at/)).toBeVisible();
  await expect(page.getByText("Your schedules · 1/20")).toBeVisible();     // Premium off: everyone has the higher limit

  await page.getByRole("button", { name: "Pause" }).click();
  await expect(page.getByText(/paused/)).toBeVisible();
  await page.getByRole("button", { name: "Resume" }).click();

  await page.goto("/dashboard");
  await expect(page.getByText("Scheduled forecasts")).toBeVisible();
  await expect(page.getByText("ETH · 1 week")).toBeVisible();
});

test("watchlist can be edited and the history exports to CSV", async ({ page }) => {
  await register(page);
  await page.goto("/dashboard");
  await expect(page.getByRole("link", { name: /^BTC/ })).toBeVisible();
  await page.getByRole("button", { name: "Edit" }).click();
  await page.getByRole("button", { name: "LINK", exact: true }).click();
  await page.getByRole("button", { name: "Done" }).click();
  await page.reload();
  await expect(page.getByRole("link", { name: /^LINK/ })).toBeVisible();

  await page.goto("/settings");
  await page.getByRole("button", { name: "Load demo data" }).click();
  await page.getByText(/Created \d+ forecasts/).waitFor();
  await page.goto("/forecast?tab=history");
  const download = page.waitForEvent("download");
  await page.getByRole("link", { name: "Export CSV" }).click();
  expect((await download).suggestedFilename()).toBe("forecast-history.csv");
});

test("phone layout uses the bottom tab bar", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await register(page);
  const nav = page.getByRole("navigation", { name: "Main navigation" }).last();
  await nav.getByRole("link", { name: "Market" }).click();
  await expect(page).toHaveURL(/\/market/);
  await nav.getByRole("button", { name: "More" }).click();
  await expect(page.getByRole("link", { name: "Settings" })).toBeVisible();
});
