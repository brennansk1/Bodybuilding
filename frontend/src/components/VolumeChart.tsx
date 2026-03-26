"use client";

// Weekly volume per muscle group — horizontal bar chart
// Shows current week's sets with MEV/MRV reference context

interface VolumeData {
  muscle: string;
  sets: number;
  mev?: number; // Minimum Effective Volume
  mrv?: number; // Maximum Recoverable Volume
}

interface VolumeChartProps {
  data: VolumeData[];
  compact?: boolean;
}

const MUSCLE_COLORS: Record<string, string> = {
  chest: "#c8a84e",
  back: "#4ade80",
  shoulders: "#60a5fa",
  biceps: "#f472b6",
  triceps: "#a78bfa",
  quads: "#fb923c",
  hamstrings: "#fbbf24",
  glutes: "#f87171",
  calves: "#34d399",
  abs: "#818cf8",
  traps: "#2dd4bf",
  forearms: "#94a3b8",
};

function muscleLabel(muscle: string): string {
  return muscle.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export default function VolumeChart({ data, compact = false }: VolumeChartProps) {
  if (!data || data.length === 0) {
    return (
      <div className="flex items-center justify-center text-jungle-dim text-xs border border-dashed border-jungle-border rounded-lg py-8">
        No volume data
      </div>
    );
  }

  const maxSets = Math.max(...data.map((d) => Math.max(d.sets, d.mrv ?? 0)), 20);

  return (
    <div className="space-y-1.5">
      {data
        .sort((a, b) => b.sets - a.sets)
        .map((item) => {
          const pct = (item.sets / maxSets) * 100;
          const color = MUSCLE_COLORS[item.muscle] || "#8faa96";
          const inRange = item.mev && item.mrv
            ? item.sets >= item.mev && item.sets <= item.mrv
            : true;
          const overMrv = item.mrv ? item.sets > item.mrv : false;
          const underMev = item.mev ? item.sets < item.mev : false;

          return (
            <div key={item.muscle} className="flex items-center gap-2">
              <span className={`text-[10px] text-jungle-muted w-16 text-right shrink-0 ${compact ? "w-12" : "w-16"}`}>
                {compact ? item.muscle.slice(0, 5).toUpperCase() : muscleLabel(item.muscle)}
              </span>
              <div className="flex-1 h-5 bg-jungle-deeper rounded-sm relative overflow-hidden">
                {/* MRV marker */}
                {item.mrv && (
                  <div
                    className="absolute top-0 bottom-0 w-px bg-red-400/40"
                    style={{ left: `${(item.mrv / maxSets) * 100}%` }}
                  />
                )}
                {/* MEV marker */}
                {item.mev && (
                  <div
                    className="absolute top-0 bottom-0 w-px bg-green-400/40"
                    style={{ left: `${(item.mev / maxSets) * 100}%` }}
                  />
                )}
                {/* Volume bar */}
                <div
                  className="h-full rounded-sm transition-all duration-500"
                  style={{
                    width: `${Math.min(pct, 100)}%`,
                    backgroundColor: overMrv ? "#f87171" : underMev ? "#fbbf24" : color,
                    opacity: overMrv ? 0.8 : underMev ? 0.6 : 0.7,
                  }}
                />
              </div>
              <span className={`text-xs font-bold w-6 text-right shrink-0 ${
                overMrv ? "text-red-400" : underMev ? "text-yellow-400" : "text-jungle-muted"
              }`}>
                {item.sets}
              </span>
            </div>
          );
        })}

      {/* Legend */}
      {!compact && data.some((d) => d.mev || d.mrv) && (
        <div className="flex gap-3 mt-2 text-[9px] text-jungle-dim">
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 bg-green-400/40 inline-block" /> MEV
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 bg-red-400/40 inline-block" /> MRV
          </span>
          <span className="flex items-center gap-1">
            <span className="w-3 h-2 bg-yellow-400/60 inline-block rounded-sm" /> Under MEV
          </span>
          <span className="flex items-center gap-1">
            <span className="w-3 h-2 bg-red-400/80 inline-block rounded-sm" /> Over MRV
          </span>
        </div>
      )}
    </div>
  );
}
