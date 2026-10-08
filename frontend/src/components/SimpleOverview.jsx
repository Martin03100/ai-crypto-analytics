/** Beginner view: for each followed coin a traffic light and one plain sentence. */

import { ArrowRight, Lightbulb } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useLanguage } from "../context/LanguageContext";
import { useSimpleMode } from "../hooks/useSimpleMode";
import { formatPrice } from "../utils/formatPrice";
import { Card } from "./Card";
import { SkeletonLines } from "./Skeleton";
import { lightFor } from "../utils/viewHelpers";

export default function SimpleOverview() {
  const { t } = useLanguage();
  const { setSimple } = useSimpleMode();
  const [coins, setCoins] = useState(null);
  const [rows, setRows] = useState(null);

  useEffect(() => {
    api.watchlist().then((w) => setCoins(w.coins)).catch(() => setCoins(["BTC", "ETH", "SOL"]));
    api.scanner().then((r) => setRows(r.rows)).catch(() => setRows([]));
  }, []);

  const items = useMemo(() => {
    if (!coins || !rows) return null;
    return coins.map((c) => rows.find((r) => r.coin === c)).filter(Boolean);
  }, [coins, rows]);

  return (
    <Card title={t("simple.title")} icon={Lightbulb} className="simple-card">
      <p className="text-sub" style={{ marginTop: 0 }}>{t("simple.lead")}</p>
      {items === null ? <SkeletonLines count={3} /> : items.length === 0 ? <p className="text-sub">{t("simple.empty")}</p> : (
        <ul className="simple-list">
          {items.map((r) => {
            const [light, key] = lightFor(r.signal);
            const pct = r.expected_24h_pct;
            return (
              <li key={r.coin} className="simple-item">
                <span className={`traffic traffic-${light}`} role="img" aria-label={t(`simple.light_${light}`)} />
                <div className="simple-text">
                  <strong>{r.coin}</strong> <span className="mono text-sub">{formatPrice(r.price)}</span>
                  <p>{t(key, { coin: r.coin, pct: pct == null ? "0" : `${pct >= 0 ? "+" : ""}${pct}` })}</p>
                </div>
                <Link to={`/forecast?coin=${r.coin}`} className="btn btn-ghost btn-sm btn-icon" aria-label={t("simple.details", { coin: r.coin })}>
                  <ArrowRight size={14} />
                </Link>
              </li>
            );
          })}
        </ul>
      )}
      <p className="text-sub simple-foot">
        {t("simple.disclaimer")}{" "}
        <button type="button" className="link-btn" onClick={() => setSimple(false)}>{t("simple.switchFull")}</button>
      </p>
    </Card>
  );
}
