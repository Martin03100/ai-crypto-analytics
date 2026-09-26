import { Keyboard } from "lucide-react";
import { useEffect, useRef } from "react";
import { useLanguage } from "../context/LanguageContext";

const ITEMS = [["D", "shortcuts.dashboard"], ["F", "shortcuts.forecast"], ["P", "shortcuts.portfolio"],
  ["M", "shortcuts.market"], ["A", "shortcuts.account"], ["S", "shortcuts.settings"], ["?", "shortcuts.help"]];

export default function ShortcutsHelp({ onClose }) {
  const { t } = useLanguage();
  const closeRef = useRef(null);
  useEffect(() => {
    closeRef.current?.focus();
    const onKey = (e) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="confirm-overlay" onClick={onClose}>
      <div className="confirm-modal" role="dialog" aria-modal="true" aria-labelledby="shortcuts-title" onClick={(e) => e.stopPropagation()}>
        <div className="confirm-icon confirm-icon-neutral"><Keyboard size={18} /></div>
        <h3 className="confirm-title" id="shortcuts-title">{t("shortcuts.title")}</h3>
        <ul className="shortcut-list">
          {ITEMS.map(([key, label]) => <li key={key}><kbd>{key}</kbd><span>{t(label)}</span></li>)}
        </ul>
        <div className="confirm-actions">
          <button className="btn btn-primary btn-sm" ref={closeRef} onClick={onClose}>{t("shortcuts.close")}</button>
        </div>
      </div>
    </div>
  );
}
