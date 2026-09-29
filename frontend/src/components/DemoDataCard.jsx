/** Load or remove demo forecasts (for presentations). */

import { Loader2, Presentation, Trash2 } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { Card } from "./Card";
import { useConfirm } from "../context/ConfirmContext";
import { useLanguage } from "../context/LanguageContext";
import { useToast } from "../context/ToastContext";

export default function DemoDataCard() {
  const { t } = useLanguage();
  const { push } = useToast();
  const confirm = useConfirm();
  const navigate = useNavigate();
  const [busy, setBusy] = useState(null);

  async function load() {
    setBusy("load");
    try {
      const res = await api.loadDemoData();
      push(t("demo.loaded", { n: res.created, portfolios: res.portfolios ?? 0 }), "success");
      navigate("/forecast?tab=history");
    } catch (err) {
      push(err, "error");
    } finally {
      setBusy(null);
    }
  }

  async function remove() {
    if (!(await confirm(t("demo.removeConfirm")))) return;
    setBusy("remove");
    try {
      const res = await api.removeDemoData();
      push(t("demo.removed", { n: res.removed }), "success");
    } catch (err) {
      push(err, "error");
    } finally {
      setBusy(null);
    }
  }

  return (
    <Card title={t("demo.title")} icon={Presentation}>
      <p className="text-sub" style={{ marginBottom: 12, lineHeight: 1.6 }}>{t("demo.description")}</p>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <button className="btn btn-primary btn-sm" onClick={load} disabled={busy !== null}>
          {busy === "load" ? <Loader2 size={14} className="spin" /> : <Presentation size={14} />} {t("demo.load")}
        </button>
        <button className="btn btn-ghost btn-sm" onClick={remove} disabled={busy !== null}>
          {busy === "remove" ? <Loader2 size={14} className="spin" /> : <Trash2 size={14} />} {t("demo.remove")}
        </button>
      </div>
    </Card>
  );
}
