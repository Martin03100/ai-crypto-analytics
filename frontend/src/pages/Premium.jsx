/** Premium plan: what it adds, price, trial, consent and checkout (or the waitlist before payments start). */

import { ArrowLeft, BarChart3, BellRing, CalendarClock, Check, Crown, Mail, Minus, Rocket, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api";
import WaitlistForm from "../components/WaitlistForm";
import { useAppConfig } from "../context/AppConfigContext";
import { useAuth } from "../context/AuthContext";
import { useLanguage } from "../context/LanguageContext";
import { useToast } from "../context/ToastContext";
import { usePageTitle } from "../hooks/usePageTitle";
import { trackEvent } from "../utils/analytics";

const HIGHLIGHTS = [
  { icon: BellRing, key: "alerts" },
  { icon: Mail, key: "briefing" },
  { icon: BarChart3, key: "stats" },
  { icon: CalendarClock, key: "schedules" },
];

function Cell({ value }) {
  if (value === true) return <Check size={15} className="plan-yes" aria-label="✓" />;
  if (value === false) return <Minus size={15} className="plan-no" aria-label="—" />;
  return <span>{value}</span>;
}

export default function Premium() {
  const { t } = useLanguage();
  const { user } = useAuth();
  const { push } = useToast();
  const { waitlist_enabled, referrals_enabled } = useAppConfig();
  const [params] = useSearchParams();
  const [info, setInfo] = useState(null);
  const [terms, setTerms] = useState(false);
  const [startNow, setStartNow] = useState(false);
  const [busy, setBusy] = useState(false);
  usePageTitle("premium.pageTitle");

  useEffect(() => { api.premiumInfo().then(setInfo).catch(() => setInfo({ billing_enabled: false })); }, []);

  const status = params.get("status");
  const free = info?.limits?.free || { schedules: 5, alerts: 1 };
  const paid = info?.limits?.premium || { schedules: 20, alerts: 25 };
  const trial = info?.trial_days || 0;

  const rows = [
    ["rowForecasts", true, true],
    ["rowTrack", true, true],
    ["rowAlerts", free.alerts, paid.alerts],
    ["rowSchedules", free.schedules, paid.schedules],
    ["rowBriefing", false, true],
    ["rowStats", false, true],
    ["rowBadge", false, true],
    ["rowSupport", false, true],
  ];

  const buy = async () => {
    setBusy(true);
    trackEvent("checkout-start");
    try {
      const { url } = await api.checkout({ accept_terms: terms, start_immediately: startNow });
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
        <p className="text-sub premium-fine">{t(trial > 0 ? "premium.fineTrial" : "premium.fine", { days: trial, price: info.price_label })}</p>
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
        <div className="premium-price">
          {info?.billing_enabled
            ? <><strong>{info.price_label}</strong>{trial > 0 && <span className="premium-trial">{t("premium.trialBadge", { days: trial })}</span>}</>
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

      <div className="card premium-compare">
        <table className="lb-table">
          <thead><tr><th /><th>{t("premium.freeTitle")}</th><th className="premium-col">Premium</th></tr></thead>
          <tbody>
            {rows.map(([key, a, b]) => (
              <tr key={key}><td>{t(`premium.${key}`)}</td><td><Cell value={a} /></td><td className="premium-col"><Cell value={b} /></td></tr>
            ))}
          </tbody>
        </table>
        {action && <div className="premium-action">{action}</div>}
      </div>

      {info && !info.billing_enabled && waitlist_enabled && <div style={{ marginTop: 20 }}><WaitlistForm id="premium-waitlist" /></div>}

      {referrals_enabled && (
        <div className="card premium-invite">
          <strong>{t("premium.inviteTitle")}</strong>
          <p className="text-sub">{t("premium.inviteText", { days: info?.referral_days ?? 30 })}</p>
          <Link to={user ? "/settings" : "/auth?tab=register"} className="key-link">{t("premium.inviteCta")}</Link>
        </div>
      )}

      <section className="premium-faq">
        <h2>{t("premium.faqTitle")}</h2>
        {[1, 2, 3, 4].map((n) => (
          <details key={n} className="card">
            <summary>{t(`premium.q${n}`)}</summary>
            <p className="text-sub">{t(`premium.a${n}`)}</p>
          </details>
        ))}
      </section>

      <p className="text-sub standalone-disclaimer"><ShieldCheck size={12} style={{ verticalAlign: -2 }} /> {t("premium.secure")} {t("track.disclaimer")}</p>
    </main>
  );
}
