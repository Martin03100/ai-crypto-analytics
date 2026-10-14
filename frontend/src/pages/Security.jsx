/** Responsible disclosure: how to report a vulnerability and what the reporter can expect. */

import { ArrowLeft } from "lucide-react";
import { Link } from "react-router-dom";
import { useLanguage } from "../context/LanguageContext";
import { usePageTitle } from "../hooks/usePageTitle";

const SECTIONS = ["how", "scope", "rules", "promise"];

export default function Security() {
  const { t } = useLanguage();
  usePageTitle("security.title");
  return (
    <main className="standalone-page">
      <Link to="/" className="key-link standalone-back"><ArrowLeft size={14} /> {t("share.backToApp")}</Link>
      <h1 className="standalone-title">{t("security.title")}</h1>
      <p style={{ lineHeight: 1.7 }}>{t("security.intro")}</p>
      <p className="card legal-operator">
        {t("legal.contact")}: <a href="mailto:aicryptoanalytics7@gmail.com?subject=Security" className="key-link">aicryptoanalytics7@gmail.com</a>
      </p>
      {SECTIONS.map((k) => (
        <section key={k} style={{ marginBottom: 20 }}>
          <h2 style={{ fontSize: 16, marginBottom: 8 }}>{t(`security.${k}Title`)}</h2>
          <p style={{ lineHeight: 1.7, color: "var(--text-secondary)", fontSize: 13.5 }}>{t(`security.${k}`)}</p>
        </section>
      ))}
    </main>
  );
}
