import { describe, expect, it } from "vitest";
import { shareTargets } from "../utils/share";

describe("shareTargets", () => {
  it("builds encoded share links for each network", () => {
    const targets = shareTargets("https://example.com/track-record?a=1&b=2", "Which AI wins? 100% & more");
    expect(targets.map((t) => t.id)).toEqual(["x", "reddit", "telegram", "whatsapp"]);
    for (const { href } of targets) {
      expect(href.startsWith("https://")).toBe(true);
      expect(href).not.toContain("a=1&b=2");
      expect(href).not.toContain(" & ");
    }
    expect(decodeURIComponent(targets[0].href)).toContain("https://example.com/track-record?a=1&b=2");
  });
});
