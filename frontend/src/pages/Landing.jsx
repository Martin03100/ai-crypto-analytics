import { ArrowRight, BarChart3, Brain, Database, ShieldCheck, Trophy, Users } from "lucide-react";
import { Link } from "react-router-dom";
import CandlestickArt from "../components/CandlestickArt";
import { useLanguage } from "../context/LanguageContext";
import { usePageTitle } from "../hooks/usePageTitle";
import { LANGUAGES } from "../i18n/translations";

const FEATURES = [
  { icon: Brain, title: "landing.f1Title", text: "landing.f1Text" },
  { icon: Database, title: "landing.f2Title", text: "landing.f2Text" },
  { icon: Trophy, title: "landing.f3Title", text: "landing.f3Text" },
  { icon: Users, title: "landing.f4Title", text: "landing.f4Text" },
];

/** Verejna uvodna stranka pre neprihlasenych - co appka robi, cim je ina a
 * co NIE je (nie je to burza ani financne poradenstvo). */
export default function Landing() {
  const { t, lang, setLang } = useLanguage();
  usePageTitle("landing.pageTitle");
  return (
    <div className="landing">
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
            <h3>{t(title)}</h3>
            <p className="text-sub">{t(text)}</p>
          </div>
        ))}
      </section>

      <section className="landing-steps">
        <h2>{t("landing.howTitle")}</h2>
        <ol>
          {[1, 2, 3].map((n) => (
            <li key={n}><strong>{t(`landing.step${n}Title`)}</strong> <span className="text-sub">{t(`landing.step${n}Text`)}</span></li>
          ))}
        </ol>
      </section>

      <section className="card landing-honest">
        <ShieldCheck size={18} />
        <div>
          <h3>{t("landing.honestTitle")}</h3>
          <p className="text-sub">{t("landing.honestText")}</p>
        </div>
      </section>

      <footer className="landing-footer">
        <Link to="/privacy">{t("privacy.title")}</Link> · <Link to="/terms">{t("terms.title")}</Link>
      </footer>
    </div>
  );
}
