import { expect, test } from "@playwright/test";
import { prepare, register, totpCode } from "./helpers";

test.beforeEach(async ({ page }) => prepare(page));

test("regular users have no admin panel", async ({ page }) => {
  await register(page);
  await expect(page.getByRole("link", { name: "Admin" })).toHaveCount(0);
  await page.goto("/admin");
  await expect(page).toHaveURL(/\/dashboard$/);
});

test("admin turns on 2FA, manages users and switches a feature off", async ({ page, browser }) => {
  await register(page, "e2eadmin");
  await page.goto("/admin");
  await expect(page.getByText("the admin panel needs two-factor authentication")).toBeVisible();

  await page.goto("/settings");
  await page.getByRole("button", { name: "Turn on 2FA" }).click();
  const secret = (await page.locator("code").first().textContent()).trim();
  await page.getByPlaceholder("123456").fill(totpCode(secret));
  await page.getByRole("button", { name: "Confirm and turn on" }).click();
  await expect(page.getByText("2FA is on")).toBeVisible();

  const other = await browser.newPage();
  await prepare(other);
  const member = await register(other);

  await page.getByRole("link", { name: "Admin" }).click();
  await expect(page.getByText("users", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Payments" }).click();
  await expect(page.getByText("Ready to sell?")).toBeVisible();
  await expect(page.getByText("Paste your Stripe secret key below.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Connect Stripe" })).toBeDisabled();
  await page.getByLabel("Stripe secret key").fill("pk_test_wrong");
  await page.getByRole("button", { name: "Connect Stripe" }).click();
  await expect(page.getByText("Paste the secret key from Stripe (starts with sk_live_ or sk_test_).")).toBeVisible();
  await page.getByRole("button", { name: "Settings" }).click();
  await expect(page.getByText("Premium is OFF — the app looks completely free")).toBeVisible();
  await page.getByTestId("premium-mode").check();
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.getByText("Saved.").last()).toBeVisible();
  await expect(page.getByRole("link", { name: "Premium" })).toBeVisible();
  await page.getByRole("button", { name: "Users" }).click();
  await page.getByPlaceholder("Search by username, email or nickname").fill(member);
  const row = page.getByRole("row").filter({ hasText: member });
  await row.getByRole("button", { name: "+30 days Premium" }).click();
  await expect(row).toContainText("Premium until");

  await page.getByRole("button", { name: "Settings" }).click();
  await page.getByRole("checkbox", { name: "AI chat" }).uncheck();
  await page.getByLabel("Text shown at the top of the app and the landing page (empty = hidden)").fill("Launch week: Premium free for invites!");
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.getByText("Saved.").last()).toBeVisible();

  await other.reload();
  await expect(other.getByText("Launch week: Premium free for invites!")).toBeVisible();
  await expect(other.locator(".fab-chat")).toHaveCount(0);

  await page.getByRole("checkbox", { name: "AI chat" }).check();
  await page.getByTestId("premium-mode").uncheck();
  await page.getByLabel("Text shown at the top of the app and the landing page (empty = hidden)").fill("");
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.getByText("Saved.").last()).toBeVisible();
  await other.close();
});
