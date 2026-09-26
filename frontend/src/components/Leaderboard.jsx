import { Trophy, Users } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api";
import { Card } from "./Card";
import InfoTip from "./InfoTip";
import { useLanguage } from "../context/LanguageContext";

const CUSTOM_LABEL = "Custom (OpenAI-compatible)";

/** Verejny rebricek presnosti AI providerov + sutaz "tvoj tip vs AI".
 * Cisla su zo vsetkych vyhodnotenych (dozretych, nie ukazkovych) predikcii. */
export default function Leaderboard() {
  const { t } = useLanguage();
  const [data, setData] = useState(null);

  useEffect(() => {
    api.forecastLeaderboard().then(setData).catch(() => setData({ providers: [], challenge: null }));
  }, []);

  if (!data) return <Card><p className="text-sub">{t("leaderboard.loading")}</p></Card>;
  const label = (name) => (name === CUSTOM_LABEL ? t("provider.customLabel") : name);
  const everyone = data.challenge?.everyone;

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <Card title={t("leaderboard.title")} icon={Trophy}>
        <p className="text-sub" style={{ marginBottom: 12 }}>{t("leaderboard.desc")}</p>
        {data.providers.length === 0 ? (
          <p className="text-sub">{t("leaderboard.empty")}</p>
        ) : (
          <div className="table-scroll">
            <table className="lb-table">
              <thead>
                <tr>
                  <th>{t("leaderboard.colProvider")}</th>
                  <th>{t("leaderboard.colEvaluated")}</th>
                  <th>{t("leaderboard.colDirection")}<InfoTip text={t("help.direction")} /></th>
                  <th>{t("leaderboard.colAccuracy")}<InfoTip text={t("help.accuracy")} /></th>
                  <th>{t("leaderboard.colBeatsBaseline")}<InfoTip text={t("help.baseline")} /></th>
                </tr>
              </thead>
              <tbody>
                {data.providers.map((p, i) => (
                  <tr key={p.provider}>
                    <td>
                      {i === 0 ? "🏆 " : ""}{label(p.provider)}
                      {p.evaluated < 5 && <span className="text-sub"> · {t("leaderboard.fewData")}</span>}
                    </td>
                    <td>{p.evaluated}</td>
                    <td>{p.direction_hit_pct}%</td>
                    <td>{p.avg_accuracy_pct}%</td>
                    <td>{p.beats_baseline_pct}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
      {data.challenge && (
        <Card title={t("challenge.title")} icon={Users}>
          <p className="text-sub" style={{ marginBottom: 10 }}>{t("challenge.howTo")}</p>
          <p style={{ margin: "0 0 6px", fontSize: 13.5 }}>{t("challenge.youStats", data.challenge.you)}</p>
          <p className="text-sub" style={{ margin: 0 }}>
            {everyone.total > 0
              ? t("challenge.everyoneStats", { pct: Math.round((everyone.wins / everyone.total) * 100), total: everyone.total })
              : t("challenge.noneYet")}
          </p>
        </Card>
      )}
    </div>
  );
}
