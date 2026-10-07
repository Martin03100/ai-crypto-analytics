import { expect, test } from "@playwright/test";
import { grantPremium, prepare, register, setAppSettings } from "./helpers";

test.beforeEach(async ({ page }) => prepare(page));

test("with Premium mode off the app looks completely free", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Market scanner" })).toBeVisible();
  await expect(page.locator(".landing-premium")).toHaveCount(0);
  await expect(page.locator(".landing-footer")).not.toContainText("Premium");
  await page.goto("/premium");
  await expect(page).toHaveURL(/\/$/);
  await page.goto("/terms");
  await expect(page.getByText("Operator and data controller")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Refunds and withdrawal" })).toHaveCount(0);

  await register(page);
  await expect(page.getByRole("link", { name: "Premium" })).toHaveCount(0);
  await page.goto("/settings");
  await expect(page.getByText("Profile & community")).toBeVisible();
  await expect(page.getByText(/ambassador badge/)).toBeVisible();
  await expect(page.getByText("Morning briefing (Premium)")).toHaveCount(0);
  await page.goto("/forecast");
  await expect(page.getByRole("button", { name: "My stats" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Simulator" })).toHaveCount(0);
  await page.goto("/dashboard");
  await expect(page.getByRole("tab", { name: "Big move" })).toBeVisible();
  await expect(page.getByText("Market signals")).toBeVisible();
  await expect(page.getByRole("tab", { name: "Fear & Greed" })).toHaveCount(0);
  await page.goto("/market");
  await expect(page.getByText("Market scanner")).toBeVisible();
  await expect(page.getByText("Market signals")).toBeVisible();
  await expect(page.getByText(/more coins in the full scan/)).toHaveCount(0);
});

test.describe.serial("with Premium mode on", () => {
  test.beforeAll(async () => setAppSettings({ premium_mode: true }));
  test.afterAll(async () => setAppSettings({ premium_mode: false }));

  test("a visitor can join the Premium waitlist and open Premium from the links page", async ({ page }) => {
    await page.goto("/?utm_source=tiktok");
    const form = page.locator("#waitlist");
    await form.getByPlaceholder("your@email.com").fill(`fan${Date.now()}@example.com`);
    await form.getByRole("button", { name: "Join the waitlist" }).click();
    await expect(form.getByRole("status")).toHaveText("You're on the list! We'll email you when Premium launches.");
    await page.goto("/links");
    await page.getByRole("link", { name: "Premium" }).click();
    await expect(page).toHaveURL(/\/premium$/);
    await expect(page.locator("#premium-waitlist")).toBeVisible();
  });

  test("free users see the limits, gates and the Premium page", async ({ page }) => {
    await register(page);
    await page.goto("/dashboard");
    await page.getByPlaceholder("Price in USD").fill("1000000");
    await page.getByRole("button", { name: "Add alert" }).click();
    await expect(page.getByText("Alert set. We'll let you know.")).toBeVisible();
    await expect(page.getByText("Active alerts: 1 of 1")).toBeVisible();
    await expect(page.getByRole("button", { name: "Add alert" })).toBeDisabled();
    await page.getByRole("tab", { name: "Fear & Greed" }).click();
    await expect(page.getByText("Fear & Greed alerts are part of Premium.")).toBeVisible();

    await page.goto("/forecast?tab=simulator");
    await expect(page.getByText("Strategy simulator")).toBeVisible();
    await expect(page.getByRole("link", { name: "Unlock with Premium" })).toBeVisible();
    await page.goto("/forecast?tab=mystats");
    await expect(page.getByRole("link", { name: "Unlock with Premium" })).toBeVisible();
    await page.goto("/forecast");
    await expect(page.getByText("Which AI has been most accurate for this coin and horizon?")).toBeVisible();

    await page.goto("/settings");
    await expect(page.getByText("Premium & community")).toBeVisible();
    await expect(page.getByText(/gets a 14-day free trial/)).toBeVisible();

    await page.goto("/premium");
    await expect(page.getByRole("heading", { name: /Your own crypto analyst/ })).toBeVisible();
    await expect(page.getByRole("row", { name: /Active alerts/ })).toContainText("25");
    await expect(page.getByRole("row", { name: /Strategy simulator/ })).toBeVisible();
    await expect(page.getByText("For pros")).toBeVisible();
    await page.getByText("Can I get my money back?").click();
    await expect(page.getByText("within 14 days of your first payment")).toBeVisible();

    await page.goto("/terms");
    await expect(page.getByRole("heading", { name: "Refunds and withdrawal" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Invites" })).toBeVisible();
  });

  test("Premium users get the tracker, smart alerts, smart model hint and the PDF report", async ({ page }) => {
    const username = await register(page);
    await grantPremium(username);
    await page.goto("/portfolio");
    await page.getByRole("button", { name: "P&L tracker" }).click();
    await page.getByLabel("Amount").fill("0.5");
    await page.getByLabel("Avg. buy price (USD)").fill("50000");
    await page.getByRole("button", { name: "Save", exact: true }).click();
    await expect(page.getByText("Position saved.")).toBeVisible();
    await expect(page.getByRole("cell", { name: "BTC" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Download PDF report" })).toHaveAttribute("href", "/api/report.pdf");
    const pdf = await page.request.get("/api/report.pdf");
    expect(pdf.headers()["content-type"]).toBe("application/pdf");

    await page.goto("/dashboard");
    await page.getByRole("tab", { name: "Fear & Greed" }).click();
    await page.getByRole("button", { name: "Add alert" }).click();
    await expect(page.getByText("Fear & Greed falls below 25")).toBeVisible();

    await page.goto("/forecast");
    await expect(page.getByTestId("smart-model")).toBeVisible();
    await page.goto("/forecast?tab=simulator");
    await expect(page.getByRole("button", { name: "Run simulation" })).toBeVisible();
  });
});
