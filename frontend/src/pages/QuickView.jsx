/** Quick view: one glance at followed coins, market mood and the next event (home-screen shortcut). */

import { BellRing, RefreshCw, Sparkles } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { lightFor } from "../utils/viewHelpers";
import { SkeletonLines } from "../components/Skeleton";
import UpcomingEvents from "../components/UpcomingEvents";
import { useLanguage } from "../context/LanguageContext";
import { localeForLang } from "../i18n/locale";
import { formatPrice } from "../utils/formatPrice";
import { stripMockTag } from "../utils/mockText";
import { usePageTitle } from "../hooks/usePageTitle";

const REFRESH_MS = 30_000;

export default function QuickView() {
  const { t, lang } = useLanguage();
  usePageTitle("quick.pageTitle");
  const [coins, setCoins] = useState(null);
  const [rows, setRows] = useState(null);
  const [fg, setFg] = useState(null);
  const [updated, setUpdated] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setBusy(true);
    const [w, s, f] = await Promise.allSettled([api.watchlist(), api.scanner(), api.fearGreed()]);
    if (w.status === "fulfilled") setCoins(w.value.coins);
    else setCoins((prev) => prev || ["BTC", "ETH", "SOL"]);
    if (s.status === "fulfilled") setRows(s.value.rows);
    else setRows((prev) => prev || []);
    if (f.status === "fulfilled" && f.value.data) setFg(f.value.data);
    setUpdated(new Date());
    setBusy(false);
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(() => { if (document.visibilityState === "visible") load(); }, REFRESH_MS);
    return () => clearInterval(id);
  }, [load]);

  const items = useMemo(() => (coins && rows ? coins.map((c) => rows.find((r) => r.coin === c)).filter(Boolean) : null), [coins, rows]);

  return (
    <div className="quick">
      <div className="topbar">
        <div>
          <h1 className="page-title">{t("quick.title")}</h1>
          {updated && <p className="page-sub">{t("quick.updated", { time: updated.toLocaleTimeString(localeForLang(lang), { hour: "2-digit", minute: "2-digit" }) })}</p>}
        </div>
        <button className="btn btn-ghost btn-sm btn-icon" onClick={load} disabled={busy} aria-label={t("common.refresh")} title={t("common.refresh")}>
          <RefreshCw size={14} className={busy ? "spin" : ""} />
        </button>
      </div>

      {fg && (
        <div className="card quick-mood">
          <span className="text-sub">{t("quick.mood")}</span>
          <strong className="mono">{fg.value}/100</strong>
          <span className="text-sub">{stripMockTag(fg.classification)}</span>
        </div>
      )}

      {items === null ? <div className="card"><SkeletonLines count={4} /></div> : (
        <ul className="quick-list">
          {items.map((r) => {
            const [light] = lightFor(r.signal);
            const ch = r.change_24h;
            return (
              <li key={r.coin}>
                <Link to={`/forecast?coin=${r.coin}`} className="card quick-row">
                  <span className={`traffic traffic-${light}`} role="img" aria-label={t(`simple.light_${light}`)} />
                  <strong>{r.coin}</strong>
                  <span className="mono quick-price">{formatPrice(r.price)}</span>
                  <span className={`metric-delta ${ch >= 0 ? "up" : "down"}`}>{ch == null ? "—" : `${ch >= 0 ? "+" : ""}${ch.toFixed(1)}%`}</span>
                </Link>
              </li>
            );
          })}
        </ul>
      )}

      <UpcomingEvents style={{ marginTop: 12 }} limit={2} />

      <div className="quick-actions">
        <Link to="/forecast" className="btn btn-primary"><Sparkles size={15} /> {t("dashboard.quickForecastLabel")}</Link>
        <Link to="/dashboard" className="btn btn-ghost"><BellRing size={15} /> {t("quick.alerts")}</Link>
      </div>
    </div>
  );
}
