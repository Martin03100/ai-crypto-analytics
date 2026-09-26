import { Trophy } from "lucide-react";
import { useState } from "react";
import { api } from "../api";
import { useLanguage } from "../context/LanguageContext";
import { useToast } from "../context/ToastContext";
import { formatPrice } from "../utils/formatPrice";

/** Sutaz "tvoj tip vs AI" pri ulozenej predikcii: zadanie tipu (do 2 hodin
 * od vytvorenia predikcie), cakanie na vysledok, alebo vysledok suboja. */
export default function TipBox({ entryId, accuracy, onTipped }) {
  const { t } = useLanguage();
  const { push } = useToast();
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);
  if (!accuracy) return null;

  const prices = accuracy.actual_prices || [];
  if (accuracy.tip_outcome) {
    return (
      <div className="tip-box">
        <strong>{t(`challenge.outcome_${accuracy.tip_outcome}`)}</strong>
        <p className="text-sub" style={{ margin: "4px 0 0" }}>
          {t("challenge.details", {
            tip: formatPrice(accuracy.tip_price), ai: formatPrice(accuracy.ai_final_price), actual: formatPrice(prices[prices.length - 1]),
          })}
        </p>
      </div>
    );
  }
  if (accuracy.tip_price != null) {
    return <p className="text-sub" style={{ marginTop: 6 }}>{t("challenge.yourTip", { price: formatPrice(accuracy.tip_price) })} {t("challenge.waiting")}</p>;
  }
  if (!accuracy.can_tip) return null;

  async function submit() {
    const price = Number(value);
    if (!(price > 0)) return;
    setBusy(true);
    try {
      await api.submitTip(entryId, price);
      push(t("challenge.submitted"), "success");
      onTipped?.(price);
    } catch (err) {
      push(err, "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="tip-box">
      <p className="text-sub" style={{ margin: "0 0 8px" }}>
        <Trophy size={13} /> {t("challenge.prompt", { ai: formatPrice(accuracy.ai_final_price) })}
      </p>
      <div style={{ display: "flex", gap: 8 }}>
        <input className="input" type="number" min="0" step="any" inputMode="decimal" value={value}
          onChange={(e) => setValue(e.target.value)} placeholder={t("challenge.placeholder")} aria-label={t("challenge.placeholder")} />
        <button className="btn btn-primary btn-sm" onClick={submit} disabled={busy || !(Number(value) > 0)}>{t("challenge.submit")}</button>
      </div>
    </div>
  );
}
