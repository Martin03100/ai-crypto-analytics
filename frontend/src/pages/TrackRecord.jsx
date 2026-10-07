/** Public AI accuracy record: every checked forecast, no login needed. */

import { ArrowLeft, ArrowRight, History, Trophy } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { Card } from "../components/Card";
import InfoTip from "../components/InfoTip";
import LoadError from "../components/LoadError";
import ShareBar from "../components/ShareBar";
import { SkeletonLines } from "../components/Skeleton";
import { useLanguage } from "../context/LanguageContext";
import { localeForLang } from "../i18n/locale";
import { usePageTitle } from "../hooks/usePageTitle";

const CUSTOM_LABEL = "Custom (OpenAI-compatible)";
const QUANT_LABEL = "Quant (free model)";

function Stat({ label, value }) {
  return (
    <div className="card track-stat">
      <span className="track-stat-value">{value}</span>
      <span className="text-sub">{label}</span>
    </div>
  );
}

export default function TrackRecord() {
  const { t, lang } = useLanguage();
  usePageTitle("track.pageTitle");
  const [data, setData] = useState(null);
  const [failed, setFailed] = useState(false);

  const load = useCallback(() => {
    setFailed(false);
    api.trackRecord().then(setData).catch(() => setFailed(true));
  }, []);
  useEffect(load, [load]);

  const label = (name) => (name === CUSTOM_LABEL ? t("provider.customLabel") : name === QUANT_LABEL ? t("provider.quantLabel") : name);
  const pct = (v) => (v == null ? "—" : `${v}%`);
  const totals = data?.totals || {};
  const challenge = data?.challenge;
  const trophyIndex = data ? data.providers.findIndex((p) => !p.low_sample) : -1;

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
            <Stat label={t("track.statDirection")} value={pct(totals.direction_hit_pct)} />
            <Stat label={t("track.statBaseline")} value={pct(totals.beats_baseline_pct)} />
          </div>

          {data.providers.length === 0 ? (
            <Card style={{ marginTop: 16 }}><p className="text-sub">{t("track.empty")}</p></Card>
          ) : (
            <>
              <Card title={t("track.providersTitle")} icon={Trophy} style={{ marginTop: 16 }}>
                <div className="table-scroll">
                  <table className="lb-table">
                    <thead>
                      <tr>
                        <th>{t("leaderboard.colProvider")}</th>
                        <th>{t("leaderboard.colEvaluated")}</th>
                        <th>{t("leaderboard.colDirection")}<InfoTip text={t("help.direction")} /></th>
                        <th>{t("leaderboard.colAccuracy")}<InfoTip text={t("help.accuracy")} /></th>
                        <th>{t("leaderboard.colBeatsBaseline")}<InfoTip text={t("help.baseline")} /></th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.providers.map((p, i) => (
                        <tr key={p.provider}>
                          <td>
                            {i === trophyIndex ? "🏆 " : ""}{label(p.provider)}
                            {p.low_sample && <span className="text-sub"> · {t("leaderboard.fewData")}</span>}
                          </td>
                          <td>{p.evaluated}</td>
                          <td>{p.direction_hit_pct}%</td>
                          <td>{p.avg_accuracy_pct}%</td>
                          <td>{p.beats_baseline_pct}%</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <p className="text-sub" style={{ marginTop: 10 }}>{t("leaderboard.minSample", { n: data.min_sample ?? 5 })}</p>
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
                        <th>{t("track.colAccuracy")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.recent.map((r, i) => (
                        <tr key={`${r.evaluated_at}-${i}`}>
                          <td>{r.coin}</td>
                          <td>{r.horizon}</td>
                          <td>{label(r.provider)}</td>
                          <td className={r.direction_correct ? "track-hit" : "track-miss"}>{t(r.direction_correct ? "track.hit" : "track.miss")}</td>
                          <td>
                            {r.accuracy_pct}%
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
