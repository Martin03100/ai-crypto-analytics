/** Public AI accuracy record: every checked forecast, no login needed. */

import { ArrowLeft, ArrowRight, History, Info, Trophy } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { Card } from "../components/Card";
import InfoTip from "../components/InfoTip";
import LoadError from "../components/LoadError";
import ProviderStatsTable from "../components/ProviderStatsTable";
import ShareBar from "../components/ShareBar";
import TipsterBoard from "../components/TipsterBoard";
import AccuracyInsights from "../components/AccuracyInsights";
import AccuracyTimeline from "../components/AccuracyTimeline";
import WeeklyRecap from "../components/WeeklyRecap";
import ChallengeCard from "../components/ChallengeCard";
import { SkeletonLines } from "../components/Skeleton";
import { useAppConfig } from "../context/AppConfigContext";
import { useLanguage } from "../context/LanguageContext";
import { localeForLang } from "../i18n/locale";
import { usePageTitle } from "../hooks/usePageTitle";
import { providerName } from "../utils/models";

function Stat({ label, value, hint }) {
  return (
    <div className="card track-stat">
      <span className="track-stat-value">{value}</span>
      <span className="text-sub">{label}</span>
      {hint && <span className="text-sub track-stat-hint">{hint}</span>}
    </div>
  );
}

export default function TrackRecord() {
  const { t, lang } = useLanguage();
  usePageTitle("track.pageTitle");
  const { tipsters_enabled } = useAppConfig();
  const [data, setData] = useState(null);
  const [failed, setFailed] = useState(false);

  const load = useCallback(() => {
    setFailed(false);
    api.trackRecord().then(setData).catch(() => setFailed(true));
  }, []);
  useEffect(load, [load]);

  const label = (name) => providerName(name, t);
  const pct = (v) => (v == null ? "—" : `${v}%`);
  const totals = data?.totals || {};
  const challenge = data?.challenge;
  const reliable = data?.reliable_sample ?? 30;
  const ci = Array.isArray(totals.direction_ci) ? totals.direction_ci : null;

  return (
    <main className="standalone-page">
      <Link to="/" className="key-link standalone-back"><ArrowLeft size={14} /> {t("share.backToApp")}</Link>
      <h1 className="standalone-title">{t("track.title")}</h1>
      <p className="text-sub" style={{ marginBottom: 20 }}>{t("track.intro")}</p>

      {failed && <LoadError onRetry={load} />}
      {!data && !failed && <SkeletonLines count={6} />}

      {data && (
        <>
          <div className="track-stats">
            <Stat label={t("track.statEvaluated")} value={totals.evaluated ?? 0} />
            <Stat label={t("track.statDirection")} value={pct(totals.direction_hit_pct)}
              hint={ci ? t("track.ci", { low: ci[0], high: ci[1] }) : null} />
            <Stat label={t("track.statBaseline")} value={pct(totals.beats_baseline_pct)} />
          </div>

          {totals.evaluated > 0 && totals.evaluated < reliable && ci && (
            <p className="track-note" data-testid="track-few-data">
              <Info size={14} aria-hidden="true" />
              <span>{t("track.fewData", { n: totals.evaluated, low: ci[0], high: ci[1], min: reliable })}</span>
            </p>
          )}

          {data.providers.length === 0 ? (
            <Card style={{ marginTop: 16 }}><p className="text-sub">{t("track.empty")}</p></Card>
          ) : (
            <>
              <Card title={t("track.providersTitle")} icon={Trophy} style={{ marginTop: 16 }}>
                <ProviderStatsTable providers={data.providers} reliableSample={reliable} />
              </Card>

              <Card title={t("track.recentTitle")} icon={History} style={{ marginTop: 16 }}>
                <div className="table-scroll">
                  <table className="lb-table" data-testid="track-recent">
                    <thead>
                      <tr>
                        <th>{t("track.colCoin")}</th>
                        <th>{t("track.colHorizon")}</th>
                        <th>{t("leaderboard.colProvider")}</th>
                        <th>{t("track.colResult")}</th>
                        <th>{t("track.colError")}<InfoTip text={t("help.error")} /></th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.recent.map((r, i) => (
                        <tr key={`${r.evaluated_at}-${i}`}>
                          <td>{r.coin}</td>
                          <td>{t(`forecast.horizon${r.horizon}`)}</td>
                          <td>{label(r.provider)}</td>
                          <td className={r.direction_correct ? "track-hit" : "track-miss"}>{t(r.direction_correct ? "track.hit" : "track.miss")}</td>
                          <td>
                            {r.error_pct ?? Math.round((100 - r.accuracy_pct) * 10) / 10}%
                            {r.evaluated_at && <span className="text-sub"> · {new Date(r.evaluated_at).toLocaleDateString(localeForLang(lang))}</span>}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            </>
          )}

          {challenge?.total > 0 && (
            <p className="text-sub" style={{ marginTop: 16 }}>
              {t("track.challenge", { pct: Math.round((challenge.wins / challenge.total) * 100), total: challenge.total })}
            </p>
          )}

          <WeeklyRecap style={{ marginTop: 16 }} />
          <AccuracyTimeline />
          <AccuracyInsights />
          <ChallengeCard style={{ marginTop: 16 }} />
          {tipsters_enabled && <TipsterBoard />}
          <ShareBar text={t("track.shareText")} />
          <div style={{ marginTop: 20 }}>
            <Link to="/auth?tab=register" className="btn btn-primary">{t("track.cta")} <ArrowRight size={15} /></Link>
          </div>
          <p className="text-sub standalone-disclaimer">{t("track.disclaimer")}</p>
        </>
      )}
    </main>
  );
}
