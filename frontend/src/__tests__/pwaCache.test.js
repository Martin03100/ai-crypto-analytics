import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

// The offline allowlist lives in vite.config.js; evaluate the literal pattern from there.
const source = readFileSync(fileURLToPath(new URL("../../vite.config.js", import.meta.url)), "utf8");
const OFFLINE_API = new Function(`return ${source.match(/const OFFLINE_API = (\/.*\/);/)[1]}`)();

describe("offline API cache allowlist", () => {
  it("caches read-only data the app shows offline", () => {
    for (const path of ["/api/forecast/history?page=1&page_size=20", "/api/forecast/history/12/accuracy",
      "/api/market/prices?ids=bitcoin&vs_currency=usd", "/api/schedules", "/api/account/watchlist"]) {
      expect(OFFLINE_API.test(path), path).toBe(true);
    }
  });

  it("never caches secrets, exports or account internals", () => {
    for (const path of ["/api/account/api-keys", "/api/account/activity", "/api/forecast/history/export.csv",
      "/api/auth/login", "/api/account/api-keys/links", "/api/public/status", "/api/forecast/backtest?coin=BTC",
      "/api/auth/me"]) {
      expect(OFFLINE_API.test(path), path).toBe(false);
    }
  });
});

describe("service worker route", () => {
  it("uses the same inline pattern as the documented allowlist (workbox serialises the function)", () => {
    const literal = source.match(/const OFFLINE_API = (\/.*\/);/)[1];
    expect(source.split(literal).length - 1).toBe(2);
  });
});

describe("offline session window", () => {
  it("reuses the last confirmed account for 24 hours, then forgets it", async () => {
    const store = {};
    globalThis.localStorage = {
      getItem: (k) => (k in store ? store[k] : null), setItem: (k, v) => { store[k] = String(v); }, removeItem: (k) => { delete store[k]; },
    };
    const { OFFLINE_SESSION_MS, offlineSessionUser, rememberOfflineSession } = await import("../pwa");
    rememberOfflineSession({ id: 7, username: "satoshi" }, 1_000);
    expect(offlineSessionUser(1_000 + OFFLINE_SESSION_MS - 1)?.username).toBe("satoshi");
    expect(offlineSessionUser(1_000 + OFFLINE_SESSION_MS + 1)).toBeNull();
    expect(offlineSessionUser(1_000)).toBeNull();   // dropped once expired
  });
});
