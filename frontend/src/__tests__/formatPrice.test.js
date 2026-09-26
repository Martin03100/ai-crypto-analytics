import { describe, expect, it } from "vitest";
import { axisDecimals, buildTimePoints, formatPrice, parseServerDate } from "../utils/formatPrice";

describe("formatPrice / axisDecimals", () => {
  it("shows enough decimals to see small moves", () => {
    expect(formatPrice(84123.456)).toBe("$84,123.46");
    expect(formatPrice(1.5)).toBe("$1.50");
    expect(formatPrice(0.451234)).toBe("$0.451234");
  });
  it("picks axis decimals from the chart range", () => {
    expect(axisDecimals(84000, 84400)).toBe(0);
    expect(axisDecimals(0.45, 0.47)).toBe(4);
  });
});

describe("parseServerDate / buildTimePoints", () => {
  it("treats timezone-less server timestamps as UTC", () => {
    expect(parseServerDate("2026-09-26T07:00:00").toISOString()).toBe("2026-09-26T07:00:00.000Z");
    expect(parseServerDate("2026-09-26T07:00:00+00:00").toISOString()).toBe("2026-09-26T07:00:00.000Z");
  });
  it("builds real time points from creation time (24h: 7:00 -> 7:00 next day)", () => {
    const pts = buildTimePoints("2026-09-26T07:00:00Z", "24h", 24);
    expect(pts).toHaveLength(25);
    expect(pts[24].getTime() - pts[0].getTime()).toBe(24 * 3600000);
    expect(buildTimePoints("2026-09-26T07:00:00Z", "1R", 12)).toHaveLength(13);
  });
  it("clamps month-end dates (31 Jan + 1 month = end of February)", () => {
    const pts = buildTimePoints(new Date(2026, 0, 31, 12), "1R", 2);
    expect([pts[1].getMonth(), pts[1].getDate()]).toEqual([1, 28]);
    expect([pts[2].getMonth(), pts[2].getDate()]).toEqual([2, 31]);
  });
});
