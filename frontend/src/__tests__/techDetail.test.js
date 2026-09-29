import { describe, expect, it } from "vitest";
import { TECH_DETAIL_MAX_CHARS, formatTechDetail } from "../utils/techDetail";

describe("formatTechDetail", () => {
  it("keeps the tail of long provider errors that used to be cut at 400 chars", () => {
    const msg = "Gemini API chyba: 429 RESOURCE_EXHAUSTED. " + "x".repeat(500) + " limit: 0, model: gemini-flash";
    expect(formatTechDetail(msg)).toContain("limit: 0, model: gemini-flash");
  });

  it("turns escaped newlines into real line breaks", () => {
    expect(formatTechDetail("first\\n* second")).toBe("first\n* second");
  });

  it("caps absurdly long payloads and marks the cut", () => {
    const out = formatTechDetail("a".repeat(TECH_DETAIL_MAX_CHARS + 50));
    expect(out).toHaveLength(TECH_DETAIL_MAX_CHARS + 1);
    expect(out.endsWith("…")).toBe(true);
  });

  it("handles non-string input", () => {
    expect(formatTechDetail(429)).toBe("429");
  });
});
