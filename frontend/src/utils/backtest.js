// Plain-language reading of backtest numbers. Kept pure so it is unit tested.

// An 80 % band is "calibrated" if it held the real price in roughly 70–90 % of cases.
export const CALIBRATION_RANGE = [70, 90];

export function backtestVerdicts(result) {
  const coverage = Number(result?.band_coverage_pct);
  const mape = Number(result?.mape_pct);
  const naive = Number(result?.naive_mape_pct);
  return {
    calibrated: Number.isFinite(coverage) && coverage >= CALIBRATION_RANGE[0] && coverage <= CALIBRATION_RANGE[1],
    // Require a clear margin: tiny differences are noise, not skill.
    beatsNaive: Number.isFinite(mape) && Number.isFinite(naive) && mape < naive * 0.95,
  };
}
