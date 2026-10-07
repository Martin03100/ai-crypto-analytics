/** Texts for the four alert kinds (list rows and notifications). */

import { formatPrice } from "./formatPrice";

export function alertValue(kind, value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "—";
  if (kind === "price") return formatPrice(n);
  if (kind === "move") return `${n > 0 ? "+" : ""}${n.toFixed(1)} %`;
  return String(Math.round(n));
}

export function alertLabel(a, t) {
  const dir = t(a.direction === "above" ? "alerts.above" : "alerts.below");
  switch (a.kind) {
    case "move":
      return t(a.direction === "above" ? "alerts.descMoveUp" : "alerts.descMoveDown", { coin: a.coin, n: a.target_price });
    case "rsi":
      return t("alerts.descRsi", { coin: a.coin, dir, n: a.target_price });
    case "fear_greed":
      return t("alerts.descFearGreed", { dir, n: a.target_price });
    default:
      return `${a.coin} ${dir} ${formatPrice(a.target_price)}`;
  }
}
