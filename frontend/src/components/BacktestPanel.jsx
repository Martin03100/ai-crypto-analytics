/** Walk-forward backtest of the free statistical model on real history. */

import { FlaskConical, Loader2, Play } from "lucide-react";
import { useState } from "react";
import {
  Area, CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { api } from "../api";
import { Card } from "./Card";
import InfoTip from "./InfoTip";
import { useLanguage } from "../context/LanguageContext";
import { humanizeError } from "../i18n/errorMessages";
import { localeForLang } from "../i18n/locale";
import { axisDecimals, formatPrice, formatUsd } from "../utils/formatPrice";
import { backtestVerdicts } from "../utils/backtest";
import { COINS } from "../utils/coins";

const HORIZONS = ["24h", "1T", "1M"];

function Metric({ value, label, help, tone }) {
  return (
    <div className="backtest-metric">
      <div className={`metric-value ${tone || ""}`} style={{ fontSize: 22 }}>{value}</div>
      <div className="metric-label">{label} {help && <InfoTip text={help} />}</div>
    </div>
  );
}

export default function BacktestPanel() {
  const { t, lang } = useLanguage();
  const locale = localeForLang(lang);
  const [coin, setCoin] = useState("BTC");
  const [horizon, setHorizon] = useState("1T");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  async function run() {
    setLoading(true);
    setError(null);
    try {
      setResult(await api.backtest(coin, horizon));
    } catch (err) {
      setResult(null);
      setError(humanizeError(err, lang, "backtest.failed"));
    } finally {
      setLoading(false);
    }
  }

  const chartData = (result?.samples || []).map((s) => ({
    d: new Date(s.date).toLocaleDateString(locale, { day: "numeric", month: "numeric", year: "2-digit" }),
    actual: s.actual, predicted: s.predicted, band: [s.low, s.high],
  }));
  const verdicts = result ? backtestVerdicts(result) : null;
  const values = chartData.flatMap((p) => [p.actual, p.predicted, ...p.band]).filter(Number.isFinite);
  const decimals = values.length ? axisDecimals(Math.min(...values), Math.max(...values)) : 0;

  return (
    <>
      <Card title={<>{t("backtest.title")} <InfoTip text={t("backtest.help")} /></>} icon={FlaskConical}>
        <p className="text-sub" style={{ marginBottom: 14 }}>{t("backtest.intro")}</p>
        <div className="grid grid-3">
          <div className="field">
            <label htmlFor="bt-coin">{t("forecast.coinLabel")}</label>
            <select id="bt-coin" className="select" value={coin} onChange={(e) => setCoin(e.target.value)}>
              {COINS.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <div className="field">
            <label htmlFor="bt-horizon">{t("forecast.horizonLabel")}</label>
            <select id="bt-horizon" className="select" value={horizon} onChange={(e) => setHorizon(e.target.value)}>
              {HORIZONS.map((h) => <option key={h} value={h}>{t(`forecast.horizon${h}`)}</option>)}
            </select>
          </div>
        </div>
        <button className="btn btn-primary" onClick={run} disabled={loading} style={{ marginTop: 4 }}>
          {loading ? <Loader2 size={15} className="spin" /> : <Play size={15} />} {t("backtest.run")}
        </button>
        {error && <div className="alert alert-warn" role="alert" style={{ marginTop: 14 }}>{error}</div>}
      </Card>

      {result && (
        <Card title={t("backtest.resultsTitle", { coin: result.coin, horizon: t(`forecast.horizon${result.horizon}`) })} style={{ marginTop: 16 }} glow="cyan">
          <p className="text-sub" style={{ marginBottom: 14 }}>
            {t("backtest.period", {
              from: new Date(result.period_start).toLocaleDateString(locale),
              to: new Date(result.period_end).toLocaleDateString(locale), n: result.sample_count,
            })}
          </p>
          <div className="backtest-metrics">
            <Metric value={`${result.mape_pct.toFixed(1)} %`} label={t("backtest.mape")} help={t("backtest.mapeHelp")} />
            <Metric value={`${result.naive_mape_pct.toFixed(1)} %`} label={t("backtest.naive")} help={t("backtest.naiveHelp")} />
            <Metric value={`${result.band_coverage_pct.toFixed(0)} %`} label={t("backtest.coverage")} help={t("backtest.coverageHelp")}
              tone={verdicts.calibrated ? "up" : "down"} />
            <Metric value={result.direction_accuracy_pct == null ? "—" : `${result.direction_accuracy_pct.toFixed(0)} %`}
              label={t("backtest.direction")} help={t("backtest.directionHelp")} />
          </div>
          <div role="img" aria-label={t("backtest.chartLabel")} style={{ marginTop: 18 }}>
            <ResponsiveContainer width="100%" height={300}>
              <ComposedChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />
                <XAxis dataKey="d" stroke="var(--text-tertiary)" fontSize={11} tickLine={false} axisLine={false} minTickGap={24} />
                <YAxis stroke="var(--text-tertiary)" fontSize={11} tickLine={false} axisLine={false} width={84}
                  domain={["auto", "auto"]} tickFormatter={(v) => formatUsd(v, decimals)} />
                <Tooltip
                  contentStyle={{ background: "var(--bg-tooltip)", border: "1px solid var(--border-strong)", borderRadius: 10, fontSize: 12, color: "var(--text-primary)" }}
                  formatter={(v, name) => (Array.isArray(v) ? [`${formatPrice(v[0])} – ${formatPrice(v[1])}`, t("forecast.legendBand")]
                    : [formatPrice(v), name === "actual" ? t("forecast.legendActual") : t("forecast.legendPredicted")])}
                />
                <Legend formatter={(v) => (v === "actual" ? t("forecast.legendActual") : v === "band" ? t("forecast.legendBand") : t("forecast.legendPredicted"))}
                  wrapperStyle={{ fontSize: 12 }} />
                <Area dataKey="band" name="band" stroke="none" fill="var(--cyan)" fillOpacity={0.14} isAnimationActive={false} />
                <Line dataKey="predicted" name="predicted" stroke="var(--cyan-fg)" strokeWidth={2} dot={false} isAnimationActive={false} />
                <Line dataKey="actual" name="actual" stroke="var(--amber-fg)" strokeWidth={2} dot={false} isAnimationActive={false} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
          <ul className="backtest-verdicts">
            <li>{t(verdicts.calibrated ? "backtest.verdictCalibrated" : "backtest.verdictNotCalibrated", { value: result.band_coverage_pct.toFixed(0) })}</li>
            <li>{t(verdicts.beatsNaive ? "backtest.verdictBeatsNaive" : "backtest.verdictNoEdge")}</li>
            <li>{t("backtest.verdictDirection")}</li>
          </ul>
        </Card>
      )}
    </>
  );
}
