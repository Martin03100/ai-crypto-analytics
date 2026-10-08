/** Public event calendar: macro releases, option expiries, token unlocks and the Bitcoin halving, with reminders. */

import { ArrowLeft, Bell, BellOff, BellRing, CalendarDays, Hourglass } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { Card } from "../components/Card";
import LoadError from "../components/LoadError";
import { SkeletonLines } from "../components/Skeleton";
import Term from "../components/Term";
import { useAuth } from "../context/AuthContext";
import { useLanguage } from "../context/LanguageContext";
import { useToast } from "../context/ToastContext";
import { localeForLang } from "../i18n/locale";
import { usePageTitle } from "../hooks/usePageTitle";
import { daysUntil, eventName, groupByDay } from "../utils/calendar";

const FILTERS = ["all", "macro", "crypto", "unlock"];
const TERM = { fomc: "fomc", cpi: "cpi", nfp: "nfp", options_monthly: "optionsExpiry", options_quarterly: "optionsExpiry", unlock: "unlock", halving: "halving" };

function Countdown({ iso }) {
  const { t } = useLanguage();
  const d = daysUntil(iso);
  if (d <= 0) return <span className="badge badge-hold">{t("calendar.today")}</span>;
  if (d === 1) return <span className="badge badge-neutral">{t("calendar.tomorrow")}</span>;
  return <span className="text-sub">{t("calendar.inDays", { n: d })}</span>;
}

export default function Calendar() {
  const { t, lang } = useLanguage();
  const { user } = useAuth();
  const { push } = useToast();
  usePageTitle("calendar.pageTitle");
  const locale = localeForLang(lang);
  const [data, setData] = useState(null);
  const [failed, setFailed] = useState(false);
  const [filter, setFilter] = useState("all");
  const [reminders, setReminders] = useState(new Set());
  const [busy, setBusy] = useState(null);

  const load = useCallback(() => {
    setFailed(false);
    api.calendar(90).then(setData).catch(() => setFailed(true));
  }, []);
  useEffect(load, [load]);
  useEffect(() => {
    if (user) api.reminders().then((r) => setReminders(new Set(r.event_ids))).catch(() => {});
  }, [user]);

  const events = useMemo(() => (data?.events || []).filter((e) => filter === "all" || e.category === filter), [data, filter]);
  const groups = useMemo(() => groupByDay(events, locale), [events, locale]);

  const toggle = async (e) => {
    setBusy(e.id);
    const on = reminders.has(e.id);
    try {
      if (on) await api.removeReminder(e.id);
      else await api.addReminder(e.id);
      setReminders((prev) => {
        const next = new Set(prev);
        if (on) next.delete(e.id); else next.add(e.id);
        return next;
      });
      push(t(on ? "calendar.reminderOff" : "calendar.reminderOn"), "success", { translated: true });
    } catch (err) {
      push(err?.message || "error", "error");
    } finally {
      setBusy(null);
    }
  };

  const halving = data?.halving;
  const time = (iso) => new Date(iso).toLocaleTimeString(locale, { hour: "2-digit", minute: "2-digit" });

  return (
    <main className="standalone-page">
      <Link to="/" className="key-link standalone-back"><ArrowLeft size={14} /> {t("share.backToApp")}</Link>
      <h1 className="standalone-title">{t("calendar.title")}</h1>
      <p className="text-sub" style={{ marginBottom: 16 }}>{t("calendar.intro")}</p>

      {halving && (
        <Card className="halving-card">
          <div className="halving-row">
            <Hourglass size={20} aria-hidden="true" />
            <div>
              <strong><Term id="halving">{t("calendar.kind_halving")}</Term></strong>
              <p className="text-sub" style={{ margin: "2px 0 0" }}>
                {t("calendar.halvingText", { days: daysUntil(halving.at), blocks: Number(halving.blocks_left || 0).toLocaleString(locale),
                  date: new Date(halving.at).toLocaleDateString(locale, { month: "long", year: "numeric" }) })}
              </p>
            </div>
          </div>
        </Card>
      )}

      <div className="chip-row" role="radiogroup" aria-label={t("calendar.filter")} style={{ marginTop: 16 }}>
        {FILTERS.map((f) => (
          <button key={f} type="button" role="radio" aria-checked={filter === f} className={`chip ${filter === f ? "on" : ""}`} onClick={() => setFilter(f)}>
            {t(`calendar.filter_${f}`)}
          </button>
        ))}
      </div>

      {!user && <p className="text-sub calendar-login"><Bell size={13} aria-hidden="true" /> <Link to="/auth" className="key-link">{t("calendar.loginForReminders")}</Link></p>}

      {failed && <LoadError onRetry={load} />}
      {!data && !failed && <Card><SkeletonLines count={6} /></Card>}
      {data && groups.length === 0 && <Card><p className="text-sub">{t("calendar.empty")}</p></Card>}

      {groups.map((g) => (
        <section key={g.label} className="calendar-day">
          <h2 className="calendar-day-title"><CalendarDays size={14} aria-hidden="true" /> {g.label}</h2>
          <ul className="calendar-list">
            {g.items.map((e) => {
              const on = reminders.has(e.id);
              return (
                <li key={e.id} className={`card calendar-item impact-${e.impact}`}>
                  <span className="calendar-time mono">{time(e.at)}</span>
                  <div className="calendar-main">
                    <strong><Term id={TERM[e.kind]}>{eventName(t, e)}</Term></strong>
                    <span className="calendar-meta">
                      <span className={`badge ${e.impact === "high" ? "badge-sell" : "badge-neutral"}`}>{t(`calendar.impact_${e.impact}`)}</span>
                      {e.estimated && <span className="badge badge-neutral">{t("calendar.estimated")}</span>}
                      {e.kind === "unlock" && e.share_pct != null && <span className="text-sub">{t("calendar.unlockShare", { pct: e.share_pct })}</span>}
                      <Countdown iso={e.at} />
                    </span>
                  </div>
                  {user && (
                    <button type="button" className={`btn btn-ghost btn-sm btn-icon ${on ? "reminder-on" : ""}`} disabled={busy === e.id}
                            onClick={() => toggle(e)} aria-pressed={on} aria-label={t(on ? "calendar.removeReminder" : "calendar.addReminder", { name: eventName(t, e) })}
                            title={t(on ? "calendar.removeReminder" : "calendar.addReminder", { name: eventName(t, e) })}>
                      {on ? <BellRing size={15} /> : <BellOff size={15} />}
                    </button>
                  )}
                </li>
              );
            })}
          </ul>
        </section>
      ))}

      <p className="text-sub" style={{ marginTop: 20 }}>{t("calendar.sources")}</p>
    </main>
  );
}
