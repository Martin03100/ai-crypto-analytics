/** Krátky, čitateľný zápis ceny pre UI (grafy, karty) - $1.2k namiesto
 * $1200.00, viac desatinných miest pre veľmi malé ceny (napr. memecoiny). */
export function formatPrice(v) {
  if (v == null) return "";
  if (v >= 1000) return `$${(v / 1000).toFixed(1)}k`;
  if (v >= 1) return `$${v.toFixed(2)}`;
  return `$${v.toFixed(4)}`;
}
