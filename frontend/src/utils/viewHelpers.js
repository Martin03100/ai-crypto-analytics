/** Pure helpers behind the dashboard widgets (kept out of component files so they can be tested and shared). */

const TIMELINE_MIN_FORECASTS = 3;
const TIMELINE_MAX_MODELS = 7;
const HEAT_CAP_PCT = 10;          // ±10 % and more = full colour
const VERDICT_BAND_PCT = 1;       // moves within ±1 % count as "no clear direction"

/** Rows for the chart: one per week, one column per model (null = no forecasts that week). */
export function timelineRows(data, minTotal = TIMELINE_MIN_FORECASTS) {
  const providers = (data?.providers || []).filter((p) => p.n >= minTotal).slice(0, TIMELINE_MAX_MODELS);
  const rows = (data?.weeks || []).map((week, i) => {
    const row = { week: week.replace(/^\d{4}-/, "") };
    for (const p of providers) row[p.provider] = p.points[i]?.hit_pct ?? null;
    return row;
  });
  return { rows, providers: providers.map((p) => p.provider) };
}

export const OPEN_PALETTE_EVENT = "aca:open-palette";

export function openPalette() {
  window.dispatchEvent(new Event(OPEN_PALETTE_EVENT));
}

/** Case- and accent-insensitive "contains all words" match. */
export function matches(text, query) {
  const norm = (s) => String(s || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  const hay = norm(text);
  return norm(query).split(/\s+/).filter(Boolean).every((w) => hay.includes(w));
}

/** Background tint for a percentage move (green up, red down, stronger for bigger moves). */
export function heatColor(pct) {
  if (pct == null || !Number.isFinite(pct)) return "var(--bg-inset)";
  const strength = Math.min(Math.abs(pct), HEAT_CAP_PCT) / HEAT_CAP_PCT;
  const alpha = (0.12 + strength * 0.5).toFixed(2);
  return pct >= 0 ? `rgba(52, 211, 153, ${alpha})` : `rgba(248, 113, 113, ${alpha})`;
}

/** Tile size class by market-cap rank: the top 2 large, the next 4 medium, the rest small. */
export function tileSize(index) {
  return index < 2 ? "xl" : index < 6 ? "md" : "sm";
}

/** green / amber / red and the sentence key for a scanner signal. */
export function lightFor(signal) {
  switch (signal) {
    case "bullish": return ["green", "simple.say_bullish"];
    case "bearish": return ["red", "simple.say_bearish"];
    case "overbought": return ["amber", "simple.say_overbought"];
    case "oversold": return ["amber", "simple.say_oversold"];
    default: return ["amber", "simple.say_neutral"];
  }
}

export function verdictLight(changePct) {
  if (changePct == null || !Number.isFinite(changePct)) return "amber";
  if (changePct >= VERDICT_BAND_PCT) return "green";
  if (changePct <= -VERDICT_BAND_PCT) return "red";
  return "amber";
}

/** "up" / "down" when a price moved since the last refresh (drives a short highlight), else "". */
export function tickDirection(prev, next) {
  if (prev == null || next == null || prev === next) return "";
  return next > prev ? "up" : "down";
}

export function parseAmount(value) {
  const n = Number(String(value).replace(/\s/g, "").replace(",", "."));
  return Number.isFinite(n) && n > 0 && n <= 10_000_000 ? n : null;
}
