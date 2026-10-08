/** Choose between the beginner view (traffic lights, plain sentences) and the full analysis. */

import { Gauge, Lightbulb } from "lucide-react";
import { useLanguage } from "../context/LanguageContext";
import { useSimpleMode } from "../hooks/useSimpleMode";
import { Card } from "./Card";

export default function ViewModeCard() {
  const { t } = useLanguage();
  const { simple, setSimple } = useSimpleMode();
  return (
    <Card title={t("viewMode.title")} icon={simple ? Lightbulb : Gauge}>
      <p className="text-sub" style={{ marginTop: 0 }}>{t("viewMode.lead")}</p>
      <div className="tabs" role="radiogroup" aria-label={t("viewMode.title")}>
        <button type="button" role="radio" aria-checked={simple} className={`tab ${simple ? "active" : ""}`} onClick={() => setSimple(true)}>
          <Lightbulb size={14} style={{ marginRight: 6 }} aria-hidden="true" /> {t("viewMode.simple")}
        </button>
        <button type="button" role="radio" aria-checked={!simple} className={`tab ${!simple ? "active" : ""}`} onClick={() => setSimple(false)}>
          <Gauge size={14} style={{ marginRight: 6 }} aria-hidden="true" /> {t("viewMode.full")}
        </button>
      </div>
    </Card>
  );
}
