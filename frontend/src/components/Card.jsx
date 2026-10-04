/** Card component. */

export function Card({ title, icon: Icon, glow, children, style, id, className = "" }) {
  return (
    <div id={id} className={`card ${glow ? `glow-${glow}` : ""} ${className}`.trim()} style={style}>
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
