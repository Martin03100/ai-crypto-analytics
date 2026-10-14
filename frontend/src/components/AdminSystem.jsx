/** Admin overview: where the database lives, which services are set up and whether the background jobs run. */

import { CheckCircle2, CircleDashed, ServerCog } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { useLanguage } from "../context/LanguageContext";
import { localeForLang } from "../i18n/locale";
import { Card } from "./Card";
import LoadError from "./LoadError";

const CHECKS = ["proxy_signature", "trusted_proxy_hops", "scheduler", "email", "captcha", "sentry_backend",
  "sentry_frontend", "google_login", "telegram"];
// Off on purpose until the owner decides to use them: shown as optional, not as a problem.
const OPTIONAL = new Set(["google_login", "telegram"]);

export default function AdminSystem() {
  const { t, lang } = useLanguage();
  const [data, setData] = useState(null);
  const [failed, setFailed] = useState(false);
  const load = useCallback(() => { setFailed(false); api.adminSystem().then(setData).catch(() => setFailed(true)); }, []);
  useEffect(load, [load]);

  if (failed) return <LoadError onRetry={load} />;
  if (!data?.checks) return null;
  // The browser part of Sentry is configured at build time on Netlify, so the page itself knows.
  const checks = { ...data.checks, sentry_frontend: Boolean(import.meta.env.VITE_SENTRY_DSN) };
  const db = data.database || {};
  const lastRun = data.job_runs?.price_alerts;

  return (
    <Card title={t("admin.sys.title")} icon={ServerCog} style={{ marginTop: 16 }}>
      <p className="text-sub" style={{ marginTop: 0 }} data-testid="admin-db">
        {t("admin.sys.database", { engine: db.engine, provider: db.provider })}
      </p>
      {db.render && <p className="alert alert-warn" role="alert">{t("admin.sys.renderWarning")}</p>}
      <ul className="pay-checklist">
        {CHECKS.map((k) => {
          const ok = Boolean(checks[k]);
          return (
            <li key={k} className={ok ? "ok" : ""}>
              {ok ? <CheckCircle2 size={16} /> : <CircleDashed size={16} />}
              <span>
                <strong>{t(`admin.sys.check_${k}`)}</strong>
                {!ok && <span className="text-sub" style={{ display: "block" }}>
                  {OPTIONAL.has(k) && `${t("admin.sys.optional")} `}{t(`admin.sys.todo_${k}`)}
                </span>}
              </span>
            </li>
          );
        })}
      </ul>
      <p className="text-sub" style={{ marginBottom: 0 }}>
        {t("admin.sys.lastJobs", { time: lastRun ? new Date(lastRun).toLocaleString(localeForLang(lang)) : "—" })}
      </p>
    </Card>
  );
}
