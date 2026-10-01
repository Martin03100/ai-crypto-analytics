/** Scheduled forecasts: display helpers. The server stores the wall-clock time together with the IANA zone. */

const DAY_MS = 86_400_000;

export function userTimeZone() {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  } catch {
    return "UTC";
  }
}

/** Localised weekday names, Monday first. */
export function weekdayNames(locale, style = "long") {
  const monday = new Date(Date.UTC(2024, 0, 1));   // 1 Jan 2024 was a Monday
  return Array.from({ length: 7 }, (_, i) =>
    new Date(monday.getTime() + i * DAY_MS).toLocaleDateString(locale, { weekday: style, timeZone: "UTC" }));
}

export function formatHour(hour, minute, locale) {
  return new Date(2024, 0, 1, hour, minute || 0).toLocaleTimeString(locale, { hour: "2-digit", minute: "2-digit" });
}
