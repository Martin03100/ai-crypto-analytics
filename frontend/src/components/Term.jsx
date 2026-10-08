/** A word with a plain-language explanation on hover / tap and a link to the glossary. */

import { useId, useState } from "react";
import { Link } from "react-router-dom";
import { useLanguage } from "../context/LanguageContext";
import { glossaryEntry, localized } from "../data/glossary";

export default function Term({ id, children }) {
  const { t, lang } = useLanguage();
  const [open, setOpen] = useState(false);
  const tipId = useId();
  const entry = glossaryEntry(id);
  if (!entry) return children || null;
  return (
    <span className="term" onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)}>
      <button type="button" className="term-btn" aria-describedby={open ? tipId : undefined} aria-expanded={open}
              onClick={(e) => { e.preventDefault(); e.stopPropagation(); setOpen((v) => !v); }}
              onFocus={() => setOpen(true)} onBlur={(e) => { if (!e.currentTarget.parentElement.contains(e.relatedTarget)) setOpen(false); }}>
        {children || localized(entry.term, lang)}
      </button>
      {open && (
        <span role="tooltip" id={tipId} className="infotip-bubble term-bubble">
          <strong>{localized(entry.term, lang)}</strong> {localized(entry.def, lang)}{" "}
          <Link to={`/glossary#${entry.id}`} className="key-link">{t("glossary.more")}</Link>
        </span>
      )}
    </span>
  );
}
