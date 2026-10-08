/** Beginner summary of one forecast: traffic light + one sentence. */

import { useLanguage } from "../context/LanguageContext";
import { finalForecastPrice, predictedChangePct } from "../utils/forecastMath";
import { formatPrice } from "../utils/formatPrice";
import { verdictLight } from "../utils/viewHelpers";


export default function SimpleVerdict({ data, coin, horizon, model }) {
  const { t } = useLanguage();
  const change = predictedChangePct(data);
  const final = finalForecastPrice(data);
  const light = verdictLight(change);
  if (final == null) return null;
  const conf = Number(data?.confidence_score);
  return (
    <div className={`simple-verdict verdict-${light}`} role="status">
      <span className={`traffic traffic-${light} traffic-lg`} role="img" aria-label={t(`simple.light_${light}`)} />
      <div>
        <strong>{t(`simple.verdict_${light}`)}</strong>
        <p>{t("simple.verdictText", { model, coin, price: formatPrice(final), horizon: t(`forecast.horizon${horizon}`),
          change: `${change >= 0 ? "+" : ""}${(change ?? 0).toFixed(1)}` })}
          {Number.isFinite(conf) && <> {t("simple.verdictConfidence", { n: Math.round(conf) })}</>}</p>
      </div>
    </div>
  );
}
