/** Public glossary: crypto and app terms explained in one or two sentences. */

import { ArrowLeft, Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { matches } from "../utils/viewHelpers";
import { useLanguage } from "../context/LanguageContext";
import { GLOSSARY, localized } from "../data/glossary";
import { usePageTitle } from "../hooks/usePageTitle";

export default function Glossary() {
  const { t, lang } = useLanguage();
  usePageTitle("glossary.pageTitle");
  const { hash } = useLocation();
  const [q, setQ] = useState("");
  const items = useMemo(() => GLOSSARY
    .map((g) => ({ id: g.id, term: localized(g.term, lang), def: localized(g.def, lang) }))
    .filter((g) => !q.trim() || matches(`${g.term} ${g.def}`, q))
    .sort((a, b) => a.term.localeCompare(b.term, lang)), [lang, q]);

  useEffect(() => {
    if (!hash) return;
    const el = document.getElementById(`term-${hash.slice(1)}`);
    if (el) {
      el.scrollIntoView({ block: "center" });
      el.classList.add("flash");
    }
  }, [hash]);

  return (
    <main className="standalone-page">
      <Link to="/" className="key-link standalone-back"><ArrowLeft size={14} /> {t("share.backToApp")}</Link>
      <h1 className="standalone-title">{t("glossary.title")}</h1>
      <p className="text-sub" style={{ marginBottom: 16 }}>{t("glossary.intro")}</p>
      <label className="search-field">
        <Search size={15} aria-hidden="true" />
        <input className="input" value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("glossary.search")} aria-label={t("glossary.search")} />
      </label>
      {items.length === 0 && <p className="text-sub">{t("glossary.none")}</p>}
      <dl className="glossary-list">
        {items.map((g) => (
          <div key={g.id} id={`term-${g.id}`} className="card glossary-item">
            <dt>{g.term}</dt>
            <dd>{g.def}</dd>
          </div>
        ))}
      </dl>
      <p className="text-sub" style={{ marginTop: 20 }}>{t("track.disclaimer")}</p>
    </main>
  );
}
