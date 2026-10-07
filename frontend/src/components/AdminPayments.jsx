/** Admin: connect Stripe with one secret key, set prices and see what is still missing before selling. */

import { CheckCircle2, CircleDashed, CreditCard, ExternalLink, Loader2, Unplug } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { useAppConfig } from "../context/AppConfigContext";
import { useConfirm } from "../context/ConfirmContext";
import { useLanguage } from "../context/LanguageContext";
import { useToast } from "../context/ToastContext";
import { humanizeError } from "../i18n/errorMessages";
import { Card } from "./Card";
import LoadError from "./LoadError";

const CHECKS = ["seller", "stripe", "payouts", "live", "premium_mode"];
const HELP_LINKS = { payouts: "https://dashboard.stripe.com/account/onboarding", live: "https://dashboard.stripe.com/apikeys" };
const toCents = (raw) => Math.round(Number(String(raw).replace(",", ".")) * 100);
const fromCents = (c) => (c ? String(c / 100) : "");

export default function AdminPayments() {
  const { t, lang } = useLanguage();
  const { push } = useToast();
  const confirm = useConfirm();
  const { reload } = useAppConfig();
  const [status, setStatus] = useState(null);
  const [failed, setFailed] = useState(false);
  const [key, setKey] = useState("");
  const [currency, setCurrency] = useState("eur");
  const [monthly, setMonthly] = useState("4.99");
  const [yearly, setYearly] = useState("39");
  const [busy, setBusy] = useState(false);

  const apply = (s) => {
    setStatus(s);
    if (s.monthly_cents) setMonthly(fromCents(s.monthly_cents));
    if (s.connected) setYearly(fromCents(s.yearly_cents));
    if (s.currency) setCurrency(s.currency);
  };
  const load = useCallback(() => { setFailed(false); api.adminPayments().then(apply).catch(() => setFailed(true)); }, []);
  useEffect(load, [load]);

  if (failed) return <LoadError onRetry={load} />;
  if (!status) return null;

  const save = async (e) => {
    e.preventDefault();
    const m = toCents(monthly);
    const y = yearly.trim() ? toCents(yearly) : null;
    if (!(m >= 50) || (y !== null && !(y >= 50))) {
      push(t("payments.badPrice"), "error", { translated: true });
      return;
    }
    setBusy(true);
    try {
      apply(await api.adminConnectPayments({ secret_key: key.trim(), currency, monthly_cents: m, yearly_cents: y }));
      setKey("");
      reload();
      push(t("payments.saved"), "success", { translated: true });
    } catch (err) {
      push(err?.message || "error", "error");
    } finally {
      setBusy(false);
    }
  };

  const disconnect = async () => {
    if (!(await confirm(t("payments.disconnectQ"), { title: t("admin.confirmTitle"), confirmLabel: t("payments.disconnect") }))) return;
    try {
      apply(await api.adminDisconnectPayments());
      reload();
    } catch (err) {
      push(err?.message || "error", "error");
    }
  };

  const env = status.source === "env";

  return (
    <>
      <Card title={t("payments.checklistTitle")} icon={CreditCard} glow={status.selling ? "emerald" : undefined}>
        <p className="text-sub" style={{ marginTop: 0 }}>{t(status.selling ? "payments.selling" : "payments.notSelling")}</p>
        <ul className="pay-checklist">
          {CHECKS.map((k) => {
            const ok = Boolean(status.checklist[k]);
            return (
              <li key={k} className={ok ? "ok" : ""}>
                {ok ? <CheckCircle2 size={16} /> : <CircleDashed size={16} />}
                <span>
                  <strong>{t(`payments.check_${k}`)}</strong>
                  {!ok && <span className="text-sub" style={{ display: "block" }}>{t(`payments.todo_${k}`)}
                    {HELP_LINKS[k] && <> <a href={HELP_LINKS[k]} target="_blank" rel="noopener noreferrer" className="key-link">Stripe <ExternalLink size={11} /></a></>}
                  </span>}
                </span>
              </li>
            );
          })}
        </ul>
        {status.account_error && <p className="alert alert-warn" role="alert">{humanizeError(status.account_error, lang)}</p>}
      </Card>

      <Card title={t("payments.stripeTitle")} style={{ marginTop: 16 }}>
        {env ? <p className="text-sub" style={{ margin: 0 }}>{t("payments.fromEnv")}</p> : (
          <form onSubmit={save} className="pay-form">
            <ol className="pay-steps text-sub">
              <li>{t("payments.step1")} <a href="https://dashboard.stripe.com/register" target="_blank" rel="noopener noreferrer" className="key-link">stripe.com <ExternalLink size={11} /></a></li>
              <li>{t("payments.step2")}</li>
              <li>{t("payments.step3")} <a href="https://dashboard.stripe.com/apikeys" target="_blank" rel="noopener noreferrer" className="key-link">API keys <ExternalLink size={11} /></a></li>
            </ol>
            <div className="field">
              <label htmlFor="pay-key">{t("payments.key")}</label>
              <input id="pay-key" className="input mono" type="password" autoComplete="off" value={key} onChange={(e) => setKey(e.target.value)}
                     placeholder={status.connected ? t("payments.keyKeep", { hint: status.key_hint }) : "sk_live_…"} />
            </div>
            <div className="grid grid-3">
              <div className="field">
                <label htmlFor="pay-currency">{t("payments.currency")}</label>
                <select id="pay-currency" className="select" value={currency} onChange={(e) => setCurrency(e.target.value)}>
                  <option value="eur">EUR (€)</option><option value="czk">CZK (Kč)</option><option value="usd">USD ($)</option>
                </select>
              </div>
              <div className="field">
                <label htmlFor="pay-monthly">{t("payments.monthly")}</label>
                <input id="pay-monthly" className="input" inputMode="decimal" value={monthly} onChange={(e) => setMonthly(e.target.value)} />
              </div>
              <div className="field">
                <label htmlFor="pay-yearly">{t("payments.yearly")}</label>
                <input id="pay-yearly" className="input" inputMode="decimal" value={yearly} placeholder={t("payments.yearlyEmpty")} onChange={(e) => setYearly(e.target.value)} />
              </div>
            </div>
            <p className="text-sub" style={{ marginTop: 0 }}>{t("payments.note")}</p>
            <div className="pay-actions">
              <button className="btn btn-primary" type="submit" disabled={busy || (!status.connected && !key.trim())}>
                {busy && <Loader2 size={15} className="spin" />} {t(status.connected ? "payments.update" : "payments.connect")}
              </button>
              {status.connected && <button type="button" className="btn btn-ghost" onClick={disconnect}><Unplug size={14} /> {t("payments.disconnect")}</button>}
            </div>
          </form>
        )}
      </Card>
    </>
  );
}
