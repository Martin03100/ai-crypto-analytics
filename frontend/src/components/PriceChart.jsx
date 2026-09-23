import { LineChart } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Area, AreaChart, Brush, CartesianGrid, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
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
    return raw.map(([ts, price], i) => ({
      t: new Date(ts).toLocaleDateString(localeForLang(lang), timeframe === "1" ? { hour: "2-digit", minute: "2-digit" } : { day: "2-digit", month: "2-digit" }),
      price,
      sma: showSma ? smaValues[i] : undefined,
    }));
  }, [raw, showSma, timeframe, lang]);

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
          {t("chart.smaIndicator")}
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
              <YAxis stroke="var(--text-tertiary)" fontSize={10.5} tickLine={false} axisLine={false} width={70}
                domain={["auto", "auto"]} tickFormatter={(v) => formatAmount(v)} />
              <Tooltip
                contentStyle={{ background: "#121824", border: "1px solid rgba(255,255,255,0.12)", borderRadius: 10, fontSize: 12 }}
                formatter={(v, name) => [formatAmount(v), name === "sma" ? t("chart.smaLabel") : t("chart.priceLabel")]}
              />
              <Area type="monotone" dataKey="price" stroke="var(--cyan)" strokeWidth={2} fill="url(#priceChartFill)" dot={false} />
              {showSma && <Line type="monotone" dataKey="sma" stroke="var(--violet)" strokeWidth={1.5} dot={false} strokeDasharray="4 3" />}
              <Brush dataKey="t" height={22} stroke="var(--cyan)" fill="var(--bg-inset)" travellerWidth={8} />
            </AreaChart>
          </ResponsiveContainer>
          <p className="text-sub" style={{ marginTop: 6, marginBottom: 0 }}>
            {t("chart.zoomHint")}
          </p>
        </>
      )}
      {!loading && chartData.length === 0 && <p className="text-sub">{t("chart.loadError")}</p>}
    </Card>
  );
}
