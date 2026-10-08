/** Dashboard page. */

import { ArrowRight, CalendarClock, Gauge, Lightbulb, RefreshCw, Sparkles, Wallet } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { ConfidenceBadge, RiskBadge } from "../components/Badge";
import { Card } from "../components/Card";
import DailyDigest from "../components/DailyDigest";
import Term from "../components/Term";
import { SkeletonLines } from "../components/Skeleton";
import ChallengeCard from "../components/ChallengeCard";
import MarketSignals from "../components/MarketSignals";
import PriceAlerts from "../components/PriceAlerts";
import SimpleOverview from "../components/SimpleOverview";
import UpcomingEvents from "../components/UpcomingEvents";
import Watchlist from "../components/Watchlist";
import { useSimpleMode } from "../hooks/useSimpleMode";
import { useAuth } from "../context/AuthContext";
import { useLanguage } from "../context/LanguageContext";
import { useToast } from "../context/ToastContext";
import { localeForLang } from "../i18n/locale";
import { finalForecastPrice, predictedChangePct } from "../utils/forecastMath";
import { formatPrice } from "../utils/formatPrice";
import { stripMockTag } from "../utils/mockText";
import { usePageTitle } from "../hooks/usePageTitle";

function EmptyCta({ icon: Icon, text, to, action }) {
  return (
    <div className="empty-cta">
      <div className="empty-cta-icon"><Icon size={16} /></div>
      <p>{text}</p>
      <Link to={to} className="btn btn-ghost btn-sm">{action}</Link>
    </div>
  );
}

function fearGreedTone(value) {
  if (value >= 55) return "up";
  if (value <= 45) return "down";
  return "";
}

