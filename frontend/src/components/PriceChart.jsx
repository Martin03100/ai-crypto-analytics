import { priceAxisDecimals } from "../utils/formatPrice";
import { LineChart } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Area, AreaChart, Bar, Brush, CartesianGrid, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { macdSeries, rsiSeries } from "../utils/indicators";
import InfoTip from "./InfoTip";

const TOOLTIP_STYLE = { background: "var(--bg-tooltip)", border: "1px solid var(--border-strong)", borderRadius: 10, fontSize: 12, color: "var(--text-primary)" };
// Na dotykovych zariadeniach vacsie "uchytky" na priblizenie casoveho rozsahu.
const COARSE_POINTER = typeof window !== "undefined" && Boolean(window.matchMedia?.("(pointer: coarse)").matches);
import { api } from "../api";
import { Card } from "./Card";
import { SkeletonChart } from "./Skeleton";
import { useCurrency } from "../context/CurrencyContext";
import { useLanguage } from "../context/LanguageContext";
import { localeForLang } from "../i18n/locale";

const COINS = [
  { id: "bitcoin", symbol: "BTC" }, { id: "ethereum", symbol: "ETH" }, { id: "solana", symbol: "SOL" },
  { id: "binancecoin", symbol: "BNB" }, { id: "ripple", symbol: "XRP" }, { id: "dogecoin", symbol: "DOGE" },
];

function sma(values, period) {
  return values.map((_, i) => {
    if (i < period - 1) return null;
    const slice = values.slice(i - period + 1, i + 1);
    return slice.reduce((sum, v) => sum + v, 0) / period;
  });
}

