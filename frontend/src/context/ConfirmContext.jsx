import { AlertTriangle } from "lucide-react";
import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { useLanguage } from "./LanguageContext";

const ConfirmContext = createContext(null);

/** Poskytuje `confirm(message, opts) => Promise<boolean>` — nahradza
 * neblokujuce window.confirm() vlastnym glassmorphism modalom v styli appky.
 * Pouzitie: const ok = await confirmDelete(t("forecast.deleteConfirm", {...}));
 *
 * Prístupnosť: modal drží fokus vnútri seba (focus trap) kým je otvorený,
 * po zatvorení fokus vráti na prvok, ktorý bol aktívny predtým (typicky
 * tlačidlo, čo modal otvorilo), reaguje na Escape a pri otvorení sa
 * automaticky sfokusuje na "Zrušiť" tlačidlo. Bez toho by sa pri ovládaní
 * klávesnicou (Tab) dalo z modalu "vypadnúť" do zvyšku vizuálne prekrytej
 * stránky. */
export function ConfirmProvider({ children }) {
  const { t } = useLanguage();
  const [state, setState] = useState(null); // { message, resolve, title, confirmLabel }
  const modalRef = useRef(null);
  const cancelBtnRef = useRef(null);
  const previouslyFocusedRef = useRef(null);

  const confirm = useCallback((message, opts = {}) => {
    return new Promise((resolve) => {
      previouslyFocusedRef.current = document.activeElement;
      setState({
        message,
        resolve,
        title: opts.title || t("confirm.defaultTitle"),
        confirmLabel: opts.confirmLabel || t("confirm.defaultConfirmLabel"),
      });
    });
  }, [t]);

  function handleChoice(result) {
    state?.resolve(result);
    setState(null);
    // Vrat fokus tam, odkial sa modal otvoril (typicky tlacidlo "Odstranit").
    previouslyFocusedRef.current?.focus?.();
  }

  useEffect(() => {
    if (!state) return;
    cancelBtnRef.current?.focus();

    function handleKeyDown(e) {
      if (e.key === "Escape") {
        e.preventDefault();
        handleChoice(false);
        return;
      }
      if (e.key !== "Tab" || !modalRef.current) return;
      // Focus trap: Tab/Shift+Tab sa nedostane von z modalu.
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state]);

  return (
    <ConfirmContext.Provider value={confirm}>
      {children}
      {state && (
        <div className="confirm-overlay" onClick={() => handleChoice(false)}>
          <div
            className="confirm-modal"
            onClick={(e) => e.stopPropagation()}
            ref={modalRef}
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="confirm-modal-title"
            aria-describedby="confirm-modal-message"
          >
            <div className="confirm-icon"><AlertTriangle size={18} /></div>
            <h3 className="confirm-title" id="confirm-modal-title">{state.title}</h3>
            <p className="confirm-message" id="confirm-modal-message">{state.message}</p>
            <div className="confirm-actions">
              <button className="btn btn-ghost btn-sm" onClick={() => handleChoice(false)} ref={cancelBtnRef}>{t("confirm.cancel")}</button>
              <button className="btn btn-danger btn-sm" onClick={() => handleChoice(true)}>{state.confirmLabel}</button>
            </div>
          </div>
        </div>
      )}
    </ConfirmContext.Provider>
  );
}

export function useConfirm() {
  const ctx = useContext(ConfirmContext);
  if (!ctx) throw new Error("useConfirm musi byt pouzity vnutri ConfirmProvider");
  return ctx;
}
