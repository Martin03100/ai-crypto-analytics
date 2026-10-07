/** Premium: "what if I had traded on every forecast?" Equity curve of the strategy against buy-and-hold. */

import { LineChart as LineIcon, Loader2, Play } from "lucide-react";
import { useMemo, useState } from "react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api";
import { useLanguage } from "../context/LanguageContext";
import { useProviders } from "../context/ProvidersContext";
import { usePremium } from "../hooks/usePremium";
import { humanizeError } from "../i18n/errorMessages";
import { localeForLang } from "../i18n/locale";
import { COINS } from "../utils/coins";
import { parseServerDate } from "../utils/formatPrice";
import { QUANT_LABEL } from "../utils/models";
import { Card } from "./Card";
import InfoTip from "./InfoTip";
import PremiumGate from "./PremiumGate";

const HORIZONS = ["24h", "1T", "1M"];

function Metric({ label, value, tone, help }) {
  return (
    <div className="backtest-metric">
      <div className={`metric-value ${tone || ""}`} style={{ fontSize: 22 }}>{value}</div>
      <div className="metric-label">{label} {help && <InfoTip text={help} />}</div>
    </div>
  );
}

const pct = (v) => (v == null ? "—" : `${v > 0 ? "+" : ""}${v.toFixed(2)} %`);
const tone = (v) => (v > 0 ? "up" : v < 0 ? "down" : "");

export default function StrategySimulator() {
  const { t, lang } = useLanguage();
  const { active } = usePremium();
  const { providers } = useProviders();
  const models = useMemo(() => [
    { value: QUANT_LABEL, label: t("provider.quantLabel") },
    ...providers.filter((p) => p.provider !== "custom").map((p) => ({ value: p.label, label: p.label })),
  ], [providers, t]);
  const [coin, setCoin] = useState("BTC");
  const [horizon, setHorizon] = useState("24h");
  const [model, setModel] = useState(QUANT_LABEL);
  const [allowShort, setAllowShort] = useState(false);
  const [fee, setFee] = useState("0.1");
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  if (!active) return <PremiumGate title={t("sim.title")} text={t("sim.gate")} />;

  const run = async () => {
    setLoading(true);
    setError(null);
    try {
      const fee_pct = Math.min(2, Math.max(0, Number(String(fee).replace(",", ".")) || 0));
      setResult(await api.simulate({ coin, horizon, model, allow_short: allowShort, fee_pct }));
    } catch (err) {
      setResult(null);
      setError(humanizeError(err, lang, "sim.failed"));
    } finally {
      setLoading(false);
    }
  };

  const locale = localeForLang(lang);
  const curve = (result?.curve || []).map((p, i) => {
    const date = /^\d{4}-\d{2}-\d{2}$/.test(p.date || "") ? new Date(`${p.date}T00:00:00Z`) : parseServerDate(p.date);
    return { ...p, d: date ? date.toLocaleDateString(locale, { day: "numeric", month: "numeric", timeZone: "UTC" }) : String(i) };
  });
  const edge = result ? result.strategy_return_pct - result.hodl_return_pct : null;

  return (
    <>
      <Card title={t("sim.title")} icon={LineIcon}>
        <p className="text-sub" style={{ marginTop: 0 }}>{t("sim.intro")}</p>
        <div className="grid grid-3">
          <div className="field">
            <label htmlFor="sim-model">{t("sim.model")}</label>
            <select id="sim-model" className="select" value={model} onChange={(e) => setModel(e.target.value)}>
              {models.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
            </select>
          </div>
          <div className="field">
            <label htmlFor="sim-coin">{t("forecast.coinLabel")}</label>
            <select id="sim-coin" className="select" value={coin} onChange={(e) => setCoin(e.target.value)}>
              {COINS.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <div className="field">
            <label htmlFor="sim-horizon">{t("forecast.horizonLabel")}</label>
            <select id="sim-horizon" className="select" value={horizon} onChange={(e) => setHorizon(e.target.value)}>
              {HORIZONS.map((h) => <option key={h} value={h}>{t(`forecast.horizon${h}`)}</option>)}
            </select>
          </div>
        </div>
        <div className="sim-options">
          <label className="toggle-row">
            <input type="checkbox" checked={allowShort} onChange={(e) => setAllowShort(e.target.checked)} />
            <span>{t("sim.short")}</span>
          </label>
          <label className="sim-fee">
            {t("sim.fee")}
            <input className="input" inputMode="decimal" value={fee} onChange={(e) => setFee(e.target.value)} aria-label={t("sim.fee")} />
            %
          </label>
        </div>
        <button className="btn btn-primary" onClick={run} disabled={loading}>
          {loading ? <Loader2 size={15} className="spin" /> : <Play size={15} />} {t("sim.run")}
        </button>
        {error && <p className="text-sub" role="alert" style={{ marginTop: 10 }}>{error}</p>}
      </Card>

      {result && (
        <Card title={t("sim.resultTitle", { coin: result.coin, horizon: t(`forecast.horizon${result.horizon}`) })} style={{ marginTop: 16 }}
              glow={edge > 0 ? "emerald" : edge < 0 ? "crimson" : undefined}>
          <div className="backtest-metrics">
            <Metric label={t("sim.strategy")} value={pct(result.strategy_return_pct)} tone={tone(result.strategy_return_pct)} />
            <Metric label={t("sim.hodl")} value={pct(result.hodl_return_pct)} tone={tone(result.hodl_return_pct)} />
            <Metric label={t("sim.winRate")} value={result.win_rate_pct == null ? "—" : `${result.win_rate_pct} %`} />
            <Metric label={t("sim.drawdown")} value={`-${result.max_drawdown_pct.toFixed(2)} %`} help={t("sim.drawdownHelp")} />
          </div>
          <p className="text-sub">{t("sim.summary", { trades: result.trades, periods: result.periods })}</p>
          <div role="img" aria-label={t("sim.chartLabel")}>
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={curve} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />
                <XAxis dataKey="d" stroke="var(--text-tertiary)" fontSize={11} tickLine={false} axisLine={false} minTickGap={24} />
                <YAxis stroke="var(--text-tertiary)" fontSize={11} tickLine={false} axisLine={false} width={44} domain={["auto", "auto"]} />
                <Tooltip contentStyle={{ background: "var(--bg-tooltip)", border: "1px solid var(--border-strong)", borderRadius: 10, fontSize: 12, color: "var(--text-primary)" }}
                         formatter={(v, key) => [v.toFixed(1), key === "strategy" ? t("sim.strategy") : t("sim.hodl")]} />
                <Legend formatter={(key) => (key === "strategy" ? t("sim.strategy") : t("sim.hodl"))} wrapperStyle={{ fontSize: 12 }} />
                <Line dataKey="strategy" stroke="#22d3ee" strokeWidth={2.2} dot={false} isAnimationActive={false} />
                <Line dataKey="hodl" stroke="#a78bfa" strokeWidth={1.6} strokeDasharray="4 3" dot={false} isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <p className="text-sub" style={{ marginBottom: 0 }}>{t("sim.disclaimer")}</p>
        </Card>
      )}
    </>
  );
}
