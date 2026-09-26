import { Coins, Loader2 } from "lucide-react";
import { useEffect, useRef } from "react";
import { useLanguage } from "../context/LanguageContext";
import { localeForLang } from "../i18n/locale";

/** Potvrdzovacie okno s odhadom ceny, zobrazene PRED skutocnym volanim AI
 * (Forecast.jsx, Portfolio.jsx) - pouzivatel vidi priblizny naklad este
 * predtym, nez sa realne minu platene tokeny. Vizualne a klavesnicovo
 * (focus trap, Escape) zrkadli ConfirmContext.jsx, ale s neutralnou/
 * informativnou farbou namiesto varovnej cervenej - toto nie je
 * deštruktivna akcia. */
export default function CostConfirmModal({ estimate, providerLabel, onConfirm, onCancel, confirming }) {
  const { t, lang } = useLanguage();
  const modalRef = useRef(null);
  const confirmBtnRef = useRef(null);
  // onCancel prichadza ako nova inline funkcia pri kazdom renderi rodica -
  // ako zavislost efektu by sposobila opakovane presuvanie fokusu. Ref drzi
  // vzdy aktualnu verziu, efekt bezi len raz pri otvoreni okna.
  const onCancelRef = useRef(onCancel);
  onCancelRef.current = onCancel;

  useEffect(() => {
    confirmBtnRef.current?.focus();

    function handleKeyDown(e) {
      if (e.key === "Escape") {
        e.preventDefault();
        onCancelRef.current();
        return;
      }
      if (e.key !== "Tab" || !modalRef.current) return;
      const focusable = modalRef.current.querySelectorAll(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
      );
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, []);

  return (
    <div className="confirm-overlay" onClick={onCancel}>
      <div
        className="confirm-modal"
        onClick={(e) => e.stopPropagation()}
        ref={modalRef}
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="cost-modal-title"
        aria-describedby="cost-modal-message"
      >
        <div className="confirm-icon confirm-icon-neutral"><Coins size={18} /></div>
        <h3 className="confirm-title" id="cost-modal-title">{t("costConfirm.title")}</h3>
        <p className="confirm-message" id="cost-modal-message">
          {t("costConfirm.message", { provider: providerLabel })}
        </p>
        <div className="cost-breakdown">
          <div className="cost-row">
            <span>{t("costConfirm.tokens")}</span>
            <span>~{estimate.estimated_total_tokens.toLocaleString(localeForLang(lang))}</span>
          </div>
          <div className="cost-row cost-row-highlight">
            <span>{t("costConfirm.estimatedCost")}</span>
            <span>${estimate.estimated_cost_usd.toFixed(4)}</span>
          </div>
        </div>
        <p className="cost-disclaimer">{t("costConfirm.disclaimer")}</p>
        <div className="confirm-actions">
          <button className="btn btn-ghost btn-sm" onClick={onCancel}>{t("confirm.cancel")}</button>
          <button className="btn btn-primary btn-sm" onClick={onConfirm} ref={confirmBtnRef} disabled={confirming}>
            {confirming && <Loader2 size={14} className="spin" />} {t("costConfirm.confirmButton")}
          </button>
        </div>
      </div>
    </div>
  );
}
