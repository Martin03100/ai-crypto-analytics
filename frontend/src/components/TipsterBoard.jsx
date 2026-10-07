/** Public "Beat the AI" board: best price tippers this week or all time. */

import { Crown, Swords, Trophy } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useLanguage } from "../context/LanguageContext";
import AmbassadorBadge from "./AmbassadorBadge";
import { Card } from "./Card";

export default function TipsterBoard() {
  const { t } = useLanguage();
  const [period, setPeriod] = useState("week");
  const [data, setData] = useState(null);

  useEffect(() => {
    let alive = true;
    api.tipsters(period).then((d) => alive && setData(d)).catch(() => alive && setData({ leaders: [], humans_vs_ai: null }));
    return () => { alive = false; };
  }, [period]);

  const duel = data?.humans_vs_ai;
  const duels = duel ? duel.wins + duel.losses + duel.ties : 0;

  return (
    <Card title={t("tipsters.title")} icon={Swords} style={{ marginTop: 16 }}>
      <p className="text-sub" style={{ marginBottom: 12 }}>{t("tipsters.intro")}</p>
      <div className="tabs" style={{ marginBottom: 12 }}>
        <button className={`tab ${period === "week" ? "active" : ""}`} onClick={() => setPeriod("week")}>{t("tipsters.week")}</button>
        <button className={`tab ${period === "all" ? "active" : ""}`} onClick={() => setPeriod("all")}>{t("tipsters.all")}</button>
      </div>
      {duels > 0 && (
        <p className="tipsters-score" data-testid="humans-vs-ai">
          {t("tipsters.score", { humans: duel.wins, ai: duel.losses, ties: duel.ties })}
        </p>
      )}
      {!data ? null : data.leaders.length === 0 ? (
        <p className="text-sub">{t("tipsters.empty")}</p>
      ) : (
        <div className="table-scroll">
          <table className="lb-table">
            <thead>
              <tr><th>#</th><th>{t("tipsters.colName")}</th><th>{t("tipsters.colWins")}</th><th>{t("tipsters.colDuels")}</th><th>{t("tipsters.colRate")}</th></tr>
            </thead>
            <tbody>
              {data.leaders.map((l, i) => (
                <tr key={l.nickname}>
                  <td>{i + 1}</td>
                  <td>{l.nickname}{l.premium && <Crown size={12} className="premium-crown" aria-label="Premium" />}<AmbassadorBadge level={l.badge} compact />
                    {l.challenge_wins > 0 && <span className="challenge-badge" title={t("weekly.winsTitle")}><Trophy size={11} /> {l.challenge_wins}</span>}</td>
                  <td>{l.wins}</td>
                  <td>{l.duels}</td>
                  <td>{l.win_pct}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="text-sub" style={{ marginTop: 10 }}>
        {t("tipsters.howTo")} <Link to="/settings" className="key-link">{t("tipsters.setNickname")}</Link>
      </p>
    </Card>
  );
}
