import { expect, test } from "@playwright/test";
import { prepare, register } from "./helpers";

test.beforeEach(async ({ page }) => prepare(page));

const MODELS = ["Claude test", "Gemini test", "OpenAI test", "DeepSeek test", "Custom model test", "Grok test"];

test("demo data fills history, leaderboard, portfolio and dashboard with test models", async ({ page }) => {
  await register(page);
  await page.goto("/settings");
  await page.getByRole("button", { name: "Load demo data" }).click();
  await expect(page.getByText(/Created \d+ forecasts and 8 portfolio analyses\./)).toBeVisible();

  // History opens with generated forecasts of the test models (and a DEMO badge)
  await expect(page).toHaveURL(/tab=history/);
  await expect(page.getByText("DeepSeek test").first()).toBeVisible();
  await expect(page.getByText("DEMO").first()).toBeVisible();

  // A matured forecast shows its real (here: synthetic) outcome as a second line next to the prediction
  await page.getByRole("button", { name: /XRP.*24h.*Claude test/ }).click();
  await expect(page.getByText("Actual price")).toBeVisible();
  await expect(page.getByText(/Accuracy: \d+/)).toBeVisible();

  // Leaderboard ranks all six test models, with the explanation that they are demo rows
  await page.getByRole("button", { name: "AI leaderboard" }).click();
  for (const label of MODELS) await expect(page.getByRole("cell", { name: new RegExp(`^(🏆 )?${label}`) })).toBeVisible();
  await expect(page.getByText("generated demo data on synthetic prices")).toBeVisible();

  // Portfolio history has the generated analyses
  await page.goto("/portfolio");
  await page.getByRole("button", { name: "Saved analyses" }).click();
  await expect(page.getByText(/Gemini test|Claude test|OpenAI test/).first()).toBeVisible();

  // Dashboard shows the latest forecast
  await page.goto("/dashboard");
  await expect(page.getByText("Latest AI forecast")).toBeVisible();
});

test("demo data can be removed again", async ({ page }) => {
  await register(page);
  await page.goto("/settings");
  await page.getByRole("button", { name: "Load demo data" }).click();
  await expect(page).toHaveURL(/tab=history/);
  await page.goto("/settings");
  await page.getByRole("button", { name: "Remove demo data" }).click();
  await page.getByRole("button", { name: "Delete", exact: true }).click();
  await expect(page.getByText(/Demo records removed: 64\./)).toBeVisible();
});
