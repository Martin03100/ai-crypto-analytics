/** Warns that hit rates from few checked forecasts say almost nothing (a short run of luck looks like skill). */

import { AlertTriangle } from "lucide-react";
import { useLanguage } from "../context/LanguageContext";

export default function SmallSampleNote({ n = 30 }) {
  const { t } = useLanguage();
  return (
    <p className="alert alert-warn small-sample-note" role="note" data-testid="small-sample-note">
      <AlertTriangle size={14} aria-hidden="true" /> {t("leaderboard.smallSampleWarning", { n })}
    </p>
  );
}
