/** Market sentiment page. */

import { Calendar, Gauge, Newspaper, Vote } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api";
import { MockBadge, SentimentBadge } from "../components/Badge";
import { Card } from "../components/Card";
import InfoTip from "../components/InfoTip";
import LoadError from "../components/LoadError";
import OnchainCard from "../components/OnchainCard";
import MarketScanner from "../components/MarketScanner";
import MarketSignals from "../components/MarketSignals";
import PriceChart from "../components/PriceChart";
import { SkeletonLines } from "../components/Skeleton";
import ProviderSelect from "../components/ProviderSelect";
import { useToast } from "../context/ToastContext";
import { useProviders } from "../context/ProvidersContext";
import { useLanguage } from "../context/LanguageContext";
import { humanizeError } from "../i18n/errorMessages";
import { safeUrl } from "../utils/safeUrl";
import { localeForLang } from "../i18n/locale";
import { stripMockTag } from "../utils/mockText";
import { usePageTitle } from "../hooks/usePageTitle";

function FearGreedGauge({ value, classification }) {
  const { t } = useLanguage();
  const pct = Math.min(Math.max(value, 0), 100);
  const tone = pct >= 55 ? "up" : pct <= 45 ? "down" : "";
  return (
    <div>
      <div className="big-figure">
        <span className={`metric-value ${tone}`}>{value}</span>
        <span className="text-sub">/ 100 · {stripMockTag(classification)}</span>
      </div>
      <div className="fg-meter" role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct} aria-label="Fear & Greed">
        <div className="fg-meter-thumb" style={{ left: `${pct}%` }} />
      </div>
      <div className="fg-scale"><span>{t("dashboard.fearLabel")}</span><span>{t("dashboard.greedLabel")}</span></div>
    </div>
  );
}

