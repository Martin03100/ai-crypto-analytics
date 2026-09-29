import { describe, expect, it } from "vitest";
import { backtestVerdicts } from "../utils/backtest";

describe("backtestVerdicts", () => {
  it("treats coverage near the 80 % target as calibrated", () => {
    expect(backtestVerdicts({ band_coverage_pct: 82.7, mape_pct: 10, naive_mape_pct: 9.6 }).calibrated).toBe(true);
    expect(backtestVerdicts({ band_coverage_pct: 55, mape_pct: 10, naive_mape_pct: 9.6 }).calibrated).toBe(false);
    expect(backtestVerdicts({ band_coverage_pct: 99, mape_pct: 10, naive_mape_pct: 9.6 }).calibrated).toBe(false);
  });

  it("claims an edge over the naive forecast only with a clear margin", () => {
    expect(backtestVerdicts({ band_coverage_pct: 80, mape_pct: 4.41, naive_mape_pct: 4.25 }).beatsNaive).toBe(false);
    expect(backtestVerdicts({ band_coverage_pct: 80, mape_pct: 3.0, naive_mape_pct: 4.25 }).beatsNaive).toBe(true);
  });

  it("is safe with missing data", () => {
    expect(backtestVerdicts(null)).toEqual({ calibrated: false, beatsNaive: false });
  });
});
