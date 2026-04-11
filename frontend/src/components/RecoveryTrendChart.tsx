"use client";

/**
 * Recovery trend — daily composite ARI score over the last 30 days
 * with red/yellow/green zone bands.
 */

interface RecoveryPoint {
  date: string;
  score: number; // 0-100
}

interface Props {
  data: RecoveryPoint[];
  height?: number;
}

export default function RecoveryTrendChart({ data, height = 150 }: Props) {
  const sorted = [...data].sort((a, b) => a.date.localeCompare(b.date)).slice(-30);
  if (sorted.length < 2) {
    return (
      <div
        className="flex items-center justify-center text-jungle-dim text-xs border border-dashed border-jungle-border rounded-lg"
        style={{ height }}
      >
        Log HRV + sleep + soreness daily to populate
      </div>
    );
  }

  const vW = 280;
  const vH = height;
  const pad = { top: 10, right: 8, bottom: 22, left: 30 };
  const plotW = vW - pad.left - pad.right;
  const plotH = vH - pad.top - pad.bottom;

  const yPos = (v: number) => pad.top + plotH - (v / 100) * plotH;
  const xPos = (i: number) => pad.left + (i / Math.max(1, sorted.length - 1)) * plotW;

  const linePath = sorted
    .map((d, i) => `${i === 0 ? "M" : "L"} ${xPos(i).toFixed(1)} ${yPos(d.score).toFixed(1)}`)
    .join(" ");

  // Zone bands: red 0-40, yellow 40-70, green 70-100.
  const redTop = yPos(40);
  const yellowTop = yPos(70);
  const greenTop = yPos(100);

  return (
    <div>
      <svg viewBox={`0 0 ${vW} ${vH}`} width="100%" height={height}>
        {/* Red band */}
        <rect x={pad.left} y={redTop} width={plotW} height={pad.top + plotH - redTop} fill="#ef44441a" />
        {/* Yellow band */}
        <rect x={pad.left} y={yellowTop} width={plotW} height={redTop - yellowTop} fill="#eab3081a" />
        {/* Green band */}
        <rect x={pad.left} y={greenTop} width={plotW} height={yellowTop - greenTop} fill="#22c55e1a" />

        {/* Y labels */}
        {[0, 40, 70, 100].map((v) => (
          <text key={v} x={pad.left - 4} y={yPos(v)} textAnchor="end" dominantBaseline="middle" fill="#5a7a62" fontSize="7.5">
            {v}
          </text>
        ))}

        {/* Line */}
        <path d={linePath} fill="none" stroke="#c8a84e" strokeWidth="1.75" strokeLinejoin="round" strokeLinecap="round" />
        {sorted.map((d, i) => (
          <circle key={i} cx={xPos(i)} cy={yPos(d.score)} r="1.5" fill="#c8a84e" />
        ))}

        {/* X labels */}
        <text x={pad.left} y={vH - 6} fill="#5a7a62" fontSize="7">
          {sorted[0].date.slice(5)}
        </text>
        <text x={vW - pad.right} y={vH - 6} textAnchor="end" fill="#5a7a62" fontSize="7">
          {sorted[sorted.length - 1].date.slice(5)}
        </text>
      </svg>
      <div className="flex items-center gap-3 mt-2 text-[10px] text-jungle-dim">
        <span className="inline-flex items-center gap-1"><span className="w-2 h-2 bg-red-500/40 inline-block rounded-sm" />under-recovered</span>
        <span className="inline-flex items-center gap-1"><span className="w-2 h-2 bg-yellow-500/40 inline-block rounded-sm" />caution</span>
        <span className="inline-flex items-center gap-1"><span className="w-2 h-2 bg-green-500/40 inline-block rounded-sm" />ready</span>
      </div>
    </div>
  );
}
