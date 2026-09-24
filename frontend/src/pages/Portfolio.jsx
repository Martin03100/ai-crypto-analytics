import { Compass, Download, FileText, GraduationCap, Loader2, Plus, RefreshCw, Save, Search, Trash2, Wallet } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { api } from "../api";
import { ActionBadge, MockBadge } from "../components/Badge";
import { Card } from "../components/Card";
import CoinSearchPicker from "../components/CoinSearchPicker";
import PortfolioHistoryItem from "../components/PortfolioHistoryItem";
import { SkeletonLines } from "../components/Skeleton";
import ProviderSelect from "../components/ProviderSelect";
import { useCurrency } from "../context/CurrencyContext";
import { useProviders } from "../context/ProvidersContext";
import { useToast } from "../context/ToastContext";
import { useLanguage } from "../context/LanguageContext";
import { humanizeError } from "../i18n/errorMessages";
import { localeForLang } from "../i18n/locale";
import { usePageTitle } from "../hooks/usePageTitle";

const COINS = ["BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "AVAX", "DOT", "LINK"];
const PIE_COLORS = ["#22d3ee", "#34d399", "#a78bfa", "#fbbf24", "#fb5a6a"];

// Mapovanie zakladnych symbolov na CoinGecko id (zhoduje sa s backend DEFAULT_COIN_IDS).
const DEFAULT_COIN_IDS = {
  BTC: "bitcoin", ETH: "ethereum", SOL: "solana", BNB: "binancecoin", XRP: "ripple",
  ADA: "cardano", DOGE: "dogecoin", AVAX: "avalanche-2", DOT: "polkadot", LINK: "chainlink",
};

/** Parsuje vstup množstva: akceptuje čiarku aj bodku ako desatinný oddeľovač,
 * zamedzí záporným číslam, neplatným znakom a NaN. Vracia { value, error }. */
function parseAmountInput(raw, t) {
  const cleaned = String(raw).trim().replace(",", ".");
  if (cleaned === "") return { value: 0, error: null };
  if (!/^\d*\.?\d*$/.test(cleaned)) {
    return { value: null, error: t("portfolio.validationInvalidNumber") };
  }
  const num = parseFloat(cleaned);
  if (Number.isNaN(num) || !Number.isFinite(num)) {
    return { value: null, error: t("portfolio.validationInvalidValue") };
  }
  if (num < 0) {
    return { value: null, error: t("portfolio.validationNegative") };
  }
  return { value: num, error: null };
}

export default function Portfolio() {
  const { push } = useToast();
  const { vsCurrency, formatAmount } = useCurrency();
  const { t, lang } = useLanguage();
  const locale = localeForLang(lang);
  usePageTitle("portfolio.title");
  const [tab, setTab] = useState("new");
  const providersCtx = useProviders();
  const providers = providersCtx.providers;
  const [provider, setProvider] = useState(null);
  const [holdings, setHoldings] = useState([{ minca: "BTC", mnozstvo: 1, coin_id: "bitcoin" }]);
  const [amountInputs, setAmountInputs] = useState({ 0: "1" });
  const [amountErrors, setAmountErrors] = useState({});
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [checked, setChecked] = useState({});
  const [prices, setPrices] = useState({});
  const [pfHistory, setPfHistory] = useState([]);
  const [pfHistoryTotal, setPfHistoryTotal] = useState(0);
  const [pfHistoryPage, setPfHistoryPage] = useState(1);
  const [pfHistoryLoading, setPfHistoryLoading] = useState(false);
  const [pfHistoryLoadingMore, setPfHistoryLoadingMore] = useState(false);
  const PF_HISTORY_PAGE_SIZE = 20;

  function loadPortfolioHistory() {
    setPfHistoryLoading(true);
    api.portfolioHistory(1, PF_HISTORY_PAGE_SIZE)
      .then((data) => { setPfHistory(data.items); setPfHistoryTotal(data.total); setPfHistoryPage(1); })
      .catch((err) => push(err, "error"))
      .finally(() => setPfHistoryLoading(false));
  }

  function loadMorePortfolioHistory() {
    setPfHistoryLoadingMore(true);
    const nextPage = pfHistoryPage + 1;
    api.portfolioHistory(nextPage, PF_HISTORY_PAGE_SIZE)
      .then((data) => { setPfHistory((prev) => [...prev, ...data.items]); setPfHistoryPage(nextPage); })
      .catch((err) => push(err, "error"))
      .finally(() => setPfHistoryLoadingMore(false));
  }

  useEffect(() => {
    if (tab === "history") loadPortfolioHistory();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab]);

  useEffect(() => {
    if (providersCtx.defaultProvider) setProvider(providersCtx.defaultProvider);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [providersCtx.defaultProvider]);

  const coinIds = useMemo(
    () => [...new Set(holdings.map((h) => h.coin_id).filter(Boolean))],
    [holdings]
  );

  useEffect(() => {
    if (coinIds.length === 0) {
      setPrices({});
      return;
    }
    api.livePrices(coinIds, vsCurrency).then((res) => setPrices(res.prices || {})).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [coinIds.join(","), vsCurrency]);

  function updateHolding(i, field, value) {
    setHoldings((prev) => prev.map((h, idx) => (idx === i ? { ...h, [field]: value } : h)));
  }

  function updateAmount(i, raw) {
    setAmountInputs((prev) => ({ ...prev, [i]: raw }));
    const { value, error } = parseAmountInput(raw, t);
    setAmountErrors((prev) => ({ ...prev, [i]: error }));
    if (!error) updateHolding(i, "mnozstvo", value);
  }

  function selectPresetCoin(i, symbol) {
    updateHolding(i, "minca", symbol);
    updateHolding(i, "coin_id", DEFAULT_COIN_IDS[symbol] || null);
  }

  function addRow() {
    const idx = holdings.length;
    setHoldings((prev) => [...prev, { minca: "BTC", mnozstvo: 1, coin_id: "bitcoin" }]);
    setAmountInputs((prev) => ({ ...prev, [idx]: "1" }));
  }

  function addCustomCoin(coin) {
    const idx = holdings.length;
    setHoldings((prev) => [...prev, { minca: coin.symbol, mnozstvo: 1, coin_id: coin.id }]);
    setAmountInputs((prev) => ({ ...prev, [idx]: "1" }));
    push(t("portfolio.addCustomCoinToast", { name: coin.name, symbol: coin.symbol }), "success");
  }

  function removeRow(i) {
    setHoldings((prev) => prev.filter((_, idx) => idx !== i));
    setAmountInputs((prev) => {
      const next = { ...prev };
      delete next[i];
      return next;
    });
  }

  const hasAmountErrors = Object.values(amountErrors).some(Boolean);

  const holdingValues = holdings.map((h) => {
    const price = h.coin_id ? prices[h.coin_id]?.[vsCurrency] : null;
    const value = price != null ? price * h.mnozstvo : null;
    return { ...h, price, value };
  });
  const totalValue = holdingValues.reduce((sum, h) => sum + (h.value || 0), 0);
  const hasAnyPrice = holdingValues.some((h) => h.value != null);

  async function analyze() {
    if (!provider || holdings.length === 0 || hasAmountErrors) return;
    setLoading(true);
    setResult(null);
    setSaved(false);
    try {
      const res = await api.analyzePortfolio(provider, holdings.map(({ minca, mnozstvo, coin_id }) => ({ minca, mnozstvo, coin_id })));
      setResult(res);
      if (res.is_mock) push(res.error_message ? humanizeError(res.error_message, lang) : t("forecast.mockNotice"), "warn");
    } catch (err) {
      push(err, "error");
    } finally {
      setLoading(false);
    }
  }

  async function saveCurrentAnalysis() {
    if (!result?.data) return;
    setSaving(true);
    try {
      await api.savePortfolio(provider, holdings.map(({ minca, mnozstvo, coin_id }) => ({ minca, mnozstvo, coin_id })), result.data, result.is_mock);
      setSaved(true);
      push(t("common.saved"), "success");
    } catch (err) {
      push(err, "error");
    } finally {
      setSaving(false);
    }
  }

  function exportJson() {
    const payload = {
      generated_at: new Date().toISOString(),
      holdings: holdingValues.map((h) => ({ minca: h.minca, mnozstvo: h.mnozstvo, cena_usd: h.price, hodnota_usd: h.value })),
      total_value_usd: totalValue,
      ai_analyza: result?.data || null,
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `portfolio-analyza-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  /** Escapuje HTML-specialne znaky pred vlozenim do document.write() nizsie.
   * NUTNE, lebo text z AI odpovede (odborna_analyza, dovod, akcia...) moze
   * teoreticky obsahovat "<script>" a pod. — bez escapovania by sa spustil
   * priamo v novom okne (XSS). Vsetky hodnoty vlozene do HTML sablony pod
   * touto funkciou MUSIA prejst cez escapeHtml(). */
  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function exportPdf() {
    const w = window.open("", "_blank");
    if (!w) return;
    const rows = holdingValues.map((h) => `<tr><td>${escapeHtml(h.minca)}</td><td>${escapeHtml(h.mnozstvo)}</td><td>${h.price != null ? escapeHtml(formatAmount(h.price)) : "—"}</td><td>${h.value != null ? escapeHtml(formatAmount(h.value)) : "—"}</td></tr>`).join("");
    const recs = (result?.data?.odporucania || []).map((r) => `<li><strong>${escapeHtml(r.minca)}</strong> — ${escapeHtml(r.akcia)}: ${escapeHtml(r.dovod)}</li>`).join("");
    const checklist = (result?.data?.rebalancing_checklist || []).map((c) => `<li>${escapeHtml(c)}</li>`).join("");
    w.document.write(`
      <html><head><title>${escapeHtml(t("portfolio.printTitle"))}</title>
      <style>body{font-family:sans-serif;padding:24px;color:#111}h1{font-size:20px}table{border-collapse:collapse;width:100%;margin:12px 0}td,th{border:1px solid #ccc;padding:6px 10px;font-size:13px;text-align:left}</style>
      </head><body>
      <h1>${escapeHtml(t("portfolio.printHeading"))}</h1>
      <p>${escapeHtml(t("portfolio.printGenerated", { date: new Date().toLocaleString(locale) }))}</p>
      <table><thead><tr><th>${escapeHtml(t("portfolio.printCoin"))}</th><th>${escapeHtml(t("portfolio.printAmount"))}</th><th>${escapeHtml(t("portfolio.printPriceUsd"))}</th><th>${escapeHtml(t("portfolio.printValueUsd"))}</th></tr></thead><tbody>${rows}</tbody></table>
      <p><strong>${escapeHtml(t("portfolio.printTotalValue", { value: formatAmount(totalValue) }))}</strong></p>
      ${result?.data?.odborna_analyza ? `<h2>${escapeHtml(t("portfolio.printExpertAnalysis"))}</h2><p>${escapeHtml(result.data.odborna_analyza)}</p>` : ""}
      ${recs ? `<h2>${escapeHtml(t("portfolio.printRecommendations"))}</h2><ul>${recs}</ul>` : ""}
      ${checklist ? `<h2>${escapeHtml(t("portfolio.printChecklist"))}</h2><ul>${checklist}</ul>` : ""}
      </body></html>
    `);
    w.document.close();
    w.print();
  }

  const sectorData = result?.data?.sektorova_alokacia
    ? Object.entries(result.data.sektorova_alokacia).map(([name, value]) => ({ name, value }))
    : [];

  return (
    <div>
      <div className="topbar">
        <div>
          <h1 className="page-title">{t("portfolio.title")}</h1>
          <p className="page-sub">{t("portfolio.subtitle")}</p>
        </div>
      </div>

      <div className="tabs">
        <button className={`tab ${tab === "new" ? "active" : ""}`} onClick={() => setTab("new")}>{t("portfolio.tabNew")}</button>
        <button className={`tab ${tab === "history" ? "active" : ""}`} onClick={() => setTab("history")}>{t("portfolio.tabHistory")}</button>
      </div>

      {tab === "new" && (
      <>
      <Card title={t("portfolio.myPortfolioTitle")} icon={Wallet}>
        <div style={{ marginBottom: 14 }}>
          <ProviderSelect providers={providers} value={provider} onChange={setProvider} />
        </div>

        {holdings.map((h, i) => {
          const hv = holdingValues[i];
          return (
            <div key={i} className="grid grid-2" style={{ marginBottom: 4, alignItems: "start" }}>
              <div className="field">
                <label>{t("portfolio.coinLabelIndexed", { index: i + 1 })}</label>
                <select className="select" value={COINS.includes(h.minca) ? h.minca : "custom"} onChange={(e) => selectPresetCoin(i, e.target.value)}>
                  {COINS.map((c) => <option key={c} value={c}>{c}</option>)}
                  {!COINS.includes(h.minca) && <option value="custom">{h.minca} ({t("common.custom")})</option>}
                </select>
              </div>
              <div style={{ display: "flex", gap: 8 }}>
                <div className="field" style={{ flex: 1 }}>
                  <label>{t("portfolio.amountLabel")}</label>
                  <input
                    className="input" type="text" inputMode="decimal" placeholder={t("portfolio.amountPlaceholder")}
                    value={amountInputs[i] ?? String(h.mnozstvo)}
                    onChange={(e) => updateAmount(i, e.target.value)}
                  />
                  {amountErrors[i] && <span style={{ color: "var(--crimson)", fontSize: 11.5 }}>{amountErrors[i]}</span>}
                  {!amountErrors[i] && hv?.value != null && (
                    <span className="holding-value">{formatAmount(hv.price)} × {h.mnozstvo} = {formatAmount(hv.value)}</span>
                  )}
                </div>
                {holdings.length > 1 && (
                  <button className="btn btn-danger-ghost" style={{ height: 41, marginTop: 22 }} onClick={() => removeRow(i)} aria-label={t("portfolio.removeCoin")}>
                    <Trash2 size={15} />
                  </button>
                )}
              </div>
            </div>
          );
        })}

        <div style={{ display: "flex", gap: 10, marginTop: 10, marginBottom: 14, flexWrap: "wrap" }}>
          <button className="btn btn-ghost btn-sm" onClick={addRow}><Plus size={14} /> {t("portfolio.addCoinButton")}</button>
        </div>

        <CoinSearchPicker onPick={addCustomCoin} />

        {hasAnyPrice && (
          <div className="portfolio-total">
            <span className="text-sub">{t("portfolio.totalValueLabel")}</span>
            <strong className="mono" style={{ fontSize: 16 }}>{formatAmount(totalValue)}</strong>
          </div>
        )}

        <hr className="divider" />
        {providers.some((p) => p.connected) && (
          <button className="btn btn-primary" onClick={analyze} disabled={loading || hasAmountErrors}>
            {loading ? <Loader2 size={15} className="spin" /> : <Search size={15} />}
            {loading ? t("portfolio.analyzingButton") : t("portfolio.analyzeButton")}
          </button>
        )}
      </Card>

      {loading && (
        <div style={{ marginTop: 20 }}>
          <Card title={t("portfolio.coinRatingTitle")}><SkeletonLines count={holdings.length} /></Card>
        </div>
      )}

      {!loading && result?.data && (
        <div style={{ marginTop: 20, display: "flex", flexDirection: "column", gap: 16 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 10 }}>
            {result.is_mock ? <MockBadge /> : <span />}
            <div style={{ display: "flex", gap: 8 }}>
              <button className="btn btn-primary btn-sm" onClick={saveCurrentAnalysis} disabled={saving || saved}>
                {saving ? <Loader2 size={13} className="spin" /> : <Save size={13} />} {saved ? t("common.savedShort") : saving ? t("common.saving") : t("common.saveAnalysis")}
              </button>
              <button className="btn btn-ghost btn-sm" onClick={exportJson}><Download size={13} /> {t("portfolio.exportJson")}</button>
              <button className="btn btn-ghost btn-sm" onClick={exportPdf}><FileText size={13} /> {t("portfolio.exportPdf")}</button>
            </div>
          </div>

          <Card title={t("portfolio.coinRatingTitle")} icon={Compass}>
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {result.data.odporucania?.map((rec, i) => (
                <div key={i} style={{
                  display: "flex", justifyContent: "space-between", alignItems: "center",
                  padding: "12px 14px", borderRadius: 10, background: "var(--bg-inset)", border: "1px solid var(--border-subtle)",
                }}>
                  <div>
                    <strong style={{ fontSize: 13.5 }}>{rec.minca}</strong>
                    <p className="text-sub" style={{ margin: "3px 0 0" }}>{rec.dovod}</p>
                  </div>
                  <ActionBadge action={rec.akcia} />
                </div>
              ))}
            </div>
          </Card>

          {sectorData.length > 0 && (
            <Card title={t("portfolio.sectorAllocationTitle")}>
              <div style={{ display: "flex", alignItems: "center", gap: 20, flexWrap: "wrap" }}>
                <ResponsiveContainer width={200} height={200}>
                  <PieChart>
                    <Pie data={sectorData} dataKey="value" nameKey="name" innerRadius={55} outerRadius={90} paddingAngle={2}>
                      {sectorData.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} stroke="none" />)}
                    </Pie>
                    <Tooltip contentStyle={{ background: "#121824", border: "1px solid rgba(255,255,255,0.12)", borderRadius: 10, fontSize: 12 }} />
                  </PieChart>
                </ResponsiveContainer>
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {sectorData.map((s, i) => (
                    <div key={s.name} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13 }}>
                      <span style={{ width: 9, height: 9, borderRadius: "50%", background: PIE_COLORS[i % PIE_COLORS.length] }} />
                      {s.name} — <strong className="mono">{s.value}%</strong>
                    </div>
                  ))}
                </div>
              </div>
            </Card>
          )}

          <Card title={t("portfolio.checklistTitle")}>
            {result.data.rebalancing_checklist?.map((step, i) => (
              <button
                key={i}
                type="button"
                className="checklist-item"
                onClick={() => setChecked((c) => ({ ...c, [i]: !c[i] }))}
                role="checkbox"
                aria-checked={Boolean(checked[i])}
              >
                <span className={`checkbox ${checked[i] ? "checked" : ""}`} aria-hidden="true">{checked[i] && "✓"}</span>
                <span style={{ textDecoration: checked[i] ? "line-through" : "none", color: checked[i] ? "var(--text-tertiary)" : "inherit" }}>
                  {step}
                </span>
              </button>
            ))}
          </Card>

          <Card title={t("portfolio.expertAnalysisTitle")} icon={GraduationCap}>
            <p style={{ margin: 0, lineHeight: 1.6, fontSize: 13.5, color: "var(--text-secondary)" }}>{result.data.odborna_analyza}</p>
          </Card>
        </div>
      )}
      </>
      )}

      {tab === "history" && (
        <div>
          <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 14 }}>
            <button className="btn btn-ghost btn-sm" onClick={loadPortfolioHistory}>
              <RefreshCw size={13} /> {t("common.refresh")}
            </button>
          </div>
          {pfHistoryLoading && <SkeletonLines count={3} />}
          {!pfHistoryLoading && pfHistory.length === 0 && (
            <div className="empty-state">{t("portfolio.emptyHistory")}</div>
          )}
          {!pfHistoryLoading && pfHistory.map((entry) => (
            <PortfolioHistoryItem key={entry.id} entry={entry} onDelete={(id) => { setPfHistory((prev) => prev.filter((h) => h.id !== id)); setPfHistoryTotal((n) => n - 1); }} />
          ))}
          {!pfHistoryLoading && pfHistory.length < pfHistoryTotal && (
            <div style={{ display: "flex", justifyContent: "center", marginTop: 8 }}>
              <button className="btn btn-ghost btn-sm" onClick={loadMorePortfolioHistory} disabled={pfHistoryLoadingMore}>
                {pfHistoryLoadingMore ? <Loader2 size={13} className="spin" /> : null}
                {t("common.loadMore", { shown: pfHistory.length, total: pfHistoryTotal })}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
