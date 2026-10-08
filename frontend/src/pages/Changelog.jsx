/** "What's new" in the app, newest first. Opening it clears the "new" badge in the menu. */

import { ArrowLeft, Sparkles } from "lucide-react";
import { useEffect } from "react";
import { Link } from "react-router-dom";
import { useLanguage } from "../context/LanguageContext";
import { CHANGELOG, itemsFor, markChangelogSeen } from "../data/changelog";
import { localeForLang } from "../i18n/locale";
import { usePageTitle } from "../hooks/usePageTitle";

export default function Changelog() {
  const { t, lang } = useLanguage();
  usePageTitle("changelog.pageTitle");
  useEffect(() => { markChangelogSeen(); }, []);
  const fmt = (d) => new Date(`${d}T12:00:00Z`).toLocaleDateString(localeForLang(lang), { day: "numeric", month: "long", year: "numeric" });

  return (
    <main className="standalone-page">
      <Link to="/" className="key-link standalone-back"><ArrowLeft size={14} /> {t("share.backToApp")}</Link>
      <h1 className="standalone-title">{t("changelog.title")}</h1>
      <p className="text-sub" style={{ marginBottom: 20 }}>{t("changelog.intro")}</p>
      <ol className="changelog">
        {CHANGELOG.map((entry, i) => (
          <li key={entry.id} className="card changelog-entry">
            <div className="changelog-head">
              <time dateTime={entry.date}>{fmt(entry.date)}</time>
              {i === 0 && <span className="badge badge-buy"><Sparkles size={11} aria-hidden="true" /> {t("changelog.latest")}</span>}
            </div>
            <ul>
              {itemsFor(entry, lang).map((item) => <li key={item}>{item}</li>)}
            </ul>
          </li>
        ))}
      </ol>
    </main>
  );
}
