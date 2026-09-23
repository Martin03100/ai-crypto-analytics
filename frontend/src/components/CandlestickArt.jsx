/** Cisto dekorativny, animovany "candlestick" graf pre branding panel na
 * prihlasovacej stranke. Ziadne realne data - len vizualny motiv, ktory
 * evokuje trading terminal. SVG (nie obrazok), takze funguje offline a bez
 * externych zavislosti. */
const CANDLES = [
  { x: 10, open: 60, close: 40, high: 68, low: 34 },
  { x: 34, open: 40, close: 52, high: 56, low: 36 },
  { x: 58, open: 52, close: 30, high: 58, low: 26 },
  { x: 82, open: 30, close: 44, high: 48, low: 24 },
  { x: 106, open: 44, close: 20, high: 50, low: 16 },
  { x: 130, open: 20, close: 34, high: 40, low: 14 },
  { x: 154, open: 34, close: 12, high: 38, low: 8 },
  { x: 178, open: 12, close: 26, high: 32, low: 6 },
  { x: 202, open: 26, close: 8, high: 30, low: 4 },
  { x: 226, open: 8, close: 22, high: 26, low: 2 },
];

export default function CandlestickArt() {
  return (
    <svg viewBox="0 0 260 90" className="candle-art" aria-hidden="true" preserveAspectRatio="none">
      <defs>
        <linearGradient id="candleLine" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor="#22d3ee" />
          <stop offset="50%" stopColor="#a78bfa" />
          <stop offset="100%" stopColor="#34d399" />
        </linearGradient>
      </defs>
      {/* trend line spajajuca close hodnoty */}
      <polyline
        className="candle-trendline"
        fill="none"
        stroke="url(#candleLine)"
        strokeWidth="1.4"
        strokeLinecap="round"
        points={CANDLES.map((c) => `${c.x},${90 - c.close}`).join(" ")}
      />
      {CANDLES.map((c, i) => {
        const bullish = c.close < c.open; // v SVG suradniciach mensie y = vyssie = rast
        const color = bullish ? "#34d399" : "#fb5a6a";
        const top = 90 - Math.max(c.open, c.close);
        const height = Math.max(2, Math.abs(c.open - c.close));
        return (
          <g key={i} className="candle" style={{ animationDelay: `${i * 0.12}s` }}>
            <line x1={c.x + 8} x2={c.x + 8} y1={90 - c.high} y2={90 - c.low} stroke={color} strokeWidth="1" opacity="0.55" />
            <rect x={c.x} y={top} width="16" height={height} rx="2" fill={color} opacity="0.85" />
          </g>
        );
      })}
    </svg>
  );
}
