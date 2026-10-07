/** Admin panel: overview, users, waitlist and app settings. Visible only to admins (ADMIN_USERNAMES + 2FA). */

import { Ban, Crown, Download, LayoutGrid, Search, Settings2, ShieldAlert, Users } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { api } from "../api";
import { Card } from "../components/Card";
import LoadError from "../components/LoadError";
import { useAppConfig } from "../context/AppConfigContext";
import { useAuth } from "../context/AuthContext";
import { useConfirm } from "../context/ConfirmContext";
import { useLanguage } from "../context/LanguageContext";
import { useToast } from "../context/ToastContext";
import { localeForLang } from "../i18n/locale";
import { usePageTitle } from "../hooks/usePageTitle";

const TABS = [["overview", LayoutGrid], ["users", Users], ["waitlist", Download], ["settings", Settings2]];
const SWITCHES = ["signups_enabled", "chat_enabled", "compare_enabled", "backtest_enabled", "tipsters_enabled",
  "waitlist_enabled", "digest_enabled", "referrals_enabled"];
const NUMBERS = ["free_schedules", "premium_schedules", "free_alerts", "premium_alerts", "premium_trial_days", "referral_reward_days"];
const OPERATOR = [["operator_name", 120], ["operator_business_id", 60], ["operator_address", 200]];

function Overview() {
  const { t } = useLanguage();
  const [s, setS] = useState(null);
  const [failed, setFailed] = useState(false);
  const load = useCallback(() => { setFailed(false); api.adminStats().then(setS).catch(() => setFailed(true)); }, []);
  useEffect(load, [load]);
  if (failed) return <LoadError onRetry={load} />;
  if (!s) return null;
  const tiles = [["users", s.users], ["users_7d", s.users_7d], ["premium", s.premium], ["paying", s.paying],
    ["waitlist", s.waitlist], ["digest_subscribers", s.digest_subscribers], ["referred", s.referred],
    ["forecasts", s.forecasts], ["forecasts_7d", s.forecasts_7d], ["evaluated", s.evaluated], ["duels", s.duels],
    ["disabled", s.disabled]];
  return (
    <>
      <div className="admin-tiles">
        {tiles.map(([k, v]) => (
          <div key={k} className="card track-stat"><span className="track-stat-value">{v}</span><span className="text-sub">{t(`admin.stat.${k}`)}</span></div>
        ))}
      </div>
      <Card title={t("admin.payments")} icon={Crown} style={{ marginTop: 16 }}>
        <p className="text-sub">{t(s.billing_enabled ? "admin.billingOn" : "admin.billingOff")}</p>
        {Object.keys(s.waitlist_by_source).length > 0 && (
          <p className="text-sub">{t("admin.sources")}: {Object.entries(s.waitlist_by_source).map(([k, v]) => `${k} ${v}`).join(" · ")}</p>
        )}
      </Card>
    </>
  );
}

