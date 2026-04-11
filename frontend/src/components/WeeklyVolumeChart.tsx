"use client";

/**
 * Weekly volume per muscle group with MEV/MAV/MRV landmark markers.
 * Horizontal bar per muscle; colored by zone (below MEV, between MEV-MAV,
 * MAV-MRV, or above MRV). Landmark lines are drawn through the bars.
 */

interface VolumeRow {
  muscle: string;
  sets: number;
  mev: number;
  mav: number;
  mrv: number;
}

interface Props {
  rows: VolumeRow[];
}

function zoneColor(sets: number, mev: number, mav: number, mrv: number): string {
  if (sets < mev) return "#ef4444";        // under MEV — not enough
  if (sets >= mev && sets < mav) return "#c8a84e"; // in growth range
  if (sets >= mav && sets <= mrv) return "#22c55e"; // high productive
  return "#f97316";                         // over MRV — recovery risk
}

export default function WeeklyVolumeChart({ rows }: Props) {
  if (!rows || rows.length === 0) {
    return (
      <div className="flex items-center justify-center text-jungle-dim text-xs border border-dashed border-jungle-border rounded-lg py-8">
        Complete this week&apos;s sessions to populate
      </div>
    );
  }

  const maxMrv = Math.max(...rows.map((r) => r.mrv), 24);

  return (
    <div className="mt-2 space-y-2">
      {rows.map((r) => {
        const widthPct = Math.min(100, (r.sets / maxMrv) * 100);
        const mevPct = (r.mev / maxMrv) * 100;
        const mavPct = (r.mav / maxMrv) * 100;
        const mrvPct = (r.mrv / maxMrv) * 100;
        const color = zoneColor(r.sets, r.mev, r.mav, r.mrv);
        return (
          <div key={r.muscle}>
            <div className="flex items-center justify-between text-[11px] mb-0.5">
              <span className="capitalize text-jungle-muted">{r.muscle.replace(/_/g, " ")}</span>
              <span className="font-mono text-jungle-text">
                {r.sets} <span className="text-jungle-dim">/ MAV {r.mav}</span>
              </span>
            </div>
            <div className="relative h-3 bg-jungle-deeper rounded-full overflow-hidden">
              {/* Filled bar */}
              <div
                className="h-full rounded-full transition-all"
                style={{ width: `${widthPct}%`, backgroundColor: color }}
              />
              {/* Landmark markers */}
              <div
                className="absolute top-0 bottom-0 w-px bg-yellow-400/70"
                style={{ left: `${mevPct}%` }}
                title={`MEV ${r.mev}`}
              />
              <div
                className="absolute top-0 bottom-0 w-px bg-green-400/70"
                style={{ left: `${mavPct}%` }}
                title={`MAV ${r.mav}`}
              />
              <div
                className="absolute top-0 bottom-0 w-px bg-red-400/70"
                style={{ left: `${mrvPct}%` }}
                title={`MRV ${r.mrv}`}
              />
            </div>
          </div>
        );
      })}
      <div className="flex items-center gap-3 pt-2 text-[9px] text-jungle-dim">
        <div className="flex items-center gap-1">
          <span className="w-2 h-2 bg-yellow-400/70 inline-block" /> MEV
        </div>
        <div className="flex items-center gap-1">
          <span className="w-2 h-2 bg-green-400/70 inline-block" /> MAV
        </div>
        <div className="flex items-center gap-1">
          <span className="w-2 h-2 bg-red-400/70 inline-block" /> MRV
        </div>
      </div>
    </div>
  );
}
