/** Public, read-only view of a shared forecast. */

import { ArrowLeft, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import { AccuracyBadge, ConfidenceBadge, RiskBadge } from "../components/Badge";
import ShareBar from "../components/ShareBar";
import ShareImages from "../components/ShareImages";
import { Card } from "../components/Card";
import DataSources from "../components/DataSources";
import ForecastChart, { hasForecastSeries } from "../components/ForecastChart";
import { SkeletonChart } from "../components/Skeleton";
import { useLanguage } from "../context/LanguageContext";
import { localeForLang } from "../i18n/locale";
import { usePageTitle } from "../hooks/usePageTitle";
import { stripMockTag } from "../utils/mockText";

export default function SharedForecast() {
  const { token } = useParams();
  const { t, lang } = useLanguage();
  usePageTitle("share.pageTitle");
  const [shared, setShared] = useState(null);
  const [error, setError] = useState(null);
  const locale = localeForLang(lang);

  useEffect(() => {
    api.sharedForecast(token).then(setShared).catch((err) => setError(err?.status === 404 ? "notFound" : "failed"));
  }, [token]);

  const data = shared?.forecast_data;
  const evaluation = shared?.evaluation;

  return (
    <main className="standalone-page">
      <Link to="/" className="key-link standalone-back"><ArrowLeft size={14} /> {t("share.backToApp")}</Link>
      <h1 className="standalone-title">{t("share.pageTitle")}</h1>

      {error && <div className="alert alert-warn" role="alert">{t(error === "notFound" ? "share.notFound" : "common.loadFailed")}</div>}
      {!error && !shared && <SkeletonChart />}

      {shared && (
        <Card title={`${shared.coin} · ${shared.horizon} · ${shared.model}`} icon={Sparkles} glow="cyan">
          <p className="text-sub" style={{ marginBottom: 12 }}>
            {t("share.createdAt", { date: new Date(shared.created_at).toLocaleString(locale) })}
          </p>
          {hasForecastSeries(data) ? (
            <ForecastChart data={data} t={t} createdAt={shared.created_at} horizon={shared.horizon} locale={locale} />
          ) : <p className="text-sub">{t("forecast.noChartData")}</p>}
          <div style={{ display: "flex", gap: 8, margin: "12px 0", flexWrap: "wrap" }}>
            {data?.confidence_score !== undefined && <ConfidenceBadge score={data.confidence_score} />}
            {data?.risk_level && <RiskBadge level={data.risk_level} />}
            {evaluation && <AccuracyBadge score={evaluation.accuracy_pct} />}
            {evaluation && (
              <span className={`badge ${evaluation.direction_correct ? "badge-buy" : "badge-sell"}`}>
                <span className="badge-dot" /> {t(evaluation.direction_correct ? "forecast.directionCorrect" : "forecast.directionWrong")}
              </span>
            )}
          </div>
          {!evaluation && <p className="text-sub">{t("share.notEvaluatedYet")}</p>}
          {data?.odovodnenie && <p className="text-sub" style={{ marginTop: 8, lineHeight: 1.6 }}>{stripMockTag(data.odovodnenie)}</p>}
          <DataSources sources={data?.zdroje_dat} signals={data?.signaly} />
        </Card>
      )}
      {shared && <ShareBar text={t("share.shareText", { coin: shared.coin, horizon: shared.horizon })} />}
      {shared && <ShareImages token={token} coin={shared.coin} />}

      <p className="text-sub standalone-disclaimer">{t("share.disclaimer")}</p>
    </main>
  );
}
