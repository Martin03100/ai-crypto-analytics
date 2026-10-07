/** Premium plan: what it adds, price, checkout or waitlist. */

import { ArrowLeft, Check, Crown } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { Card } from "../components/Card";
import WaitlistForm from "../components/WaitlistForm";
import { useAuth } from "../context/AuthContext";
import { useLanguage } from "../context/LanguageContext";
import { useToast } from "../context/ToastContext";
import { usePageTitle } from "../hooks/usePageTitle";
import { trackEvent } from "../utils/analytics";

const FREE = ["premium.free1", "premium.free2", "premium.free3", "premium.free4"];
const PAID = ["premium.paid1", "premium.paid2", "premium.paid3", "premium.paid4"];

export default function Premium() {
  const { t } = useLanguage();
  const { user } = useAuth();
  const { push } = useToast();
  const [params] = useSearchParams();
  const [info, setInfo] = useState(null);
  const [busy, setBusy] = useState(false);
  usePageTitle("premium.pageTitle");

  useEffect(() => { api.premiumInfo().then(setInfo).catch(() => setInfo({ billing_enabled: false })); }, []);

  const status = params.get("status");
  const limits = info?.limits;

  const buy = async () => {
    setBusy(true);
    trackEvent("checkout-start");
    try {
      const { url } = await api.checkout();
      window.location.assign(url);
    } catch (err) {
      push(err?.message || "error", "error");
      setBusy(false);
    }
  };

  return (
    <main className="standalone-page">
      <Link to="/" className="key-link standalone-back"><ArrowLeft size={14} /> {t("share.backToApp")}</Link>
      <h1 className="standalone-title">{t("premium.title")}</h1>
      <p className="text-sub" style={{ marginBottom: 20 }}>{t("premium.intro")}</p>

      {status === "success" && <div className="alert alert-success" role="status">{t("premium.success")}</div>}
      {status === "cancel" && <div className="alert alert-warn" role="status">{t("premium.cancelled")}</div>}

      <div className="plan-grid">
        <Card title={t("premium.freeTitle")}>
          <p className="plan-price">{t("premium.freePrice")}</p>
          <ul className="plan-list">
            {FREE.map((k) => <li key={k}><Check size={14} /> {t(k, { n: limits?.free?.schedules ?? 5 })}</li>)}
          </ul>
        </Card>
        <Card title="Premium" icon={Crown} glow="cyan">
          <p className="plan-price">{info?.billing_enabled ? info.price_label : t("premium.soon")}</p>
          <ul className="plan-list">
            {PAID.map((k) => <li key={k}><Check size={14} /> {t(k, { n: limits?.premium?.schedules ?? 20 })}</li>)}
          </ul>
          {user?.premium ? (
            <p className="text-sub">{t("premium.alreadyPremium")} <Link to="/settings" className="key-link">{t("nav.settings")}</Link></p>
          ) : info?.billing_enabled ? (
            user ? (
              <button className="btn btn-primary" onClick={buy} disabled={busy}>{t("premium.buy")}</button>
            ) : (
              <Link to="/auth?tab=register" className="btn btn-primary">{t("premium.signUpFirst")}</Link>
            )
          ) : null}
        </Card>
      </div>

      {info && !info.billing_enabled && <div style={{ marginTop: 20 }}><WaitlistForm id="premium-waitlist" /></div>}

      <Card title={t("premium.inviteTitle")} style={{ marginTop: 20 }}>
        <p className="text-sub">{t("premium.inviteText", { days: info?.referral_days ?? 30 })}</p>
        <Link to={user ? "/settings" : "/auth?tab=register"} className="key-link">{t("premium.inviteCta")}</Link>
      </Card>
      <p className="text-sub standalone-disclaimer">{t("track.disclaimer")}</p>
    </main>
  );
}
