import { useLanguage } from "../context/LanguageContext";

export function ActionBadge({ action }) {
  const { t } = useLanguage();
  const normalized = (action || "").toUpperCase();
  const map = {
    BUY: ["badge-buy", t("badge.buy")],
    SELL: ["badge-sell", t("badge.sell")],
    HOLD: ["badge-hold", t("badge.hold")],
  };
  const [cls, label] = map[normalized] || ["badge-neutral", normalized || "N/A"];
  return (
    <span className={`badge ${cls}`}>
      <span className="badge-dot" /> {label}
    </span>
  );
}

export function SentimentBadge({ sentiment }) {
  const { t } = useLanguage();
  const normalized = (sentiment || "Neutral").toLowerCase();
  const map = { bullish: "badge-bullish", bearish: "badge-bearish", neutral: "badge-neutral" };
  const label = { bullish: t("badge.bullish"), bearish: t("badge.bearish"), neutral: t("badge.neutral") }[normalized] || sentiment;
  return (
    <span className={`badge ${map[normalized] || "badge-neutral"}`}>
      <span className="badge-dot" /> {label}
    </span>
  );
}

export function RiskBadge({ level }) {
  const { t } = useLanguage();
  const normalized = (level || "Medium").toLowerCase();
  const map = { low: "badge-risk-low", medium: "badge-risk-medium", high: "badge-risk-high" };
  const label = { low: t("badge.riskLow"), medium: t("badge.riskMedium"), high: t("badge.riskHigh") }[normalized] || level;
  return (
    <span className={`badge ${map[normalized] || "badge-risk-medium"}`}>
      <span className="badge-dot" /> {label}
    </span>
  );
}

export function ConfidenceBadge({ score }) {
  const { t } = useLanguage();
  const value = Math.round(score ?? 0);
  const cls = value >= 70 ? "badge-buy" : value >= 40 ? "badge-hold" : "badge-sell";
  return (
    <span className={`badge ${cls}`}>
      <span className="badge-dot" /> {t("badge.confidence", { value })}
    </span>
  );
}

export function AccuracyBadge({ score }) {
  const { t } = useLanguage();
  const value = Math.round(score ?? 0);
  const cls = value >= 70 ? "badge-buy" : value >= 40 ? "badge-hold" : "badge-sell";
  return (
    <span className={`badge ${cls}`}>
      <span className="badge-dot" /> {t("badge.accuracy", { value })}
    </span>
  );
}

export function MockBadge() {
  const { t } = useLanguage();
  return <span className="badge badge-mock">{t("badge.mock")}</span>;
}
