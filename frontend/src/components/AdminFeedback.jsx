/** Admin: bug reports and ideas sent from the app. */

import { Check, RotateCcw, Trash2 } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";
import { useConfirm } from "../context/ConfirmContext";
import { useLanguage } from "../context/LanguageContext";
import { useToast } from "../context/ToastContext";
import { localeForLang } from "../i18n/locale";
import { Card } from "./Card";
import LoadError from "./LoadError";

const KIND_BADGE = { bug: "badge-sell", idea: "badge-buy", other: "badge-neutral" };

export default function AdminFeedback() {
  const { t, lang } = useLanguage();
  const { push } = useToast();
  const confirm = useConfirm();
  const [status, setStatus] = useState("new");
  const [data, setData] = useState(null);
  const [failed, setFailed] = useState(false);

  const latest = useRef(0);
  const load = useCallback(() => {
    const request = ++latest.current;       // a slower answer for an older filter must not win
    setFailed(false);
    api.adminFeedback(status)
      .then((d) => { if (request === latest.current) setData(d); })
      .catch(() => { if (request === latest.current) setFailed(true); });
  }, [status]);
  useEffect(load, [load]);

  const mark = async (id, next) => {
    try {
      await api.adminFeedbackStatus(id, next);
      load();
    } catch (err) {
      push(err?.message || "error", "error");
    }
  };

  const remove = async (id) => {
    if (!(await confirm(t("admin.feedbackDeleteQ"), { title: t("admin.confirmTitle"), confirmLabel: t("common.delete") }))) return;
    try {
      await api.adminFeedbackDelete(id);
      load();
    } catch (err) {
      push(err?.message || "error", "error");
    }
  };

  return (
    <Card>
      <div className="tabs" role="radiogroup" aria-label={t("admin.feedbackFilter")} style={{ marginBottom: 12 }}>
        {["new", "done", "all"].map((s) => (
          <button key={s} type="button" role="radio" aria-checked={status === s} className={`tab ${status === s ? "active" : ""}`} onClick={() => setStatus(s)}>
            {t(`admin.feedback_${s}`)}{s === "new" && data?.new ? ` (${data.new})` : ""}
          </button>
        ))}
      </div>
      {failed && <LoadError onRetry={load} />}
      {data && data.items.length === 0 && <p className="text-sub">{t("admin.feedbackEmpty")}</p>}
      {data && data.items.length > 0 && (
        <ul className="feedback-list">
          {data.items.map((f) => (
            <li key={f.id} className="feedback-item">
              <div className="feedback-meta">
                <span className={`badge ${KIND_BADGE[f.kind] || "badge-neutral"}`}>{t(`feedback.kind_${f.kind}`)}</span>
                <span className="text-sub">{new Date(f.created_at).toLocaleString(localeForLang(lang))}</span>
                <span className="text-sub">· {f.username || t("admin.feedbackAnon")}</span>
                {f.page && <span className="text-sub mono">· {f.page}</span>}
                {f.lang && <span className="text-sub">· {f.lang.toUpperCase()}</span>}
              </div>
              <p>{f.message}</p>
              <div className="feedback-actions">
                {f.status === "new"
                  ? <button className="btn btn-ghost btn-sm" onClick={() => mark(f.id, "done")}><Check size={13} /> {t("admin.feedbackDone")}</button>
                  : <button className="btn btn-ghost btn-sm" onClick={() => mark(f.id, "new")}><RotateCcw size={13} /> {t("admin.feedbackReopen")}</button>}
                <button className="btn btn-danger-ghost btn-sm" onClick={() => remove(f.id)} aria-label={t("common.delete")}><Trash2 size={13} /></button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
