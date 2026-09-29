/** Account activity (audit) log. */

import { History } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api";
import { Card } from "./Card";
import InfoTip from "./InfoTip";
import LoadError from "./LoadError";
import { SkeletonLines } from "./Skeleton";
import { useLanguage } from "../context/LanguageContext";
import { localeForLang } from "../i18n/locale";

// Actions that deserve attention if the user did not do them.
const WARN_ACTIONS = new Set(["login_failed", "account_locked", "password_reset", "twofa_disabled", "email_changed"]);

export default function ActivityLog() {
  const { t, lang } = useLanguage();
  const [events, setEvents] = useState(null);
  const [failed, setFailed] = useState(false);

  function load() {
    setFailed(false);
    api.accountActivity().then((r) => setEvents(r.events)).catch(() => setFailed(true));
  }
  useEffect(load, []);

  const locale = localeForLang(lang);
  const formatTime = (iso) => (iso ? new Date(iso).toLocaleString(locale, { dateStyle: "short", timeStyle: "short" }) : "");

  return (
    <Card title={<>{t("activity.title")} <InfoTip text={t("activity.help")} /></>} icon={History} style={{ marginTop: 16 }}>
      {failed ? <LoadError onRetry={load} /> : events === null ? <SkeletonLines count={4} /> : events.length === 0 ? (
        <p className="text-sub">{t("activity.empty")}</p>
      ) : (
        <div className="activity-list" data-testid="activity-list">
          {events.map((ev, i) => (
            <div key={`${ev.created_at}-${i}`} className={`activity-row ${WARN_ACTIONS.has(ev.action) ? "warn" : ""}`}>
              <span className="mono activity-time">{formatTime(ev.created_at)}</span>
              <span className="activity-action">
                {t(`activity.action.${ev.action}`)}
                {ev.details && <span className="text-sub"> · {ev.details}</span>}
              </span>
              <span className="text-sub activity-device">{ev.device}{ev.ip ? ` · ${ev.ip}` : ""}</span>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}
