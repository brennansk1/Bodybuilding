"use client";

import { useState } from "react";

interface AdherenceDay {
  date: string;
  nutrition: number;
  training: number;
  overall: number;
}

interface AdherenceHeatmapProps {
  data: AdherenceDay[];
  type?: "nutrition" | "training" | "overall";
}

function adherenceColor(value: number | null | undefined): string {
  if (value === null || value === undefined) return "#0f1f18";
  if (value === 0) return "#1a2414";
  if (value <= 40) return "#991b1b";
  if (value <= 60) return "#9a3412";
  if (value <= 75) return "#854d0e";
  if (value <= 85) return "#3f6212";
  if (value <= 94) return "#166534";
  return "#16a34a";
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr + "T00:00:00");
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function getMonday(d: Date): Date {
  const day = d.getDay();
  const diff = d.getDate() - day + (day === 0 ? -6 : 1);
  return new Date(d.getFullYear(), d.getMonth(), diff);
}

export default function AdherenceHeatmap({ data, type = "overall" }: AdherenceHeatmapProps) {
  const [tooltip, setTooltip] = useState<{
    date: string;
    nutrition: number;
    training: number;
    overall: number;
    x: number;
    y: number;
  } | null>(null);

  const dataMap: Record<string, AdherenceDay> = {};
  for (const entry of data) {
    dataMap[entry.date] = entry;
  }

  const today = new Date();
  const endMonday = getMonday(today);
  const startDate = new Date(endMonday);
  startDate.setDate(startDate.getDate() - 11 * 7);

  const weeks: Array<Array<Date | null>> = [];
  for (let w = 0; w < 12; w++) {
    const week: Array<Date | null> = [];
    for (let d = 0; d < 7; d++) {
      const dayDate = new Date(startDate);
      dayDate.setDate(startDate.getDate() + w * 7 + d);
      week.push(dayDate > today ? null : dayDate);
    }
    weeks.push(week);
  }

  const monthLabels: Array<{ col: number; label: string }> = [];
  let lastMonth = -1;
  for (let w = 0; w < 12; w++) {
    const firstDay = weeks[w][0];
    if (firstDay) {
      const m = firstDay.getMonth();
      if (m !== lastMonth) {
        monthLabels.push({ col: w, label: firstDay.toLocaleDateString("en-US", { month: "short" }) });
        lastMonth = m;
      }
    }
  }

  const CELL = 16;
  const GAP = 3;
  const LEFT_OFFSET = 24;
  const TOP_OFFSET = 18;
  const dayLabels = ["Mon", "", "Wed", "", "Fri", "", "Sun"];

  function getValue(entry: AdherenceDay | undefined): number | null {
    if (!entry) return null;
    if (type === "nutrition") return entry.nutrition;
    if (type === "training") return entry.training;
    return entry.overall;
  }

  // Compute summary stats
  const logged = data.filter((d) => d.overall > 0);
  const avgAdherence = logged.length > 0 ? Math.round(logged.reduce((s, d) => s + d.overall, 0) / logged.length) : 0;
  const streak = (() => {
    let count = 0;
    const sorted = [...data].sort((a, b) => b.date.localeCompare(a.date));
    for (const d of sorted) {
      if (d.overall >= 80) count++;
      else break;
    }
    return count;
  })();

  return (
    <div className="space-y-3">
      {/* Summary row */}
      <div className="flex items-center gap-4 text-[10px]">
        <span className="text-jungle-muted">
          Avg: <span className={`font-bold ${avgAdherence >= 85 ? "text-green-400" : avgAdherence >= 70 ? "text-jungle-accent" : "text-red-400"}`}>
            {avgAdherence}%
          </span>
        </span>
        <span className="text-jungle-muted">
          Streak: <span className="text-jungle-accent font-bold">{streak}d</span>
        </span>
        <span className="text-jungle-muted">
          Logged: <span className="text-jungle-text font-bold">{logged.length}</span>/84
        </span>
      </div>

      {/* Grid */}
      <div className="overflow-x-auto relative">
        <svg
          width={LEFT_OFFSET + 12 * (CELL + GAP) + 4}
          height={TOP_OFFSET + 7 * (CELL + GAP) + 4}
          style={{ display: "block", minWidth: LEFT_OFFSET + 12 * (CELL + GAP) }}
        >
          {/* Month labels */}
          {monthLabels.map(({ col, label }) => (
            <text key={`month-${col}`} x={LEFT_OFFSET + col * (CELL + GAP)} y={12} fontSize="8" fill="#8faa96" fontWeight="600">
              {label}
            </text>
          ))}

          {/* Day-of-week labels */}
          {dayLabels.map((d, i) => (
            d ? (
              <text key={`dow-${i}`} x={LEFT_OFFSET - 5} y={TOP_OFFSET + i * (CELL + GAP) + CELL / 2 + 1}
                fontSize="7" fill="#5a7a62" textAnchor="end" dominantBaseline="middle">
                {d}
              </text>
            ) : null
          ))}

          {/* Cells */}
          {weeks.map((week, col) =>
            week.map((date, row) => {
              if (!date) return null;
              const dateStr = date.toISOString().slice(0, 10);
              const entry = dataMap[dateStr];
              const value = getValue(entry);
              const color = adherenceColor(value);
              const cx = LEFT_OFFSET + col * (CELL + GAP);
              const cy = TOP_OFFSET + row * (CELL + GAP);
              const isToday = dateStr === today.toISOString().slice(0, 10);

              return (
                <rect
                  key={`${col}-${row}`}
                  x={cx} y={cy}
                  width={CELL} height={CELL}
                  rx={3}
                  fill={color}
                  stroke={isToday ? "var(--viltrum-accent)" : "var(--viltrum-bg)"}
                  strokeWidth={isToday ? 1.5 : 0.5}
                  style={{ cursor: entry ? "pointer" : "default" }}
                  onMouseEnter={(e) => {
                    if (entry) {
                      setTooltip({
                        date: dateStr,
                        nutrition: entry.nutrition,
                        training: entry.training,
                        overall: entry.overall,
                        x: cx, y: cy,
                      });
                    }
                  }}
                  onMouseLeave={() => setTooltip(null)}
                />
              );
            })
          )}
        </svg>

        {/* Tooltip — rendered as HTML for better styling */}
        {tooltip && (
          <div
            className="absolute z-10 bg-jungle-card border border-jungle-border rounded-lg shadow-xl px-3 py-2 pointer-events-none"
            style={{
              left: Math.min(tooltip.x, LEFT_OFFSET + 12 * (CELL + GAP) - 120),
              top: tooltip.y > 60 ? tooltip.y - 60 : tooltip.y + CELL + 4,
            }}
          >
            <p className="text-[10px] text-jungle-accent font-semibold">{formatDate(tooltip.date)}</p>
            <div className="flex gap-3 mt-1 text-[9px]">
              <span className="text-blue-400">N: {Math.round(tooltip.nutrition)}%</span>
              <span className="text-green-400">T: {Math.round(tooltip.training)}%</span>
              <span className="text-jungle-muted font-bold">{Math.round(tooltip.overall)}%</span>
            </div>
          </div>
        )}
      </div>

      {/* Legend */}
      <div className="flex items-center gap-1 text-[9px] text-jungle-dim">
        <span className="mr-1">Less</span>
        {[
          { color: "#1a2414", label: "0%" },
          { color: "#991b1b", label: "40%" },
          { color: "#854d0e", label: "75%" },
          { color: "#166534", label: "90%" },
          { color: "#16a34a", label: "100%" },
        ].map(({ color, label }) => (
          <div key={label} className="flex flex-col items-center gap-0.5">
            <span className="w-3.5 h-3.5 rounded-sm inline-block" style={{ backgroundColor: color }} />
            <span className="text-[7px]">{label}</span>
          </div>
        ))}
        <span className="ml-1">More</span>
      </div>
    </div>
  );
}
