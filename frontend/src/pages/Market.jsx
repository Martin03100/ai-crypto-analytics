import { Calendar, Gauge, Newspaper, Vote } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api";
import { MockBadge, SentimentBadge } from "../components/Badge";
import { Card } from "../components/Card";
import InfoTip from "../components/InfoTip";
import OnchainCard from "../components/OnchainCard";
import PriceChart from "../components/PriceChart";
import { SkeletonLines } from "../components/Skeleton";
import ProviderSelect from "../components/ProviderSelect";
import { useToast } from "../context/ToastContext";
import { useProviders } from "../context/ProvidersContext";
import { useLanguage } from "../context/LanguageContext";
import { humanizeError } from "../i18n/errorMessages";
import { localeForLang } from "../i18n/locale";
import { usePageTitle } from "../hooks/usePageTitle";

function FearGreedGauge({ value, classification }) {
  const pct = Math.min(Math.max(value, 0), 100);
  const color = pct <= 25 ? "var(--crimson)" : pct <= 45 ? "#fb923c" : pct <= 55 ? "var(--text-secondary)" : pct <= 75 ? "var(--amber)" : "var(--emerald)";
  return (
    <div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 10, marginBottom: 10 }}>
        <span className="metric-value mono" style={{ color }}>{value}/100</span>
        <span className="text-sub">{classification}</span>
      </div>
      <div style={{ height: 8, borderRadius: 999, background: "var(--bg-inset)", overflow: "hidden" }}>
        <div style={{ height: "100%", width: `${pct}%`, background: color, borderRadius: 999, transition: "width 0.4s var(--ease)" }} />
      </div>
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
  const [events, setEvents] = useState([]);
  const [myVote, setMyVote] = useState(null);
  const [percentages, setPercentages] = useState(null);

  useEffect(() => {
    api.fearGreed().then((r) => { setFg(r.data); setFgMock(r.is_mock); }).catch(() => {});
    api.headlines().then((r) => setHeadlines(r.headlines)).catch(() => {});
    api.events().then((r) => setEvents(r.events)).catch(() => {});
    api.myVote().then((r) => setMyVote(r.sentiment_vote)).catch(() => {});
    api.votePercentages().then(setPercentages).catch(() => {});
  }, []);

  useEffect(() => {
    if (providersCtx.defaultProvider) setProvider(providersCtx.defaultProvider);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [providersCtx.defaultProvider]);

  async function runNewsAnalysis() {
    if (!provider || headlines.length === 0) return;
    setNewsLoading(true);
    try {
      const titles = headlines.map((h) => h.title);
      const res = await api.newsSentiment(provider, titles);
      setNewsResult(res);
      if (res.is_mock) push(res.error_message ? humanizeError(res.error_message, lang) : t("market.mockNotice"), "warn");
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
      api.votePercentages().then(setPercentages);
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
          ) : <SkeletonLines count={2} />}
        </Card>

        <Card title={t("market.communityTitle")} icon={Vote}>
          {myVote && <p className="text-sub" style={{ marginTop: -4, marginBottom: 10 }}>{t("market.myLastVote")} <SentimentBadge sentiment={myVote} /></p>}
          <div className="grid grid-3" style={{ gap: 8, marginBottom: 14 }}>
            <button className={`btn btn-sm ${myVote === "Bullish" ? "btn-primary" : "btn-ghost"}`} onClick={() => castVote("Bullish")} aria-pressed={myVote === "Bullish"}>{t("market.voteBullish")}</button>
            <button className={`btn btn-sm ${myVote === "Neutral" ? "btn-primary" : "btn-ghost"}`} onClick={() => castVote("Neutral")} aria-pressed={myVote === "Neutral"}>{t("market.voteNeutral")}</button>
            <button className={`btn btn-sm ${myVote === "Bearish" ? "btn-primary" : "btn-ghost"}`} onClick={() => castVote("Bearish")} aria-pressed={myVote === "Bearish"}>{t("market.voteBearish")}</button>
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
              {newsResult.data.spravy.map((item, i) => {
                const headline = headlineFor(item.titulok);
                const link = headline?.link;
                return (
                  <div key={i} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, padding: "10px 12px", borderRadius: 10, background: "var(--bg-inset)", border: "1px solid var(--border-subtle)" }}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      {link && link !== "#" ? (
                        <a href={link} target="_blank" rel="noreferrer" style={{ fontSize: 13, color: "var(--text-primary)", textDecoration: "none" }}>{item.titulok}</a>
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
              {newsResult.data.trendy.map((trend, i) => <li key={i}>{trend}</li>)}
            </ul>
          </>
        )}

        {!newsLoading && !newsResult && headlines.length === 0 && <SkeletonLines count={4} />}
      </Card>

      <OnchainCard />

      <Card title={t("market.eventsTitle")} icon={Calendar}>
        {events.length === 0 ? <SkeletonLines count={3} /> : (
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
      </Card>
    </div>
  );
}
