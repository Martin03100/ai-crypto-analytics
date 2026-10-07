/** Data sources list and, when present, the exact market signals the AI model received. */

import { AlertTriangle, Database, ListTree } from "lucide-react";
import { useLanguage } from "../context/LanguageContext";
import SignalList from "./SignalList";

export default function DataSources({ sources, signals }) {
  const { t } = useLanguage();
  const label = (source) => {
    const key = `sources.${source}`;
    const translated = t(key);
    return translated === key ? source : translated;
  };
  return (
    <>
      {Array.isArray(sources) && sources.length > 0 && (
        <p className="data-sources">
          <Database size={12} /> {t("common.dataSources")}: {sources.map(label).join(" · ")}
        </p>
      )}
      {Array.isArray(signals) && signals.length > 0 && (
        <details className="data-used">
          <summary><ListTree size={13} /> {t("signals.usedTitle", { n: signals.length })}</summary>
          <p className="text-sub">{t("signals.usedText")}</p>
          <SignalList items={signals} compact />
        </details>
      )}
      <p className="data-sources">
        <AlertTriangle size={12} /> {t("common.notAdviceShort")}
      </p>
    </>
  );
}
