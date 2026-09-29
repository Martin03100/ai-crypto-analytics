// Merge several forecasts (one per provider) into rows for a single overlay chart.

export const COMPARE_COLORS = ["var(--cyan-fg)", "var(--amber-fg)", "var(--violet-fg)", "var(--emerald-fg)", "var(--crimson-fg)"];

/**
 * @param {Array<{key: string, data: {ceny: number[], aktualna_cena?: number}}>} series
 * @returns {Array<object>} rows: { i, start?, [key]: price }
 */
export function buildComparisonRows(series) {
  const usable = series.filter((s) => Array.isArray(s?.data?.ceny) && s.data.ceny.length > 0
    && s.data.ceny.every(Number.isFinite));
  if (usable.length === 0) return [];
  const length = Math.min(...usable.map((s) => s.data.ceny.length));
  const start = usable.map((s) => s.data.aktualna_cena).find(Number.isFinite);
  const rows = [];
  if (Number.isFinite(start)) {
    const row = { i: 0 };
    usable.forEach((s) => { row[s.key] = start; });
    rows.push(row);
  }
  for (let idx = 0; idx < length; idx += 1) {
    const row = { i: idx + 1 };
    usable.forEach((s) => { row[s.key] = s.data.ceny[idx]; });
    rows.push(row);
  }
  return rows;
}

export function changePct(data) {
  const start = data?.aktualna_cena;
  const end = Array.isArray(data?.ceny) ? data.ceny[data.ceny.length - 1] : undefined;
  if (!Number.isFinite(start) || !Number.isFinite(end) || start === 0) return null;
  return ((end / start) - 1) * 100;
}