function UsersTab() {
  const { t, lang } = useLanguage();
  const { push } = useToast();
  const confirm = useConfirm();
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState(null);
  const load = useCallback(() => api.adminUsers(q, page).then(setData).catch((e) => push(e?.message || "error", "error")), [q, page, push]);
  useEffect(() => { const id = setTimeout(load, 250); return () => clearTimeout(id); }, [load]);

  const change = async (u, changes, question) => {
    if (question && !(await confirm(question, { title: t("admin.confirmTitle"), confirmLabel: t("admin.confirm") }))) return;
    try {
      const row = await api.adminUpdateUser(u.id, changes);
      setData((prev) => ({ ...prev, items: prev.items.map((x) => (x.id === row.id ? row : x)) }));
      push(t("admin.saved"), "success", { translated: true });
    } catch (e) {
      push(e?.message || "error", "error");
    }
  };
  const date = (iso) => (iso ? new Date(iso).toLocaleDateString(localeForLang(lang)) : "—");
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;

  return (
    <Card>
      <div className="admin-search">
        <Search size={15} />
        <input className="input" value={q} placeholder={t("admin.searchPlaceholder")} aria-label={t("admin.searchPlaceholder")}
               onChange={(e) => { setQ(e.target.value); setPage(1); }} />
      </div>
      {data && (
        <>
          <p className="text-sub" style={{ margin: "10px 0" }}>{t("admin.found", { n: data.total })}</p>
          <div className="table-scroll">
            <table className="lb-table admin-table">
              <thead>
                <tr><th>{t("admin.colUser")}</th><th>{t("admin.colJoined")}</th><th>{t("admin.colPlan")}</th><th>{t("admin.colActions")}</th></tr>
              </thead>
              <tbody>
                {data.items.map((u) => (
                  <tr key={u.id} className={u.disabled ? "admin-row-disabled" : ""}>
                    <td>
                      <strong>{u.username}</strong>{u.admin && <span className="badge badge-neutral admin-badge">admin</span>}
                      <span className="text-sub" style={{ display: "block" }}>{u.email}{u.nickname ? ` · ${u.nickname}` : ""}</span>
                    </td>
                    <td>{date(u.created_at)}{u.email_verified === false && <span className="text-sub" style={{ display: "block" }}>{t("admin.unverified")}</span>}</td>
                    <td>{u.premium ? `Premium ${t("admin.until", { date: date(u.premium_until) })}` : t("membership.free")}{u.paying && <span className="text-sub" style={{ display: "block" }}>Stripe</span>}</td>
                    <td>
                      <div className="admin-actions">
                        <button className="btn btn-ghost btn-sm" onClick={() => change(u, { add_premium_days: 30 })}>{t("admin.add30")}</button>
                        {u.premium && <button className="btn btn-ghost btn-sm" onClick={() => change(u, { remove_premium: true }, t("admin.removePremiumQ", { user: u.username }))}>{t("admin.removePremium")}</button>}
                        {u.nickname && <button className="btn btn-ghost btn-sm" onClick={() => change(u, { clear_nickname: true })}>{t("admin.clearNickname")}</button>}
                        {!u.admin && (
                          <button className="btn btn-danger-ghost btn-sm" onClick={() => change(u, { disabled: !u.disabled }, u.disabled ? null : t("admin.blockQ", { user: u.username }))}>
                            <Ban size={13} /> {t(u.disabled ? "admin.unblock" : "admin.block")}
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {pages > 1 && (
            <div className="admin-pager">
              <button className="btn btn-ghost btn-sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>←</button>
              <span className="text-sub">{page} / {pages}</span>
              <button className="btn btn-ghost btn-sm" disabled={page >= pages} onClick={() => setPage(page + 1)}>→</button>
            </div>
          )}
        </>
      )}
    </Card>
  );
}

function WaitlistTab() {
  const { t, lang } = useLanguage();
  const [data, setData] = useState(null);
  useEffect(() => { api.adminWaitlist().then(setData).catch(() => setData({ items: [], total: 0 })); }, []);
  if (!data) return null;
  return (
    <Card>
      <div className="admin-actions" style={{ justifyContent: "space-between", marginBottom: 10 }}>
        <span className="text-sub">{t("admin.found", { n: data.total })}</span>
        <a className="btn btn-ghost btn-sm" href={api.adminWaitlistCsvUrl()} download><Download size={13} /> CSV</a>
      </div>
      <div className="table-scroll">
        <table className="lb-table">
          <thead><tr><th>E-mail</th><th>{t("admin.colSource")}</th><th>{t("admin.colLang")}</th><th>{t("admin.colJoined")}</th></tr></thead>
          <tbody>
            {data.items.map((r) => (
              <tr key={r.email}><td>{r.email}</td><td>{r.source || "direct"}</td><td>{r.lang}</td>
                <td>{r.created_at ? new Date(r.created_at).toLocaleDateString(localeForLang(lang)) : ""}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function SettingsTab() {
  const { t } = useLanguage();
  const { push } = useToast();
  const { reload } = useAppConfig();
  const [values, setValues] = useState(null);
  const [saving, setSaving] = useState(false);
  useEffect(() => { api.adminSettings().then((r) => setValues(r.values)).catch((e) => push(e?.message || "error", "error")); }, [push]);
  if (!values) return null;
  const set = (k, v) => setValues((prev) => ({ ...prev, [k]: v }));

  const save = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const res = await api.adminSaveSettings(values);
      setValues(res.values);
      reload();
      push(t("admin.saved"), "success", { translated: true });
    } catch (err) {
      push(err?.message || "error", "error");
    } finally {
      setSaving(false);
    }
  };

  return (
    <form onSubmit={save} className="admin-settings">
      <Card title={t("admin.features")}>
        <div className="admin-switches">
          {SWITCHES.map((k) => (
            <label key={k} className="toggle-row">
              <input type="checkbox" checked={Boolean(values[k])} onChange={(e) => set(k, e.target.checked)} />
              <span><strong>{t(`admin.set.${k}`)}</strong></span>
            </label>
          ))}
        </div>
      </Card>
      <Card title={t("admin.premiumSettings")} style={{ marginTop: 16 }}>
        <div className="grid grid-2">
          <div className="field">
            <label>{t("admin.set.premium_price_label")}</label>
            <input className="input" maxLength={40} value={values.premium_price_label} onChange={(e) => set("premium_price_label", e.target.value)} />
          </div>
          {NUMBERS.map((k) => (
            <div key={k} className="field">
              <label>{t(`admin.set.${k}`)}</label>
              <input className="input" type="number" min={0} value={values[k]} onChange={(e) => set(k, Number.parseInt(e.target.value, 10) || 0)} />
            </div>
          ))}
        </div>
        <p className="text-sub">{t("admin.stripeNote")}</p>
      </Card>
      <Card title={t("admin.operator")} style={{ marginTop: 16 }}>
        <p className="text-sub" style={{ marginTop: 0 }}>{t("admin.operatorNote")}</p>
        <div className="grid grid-2">
          {OPERATOR.map(([k, max]) => (
            <div key={k} className="field">
              <label>{t(`admin.set.${k}`)}</label>
              <input className="input" maxLength={max} value={values[k]} onChange={(e) => set(k, e.target.value)} />
            </div>
          ))}
        </div>
      </Card>
      <Card title={t("admin.announcement")} style={{ marginTop: 16 }}>
        <div className="field">
          <label>{t("admin.announcementText")}</label>
          <textarea className="input" rows={2} maxLength={280} value={values.announcement} onChange={(e) => set("announcement", e.target.value)} />
        </div>
        <div className="tabs">
          {["info", "success", "warn"].map((lvl) => (
            <button type="button" key={lvl} className={`tab ${values.announcement_level === lvl ? "active" : ""}`} onClick={() => set("announcement_level", lvl)}>
              {t(`admin.level.${lvl}`)}
            </button>
          ))}
        </div>
      </Card>
      <button className="btn btn-primary" type="submit" disabled={saving} style={{ marginTop: 16 }}>{saving ? t("common.saving") : t("common.save")}</button>
    </form>
  );
}

export default function Admin() {
  const { t } = useLanguage();
  const { user } = useAuth();
  const [tab, setTab] = useState("overview");
  usePageTitle("admin.title");

  if (!user?.admin) return <Navigate to="/dashboard" replace />;

  return (
    <div>
      <div className="topbar">
        <div>
          <h1 className="page-title">{t("admin.title")}</h1>
          <p className="page-sub">{t("admin.sub")}</p>
        </div>
      </div>
      {!user.totpEnabled ? (
        <div className="alert alert-warn" role="alert">
          <ShieldAlert size={14} style={{ marginRight: 6 }} />{t("admin.need2fa")} <Link to="/settings" className="key-link">{t("nav.settings")}</Link>
        </div>
      ) : (
        <>
          <div className="tabs" style={{ marginBottom: 16 }}>
            {TABS.map(([k, Icon]) => (
              <button key={k} className={`tab ${tab === k ? "active" : ""}`} onClick={() => setTab(k)}><Icon size={14} style={{ marginRight: 6 }} />{t(`admin.tab.${k}`)}</button>
            ))}
          </div>
          {tab === "overview" && <Overview />}
          {tab === "users" && <UsersTab />}
          {tab === "waitlist" && <WaitlistTab />}
          {tab === "settings" && <SettingsTab />}
        </>
      )}
    </div>
  );
}
