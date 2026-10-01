import { describe, expect, it } from "vitest";
import { detectLang } from "../context/LanguageContext";
import { userTimeZone, weekdayNames } from "../utils/schedule";

describe("schedule display helpers", () => {
  it("knows the browser time zone", () => {
    expect(userTimeZone()).toMatch(/^[A-Za-z_]+(\/[A-Za-z_+-]+)*$|^UTC$/);
  });

  it("names weekdays starting with Monday", () => {
    expect(weekdayNames("en-US")[0]).toBe("Monday");
    expect(weekdayNames("en-US", "short")[6]).toBe("Sun");
  });
});

describe("first-visit language", () => {
  it("follows the browser language when supported", () => {
    expect(detectLang(["sk-SK", "en"])).toBe("sk");
    expect(detectLang(["cs"])).toBe("cs");
    expect(detectLang(["de-DE", "en-US"])).toBe("en");
    expect(detectLang([])).toBe("en");
  });
});
