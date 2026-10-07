/** Premium plan: what it adds, monthly or yearly price, trial, consent and checkout (or the waitlist before payments start). */

import {
  ArrowLeft, BellRing, Check, Crown, FileDown, GraduationCap, Lightbulb, LineChart, Minus, Radar, Rocket, Scale, Send,
  ShieldCheck, Sun, Target, Wallet,
} from "lucide-react";
import { useEffect, useState } from "react";
import { Link, Navigate, useSearchParams } from "react-router-dom";
import { api } from "../api";
import WaitlistForm from "../components/WaitlistForm";
import { useAppConfig } from "../context/AppConfigContext";
import { useAuth } from "../context/AuthContext";
import { useLanguage } from "../context/LanguageContext";
import { useToast } from "../context/ToastContext";
import { usePageTitle } from "../hooks/usePageTitle";
import { usePremium } from "../hooks/usePremium";
import { trackEvent } from "../utils/analytics";
import { localizePriceLabel } from "../utils/price";

const HIGHLIGHTS = [
  { icon: Scale, key: "consensus" },
  { icon: Lightbulb, key: "smartModel" },
  { icon: LineChart, key: "simulator" },
  { icon: Radar, key: "scanner" },
  { icon: Wallet, key: "tracker" },
  { icon: BellRing, key: "alerts" },
  { icon: Send, key: "telegram" },
  { icon: Sun, key: "briefing" },
  { icon: FileDown, key: "report" },
];

function Cell({ value, t }) {
  if (value === true) return <><Check size={15} className="plan-yes" aria-hidden="true" /><span className="sr-only">{t("premium.included")}</span></>;
  if (value === false) return <><Minus size={15} className="plan-no" aria-hidden="true" /><span className="sr-only">{t("premium.notIncluded")}</span></>;
  return <span>{value}</span>;
}

