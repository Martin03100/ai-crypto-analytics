import { describe, expect, it } from "vitest";
import { emaSeries, macdSeries, rsiSeries } from "../utils/indicators";

describe("technical indicators", () => {
  it("RSI is 100 for a steady rise and ~50 for a zigzag", () => {
    expect(rsiSeries(Array.from({ length: 30 }, (_, i) => 100 + i))[29]).toBe(100);
    const zig = rsiSeries(Array.from({ length: 40 }, (_, i) => (i % 2 ? 101 : 100)))[39];
    expect(zig).toBeGreaterThan(40);
    expect(zig).toBeLessThan(60);
  });
  it("EMA of a constant series equals the constant", () => {
    expect(emaSeries(Array(20).fill(5), 10)[19]).toBe(5);
  });
  it("MACD of a constant series is zero once warmed up", () => {
    const m = macdSeries(Array(60).fill(10));
    expect(m[10].macd).toBeNull();
    expect(m[59].macd).toBe(0);
    expect(m[59].hist).toBe(0);
  });
});
