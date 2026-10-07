/** Calibration (is "80 % sure" right 80 % of the time?) and accuracy in rising, falling and sideways markets. */

import { Gauge, Waves } from "lucide-react";
import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api";
import { useLanguage } from "../context/LanguageContext";
import { QUANT_LABEL } from "../utils/models";
import { Card } from "./Card";
import InfoTip from "./InfoTip";

const MIN_FORECASTS = 5;

export default function AccuracyInsights() {
  const { t } = useLanguage();
  const [data, setData] = useState(null);
  useEffect(() => { api.accuracyInsights().then(setData).catch(() => setData(null)); }, []);
  if (!data) return null;
  const calibration = data.calibration.filter((b) => b.forecasts >= MIN_FORECASTS);
  const name = (p) => (p === QUANT_LABEL ? t("provider.quantLabel") : p);
  const cell = (r) => (r ? <>{r.hit_pct}% <span className="text-sub">({r.forecasts})</span></> : <span className="text-sub">—</span>);

  return (
    <>
      <Card title={<>{t("insights.calibrationTitle")} <InfoTip text={t("insights.calibrationHelp")} /></>} icon={Gauge} style={{ marginTop: 16 }}>
        {calibration.length === 0 ? <p className="text-sub" style={{ margin: 0 }}>{t("insights.notEnough")}</p> : (
          <div role="img" aria-label={t("insights.calibrationTitle")}>
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={calibration} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />
                <XAxis dataKey="band" stroke="var(--text-tertiary)" fontSize={11} tickLine={false} axisLine={false} />
                <YAxis stroke="var(--text-tertiary)" fontSize={11} tickLine={false} axisLine={false} width={36} domain={[0, 100]} unit="%" />
                <Tooltip contentStyle={{ background: "var(--bg-tooltip)", border: "1px solid var(--border-strong)", borderRadius: 10, fontSize: 12, color: "var(--text-primary)" }}
                         formatter={(v, key) => [`${v}%`, t(key === "claimed_pct" ? "insights.claimed" : "insights.actual")]} />
                <Legend formatter={(key) => t(key === "claimed_pct" ? "insights.claimed" : "insights.actual")} wrapperStyle={{ fontSize: 12 }} />
                <Bar dataKey="claimed_pct" fill="#a78bfa" radius={[4, 4, 0, 0]} isAnimationActive={false} />
                <Bar dataKey="actual_pct" fill="#22d3ee" radius={[4, 4, 0, 0]} isAnimationActive={false} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </Card>

      {data.regimes.length > 0 && (
        <Card title={<>{t("insights.regimeTitle")} <InfoTip text={t("insights.regimeHelp", { band: data.flat_band_pct })} /></>} icon={Waves} style={{ marginTop: 16 }}>
          <div className="table-scroll">
            <table className="lb-table">
              <thead><tr><th>{t("leaderboard.colProvider")}</th><th>{t("insights.up")}</th><th>{t("insights.down")}</th><th>{t("insights.flat")}</th></tr></thead>
              <tbody>
                {data.regimes.map((r) => (
                  <tr key={r.provider}><td>{name(r.provider)}</td><td>{cell(r.up)}</td><td>{cell(r.down)}</td><td>{cell(r.flat)}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </>
  );
}
