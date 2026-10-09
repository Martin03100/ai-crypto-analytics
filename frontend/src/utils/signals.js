/** Grouping and labels for market signals (backend: services/signals.py). */

export const SIGNAL_GROUPS = ["derivatives", "options", "flows", "market", "network", "macro", "events", "regulation", "predictions"];

export function groupSignals(items) {
  const groups = new Map();
  for (const s of items || []) {
    if (!groups.has(s.group)) groups.set(s.group, []);
    groups.get(s.group).push(s);
  }
  return SIGNAL_GROUPS.filter((g) => groups.has(g)).map((g) => [g, groups.get(g)]);
}

export function signalLabel(s, t) {
  const key = `signals.k.${s.key}`;
  const label = t(key);
  return label === key ? s.key : label;
}

/** Free-text items (calendar, regulators, prediction markets) show the text itself, numbers show "label: value". */
export const TEXT_SIGNALS = new Set(["event", "regulator_news", "polymarket"]);

/** Calendar and prediction-market rows phrased in the reader's language (older saved analyses fall back to display). */
export function signalText(s, t) {
  const m = s.meta || {};
  if (s.key === "event" && m.name && Number.isFinite(m.days)) {
    const when = m.days === 0 ? t("signals.today") : m.days === 1 ? t("signals.tomorrow") : t("signals.inDays", { n: m.days });
    return `${m.name} · ${when}`;
  }
  if (s.key === "polymarket" && m.question && Number.isFinite(m.yes)) return `${m.question} · ${t("signals.odds", { n: m.yes })}`;
  return s.display;
}

/** The server writes values with English period marks ("+2.5% 1w", "3.7% y/y"); show them in the reader's language. */
export function localizeDisplay(display, t) {
  const text = String(display ?? "");
  const liquidations = /^(\d+)% long$/.exec(text);
  if (liquidations) return t("signals.u.liqLongs", { n: liquidations[1] });
  return text
    .replace(/(\s)(24h|7d|30d|1w|1m)(?=\)|$)/g, (_m, space, unit) => `${space}${t(`signals.u.${unit}`)}`)
    .replace(/\/ 8h$/, `/ ${t("signals.u.8h")}`)
    .replace(/ y\/y$/, ` ${t("signals.u.yy")}`);
}

export function signalBalance(items) {
  const count = (tone) => (items || []).filter((s) => s.tone === tone).length;
  return { bullish: count("bullish"), bearish: count("bearish"), neutral: count("neutral") };
}
