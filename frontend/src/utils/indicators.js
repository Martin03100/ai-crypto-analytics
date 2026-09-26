/** Technicke indikatory pre graf na stranke Trh. */

export function emaSeries(values, period) {
  const k = 2 / (period + 1);
  const out = new Array(values.length).fill(null);
  if (values.length < period) return out;
  let ema = values.slice(0, period).reduce((a, b) => a + b, 0) / period;
  out[period - 1] = ema;
  for (let i = period; i < values.length; i++) {
    ema = values[i] * k + ema * (1 - k);
    out[i] = ema;
  }
  return out;
}

/** RSI (Wilderovo vyhladenie): nad 70 = prekupeny, pod 30 = prepredany. */
export function rsiSeries(values, period = 14) {
  const out = new Array(values.length).fill(null);
  if (values.length <= period) return out;
  let gain = 0;
  let loss = 0;
  for (let i = 1; i <= period; i++) {
    const d = values[i] - values[i - 1];
    if (d >= 0) gain += d; else loss -= d;
  }
  gain /= period;
  loss /= period;
  out[period] = loss === 0 ? 100 : 100 - 100 / (1 + gain / loss);
  for (let i = period + 1; i < values.length; i++) {
    const d = values[i] - values[i - 1];
    gain = (gain * (period - 1) + Math.max(d, 0)) / period;
    loss = (loss * (period - 1) + Math.max(-d, 0)) / period;
    out[i] = loss === 0 ? 100 : 100 - 100 / (1 + gain / loss);
  }
  return out;
}

/** MACD (12, 26, 9): linia MACD, signalna linia a histogram. */
export function macdSeries(values, fast = 12, slow = 26, signal = 9) {
  const fastEma = emaSeries(values, fast);
  const slowEma = emaSeries(values, slow);
  const macd = values.map((_, i) => (fastEma[i] != null && slowEma[i] != null ? fastEma[i] - slowEma[i] : null));
  const first = macd.findIndex((v) => v != null);
  const sig = new Array(values.length).fill(null);
  if (first >= 0) emaSeries(macd.slice(first), signal).forEach((v, j) => { sig[first + j] = v; });
  return values.map((_, i) => ({
    macd: macd[i], signal: sig[i], hist: macd[i] != null && sig[i] != null ? macd[i] - sig[i] : null,
  }));
}
