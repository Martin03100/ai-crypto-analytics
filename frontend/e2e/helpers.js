import { createHmac } from "node:crypto";
import { expect } from "@playwright/test";

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
