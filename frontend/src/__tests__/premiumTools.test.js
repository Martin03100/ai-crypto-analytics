import { describe, expect, it } from "vitest";
import { translate } from "../i18n/translations";
import { humanizeError } from "../i18n/errorMessages";
import { alertLabel, alertValue } from "../utils/alerts";
import { QUANT_LABEL, consensusInput, providerForLabel } from "../utils/models";
import { notificationText } from "../utils/notifications";

const t = (key, params) => translate(key, "en", params);

describe("smart alerts", () => {
  it("formats values per kind", () => {
    expect(alertValue("price", 101500)).toBe("$101,500.00");
    expect(alertValue("move", 7.25)).toBe("+7.3 %");
    expect(alertValue("move", -5)).toBe("-5.0 %");
    expect(alertValue("rsi", 71.6)).toBe("72");
    expect(alertValue("fear_greed", "x")).toBe("—");
  });

  it("describes each alert kind", () => {
    expect(alertLabel({ kind: "move", coin: "SOL", direction: "below", target_price: 8 }, t)).toBe("SOL down more than 8 % in 24h");
    expect(alertLabel({ kind: "rsi", coin: "BTC", direction: "above", target_price: 70 }, t)).toBe("BTC RSI rises above 70");
    expect(alertLabel({ kind: "fear_greed", coin: "ALL", direction: "below", target_price: 25 }, t)).toBe("Fear & Greed falls below 25");
  });

  it("notification texts use the alert kind", () => {
    expect(notificationText({ kind: "price_alert", data: { alert_kind: "move", coin: "ETH", price: -9.04 } }, t)).toBe("🔔 ETH moved -9.0 % in 24 hours.");
    expect(notificationText({ kind: "price_alert", data: { alert_kind: "fear_greed", coin: "ALL", price: 12 } }, t)).toBe("🔔 Fear & Greed index is at 12.");
    expect(notificationText({ kind: "price_alert", data: { alert_kind: "price", coin: "BTC", direction: "above", price: 100 } }, t))
      .toBe("🔔 BTC rose above your alert — now $100.00.");
  });
});

describe("models", () => {
  const providers = [{ provider: "gemini", label: "Gemini", connected: true }, { provider: "quant", label: "Statistical model" }];

  it("maps stored model names to providers", () => {
    expect(providerForLabel(QUANT_LABEL, providers).provider).toBe("quant");
    expect(providerForLabel("Gemini", providers).provider).toBe("gemini");
    expect(providerForLabel("Grok (xAI)", providers)).toBeUndefined();
  });

  it("builds consensus input only from complete forecasts", () => {
    const series = [
      { key: "quant", label: "Statistical", data: { aktualna_cena: 100, ceny: [101, 103] } },
      { key: "gemini", label: "Gemini", data: { aktualna_cena: 100, ceny: [99] } },
      { key: "openai", label: "OpenAI", data: { ceny: [1] } },
    ];
    expect(consensusInput(series)).toEqual([{ model: QUANT_LABEL, start: 100, final: 103 }, { model: "Gemini", start: 100, final: 99 }]);
  });
});

describe("new backend messages", () => {
  it("are translated", () => {
    expect(humanizeError("Hodnota alarmu je mimo povoleného rozsahu.", "en")).toBe("Enter a value in the allowed range.");
    expect(humanizeError("Môžeš sledovať najviac 30 mincí.", "sk")).toBe("Môžeš sledovať najviac 30 mincí.");
    expect(humanizeError("Pre tento model zatiaľ nie je dosť vyhodnotených predikcií.", "cs")).toContain("ověřených");
  });
});
