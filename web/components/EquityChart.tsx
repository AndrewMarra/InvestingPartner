// Equity curve as a clean SVG sparkline (no chart lib needed).
export function EquityChart({ values }: { values: number[] }) {
  if (values.length < 2) {
    return <div className="note">Your equity curve appears here once the buddy has a few days of history.</div>;
  }
  const w = 680, h = 160, pad = 4;
  const min = Math.min(...values) * 0.999;
  const max = Math.max(...values) * 1.001;
  const x = (i: number) => (i / (values.length - 1)) * (w - pad * 2) + pad;
  const y = (v: number) => h - ((v - min) / (max - min || 1)) * (h - pad * 2) - pad;
  const line = values.map((v, i) => `${x(i)},${y(v)}`).join(" ");
  const up = values[values.length - 1] >= values[0];
  const color = up ? "var(--gain)" : "var(--loss)";
  return (
    <svg viewBox={`0 0 ${w} ${h}`} width="100%" height={h} preserveAspectRatio="none"
      role="img" aria-label="Equity over time">
      <defs>
        <linearGradient id="eq" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.22" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <polygon points={`${pad},${h} ${line} ${w - pad},${h}`} fill="url(#eq)" />
      <polyline points={line} fill="none" stroke={color} strokeWidth="2" />
    </svg>
  );
}
