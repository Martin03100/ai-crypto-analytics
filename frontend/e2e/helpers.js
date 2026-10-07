import { createHmac } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { expect, request } from "@playwright/test";

export const PASSWORD = "E2e-Passw0rd!";

export function uniqueUsername() {
  return `e2e${Date.now().toString(36)}${Math.floor(Math.random() * 1e4)}`;
}

// English UI and no onboarding tour, so tests read stable texts and nothing covers the page.
export async function prepare(page) {
  await page.addInitScript(() => {
    localStorage.setItem("aca_lang", "en");
    localStorage.setItem("aca_onboarding_seen_v1", "1");
    for (let id = 1; id <= 50; id += 1) localStorage.setItem(`aca_onboarding_seen_v1:${id}`, "1");
  });
}

export async function register(page, username = uniqueUsername()) {
  await page.goto("/auth");
  await page.locator(".tabs").getByRole("button", { name: "Sign up" }).click();
  await page.getByPlaceholder("e.g. satoshi").fill(username);
  await page.getByPlaceholder("you@email.com").fill(`${username}@example.com`);
  const passwords = page.locator('input[autocomplete="new-password"]');
  await passwords.nth(0).fill(PASSWORD);
  await passwords.nth(1).fill(PASSWORD);
  await page.locator('form button[type="submit"]').click();
  await expect(page).not.toHaveURL(/\/auth/);
  return username;
}

export async function login(page, username) {
  await page.goto("/auth");
  await page.getByPlaceholder("e.g. satoshi").fill(username);
  await page.locator('input[autocomplete="current-password"]').fill(PASSWORD);
  await page.locator('form button[type="submit"]').click();
  await expect(page).not.toHaveURL(/\/auth/);
}

/** RFC 6238 code for a base32 secret, as an authenticator app would show it. */
export function totpCode(secret, now = Date.now()) {
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
  let bits = "";
  for (const ch of secret.replace(/=+$/, "").toUpperCase()) bits += alphabet.indexOf(ch).toString(2).padStart(5, "0");
  const key = Buffer.from(bits.match(/.{8}/g).map((b) => parseInt(b, 2)));
  const counter = Buffer.alloc(8);
  counter.writeBigUInt64BE(BigInt(Math.floor(now / 30000)));
  const hmac = createHmac("sha1", key).update(counter).digest();
  const offset = hmac[hmac.length - 1] & 0xf;
  return String((hmac.readUInt32BE(offset) & 0x7fffffff) % 1_000_000).padStart(6, "0");
}

const OWNER = "e2eowner";
const OWNER_FILE = path.join(os.tmpdir(), "aca-e2e-owner-secret.txt");

async function csrf(ctx) {
  await ctx.get("/api/health");
  return (await ctx.storageState()).cookies.find((c) => c.name === "aca_csrf")?.value;
}

/** API session of a second admin account (with 2FA) used to change settings from tests. */
export async function ownerSession() {
  const ctx = await request.newContext({ baseURL: "http://localhost:5173" });
  let token = await csrf(ctx);
  let secret = null;
  try { secret = readFileSync(OWNER_FILE, "utf8").trim(); } catch { /* first run */ }
  const login = () => ctx.post("/api/auth/login", { headers: { "X-CSRF-Token": token },
    data: { username: OWNER, password: PASSWORD, totp_code: totpCode(secret) } });
  let res = secret ? await login() : null;
  if (res && !res.ok() && /u[zž] bol pou[zž]it/i.test(await res.text())) {
    await new Promise((r) => { setTimeout(r, 30_500 - (Date.now() % 30_000)); });   // one code per 30 s window
    res = await login();
  }
  if (!res?.ok()) {
    res = await ctx.post("/api/auth/register", { headers: { "X-CSRF-Token": token },
      data: { username: OWNER, password: PASSWORD, email: `${OWNER}@example.com` } });
    expect(res.ok(), await res.text()).toBeTruthy();
    token = await csrf(ctx);
    secret = (await (await ctx.post("/api/account/2fa/setup", { headers: { "X-CSRF-Token": token } })).json()).secret;
    const enabled = await ctx.post("/api/account/2fa/enable", { headers: { "X-CSRF-Token": token }, data: { code: totpCode(secret) } });
    expect(enabled.ok(), await enabled.text()).toBeTruthy();
    writeFileSync(OWNER_FILE, secret);
  }
  return { ctx, headers: { "X-CSRF-Token": await csrf(ctx) } };
}

/** e.g. setAppSettings({ premium_mode: true }) */
export async function setAppSettings(values) {
  const { ctx, headers } = await ownerSession();
  const saved = await ctx.put("/api/admin/settings", { headers, data: { values } });
  expect(saved.ok(), await saved.text()).toBeTruthy();
  await ctx.dispose();
}

export async function grantPremium(username, days = 30) {
  const { ctx, headers } = await ownerSession();
  const found = await (await ctx.get(`/api/admin/users?q=${encodeURIComponent(username)}`)).json();
  const id = found.items.find((u) => u.username === username).id;
  const res = await ctx.patch(`/api/admin/users/${id}`, { headers, data: { add_premium_days: days } });
  expect(res.ok(), await res.text()).toBeTruthy();
  await ctx.dispose();
}
