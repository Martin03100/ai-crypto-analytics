export function Card({ title, icon: Icon, glow, children, style, id }) {
  return (
    <div id={id} className={`card ${glow ? `glow-${glow}` : ""}`} style={style}>
      {title && (
        <p className="card-title">
          {Icon && <Icon size={15} />}
          {title}
        </p>
      )}
      {children}
    </div>
  );
}

export function Metric({ label, value, delta, direction }) {
  return (
    <div>
      <div className="metric-value mono">{value}</div>
      <div className="metric-label">{label}</div>
      {delta && (
        <div className={`metric-delta ${direction === "down" ? "down" : "up"}`}>{delta}</div>
      )}
    </div>
  );
}
