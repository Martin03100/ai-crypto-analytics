import { expect, test } from "@playwright/test";
import { prepare, register } from "./helpers";

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

test("links page offers the app, track record, Premium and social placeholders", async ({ page }) => {
  await page.goto("/links");
  await expect(page.getByRole("heading", { name: "AI Crypto Analytics" })).toBeVisible();
  await expect(page.getByText("Instagram · link coming soon")).toBeVisible();
  await page.getByRole("link", { name: "Premium" }).click();
  await expect(page).toHaveURL(/\/premium$/);
  await expect(page.locator("#premium-waitlist")).toBeVisible();
});

test("privacy policy describes analytics and the waitlist", async ({ page }) => {
  await page.goto("/privacy");
  await expect(page.getByRole("heading", { name: "Analytics" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Premium waitlist" })).toBeVisible();
});

test("track record offers sharing and SEO files are served", async ({ page, request }) => {
  await page.goto("/track-record");
  await expect(page.getByRole("link", { name: "Reddit" })).toHaveAttribute("href", /reddit\.com\/submit/);
  await expect(page.getByRole("button", { name: "Copy link" })).toBeVisible();
  expect((await (await request.get("/robots.txt")).text())).toContain("Sitemap:");
  expect((await (await request.get("/sitemap.xml")).text())).toContain("/track-record");
});

test("about page does not mention the thesis", async ({ page }) => {
  await page.goto("/about");
  await expect(page.getByText("student developer from Prague")).toBeVisible();
  await expect(page.locator("body")).not.toContainText(/thesis|Unicorn/i);
});

test("signed-in user gets a bell, membership card, invite link, 4h horizon and new coins", async ({ page }) => {
  await register(page);
  await expect(page.getByRole("button", { name: "Notifications" })).toBeVisible();
  await page.getByRole("button", { name: "Notifications" }).click();
  await expect(page.getByText("Nothing yet.")).toBeVisible();
  await page.goto("/settings");
  await expect(page.getByText("Premium & community")).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Invite friends" })).toHaveValue(/\?ref=[A-Z0-9]{8}$/);
  const nick = `Fox${Date.now().toString(36).slice(-6)}`;
  await page.getByRole("textbox", { name: "Public nickname" }).fill(nick);
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.getByText("Nickname saved.")).toBeVisible();
  await page.getByRole("checkbox", { name: /Weekly "AI vs reality" email/ }).check();
  await page.goto("/track-record");
  await expect(page.getByText("Beat the AI: top tippers")).toBeVisible();
  await page.goto("/forecast");
  await expect(page.locator("select").filter({ has: page.locator('option[value="4h"]') })).toHaveCount(1);
  await expect(page.locator('option[value="PEPE"]').first()).toBeAttached();
});

test("invalid unsubscribe link explains what to do", async ({ page }) => {
  await page.goto("/unsubscribe?u=1&t=short");
  await expect(page.getByText("This unsubscribe link is not valid.")).toBeVisible();
});

test("price alerts, Premium gate and the Premium page", async ({ page }) => {
  await register(page);
  await page.goto("/dashboard");
  await page.getByPlaceholder("Price in USD").fill("1000000");
  await page.getByRole("button", { name: "Add alert" }).click();
  await expect(page.getByText("Alert set. We'll let you know.")).toBeVisible();
  await expect(page.getByText("Active alerts: 1 of 1")).toBeVisible();
  await expect(page.getByRole("button", { name: "Add alert" })).toBeDisabled();

  await page.goto("/forecast?tab=mystats");
  await expect(page.getByText("Your personal accuracy")).toBeVisible();
  await expect(page.getByRole("link", { name: "Unlock with Premium" })).toBeVisible();

  await page.goto("/premium");
  await expect(page.getByRole("heading", { name: /Let the app watch the market for you/ })).toBeVisible();
  await expect(page.getByRole("row", { name: /Active price alerts/ })).toContainText("25");
  await page.getByText("Can I get my money back?").click();
  await expect(page.getByText("within 14 days of your first payment")).toBeVisible();

  await page.goto("/terms");
  await expect(page.getByRole("heading", { name: "Refunds and withdrawal" })).toBeVisible();
  await expect(page.getByText("Operator and data controller")).toBeVisible();
});
