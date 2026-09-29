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
            </div>
          ))}
          {group === "ai" && <p className="text-sub" style={{ marginTop: 8 }}>{t("status.aiNote")}</p>}
        </Card>
      ))}
    </main>
  );
}
