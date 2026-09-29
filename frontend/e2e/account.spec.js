import { expect, test } from "@playwright/test";
import { login, prepare, register } from "./helpers";

test.beforeEach(async ({ page }) => prepare(page));

test("sign-up, sign-out, sign-in and the activity log records it", async ({ page, context }) => {
  const username = await register(page);
  await page.getByRole("button", { name: "Log out" }).click();
  await expect(page).toHaveURL(/\/(auth)?$/);
  await context.clearCookies();

  await login(page, username);
  await page.goto("/account");
  const log = page.getByTestId("activity-list");
  await expect(log).toContainText("Account created");
  await expect(log).toContainText("Signed in");
});

test("wrong password is rejected and logged as a failed sign-in", async ({ page, context }) => {
  const username = await register(page);
  await context.clearCookies();
  await page.goto("/auth");
  await page.getByPlaceholder("e.g. satoshi").fill(username);
  await page.locator('input[autocomplete="current-password"]').fill("definitely-wrong-1");
  await page.locator('form button[type="submit"]').click();
  await expect(page.locator(".alert-error")).toBeVisible();

  await login(page, username);
  await page.goto("/account");
  await expect(page.getByTestId("activity-list")).toContainText("Failed sign-in");
});
