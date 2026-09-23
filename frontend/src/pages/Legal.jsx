import { Link } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { useLanguage } from "../context/LanguageContext";
import { usePageTitle } from "../hooks/usePageTitle";

/** Spolocny layout pre Privacy Policy a Terms of Service — obe su
 * verejne dostupne aj bez prihlasenia (viz App.jsx, routy mimo
 * RequireAuth), aby na ne vedel odkazovat aj Auth screen. */
function LegalPage({ titleKey, sections }) {
  const { t } = useLanguage();
  usePageTitle(titleKey);
  return (
    <div style={{ minHeight: "100vh", padding: "40px 20px", maxWidth: 720, margin: "0 auto" }}>
      <Link to="/" className="key-link" style={{ display: "inline-flex", alignItems: "center", gap: 6, marginBottom: 24 }}>
        <ArrowLeft size={14} /> {t("legal.backToApp")}
      </Link>
      <h1 style={{ fontSize: 24, marginBottom: 4 }}>{t(titleKey)}</h1>
      <p className="text-sub" style={{ marginBottom: 28 }}>{t("legal.lastUpdated")}</p>
      <p style={{ lineHeight: 1.7, marginBottom: 28 }}>{t(`${sections}.intro`)}</p>
      <LegalSections prefix={sections} t={t} />
    </div>
  );
}

const PRIVACY_SECTIONS = ["dataCollected", "cookies", "thirdParty", "rights", "contact"];
const TERMS_SECTIONS = ["notAdvice", "account", "acceptableUse", "liability", "changes"];

function LegalSections({ prefix, t }) {
  const sections = prefix === "privacy" ? PRIVACY_SECTIONS : TERMS_SECTIONS;
  return (
    <>
      {sections.map((key) => (
        <section key={key} style={{ marginBottom: 24 }}>
          <h2 style={{ fontSize: 16, marginBottom: 8 }}>{t(`${prefix}.${key}Title`)}</h2>
          <p style={{ lineHeight: 1.7, color: "var(--text-secondary)", fontSize: 13.5 }}>{t(`${prefix}.${key}`)}</p>
        </section>
      ))}
    </>
  );
}

export function PrivacyPolicy() {
  return <LegalPage titleKey="privacy.title" sections="privacy" />;
}

export function TermsOfService() {
  return <LegalPage titleKey="terms.title" sections="terms" />;
}
