import { expect, test } from "@playwright/test";
import { prepare, register } from "./helpers";

test.beforeEach(async ({ page }) => prepare(page));

test("portfolio CSV import fills the holdings and reports skipped rows", async ({ page }) => {
  await register(page);
  await page.goto("/portfolio");
  await page.getByTestId("csv-input").setInputFiles({
    name: "portfolio.csv", mimeType: "text/csv",
    buffer: Buffer.from("coin,amount\nETH,2\nSOL,10\nBTC,not-a-number\n"),
  });
  await expect(page.getByText("Coins imported: 2.")).toBeVisible();
  await expect(page.getByText("Skipped rows with invalid data: 4.")).toBeVisible();
  await expect(page.locator('input[inputmode="decimal"]').first()).toHaveValue("2");
  await expect(page.locator('input[inputmode="decimal"]').nth(1)).toHaveValue("10");
});

test("forecast page offers comparison and backtest tabs", async ({ page }) => {
  await register(page);
  await page.goto("/forecast");
  await page.getByRole("button", { name: "Model comparison" }).click();
  await expect(page.getByRole("group", { name: "Models to compare" })).toContainText("statistical model");
  await expect(page.getByRole("button", { name: "Compare", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Model backtest" }).click();
  await expect(page.getByRole("button", { name: "Run backtest" })).toBeVisible();
});

test("settings link to About and Status pages", async ({ page }) => {
  await register(page);
  await page.goto("/settings");
  await expect(page.getByText("Demo mode")).toBeVisible();
  await page.getByRole("link", { name: "Service status" }).click();
  await expect(page).toHaveURL(/\/status$/);
});
