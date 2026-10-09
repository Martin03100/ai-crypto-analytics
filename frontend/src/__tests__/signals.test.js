import { beforeAll, describe, expect, it } from "vitest";
import { loadLanguage, translate } from "../i18n/translations";
import { groupSignals, signalBalance, signalLabel } from "../utils/signals";

const t = (key, params) => translate(key, "en", params);
const items = [
  { group: "macro", key: "vix", display: "27.5", tone: "bearish", source: "fred" },
  { group: "derivatives", key: "funding", display: "+0.01%", tone: "neutral", source: "binance" },
  { group: "derivatives", key: "long_short", display: "0.70", tone: "bullish", source: "okx" },
  { group: "unknown", key: "x", display: "1", tone: "neutral", source: "?" },
];

beforeAll(async () => { await Promise.all(["sk", "cs", "de", "pl"].map(loadLanguage)); });

describe("market signals", () => {
  it("groups in a fixed order and drops unknown groups", () => {
    expect(groupSignals(items).map(([g, rows]) => [g, rows.length])).toEqual([["derivatives", 2], ["macro", 1]]);
  });

  it("labels keys and counts the balance", () => {
    expect(signalLabel(items[0], t)).toBe("VIX (fear index)");
    expect(signalLabel({ key: "new_metric" }, t)).toBe("new_metric");
    expect(signalBalance(items)).toEqual({ bullish: 1, bearish: 1, neutral: 2 });
  });
});

describe("localized rows", () => {
  it("phrases calendar and prediction markets in the reader's language", async () => {
    const { signalText } = await import("../utils/signals");
    const sk = (key, params) => translate(key, "sk", params);
    expect(signalText({ key: "event", display: "x", meta: { name: "Rozhodnutie Fedu", days: 3 } }, sk)).toBe("Rozhodnutie Fedu · o 3 dni");
    expect(signalText({ key: "event", display: "x", meta: { name: "CPI", days: 1 } }, t)).toBe("CPI · tomorrow");
    expect(signalText({ key: "polymarket", display: "x", meta: { question: "BTC 150k?", yes: 23 } }, sk)).toBe("BTC 150k? · 23 % áno");
    expect(signalText({ key: "regulator_news", display: "SEC news" }, t)).toBe("SEC news");
  });

  it("translates the price period", async () => {
    const { localizePriceLabel } = await import("../utils/price");
    const cs = (key, params) => translate(key, "cs", params);
    expect(localizePriceLabel("€4.99 / month", cs)).toBe("€4.99 / měsíc");
    expect(localizePriceLabel("129 Kč / year", cs)).toBe("129 Kč / rok");
    expect(localizePriceLabel(undefined, cs)).toBeUndefined();
  });

  it("shows value periods in the reader's language", async () => {
    const { localizeDisplay } = await import("../utils/signals");
    const sk = (key, params) => translate(key, "sk", params);
    expect(localizeDisplay("+2.8% 1m", sk)).toBe("+2.8% 1 mes.");
    expect(localizeDisplay("5.28% (+0.45 1m)", sk)).toBe("5.28% (+0.45 1 mes.)");
    expect(localizeDisplay("3.7% y/y", sk)).toBe("3.7% medziročne");
    expect(localizeDisplay("$2.78T (-4.8% 24h)", sk)).toBe("$2.78T (-4.8% 24 h)");
    expect(localizeDisplay("+0.0450% / 8h", sk)).toBe("+0.0450% / 8 h");
    expect(localizeDisplay("0% long", sk)).toBe("0 % longov");
    expect(localizeDisplay("27.5", t)).toBe("27.5");
  });
});
