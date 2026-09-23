import { ArrowRight, Gauge, Sparkles, TrendingUp, Wallet } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { ConfidenceBadge, RiskBadge } from "../components/Badge";
import { Card } from "../components/Card";
import { SkeletonLines } from "../components/Skeleton";
import { useAuth } from "../context/AuthContext";
import { useLanguage } from "../context/LanguageContext";
import { localeForLang } from "../i18n/locale";
import { usePageTitle } from "../hooks/usePageTitle";

function QuickLink({ to, icon: Icon, label, sub }) {
  return (
    <Link to={to} className="quick-link-card">
      <div className="quick-link-icon"><Icon size={18} /></div>
      <div style={{ flex: 1 }}>
        <div style={{ fontWeight: 600, fontSize: 13.5 }}>{label}</div>
        <div className="text-sub" style={{ marginTop: 2 }}>{sub}</div>
      </div>
      <ArrowRight size={15} style={{ opacity: 0.5 }} />
    </Link>
  );
}

export default function Dashboard() {
  const { user } = useAuth();
  const { t, lang } = useLanguage();
  usePageTitle("dashboard.pageTitle");
  const [fg, setFg] = useState(null);
  const [lastForecast, setLastForecast] = useState(null);
  const [lastPortfolio, setLastPortfolio] = useState(null);
  const [loading, setLoading] = useState(true);
  const locale = localeForLang(lang);

  useEffect(() => {
    Promise.allSettled([
      api.fearGreed(),
      api.forecastHistory(undefined, 90),
      api.portfolioHistory(),
    ]).then(([fgRes, forecastRes, portfolioRes]) => {
      if (fgRes.status === "fulfilled") setFg(fgRes.value.data);
      if (forecastRes.status === "fulfilled" && forecastRes.value.items.length > 0) setLastForecast(forecastRes.value.items[0]);
      if (portfolioRes.status === "fulfilled" && portfolioRes.value.items.length > 0) setLastPortfolio(portfolioRes.value.items[0]);
    }).finally(() => setLoading(false));
  }, []);

  const hour = new Date().getHours();
  const greetingKey = hour < 5 ? "dashboard.greetingNight" : hour < 12 ? "dashboard.greetingMorning" : hour < 18 ? "dashboard.greetingDay" : "dashboard.greetingEvening";
  const greeting = t(greetingKey);

  return (
    <div>
      <div className="topbar">
        <div>
          <h1 className="page-title">{greeting}, {user?.username} 👋</h1>
          <p className="page-sub">{t("dashboard.subtitle")}</p>
        </div>
      </div>

      <div className="grid grid-3" style={{ marginBottom: 20 }}>
        <QuickLink to="/forecast" icon={Sparkles} label={t("dashboard.quickForecastLabel")} sub={t("dashboard.quickForecastSub")} />
        <QuickLink to="/portfolio" icon={Wallet} label={t("dashboard.quickPortfolioLabel")} sub={t("dashboard.quickPortfolioSub")} />
        <QuickLink to="/market" icon={TrendingUp} label={t("dashboard.quickMarketLabel")} sub={t("dashboard.quickMarketSub")} />
      </div>

      {loading ? (
        <div className="grid grid-2"><Card><SkeletonLines count={4} /></Card><Card><SkeletonLines count={4} /></Card></div>
      ) : (
        <div className="grid grid-2" style={{ marginBottom: 16 }}>
          <Card title={t("dashboard.lastForecastTitle")} icon={Sparkles}>
            {lastForecast ? (
              <>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
                  <strong style={{ fontSize: 15 }}>{lastForecast.crypto_symbol} · {lastForecast.timeframe}</strong>
                  <span className="text-sub">{new Date(lastForecast.created_at).toLocaleDateString(locale)}</span>
                </div>
                <div style={{ display: "flex", gap: 8, marginBottom: 10, flexWrap: "wrap" }}>
                  {lastForecast.forecast_data?.confidence_score !== undefined && <ConfidenceBadge score={lastForecast.forecast_data.confidence_score} />}
                  {lastForecast.forecast_data?.risk_level && <RiskBadge level={lastForecast.forecast_data.risk_level} />}
                </div>
                <p className="text-sub" style={{ marginBottom: 12 }}>{lastForecast.forecast_data?.odovodnenie?.slice(0, 160)}…</p>
                <Link to="/forecast" className="btn btn-ghost btn-sm">{t("dashboard.viewHistory")} <ArrowRight size={13} /></Link>
              </>
            ) : (
              <p className="empty-state">{t("dashboard.emptyForecast")} <Link to="/forecast" className="key-link">{t("common.createFirst")}</Link></p>
            )}
          </Card>

          <Card title={t("dashboard.lastPortfolioTitle")} icon={Wallet}>
            {lastPortfolio ? (
              <>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
                  <strong style={{ fontSize: 15 }}>{lastPortfolio.holdings.map((h) => h.minca).join(", ")}</strong>
                  <span className="text-sub">{new Date(lastPortfolio.created_at).toLocaleDateString(locale)}</span>
                </div>
                <p className="text-sub" style={{ marginBottom: 12 }}>{lastPortfolio.analysis_data?.odborna_analyza?.slice(0, 160)}…</p>
                <Link to="/portfolio" className="btn btn-ghost btn-sm">{t("dashboard.viewHistory")} <ArrowRight size={13} /></Link>
              </>
            ) : (
              <p className="empty-state">{t("dashboard.emptyPortfolio")} <Link to="/portfolio" className="key-link">{t("common.createFirst")}</Link></p>
            )}
          </Card>
        </div>
      )}

      {fg && (
        <Card title={t("dashboard.fearGreedTitle")} icon={Gauge} glow={fg.value >= 55 ? "emerald" : fg.value <= 45 ? "crimson" : undefined}>
          <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
            <div className="metric-value mono" style={{ fontSize: 32 }}>{fg.value}</div>
            <div>
              <div style={{ fontWeight: 600 }}>{fg.classification}</div>
              <Link to="/market" className="key-link">{t("dashboard.detailedMarket")}</Link>
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}
