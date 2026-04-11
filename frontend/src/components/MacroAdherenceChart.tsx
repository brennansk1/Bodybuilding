"use client";

/**
 * 30-day macro adherence chart — a bar per day, height = average
 * protein/carbs/fat hit rate. Reuses the existing AdherenceEntry shape.
 */

interface AdherenceEntry {
  date: string;
  nutrition: number; // 0-100
  training?: number;
  overall?: number;
}

interface Props {
  data: AdherenceEntry[];
  height?: number;
}

export default function MacroAdherenceChart({ data, height = 140 }: Props) {
  const last30 = [...data].sort((a, b) => a.date.localeCompare(b.date)).slice(-30);
  if (last30.length === 0) {
    return (
      <div
        className="flex items-center justify-center text-jungle-dim text-xs border border-dashed border-jungle-border rounded-lg"
        style={{ height }}
      >
        Log meals to see adherence trend
      </div>
    );
  }

  const vW = 280;
  const vH = height;
  const pad = { top: 10, right: 8, bottom: 22, left: 28 };
  const plotW = vW - pad.left - pad.right;
  const plotH = vH - pad.top - pad.bottom;
  const barW = plotW / Math.max(1, last30.length);

  const colorFor = (pct: number) => {
    if (pct >= 90) return "#22c55e";
    if (pct >= 75) return "#c8a84e";
    if (pct >= 50) return "#f97316";
    return "#ef4444";
  };

  const average = last30.reduce((a, e) => a + e.nutrition, 0) / last30.length;

  return (
    <div>
      <svg viewBox={`0 0 ${vW} ${vH}`} width="100%" height={height}>
        {/* 100% line */}
        <line
          x1={pad.left}
          y1={pad.top}
          x2={vW - pad.right}
          y2={pad.top}
          stroke="#c8a84e55"
          strokeWidth="0.75"
          strokeDasharray="2 2"
        />
        {/* Average line */}
        <line
          x1={pad.left}
          y1={pad.top + plotH * (1 - average / 100)}
          x2={vW - pad.right}
          y2={pad.top + plotH * (1 - average / 100)}
          stroke="#c8a84e"
          strokeWidth="0.75"
        />
        {/* Y labels */}
        {[0, 50, 100].map((v, i) => (
          <text
            key={i}
            x={pad.left - 4}
            y={pad.top + plotH * (1 - v / 100)}
            textAnchor="end"
            dominantBaseline="middle"
            fill="#5a7a62"
            fontSize="7.5"
          >
            {v}%
          </text>
        ))}
        {/* Bars */}
        {last30.map((e, i) => {
          const h = plotH * (e.nutrition / 100);
          const x = pad.left + i * barW;
          const y = pad.top + plotH - h;
          return (
            <rect
              key={i}
              x={x + 0.5}
              y={y}
              width={Math.max(1, barW - 1)}
              height={h}
              fill={colorFor(e.nutrition)}
              rx="1"
            />
          );
        })}
        {/* X labels */}
        <text x={pad.left} y={vH - 6} fill="#5a7a62" fontSize="7">
          {last30[0].date.slice(5)}
        </text>
        <text x={vW - pad.right} y={vH - 6} textAnchor="end" fill="#5a7a62" fontSize="7">
          {last30[last30.length - 1].date.slice(5)}
        </text>
      </svg>
      <div className="flex items-center justify-between mt-2 text-[10px]">
        <span className="text-jungle-muted">
          30-day average: <span className="text-jungle-accent font-bold">{average.toFixed(0)}%</span>
        </span>
        <span className="text-jungle-dim">green ≥90 · gold ≥75 · orange ≥50 · red &lt;50</span>
      </div>
    </div>
  );
}
