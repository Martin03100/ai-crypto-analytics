/** Human-readable notification texts. */

import { alertValue } from "./alerts";
import { formatPrice } from "./formatPrice";

function alertNotification(d, t) {
  switch (d.alert_kind) {
    case "move":
      return t("notif.alertMove", { coin: d.coin, value: alertValue("move", d.price) });
    case "rsi":
      return t("notif.alertRsi", { coin: d.coin, value: alertValue("rsi", d.price) });
    case "fear_greed":
      return t("notif.alertFearGreed", { value: alertValue("fear_greed", d.price) });
    default:
      return t(d.direction === "above" ? "notif.alertAbove" : "notif.alertBelow", { coin: d.coin, price: formatPrice(d.price) });
  }
}

export function notificationText(n, t) {
  const d = n.data || {};
  switch (n.kind) {
    case "forecast_evaluated":
      return t(d.direction_correct ? "notif.evaluatedHit" : "notif.evaluatedMiss",
               { coin: d.coin, horizon: t(`forecast.horizon${d.horizon}`), accuracy: d.accuracy_pct });
    case "duel_settled":
      return t(`notif.duel_${d.outcome}`);
    case "referral_reward":
      return t("notif.referral", { days: d.days });
    case "price_alert":
      return alertNotification(d, t);
    case "challenge_won":
      return t("notif.challengeWon", { coin: d.coin, price: formatPrice(d.price) });
    case "premium_started":
      return t("notif.premium");
    default:
      return "";
  }
}

export function timeAgo(iso, t, now = Date.now()) {
  const minutes = Math.max(0, Math.round((now - new Date(iso).getTime()) / 60000));
  if (minutes < 1) return t("market.timeAgoNow");
  if (minutes < 60) return t("market.timeAgoMinutes", { count: minutes });
  if (minutes < 1440) return t("market.timeAgoHours", { count: Math.round(minutes / 60) });
  return t("market.timeAgoDays", { count: Math.round(minutes / 1440) });
}
