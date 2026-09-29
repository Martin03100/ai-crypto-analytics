/** Forecast price chart with optional uncertainty band and actual prices. */

import {
  Area, CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { axisDecimals, buildTimePoints, formatPrice, formatTimeFull, formatTimeShort, formatUsd } from "../utils/formatPrice";

export function hasForecastSeries(data) {
  return Array.isArray(data?.ceny) && data.ceny.length > 0 && data.ceny.every((p) => Number.isFinite(p));
}

export default function ForecastChart({ data, t, actualPrices, createdAt, horizon, locale }) {
  const n = data.ceny.length;
  const labels = Array.isArray(data.casove_body) ? data.casove_body : [];
  const band = data.pasmo && Array.isArray(data.pasmo.dolne) && Array.isArray(data.pasmo.horne)
    && data.pasmo.dolne.length === n && data.pasmo.horne.length === n ? data.pasmo : null;
  const hasActual = Array.isArray(actualPrices) && actualPrices.length === n;
  const points = buildTimePoints(data.vytvorene || createdAt, horizon, n);
  const startPrice = points && typeof data.aktualna_cena === "number" ? data.aktualna_cena : null;
  const shortLabel = (i) => (points ? formatTimeShort(points[i], horizon, locale) : String(labels[i - 1] ?? i));
  const fullLabel = (i) => (points ? formatTimeFull(points[i], locale) : String(labels[i - 1] ?? i));

  const chartData = [];
  if (startPrice !== null) {
    chartData.push({ t: shortLabel(0), full: `${fullLabel(0)} · ${t("forecast.startPoint")}`, price: startPrice, band: band ? [startPrice, startPrice] : undefined, actual: hasActual ? startPrice : undefined });
  }
  data.ceny.forEach((price, idx) => {
    chartData.push({ t: shortLabel(idx + 1), full: fullLabel(idx + 1), price, band: band ? [band.dolne[idx], band.horne[idx]] : undefined, actual: hasActual ? actualPrices[idx] : undefined });
  });

  const values = chartData.flatMap((p) => [p.price, p.actual, ...(p.band || [])]).filter((v) => Number.isFinite(v));
  const minPrice = Math.min(...values);
  const maxPrice = Math.max(...values);
  const padding = (maxPrice - minPrice) * 0.05 || maxPrice * 0.05 || 1;
  const yDomain = [Math.max(0, minPrice - padding), maxPrice + padding];
  const decimals = axisDecimals(yDomain[0], yDomain[1]);

  const first = chartData[0];
  const last = chartData[chartData.length - 1];
  const summary = t("forecast.chartSummary", { from: formatPrice(first.price), to: formatPrice(last.price), start: first.full, end: last.full });

  return (
    <>
    <div role="img" aria-label={summary}>
    <ResponsiveContainer width="100%" height={280}>
      <ComposedChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="priceFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--cyan)" stopOpacity={0.35} />
            <stop offset="100%" stopColor="var(--cyan)" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />
        <XAxis dataKey="t" stroke="var(--text-tertiary)" fontSize={11} tickLine={false} axisLine={false} minTickGap={16} />
        <YAxis
          stroke="var(--text-tertiary)" fontSize={11} tickLine={false} axisLine={false} width={84}
          domain={yDomain} tickFormatter={(v) => formatUsd(v, decimals)}
        />
        <Tooltip
          contentStyle={{ background: "var(--bg-tooltip)", border: "1px solid var(--border-strong)", borderRadius: 10, fontSize: 12, color: "var(--text-primary)" }}
          labelStyle={{ color: "var(--text-secondary)" }}
          formatter={(v, name) => (name === "band" && Array.isArray(v)
            ? [`${formatPrice(v[0])} – ${formatPrice(v[1])}`, t("forecast.legendBand")]
            : [formatPrice(v), name === "price" ? t("forecast.legendPredicted") : name === "actual" ? t("forecast.legendActual") : name])}
          labelFormatter={(label, payload) => t("forecast.timeTooltip", { label: payload?.[0]?.payload?.full || label })}
        />
        {hasActual && <Legend formatter={(value) => (value === "price" ? t("forecast.legendPredicted") : value === "band" ? t("forecast.legendBand") : t("forecast.legendActual"))} wrapperStyle={{ fontSize: 12 }} />}
        {band && <Area type="monotone" dataKey="band" name="band" stroke="none" fill="var(--cyan)" fillOpacity={0.14} isAnimationActive={false} />}
        <Area type="monotone" dataKey="price" stroke="var(--cyan-fg)" strokeWidth={2.5} fill="url(#priceFill)" dot={{ r: 3, fill: "var(--cyan-fg)" }} />
        {hasActual && (
          <Line type="monotone" dataKey="actual" stroke="var(--amber-fg)" strokeWidth={2.5} strokeDasharray="6 3" dot={{ r: 3.5, fill: "var(--amber-fg)" }} />
        )}
      </ComposedChart>
    </ResponsiveContainer>
    </div>
    {band && <p className="text-sub" style={{ marginTop: 6 }}>{t("forecast.bandNote", { vol: data.denna_volatilita_pct ?? "—" })}</p>}
    </>
  );
}
