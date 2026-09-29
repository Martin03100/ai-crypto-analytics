/** Toast notifications. */

import { AlertTriangle, CheckCircle2, XCircle } from "lucide-react";
import { createContext, useCallback, useContext, useState } from "react";
import { useLanguage } from "./LanguageContext";
import { humanizeError } from "../i18n/errorMessages";

const ToastContext = createContext(null);
const TOAST_DURATION_MS = 4000;

let idCounter = 0;

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const { lang } = useLanguage();

  // Errors are humanized here; pass { translated: true } when the message is already user-facing text.
  const push = useCallback((message, type = "success", { translated = false } = {}) => {
    const displayMessage = type === "error" && !translated ? humanizeError(message, lang) : String(message ?? "");
    const id = ++idCounter;
    setToasts((prev) => [...prev, { id, message: displayMessage, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, TOAST_DURATION_MS);
  }, [lang]);

  return (
    <ToastContext.Provider value={{ push }}>
      {children}
      <div className="toast-stack">
        {toasts.map((t) => (
          <div key={t.id} className={`toast ${t.type}`}>
            {t.type === "error" && <XCircle size={16} color="var(--crimson-fg)" />}
            {t.type === "warn" && <AlertTriangle size={16} color="var(--amber-fg)" />}
            {t.type === "success" && <CheckCircle2 size={16} color="var(--emerald-fg)" />}
            <span>{t.message}</span>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast musi byt pouzity vnutri ToastProvider");
  return ctx;
}
