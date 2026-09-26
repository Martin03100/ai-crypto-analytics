import { ChevronDown, Copy, Trash2 } from "lucide-react";
import { useState } from "react";
import { api } from "../api";
import { ActionBadge } from "./Badge";
import { useConfirm } from "../context/ConfirmContext";
import DataSources from "./DataSources";
import { useToast } from "../context/ToastContext";
import { useLanguage } from "../context/LanguageContext";
import { localeForLang } from "../i18n/locale";
import { copyToClipboard } from "../utils/copyToClipboard";

/** Jedna polozka v historii ulozenych portfolio analyz — rozbalitelna karta
 * s kopirovanim a mazanim (s potvrdzovacim dialogom). Vytiahnute z
 * Portfolio.jsx pre lepsiu citatelnost.
 *
 * Poznamka k i18n: `entry.holdings[].minca`, `entry.analysis_data.*` su
 * OBSAH VYGENEROVANY AI providerom (v jazyku, v akom bol prompt zadany) —
 * tento text sa NEPREKLADA klientom, iba staticke UI prvky okolo neho. */
export default function PortfolioHistoryItem({ entry, onDelete }) {
  const { push } = useToast();
  const confirm = useConfirm();
  const { t, lang } = useLanguage();
  const [open, setOpen] = useState(false);
  const locale = localeForLang(lang);

  async function handleCopy(e) {
    e.stopPropagation();
    const holdingsText = entry.holdings.map((h) => `${h.minca}: ${h.mnozstvo}`).join(", ");
    const lines = [
      t("portfolio.copyHeader", { date: new Date(entry.created_at).toLocaleString(locale) }),
      t("portfolio.copyModel", { model: entry.model_used }),
      t("portfolio.copyHoldings", { holdings: holdingsText }),
    ];
    if (entry.analysis_data?.odborna_analyza) lines.push("", entry.analysis_data.odborna_analyza);
    if (entry.analysis_data?.odporucania?.length) {
      lines.push("", t("portfolio.copyRecommendations"));
      entry.analysis_data.odporucania.forEach((r) => lines.push(`- ${r.minca}: ${r.akcia} — ${r.dovod}`));
    }
    const ok = await copyToClipboard(lines.join("\n"));
    push(ok ? t("common.copied") : t("common.copyFailed"), ok ? "success" : "error");
  }

  async function handleDelete(e) {
    e.stopPropagation();
    const ok = await confirm(t("portfolio.deleteConfirm"));
    if (!ok) return;
    try {
      await api.deletePortfolioAnalysis(entry.id);
      push(t("common.deleted"), "success");
      onDelete?.(entry.id);
    } catch (err) {
      push(err, "error");
    }
  }

  return (
    <div className="card" style={{ marginBottom: 12, padding: 0, overflow: "hidden" }}>
      <button
        onClick={() => setOpen((v) => !v)}
        style={{
          width: "100%", display: "flex", alignItems: "center", justifyContent: "space-between",
          padding: "14px 18px", background: "transparent", border: "none", color: "var(--text-primary)",
          cursor: "pointer", fontSize: 13,
        }}
      >
        <span>
          {entry.holdings.map((h) => h.minca).join(", ")} · {entry.model_used} ·{" "}
          <span className="text-sub">{new Date(entry.created_at).toLocaleString(locale)}</span>
        </span>
        <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <span className="btn btn-ghost btn-sm" onClick={handleCopy} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); handleCopy(e); } }} title={t("common.copy")} aria-label={t("common.copy")} role="button" tabIndex={0}><Copy size={12} /></span>
          <span className="btn btn-danger-ghost btn-sm" onClick={handleDelete} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); handleDelete(e); } }} title={t("common.delete")} aria-label={t("common.delete")} role="button" tabIndex={0}><Trash2 size={12} /></span>
          <ChevronDown size={16} style={{ transform: open ? "rotate(180deg)" : "none", transition: "transform 0.15s" }} />
        </span>
      </button>
      {open && (
        <div style={{ padding: "0 18px 18px" }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 12 }}>
            {entry.analysis_data?.odporucania?.map((rec, i) => (
              <div key={i} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "8px 10px", borderRadius: 8, background: "var(--bg-inset)" }}>
                <div>
                  <strong style={{ fontSize: 12.5 }}>{rec.minca}</strong>
                  <p className="text-sub" style={{ margin: "2px 0 0" }}>{rec.dovod}</p>
                </div>
                <ActionBadge action={rec.akcia} />
              </div>
            ))}
          </div>
          <p className="text-sub">{entry.analysis_data?.odborna_analyza}</p>
          <DataSources sources={entry.analysis_data?.zdroje_dat} />
        </div>
      )}
    </div>
  );
}