export default function PriceChart() {
  const { vsCurrency, formatAmount } = useCurrency();
  const { t, lang } = useLanguage();
  const TIMEFRAMES = [
    { label: t("chart.tf24h"), days: "1" }, { label: t("chart.tf7d"), days: "7" },
    { label: t("chart.tf30d"), days: "30" }, { label: t("chart.tf1y"), days: "365" },
  ];
  const [coinId, setCoinId] = useState("bitcoin");
  const [timeframe, setTimeframe] = useState("7");
  const [showSma, setShowSma] = useState(false);
  const [showRsi, setShowRsi] = useState(false);
  const [showMacd, setShowMacd] = useState(false);
  const [raw, setRaw] = useState(null);
  const [loading, setLoading] = useState(false);
  const [isMock, setIsMock] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api.marketChart(coinId, vsCurrency, timeframe)
      .then((res) => {
        if (cancelled) return;
        setRaw(res.prices || []);
        setIsMock(res.is_mock);
      })
      .catch(() => { if (!cancelled) setRaw([]); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [coinId, timeframe, vsCurrency]);

  const chartData = useMemo(() => {
    if (!raw || raw.length === 0) return [];
    const values = raw.map((p) => p[1]);
    const smaValues = showSma ? sma(values, Math.min(14, Math.floor(values.length / 3) || 1)) : [];
    const rsiValues = showRsi ? rsiSeries(values) : [];
    const macdValues = showMacd ? macdSeries(values) : [];
    return raw.map(([ts, price], i) => ({
      t: new Date(ts).toLocaleDateString(localeForLang(lang), timeframe === "1" ? { hour: "2-digit", minute: "2-digit" } : { day: "2-digit", month: "2-digit" }),
      price,
      sma: showSma ? smaValues[i] : undefined,
      rsi: showRsi ? rsiValues[i] : undefined,
      ...(showMacd ? macdValues[i] : {}),
    }));
  }, [raw, showSma, showRsi, showMacd, timeframe, lang]);

  return (
    <Card title={t("chart.title")} icon={LineChart}>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 10, alignItems: "center", marginBottom: 14 }}>
        <select className="select" style={{ maxWidth: 140 }} value={coinId} onChange={(e) => setCoinId(e.target.value)}>
          {COINS.map((c) => <option key={c.id} value={c.id}>{c.symbol}</option>)}
        </select>
        <div className="tabs">
          {TIMEFRAMES.map((tf) => (
            <button key={tf.days} className={`tab ${timeframe === tf.days ? "active" : ""}`} onClick={() => setTimeframe(tf.days)}>
              {tf.label}
            </button>
          ))}
        </div>
        <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12.5, color: "var(--text-secondary)", cursor: "pointer", marginLeft: "auto" }}>
          <input type="checkbox" checked={showSma} onChange={(e) => setShowSma(e.target.checked)} />
          {t("chart.smaIndicator")} <InfoTip text={t("help.sma")} />
        </label>
        <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12.5, color: "var(--text-secondary)", cursor: "pointer" }}>
          <input type="checkbox" checked={showRsi} onChange={(e) => setShowRsi(e.target.checked)} />
          RSI <InfoTip text={t("help.rsi")} />
        </label>
        <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12.5, color: "var(--text-secondary)", cursor: "pointer" }}>
          <input type="checkbox" checked={showMacd} onChange={(e) => setShowMacd(e.target.checked)} />
          MACD <InfoTip text={t("help.macd")} />
        </label>
      </div>

      {loading && <SkeletonChart />}
      {!loading && chartData.length > 0 && (
        <>
          {isMock && <p className="text-sub" style={{ marginBottom: 8 }}>{t("chart.mockNotice")}</p>}
          <ResponsiveContainer width="100%" height={260}>
            <AreaChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="priceChartFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="var(--cyan)" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="var(--cyan)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />
              <XAxis dataKey="t" stroke="var(--text-tertiary)" fontSize={10.5} tickLine={false} axisLine={false} minTickGap={30} />
              <YAxis stroke="var(--text-tertiary)" fontSize={10.5} tickLine={false} axisLine={false} width={84}
                domain={["auto", "auto"]} tickFormatter={(v) => formatAmount(v, priceAxisDecimals(chartData))} />
              <Tooltip
                contentStyle={{ background: "var(--bg-tooltip)", border: "1px solid var(--border-strong)", borderRadius: 10, fontSize: 12, color: "var(--text-primary)" }}
                formatter={(v, name) => [formatAmount(v, Math.min(8, Math.max(2, priceAxisDecimals(chartData) + 1))), name === "sma" ? t("chart.smaLabel") : t("chart.priceLabel")]}
              />
              <Area type="monotone" dataKey="price" stroke="var(--cyan)" strokeWidth={2} fill="url(#priceChartFill)" dot={false} />
              {showSma && <Line type="monotone" dataKey="sma" stroke="var(--violet)" strokeWidth={1.5} dot={false} strokeDasharray="4 3" />}
              <Brush dataKey="t" height={COARSE_POINTER ? 34 : 22} stroke="var(--cyan)" fill="var(--bg-inset)" travellerWidth={COARSE_POINTER ? 16 : 8} />
            </AreaChart>
          </ResponsiveContainer>
          {showRsi && (
            <div className="indicator-panel" role="img" aria-label={t("chart.rsiLabel")}>
              <span className="indicator-title">RSI (14)</span>
              <ResponsiveContainer width="100%" height={110}>
                <ComposedChart data={chartData} margin={{ top: 4, right: 10, left: 0, bottom: 0 }}>
                  <CartesianGrid stroke="rgba(128,128,128,0.12)" vertical={false} />
                  <XAxis dataKey="t" hide />
                  <YAxis domain={[0, 100]} ticks={[30, 70]} width={84} fontSize={10.5} stroke="var(--text-tertiary)" tickLine={false} axisLine={false} />
                  <ReferenceLine y={70} stroke="var(--crimson)" strokeDasharray="4 3" />
                  <ReferenceLine y={30} stroke="var(--emerald)" strokeDasharray="4 3" />
                  <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v) => [Number(v).toFixed(1), "RSI"]} />
                  <Line type="monotone" dataKey="rsi" stroke="var(--violet)" strokeWidth={1.6} dot={false} connectNulls />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          )}
          {showMacd && (
            <div className="indicator-panel" role="img" aria-label={t("chart.macdLabel")}>
              <span className="indicator-title">MACD (12, 26, 9)</span>
              <ResponsiveContainer width="100%" height={120}>
                <ComposedChart data={chartData} margin={{ top: 4, right: 10, left: 0, bottom: 0 }}>
                  <CartesianGrid stroke="rgba(128,128,128,0.12)" vertical={false} />
                  <XAxis dataKey="t" hide />
                  <YAxis width={84} fontSize={10.5} stroke="var(--text-tertiary)" tickLine={false} axisLine={false} tickFormatter={(v) => Number(v).toPrecision(3)} />
                  <ReferenceLine y={0} stroke="var(--border-strong)" />
                  <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v, name) => [Number(v).toPrecision(4), name]} />
                  <Bar dataKey="hist" name={t("chart.macdHist")} fill="var(--amber)" opacity={0.55} />
                  <Line type="monotone" dataKey="macd" name="MACD" stroke="var(--cyan)" strokeWidth={1.6} dot={false} connectNulls />
                  <Line type="monotone" dataKey="signal" name={t("chart.macdSignal")} stroke="var(--violet)" strokeWidth={1.4} dot={false} connectNulls strokeDasharray="4 3" />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          )}
          <p className="text-sub" style={{ marginTop: 6, marginBottom: 0 }}>
            {t("chart.zoomHint")}
          </p>
        </>
      )}
      {!loading && chartData.length === 0 && <p className="text-sub">{t("chart.loadError")}</p>}
    </Card>
  );
}
