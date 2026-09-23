import { describe, expect, it } from "vitest";
import { localeForLang } from "../i18n/locale";

describe("localeForLang()", () => {
  it("maps each supported app language to the correct Intl locale", () => {
    expect(localeForLang("en")).toBe("en-US");
    expect(localeForLang("sk")).toBe("sk-SK");
    expect(localeForLang("cs")).toBe("cs-CZ");
  });

  it("falls back to en-US for an unknown language code", () => {
    expect(localeForLang("xx")).toBe("en-US");
    expect(localeForLang(undefined)).toBe("en-US");
  });
});
