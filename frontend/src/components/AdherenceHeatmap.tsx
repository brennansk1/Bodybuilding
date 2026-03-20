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
  if (value === null || value === undefined) return "#1e3a1e";
  if (value === 0) return "#1a2414";
  if (value <= 60) return "#7f1d1d";
  if (value <= 84) return "#92400e";
  if (value <= 94) return "#166534";
  return "#16a34a";
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
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
    col: number;
    row: number;
  } | null>(null);

  // Build a lookup map from date string -> entry
  const dataMap: Record<string, AdherenceDay> = {};
  for (const entry of data) {
    dataMap[entry.date] = entry;
  }

  // Build 12-week grid (84 days) ending today
  const today = new Date();
  const endMonday = getMonday(today);
  // Go back 11 more weeks from this week's Monday = 12 weeks total
  const startDate = new Date(endMonday);
  startDate.setDate(startDate.getDate() - 11 * 7);

  // Build columns: 12 weeks, each column = one week (Mon-Sun)
  const weeks: Array<Array<Date | null>> = [];
  for (let w = 0; w < 12; w++) {
    const week: Array<Date | null> = [];
    for (let d = 0; d < 7; d++) {
      const dayDate = new Date(startDate);
      dayDate.setDate(startDate.getDate() + w * 7 + d);
      // Don't show future dates
      if (dayDate > today) {
        week.push(null);
      } else {
        week.push(dayDate);
      }
    }
    weeks.push(week);
  }

  // Month labels: show month name at first week where a new month appears
  const monthLabels: Array<{ col: number; label: string }> = [];
  let lastMonth = -1;
  for (let w = 0; w < 12; w++) {
    const firstDay = weeks[w][0];
    if (firstDay) {
      const m = firstDay.getMonth();
      if (m !== lastMonth) {
        monthLabels.push({
          col: w,
          label: firstDay.toLocaleDateString("en-US", { month: "short" }),
        });
        lastMonth = m;
      }
    }
  }

  const CELL = 12;
  const GAP = 2;
  const LEFT_OFFSET = 20; // space for day labels
  const TOP_OFFSET = 16;  // space for month labels

  const dayLabels = ["M", "T", "W", "T", "F", "S", "S"];

  function getValue(entry: AdherenceDay | undefined): number | null {
    if (!entry) return null;
    if (type === "nutrition") return entry.nutrition;
    if (type === "training") return entry.training;
    return entry.overall;
  }

  return (
    <div className="relative">
      {/* Grid */}
      <div className="overflow-x-auto">
        <svg
          width={LEFT_OFFSET + 12 * (CELL + GAP)}
          height={TOP_OFFSET + 7 * (CELL + GAP) + 24}
          style={{ display: "block", minWidth: LEFT_OFFSET + 12 * (CELL + GAP) }}
        >
          {/* Month labels */}
          {monthLabels.map(({ col, label }) => (
            <text
              key={`month-${col}`}
              x={LEFT_OFFSET + col * (CELL + GAP)}
              y={10}
              fontSize="7"
              fill="#6a8a60"
              fontWeight="500"
            >
              {label}
            </text>
          ))}

          {/* Day-of-week labels */}
          {dayLabels.map((d, i) => (
            <text
              key={`dow-${i}`}
              x={LEFT_OFFSET - 4}
              y={TOP_OFFSET + i * (CELL + GAP) + CELL / 2 + 1}
              fontSize="6.5"
              fill="#4a6040"
              textAnchor="middle"
              dominantBaseline="middle"
            >
              {i % 2 === 0 ? d : ""}
            </text>
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

              return (
                <g key={`${col}-${row}`}>
                  <rect
                    x={cx} y={cy}
                    width={CELL} height={CELL}
                    rx={2}
                    fill={color}
                    stroke="#0f1a0c"
                    strokeWidth="0.5"
                    style={{ cursor: entry ? "pointer" : "default" }}
                    onMouseEnter={() => {
                      if (entry) {
                        setTooltip({ date: dateStr, nutrition: entry.nutrition, training: entry.training, overall: entry.overall, col, row });
                      }
                    }}
                    onMouseLeave={() => setTooltip(null)}
                  />
                  {/* N/T icons for high adherence days */}
                  {entry && entry.nutrition >= 85 && (
                    <text x={cx + 3} y={cy + 5} fontSize="4" fill="#16a34a" style={{ pointerEvents: "none" }}>N</text>
                  )}
                  {entry && entry.training >= 85 && (
                    <text x={cx + 7} y={cy + 5} fontSize="4" fill="#4ade80" style={{ pointerEvents: "none" }}>T</text>
                  )}
                </g>
              );
            })
          )}

          {/* Tooltip */}
          {tooltip && (() => {
            const tx = LEFT_OFFSET + tooltip.col * (CELL + GAP);
            const ty = TOP_OFFSET + tooltip.row * (CELL + GAP);
            const boxW = 90;
            const boxH = 44;
            // Clamp so it doesn't go off right edge
            const bx = Math.min(tx, LEFT_OFFSET + 12 * (CELL + GAP) - boxW - 4);
            const by = tooltip.row <= 3 ? ty + CELL + 2 : ty - boxH - 2;

            return (
              <g style={{ pointerEvents: "none" }}>
                <rect x={bx} y={by} width={boxW} height={boxH} rx={4} fill="#0f1a0c" stroke="#4a6040" strokeWidth="0.75" />
                <text x={bx + 6} y={by + 10} fontSize="6.5" fill="#c8a84e" fontWeight="600">{formatDate(tooltip.date)}</text>
                <text x={bx + 6} y={by + 21} fontSize="6" fill="#8faa96">Nutrition: {Math.round(tooltip.nutrition)}%</text>
                <text x={bx + 6} y={by + 30} fontSize="6" fill="#8faa96">Training:  {Math.round(tooltip.training)}%</text>
                <text x={bx + 6} y={by + 39} fontSize="6" fill="#6a8a60">Overall: {Math.round(tooltip.overall)}%</text>
              </g>
            );
          })()}
        </svg>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-3 mt-2 text-[9px] text-jungle-dim flex-wrap">
        <span className="text-jungle-dim mr-1">Less</span>
        {[
          { color: "#1a2414", label: "0%" },
          { color: "#7f1d1d", label: "≤60%" },
          { color: "#92400e", label: "≤84%" },
          { color: "#166534", label: "≤94%" },
          { color: "#16a34a", label: "100%" },
        ].map(({ color, label }) => (
          <span key={label} className="flex items-center gap-0.5">
            <span
              className="w-2.5 h-2.5 rounded-sm inline-block border border-black/20"
              style={{ backgroundColor: color }}
            />
            <span className="text-[8px]">{label}</span>
          </span>
        ))}
        <span className="text-jungle-dim ml-1">More</span>
      </div>
    </div>
  );
}
