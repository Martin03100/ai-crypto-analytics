import { describe, expect, it } from "vitest";
import { translate } from "../i18n/translations";
import { groupSignals, signalBalance, signalLabel } from "../utils/signals";

const t = (key, params) => translate(key, "en", params);
const items = [
  { group: "macro", key: "vix", display: "27.5", tone: "bearish", source: "fred" },
  { group: "derivatives", key: "funding", display: "+0.01%", tone: "neutral", source: "binance" },
  { group: "derivatives", key: "long_short", display: "0.70", tone: "bullish", source: "okx" },
  { group: "unknown", key: "x", display: "1", tone: "neutral", source: "?" },
];

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
