/** Grouped list of market signals with a coloured direction mark. */

import { useLanguage } from "../context/LanguageContext";
import { TEXT_SIGNALS, groupSignals, localizeDisplay, signalLabel, signalText } from "../utils/signals";

const MARK = { bullish: "▲", bearish: "▼", neutral: "•" };

export default function SignalList({ items, compact = false }) {
  const { t } = useLanguage();
  const sourceName = (src) => {
    const key = `sources.${src}`;
    const label = t(key);
    return label === key ? src : label;
  };
  return (
    <div className={`signal-groups ${compact ? "signal-groups-compact" : ""}`}>
      {groupSignals(items).map(([group, rows]) => (
        <section key={group} className="signal-group">
          <h4>{t(`signals.g.${group}`)}</h4>
          <ul>
            {rows.map((s, i) => (
              <li key={`${s.key}-${i}`} className={`signal-row tone-${s.tone}`} title={sourceName(s.source)}>
                <span className="signal-mark" aria-label={t(`signals.tone.${s.tone}`)}>{MARK[s.tone]}</span>
                {TEXT_SIGNALS.has(s.key) ? (
                  <span className="signal-text">{signalText(s, t)}</span>
                ) : (
                  <>
                    <span className="signal-label">{signalLabel(s, t)}</span>
                    <span className="signal-value mono">{localizeDisplay(s.display, t)}</span>
                  </>
                )}
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
