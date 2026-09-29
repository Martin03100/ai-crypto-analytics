/** Inline "failed to load" message with a retry button. */

import { RefreshCw } from "lucide-react";
import { useLanguage } from "../context/LanguageContext";

export default function LoadError({ onRetry }) {
  const { t } = useLanguage();
  return (
    <div className="inline-error" role="alert">
      <span>{t("common.loadFailed")}</span>
      <button className="btn btn-ghost btn-sm" onClick={onRetry}><RefreshCw size={13} /> {t("common.retry")}</button>
    </div>
  );
}
