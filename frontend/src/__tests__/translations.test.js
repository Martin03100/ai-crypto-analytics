import { describe, expect, it } from "vitest";
import { DEFAULT_LANG, translate } from "../i18n/translations";

describe("translate()", () => {
  it("returns the correct string for each supported language", () => {
    expect(translate("common.save", "en")).toBe("Save");
    expect(translate("common.save", "sk")).toBe("Uložiť");
    expect(translate("common.save", "cs")).toBe("Uložit");
  });

  it("interpolates {params} into the template", () => {
    const result = translate("badge.confidence", "en", { value: 72 });
    expect(result).toBe("Confidence: 72%");
  });

  it("interpolates multiple different params correctly", () => {
    const result = translate("forecast.deleteConfirm", "en", { coin: "BTC" });
    expect(result).toContain("BTC");
  });

  it("falls back to English when the language is unknown", () => {
    expect(translate("common.save", "fr")).toBe(translate("common.save", DEFAULT_LANG));
  });

  it("falls back to the key itself when the key doesn't exist in any dictionary", () => {
    expect(translate("this.key.does.not.exist", "en")).toBe("this.key.does.not.exist");
  });

  it("leaves an unmatched {placeholder} untouched instead of crashing", () => {
    // badge.confidence expects {value} - if we forget to pass it, the app
    // should still render *something* readable, not throw.
    expect(() => translate("badge.confidence", "en", {})).not.toThrow();
  });
});
