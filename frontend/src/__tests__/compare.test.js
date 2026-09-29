import { describe, expect, it } from "vitest";
import { buildComparisonRows, changePct } from "../utils/compare";

describe("buildComparisonRows", () => {
  it("aligns providers on the same steps and prepends the shared start price", () => {
    const rows = buildComparisonRows([
      { key: "quant", data: { ceny: [101, 102, 103], aktualna_cena: 100 } },
      { key: "gemini", data: { ceny: [99, 98, 97] } },
    ]);
    expect(rows).toEqual([
      { i: 0, quant: 100, gemini: 100 },
      { i: 1, quant: 101, gemini: 99 },
      { i: 2, quant: 102, gemini: 98 },
      { i: 3, quant: 103, gemini: 97 },
    ]);
  });

  it("cuts to the shortest series and skips broken ones", () => {
    const rows = buildComparisonRows([
      { key: "a", data: { ceny: [1, 2, 3] } },
      { key: "b", data: { ceny: [4, 5] } },
      { key: "broken", data: { ceny: [1, NaN] } },
      { key: "empty", data: null },
    ]);
    expect(rows).toEqual([{ i: 1, a: 1, b: 4 }, { i: 2, a: 2, b: 5 }]);
  });

  it("returns nothing when no series is usable", () => {
    expect(buildComparisonRows([{ key: "x", data: {} }])).toEqual([]);
  });
});

describe("changePct", () => {
  it("computes the change from start to the last point", () => {
    expect(changePct({ aktualna_cena: 100, ceny: [105, 110] })).toBeCloseTo(10);
    expect(changePct({ ceny: [1] })).toBeNull();
  });
});
