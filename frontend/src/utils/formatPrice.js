/** Formatovanie cien a casov pre grafy AI predikcii. */

/** Presna cena pre texty a tooltipy - vzdy dost desatinnych miest, aby bolo
 * vidiet aj male zmeny ($84,123.46 namiesto predosleho $84.1k). */
export function formatPrice(v) {
  if (v == null || !Number.isFinite(Number(v))) return "";
  const n = Number(v);
  const abs = Math.abs(n);
  const max = abs >= 1000 ? 2 : abs >= 1 ? 4 : abs >= 0.01 ? 6 : 8;
  return "$" + n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: max });
}

/** Pocet desatinnych miest pre popisky osi Y podla rozpatia grafu - aby sa
 * susedne popisky navzajom lisili (24h graf BTC: $84,120 vs $84,180;
 * ADA: $0.4512 vs $0.4530). */
export function axisDecimals(min, max) {
  const span = Math.abs(max - min) || Math.abs(max) * 0.01 || 1;
  return Math.min(8, Math.max(0, Math.ceil(-Math.log10(span / 5)) + 1));
}

export function priceAxisDecimals(rows, key = "price") {
  const values = (rows || []).map((r) => Number(r?.[key])).filter(Number.isFinite);
  if (!values.length) return 2;
  return axisDecimals(Math.min(...values), Math.max(...values));
}

export function formatUsd(v, decimals) {
  if (v == null || !Number.isFinite(Number(v))) return "";
  return "$" + Number(v).toLocaleString("en-US", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

/** Server posiela UTC cas - ak chyba casove pasmo, doplni "Z". Inak by ho
 * prehliadac povazoval za lokalny cas (v Prahe posun o 1-2 hodiny). */
export function parseServerDate(value) {
  if (!value) return null;
  if (value instanceof Date) return value;
  const s = String(value);
  const d = new Date(/[zZ]$|[+-]\d{2}:?\d{2}$/.test(s) ? s : `${s}Z`);
  return Number.isNaN(d.getTime()) ? null : d;
}

const HORIZON_UNIT = { "24h": "hour", "1T": "day", "1M": "day", "1R": "month" };

/** Skutocne casy bodov predikcie: [cas vytvorenia, +1 jednotka, ..., +count].
 * Napr. 24h predikcia vytvorena o 7:00 -> 7:00, 8:00, ..., 7:00 nasledujuci den. */
export function buildTimePoints(createdAt, horizon, count) {
  const start = parseServerDate(createdAt);
  if (!start || !count) return null;
  const unit = HORIZON_UNIT[horizon] || "day";
  return Array.from({ length: count + 1 }, (_, i) => {
    const d = new Date(start.getTime());
    if (unit === "hour") d.setTime(start.getTime() + i * 3600000);
    else if (unit === "day") d.setDate(d.getDate() + i);
    else {
      // 31. januar + 1 mesiac = 28. februar (nie 3. marec)
      const day = start.getDate();
      d.setDate(1);
      d.setMonth(start.getMonth() + i);
      d.setDate(Math.min(day, new Date(d.getFullYear(), d.getMonth() + 1, 0).getDate()));
    }
    return d;
  });
}

export function formatTimeShort(date, horizon, locale) {
  const unit = HORIZON_UNIT[horizon] || "day";
  if (unit === "hour") return date.toLocaleTimeString(locale, { hour: "2-digit", minute: "2-digit" });
  if (unit === "day") return date.toLocaleDateString(locale, { day: "numeric", month: "numeric" });
  return date.toLocaleDateString(locale, { month: "short", year: "2-digit" });
}

export function formatTimeFull(date, locale) {
  return date.toLocaleString(locale, { day: "numeric", month: "numeric", year: "numeric", hour: "2-digit", minute: "2-digit" });
}
