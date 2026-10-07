/** Public service status page. */

import { Activity, ArrowLeft, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { Card } from "../components/Card";
import LoadError from "../components/LoadError";
import { SkeletonLines } from "../components/Skeleton";
import { useLanguage } from "../context/LanguageContext";
import { localeForLang } from "../i18n/locale";
import { usePageTitle } from "../hooks/usePageTitle";

const GROUPS = ["core", "data", "ai"];

function UptimeBars({ data, t, locale }) {
  const tone = (v) => (v == null ? "none" : v >= 99 ? "up" : v >= 90 ? "degraded" : "down");
  return (
    <div className="uptime">
      <div className="uptime-bars" role="img" aria-label={t("status.uptimeLabel", { pct: data.uptime_pct ?? "—" })}>
        {data.days.map((d) => (
          <span key={d.day} className={`uptime-bar ${tone(d.uptime_pct)}`}
                title={`${new Date(`${d.day}T00:00:00Z`).toLocaleDateString(locale, { timeZone: "UTC" })}: ${d.uptime_pct == null ? t("status.noData") : `${d.uptime_pct} %`}`} />
        ))}
      </div>
      <span className="text-sub uptime-pct">{data.uptime_pct == null ? "" : t("status.uptime30", { pct: data.uptime_pct })}</span>
    </div>
  );
}

export default function StatusPage() {
  const { t, lang } = useLanguage();
  usePageTitle("status.title");
  const [status, setStatus] = useState(null);
  const [failed, setFailed] = useState(false);
  const [loading, setLoading] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    setFailed(false);
    api.serviceStatus().then(setStatus).catch(() => setFailed(true)).finally(() => setLoading(false));
  }, []);
  useEffect(load, [load]);
  const [history, setHistory] = useState(null);
  useEffect(() => { api.statusHistory().then(setHistory).catch(() => setHistory(null)); }, []);
  const historyOf = (id) => history?.services.find((s) => s.id === id);
  const locale = localeForLang(lang);

  return (
    <main className="standalone-page">
      <Link to="/" className="key-link standalone-back"><ArrowLeft size={14} /> {t("share.backToApp")}</Link>
      <h1 className="standalone-title">{t("status.title")}</h1>

      {status && (
        <div className={`status-banner ${status.overall}`} role="status">
          <span className={`status-dot ${status.overall}`} />
          <strong>{t(`status.overall.${status.overall}`)}</strong>
          <span className="text-sub" style={{ marginLeft: "auto" }}>
            {t("status.checkedAt", { time: new Date(status.checked_at).toLocaleTimeString(localeForLang(lang)) })}
          </span>
          <button className="btn btn-ghost btn-sm" onClick={load} disabled={loading} aria-label={t("common.retry")}>
            <RefreshCw size={13} className={loading ? "spin" : ""} />
          </button>
        </div>
      )}
      {failed && <LoadError onRetry={load} />}
      {!status && !failed && <SkeletonLines count={6} />}

      {status && GROUPS.map((group) => (
        <Card key={group} title={t(`status.group.${group}`)} icon={Activity} style={{ marginTop: 16 }}>
          {status.services.filter((s) => s.group === group).map((s) => (
            <div key={s.id} className="status-row" data-testid={`status-${s.id}`}>
              <span className={`status-dot ${s.status}`} aria-hidden="true" />
              <span className="status-name">{t(`status.service.${s.id}`)}</span>
              <span className="text-sub mono">{s.latency_ms != null && s.status !== "down" ? `${s.latency_ms} ms` : ""}</span>
              <span className={`status-label ${s.status}`}>{t(`status.state.${s.status}`)}</span>
              {historyOf(s.id) && <UptimeBars data={historyOf(s.id)} t={t} locale={locale} />}
            </div>
          ))}
          {group === "ai" && <p className="text-sub" style={{ marginTop: 8 }}>{t("status.aiNote")}</p>}
        </Card>
      ))}
    </main>
  );
}
