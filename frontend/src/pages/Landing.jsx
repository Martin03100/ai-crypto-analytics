/** Landing page. */

import { ArrowRight, BarChart3, BellRing, Brain, Check, Crown, Database, Radar, ShieldCheck, Trophy, Users } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { api } from "../api";
import AnnouncementBar from "../components/AnnouncementBar";
import CandlestickArt from "../components/CandlestickArt";
import WaitlistForm from "../components/WaitlistForm";
import { useAppConfig } from "../context/AppConfigContext";
import { useLanguage } from "../context/LanguageContext";
import { usePageTitle } from "../hooks/usePageTitle";
import { usePremium } from "../hooks/usePremium";
import { LANGUAGES } from "../i18n/translations";

const FEATURES = [
  { icon: Brain, title: "landing.f1Title", text: "landing.f1Text" },
  { icon: Database, title: "landing.f2Title", text: "landing.f2Text" },
  { icon: Trophy, title: "landing.f3Title", text: "landing.f3Text" },
  { icon: Users, title: "landing.f4Title", text: "landing.f4Text" },
  { icon: Radar, title: "landing.f5Title", text: "landing.f5Text" },
  { icon: BellRing, title: "landing.f6Title", text: "landing.f6Text" },
];
const PREMIUM_POINTS = ["consensus", "smartModel", "simulator", "scanner", "tracker", "telegram"];

export default function Landing() {
  const { t, lang, setLang } = useLanguage();
  const { waitlist_enabled } = useAppConfig();
  const { mode } = usePremium();
  const [stats, setStats] = useState(null);
  useEffect(() => {
    api.trackRecord()
      .then((d) => setStats({ evaluated: d.totals?.evaluated ?? 0, direction_hit_pct: d.totals?.direction_hit_pct, providers: d.providers.length }))
      .catch(() => {});
  }, []);
  usePageTitle("landing.pageTitle");
  const { hash } = useLocation();
  useEffect(() => {
    if (hash === "#waitlist") document.getElementById("waitlist")?.scrollIntoView({ behavior: "smooth" });
  }, [hash]);
  return (
    <main className="landing">
      <AnnouncementBar />
      <header className="landing-nav">
        <div className="landing-brand"><div className="brand-mark"><BarChart3 size={18} /></div><strong>AI Crypto Analytics</strong></div>
        <div className="landing-nav-actions">
          <select className="select landing-lang" value={lang} onChange={(e) => setLang(e.target.value)} aria-label={t("landing.language")}>
            {LANGUAGES.map((l) => <option key={l.code} value={l.code}>{l.label}</option>)}
          </select>
          <Link to="/auth" className="btn btn-ghost btn-sm">{t("landing.login")}</Link>
        </div>
      </header>

      <section className="landing-hero">
        <span className="landing-eyebrow">{t("landing.eyebrow")}</span>
        <h1>{t("landing.headline")}</h1>
        <p className="landing-sub">{t("landing.sub")}</p>
        <div className="landing-cta">
          <Link to="/auth?tab=register" className="btn btn-primary">{t("landing.ctaPrimary")} <ArrowRight size={15} /></Link>
          <Link to="/auth" className="btn btn-ghost">{t("landing.ctaSecondary")}</Link>
        </div>
        <p className="landing-note">{t("landing.freeNote")}</p>
        <div className="landing-art"><CandlestickArt /></div>
      </section>

      <section className="landing-features">
        {FEATURES.map(({ icon: Icon, title, text }) => (
          <div key={title} className="card landing-feature">
            <div className="landing-feature-icon"><Icon size={18} /></div>
            <h2>{t(title)}</h2>
            <p className="text-sub">{t(text)}</p>
            {title === "landing.f3Title" && (
              <Link to="/track-record" className="key-link landing-feature-link">{t("track.landingLink")} <ArrowRight size={13} /></Link>
            )}
          </div>
        ))}
      </section>

      {stats?.evaluated > 0 && (
        <Link to="/track-record" className="landing-stats" aria-label={t("track.landingLink")}>
          <span><strong>{stats.evaluated}</strong> {t("landing.statChecked")}</span>
          <span><strong>{stats.direction_hit_pct}%</strong> {t("landing.statHit")}</span>
          <span><strong>{stats.providers}</strong> {t("landing.statModels")}</span>
          <span className="landing-stats-link">{t("track.landingLink")} <ArrowRight size={13} /></span>
        </Link>
      )}

      <section className="landing-steps">
        <h2>{t("landing.howTitle")}</h2>
        <ol>
          {[1, 2, 3].map((n) => (
            <li key={n}><strong>{t(`landing.step${n}Title`)}</strong> <span className="text-sub">{t(`landing.step${n}Text`)}</span></li>
          ))}
        </ol>
      </section>

      {mode && <section className="card landing-premium">
        <span className="premium-pill"><Crown size={13} /> Premium</span>
        <h2>{t("landing.premiumTitle")}</h2>
        <ul>
          {PREMIUM_POINTS.map((k) => <li key={k}><Check size={14} /> {t(`landing.premium.${k}`)}</li>)}
        </ul>
        <Link to="/premium" className="btn btn-primary btn-sm">{t("landing.premiumCta")} <ArrowRight size={14} /></Link>
      </section>}

      {waitlist_enabled && <WaitlistForm />}

      <section className="card landing-honest">
        <ShieldCheck size={18} />
        <div>
          <h2>{t("landing.honestTitle")}</h2>
          <p className="text-sub">{t("landing.honestText")}</p>
        </div>
      </section>

      <footer className="landing-footer">
        <Link to="/about">{t("about.title")}</Link> · <Link to="/track-record">{t("track.title")}</Link> · {mode && <><Link to="/premium">Premium</Link> · </>}<Link to="/status">{t("status.title")}</Link> ·{" "}
        <Link to="/privacy">{t("privacy.title")}</Link> · <Link to="/terms">{t("terms.title")}</Link>
      </footer>
    </main>
  );
}
