export function SkeletonLines({ count = 3 }) {
  return (
    <div>
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="skeleton skeleton-line" style={{ width: `${92 - i * 14}%` }} />
      ))}
    </div>
  );
}

export function SkeletonChart() {
  return <div className="skeleton skeleton-chart" />;
}
