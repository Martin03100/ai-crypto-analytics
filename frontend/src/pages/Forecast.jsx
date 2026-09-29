/** Forecast page. */

import { Brain, CheckCircle2, ChevronDown, Copy, Link2, Loader2, RefreshCw, Rocket, Save, Share2, Sparkles, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { AccuracyBadge, ConfidenceBadge, FallbackBadge, MockBadge, RiskBadge } from "../components/Badge";
import { Card } from "../components/Card";
import CostConfirmModal from "../components/CostConfirmModal";
import DataSources from "../components/DataSources";
import ForecastChart, { hasForecastSeries } from "../components/ForecastChart";
import InfoTip from "../components/InfoTip";
import Leaderboard from "../components/Leaderboard";
import TipBox from "../components/TipBox";
import { useCurrency } from "../context/CurrencyContext";
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
import { stripMockTag } from "../utils/mockText";
import { formatTechDetail } from "../utils/techDetail";

const COINS = ["BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "AVAX", "DOT", "LINK"];
const HORIZONS = ["24h", "1T", "1M", "1R"];

function HistoryItem({ entry, onDelete }) {
  const { push } = useToast();
  const confirm = useConfirm();
  const { t, lang } = useLanguage();
  const [open, setOpen] = useState(false);
  const [accuracy, setAccuracy] = useState(null);
  const [accuracyLoading, setAccuracyLoading] = useState(false);
  const [shareToken, setShareToken] = useState(entry.share_token || null);
  const locale = localeForLang(lang);
  const hasChart = hasForecastSeries(entry.forecast_data);
  const canShare = entry.model_used !== "mock";
  const shareUrl = shareToken ? `${window.location.origin}/share/${shareToken}` : null;

  useEffect(() => {
    if (!open || accuracy || accuracyLoading) return;
    setAccuracyLoading(true);
    api.forecastAccuracy(entry.id)
      .then(setAccuracy)
      .catch(() => setAccuracy(null))
      .finally(() => setAccuracyLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

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
    push(ok ? t("common.copied") : t("common.copyFailed"), ok ? "success" : "error", { translated: true });
  }

  async function handleShare(e) {
    e.stopPropagation();
    try {
      const token = shareToken || (await api.shareForecast(entry.id)).share_token;
      setShareToken(token);
      const ok = await copyToClipboard(`${window.location.origin}/share/${token}`);
      push(t(ok ? "share.linkCopied" : "share.linkCreated"), "success");
    } catch (err) {
      push(err, "error");
    }
  }

  async function handleUnshare() {
    const ok = await confirm(t("share.revokeConfirm"));
    if (!ok) return;
    try {
      await api.unshareForecast(entry.id);
      setShareToken(null);
      push(t("share.revoked"), "success");
    } catch (err) {
      push(err, "error");
    }
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
          {canShare && (
            <span className={`btn btn-ghost btn-sm ${shareToken ? "is-shared" : ""}`} onClick={handleShare} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); handleShare(e); } }} title={t("share.button")} aria-label={t("share.button")} role="button" tabIndex={0}><Share2 size={12} /></span>
          )}
          <span className="btn btn-danger-ghost btn-sm" onClick={handleDelete} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); handleDelete(e); } }} title={t("common.delete")} aria-label={t("common.delete")} role="button" tabIndex={0}><Trash2 size={12} /></span>
          <ChevronDown size={16} style={{ transform: open ? "rotate(180deg)" : "none", transition: "transform 0.15s" }} />
        </span>
      </button>
      {open && (
        <div style={{ padding: "0 18px 18px" }}>
          {shareUrl && (
            <div className="share-row">
              <Link2 size={13} />
              <a href={shareUrl} target="_blank" rel="noreferrer" className="mono share-url">{shareUrl}</a>
              <button className="btn btn-danger-ghost btn-sm" onClick={handleUnshare}>{t("share.revoke")}</button>
            </div>
          )}
          {hasChart ? (
            <>
              <ForecastChart data={entry.forecast_data} t={t} createdAt={entry.created_at} horizon={entry.timeframe} locale={locale} actualPrices={accuracy?.status === "completed" ? accuracy.actual_prices : undefined} />
              {(entry.forecast_data.confidence_score !== undefined || entry.forecast_data.risk_level || accuracy?.status === "completed") && (
                <div style={{ display: "flex", gap: 8, margin: "10px 0", flexWrap: "wrap" }}>
                  {entry.forecast_data.confidence_score !== undefined && <ConfidenceBadge score={entry.forecast_data.confidence_score} />}
                  {entry.forecast_data.risk_level && <RiskBadge level={entry.forecast_data.risk_level} />}
                  {accuracy?.status === "completed" && <><AccuracyBadge score={accuracy.accuracy_pct} /><InfoTip text={t("help.accuracy")} /></>}
                  {accuracy?.status === "completed" && typeof accuracy.direction_correct === "boolean" && (
                    <span className={`badge ${accuracy.direction_correct ? "badge-buy" : "badge-sell"}`}>
                      <span className="badge-dot" /> {t(accuracy.direction_correct ? "forecast.directionCorrect" : "forecast.directionWrong")}
                    </span>
                  )}
                </div>
              )}
              {accuracy?.status === "completed" && accuracy.baseline_accuracy_pct != null && (
                <p className="text-sub" style={{ marginTop: 4 }}>{t("forecast.baselineComparison", { baseline: accuracy.baseline_accuracy_pct.toFixed(1) })}</p>
              )}
              <TipBox entryId={entry.id} accuracy={accuracy} onTipped={(price) => setAccuracy((a) => ({ ...a, tip_price: price, can_tip: false }))} />
              {accuracyLoading && <p className="text-sub" style={{ marginTop: 4 }}>{t("forecast.accuracyLoading")}</p>}
              {accuracy?.status === "unavailable" && (
                <p className="text-sub" style={{ marginTop: 4 }}>{t("forecast.accuracyUnavailable")}</p>
              )}
              {accuracy?.status === "mock" && (
                <p className="text-sub" style={{ marginTop: 4 }}>{t("forecast.accuracyMock")}</p>
              )}
              {accuracy?.status === "pending" && (
                <p className="text-sub" style={{ marginTop: 4 }}>
                  {t("forecast.accuracyPending", { date: new Date(accuracy.matures_at).toLocaleDateString(locale) })}
                </p>
              )}
              <p className="text-sub" style={{ marginTop: 8 }}>{stripMockTag(entry.forecast_data.odovodnenie)}</p>
              <DataSources sources={entry.forecast_data.zdroje_dat} />
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
  const { t, lang } = useLanguage();
  usePageTitle("forecast.title");
  const { currency } = useCurrency();
  const [tab, setTab] = useState("new");
  const providersCtx = useProviders();
  const providers = useMemo(
    () => [...providersCtx.providers, { provider: "quant", label: t("provider.quantLabel"), connected: true }],
    [providersCtx.providers, t]
  );
  const hasAiProvider = providersCtx.providers.some((p) => p.connected);
  const canGenerate = providers.some((p) => p.connected);
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
  const [selectedIds, setSelectedIds] = useState([]);
  const confirmDialog = useConfirm();
  const [costEstimate, setCostEstimate] = useState(null);
  const [estimating, setEstimating] = useState(false);

  useEffect(() => {
    setProvider(providersCtx.defaultProvider || "quant");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [providersCtx.defaultProvider]);

  useEffect(() => {
    if (tab === "history") loadHistory();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab]);

  async function loadHistory() {
    setHistoryLoading(true);
    try {
      const data = await api.forecastHistory(null, null, 1, HISTORY_PAGE_SIZE);
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
      const data = await api.forecastHistory(null, null, nextPage, HISTORY_PAGE_SIZE);
      setHistory((prev) => [...prev, ...data.items.filter((n) => !prev.some((p) => p.id === n.id))]);
      setHistoryPage(nextPage);
    } catch (err) {
      push(err, "error");
    } finally {
      setHistoryLoadingMore(false);
    }
  }

  async function bulkDeleteForecasts() {
    const ok = await confirmDialog(t("common.deleteSelectedConfirm", { n: selectedIds.length }));
    if (!ok) return;
    try {
      const res = await api.bulkDeleteForecasts(selectedIds);
      setHistory((prev) => prev.filter((h) => !selectedIds.includes(h.id)));
      setHistoryTotal((n) => n - res.deleted);
      setSelectedIds([]);
      push(t("common.deleted"), "success");
    } catch (err) {
      push(err, "error");
    }
  }

  async function generate() {
    if (!provider) return;
    const providerInfo = providers.find((p) => p.provider === provider);
    if (provider === "quant" || !providerInfo?.connected) {
      doGenerate();
      return;
    }
    setEstimating(true);
    try {
      const est = await api.estimateForecastCost(provider, coin, horizon);
      setCostEstimate(est);
    } catch (err) {
      doGenerate();
    } finally {
      setEstimating(false);
    }
  }

  async function doGenerate() {
    setCostEstimate(null);
    setLoading(true);
    setResult(null);
    setSaved(false);
    try {
      const res = await api.generateForecast(provider, coin, horizon);
      if (!res.success || !res.data) {
        push(res.error_message || t("errors.generic"), "error");
        return;
      }
      // provider_used is set when the backend fell back to the free statistical model;
      // the result must then be saved and labelled as that model, not the requested one.
      const usedProvider = res.provider_used || provider;
      const fallbackFrom = res.provider_used && res.provider_used !== provider ? provider : null;
      setResult({ ...res, generatedAt: new Date().toISOString(), horizon, coin, provider: usedProvider, fallbackFrom });
      if (fallbackFrom) push(t("forecast.quantFallback"), "warn");
      else if (res.is_mock) push(res.error_message ? humanizeError(res.error_message, lang, "errors.aiFallback") : t("forecast.mockNotice"), "warn");
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
      await api.saveForecast(result.provider, result.coin, result.horizon, result.data, result.is_mock);
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
        <button className={`tab ${tab === "leaderboard" ? "active" : ""}`} onClick={() => setTab("leaderboard")}>{t("forecast.tabLeaderboard")}</button>
      </div>

      {tab === "new" && (
        <>
          <Card>
            <div className="grid grid-3">
              <ProviderSelect providers={providers} value={provider} onChange={setProvider} />
              {canGenerate && (
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
            {!hasAiProvider && (() => {
              const [before, after] = t("forecast.quantHint", { link: "\u0000" }).split("\u0000");
              return <p className="text-sub" style={{ margin: "4px 0 10px" }}>{before}<Link to="/account" style={{ color: "var(--cyan-fg)" }}>{t("provider.connectLinkLabel")}</Link>{after}</p>;
            })()}
            {canGenerate && (
              <button className="btn btn-primary" onClick={generate} disabled={loading || estimating} style={{ marginTop: 4 }}>
                {(loading || estimating) ? <Loader2 size={15} className="spin" /> : <Rocket size={15} />}
                {loading ? t("forecast.generatingButton") : estimating ? t("costConfirm.estimating") : t("forecast.generateButton")}
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
              <Card title={`${t("forecast.chartTitlePrefix")}: ${result.coin}`} icon={Sparkles} glow="cyan">
                {result.is_mock && <div style={{ marginBottom: 12 }}><MockBadge /></div>}
                {result.fallbackFrom && <div style={{ marginBottom: 12 }}><FallbackBadge /></div>}
                {(result.is_mock || result.fallbackFrom) && result.error_message && (
                  <details className="tech-detail">
                    <summary>{t("forecast.technicalDetail")}</summary>
                    <code>{formatTechDetail(result.error_message)}</code>
                  </details>
                )}
                <ForecastChart data={result.data} t={t} createdAt={result.generatedAt} horizon={result.horizon} locale={localeForLang(lang)} />
                {currency !== "USD" && <p className="text-sub" style={{ marginTop: 6 }}>{t("forecast.usdNote")}</p>}
              </Card>
              <div style={{ height: 16 }} />
              <Card title={t(result.provider === "quant" ? "forecast.reasoningTitleQuant" : "forecast.reasoningTitle")} icon={Brain}>
                {(result.data.confidence_score !== undefined || result.data.risk_level) && (
                  <div style={{ display: "flex", gap: 8, marginBottom: 12, flexWrap: "wrap" }}>
                    {result.data.confidence_score !== undefined && <><ConfidenceBadge score={result.data.confidence_score} /><InfoTip text={t("help.confidence")} /></>}
                    {result.data.risk_level && <><RiskBadge level={result.data.risk_level} /><InfoTip text={t("help.risk")} /></>}
                  </div>
                )}
                <p style={{ margin: 0, lineHeight: 1.6, fontSize: 13.5, color: "var(--text-secondary)" }}>
                  {stripMockTag(result.data.odovodnenie)}
                </p>
                <DataSources sources={result.data.zdroje_dat} />
              </Card>
              <div style={{ marginTop: 14, display: "flex", justifyContent: "flex-end" }}>
                <button className={`btn btn-sm ${saved ? "btn-success" : "btn-primary"}`} onClick={saveCurrentForecast} disabled={saving || saved}>
                  {saving ? <Loader2 size={14} className="spin" /> : saved ? <CheckCircle2 size={14} /> : <Save size={14} />} {saved ? t("common.savedShort") : saving ? t("common.saving") : t("common.saveAnalysis")}
                </button>
              </div>
            </div>
          )}
        </>
      )}

      {tab === "leaderboard" && <Leaderboard />}

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
          {!historyLoading && history.length > 0 && (
            <div className="bulk-toolbar">
              <label className="bulk-select-all">
                <input type="checkbox" checked={selectedIds.length === history.length}
                  onChange={(e) => setSelectedIds(e.target.checked ? history.map((h) => h.id) : [])} /> {t("common.selectAll")}
              </label>
              {selectedIds.length > 0 && (
                <button className="btn btn-ghost btn-sm" style={{ color: "var(--crimson-fg)" }} onClick={bulkDeleteForecasts}>
                  <Trash2 size={13} /> {t("common.deleteSelected", { n: selectedIds.length })}
                </button>
              )}
            </div>
          )}
          {!historyLoading && history.map((entry) => (
            <div key={entry.id} className="selectable-row">
              <input type="checkbox" className="row-check" aria-label={t("common.selectItem")} checked={selectedIds.includes(entry.id)}
                onChange={(e) => setSelectedIds((prev) => (e.target.checked ? [...prev, entry.id] : prev.filter((x) => x !== entry.id)))} />
              <div className="selectable-row-body">
                <HistoryItem entry={entry} onDelete={(id) => { setHistory((prev) => prev.filter((h) => h.id !== id)); setHistoryTotal((n) => n - 1); setSelectedIds((prev) => prev.filter((x) => x !== id)); }} />
              </div>
            </div>
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
      {costEstimate && (
        <CostConfirmModal
          estimate={costEstimate}
          providerLabel={providers.find((p) => p.provider === provider)?.label || provider}
          confirming={loading}
          onConfirm={doGenerate}
          onCancel={() => setCostEstimate(null)}
        />
      )}
    </div>
  );
}
