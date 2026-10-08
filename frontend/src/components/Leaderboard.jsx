/** AI accuracy leaderboard. */

import { Trophy, Users } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api";
import { Card } from "./Card";
import ProviderStatsTable from "./ProviderStatsTable";
import { useLanguage } from "../context/LanguageContext";
import { QUANT_LABEL } from "../utils/models";

export default function Leaderboard() {
  const { t } = useLanguage();
  const [data, setData] = useState(null);

  useEffect(() => {
    api.forecastLeaderboard().then(setData).catch(() => setData({ providers: [], challenge: null }));
  }, []);

  if (!data) return <Card><p className="text-sub">{t("leaderboard.loading")}</p></Card>;
  const hasQuant = data.providers.some((p) => p.provider === QUANT_LABEL);
  const hasDemo = data.providers.some((p) => p.provider.endsWith(" test"));
  const everyone = data.challenge?.everyone;

  return (
    <div style={{ display: "grid", gap: 16, gridTemplateColumns: "minmax(0, 1fr)" }}>
      <Card title={t("leaderboard.title")} icon={Trophy}>
        <p className="text-sub" style={{ marginBottom: 12 }}>{t("leaderboard.desc")}</p>
        {hasQuant && <p className="text-sub" style={{ marginBottom: 12 }}>{t("leaderboard.quantNote")}</p>}
        {hasDemo && <p className="text-sub" style={{ marginBottom: 12 }}>{t("leaderboard.demoNote")}</p>}
        {data.providers.length === 0 ? (
          <p className="text-sub">{t("leaderboard.empty")}</p>
        ) : (
          <ProviderStatsTable providers={data.providers} reliableSample={data.reliable_sample ?? 30} />
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
