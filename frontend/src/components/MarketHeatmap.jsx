/** Market heatmap: 20 coins coloured by their 24h or 7-day move; bigger tiles for bigger coins. */

import { LayoutGrid } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useLanguage } from "../context/LanguageContext";
import { formatPrice } from "../utils/formatPrice";
import { Card } from "./Card";
import { SkeletonLines } from "./Skeleton";
import { heatColor, tileSize } from "../utils/viewHelpers";


export default function MarketHeatmap({ style }) {
  const { t } = useLanguage();
  const [rows, setRows] = useState(null);
  const [period, setPeriod] = useState("change_24h");

  useEffect(() => {
    let alive = true;
    const load = () => api.scanner().then((r) => alive && setRows(r.rows)).catch(() => alive && setRows((prev) => prev || []));
    load();
    const id = setInterval(() => { if (document.visibilityState === "visible") load(); }, 60_000);
    return () => { alive = false; clearInterval(id); };
  }, []);

  const sorted = useMemo(() => [...(rows || [])].sort((a, b) => (b.market_cap || 0) - (a.market_cap || 0)), [rows]);

  return (
    <Card title={t("heatmap.title")} icon={LayoutGrid} style={style}>
      <div className="tabs" role="radiogroup" aria-label={t("heatmap.period")} style={{ marginBottom: 12 }}>
        {[["change_24h", "heatmap.day"], ["change_7d", "heatmap.week"]].map(([key, label]) => (
          <button key={key} type="button" role="radio" aria-checked={period === key} className={`tab ${period === key ? "active" : ""}`} onClick={() => setPeriod(key)}>
            {t(label)}
          </button>
        ))}
      </div>
      {rows === null ? <SkeletonLines count={4} /> : sorted.length === 0 ? <p className="text-sub">{t("heatmap.empty")}</p> : (
        <ul className="heatmap">
          {sorted.map((r, i) => {
            const pct = r[period];
            return (
              <li key={r.coin} className={`heat-cell heat-${tileSize(i)}`}><Link to={`/forecast?coin=${r.coin}`} className="heat-tile"
                    style={{ background: heatColor(pct) }}
                    aria-label={t("heatmap.tileLabel", { coin: r.coin, pct: pct == null ? "—" : pct.toFixed(1) })}>
                <strong>{r.coin}</strong>
                <span className="mono">{pct == null ? "—" : `${pct >= 0 ? "+" : ""}${pct.toFixed(1)}%`}</span>
                <span className="heat-price mono">{formatPrice(r.price)}</span>
              </Link></li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}
