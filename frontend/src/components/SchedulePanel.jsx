/** Scheduled forecasts: create a recurring forecast and manage the existing plans. */

import { AlertTriangle, CalendarClock, CheckCircle2, Pause, Play, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { useConfirm } from "../context/ConfirmContext";
import { useLanguage } from "../context/LanguageContext";
import { useProviders } from "../context/ProvidersContext";
import { useToast } from "../context/ToastContext";
import { localeForLang } from "../i18n/locale";
import { COINS } from "../utils/coins";
import { formatHour, userTimeZone, weekdayNames } from "../utils/schedule";
import { Card } from "./Card";
import { SkeletonLines } from "./Skeleton";

const HORIZONS = ["24h", "1T", "1M"];
const HOURS = Array.from({ length: 24 }, (_, h) => h);

function StatusBadge({ schedule, t }) {
  if (!schedule.last_status) return <span className="badge badge-neutral">{t("schedule.statusWaiting")}</span>;
  if (schedule.last_status === "error") {
    const reason = schedule.last_error === "missing_key" ? t("schedule.errorMissingKey")
      : schedule.last_error === "limit" ? t("schedule.errorLimit") : t("schedule.errorFailed");
    return <span className="badge badge-sell" title={reason}><AlertTriangle size={11} /> {reason}</span>;
  }
  return (
    <span className="badge badge-buy">
      <CheckCircle2 size={11} /> {schedule.last_status === "fallback" ? t("schedule.statusFallback") : t("schedule.statusOk")}
    </span>
  );
}

export default function SchedulePanel({ onOpenHistory }) {
  const { t, lang } = useLanguage();
  const { push } = useToast();
  const confirm = useConfirm();
  const locale = localeForLang(lang);
  const providersCtx = useProviders();
  const providers = useMemo(
    () => [{ provider: "quant", label: t("provider.quantLabel") }, ...providersCtx.connected],
    [providersCtx.connected, t],
  );
  const days = useMemo(() => weekdayNames(locale), [locale]);

  const [items, setItems] = useState(null);
  const [maxSchedules, setMaxSchedules] = useState(5);
  const [form, setForm] = useState({ provider: "quant", coin: "BTC", horizon: "1T", frequency: "weekly", weekday: 0, hour: 8 });
  const [saving, setSaving] = useState(false);
  const [busyId, setBusyId] = useState(null);

  useEffect(() => {
    api.schedules()
      .then((r) => { setItems(r.items); if (r.max) setMaxSchedules(r.max); })
      .catch((err) => { setItems([]); push(err, "error"); });
  }, [push]);

  const set = (key, numeric = false) => (e) => {
    const value = numeric ? Number(e.target.value) : e.target.value;
    setForm((f) => ({ ...f, [key]: value }));
  };

  async function create(e) {
    e.preventDefault();
    setSaving(true);
    try {
      const created = await api.createSchedule({
        provider: form.provider, coin: form.coin, horizon: form.horizon, frequency: form.frequency,
        weekday: form.frequency === "weekly" ? form.weekday : null, hour: form.hour, minute: 0, timezone: userTimeZone(),
      });
      setItems((list) => [...(list || []), created]);
      push(t("schedule.created"), "success");
    } catch (err) {
      push(err, "error");
    } finally {
      setSaving(false);
    }
  }

  async function toggle(s) {
    setBusyId(s.id);
    try {
      const updated = await api.setScheduleActive(s.id, !s.active);
      setItems((list) => list.map((x) => (x.id === s.id ? updated : x)));
    } catch (err) {
      push(err, "error");
    } finally {
      setBusyId(null);
    }
  }

  async function remove(s) {
    if (!(await confirm(t("schedule.deleteConfirm")))) return;
    setBusyId(s.id);
    try {
      await api.deleteSchedule(s.id);
      setItems((list) => list.filter((x) => x.id !== s.id));
    } catch (err) {
      push(err, "error");
    } finally {
      setBusyId(null);
    }
  }

  function describe(s) {
    // Shown in the schedule's own time zone (the one it was created in); the zone is named only if it differs.
    const time = formatHour(s.hour, s.minute, locale) + (s.timezone !== userTimeZone() ? ` (${s.timezone})` : "");
    return s.frequency === "weekly" ? t("schedule.everyWeekday", { day: days[s.weekday], time }) : t("schedule.everyDay", { time });
  }

  const providerLabel = (key) => providers.find((p) => p.provider === key)?.label || key;
  const full = (items?.length || 0) >= maxSchedules;
  const isAi = form.provider !== "quant";

  return (
    <div className="grid" style={{ gap: 16 }}>
      <Card title={t("schedule.newTitle")} icon={CalendarClock}>
        <p className="text-sub" style={{ margin: "-6px 0 16px" }}>{t("schedule.intro")}</p>
        <form onSubmit={create}>
          <div className="form-grid">
            <div className="field">
              <label htmlFor="sch-provider">{t("provider.defaultLabel")}</label>
              <select id="sch-provider" className="select" value={form.provider} onChange={set("provider")}>
                {providers.map((p) => <option key={p.provider} value={p.provider}>{p.provider === "custom" ? t("provider.customLabel") : p.label}</option>)}
              </select>
            </div>
            <div className="field">
              <label htmlFor="sch-coin">{t("forecast.coinLabel")}</label>
              <select id="sch-coin" className="select" value={form.coin} onChange={set("coin")}>
                {COINS.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            <div className="field">
              <label htmlFor="sch-horizon">{t("forecast.horizonLabel")}</label>
              <select id="sch-horizon" className="select" value={form.horizon} onChange={set("horizon")}>
                {HORIZONS.map((h) => <option key={h} value={h}>{t(`forecast.horizon${h}`)}</option>)}
              </select>
            </div>
            <div className="field">
              <span className="field-label">{t("schedule.frequency")}</span>
              <div className="segmented" role="radiogroup" aria-label={t("schedule.frequency")}>
                {["daily", "weekly"].map((f) => (
                  <button key={f} type="button" role="radio" aria-checked={form.frequency === f}
                          className={`segmented-item ${form.frequency === f ? "active" : ""}`}
                          onClick={() => setForm((x) => ({ ...x, frequency: f }))}>
                    {t(`schedule.${f}`)}
                  </button>
                ))}
              </div>
            </div>
            {form.frequency === "weekly" && (
              <div className="field">
                <label htmlFor="sch-day">{t("schedule.day")}</label>
                <select id="sch-day" className="select" value={form.weekday} onChange={set("weekday", true)}>
                  {days.map((d, i) => <option key={d} value={i}>{d}</option>)}
                </select>
              </div>
            )}
            <div className="field">
              <label htmlFor="sch-hour">{t("schedule.time")}</label>
              <select id="sch-hour" className="select" value={form.hour} onChange={set("hour", true)}>
                {HOURS.map((h) => <option key={h} value={h}>{formatHour(h, 0, locale)}</option>)}
              </select>
            </div>
          </div>
          {isAi && <p className="field-hint" style={{ margin: "0 0 14px" }}><AlertTriangle size={12} style={{ verticalAlign: -1 }} /> {t("schedule.aiCostNote")}</p>}
          <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
            <button className="btn btn-primary" type="submit" disabled={saving || full}>
              <CalendarClock size={15} /> {saving ? t("common.saving") : t("schedule.create")}
            </button>
            {full && <span className="text-sub">{t("schedule.limitReached", { max: maxSchedules })}</span>}
          </div>
        </form>
      </Card>

      <Card title={`${t("schedule.listTitle")} · ${items?.length ?? 0}/${maxSchedules}`}>
        {items === null ? <SkeletonLines count={3} /> : items.length === 0 ? (
          <p className="text-sub" style={{ margin: 0 }}>{t("schedule.empty")}</p>
        ) : (
          <ul className="list">
            {items.map((s) => (
              <li key={s.id} className={`list-row ${s.active ? "" : "is-muted"}`}>
                <div className="list-main">
                  <div className="list-title">
                    <strong>{s.coin}</strong> · {t(`forecast.horizon${s.horizon}`)} · {providerLabel(s.provider)}
                  </div>
                  <div className="list-sub">
                    {describe(s)}
                    {s.active
                      ? <> · {t("schedule.nextRun", { when: new Date(s.next_run_at).toLocaleString(locale, { weekday: "short", day: "numeric", month: "numeric", hour: "2-digit", minute: "2-digit" }) })}</>
                      : <> · {t("schedule.paused")}</>}
                  </div>
                </div>
                <div className="list-actions">
                  <StatusBadge schedule={s} t={t} />
                  {s.last_forecast_id && onOpenHistory && (
                    <button className="btn btn-ghost btn-sm" onClick={onOpenHistory}>{t("schedule.viewResult")}</button>
                  )}
                  <button className="btn btn-ghost btn-sm btn-icon" onClick={() => toggle(s)} disabled={busyId === s.id}
                          aria-label={s.active ? t("schedule.pause") : t("schedule.resume")} title={s.active ? t("schedule.pause") : t("schedule.resume")}>
                    {s.active ? <Pause size={13} /> : <Play size={13} />}
                  </button>
                  <button className="btn btn-danger-ghost btn-sm btn-icon" onClick={() => remove(s)} disabled={busyId === s.id}
                          aria-label={t("common.delete")} title={t("common.delete")}>
                    <Trash2 size={13} />
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
