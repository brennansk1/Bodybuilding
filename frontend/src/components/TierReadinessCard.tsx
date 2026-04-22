"use client";

import type { TierReadiness, TierProjection, ReadinessState } from "@/lib/types";
import { AlertTriangle, Check } from "./icons";

const STATE: Record<ReadinessState, { label: string; badge: string; ring: string }> = {
  not_ready:   { label: "Not Ready",    badge: "bg-viltrum-limestone text-viltrum-iron",     ring: "border-viltrum-ash" },
  developing:  { label: "Developing",   badge: "bg-viltrum-adriatic-bg text-viltrum-adriatic", ring: "border-viltrum-adriatic/30" },
  approaching: { label: "Approaching",  badge: "bg-viltrum-aureus-bg text-viltrum-aureus",   ring: "border-viltrum-aureus/30" },
  stage_ready: { label: "Stage Ready",  badge: "bg-viltrum-laurel-bg text-viltrum-laurel",   ring: "border-viltrum-laurel/40" },
};

const METRIC_LABELS: Record<string, string> = {
  weight_cap_pct:       "Stage-projected weight",
  ffmi:                 "FFMI",
  shoulder_waist:       "Shoulder : Waist",
  chest_waist:          "Chest : Waist",
  arm_calf_neck_parity: "Arm · Calf · Neck parity",
  hqi:                  "HQI (last diagnostic)",
  training_years:       "Training years",
  mass_distribution:    "Mass distribution (worst site)",
};

const GROUPS: Array<{ title: string; keys: string[] }> = [
  { title: "Mass",        keys: ["weight_cap_pct", "ffmi", "mass_distribution"] },
  { title: "Proportions", keys: ["shoulder_waist", "chest_waist", "arm_calf_neck_parity"] },
  { title: "Readiness",   keys: ["hqi", "training_years"] },
];

const SITE_LABEL: Record<string, string> = {
  bicep: "Biceps",
  forearm: "Forearms",
  calf: "Calves",
  thigh: "Thighs",
  chest: "Chest",
  shoulders: "Shoulders",
  neck: "Neck",
  back_width: "Back width",
  waist: "Waist",
  hips: "Hips",
};

interface Props {
  readiness: TierReadiness;
  projection?: TierProjection;
  currentCycleWeek?: number;
  totalCycleWeeks?: number;
  onTransitionToComp?: () => void;
}

type MetricShape = TierReadiness["per_metric"][string] & {
  current_weight_kg?: number;
  projected_stage_kg?: number;
  weight_cap_kg?: number;
  bf_pct?: number | null;
  stale?: boolean;
  raw?: number;
  age_days?: number | null;
};

function formatMetricValue(key: string, m: MetricShape): string {
  if (key === "weight_cap_pct") return `${(m.current * 100).toFixed(0)}%`;
  if (key === "ffmi") return m.current.toFixed(1);
  if (key === "shoulder_waist" || key === "chest_waist") return m.current.toFixed(2);
  if (key === "arm_calf_neck_parity") return `${m.current.toFixed(2)}"`;
  if (key === "hqi") return m.current.toFixed(0);
  if (key === "training_years") return `${m.current.toFixed(0)} yr`;
  if (key === "mass_distribution") return `${(m.current * 100).toFixed(0)}%`;
  return String(m.current);
}

function formatTarget(key: string, m: MetricShape): string {
  if (key === "weight_cap_pct") return `${(m.target * 100).toFixed(0)}%`;
  if (key === "arm_calf_neck_parity") return `${m.target.toFixed(2)}"`;
  if (key === "training_years") return `${m.target.toFixed(0)} yr`;
  if (key === "mass_distribution") return `${(m.target * 100).toFixed(0)}%`;
  return m.target.toFixed(2);
}

