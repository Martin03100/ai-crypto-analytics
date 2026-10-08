/** "Report a bug / share an idea": a small dialog; messages go to the admin panel. */

import { Bug, Lightbulb, MessageSquare, MessageSquarePlus } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { api } from "../api";
import { useLanguage } from "../context/LanguageContext";
import { useToast } from "../context/ToastContext";

const KINDS = [["bug", Bug], ["idea", Lightbulb], ["other", MessageSquare]];

export function FeedbackDialog({ onClose }) {
  const { t } = useLanguage();
  const { push } = useToast();
  const { pathname } = useLocation();
  const [kind, setKind] = useState("bug");
  const [message, setMessage] = useState("");
  const [website, setWebsite] = useState("");
  const [busy, setBusy] = useState(false);
  const textRef = useRef(null);

  useEffect(() => {
    textRef.current?.focus();
    const onKey = (e) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const submit = async (e) => {
    e.preventDefault();
    if (message.trim().length < 5) {
      push(t("feedback.tooShort"), "error", { translated: true });
      return;
    }
    setBusy(true);
    try {
      await api.sendFeedback({ kind, message: message.trim(), page: pathname, website: website || undefined });
      push(t("feedback.thanks"), "success", { translated: true });
      onClose();
    } catch (err) {
      push(err?.message || "error", "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="confirm-overlay" onClick={onClose}>
      <form className="confirm-modal feedback-modal" role="dialog" aria-modal="true" aria-labelledby="feedback-title"
            onClick={(e) => e.stopPropagation()} onSubmit={submit}>
        <h3 className="confirm-title" id="feedback-title">{t("feedback.title")}</h3>
        <p className="text-sub" style={{ marginTop: 0 }}>{t("feedback.lead")}</p>
        <div className="tabs" role="radiogroup" aria-label={t("feedback.kind")}>
          {KINDS.map(([k, Icon]) => (
            <button key={k} type="button" role="radio" aria-checked={kind === k} className={`tab ${kind === k ? "active" : ""}`} onClick={() => setKind(k)}>
              <Icon size={13} style={{ marginRight: 5 }} aria-hidden="true" />{t(`feedback.kind_${k}`)}
            </button>
          ))}
        </div>
        <textarea ref={textRef} className="input feedback-text" rows={5} maxLength={2000} value={message}
                  onChange={(e) => setMessage(e.target.value)} placeholder={t(`feedback.placeholder_${kind}`)} aria-label={t("feedback.message")} />
        <input className="hp-field" tabIndex={-1} autoComplete="off" aria-hidden="true" value={website} onChange={(e) => setWebsite(e.target.value)} name="website" />
        <p className="text-sub feedback-note">{t("feedback.privacy")}</p>
        <div className="confirm-actions">
          <button type="button" className="btn btn-ghost btn-sm" onClick={onClose}>{t("common.cancel")}</button>
          <button type="submit" className="btn btn-primary btn-sm" disabled={busy}>{t("feedback.send")}</button>
        </div>
      </form>
    </div>
  );
}

export default function FeedbackButton({ className = "" }) {
  const { t } = useLanguage();
  const [open, setOpen] = useState(false);
  return (
    <>
      <button type="button" className={`feedback-btn ${className}`} onClick={() => setOpen(true)}>
        <MessageSquarePlus size={14} aria-hidden="true" /> {t("feedback.button")}
      </button>
      {open && <FeedbackDialog onClose={() => setOpen(false)} />}
    </>
  );
}
