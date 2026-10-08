/** Download your own data: the full JSON archive or spreadsheet-ready CSV files. */

import { Download, FileSpreadsheet } from "lucide-react";
import { api } from "../api";
import { useLanguage } from "../context/LanguageContext";
import { Card } from "./Card";

const KINDS = ["forecasts", "evaluations", "alerts", "tips", "challenge"];

export default function DataExport() {
  const { t } = useLanguage();
  return (
    <Card title={t("settings.dataTitle")} icon={Download}>
      <p className="text-sub" style={{ marginTop: 0 }}>{t("settings.dataText")}</p>
      <a className="btn btn-ghost btn-sm" href={api.exportDataUrl()} download><Download size={14} /> {t("settings.dataButton")}</a>
      <hr className="divider" />
      <p className="text-sub" style={{ marginTop: 0 }}><FileSpreadsheet size={13} style={{ verticalAlign: -2, marginRight: 4 }} />{t("export.csvText")}</p>
      <div className="export-buttons">
        {KINDS.map((k) => (
          <a key={k} className="btn btn-ghost btn-sm" href={api.exportCsvUrl(k)} download>{t(`export.kind_${k}`)}</a>
        ))}
      </div>
    </Card>
  );
}
