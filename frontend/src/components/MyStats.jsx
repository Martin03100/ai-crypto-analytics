/** Premium: the user's own accuracy by model, coin and horizon. */

import { BarChart3, FileDown } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api";
import { useAuth } from "../context/AuthContext";
import { useLanguage } from "../context/LanguageContext";
import { QUANT_LABEL } from "../utils/models";
import { Card } from "./Card";
import PremiumGate from "./PremiumGate";

const pct = (v) => (v == null ? "—" : `${v}%`);

function Table({ title, rows, label }) {
  const { t } = useLanguage();
  if (!rows.length) return null;
  return (
    <Card title={title} style={{ marginTop: 16 }}>
      <div className="table-scroll">
        <table className="lb-table">
          <thead>
            <tr><th>{label}</th><th>{t("leaderboard.colEvaluated")}</th><th>{t("leaderboard.colDirection")}</th>
              <th>{t("leaderboard.colAccuracy")}</th><th>{t("leaderboard.colBeatsBaseline")}</th></tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.key}><td>{r.key}</td><td>{r.evaluated}</td><td>{pct(r.direction_hit_pct)}</td><td>{pct(r.avg_accuracy_pct)}</td><td>{pct(r.beats_baseline_pct)}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

export default function MyStats() {
  const { t } = useLanguage();
  const { user } = useAuth();
  const [stats, setStats] = useState(null);

  useEffect(() => { if (user?.premium) api.myStats().then(setStats).catch(() => setStats(null)); }, [user?.premium]);

  if (!user?.premium) return <PremiumGate title={t("mystats.title")} text={t("mystats.gate")} />;
  if (!stats) return null;
  const providers = stats.by_provider.map((r) => ({ ...r, key: r.key === QUANT_LABEL ? t("provider.quantLabel") : r.key }));
  const horizons = stats.by_horizon.map((r) => ({ ...r, key: t(`forecast.horizon${r.key}`) }));

  return (
    <>
      <div className="mystats-actions">
        <a className="btn btn-ghost btn-sm" href={api.reportPdfUrl()} download><FileDown size={14} /> {t("report.download")}</a>
      </div>
      <div className="track-stats">
        <div className="card track-stat"><span className="track-stat-value">{stats.total_evaluated}</span><span className="text-sub">{t("track.statEvaluated")}</span></div>
        <div className="card track-stat"><span className="track-stat-value">{stats.direction_hit_pct == null ? "—" : `${stats.direction_hit_pct}%`}</span><span className="text-sub">{t("track.statDirection")}</span></div>
        <div className="card track-stat"><span className="track-stat-value">{stats.duels.wins}:{stats.duels.losses}</span><span className="text-sub">{t("mystats.duels")}</span></div>
      </div>
      {stats.total_evaluated === 0 ? (
        <Card style={{ marginTop: 16 }} icon={BarChart3} title={t("mystats.title")}><p className="text-sub">{t("mystats.empty")}</p></Card>
      ) : (
        <>
          <Table title={t("mystats.byModel")} rows={providers} label={t("leaderboard.colProvider")} />
          <Table title={t("mystats.byCoin")} rows={stats.by_coin} label={t("track.colCoin")} />
          <Table title={t("mystats.byHorizon")} rows={horizons} label={t("track.colHorizon")} />
        </>
      )}
    </>
  );
}
