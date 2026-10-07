/** Link-in-bio page for social media profiles. */

import { BarChart3, ExternalLink } from "lucide-react";
import { Link } from "react-router-dom";
import { SOCIAL_LINKS } from "../config/social";
import { useLanguage } from "../context/LanguageContext";
import { usePageTitle } from "../hooks/usePageTitle";
import { usePremium } from "../hooks/usePremium";
import { safeUrl } from "../utils/safeUrl";

export default function Links() {
  const { t } = useLanguage();
  usePageTitle("links.pageTitle");
  const { mode } = usePremium();
  const socials = SOCIAL_LINKS.map((s) => ({ ...s, href: safeUrl(s.url) }));

  return (
    <main className="links-page">
      <div className="brand-mark links-logo"><BarChart3 size={26} /></div>
      <h1>AI Crypto Analytics</h1>
      <p className="text-sub">{t("links.tagline")}</p>

      <nav className="links-list" aria-label={t("links.pageTitle")}>
        <Link to="/auth?tab=register" className="btn btn-primary links-item">{t("links.tryApp")}</Link>
        <Link to="/track-record" className="btn btn-ghost links-item">{t("links.trackRecord")}</Link>
        {mode && <Link to="/premium" className="btn btn-ghost links-item">Premium</Link>}
      </nav>

      <h2 className="links-follow">{t("links.followTitle")}</h2>
      <nav className="links-list" aria-label={t("links.followTitle")}>
        {socials.map((s) => (s.href ? (
          <a key={s.id} href={s.href} target="_blank" rel="noopener noreferrer" className="btn btn-ghost links-item">
            {s.label} <ExternalLink size={13} />
          </a>
        ) : (
          <span key={s.id} className="btn btn-ghost links-item links-soon" aria-disabled="true">
            {s.label} <span className="text-sub">· {t("links.comingSoon")}</span>
          </span>
        )))}
      </nav>

      <p className="text-sub links-footer">{t("track.disclaimer")}</p>
    </main>
  );
}
