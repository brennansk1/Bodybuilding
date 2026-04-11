"use client";

/**
 * Multi-series line chart showing e1RM progression for the big compound lifts
 * (squat, bench, deadlift, OHP). Each lift gets its own color line.
 */

interface SeriesPoint {
  date: string;   // ISO
  e1rm_kg: number;
}

interface Series {
  lift: string;       // "squat" | "bench" | "deadlift" | "ohp"
  label: string;
  color: string;
  data: SeriesPoint[];
}

interface Props {
  series: Series[];
  height?: number;
  useLbs?: boolean;
}

export default function StrengthProgressionChart({ series, height = 160, useLbs = false }: Props) {
  const valid = series.filter((s) => s.data.length >= 2);
  if (valid.length === 0) {
    return (
      <div
        className="flex items-center justify-center text-jungle-dim text-xs border border-dashed border-jungle-border rounded-lg"
        style={{ height }}
      >
        Log at least 2 sets of a main lift to populate
      </div>
    );
  }

  const vW = 280;
  const vH = height;
  const pad = { top: 10, right: 8, bottom: 22, left: 34 };
  const plotW = vW - pad.left - pad.right;
  const plotH = vH - pad.top - pad.bottom;

  const conv = (kg: number) => (useLbs ? kg * 2.20462 : kg);

  const allValues = valid.flatMap((s) => s.data.map((d) => conv(d.e1rm_kg)));
  const allDates = Array.from(new Set(valid.flatMap((s) => s.data.map((d) => d.date)))).sort();
  const minVal = Math.floor(Math.min(...allValues) * 0.92);
  const maxVal = Math.ceil(Math.max(...allValues) * 1.06);
  const range = maxVal - minVal || 1;

  const dateIdx = (d: string) => allDates.indexOf(d);
  const xPos = (d: string) => pad.left + (dateIdx(d) / Math.max(1, allDates.length - 1)) * plotW;
  const yPos = (v: number) => pad.top + plotH - ((v - minVal) / range) * plotH;

  return (
    <div>
      <svg viewBox={`0 0 ${vW} ${vH}`} width="100%" height={height}>
        {/* Grid */}
        {[0, 0.5, 1].map((t) => {
          const y = pad.top + plotH * (1 - t);
          return (
            <line key={t} x1={pad.left} y1={y} x2={vW - pad.right} y2={y} stroke="#1a3328" strokeWidth="0.75" />
          );
        })}
        {/* Y labels */}
        {[minVal, Math.round((minVal + maxVal) / 2), maxVal].map((v, i) => (
          <text key={i} x={pad.left - 4} y={yPos(v)} textAnchor="end" dominantBaseline="middle" fill="#5a7a62" fontSize="7.5">
            {Math.round(v)}
          </text>
        ))}
        {/* Lines */}
        {valid.map((s) => {
          const path = s.data
            .slice()
            .sort((a, b) => a.date.localeCompare(b.date))
            .map((d, i) => `${i === 0 ? "M" : "L"} ${xPos(d.date).toFixed(1)} ${yPos(conv(d.e1rm_kg)).toFixed(1)}`)
            .join(" ");
          return (
            <g key={s.lift}>
              <path d={path} fill="none" stroke={s.color} strokeWidth="1.75" strokeLinejoin="round" strokeLinecap="round" />
              {s.data.map((d, i) => (
                <circle key={i} cx={xPos(d.date)} cy={yPos(conv(d.e1rm_kg))} r="2" fill={s.color} />
              ))}
            </g>
          );
        })}
        {/* X labels — first and last only */}
        {allDates.length > 0 && (
          <>
            <text x={pad.left} y={vH - 6} fill="#5a7a62" fontSize="7">
              {allDates[0].slice(5)}
            </text>
            <text x={vW - pad.right} y={vH - 6} textAnchor="end" fill="#5a7a62" fontSize="7">
              {allDates[allDates.length - 1].slice(5)}
            </text>
          </>
        )}
      </svg>
      <div className="flex flex-wrap gap-3 mt-2 text-[10px]">
        {valid.map((s) => (
          <div key={s.lift} className="flex items-center gap-1">
            <span className="inline-block w-2.5 h-2.5 rounded-sm" style={{ backgroundColor: s.color }} />
            <span className="text-jungle-muted">{s.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
