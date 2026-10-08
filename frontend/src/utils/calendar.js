/** Helpers for the market event calendar. */

export function eventName(t, e) {
  return t(`calendar.kind_${e.kind}`, { coin: e.coin || "" });
}

/** Calendar days until the event in the viewer's time zone (0 = today or already started, 1 = tomorrow). */
export function daysUntil(iso, now = Date.now()) {
  const startOfDay = (t) => { const d = new Date(t); d.setHours(0, 0, 0, 0); return d.getTime(); };
  return Math.max(0, Math.round((startOfDay(new Date(iso).getTime()) - startOfDay(now)) / 86_400_000));
}

export function groupByDay(events, locale) {
  const groups = [];
  for (const e of events) {
    const label = new Date(e.at).toLocaleDateString(locale, { weekday: "long", day: "numeric", month: "long" });
    const last = groups[groups.length - 1];
    if (last && last.label === label) last.items.push(e);
    else groups.push({ label, items: [e] });
  }
  return groups;
}
