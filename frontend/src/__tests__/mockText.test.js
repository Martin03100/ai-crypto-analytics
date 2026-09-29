import { describe, expect, it } from "vitest";
import { stripMockTag } from "../utils/mockText";

describe("stripMockTag", () => {
  it("removes leading demo tags", () => {
    expect(stripMockTag("[SAMPLE DATA] Hello")).toBe("Hello");
    expect(stripMockTag("[MOCK] Keep an eye")).toBe("Keep an eye");
    expect(stripMockTag("[dummy]   Neutral")).toBe("Neutral");
  });
  it("leaves normal text and non-strings alone", () => {
    expect(stripMockTag("Neutral")).toBe("Neutral");
    expect(stripMockTag("Price [MOCK] later")).toBe("Price [MOCK] later");
    expect(stripMockTag(undefined)).toBeUndefined();
  });
});
