/** Run several providers for the same coin and horizon and overlay their forecasts. */

import { GitCompare, Loader2, Play } from "lucide-react";
import { useMemo, useState } from "react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api";
import { ConfidenceBadge, FallbackBadge, MockBadge, RiskBadge } from "./Badge";
import { Card } from "./Card";
import { useLanguage } from "../context/LanguageContext";
import { useProviders } from "../context/ProvidersContext";
import { humanizeError } from "../i18n/errorMessages";
import { COMPARE_COLORS, buildComparisonRows, changePct } from "../utils/compare";
import { axisDecimals, formatPrice, formatUsd } from "../utils/formatPrice";

const COINS = ["BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "AVAX", "DOT", "LINK"];
const HORIZONS = ["24h", "1T", "1M", "1R"];
const MAX_PROVIDERS = COMPARE_COLORS.length;

export default function ComparePanel() {
  const { t, lang } = useLanguage();
  const providersCtx = useProviders();
  const options = useMemo(() => [
    { provider: "quant", label: t("provider.quantLabel") },
    ...providersCtx.connected.map((p) => ({ provider: p.provider, label: p.provider === "custom" ? t("provider.customLabel") : p.label })),
  ], [providersCtx.connected, t]);
  const [selected, setSelected] = useState(["quant"]);
  const [coin, setCoin] = useState("BTC");
  const [horizon, setHorizon] = useState("1T");
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);

  function toggle(provider) {
    setSelected((prev) => (prev.includes(provider) ? prev.filter((p) => p !== provider)
      : prev.length >= MAX_PROVIDERS ? prev : [...prev, provider]));
  }

  async function run() {
    setLoading(true);
    setResults([]);
    // allSettled: one failing provider must not hide the others.
    const settled = await Promise.allSettled(selected.map((p) => api.generateForecast(p, coin, horizon)));
    setResults(settled.map((s, idx) => {
      const requested = selected[idx];
      const label = options.find((o) => o.provider === requested)?.label || requested;
      if (s.status === "rejected" || !s.value?.success) {
        return { key: requested, label, error: humanizeError(s.status === "rejected" ? s.reason : s.value?.error_message, lang) };
      }
      const res = s.value;
      return { key: requested, label, data: res.data, isMock: res.is_mock, fallback: Boolean(res.provider_used && res.provider_used !== requested) };
    }));
    setLoading(false);
  }

  // Sample data is not a forecast, so it never goes into the comparison chart.
  const charted = results.filter((r) => r.data && !r.isMock);
  const rows = buildComparisonRows(charted);
  const values = rows.flatMap((r) => charted.map((c) => r[c.key])).filter(Number.isFinite);
  const decimals = values.length ? axisDecimals(Math.min(...values), Math.max(...values)) : 0;
  const colorOf = (key) => COMPARE_COLORS[selected.indexOf(key) % COMPARE_COLORS.length];
  const aiCount = selected.filter((p) => p !== "quant").length;

  return (
    <>
      <Card title={t("compare.title")} icon={GitCompare}>
        <p className="text-sub" style={{ marginBottom: 14 }}>{t("compare.intro")}</p>
        <div className="compare-providers" role="group" aria-label={t("compare.providers")}>
          {options.map((o) => (
            <label key={o.provider} className={`compare-chip ${selected.includes(o.provider) ? "on" : ""}`}>
              <input type="checkbox" checked={selected.includes(o.provider)} onChange={() => toggle(o.provider)} />
              {o.label}
            </label>
          ))}
        </div>
        {options.length === 1 && <p className="text-sub" style={{ marginTop: 8 }}>{t("compare.onlyQuant")}</p>}
        <div className="grid grid-3" style={{ marginTop: 14 }}>
          <div className="field">
            <label htmlFor="cmp-coin">{t("forecast.coinLabel")}</label>
            <select id="cmp-coin" className="select" value={coin} onChange={(e) => setCoin(e.target.value)}>
              {COINS.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <div className="field">
            <label htmlFor="cmp-horizon">{t("forecast.horizonLabel")}</label>
            <select id="cmp-horizon" className="select" value={horizon} onChange={(e) => setHorizon(e.target.value)}>
              {HORIZONS.map((h) => <option key={h} value={h}>{t(`forecast.horizon${h}`)}</option>)}
            </select>
          </div>
        </div>
        {aiCount > 0 && <p className="text-sub" style={{ marginBottom: 8 }}>{t("compare.costNote", { n: aiCount })}</p>}
        <button className="btn btn-primary" onClick={run} disabled={loading || selected.length === 0}>
          {loading ? <Loader2 size={15} className="spin" /> : <Play size={15} />} {t("compare.run")}
        </button>
      </Card>

      {results.length > 0 && (
        <Card title={t("compare.resultsTitle", { coin, horizon })} style={{ marginTop: 16 }} glow="cyan">
          {rows.length > 0 ? (
            <div role="img" aria-label={t("compare.chartLabel")}>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={rows} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                  <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />
                  <XAxis dataKey="i" stroke="var(--text-tertiary)" fontSize={11} tickLine={false} axisLine={false}
                    tickFormatter={(i) => (i === 0 ? t("compare.now") : `+${i}`)} />
                  <YAxis stroke="var(--text-tertiary)" fontSize={11} tickLine={false} axisLine={false} width={84}
                    domain={["auto", "auto"]} tickFormatter={(v) => formatUsd(v, decimals)} />
                  <Tooltip
                    contentStyle={{ background: "var(--bg-tooltip)", border: "1px solid var(--border-strong)", borderRadius: 10, fontSize: 12, color: "var(--text-primary)" }}
                    labelFormatter={(i) => (i === 0 ? t("compare.now") : t("compare.step", { n: i }))}
                    formatter={(v, key) => [formatPrice(v), charted.find((c) => c.key === key)?.label || key]}
                  />
                  <Legend formatter={(key) => charted.find((c) => c.key === key)?.label || key} wrapperStyle={{ fontSize: 12 }} />
                  {charted.map((c) => (
                    <Line key={c.key} dataKey={c.key} stroke={colorOf(c.key)} strokeWidth={2.2} dot={{ r: 2.5 }} isAnimationActive={false} />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
          ) : <p className="text-sub">{t("compare.nothingToChart")}</p>}

          <div className="compare-table" role="table">
            {results.map((r) => {
              const change = r.data ? changePct(r.data) : null;
              return (
                <div key={r.key} className="compare-row" role="row">
                  <span role="cell" className="compare-name"><span className="compare-dot" style={{ background: colorOf(r.key) }} />{r.label}</span>
                  {r.error ? <span role="cell" className="text-sub compare-error">{r.error}</span> : (
                    <>
                      <span role="cell" className="mono">{formatPrice(r.data.ceny[r.data.ceny.length - 1])}</span>
                      <span role="cell" className={`mono ${change > 0 ? "up" : change < 0 ? "down" : ""}`}>
                        {change == null ? "—" : `${change > 0 ? "+" : ""}${change.toFixed(2)} %`}
                      </span>
                      <span role="cell" className="compare-badges">
                        {r.isMock && <MockBadge />}
                        {r.fallback && <FallbackBadge />}
                        {r.data.confidence_score !== undefined && <ConfidenceBadge score={r.data.confidence_score} />}
                        {r.data.risk_level && <RiskBadge level={r.data.risk_level} />}
                      </span>
                    </>
                  )}
                </div>
              );
            })}
          </div>
        </Card>
      )}
    </>
  );
}
