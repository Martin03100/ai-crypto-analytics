import { expect, test } from "@playwright/test";
import { prepare } from "./helpers";

test.beforeEach(async ({ page }) => prepare(page));

// Google itself cannot be used in tests: the client ID comes from a mocked config and a tiny stand-in for the
// Google Identity Services script renders a button that hands back a fake credential.
const FAKE_GSI = `window.google = { accounts: { id: {
  initialize(o) { window.__gsi = o; },
  renderButton(el) { const b = document.createElement("button"); b.type = "button"; b.textContent = "Continue with Google";
    b.onclick = () => window.__gsi.callback({ credential: "fake-google-credential-0123456789" }); el.appendChild(b); },
} } };`;

test("no Google button while the server has no client ID", async ({ page }) => {
  await page.goto("/auth");
  await expect(page.getByRole("button", { name: "Log in" }).last()).toBeVisible();
  await expect(page.getByTestId("google-signin")).toHaveCount(0);
});

test("Google sign-in asks for the 2FA code when the account has 2FA", async ({ page }) => {
  await page.route("**/api/public/config", async (route) => {
    const res = await route.fetch();
    await route.fulfill({ response: res, json: { ...(await res.json()), google_client_id: "test.apps.googleusercontent.com" } });
  });
  await page.route("https://accounts.google.com/gsi/client", (route) => route.fulfill({ contentType: "text/javascript", body: FAKE_GSI }));
  const bodies = [];
  await page.route("**/api/auth/google", async (route) => {
    bodies.push(route.request().postDataJSON());
    await route.fulfill({ status: 401, headers: { "X-Error-Code": "totp_required", "Access-Control-Expose-Headers": "X-Error-Code" },
      json: { detail: "Zadaj 6-miestny kód z overovacej aplikácie (2FA)." } });
  });
  await page.goto("/auth");
  await page.getByRole("button", { name: "Continue with Google" }).click();
  await expect(page.getByTestId("google-totp")).toBeVisible();
  await page.getByTestId("google-totp").getByPlaceholder("123456").fill("123456");
  await page.getByTestId("google-totp").getByRole("button", { name: "Log in" }).click();
  await expect.poll(() => bodies.length).toBe(2);
  expect(bodies[0]).toMatchObject({ credential: "fake-google-credential-0123456789", lang: "en" });
  expect(bodies[1]).toMatchObject({ credential: "fake-google-credential-0123456789", totp_code: "123456" });
});
