/** German/Polish, glossary, changelog, calendar helpers, beginner view, heatmap, palette search and push helpers. */

import { beforeAll, describe, expect, it } from "vitest";
import cz from "../i18n/locales/cz.json";
import de from "../i18n/locales/de.json";
import en from "../i18n/locales/en.json";
import pl from "../i18n/locales/pl.json";
import sk from "../i18n/locales/sk.json";
import { localeForLang } from "../i18n/locale";
import { LANGUAGES, loadLanguage, translate } from "../i18n/translations";
import { CHANGELOG, itemsFor } from "../data/changelog";
import { GLOSSARY } from "../data/glossary";
import { daysUntil, eventName, groupByDay } from "../utils/calendar";
import { notificationTarget, notificationText } from "../utils/notifications";
import { sameKey, urlBase64ToUint8Array } from "../utils/pushClient";
import { heatColor, lightFor, matches, parseAmount, tickDirection, tileSize, timelineRows, verdictLight } from "../utils/viewHelpers";

const placeholders = (s) => [...String(s).matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort().join(",");
const LANGS = { en, sk, cs: cz, de, pl };

describe("translations in all five languages", () => {
  beforeAll(async () => { await Promise.all(["de", "pl"].map(loadLanguage)); });
  it("has the same keys and placeholders everywhere", () => {
    for (const [code, dict] of Object.entries(LANGS)) {
      expect(Object.keys(dict).sort(), code).toEqual(Object.keys(en).sort());
      for (const key of Object.keys(en)) expect(placeholders(dict[key]), `${code} ${key}`).toBe(placeholders(en[key]));
    }
  });
  it("offers German and Polish with their own locale", () => {
    expect(LANGUAGES.map((l) => l.code)).toEqual(["en", "sk", "cs", "de", "pl"]);
    expect(translate("common.save", "de")).not.toBe(translate("common.save", "en"));
    expect(translate("common.save", "pl")).not.toBe(translate("common.save", "en"));
    expect(localeForLang("de")).toBe("de-DE");
    expect(localeForLang("pl")).toBe("pl-PL");
  });
});

describe("glossary and changelog", () => {
  it("explains every term in every language", () => {
    expect(GLOSSARY.length).toBeGreaterThanOrEqual(20);
    expect(new Set(GLOSSARY.map((g) => g.id)).size).toBe(GLOSSARY.length);
    for (const g of GLOSSARY) for (const l of Object.keys(LANGS)) {
      expect(g.term[l], `${g.id} ${l}`).toBeTruthy();
      expect(g.def[l].length, `${g.id} ${l}`).toBeGreaterThan(20);
    }
  });
  it("has newest-first entries with growing ids and all languages", () => {
    const ids = CHANGELOG.map((c) => c.id);
    expect([...ids].sort((a, b) => b - a)).toEqual(ids);
    for (const entry of CHANGELOG) for (const l of Object.keys(LANGS)) {
      expect(itemsFor(entry, l).length).toBe(entry.items.en.length);
    }
  });
});

describe("calendar helpers", () => {
  const t = (k, p) => `${k}${p?.coin ? `:${p.coin}` : ""}`;
  it("names events, counts days and groups by day", () => {
    expect(eventName(t, { kind: "unlock", coin: "SUI" })).toBe("calendar.kind_unlock:SUI");
    const now = Date.parse("2026-10-08T12:00:00Z");
    expect(daysUntil("2026-10-10T12:00:00Z", now)).toBe(2);
    expect(daysUntil("2026-10-08T10:00:00Z", now)).toBe(0);
    expect(daysUntil("2026-10-08T23:00:00Z", now)).toBe(0);          // later today is "today", not "tomorrow"
    expect(daysUntil("2026-10-09T01:00:00Z", now)).toBe(1);
    const groups = groupByDay([{ at: "2026-10-14T12:30:00Z" }, { at: "2026-10-14T18:00:00Z" }, { at: "2026-10-28T18:00:00Z" }], "en-GB");
    expect(groups.map((g) => g.items.length)).toEqual([2, 1]);
  });
  it("routes and words the new notifications", () => {
    const tt = (k, p) => `${k}|${JSON.stringify(p || {})}`;
    expect(notificationTarget({ kind: "direction_flip", data: { coin: "ETH" } })).toBe("/forecast?coin=ETH");
    expect(notificationTarget({ kind: "event_reminder", data: {} })).toBe("/calendar");
    expect(notificationTarget({ kind: "forecast_evaluated", data: {} })).toBe("/forecast?tab=history");
    expect(notificationText({ kind: "direction_flip", data: { coin: "ETH", direction: "down", change_pct: -1.2 } }, tt)).toContain("notif.flipDown");
    expect(notificationText({ kind: "event_reminder", data: { title_key: "fomc" } }, tt)).toContain("notif.eventReminder");
  });
});

describe("dashboard helpers", () => {
  it("maps signals and forecasts to traffic lights", () => {
    expect(lightFor("bullish")[0]).toBe("green");
    expect(lightFor("bearish")[0]).toBe("red");
    expect(lightFor("overbought")).toEqual(["amber", "simple.say_overbought"]);
    expect(lightFor(undefined)[0]).toBe("amber");
    expect(verdictLight(2.5)).toBe("green");
    expect(verdictLight(-1)).toBe("red");
    expect(verdictLight(0.4)).toBe("amber");
    expect(verdictLight(null)).toBe("amber");
  });
  it("colours the heatmap and sizes tiles", () => {
    expect(heatColor(5)).toBe("rgba(52, 211, 153, 0.37)");
    expect(heatColor(-25)).toBe("rgba(248, 113, 113, 0.62)");
    expect(heatColor(null)).toBe("var(--bg-inset)");
    expect([0, 1, 2, 5, 6].map(tileSize)).toEqual(["xl", "xl", "md", "md", "sm"]);
  });
  it("detects price ticks and parses amounts", () => {
    expect(tickDirection(1, 2)).toBe("up");
    expect(tickDirection(2, 1)).toBe("down");
    expect(tickDirection(undefined, 1)).toBe("");
    expect(parseAmount("1 000,5")).toBe(1000.5);
    expect(parseAmount("-5")).toBeNull();
    expect(parseAmount("abc")).toBeNull();
  });
  it("builds timeline rows only for models with enough data", () => {
    const data = { weeks: ["2026-W40", "2026-W41"], providers: [
      { provider: "Gemini", n: 5, points: [{ hit_pct: 60 }, { hit_pct: null }] },
      { provider: "Grok", n: 1, points: [{ hit_pct: 100 }, { hit_pct: null }] }] };
    expect(timelineRows(data)).toEqual({ rows: [{ week: "W40", Gemini: 60 }, { week: "W41", Gemini: null }], providers: ["Gemini"] });
  });
  it("matches palette search without accents or word order", () => {
    expect(matches("Nastavenia účtu", "ucet nast")).toBe(false);
    expect(matches("Nastavenia účtu", "uctu nast")).toBe(true);
    expect(matches("Predikcia BTC", "btc")).toBe(true);
  });
  it("decodes the push server key", () => {
    expect(Array.from(urlBase64ToUint8Array("AQID_-8"))).toEqual([1, 2, 3, 255, 239]);
    expect(sameKey(new Uint8Array([1, 2]).buffer, new Uint8Array([1, 2]))).toBe(true);
    expect(sameKey(new Uint8Array([1, 3]).buffer, new Uint8Array([1, 2]))).toBe(false);
    expect(sameKey(null, new Uint8Array([1]))).toBe(true);
  });
});
