/** Accuracy per AI model: direction hit rate with its 95 % interval, average price error and the naive-guess check. */

import InfoTip from "./InfoTip";
import { useLanguage } from "../context/LanguageContext";
import { providerName } from "../utils/models";

export default function ProviderStatsTable({ providers, reliableSample = 30 }) {
  const { t } = useLanguage();
  // The trophy only goes to a model with enough checked forecasts for the ranking to mean something.
  const trophyIndex = providers.findIndex((p) => (p.reliable ?? p.evaluated >= reliableSample));
  return (
    <>
      <div className="table-scroll">
        <table className="lb-table">
          <thead>
            <tr>
              <th>{t("leaderboard.colProvider")}</th>
              <th>{t("leaderboard.colEvaluated")}</th>
              <th>{t("leaderboard.colDirection")}<InfoTip text={t("help.direction")} /></th>
              <th>{t("leaderboard.colError")}<InfoTip text={t("help.error")} /></th>
              <th>{t("leaderboard.colBeatsBaseline")}<InfoTip text={t("help.baseline")} /></th>
            </tr>
          </thead>
          <tbody>
            {providers.map((p, i) => (
              <tr key={p.provider}>
                <td>
                  {i === trophyIndex ? "🏆 " : ""}{providerName(p.provider, t)}
                  {!(p.reliable ?? p.evaluated >= reliableSample) && <span className="text-sub"> · {t("leaderboard.fewData")}</span>}
                </td>
                <td>{p.evaluated}</td>
                <td>
                  {p.direction_hit_pct}%
                  {Array.isArray(p.direction_ci) && <span className="text-sub lb-ci">{p.direction_ci[0]}–{p.direction_ci[1]} %</span>}
                </td>
                <td>{p.avg_error_pct ?? Math.round((100 - p.avg_accuracy_pct) * 10) / 10}%</td>
                <td>{p.beats_baseline_pct}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-sub" style={{ marginTop: 10 }}>{t("leaderboard.reliableNote", { n: reliableSample })}</p>
    </>
  );
}
