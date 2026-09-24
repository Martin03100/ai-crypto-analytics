import { Brain, ChevronDown, Copy, Loader2, RefreshCw, Rocket, Save, Sparkles, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import {
  Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { api } from "../api";
import { ConfidenceBadge, MockBadge, RiskBadge } from "../components/Badge";
import { Card } from "../components/Card";
import { SkeletonChart, SkeletonLines } from "../components/Skeleton";
import ProviderSelect from "../components/ProviderSelect";
import { useToast } from "../context/ToastContext";
import { useProviders } from "../context/ProvidersContext";
import { useConfirm } from "../context/ConfirmContext";
import { useLanguage } from "../context/LanguageContext";
import { humanizeError } from "../i18n/errorMessages";
import { localeForLang } from "../i18n/locale";
import { copyToClipboard } from "../utils/copyToClipboard";
import { usePageTitle } from "../hooks/usePageTitle";

const COINS = ["BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "AVAX", "DOT", "LINK"];
const HORIZONS = ["24h", "1T", "1M", "1R"];

function formatPrice(v) {
  if (v == null) return "";
  if (v >= 1000) return `$${(v / 1000).toFixed(1)}k`;
  if (v >= 1) return `$${v.toFixed(2)}`;
  return `$${v.toFixed(4)}`;
}

function ForecastChart({ data, coin, t }) {
  const chartData = data.casove_body.map((time, i) => {
    const price = data.ceny[i];
    return { t: time, price, upper: +(price * 1.05).toFixed(4), lower: +(price * 0.95).toFixed(4) };
  });

  // Dynamický Y-axis rozsah (min/max ±5%), aby graf nezačínal od $0.
  const prices = data.ceny;
  const minPrice = Math.min(...prices);
  const maxPrice = Math.max(...prices);
  const padding = (maxPrice - minPrice) * 0.05 || maxPrice * 0.05 || 1;
  const yDomain = [Math.max(0, minPrice - padding), maxPrice + padding];

  return (
    <ResponsiveContainer width="100%" height={280}>
      <AreaChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="priceFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--cyan)" stopOpacity={0.35} />
            <stop offset="100%" stopColor="var(--cyan)" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />
        <XAxis dataKey="t" stroke="var(--text-tertiary)" fontSize={11} tickLine={false} axisLine={false} />
        <YAxis
          stroke="var(--text-tertiary)" fontSize={11} tickLine={false} axisLine={false} width={70}
          domain={yDomain} tickFormatter={formatPrice}
        />
        <Tooltip
          contentStyle={{ background: "#121824", border: "1px solid rgba(255,255,255,0.12)", borderRadius: 10, fontSize: 12 }}
          labelStyle={{ color: "var(--text-secondary)" }}
          formatter={(v, name) => [formatPrice(v), name === "price" ? coin : name]}
          labelFormatter={(label) => t("forecast.timeTooltip", { label })}
        />
        <Area type="monotone" dataKey="upper" stroke="none" fill="url(#priceFill)" fillOpacity={0.4} isAnimationActive={false} />
        <Area type="monotone" dataKey="price" stroke="var(--cyan)" strokeWidth={2.5} fill="url(#priceFill)" dot={{ r: 3, fill: "var(--cyan)" }} />
      </AreaChart>
    </ResponsiveContainer>
  );
}

function HistoryItem({ entry, onDelete }) {
  const { push } = useToast();
  const confirm = useConfirm();
  const { t, lang } = useLanguage();
  const [open, setOpen] = useState(false);
  const locale = localeForLang(lang);
  const hasChart = entry.forecast_data?.ceny && entry.forecast_data?.casove_body;

  async function handleCopy(e) {
    e.stopPropagation();
    const lines = [
      t("forecast.copyHeader", { coin: entry.crypto_symbol, timeframe: entry.timeframe }),
      t("forecast.copyModel", { model: entry.model_used }),
      t("forecast.copyCreated", { date: new Date(entry.created_at).toLocaleString(locale) }),
    ];
    if (entry.forecast_data?.confidence_score !== undefined) lines.push(t("forecast.copyConfidence", { value: entry.forecast_data.confidence_score }));
    if (entry.forecast_data?.risk_level) lines.push(t("forecast.copyRisk", { level: entry.forecast_data.risk_level }));
    if (entry.forecast_data?.odovodnenie) lines.push("", entry.forecast_data.odovodnenie);
    const ok = await copyToClipboard(lines.join("\n"));
    push(ok ? t("common.copied") : t("common.copyFailed"), ok ? "success" : "error");
  }

  async function handleDelete(e) {
    e.stopPropagation();
    const ok = await confirm(t("forecast.deleteConfirm", { coin: entry.crypto_symbol }));
    if (!ok) return;
    try {
      await api.deleteForecast(entry.id);
      push(t("common.deleted"), "success");
      onDelete?.(entry.id);
    } catch (err) {
      push(err, "error");
    }
  }

  return (
    <div className="card" style={{ marginBottom: 12, padding: 0, overflow: "hidden" }}>
      <button
        onClick={() => setOpen((v) => !v)}
        style={{
          width: "100%", display: "flex", alignItems: "center", justifyContent: "space-between",
          padding: "14px 18px", background: "transparent", border: "none", color: "var(--text-primary)",
          cursor: "pointer", fontSize: 13,
        }}
      >
        <span>
          <strong>{entry.crypto_symbol}</strong> · {entry.timeframe} · {entry.model_used} ·{" "}
          <span className="text-sub">{new Date(entry.created_at).toLocaleString(locale)}</span>
        </span>
        <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <span className="btn btn-ghost btn-sm" onClick={handleCopy} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); handleCopy(e); } }} title={t("common.copy")} aria-label={t("common.copy")} role="button" tabIndex={0}><Copy size={12} /></span>
          <span className="btn btn-danger-ghost btn-sm" onClick={handleDelete} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); handleDelete(e); } }} title={t("common.delete")} aria-label={t("common.delete")} role="button" tabIndex={0}><Trash2 size={12} /></span>
          <ChevronDown size={16} style={{ transform: open ? "rotate(180deg)" : "none", transition: "transform 0.15s" }} />
        </span>
      </button>
      {open && (
        <div style={{ padding: "0 18px 18px" }}>
          {hasChart ? (
            <>
              <ForecastChart data={entry.forecast_data} coin={entry.crypto_symbol} t={t} />
              {(entry.forecast_data.confidence_score !== undefined || entry.forecast_data.risk_level) && (
                <div style={{ display: "flex", gap: 8, margin: "10px 0", flexWrap: "wrap" }}>
                  {entry.forecast_data.confidence_score !== undefined && <ConfidenceBadge score={entry.forecast_data.confidence_score} />}
                  {entry.forecast_data.risk_level && <RiskBadge level={entry.forecast_data.risk_level} />}
                </div>
              )}
              <p className="text-sub" style={{ marginTop: 8 }}>{entry.forecast_data.odovodnenie}</p>
            </>
          ) : (
            <p className="text-sub">{t("forecast.noChartData")}</p>
          )}
        </div>
      )}
    </div>
  );
}

