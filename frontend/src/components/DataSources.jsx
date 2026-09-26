import { AlertTriangle, Database } from "lucide-react";
import { useLanguage } from "../context/LanguageContext";

/** Zdroje dat, z ktorych AI analyza vychadzala (backend posiela kluce,
 * napr. "hyperliquid" - tu sa prelozia do jazyka appky; starsie ulozene
 * analyzy maju texty, tie sa zobrazia tak, ako su) + kratke upozornenie,
 * ze nejde o financne poradenstvo. */
export default function DataSources({ sources }) {
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
      <p className="data-sources">
        <AlertTriangle size={12} /> {t("common.notAdviceShort")}
      </p>
    </>
  );
}
