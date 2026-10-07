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

export function signalBalance(items) {
  const count = (tone) => (items || []).filter((s) => s.tone === tone).length;
  return { bullish: count("bullish"), bearish: count("bearish"), neutral: count("neutral") };
}
