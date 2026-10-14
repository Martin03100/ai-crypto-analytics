/** Public FAQ, with FAQPage structured data so search engines can show the answers. */

import { ArrowLeft } from "lucide-react";
import { useEffect, useMemo } from "react";
import { Link } from "react-router-dom";
import { useLanguage } from "../context/LanguageContext";
import { FAQ } from "../data/faq";
import { localized } from "../data/glossary";
import { usePageTitle } from "../hooks/usePageTitle";
import { usePremium } from "../hooks/usePremium";

export default function Faq() {
  const { t, lang } = useLanguage();
  const { mode } = usePremium();
  usePageTitle("faq.title");
  const items = useMemo(() => FAQ.map((f) => ({
    id: f.id, q: localized(f.q, lang), a: localized(mode && f.aPremium ? f.aPremium : f.a, lang),
  })), [lang, mode]);

  useEffect(() => {
    const script = document.createElement("script");
    script.type = "application/ld+json";
    script.textContent = JSON.stringify({
      "@context": "https://schema.org", "@type": "FAQPage",
      mainEntity: items.map((f) => ({ "@type": "Question", name: f.q, acceptedAnswer: { "@type": "Answer", text: f.a } })),
    });
    document.head.appendChild(script);
    return () => script.remove();
  }, [items]);

  return (
    <main className="standalone-page">
      <Link to="/" className="key-link standalone-back"><ArrowLeft size={14} /> {t("share.backToApp")}</Link>
      <h1 className="standalone-title">{t("faq.title")}</h1>
      <p className="text-sub" style={{ marginBottom: 16 }}>{t("faq.intro")}</p>
      <div className="faq-list">
        {items.map((f) => (
          <details key={f.id} id={`faq-${f.id}`} className="card faq-item">
            <summary>{f.q}</summary>
            <p>{f.a}{f.id === "report" && <> <Link to="/security" className="key-link">{t("security.title")}</Link></>}
              {f.id === "accuracy" && <> <Link to="/track-record" className="key-link">{t("track.title")}</Link></>}
              {f.id === "data" && <> <Link to="/privacy" className="key-link">{t("privacy.title")}</Link></>}</p>
          </details>
        ))}
      </div>
      <p className="text-sub" style={{ marginTop: 20 }}>{t("faq.more")} <a href="mailto:aicryptoanalytics7@gmail.com" className="key-link">aicryptoanalytics7@gmail.com</a></p>
    </main>
  );
}
