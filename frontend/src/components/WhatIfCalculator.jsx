/** "What if": X dollars following the free model's daily signal vs. just holding, over 7 / 30 / 90 days. */

import { Calculator, Loader2, Play } from "lucide-react";
import { useState } from "react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api";
import { useLanguage } from "../context/LanguageContext";
import { humanizeError } from "../i18n/errorMessages";
import { localeForLang } from "../i18n/locale";
import { COINS } from "../utils/coins";
import { Card } from "./Card";
import InfoTip from "./InfoTip";
import { parseAmount } from "../utils/viewHelpers";

const PERIODS = [7, 30, 90];

function Result({ label, data, tone, extra }) {
  const { t } = useLanguage();
  const pct = data.return_pct;
  return (
    <div className={`card whatif-tile ${tone}`}>
      <span className="text-sub">{label}</span>
      <span className="whatif-value mono">${Number(data.final).toLocaleString("en-US", { maximumFractionDigits: 2 })}</span>
      <span className={`metric-delta ${pct >= 0 ? "up" : "down"}`}>{pct >= 0 ? "+" : ""}{pct}%</span>
      <span className="text-sub">{t("whatif.drawdown", { pct: data.max_drawdown_pct })}</span>
      {extra}
    </div>
  );
}

export default function WhatIfCalculator({ style }) {
  const { t, lang } = useLanguage();
  const [coin, setCoin] = useState("BTC");
  const [days, setDays] = useState(30);
  const [amount, setAmount] = useState("1000");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const run = async (e) => {
    e.preventDefault();
    const value = parseAmount(amount);
    if (value == null) {
      setError(t("whatif.badAmount"));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      setResult(await api.whatIf(coin, days, value));
    } catch (err) {
      setError(humanizeError(err, lang));
      setResult(null);
    } finally {
      setBusy(false);
    }
  };

  const locale = localeForLang(lang);
  const rows = (result?.curve || []).map((p) => ({ ...p, label: new Date(`${p.date}T12:00:00Z`).toLocaleDateString(locale, { day: "numeric", month: "short" }) }));
  const won = result && result.strategy.final >= result.hold.final;

  return (
    <Card title={<>{t("whatif.title")} <InfoTip text={t("whatif.help")} /></>} icon={Calculator} style={style}>
      <form className="whatif-form" onSubmit={run}>
        <label className="whatif-field">
          <span className="text-sub">{t("whatif.coin")}</span>
          <select className="select" value={coin} onChange={(e) => setCoin(e.target.value)}>
            {COINS.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </label>
        <label className="whatif-field">
          <span className="text-sub">{t("whatif.amount")}</span>
          <input className="input mono" inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} />
        </label>
        <div className="whatif-field">
          <span className="text-sub" id="whatif-period">{t("whatif.period")}</span>
          <div className="tabs" role="radiogroup" aria-labelledby="whatif-period">
            {PERIODS.map((p) => (
              <button key={p} type="button" role="radio" aria-checked={days === p} className={`tab ${days === p ? "active" : ""}`} onClick={() => setDays(p)}>
                {t("whatif.days", { n: p })}
              </button>
            ))}
          </div>
        </div>
        <button className="btn btn-primary btn-sm" type="submit" disabled={busy}>
          {busy ? <Loader2 size={14} className="spin" /> : <Play size={14} />} {t("whatif.run")}
        </button>
      </form>

      {error && <p className="inline-error" role="alert">{error}</p>}

      {result && (
        <div className="whatif-result" aria-live="polite">
          <p className="whatif-verdict">
            {t(won ? "whatif.verdictWin" : "whatif.verdictLose", {
              coin: result.coin, days: result.days, diff: Math.abs(result.strategy.final - result.hold.final).toLocaleString("en-US", { maximumFractionDigits: 0 }),
            })}
          </p>
          <div className="whatif-tiles">
            <Result label={t("whatif.followAi")} data={result.strategy} tone={won ? "win" : ""}
                    extra={<span className="text-sub">{t("whatif.trades", { n: result.strategy.trades, pct: result.strategy.exposure_pct })}</span>} />
            <Result label={t("whatif.hold")} data={result.hold} tone={won ? "" : "win"} />
          </div>
          <div role="img" aria-label={t("whatif.chart")}>
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={rows} margin={{ top: 10, right: 12, left: 0, bottom: 0 }}>
                <CartesianGrid stroke="rgba(127,127,127,0.12)" vertical={false} />
                <XAxis dataKey="label" stroke="var(--text-tertiary)" fontSize={11} tickLine={false} axisLine={false} minTickGap={24} />
                <YAxis stroke="var(--text-tertiary)" fontSize={11} tickLine={false} axisLine={false} width={56} domain={["auto", "auto"]}
                       tickFormatter={(v) => `$${Math.round(v).toLocaleString("en-US")}`} />
                <Tooltip contentStyle={{ background: "var(--bg-tooltip)", border: "1px solid var(--border-strong)", borderRadius: 10, fontSize: 12, color: "var(--text-primary)" }}
                         formatter={(v, key) => [`$${Number(v).toLocaleString("en-US", { maximumFractionDigits: 2 })}`, t(key === "strategy" ? "whatif.followAi" : "whatif.hold")]} />
                <Legend formatter={(key) => t(key === "strategy" ? "whatif.followAi" : "whatif.hold")} wrapperStyle={{ fontSize: 12 }} />
                <Line type="monotone" dataKey="strategy" stroke="#22d3ee" strokeWidth={2} dot={false} isAnimationActive={false} />
                <Line type="monotone" dataKey="hold" stroke="#a1a1aa" strokeWidth={2} dot={false} isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <p className="text-sub" style={{ margin: "6px 0 0" }}>
            {t(`whatif.today_${result.signal_today}`, { coin: result.coin })} · {t("whatif.disclaimer", { fee: result.fee_pct })}
          </p>
        </div>
      )}
    </Card>
  );
}
