/** Security and translation tests. */

import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import en from "../i18n/locales/en.json";
import sk from "../i18n/locales/sk.json";
import cz from "../i18n/locales/cz.json";
import { humanizeError } from "../i18n/errorMessages";

describe("safeUrl", () => {
  beforeEach(() => { vi.stubGlobal("window", { location: { origin: "https://app.example" } }); });
  afterEach(() => { vi.unstubAllGlobals(); });

  it("allows only http(s) links", async () => {
    const { safeUrl } = await import("../utils/safeUrl");
    expect(safeUrl("https://coindesk.com/a?b=1")).toBe("https://coindesk.com/a?b=1");
    expect(safeUrl("http://x.example/")).toBe("http://x.example/");
    expect(safeUrl("javascript:alert(1)")).toBe("");
    expect(safeUrl("  JaVaScRiPt:alert(1)")).toBe("");
    expect(safeUrl("data:text/html,<script>1</script>")).toBe("");
    expect(safeUrl("")).toBe("");
    expect(safeUrl(null)).toBe("");
  });
});

describe("api session handling", () => {
  let events;
  beforeEach(() => {
    events = [];
    vi.stubGlobal("window", { dispatchEvent: (e) => events.push(e.type), location: { origin: "https://app.example" } });
    vi.stubGlobal("document", { cookie: "aca_csrf=tok" });
    vi.stubGlobal("localStorage", { getItem: () => "en" });
  });
  afterEach(() => { vi.unstubAllGlobals(); });

  const respond = (status, body = {}, headers = {}) =>
    vi.fn().mockResolvedValue({ ok: status < 400, status, json: async () => body, headers: { get: (k) => headers[k] ?? null } });

  it("signals an expired session on 401 from a normal endpoint", async () => {
    const { api, SESSION_EXPIRED_EVENT } = await import("../api");
    vi.stubGlobal("fetch", respond(401, { detail: "Neplatne alebo expirovane prihlasenie." }));
    await expect(api.listApiKeys()).rejects.toMatchObject({ status: 401 });
    expect(events).toContain(SESSION_EXPIRED_EVENT);
  });

  it("does NOT log the user out on a wrong password, /auth/me or a failed 2FA prompt", async () => {
    const { api } = await import("../api");
    vi.stubGlobal("fetch", respond(401, { detail: "Nespravne pouzivatelske meno alebo heslo." }));
    await expect(api.login("a", "b")).rejects.toBeTruthy();
    await expect(api.me()).rejects.toBeTruthy();
    expect(events).toEqual([]);
  });

  it("exposes the machine-readable error code", async () => {
    const { api } = await import("../api");
    vi.stubGlobal("fetch", respond(401, { detail: "x" }, { "X-Error-Code": "totp_required" }));
    await expect(api.login("a", "b")).rejects.toMatchObject({ code: "totp_required" });
  });

  it("sends the CSRF header on mutating requests only", async () => {
    const { api } = await import("../api");
    const f = respond(200, {});
    vi.stubGlobal("fetch", f);
    await api.logout();
    await api.me();
    expect(f.mock.calls[0][1].headers["X-CSRF-Token"]).toBe("tok");
    expect(f.mock.calls[1][1].headers["X-CSRF-Token"]).toBeUndefined();
  });
});

describe("translations", () => {
  const keys = Object.keys(en);
  const placeholders = (s) => [...s.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort().join(",");

  it("all three languages have exactly the same keys", () => {
    expect(Object.keys(sk).sort()).toEqual(keys.slice().sort());
    expect(Object.keys(cz).sort()).toEqual(keys.slice().sort());
  });

  it("placeholders match across languages", () => {
    for (const k of keys) {
      expect(placeholders(sk[k]), k).toBe(placeholders(en[k]));
      expect(placeholders(cz[k]), k).toBe(placeholders(en[k]));
    }
  });

  it("every t('...') key used in the source exists (no raw keys shown to users)", () => {
    const walk = (dir) => readdirSync(dir).flatMap((f) => {
      const p = join(dir, f);
      if (statSync(p).isDirectory()) return f === "__tests__" ? [] : walk(p);
      return /\.(jsx?|js)$/.test(f) ? [p] : [];
    });
    const root = fileURLToPath(new URL("..", import.meta.url));
    const used = new Set();
    for (const file of walk(root)) {
      for (const m of readFileSync(file, "utf8").matchAll(/\bt\(\s*"([\w.]+)"/g)) used.add(m[1]);
    }
    expect([...used].filter((k) => !(k in en))).toEqual([]);
  });
});

describe("new backend error messages are translated", () => {
  it("maps username, unverified forecast and quant-unavailable errors", () => {
    expect(humanizeError("Používateľské meno musí mať 3–32 znakov: písmená", "en")).toBe(en["errors.usernameInvalid"]);
    expect(humanizeError("Predikciu sa nepodarilo overiť. Vygeneruj ju znova", "sk")).toBe(sk["errors.forecastUnverified"]);
    expect(humanizeError("Nedostatok historickych dat na odhad volatility.", "cs")).toBe(cz["errors.quantUnavailable"]);
  });
});

describe("AI provider errors are attributed to the provider", () => {
  it("does not blame our server for a Gemini 500 and explains a used-up daily quota", () => {
    expect(humanizeError("Gemini API chyba: 500 INTERNAL. {'error': {'code': 500}}", "en")).toBe(en["errors.providerServerError"]);
    expect(humanizeError("Gemini API chyba: 429 RESOURCE_EXHAUSTED quotaId: GenerateRequestsPerDayPerProjectPerModel-FreeTier", "sk"))
      .toBe(sk["errors.providerDailyQuota"]);
    expect(humanizeError("Gemini API chyba: 503 UNAVAILABLE. The model is overloaded.", "en")).toBe(en["errors.providerOverloaded"]);
  });
});
