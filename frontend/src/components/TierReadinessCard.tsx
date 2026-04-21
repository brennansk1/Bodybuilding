"use client";

import type { TierReadiness, TierProjection, ReadinessState } from "@/lib/types";

const STATE_LABELS: Record<ReadinessState, { label: string; tone: string }> = {
  not_ready:    { label: "Not Ready",    tone: "text-jungle-dim" },
  developing:   { label: "Developing",   tone: "text-sky-400" },
  approaching:  { label: "Approaching",  tone: "text-amber-400" },
  stage_ready:  { label: "Stage Ready",  tone: "text-emerald-400" },
};

const METRIC_LABELS: Record<string, string> = {
  weight_cap_pct:       "Weight / Cap",
  ffmi:                 "FFMI",
  shoulder_waist:       "Shoulder:Waist",
  chest_waist:          "Chest:Waist",
  arm_calf_neck_parity: "Arm-Calf-Neck parity",
  hqi:                  "HQI",
  training_years:       "Training years",
};

interface Props {
  readiness: TierReadiness;
  projection?: TierProjection;
  currentCycleWeek?: number;
  totalCycleWeeks?: number;
  onTransitionToComp?: () => void;
}

export default function TierReadinessCard({
  readiness,
  projection,
  currentCycleWeek,
  totalCycleWeeks,
  onTransitionToComp,
}: Props) {
  const state = STATE_LABELS[readiness.state];
  const canTransition = readiness.state === "approaching" || readiness.state === "stage_ready";

  return (
    <div className="jungle-card p-5 space-y-4">
      <header className="flex items-start justify-between">
        <div>
          <div className="text-xs uppercase tracking-wide text-jungle-dim">Target tier</div>
          <div className="text-lg font-semibold">{readiness.tier}</div>
        </div>
        <div className="text-right">
          <div className="text-xs uppercase tracking-wide text-jungle-dim">Readiness</div>
          <div className={`text-lg font-semibold ${state.tone}`}>{state.label}</div>
          <div className="text-xs text-jungle-dim mt-0.5">
            {readiness.metrics_met}/{readiness.metrics_total} thresholds met · {Math.round(readiness.pct_met * 100)}%
          </div>
        </div>
      </header>

      {typeof currentCycleWeek === "number" && typeof totalCycleWeeks === "number" && (
        <div>
          <div className="flex justify-between text-xs text-jungle-dim mb-1">
            <span>Cycle week</span>
            <span>{currentCycleWeek} / {totalCycleWeeks}</span>
          </div>
          <div className="h-1.5 bg-jungle-dim/20 rounded">
            <div
              className="h-1.5 bg-jungle-accent rounded"
              style={{ width: `${Math.min(100, (currentCycleWeek / totalCycleWeeks) * 100)}%` }}
            />
          </div>
        </div>
      )}

      <div className="space-y-2">
        {Object.entries(readiness.per_metric).map(([key, m]) => {
          const label = METRIC_LABELS[key] || key;
          const pct = Math.round(m.pct_progress * 100);
          return (
            <div key={key}>
              <div className="flex justify-between text-xs">
                <span className="text-jungle-muted">{label}</span>
                <span className={m.met ? "text-emerald-400" : "text-jungle-dim"}>
                  {m.current} / {m.target} {m.met && "✓"}
                </span>
              </div>
              <div className="h-1 bg-jungle-dim/20 rounded mt-0.5">
                <div
                  className={`h-1 rounded ${m.met ? "bg-emerald-500" : "bg-jungle-accent"}`}
                  style={{ width: `${Math.min(100, pct)}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>

      <div className="border-t border-jungle-dim/20 pt-3 space-y-1">
        <div className="text-xs text-jungle-dim">Limiting factor</div>
        <div className="text-sm font-medium">
          {METRIC_LABELS[readiness.limiting_factor] || readiness.limiting_factor}
        </div>
        {projection && (
          <div className="text-xs text-jungle-dim mt-1">
            Projected {projection.estimated_cycles} cycles · {projection.estimated_months} months
            · limiter = {projection.limiting_dimension}
          </div>
        )}
      </div>

      {canTransition && (
        <button
          type="button"
          onClick={onTransitionToComp}
          className="btn-primary w-full text-sm"
        >
          {readiness.state === "stage_ready"
            ? "You're ready — pick a show"
            : "Approaching readiness — browse shows"}
        </button>
      )}
    </div>
  );
}
