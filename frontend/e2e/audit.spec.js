/**
 * Page audit, not a regular test: visits every page with demo data on desktop and phone, in both themes and all
 * languages, and reports console errors, failed requests, axe accessibility violations, horizontal overflow
 * on phones and untranslated keys. Run: AUDIT=1 npx playwright test e2e/audit.spec.js
 */

import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { test } from "@playwright/test";
import { register } from "./helpers";

test.skip(!process.env.AUDIT, "set AUDIT=1 to run the page audit");
test.setTimeout(600_000);

const AXE = readFileSync(createRequire(import.meta.url).resolve("axe-core/axe.min.js"), "utf8");
const PUBLIC = ["/", "/auth", "/about", "/status", "/privacy", "/terms"];
const PRIVATE = ["/dashboard", "/forecast", "/forecast?tab=history", "/forecast?tab=schedule", "/forecast?tab=leaderboard",
  "/forecast?tab=compare", "/forecast?tab=backtest", "/portfolio", "/market", "/account", "/settings"];
// External data the sandboxed CI/dev machine may not reach; their failures are not app bugs.
const IGNORED_REQUEST = /coingecko|alternative\.me|blockchair|reddit|coindesk|cointelegraph|decrypt|challenges\.cloudflare|sentry/i;

const findings = [];
const note = (kind, where, detail) => findings.push(`${kind.padEnd(9)} ${where}  ${detail}`);

async function audit(page, where, { phone }) {
  await page.waitForLoadState("networkidle").catch(() => {});
  await page.waitForTimeout(600);
  if (phone) {
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    if (overflow > 1) note("overflow", where, `page is ${overflow}px wider than the phone screen`);
  }
  const rawKeys = await page.evaluate(() =>
    [...document.body.innerText.matchAll(/\b[a-z]+\.[a-z][A-Za-z0-9]+(?:\.[A-Za-z0-9]+)*\b/g)]
      .map((m) => m[0]).filter((k) => /^(common|nav|forecast|dashboard|schedule|watchlist|pwa|settings|errors|market|portfolio|account)\./.test(k)));
  if (rawKeys.length) note("i18n", where, `raw translation keys: ${[...new Set(rawKeys)].join(", ")}`);
  await page.addScriptTag({ content: AXE });
  const violations = await page.evaluate(async () => {
    const res = await window.axe.run(document, { resultTypes: ["violations"] });
    return res.violations.filter((v) => ["serious", "critical"].includes(v.impact))
      .map((v) => `${v.id} (${v.impact}) x${v.nodes.length}: ${v.nodes.slice(0, 2).map((n) => n.target.join(" ")).join(" | ")}`);
  });
  violations.forEach((v) => note("a11y", where, v));
}

for (const [device, viewport] of [["desktop", { width: 1440, height: 900 }], ["phone", { width: 390, height: 844 }]]) {
  for (const scheme of ["dark", "light"]) {
    test(`audit ${device} ${scheme}`, async ({ page }) => {
      await page.setViewportSize(viewport);
      await page.emulateMedia({ colorScheme: scheme });
      const lang = scheme === "dark" ? "sk" : "en";
      await page.addInitScript((l) => {
        if (!localStorage.getItem("audit_hold_lang")) localStorage.setItem("aca_lang", l);
        localStorage.setItem("aca_onboarding_seen_v1", "1");
        for (let id = 1; id <= 80; id += 1) localStorage.setItem(`aca_onboarding_seen_v1:${id}`, "1");
      }, lang);
      let current = "";
      page.on("console", (msg) => {
        // A signed-out visit asks /auth/me and gets the expected 401; the browser logs that as a failed load.
        if (msg.type() === "error" && !/status of 401/.test(msg.text())) note("console", current, msg.text().slice(0, 200));
      });
      page.on("pageerror", (err) => note("crash", current, err.message.slice(0, 200)));
      page.on("response", (res) => {
        const url = res.url();
        if (res.status() >= 400 && !IGNORED_REQUEST.test(url) && !(res.status() === 401 && url.endsWith("/api/auth/session"))) {
          note("http", current, `${res.status()} ${res.request().method()} ${url.replace(/^https?:\/\/[^/]+/, "")}`);
        }
      });
      const tag = `[${device}/${scheme}/${lang}]`;
      for (const path of PUBLIC) {
        current = `${tag} ${path}`;
        await page.goto(path);
        await audit(page, current, { phone: device === "phone" });
      }
      current = `${tag} register`;
      // The helper fills in English labels, so register in English and switch back afterwards.
      await page.evaluate(() => { localStorage.setItem("audit_hold_lang", "1"); localStorage.setItem("aca_lang", "en"); });
      await register(page);
      await page.evaluate((l) => { localStorage.removeItem("audit_hold_lang"); localStorage.setItem("aca_lang", l); }, lang);
      await page.goto("/settings");
      await page.locator("button", { hasText: /demo/i }).first().click();
      await page.waitForTimeout(2500);
      for (const path of PRIVATE) {
        current = `${tag} ${path}`;
        await page.goto(path);
        await audit(page, current, { phone: device === "phone" });
      }
    });
  }
}

test.afterAll(() => {
  console.log(`\n===== AUDIT: ${findings.length} findings =====\n${findings.join("\n")}\n`);
});