export default function Market() {
  const { push } = useToast();
  const { t, lang } = useLanguage();
  const locale = localeForLang(lang);
  usePageTitle("market.title");
  const [fg, setFg] = useState(null);
  const [fgMock, setFgMock] = useState(false);
  const [headlines, setHeadlines] = useState([]);
  const providersCtx = useProviders();
  const providers = providersCtx.providers;
  const [provider, setProvider] = useState(null);
  const [newsResult, setNewsResult] = useState(null);
  const [newsLoading, setNewsLoading] = useState(false);
  const [events, setEvents] = useState(null);
  const [myVote, setMyVote] = useState(null);
  const [percentages, setPercentages] = useState(null);

  const [failed, setFailed] = useState({ fg: false, headlines: false, events: false });
  const markFailed = (key, value) => setFailed((prev) => ({ ...prev, [key]: value }));

  function loadFearGreed() {
    markFailed("fg", false);
    api.fearGreed()
      .then((r) => {
        if (!r.data) throw new Error("invalid");
        setFg(r.data);
        setFgMock(r.is_mock);
      })
      .catch(() => markFailed("fg", true));
  }

  function loadHeadlines() {
    markFailed("headlines", false);
    api.headlines().then((r) => setHeadlines(r.headlines)).catch(() => markFailed("headlines", true));
  }

  function loadEvents() {
    markFailed("events", false);
    api.events().then((r) => setEvents(r.events)).catch(() => markFailed("events", true));
  }

  useEffect(() => {
    loadFearGreed();
    loadHeadlines();
    loadEvents();
    api.myVote().then((r) => setMyVote(typeof r.sentiment_vote === "string" ? r.sentiment_vote : null)).catch(() => {});
    api.votePercentages().then(setPercentages).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (providersCtx.defaultProvider) setProvider(providersCtx.defaultProvider);
  }, [providersCtx.defaultProvider]);

  async function runNewsAnalysis() {
    if (!provider || headlines.length === 0) return;
    setNewsLoading(true);
    try {
      const titles = headlines.map((h) => h.title).filter((title) => typeof title === "string" && title.trim());
      const res = await api.newsSentiment(provider, titles.slice(0, 20));
      if (!res.success) {
        push(res.error_message || t("errors.generic"), "error");
        return;
      }
      setNewsResult(res);
      if (res.is_mock) push(res.error_message ? humanizeError(res.error_message, lang, "errors.aiFallback") : t("market.mockNotice"), "warn");
    } catch (err) {
      push(err, "error");
    } finally {
      setNewsLoading(false);
    }
  }

  async function castVote(sentiment) {
    try {
      await api.vote(sentiment);
      setMyVote(sentiment);
      push(t("market.voteRecorded"), "success");
      api.votePercentages().then(setPercentages).catch(() => {});
    } catch (err) {
      push(err, "error");
    }
  }

  const headlineFor = (title) => headlines.find((h) => h.title === title);

  function timeAgo(iso) {
    if (!iso) return "";
    const diffMs = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diffMs / 60000);
    if (mins < 1) return t("market.timeAgoNow");
    if (mins < 60) return t("market.timeAgoMinutes", { count: mins });
    const hours = Math.floor(mins / 60);
    if (hours < 24) return t("market.timeAgoHours", { count: hours });
    const days = Math.floor(hours / 24);
    return t("market.timeAgoDays", { count: days });
  }

  return (
    <div>
      <div className="topbar">
        <div>
          <h1 className="page-title">{t("market.title")}</h1>
          <p className="page-sub">{t("market.subtitle")}</p>
        </div>
      </div>

      <div style={{ marginBottom: 16 }}>
        <PriceChart />
      </div>

      <MarketScanner />

      <MarketSignals style={{ marginBottom: 16 }} />

      <div className="grid grid-2" style={{ marginBottom: 16 }}>
        <Card title={<>{t("market.fearGreedTitle")} <InfoTip text={t("help.fearGreed")} /></>} icon={Gauge} glow={fg && fg.value >= 55 ? "emerald" : fg && fg.value <= 45 ? "crimson" : undefined}>
          {fg ? (
            <>
              {fgMock && <div style={{ marginBottom: 10 }}><MockBadge /></div>}
              <FearGreedGauge value={fg.value} classification={fg.classification} />
              {fg.updated_at && (
                <p className="text-sub" style={{ marginTop: 6, marginBottom: 0 }}>
                  {t("market.updated", { date: new Date(fg.updated_at).toLocaleString(locale) })}
                </p>
              )}
            </>
          ) : failed.fg ? <LoadError onRetry={loadFearGreed} /> : <SkeletonLines count={2} />}
        </Card>

        <Card title={t("market.communityTitle")} icon={Vote}>
          {myVote && <p className="text-sub" style={{ marginTop: -4, marginBottom: 10 }}>{t("market.myLastVote")} <SentimentBadge sentiment={myVote} /></p>}
          <div className="grid grid-3" style={{ gap: 8, marginBottom: 14 }}>
            <button className={`btn btn-sm ${myVote === "Bullish" ? "btn-primary" : "btn-ghost"}`} onClick={() => castVote("Bullish")} aria-pressed={myVote === "Bullish"}><span className="vote-dot vote-dot-emerald" aria-hidden="true" />{t("market.voteBullish")}</button>
            <button className={`btn btn-sm ${myVote === "Neutral" ? "btn-primary" : "btn-ghost"}`} onClick={() => castVote("Neutral")} aria-pressed={myVote === "Neutral"}><span className="vote-dot vote-dot-muted" aria-hidden="true" />{t("market.voteNeutral")}</button>
            <button className={`btn btn-sm ${myVote === "Bearish" ? "btn-primary" : "btn-ghost"}`} onClick={() => castVote("Bearish")} aria-pressed={myVote === "Bearish"}><span className="vote-dot vote-dot-crimson" aria-hidden="true" />{t("market.voteBearish")}</button>
          </div>
          {percentages && percentages.total_votes > 0 ? (
            <>
              {Object.entries(percentages).filter(([key]) => key !== "total_votes").map(([sentiment, pct]) => (
                <div key={sentiment} style={{ marginBottom: 8 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12.5, marginBottom: 3 }}>
                    <SentimentBadge sentiment={sentiment} /> <span className="mono">{pct}%</span>
                  </div>
                  <div style={{ height: 6, borderRadius: 999, background: "var(--bg-inset)" }}>
                    <div style={{ height: "100%", width: `${pct}%`, borderRadius: 999, background: sentiment === "Bullish" ? "var(--emerald)" : sentiment === "Bearish" ? "var(--crimson)" : "var(--text-secondary)" }} />
                  </div>
                </div>
              ))}
              <p className="text-sub" style={{ marginTop: 10, marginBottom: 0 }}>
                {t("market.votedTotal")} <strong>{percentages.total_votes.toLocaleString(locale)}</strong> {t("market.votedUsers")}
              </p>
            </>
          ) : <p className="text-sub">{t("market.noVotesYet")}</p>}
        </Card>
      </div>

      <Card title={t("market.newsTitle")} icon={Newspaper} style={{ marginBottom: 16 }}>
        <div style={{ marginBottom: 14 }}>
          <ProviderSelect providers={providers} value={provider} onChange={setProvider} label={t("market.providerLabelNews")} />
        </div>
        {providers.some((p) => p.connected) && (
          <button className="btn btn-ghost btn-sm" onClick={runNewsAnalysis} disabled={newsLoading} style={{ marginBottom: 16 }}>
            {newsLoading ? t("market.analyzingSentiment") : t("market.analyzeSentimentButton")}
          </button>
        )}

        {newsLoading && <SkeletonLines count={5} />}

        {!newsLoading && newsResult?.data && (
          <>
            {newsResult.is_mock && <div style={{ marginBottom: 10 }}><MockBadge /></div>}
            <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 18 }}>
              {(Array.isArray(newsResult.data.spravy) ? newsResult.data.spravy : []).filter((item) => item && typeof item === "object").map((item, i) => {
                const headline = headlineFor(item.titulok);
                const link = safeUrl(headline?.link);
                return (
                  <div key={i} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, padding: "10px 12px", borderRadius: 10, background: "var(--bg-inset)", border: "1px solid var(--border-subtle)" }}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      {link && link !== "#" ? (
                        <a href={link} target="_blank" rel="noopener noreferrer" style={{ fontSize: 13, color: "var(--text-primary)", textDecoration: "none" }}>{item.titulok}</a>
                      ) : <span style={{ fontSize: 13 }}>{item.titulok}</span>}
                      {headline && (headline.source || headline.published_at) && (
                        <div className="headline-meta">
                          {headline.source}{headline.source && headline.published_at ? " · " : ""}
                          {headline.published_at ? timeAgo(headline.published_at) : ""}
                        </div>
                      )}
                    </div>
                    <SentimentBadge sentiment={item.sentiment} />
                  </div>
                );
              })}
            </div>
            <p className="card-title" style={{ marginBottom: 8 }}>{t("market.trendingTitle")}</p>
            <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13.5, color: "var(--text-secondary)", lineHeight: 1.8 }}>
              {(Array.isArray(newsResult.data.trendy) ? newsResult.data.trendy : []).map((trend, i) => <li key={i}>{stripMockTag(String(trend))}</li>)}
            </ul>
          </>
        )}

        {!newsLoading && !newsResult && headlines.length === 0 && (failed.headlines ? <LoadError onRetry={loadHeadlines} /> : <SkeletonLines count={4} />)}
      </Card>

      <OnchainCard />

      <Card title={t("market.eventsTitle")} icon={Calendar}>
        {failed.events ? <LoadError onRetry={loadEvents} /> : events === null ? <SkeletonLines count={3} /> : events.length === 0 ? (
          <p className="text-sub">{t("market.noEvents")}</p>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {events.map((ev, i) => (
              <div key={i} style={{ display: "flex", justifyContent: "space-between", padding: "9px 0", borderBottom: i < events.length - 1 ? "1px solid var(--border-subtle)" : "none", fontSize: 13 }}>
                <span className="mono" style={{ color: "var(--text-tertiary)", minWidth: 90 }}>{ev.datum}</span>
                <span style={{ flex: 1, marginLeft: 12 }}>{ev.udalost}</span>
                <span className="text-sub">{ev.typ}</span>
              </div>
            ))}
          </div>
        )}
        <p className="data-sources">{t("market.eventsSource")}</p>
      </Card>
    </div>
  );
}
