/** "AI vs reality" this week: totals, the best model and a shareable image for social networks. */

import { CalendarCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api";
import { useLanguage } from "../context/LanguageContext";
import { providerName } from "../utils/models";
import { Card } from "./Card";
import ShareImages from "./ShareImages";

export default function WeeklyRecap({ style }) {
  const { t } = useLanguage();
  const [data, setData] = useState(null);
  useEffect(() => { api.weeklySummary().then(setData).catch(() => setData(null)); }, []);
  if (!data) return null;
  const top = data.providers[0];
  const vs = data.humans_vs_ai || {};
  const duels = (vs.wins || 0) + (vs.losses || 0) + (vs.ties || 0);
  const name = (p) => (p === "quant" ? t("provider.quantShort") : providerName(p, t, true));

  return (
    <Card title={t("recap.title")} icon={CalendarCheck} style={style}>
      {data.forecasts === 0 ? <p className="text-sub" style={{ marginTop: 0 }}>{t("recap.empty")}</p> : (
        <div className="recap-grid">
          <div><span className="recap-value">{data.forecasts}</span><span className="text-sub">{t("recap.forecasts")}</span></div>
          <div><span className="recap-value">{data.hit_pct == null ? "—" : `${data.hit_pct}%`}</span><span className="text-sub">{t("recap.hit")}</span></div>
          {top && <div><span className="recap-value">{name(top.provider)}</span><span className="text-sub">{t("recap.best", { pct: top.hit_pct })}</span></div>}
          {duels > 0 && <div><span className="recap-value">{vs.wins}/{duels}</span><span className="text-sub">{t("recap.humans")}</span></div>}
        </div>
      )}
      {data.forecasts > 0 && (   // an empty week is nothing to share
        <ShareImages coin="weekly" urlFor={api.weeklyCardUrl} shareUrl={`${window.location.origin}/track-record`} label={t("recap.share")} />
      )}
    </Card>
  );
}
