/** Human-readable notification texts. */

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
