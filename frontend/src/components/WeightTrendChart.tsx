"use client";

// Weight trend chart with rolling average and optional glide path
// Pure SVG — no external dependencies

interface WeightPoint {
  date: string;
  weight_kg: number;
  rolling_avg?: number;
}

interface WeightTrendChartProps {
  data: WeightPoint[];
  height?: number;
  targetWeight?: number; // glide path target (if in prep)
  useLbs?: boolean;
}

export default function WeightTrendChart({
  data,
  height = 160,
  targetWeight,
  useLbs = false,
}: WeightTrendChartProps) {
  if (!data || data.length < 2) {
    return (
      <div
        className="flex items-center justify-center text-jungle-dim text-xs border border-dashed border-jungle-border rounded-lg"
        style={{ height }}
      >
        Not enough data
      </div>
    );
  }

  const m = useLbs ? 2.20462 : 1;
  const unit = useLbs ? "lbs" : "kg";

  const vW = 300;
  const vH = height;
  const pad = { top: 12, right: 8, bottom: 24, left: 36 };
  const plotW = vW - pad.left - pad.right;
  const plotH = vH - pad.top - pad.bottom;

  const weights = data.map((d) => d.weight_kg * m);
  const rollingAvgs = data.map((d) => (d.rolling_avg ?? d.weight_kg) * m);
  const allValues = [...weights, ...rollingAvgs];
  if (targetWeight) allValues.push(targetWeight * m);

  const minVal = Math.floor(Math.min(...allValues) - 1);
  const maxVal = Math.ceil(Math.max(...allValues) + 1);
  const range = maxVal - minVal || 1;

  const xPos = (i: number) => pad.left + (i / (data.length - 1)) * plotW;
  const yPos = (v: number) => pad.top + plotH - ((v - minVal) / range) * plotH;

  // Daily weight dots path
  const dotPoints = data.map((d, i) => ({
    x: xPos(i),
    y: yPos(d.weight_kg * m),
    value: d.weight_kg * m,
  }));

  // Rolling average line
  const avgPath = data
    .filter((d) => d.rolling_avg != null)
    .map((d, i) => {
      const origIdx = data.indexOf(d);
      return `${i === 0 ? "M" : "L"} ${xPos(origIdx).toFixed(1)} ${yPos((d.rolling_avg!) * m).toFixed(1)}`;
    })
    .join(" ");

  // Y-axis labels
  const yTicks = 4;
  const yLabels: number[] = [];
  for (let i = 0; i <= yTicks; i++) {
    yLabels.push(Math.round(minVal + (range * i) / yTicks));
  }

  // X-axis labels (show ~5)
  const maxLabels = Math.min(5, data.length);
  const labelStep = Math.ceil(data.length / maxLabels);
  const showLabel = (i: number) =>
    i === 0 || i === data.length - 1 || i % labelStep === 0;

  const formatDate = (d: string) => {
    const date = new Date(d + "T00:00:00");
    return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  };

  // Latest values
  const latest = data[data.length - 1];
  const latestWeight = (latest.weight_kg * m).toFixed(1);
  const latestAvg = latest.rolling_avg
    ? (latest.rolling_avg * m).toFixed(1)
    : null;

  return (
    <div>
      {/* Legend bar */}
      <div className="flex items-center gap-4 mb-2 text-[10px]">
        <span className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-jungle-muted inline-block" />
          <span className="text-jungle-dim">Daily</span>
          <span className="text-jungle-muted font-semibold">{latestWeight} {unit}</span>
        </span>
        {latestAvg && (
          <span className="flex items-center gap-1.5">
            <span className="w-4 h-0.5 bg-jungle-accent inline-block rounded" />
            <span className="text-jungle-dim">7d avg</span>
            <span className="text-jungle-accent font-semibold">{latestAvg} {unit}</span>
          </span>
        )}
        {targetWeight && (
          <span className="flex items-center gap-1.5">
            <span className="w-4 h-0.5 bg-red-400/60 inline-block rounded border-t border-dashed border-red-400" />
            <span className="text-jungle-dim">Target</span>
            <span className="text-red-400 font-semibold">{(targetWeight * m).toFixed(1)} {unit}</span>
          </span>
        )}
      </div>

      <svg viewBox={`0 0 ${vW} ${vH}`} width="100%" height={height}>
        {/* Grid lines */}
        {yLabels.map((val) => {
          const y = yPos(val);
          return (
            <g key={val}>
              <line x1={pad.left} y1={y} x2={vW - pad.right} y2={y} stroke="#1a3328" strokeWidth="0.5" />
              <text x={pad.left - 4} y={y} textAnchor="end" dominantBaseline="middle" fill="#5a7a62" fontSize="7">
                {val.toFixed(0)}
              </text>
            </g>
          );
        })}

        {/* Target weight line (dashed) */}
        {targetWeight && (
          <line
            x1={pad.left}
            y1={yPos(targetWeight * m)}
            x2={vW - pad.right}
            y2={yPos(targetWeight * m)}
            stroke="#f87171"
            strokeWidth="0.75"
            strokeDasharray="4 3"
            opacity="0.6"
          />
        )}

        {/* Daily weight dots */}
        {dotPoints.map((pt, i) => (
          <circle key={i} cx={pt.x} cy={pt.y} r="2" fill="#8faa96" opacity="0.5" />
        ))}

        {/* Rolling average line */}
        {avgPath && (
          <path d={avgPath} fill="none" stroke="#c8a84e" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
        )}

        {/* X-axis labels */}
        {data.map((d, i) =>
          showLabel(i) ? (
            <text key={i} x={xPos(i)} y={vH - 4} textAnchor="middle" fill="#5a7a62" fontSize="6.5">
              {formatDate(d.date)}
            </text>
          ) : null
        )}
      </svg>
    </div>
  );
}
