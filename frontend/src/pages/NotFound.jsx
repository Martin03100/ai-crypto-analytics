/** Unknown address: says so instead of silently jumping to the home page (and keeps it out of search results). */

import { ArrowLeft } from "lucide-react";
import { useEffect } from "react";
import { Link } from "react-router-dom";
import { useLanguage } from "../context/LanguageContext";
import { usePageTitle } from "../hooks/usePageTitle";

export default function NotFound() {
  const { t } = useLanguage();
  usePageTitle("notFound.title");

  useEffect(() => {
    const meta = document.createElement("meta");
    meta.name = "robots";
    meta.content = "noindex";
    document.head.appendChild(meta);
    return () => meta.remove();
  }, []);

  return (
    <main className="standalone-page">
      <Link to="/" className="key-link standalone-back"><ArrowLeft size={14} /> {t("share.backToApp")}</Link>
      <h1 className="standalone-title">{t("notFound.title")}</h1>
      <p>{t("notFound.text")}</p>
      <p style={{ marginTop: 16, display: "flex", gap: 10, flexWrap: "wrap" }}>
        <Link to="/" className="btn btn-primary btn-sm">{t("notFound.home")}</Link>
        <Link to="/track-record" className="btn btn-ghost btn-sm">{t("track.title")}</Link>
      </p>
    </main>
  );
}