export default function Forecast() {
  const { push } = useToast();
  const { t } = useLanguage();
  usePageTitle("forecast.title");
  const [tab, setTab] = useState("new");
  const providersCtx = useProviders();
  const providers = providersCtx.providers;
  const [provider, setProvider] = useState(null);
  const [coin, setCoin] = useState("BTC");
  const [horizon, setHorizon] = useState("1T");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [history, setHistory] = useState([]);
  const [historyTotal, setHistoryTotal] = useState(0);
  const [historyPage, setHistoryPage] = useState(1);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyLoadingMore, setHistoryLoadingMore] = useState(false);
  const HISTORY_PAGE_SIZE = 20;
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (providersCtx.defaultProvider) setProvider(providersCtx.defaultProvider);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [providersCtx.defaultProvider]);

  useEffect(() => {
    if (tab === "history") loadHistory();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab]);

  async function loadHistory() {
    setHistoryLoading(true);
    try {
      const data = await api.forecastHistory(null, 30, 1, HISTORY_PAGE_SIZE);
      setHistory(data.items);
      setHistoryTotal(data.total);
      setHistoryPage(1);
    } catch (err) {
      push(err, "error");
    } finally {
      setHistoryLoading(false);
    }
  }

  async function loadMoreHistory() {
    setHistoryLoadingMore(true);
    try {
      const nextPage = historyPage + 1;
      const data = await api.forecastHistory(null, 30, nextPage, HISTORY_PAGE_SIZE);
      setHistory((prev) => [...prev, ...data.items]);
      setHistoryPage(nextPage);
    } catch (err) {
      push(err, "error");
    } finally {
      setHistoryLoadingMore(false);
    }
  }

  async function generate() {
    if (!provider) return;
    setLoading(true);
    setResult(null);
    setSaved(false);
    try {
      const res = await api.generateForecast(provider, coin, horizon);
      setResult(res);
      if (res.is_mock) push(res.error_message ? humanizeError(res.error_message, lang) : t("forecast.mockNotice"), "warn");
    } catch (err) {
      push(err, "error");
    } finally {
      setLoading(false);
    }
  }

  async function saveCurrentForecast() {
    if (!result?.data) return;
    setSaving(true);
    try {
      await api.saveForecast(provider, coin, horizon, result.data, result.is_mock);
      setSaved(true);
      push(t("common.saved"), "success");
    } catch (err) {
      push(err, "error");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div>
      <div className="topbar">
        <div>
          <h1 className="page-title">{t("forecast.title")}</h1>
          <p className="page-sub">{t("forecast.subtitle")}</p>
        </div>
      </div>

      <div className="tabs">
        <button className={`tab ${tab === "new" ? "active" : ""}`} onClick={() => setTab("new")}>{t("forecast.tabNew")}</button>
        <button className={`tab ${tab === "history" ? "active" : ""}`} onClick={() => setTab("history")}>{t("forecast.tabHistory")}</button>
      </div>

      {tab === "new" && (
        <>
          <Card>
            <div className="grid grid-3">
              <ProviderSelect providers={providers} value={provider} onChange={setProvider} />
              {providers.some((p) => p.connected) && (
                <>
                  <div className="field">
                    <label>{t("forecast.coinLabel")}</label>
                    <select className="select" value={coin} onChange={(e) => setCoin(e.target.value)}>
                      {COINS.map((c) => <option key={c} value={c}>{c}</option>)}
                      {!COINS.includes(coin) && <option value={coin}>{coin} {t("forecast.customSuffix")}</option>}
                    </select>
                  </div>
                  <div className="field">
                    <label>{t("forecast.horizonLabel")}</label>
                    <select className="select" value={horizon} onChange={(e) => setHorizon(e.target.value)}>
                      {HORIZONS.map((h) => <option key={h} value={h}>{t(`forecast.horizon${h}`)}</option>)}
                    </select>
                  </div>
                </>
              )}
            </div>
            {providers.some((p) => p.connected) && (
              <button className="btn btn-primary" onClick={generate} disabled={loading} style={{ marginTop: 4 }}>
                {loading ? <Loader2 size={15} className="spin" /> : <Rocket size={15} />}
                {loading ? t("forecast.generatingButton") : t("forecast.generateButton")}
              </button>
            )}
          </Card>

          {loading && (
            <div style={{ marginTop: 20 }}>
              <Card title={t("forecast.chartTitlePrefix")} icon={Sparkles}><SkeletonChart /></Card>
              <div style={{ height: 16 }} />
              <Card title={t("forecast.reasoningTitle")} icon={Brain}><SkeletonLines count={3} /></Card>
            </div>
          )}

          {!loading && result?.data && (
            <div style={{ marginTop: 20 }}>
              <Card title={`${t("forecast.chartTitlePrefix")}: ${coin}`} icon={Sparkles} glow="cyan">
                {result.is_mock && <div style={{ marginBottom: 12 }}><MockBadge /></div>}
                <ForecastChart data={result.data} coin={coin} t={t} />
              </Card>
              <div style={{ height: 16 }} />
              <Card title={t("forecast.reasoningTitle")} icon={Brain}>
                {(result.data.confidence_score !== undefined || result.data.risk_level) && (
                  <div style={{ display: "flex", gap: 8, marginBottom: 12, flexWrap: "wrap" }}>
                    {result.data.confidence_score !== undefined && <ConfidenceBadge score={result.data.confidence_score} />}
                    {result.data.risk_level && <RiskBadge level={result.data.risk_level} />}
                  </div>
                )}
                <p style={{ margin: 0, lineHeight: 1.6, fontSize: 13.5, color: "var(--text-secondary)" }}>
                  {result.data.odovodnenie}
                </p>
              </Card>
              <div style={{ marginTop: 14, display: "flex", justifyContent: "flex-end" }}>
                <button className="btn btn-primary btn-sm" onClick={saveCurrentForecast} disabled={saving || saved}>
                  {saving ? <Loader2 size={14} className="spin" /> : <Save size={14} />} {saved ? t("common.savedShort") : saving ? t("common.saving") : t("common.saveAnalysis")}
                </button>
              </div>
            </div>
          )}
        </>
      )}

      {tab === "history" && (
        <div>
          <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 14 }}>
            <button className="btn btn-ghost btn-sm" onClick={loadHistory}>
              <RefreshCw size={13} /> {t("common.refresh")}
            </button>
          </div>
          {historyLoading && <SkeletonLines count={4} />}
          {!historyLoading && history.length === 0 && (
            <div className="empty-state">{t("forecast.emptyHistory")}</div>
          )}
          {!historyLoading && history.map((entry) => (
            <HistoryItem key={entry.id} entry={entry} onDelete={(id) => { setHistory((prev) => prev.filter((h) => h.id !== id)); setHistoryTotal((n) => n - 1); }} />
          ))}
          {!historyLoading && history.length < historyTotal && (
            <div style={{ display: "flex", justifyContent: "center", marginTop: 8 }}>
              <button className="btn btn-ghost btn-sm" onClick={loadMoreHistory} disabled={historyLoadingMore}>
                {historyLoadingMore ? <Loader2 size={13} className="spin" /> : null}
                {t("common.loadMore", { shown: history.length, total: historyTotal })}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
