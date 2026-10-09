/** Translation tests. */

import { beforeAll, describe, expect, it } from "vitest";
import { DEFAULT_LANG, loadLanguage, translate } from "../i18n/translations";

beforeAll(async () => { await Promise.all(["sk", "cs", "de", "pl"].map(loadLanguage)); });

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
    expect(() => translate("badge.confidence", "en", {})).not.toThrow();
  });

  it("uses the right plural form for counted words", () => {
    expect([1, 3, 5].map((n) => translate("calendar.inDays", "sk", { n })))
      .toEqual(["o 1 deň", "o 3 dni", "o 5 dní"]);
    expect([2, 5, 22].map((n) => translate("whatif.days", "pl", { n }))).toEqual(["2 dni", "5 dni", "22 dni"]);
    expect(translate("whatif.days", "cs", { n: 4 })).toBe("4 dny");
    expect(translate("calendar.inDays", "en", { n: 1 })).toBe("in 1 day");
    expect(translate("track.challenge", "sk", { pct: 0, total: 1 })).toContain("z 1 duelu");
    expect(translate("track.challenge", "sk", { pct: 50, total: 4 })).toContain("z 4 duelov");
    expect(translate("calendar.inDays", "de")).toBe("in {n} Tagen");     // no count: the plain text
  });
});
