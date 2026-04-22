"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { PPMCheckpoint } from "@/lib/types";

/**
 * Program page view for PPM (Perpetual Progression Mode) users.
 *
 * Renders the 14-week improvement cycle as the macrocycle:
 *   ┌──── Cycle header ─────────────────────────────┐
 *   │ Cycle #N · Week W / 14 · Focus: side_delt     │
 *   ├──── Macro strip (14 sub-phase columns) ───────┤
 *   ├──── Current mesocycle (MEV→MRV wave) ─────────┤
 *   ├──── This-week microcycle (7 day chips) ───────┤
 *   ├──── Split rationale (design_split reasoning) ─┤
 *   └──── Checkpoint history table ─────────────────┘
 */

interface PPMStatus {
  ppm_enabled: boolean;
  target_tier: number | null;
  current_cycle_number: number;
  current_cycle_start_date: string | null;
  current_cycle_week: number;
  cycle_focus_muscles: string[] | null;
  current_phase: string;
}

interface WeekPlan {
  week: number;
  ppm_sub_phase: string;
  landmark_zone: string;
  rir: number;
  fst7_mode: string;
  per_muscle_sets: Record<string, { target_sets: number; is_focus: boolean; rir: number; fst7_mode: string }>;
  day_rotation: { day: string; muscles: string[] }[];
}

interface CyclePlan {
  split: string;
  split_reasoning: string;
  focus_muscles: string[];
  total_weeks: number;
  weeks: WeekPlan[];
}

// Two forms per sub-phase:
//   abbr  — 2-3 char code rendered INSIDE a cycle column (narrow space)
//   label — full word rendered in the legend at the bottom of the strip
const SUB_PHASE_STYLE: Record<string, { abbr: string; label: string; fill: string; text: string }> = {
  ppm_assessment:      { abbr: "ASMT", label: "Assessment",     fill: "bg-viltrum-adriatic-bg",  text: "text-viltrum-adriatic" },
  ppm_accumulation:    { abbr: "ACC",  label: "Accumulation",   fill: "bg-viltrum-laurel-bg",    text: "text-viltrum-laurel"   },
  ppm_intensification: { abbr: "INT",  label: "Intensification",fill: "bg-viltrum-aureus-bg",    text: "text-viltrum-aureus"   },
  ppm_deload:          { abbr: "DLD",  label: "Deload",         fill: "bg-viltrum-limestone",    text: "text-viltrum-iron"     },
  ppm_checkpoint:      { abbr: "CHK",  label: "Checkpoint",     fill: "bg-viltrum-blush",        text: "text-viltrum-centurion"},
  ppm_mini_cut:        { abbr: "CUT",  label: "Mini-cut",       fill: "bg-viltrum-aureus-bg",    text: "text-viltrum-aureus"   },
};

const DAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export default function PPMCycleView({ status }: { status: PPMStatus }) {
  const [plan, setPlan] = useState<CyclePlan | null>(null);
  const [currentWeekPlan, setCurrentWeekPlan] = useState<WeekPlan | null>(null);
  const [history, setHistory] = useState<PPMCheckpoint[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.get<{ week_plan: WeekPlan; cycle_summary: { split: string; focus_muscles: string[]; total_weeks: number } }>(
        `/ppm/plan/${status.current_cycle_week || 1}`,
      ).catch(() => null),
      api.get<PPMCheckpoint[]>("/ppm/history?limit=10").catch(() => []),
    ])
      .then(([weekResp, hist]) => {
        if (weekResp) setCurrentWeekPlan(weekResp.week_plan);
        if (hist) setHistory(hist);
        // The cycle-wide strip is generated from the stable sub-phase rule:
        // weeks 1-2 assess, 3-10 accum, 11-12 intensify, 13 deload, 14 checkpoint.
        const labelFor = (w: number): string => {
          if (w <= 2) return "ppm_assessment";
          if (w <= 10) return "ppm_accumulation";
          if (w <= 12) return "ppm_intensification";
          if (w === 13) return "ppm_deload";
          if (w === 14) return "ppm_checkpoint";
          return "ppm_mini_cut";
        };
        const totalWeeks = weekResp?.cycle_summary?.total_weeks ?? 14;
        const generatedWeeks: WeekPlan[] = Array.from({ length: totalWeeks }, (_, i) => ({
          week: i + 1,
          ppm_sub_phase: labelFor(i + 1),
          landmark_zone: "",
          rir: 0,
          fst7_mode: "",
          per_muscle_sets: {},
          day_rotation: [],
        }));
        setPlan({
          split: weekResp?.cycle_summary?.split ?? "custom",
          split_reasoning: "",
          focus_muscles: weekResp?.cycle_summary?.focus_muscles ?? status.cycle_focus_muscles ?? [],
          total_weeks: totalWeeks,
          weeks: generatedWeeks,
        });
      })
      .finally(() => setLoading(false));
  }, [status.current_cycle_week, status.cycle_focus_muscles]);

  const cycleWeek = Math.max(1, Math.min(status.current_cycle_week || 1, plan?.total_weeks ?? 14));

  return (
    <div className="space-y-6">
      {/* ── Cycle Header ─────────────────────────────────────────────── */}
      <section className="card">
        <div className="flex items-start justify-between gap-3 flex-wrap">
          <div>
            <div className="h-section">Improvement Cycle</div>
            <div className="font-display uppercase tracking-[4px] text-[28px] leading-none text-viltrum-obsidian mt-1">
              Cycle #{status.current_cycle_number}
            </div>
            <div className="text-[11px] text-viltrum-travertine mt-1">
              Week {cycleWeek} of {plan?.total_weeks ?? 14} ·{" "}
              {SUB_PHASE_STYLE[status.current_phase]?.label ?? status.current_phase.replace(/^ppm_/, "")}
            </div>
          </div>
          {(plan?.focus_muscles?.length ?? 0) > 0 && (
            <div className="flex flex-col gap-1 items-end">
              <span className="text-[10px] uppercase tracking-[2px] text-viltrum-travertine">Focus</span>
              <div className="flex flex-wrap gap-1 justify-end">
                {plan!.focus_muscles.map((m) => (
                  <span key={m} className="text-[10px] px-2 py-0.5 rounded-pill bg-viltrum-blush text-viltrum-centurion border border-viltrum-legion/30">
                    {m.replace(/_/g, " ")}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      </section>

      {/* ── Macro strip (14 weeks) ──────────────────────────────────── */}
      <section className="card">
        <h3 className="h-card mb-3">Macro · Improvement Cycle</h3>
        <div className="grid gap-1" style={{ gridTemplateColumns: `repeat(${plan?.total_weeks ?? 14}, minmax(0, 1fr))` }}>
          {(plan?.weeks ?? []).map((w) => {
            const style = SUB_PHASE_STYLE[w.ppm_sub_phase];
            const active = w.week === cycleWeek;
            return (
              <div
                key={w.week}
                title={`Week ${w.week} · ${style?.label ?? w.ppm_sub_phase}`}
                className={`relative h-14 rounded-card flex flex-col items-center justify-center overflow-hidden ${style?.fill ?? "bg-viltrum-limestone"} ${active ? "border-b-[2.5px] border-viltrum-obsidian" : ""}`}
              >
                {/* Week number — primary, always visible. */}
                <span className={`font-display text-[12px] ${style?.text ?? "text-viltrum-iron"}`}>
                  {w.week}
                </span>
                {/* Sub-phase abbreviation — 3-char code so it fits in a
                    ~70px cell even at 16 columns. Full label appears in the
                    legend below plus the column's title tooltip. */}
                <span className={`text-[8px] font-semibold tracking-[1px] mt-0.5 ${style?.text ?? "text-viltrum-iron"}/80`}>
                  {style?.abbr ?? ""}
                </span>
              </div>
            );
          })}
        </div>
        <div className="flex flex-wrap gap-x-3 gap-y-1.5 mt-3 text-[10px] text-viltrum-travertine">
          {Object.entries(SUB_PHASE_STYLE).map(([k, s]) => (
            <span key={k} className="flex items-center gap-1.5">
              <span className={`inline-block w-2.5 h-2.5 rounded-sm ${s.fill}`} />
              <span className={s.text}>
                <span className="font-mono text-[9px] mr-1">{s.abbr}</span>
                {s.label}
              </span>
            </span>
          ))}
        </div>
      </section>

      {/* ── Mesocycle — current week focus ──────────────────────────── */}
      {currentWeekPlan && (
        <section className="card">
          <div className="flex items-baseline justify-between mb-3">
            <h3 className="h-card">Mesocycle · Current Week</h3>
            <span className="text-[10px] text-viltrum-travertine uppercase tracking-[2px]">
              {currentWeekPlan.landmark_zone || "—"} · RIR {currentWeekPlan.rir} · FST-7 {currentWeekPlan.fst7_mode}
            </span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
            {Object.entries(currentWeekPlan.per_muscle_sets).map(([muscle, info]) => (
              <div
                key={muscle}
                className={`rounded-card p-2 border ${info.is_focus ? "border-viltrum-legion/40 bg-viltrum-blush" : "border-viltrum-ash bg-white"}`}
              >
                <div className="flex justify-between items-center">
                  <span className="text-[11px] text-viltrum-iron capitalize">{muscle.replace(/_/g, " ")}</span>
                  <span className="font-display text-[14px] text-viltrum-obsidian">{info.target_sets}</span>
                </div>
                {info.is_focus && (
                  <span className="text-[9px] text-viltrum-centurion uppercase tracking-[2px] mt-0.5 inline-block">
                    Focus +20%
                  </span>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* ── Microcycle — this week at a glance ──────────────────────── */}
      {currentWeekPlan && currentWeekPlan.day_rotation.length > 0 && (
        <section className="card">
          <h3 className="h-card mb-3">Microcycle · This Week</h3>
          <div className="grid grid-cols-7 gap-1">
            {DAY_LABELS.map((label, i) => {
              const day = currentWeekPlan.day_rotation[i % currentWeekPlan.day_rotation.length];
              return (
                <div
                  key={label}
                  className="rounded-card p-2 bg-viltrum-limestone border border-viltrum-ash text-center"
                >
                  <div className="text-[9px] uppercase tracking-[2px] text-viltrum-travertine">{label}</div>
                  <div className="text-[11px] text-viltrum-obsidian font-medium mt-1">
                    {day?.day ?? "Rest"}
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* ── Checkpoint history ─────────────────────────────────────── */}
      {history.length > 0 && (
        <section className="card">
          <h3 className="h-card mb-3">Checkpoint History</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-[11px]">
              <thead>
                <tr className="text-viltrum-travertine uppercase tracking-[2px] text-[9px]">
                  <th className="text-left py-1 px-2">Date</th>
                  <th className="text-right py-1 px-2">BW</th>
                  <th className="text-right py-1 px-2">BF%</th>
                  <th className="text-right py-1 px-2">FFMI</th>
                  <th className="text-right py-1 px-2">HQI</th>
                  <th className="text-right py-1 px-2">Cycle</th>
                </tr>
              </thead>
              <tbody>
                {history.map((c) => (
                  <tr key={c.id} className="border-t border-viltrum-ash text-viltrum-iron">
                    <td className="py-1.5 px-2 font-mono">{c.checkpoint_date}</td>
                    <td className="py-1.5 px-2 text-right font-mono">{c.body_weight_kg?.toFixed(1) ?? "—"}</td>
                    <td className="py-1.5 px-2 text-right font-mono">{c.bf_pct?.toFixed(1) ?? "—"}</td>
                    <td className="py-1.5 px-2 text-right font-mono">{c.ffmi?.toFixed(1) ?? "—"}</td>
                    <td className="py-1.5 px-2 text-right font-mono">{c.hqi_score?.toFixed(0) ?? "—"}</td>
                    <td className="py-1.5 px-2 text-right">#{c.cycle_number}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {loading && (
        <div className="text-center text-viltrum-travertine text-[11px] py-8">
          Loading cycle plan…
        </div>
      )}
    </div>
  );
}