export default function Dashboard() {
  const { user } = useAuth();
  const { t, lang } = useLanguage();
  const { push } = useToast();
  const { simple, setSimple } = useSimpleMode();
  usePageTitle("dashboard.pageTitle");
  const [fg, setFg] = useState(null);
  const [refreshingFg, setRefreshingFg] = useState(false);
  const [lastForecast, setLastForecast] = useState(null);
  const [lastPortfolio, setLastPortfolio] = useState(null);
  const [schedules, setSchedules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [fgError, setFgError] = useState(false);
  const locale = localeForLang(lang);

  useEffect(() => {
    Promise.allSettled([
      api.fearGreed(),
      api.forecastHistory(undefined, null, 1, 1),
      api.portfolioHistory(1, 1),
      api.schedules(),
    ]).then(([fgRes, forecastRes, portfolioRes, schedulesRes]) => {
      if (fgRes.status === "fulfilled" && fgRes.value.data) setFg(fgRes.value.data);
      else setFgError(true);
      if (forecastRes.status === "fulfilled" && forecastRes.value.items.length > 0) setLastForecast(forecastRes.value.items[0]);
      if (portfolioRes.status === "fulfilled" && portfolioRes.value.items.length > 0) setLastPortfolio(portfolioRes.value.items[0]);
      if (schedulesRes.status === "fulfilled") setSchedules(schedulesRes.value.items.filter((s) => s.active));
    }).finally(() => setLoading(false));
  }, []);

  async function handleRefreshFg() {
    setRefreshingFg(true);
    try {
      const res = await api.fearGreed(true);
      if (!res.data) throw new Error("Server error (502): invalid response");
      setFg(res.data);
      setFgError(false);
      push(t("dashboard.fearGreedRefreshed"), "success");
    } catch (err) {
      push(err, "error");
    } finally {
      setRefreshingFg(false);
    }
  }

  const hour = new Date().getHours();
  const greetingKey = hour < 5 ? "dashboard.greetingNight" : hour < 12 ? "dashboard.greetingMorning" : hour < 18 ? "dashboard.greetingDay" : "dashboard.greetingEvening";
  const today = new Date().toLocaleDateString(locale, { weekday: "long", day: "numeric", month: "long" });

  const fd = lastForecast?.forecast_data;
  const finalPrice = finalForecastPrice(fd);
  const change = predictedChangePct(fd);
  const nextSchedule = [...schedules].sort((a, b) => new Date(a.next_run_at) - new Date(b.next_run_at))[0];

  return (
    <div>
      <div className="topbar">
        <div>
          <p className="eyebrow">{today}</p>
          <h1 className="page-title">{t(greetingKey)}, {user?.username}</h1>
        </div>
        <div className="topbar-actions">
          <button type="button" className={`btn btn-ghost btn-sm mode-pill ${simple ? "on" : ""}`} aria-pressed={simple}
                  onClick={() => setSimple(!simple)} title={t("viewMode.title")}>
            <Lightbulb size={14} aria-hidden="true" /> {t("viewMode.simple")}
          </button>
          <Link to="/forecast" className="btn btn-primary"><Sparkles size={15} /> {t("dashboard.quickForecastLabel")}</Link>
        </div>
      </div>

      {simple ? <SimpleOverview /> : <DailyDigest />}

      <Watchlist />

      <PriceAlerts />

      <UpcomingEvents style={{ marginTop: 16 }} />

      <ChallengeCard style={{ marginTop: 16 }} />

      {!simple && <MarketSignals compact style={{ marginTop: 16 }} />}

      {loading ? (
        <div className="grid grid-2" style={{ marginTop: 16 }}><Card><SkeletonLines count={4} /></Card><Card><SkeletonLines count={4} /></Card></div>
      ) : (
        <div className="dash-grid">
          <Card title={t("dashboard.lastForecastTitle")} icon={Sparkles}>
            {lastForecast ? (
              <>
                <div className="kv-head">
                  <span className="kv-title">{lastForecast.crypto_symbol} · {t(`forecast.horizon${lastForecast.timeframe}`)}</span>
                  <span className="text-sub">{new Date(lastForecast.created_at).toLocaleDateString(locale)}</span>
                </div>
                {finalPrice != null && (
                  <div className="big-figure">
                    <span className="metric-value">{formatPrice(finalPrice)}</span>
                    {change != null && (
                      <span className={`metric-delta ${change >= 0 ? "up" : "down"}`}>{change >= 0 ? "+" : ""}{change.toFixed(1)} %</span>
                    )}
                  </div>
                )}
                <div className="metric-label" style={{ marginBottom: 12 }}>{t("dashboard.predictedPriceLabel")} · {lastForecast.model_used}</div>
                <div style={{ display: "flex", gap: 6, marginBottom: 12, flexWrap: "wrap" }}>
                  {fd?.confidence_score !== undefined && <ConfidenceBadge score={fd.confidence_score} />}
                  {fd?.risk_level && <RiskBadge level={fd.risk_level} />}
                </div>
                {fd?.odovodnenie && <p className="text-sub clamp-3" style={{ margin: "0 0 14px" }}>{stripMockTag(fd.odovodnenie)}</p>}
                <Link to="/forecast?tab=history" className="text-link">{t("dashboard.viewHistory")} <ArrowRight size={13} /></Link>
              </>
            ) : (
              <EmptyCta icon={Sparkles} text={t("dashboard.emptyForecast")} to="/forecast" action={t("common.createFirst")} />
            )}
          </Card>

          {fg ? (
            <Card id="tour-feargreed-card">
              <div className="card-head">
                <h2 className="card-title" style={{ margin: 0 }}><Gauge size={14} /> <Term id="fearGreed">{t("dashboard.fearGreedTitle")}</Term></h2>
                <button className="btn btn-ghost btn-sm btn-icon" onClick={handleRefreshFg} disabled={refreshingFg}
                        aria-label={t("dashboard.fearGreedRefresh")} title={t("dashboard.fearGreedRefresh")}>
                  <RefreshCw size={13} className={refreshingFg ? "spin" : ""} />
                </button>
              </div>
              <div className="big-figure">
                <span className={`metric-value ${fearGreedTone(fg.value)}`}>{fg.value}</span>
                <span className="text-sub">/ 100 · {stripMockTag(fg.classification)}</span>
              </div>
              <div className="fg-meter" role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={fg.value} aria-label={t("dashboard.fearGreedTitle")}>
                <div className="fg-meter-thumb" style={{ left: `${fg.value}%` }} />
              </div>
              <div className="fg-scale"><span>{t("dashboard.fearLabel")}</span><span>{t("dashboard.greedLabel")}</span></div>
              <Link to="/market" className="text-link" style={{ marginTop: 14 }}>{t("dashboard.detailedMarket")}</Link>
            </Card>
          ) : (
            <Card id="tour-feargreed-card" title={t("dashboard.fearGreedTitle")} icon={Gauge}>
              {fgError && (
                <div className="inline-error" role="alert">
                  <span>{t("dashboard.fearGreedError")}</span>
                  <button className="btn btn-ghost btn-sm" onClick={handleRefreshFg} disabled={refreshingFg}>
                    <RefreshCw size={13} className={refreshingFg ? "spin" : ""} /> {t("common.retry")}
                  </button>
                </div>
              )}
            </Card>
          )}

          {!simple && <Card title={t("schedule.dashboardTitle")} icon={CalendarClock}>
            {nextSchedule ? (
              <>
                <div className="kv-head">
                  <span className="kv-title">{nextSchedule.coin} · {t(`forecast.horizon${nextSchedule.horizon}`)}</span>
                  <span className="badge badge-neutral">{t("schedule.activeCount", { n: schedules.length })}</span>
                </div>
                <p className="text-sub" style={{ margin: "0 0 14px" }}>
                  {t("schedule.nextRun", { when: new Date(nextSchedule.next_run_at).toLocaleString(locale, { weekday: "long", hour: "2-digit", minute: "2-digit" }) })}
                </p>
                <Link to="/forecast?tab=schedule" className="text-link">{t("schedule.manage")} <ArrowRight size={13} /></Link>
              </>
            ) : (
              <EmptyCta icon={CalendarClock} text={t("schedule.dashboardEmpty")} to="/forecast?tab=schedule" action={t("schedule.create")} />
            )}
          </Card>}

          <Card title={t("dashboard.lastPortfolioTitle")} icon={Wallet}>
            {lastPortfolio ? (
              <>
                <div className="kv-head">
                  <span className="kv-title">{lastPortfolio.holdings.map((h) => h.minca).join(", ")}</span>
                  <span className="text-sub">{new Date(lastPortfolio.created_at).toLocaleDateString(locale)}</span>
                </div>
                {lastPortfolio.analysis_data?.odborna_analyza && (
                  <p className="text-sub clamp-3" style={{ margin: "0 0 14px" }}>{stripMockTag(lastPortfolio.analysis_data.odborna_analyza)}</p>
                )}
                <Link to="/portfolio" className="text-link">{t("dashboard.viewHistory")} <ArrowRight size={13} /></Link>
              </>
            ) : (
              <EmptyCta icon={Wallet} text={t("dashboard.emptyPortfolio")} to="/portfolio" action={t("common.createFirst")} />
            )}
          </Card>
        </div>
      )}
    </div>
  );
}
