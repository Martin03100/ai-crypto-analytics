/** How each model's direction hit rate developed week by week (last 12 weeks). */

import { TrendingUp } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { CartesianGrid, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api";
import { useLanguage } from "../context/LanguageContext";
import { Card } from "./Card";
import InfoTip from "./InfoTip";
import { timelineRows } from "../utils/viewHelpers";

const COLORS = ["#22d3ee", "#a78bfa", "#34d399", "#fbbf24", "#f87171", "#60a5fa", "#f472b6"];

export default function AccuracyTimeline() {
  const { t } = useLanguage();
  const [data, setData] = useState(null);
  useEffect(() => { api.accuracyTimeline().then(setData).catch(() => setData(null)); }, []);
  const { rows, providers } = useMemo(() => timelineRows(data), [data]);
  const name = (p) => (p === "quant" ? t("provider.quantLabel") : p);
  if (!data) return null;

  return (
    <Card title={<>{t("timeline.title")} <InfoTip text={t("timeline.help")} /></>} icon={TrendingUp} style={{ marginTop: 16 }}>
      {providers.length === 0 ? <p className="text-sub" style={{ margin: 0 }}>{t("insights.notEnough")}</p> : (
        <div role="img" aria-label={t("timeline.title")}>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={rows} margin={{ top: 10, right: 12, left: 0, bottom: 0 }}>
              <CartesianGrid stroke="rgba(127,127,127,0.12)" vertical={false} />
              <XAxis dataKey="week" stroke="var(--text-tertiary)" fontSize={11} tickLine={false} axisLine={false} />
              <YAxis stroke="var(--text-tertiary)" fontSize={11} tickLine={false} axisLine={false} width={36} domain={[0, 100]} unit="%" />
              <ReferenceLine y={50} stroke="var(--text-tertiary)" strokeDasharray="4 4" />
              <Tooltip contentStyle={{ background: "var(--bg-tooltip)", border: "1px solid var(--border-strong)", borderRadius: 10, fontSize: 12, color: "var(--text-primary)" }}
                       formatter={(v, key) => [v == null ? "—" : `${v}%`, name(key)]} />
              <Legend formatter={name} wrapperStyle={{ fontSize: 12 }} />
              {providers.map((p, i) => (
                <Line key={p} type="monotone" dataKey={p} stroke={COLORS[i]} strokeWidth={2} dot={{ r: 2 }} connectNulls isAnimationActive={false} />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
      <p className="text-sub" style={{ margin: "8px 0 0" }}>{t("timeline.note")}</p>
    </Card>
  );
}