export default function Premium() {
  const { t } = useLanguage();
  const { user } = useAuth();
  const { push } = useToast();
  const { waitlist_enabled, referrals_enabled } = useAppConfig();
  const { mode, loaded } = usePremium();
  const [params] = useSearchParams();
  const [info, setInfo] = useState(null);
  const [plan, setPlan] = useState("yearly");
  const [terms, setTerms] = useState(false);
  const [startNow, setStartNow] = useState(false);
  const [busy, setBusy] = useState(false);
  usePageTitle("premium.pageTitle");

  useEffect(() => { api.premiumInfo().then(setInfo).catch(() => setInfo({ enabled: false })); }, []);

  if (!loaded) return null;
  if (!mode || info?.enabled === false) return <Navigate to="/" replace />;

  const status = params.get("status");
  const free = info?.limits?.free || { schedules: 5, alerts: 1 };
  const paid = info?.limits?.premium || { schedules: 20, alerts: 25 };
  const trial = info?.trial_days || 0;
  const yearly = Boolean(info?.yearly);
  const chosen = yearly ? plan : "monthly";
  const price = localizePriceLabel(chosen === "yearly" ? info?.price_label_yearly : info?.price_label, t);

  const rows = [
    ["rowForecasts", true, true],
    ["rowTrack", true, true],
    ["rowScanner", t("premium.top5"), t("premium.allCoins")],
    ["rowAlerts", free.alerts, paid.alerts],
    ["rowSmartAlerts", false, true],
    ["rowSchedules", free.schedules, paid.schedules],
    ["rowConsensus", false, true],
    ["rowSmartModel", false, true],
    ["rowSimulator", false, true],
    ["rowTracker", false, true],
    ["rowReport", false, true],
    ["rowTelegram", false, true],
    ["rowBriefing", false, true],
    ["rowStats", false, true],
    ["rowBadge", false, true],
    ["rowSupport", false, true],
  ];

  const buy = async () => {
    setBusy(true);
    trackEvent("checkout-start", { plan: chosen });
    try {
      const { url } = await api.checkout({ plan: chosen, accept_terms: terms, start_immediately: startNow });
      window.location.assign(url);
    } catch (err) {
      push(err?.message || "error", "error");
      setBusy(false);
    }
  };

  let action = null;
  if (user?.premium) {
    action = <p className="text-sub">{t("premium.alreadyPremium")} <Link to="/settings" className="key-link">{t("nav.settings")}</Link></p>;
  } else if (info?.billing_enabled && !user) {
    action = <Link to="/auth?tab=register" className="btn btn-primary">{t("premium.signUpFirst")}</Link>;
  } else if (info?.billing_enabled) {
    action = (
      <div className="premium-buy">
        <label className="toggle-row">
          <input type="checkbox" checked={terms} onChange={(e) => setTerms(e.target.checked)} />
          <span>{t("premium.consentTerms")} <Link to="/terms" className="key-link">{t("terms.title")}</Link> · <Link to="/privacy" className="key-link">{t("privacy.title")}</Link></span>
        </label>
        <label className="toggle-row">
          <input type="checkbox" checked={startNow} onChange={(e) => setStartNow(e.target.checked)} />
          <span>{t("premium.consentStart")}</span>
        </label>
        <button className="btn btn-primary premium-cta" onClick={buy} disabled={busy || !terms || !startNow}>
          <Rocket size={15} /> {trial > 0 ? t("premium.startTrial", { days: trial }) : t("premium.buy")}
        </button>
        <p className="text-sub premium-fine">{t(trial > 0 ? "premium.fineTrial" : "premium.fine", { days: trial, price })}</p>
      </div>
    );
  }

  return (
    <main className="standalone-page premium-page">
      <Link to="/" className="key-link standalone-back"><ArrowLeft size={14} /> {t("share.backToApp")}</Link>

      <section className="premium-hero">
        <span className="premium-pill"><Crown size={13} /> Premium</span>
        <h1>{t("premium.headline")}</h1>
        <p className="text-sub">{t("premium.intro")}</p>
        {info?.billing_enabled && yearly && (
          <div className="plan-switch" role="radiogroup" aria-label={t("premium.planLabel")}>
            {["monthly", "yearly"].map((p) => (
              <button key={p} type="button" role="radio" aria-checked={chosen === p} className={`plan-option ${chosen === p ? "on" : ""}`} onClick={() => setPlan(p)}>
                {t(`premium.plan_${p}`)}{p === "yearly" && <span className="plan-save">{t("premium.yearlyBadge")}</span>}
              </button>
            ))}
          </div>
        )}
        <div className="premium-price">
          {info?.billing_enabled
            ? <><strong>{price}</strong>{trial > 0 && <span className="premium-trial">{t("premium.trialBadge", { days: trial })}</span>}</>
            : <strong>{t("premium.soon")}</strong>}
        </div>
      </section>

      {status === "success" && <div className="alert alert-success" role="status">{t("premium.success")}</div>}
      {status === "cancel" && <div className="alert alert-warn" role="status">{t("premium.cancelled")}</div>}

      <div className="premium-highlights">
        {HIGHLIGHTS.map(({ icon: Icon, key }) => (
          <div key={key} className="card premium-highlight">
            <div className="landing-feature-icon"><Icon size={18} /></div>
            <h2>{t(`premium.h.${key}`)}</h2>
            <p className="text-sub">{t(`premium.h.${key}Text`, { n: paid.alerts, s: paid.schedules })}</p>
          </div>
        ))}
      </div>

      <div className="premium-audience">
        <div className="card">
          <h2><GraduationCap size={16} /> {t("premium.forBeginners")}</h2>
          <p className="text-sub">{t("premium.forBeginnersText")}</p>
        </div>
        <div className="card">
          <h2><Target size={16} /> {t("premium.forPros")}</h2>
          <p className="text-sub">{t("premium.forProsText")}</p>
        </div>
      </div>

      <div className="card premium-compare">
        <table className="lb-table">
          <thead><tr><th /><th>{t("premium.freeTitle")}</th><th className="premium-col">Premium</th></tr></thead>
          <tbody>
            {rows.map(([key, a, b]) => (
              <tr key={key}><td>{t(`premium.${key}`)}</td><td><Cell value={a} t={t} /></td><td className="premium-col"><Cell value={b} t={t} /></td></tr>
            ))}
          </tbody>
        </table>
        {action && <div className="premium-action">{action}</div>}
      </div>

      {info && !info.billing_enabled && waitlist_enabled && !user?.premium && <div style={{ marginTop: 20 }}><WaitlistForm id="premium-waitlist" /></div>}

      {referrals_enabled && (
        <div className="card premium-invite">
          <strong>{t("premium.inviteTitle")}</strong>
          <p className="text-sub">{t("premium.inviteText", { days: info?.referral_days ?? 30, trial: info?.referral_trial_days ?? 14 })}</p>
          <Link to={user ? "/settings" : "/auth?tab=register"} className="key-link">{t("premium.inviteCta")}</Link>
        </div>
      )}

      <section className="premium-faq">
        <h2>{t("premium.faqTitle")}</h2>
        {[1, 2, 3, 4, 5].map((n) => (
          <details key={n} className="card">
            <summary>{t(`premium.q${n}`)}</summary>
            <p className="text-sub">{t(`premium.a${n}`, { days: info?.referral_days ?? 30, trial: info?.referral_trial_days ?? 14 })}</p>
          </details>
        ))}
      </section>

      <p className="text-sub standalone-disclaimer"><ShieldCheck size={12} style={{ verticalAlign: -2 }} /> {t("premium.secure")} {t("track.disclaimer")}</p>
    </main>
  );
}