export default function TierReadinessCard({
  readiness,
  projection,
  currentCycleWeek,
  totalCycleWeeks,
  onTransitionToComp,
}: Props) {
  const state = STATE[readiness.state];
  const canTransition = readiness.state === "approaching" || readiness.state === "stage_ready";
  const limiter = readiness.per_metric[readiness.limiting_factor] as MetricShape | undefined;

  return (
    <div className="jungle-card">
      {/* Header row */}
      <header className="flex items-start justify-between gap-4 pb-4 border-b border-viltrum-ash">
        <div className="min-w-0">
          <div className="text-[10px] uppercase tracking-[2px] text-viltrum-travertine">
            Target tier
          </div>
          <div className="font-display text-[22px] tracking-[3px] uppercase text-viltrum-obsidian mt-0.5">
            {readiness.tier.replace(/_/g, " ")}
          </div>
        </div>
        <div className="text-right shrink-0">
          <div className="text-[10px] uppercase tracking-[2px] text-viltrum-travertine">Readiness</div>
          <span className={`inline-flex items-center gap-1.5 text-[11px] font-semibold px-3 py-1 rounded-pill mt-1 ${state.badge}`}>
            {readiness.state === "stage_ready" && <Check className="w-3 h-3" />}
            {state.label}
          </span>
          <div className="text-[10px] text-viltrum-travertine mt-1">
            {readiness.metrics_met}/{readiness.metrics_total} · {Math.round(readiness.pct_met * 100)}%
          </div>
        </div>
      </header>

      {/* Cycle progress (PPM) */}
      {typeof currentCycleWeek === "number" && typeof totalCycleWeeks === "number" && (
        <div className="py-3 border-b border-viltrum-ash">
          <div className="flex justify-between text-[10px] text-viltrum-travertine mb-1 uppercase tracking-[2px]">
            <span>Cycle week</span>
            <span className="font-mono">{currentCycleWeek} / {totalCycleWeeks}</span>
          </div>
          <div className="h-1.5 bg-viltrum-limestone rounded">
            <div
              className="h-1.5 bg-viltrum-obsidian rounded transition-all"
              style={{ width: `${Math.min(100, (currentCycleWeek / totalCycleWeeks) * 100)}%` }}
            />
          </div>
        </div>
      )}

      {/* Metric groups — two columns on desktop, stacked on mobile */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-4 py-4">
        {GROUPS.map((group) => (
          <div key={group.title} className="space-y-2">
            <h4 className="h-section">{group.title}</h4>
            {group.keys.map((key) => {
              const m = readiness.per_metric[key] as MetricShape | undefined;
              if (!m) return null;
              const pct = Math.round(m.pct_progress * 100);
              const label = METRIC_LABELS[key] || key;
              return (
                <div key={key}>
                  <div className="flex justify-between items-baseline text-[11px]">
                    <span className="text-viltrum-iron">{label}</span>
                    <span className={m.met ? "text-viltrum-laurel font-semibold" : "text-viltrum-obsidian"}>
                      <span className="font-mono">{formatMetricValue(key, m)}</span>
                      <span className="text-viltrum-pewter"> / </span>
                      <span className="font-mono">{formatTarget(key, m)}</span>
                      {m.met && <Check className="inline-block w-3 h-3 ml-1" />}
                    </span>
                  </div>
                  <div className="h-1 bg-viltrum-limestone rounded mt-1">
                    <div
                      className={`h-1 rounded ${m.met ? "bg-viltrum-laurel" : "bg-viltrum-legion"}`}
                      style={{ width: `${Math.min(100, pct)}%` }}
                    />
                  </div>
                  {/* Stage weight detail — only on weight_cap_pct */}
                  {key === "weight_cap_pct" && m.projected_stage_kg != null && (
                    <div className="text-[10px] text-viltrum-travertine mt-1 flex justify-between">
                      <span>Now {m.current_weight_kg} kg {m.bf_pct != null && `@ ${m.bf_pct}% BF`}</span>
                      <span>→ stage {m.projected_stage_kg} kg vs {m.weight_cap_kg} kg cap</span>
                    </div>
                  )}
                  {key === "hqi" && m.stale && (
                    <div className="text-[10px] text-viltrum-aureus mt-1 flex items-center gap-1">
                      <AlertTriangle className="w-3 h-3" />
                      Diagnostic is {m.age_days ?? "90+"} days old — rerun to refresh.
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        ))}
      </div>

      {/* Lagging muscles — per-site lean-gap callout pulled from HQI diagnostic */}
      {readiness.mass_gaps && readiness.mass_gaps.length > 0 && (
        <div className="mt-2 p-3 rounded-card bg-viltrum-limestone border border-viltrum-ash">
          <div className="text-[10px] uppercase tracking-[2px] text-viltrum-travertine mb-2">
            Lagging muscles (lean gap)
          </div>
          <div className="space-y-1.5">
            {readiness.mass_gaps.map((g) => (
              <div key={g.site} className="flex items-baseline justify-between text-[11px]">
                <span className="text-viltrum-iron">{SITE_LABEL[g.site] || g.site}</span>
                <span className="text-viltrum-obsidian">
                  <span className="font-mono">{g.current_lean_cm} cm</span>
                  <span className="text-viltrum-pewter"> / </span>
                  <span className="font-mono">{g.ideal_lean_cm} cm</span>
                  <span className="text-viltrum-centurion font-semibold ml-2">
                    −{g.gap_cm} cm
                  </span>
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Limiting factor callout */}
      {limiter && (
        <div className="mt-2 p-3 rounded-card bg-viltrum-blush border-l-[3px] border-viltrum-centurion">
          <div className="text-[10px] uppercase tracking-[2px] text-viltrum-centurion">Limiting factor</div>
          <div className="text-sm font-semibold text-viltrum-obsidian mt-0.5">
            {METRIC_LABELS[readiness.limiting_factor] || readiness.limiting_factor}
          </div>
          {projection && (
            <div className="text-[11px] text-viltrum-iron mt-1">
              ~{projection.estimated_cycles} cycles · {projection.estimated_months} months · limited by {projection.limiting_dimension}
            </div>
          )}
        </div>
      )}

      {canTransition && (
        <button
          type="button"
          onClick={onTransitionToComp}
          className="btn-primary w-full mt-4"
        >
          {readiness.state === "stage_ready" ? "You're ready — pick a show" : "Approaching — browse shows"}
        </button>
      )}
    </div>
  );
}
