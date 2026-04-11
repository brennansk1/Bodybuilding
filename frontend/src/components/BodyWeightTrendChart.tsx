"use client";

/**
 * Body weight trend with 7-day rolling average overlay.
 * Raw daily dots + a smoothed trend line. Data comes from /checkin/weight-history.
 */

interface WeightEntry {
  date: string;
  weight_kg: number;
}

interface Props {
  data: WeightEntry[];
  height?: number;
  useLbs?: boolean;
  phase?: string | null;
}

function rolling(values: number[], window = 7): number[] {
  const out: number[] = [];
  for (let i = 0; i < values.length; i++) {
    const start = Math.max(0, i - window + 1);
    const slice = values.slice(start, i + 1);
    const avg = slice.reduce((a, b) => a + b, 0) / slice.length;
    out.push(avg);
  }
  return out;
}

const PHASE_BAND: Record<string, string> = {
  bulk: "#22c55e1a",
  lean_bulk: "#84cc161a",
  cut: "#ef44441a",
  peak: "#f973161a",
  maintain: "#c8a84e1a",
  restoration: "#3b82f61a",
};

export default function BodyWeightTrendChart({ data, height = 150, useLbs = false, phase }: Props) {
  if (!data || data.length < 2) {
    return (
      <div
        className="flex items-center justify-center text-jungle-dim text-xs border border-dashed border-jungle-border rounded-lg"
        style={{ height }}
      >
        Log weight daily to populate
      </div>
    );
  }

  const sorted = [...data].sort((a, b) => a.date.localeCompare(b.date));
  const conv = (kg: number) => (useLbs ? kg * 2.20462 : kg);
  const weights = sorted.map((d) => conv(d.weight_kg));
  const smoothed = rolling(weights, 7);

  const vW = 280;
  const vH = height;
  const pad = { top: 10, right: 8, bottom: 22, left: 32 };
  const plotW = vW - pad.left - pad.right;
  const plotH = vH - pad.top - pad.bottom;

  const all = [...weights, ...smoothed];
  const minVal = Math.floor(Math.min(...all) - 0.5);
  const maxVal = Math.ceil(Math.max(...all) + 0.5);
  const range = maxVal - minVal || 1;

  const xPos = (i: number) => pad.left + (i / Math.max(1, sorted.length - 1)) * plotW;
  const yPos = (v: number) => pad.top + plotH - ((v - minVal) / range) * plotH;

  const smoothPath = smoothed.map((v, i) => `${i === 0 ? "M" : "L"} ${xPos(i).toFixed(1)} ${yPos(v).toFixed(1)}`).join(" ");

  const bandColor = phase ? PHASE_BAND[phase] || "#ffffff0a" : "#ffffff0a";

  return (
    <div>
      <svg viewBox={`0 0 ${vW} ${vH}`} width="100%" height={height}>
        {/* Phase band */}
        <rect x={pad.left} y={pad.top} width={plotW} height={plotH} fill={bandColor} />
        {/* Grid */}
        {[0, 0.5, 1].map((t) => {
          const y = pad.top + plotH * (1 - t);
          return <line key={t} x1={pad.left} y1={y} x2={vW - pad.right} y2={y} stroke="#1a3328" strokeWidth="0.75" />;
        })}
        {/* Y labels */}
        {[minVal, (minVal + maxVal) / 2, maxVal].map((v, i) => (
          <text key={i} x={pad.left - 4} y={yPos(v)} textAnchor="end" dominantBaseline="middle" fill="#5a7a62" fontSize="7.5">
            {v.toFixed(1)}
          </text>
        ))}
        {/* Raw dots */}
        {weights.map((w, i) => (
          <circle key={i} cx={xPos(i)} cy={yPos(w)} r="1.6" fill="#5a7a62" />
        ))}
        {/* Smoothed line */}
        <path d={smoothPath} fill="none" stroke="#c8a84e" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
        {/* X labels */}
        <text x={pad.left} y={vH - 6} fill="#5a7a62" fontSize="7">
          {sorted[0].date.slice(5)}
        </text>
        <text x={vW - pad.right} y={vH - 6} textAnchor="end" fill="#5a7a62" fontSize="7">
          {sorted[sorted.length - 1].date.slice(5)}
        </text>
      </svg>
      <div className="flex items-center gap-3 mt-2 text-[10px]">
        <div className="flex items-center gap-1">
          <span className="inline-block w-2.5 h-1 bg-jungle-accent" />
          <span className="text-jungle-muted">7-day avg</span>
        </div>
        <div className="flex items-center gap-1">
          <span className="inline-block w-2 h-2 rounded-full bg-jungle-dim" />
          <span className="text-jungle-muted">Daily</span>
        </div>
        {phase && <span className="text-jungle-dim capitalize">· {phase.replace(/_/g, " ")} phase</span>}
      </div>
    </div>
  );
}
