"use client";

/**
 * Small visualization components for Perpetual Progression Mode (PPM) dashboard.
 *
 * Each card is intentionally self-contained so the main dashboard grid can
 * toggle them independently. All cards respect the jungle theme tokens
 * (`jungle-card`, `jungle-accent`, `jungle-dim`, etc.) defined in globals.css.
 */

import type { TierReadiness } from "@/lib/types";

// ---------------------------------------------------------------------------
// Improvement Cycle progress — week N of 14, sub-phase, focus muscles
// ---------------------------------------------------------------------------
interface CycleProgressProps {
  cycleNumber: number;
  cycleWeek: number;
  totalWeeks: number;           // 14 or 16 (mini-cut extension)
  subPhase: string;             // "ppm_assessment" | "ppm_accumulation" | ...
  focusMuscles: string[];
}

const SUB_PHASE_LABELS: Record<string, { label: string; tone: string }> = {
  ppm_assessment:     { label: "Assessment",     tone: "text-sky-400" },
  ppm_accumulation:   { label: "Accumulation",   tone: "text-emerald-400" },
  ppm_intensification:{ label: "Intensification",tone: "text-amber-400" },
  ppm_deload:         { label: "Deload",         tone: "text-jungle-dim" },
  ppm_checkpoint:     { label: "Checkpoint",     tone: "text-purple-400" },
  ppm_mini_cut:       { label: "Mini-Cut",       tone: "text-orange-400" },
};

export function CycleProgressCard({
  cycleNumber,
  cycleWeek,
  totalWeeks,
  subPhase,
  focusMuscles,
}: CycleProgressProps) {
  const pct = Math.min(100, Math.round((cycleWeek / totalWeeks) * 100));
  const phase = SUB_PHASE_LABELS[subPhase] ?? { label: subPhase, tone: "text-jungle-muted" };

  // Segment markers at the PPM sub-phase boundaries (weeks 2, 10, 12, 13, 14).
  const markers = [2, 10, 12, 13, 14];

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-[10px] uppercase tracking-wide text-jungle-dim">Cycle</div>
          <div className="text-sm font-semibold">#{cycleNumber}</div>
        </div>
        <div className="text-right">
          <div className={`text-sm font-semibold ${phase.tone}`}>{phase.label}</div>
          <div className="text-xs text-jungle-dim">Week {cycleWeek} / {totalWeeks}</div>
        </div>
      </div>
      <div className="relative h-2 rounded bg-jungle-dim/20">
        <div
          className="absolute h-2 rounded bg-jungle-accent transition-all"
          style={{ width: `${pct}%` }}
        />
        {markers.filter((m) => m < totalWeeks).map((m) => (
          <div
            key={m}
            className="absolute top-0 h-2 w-px bg-jungle-deeper"
            style={{ left: `${(m / totalWeeks) * 100}%` }}
          />
        ))}
      </div>
      <div className="flex flex-wrap gap-1">
        {focusMuscles.length === 0 ? (
          <span className="text-xs text-jungle-dim italic">Balanced — no specialization this cycle</span>
        ) : (
          focusMuscles.map((m) => (
            <span
              key={m}
              className="text-[10px] px-2 py-0.5 rounded bg-jungle-accent/25 text-jungle-accent border border-jungle-accent/40"
            >
              {m}
            </span>
          ))
        )}
      </div>
    </div>
  );
}


// ---------------------------------------------------------------------------
// Arm-Calf-Neck parity (Steve Reeves classical standard) — Classic only
// ---------------------------------------------------------------------------
interface ParityProps {
  arm_cm: number | null;
  calf_cm: number | null;
  neck_cm: number | null;
}

export function ParityCheckCard({ arm_cm, calf_cm, neck_cm }: ParityProps) {
  const values = [arm_cm, calf_cm, neck_cm];
  if (values.some((v) => v === null || v === undefined)) {
    return (
      <div className="text-xs text-jungle-dim italic">
        Log arm, calf, and neck measurements to see parity.
      </div>
    );
  }

  const [arm, calf, neck] = values as number[];
  const min = Math.min(arm, calf, neck);
  const max = Math.max(arm, calf, neck);
  const diff_cm = max - min;
  const diff_in = diff_cm / 2.54;
  const reeves_equal = diff_cm <= 1.27;

  const tone = reeves_equal ? "text-emerald-400" : diff_in > 2 ? "text-amber-400" : "text-jungle-muted";

  const bar = (label: string, val: number) => {
    const pct = Math.min(100, (val / max) * 100);
    return (
      <div>
        <div className="flex justify-between text-[10px] text-jungle-dim">
          <span>{label}</span>
          <span className="font-mono">{val.toFixed(1)} cm</span>
        </div>
        <div className="h-1.5 bg-jungle-dim/20 rounded">
          <div className="h-1.5 bg-jungle-accent rounded" style={{ width: `${pct}%` }} />
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-2">
      {bar("Arm", arm)}
      {bar("Calf", calf)}
      {bar("Neck", neck)}
      <div className="pt-1 text-xs flex justify-between">
        <span className="text-jungle-dim">Max diff</span>
        <span className={`font-mono ${tone}`}>
          {diff_in.toFixed(2)}"{" "}
          {reeves_equal ? "· Reeves parity ✓" : ""}
        </span>
      </div>
    </div>
  );
}


// ---------------------------------------------------------------------------
// Chest : Waist ratio (Classic-relevant; Reeves target 148%, Olympia ~175%)
// ---------------------------------------------------------------------------
interface ChestWaistProps {
  chest_cm: number | null;
  waist_cm: number | null;
  target?: number;       // 1.30 default for T1, 1.48 Reeves
}

export function ChestWaistCard({ chest_cm, waist_cm, target = 1.38 }: ChestWaistProps) {
  if (!chest_cm || !waist_cm) {
    return (
      <div className="text-xs text-jungle-dim italic">
        Log chest and waist measurements to see ratio.
      </div>
    );
  }
  const ratio = chest_cm / waist_cm;
  const pct_of_target = Math.min(200, (ratio / target) * 100);

  // Bands — 1.30 local, 1.38 regional, 1.42 national, 1.46 pro, 1.48 olympia
  const bands = [
    { at: 1.30, label: "T1" },
    { at: 1.38, label: "T2" },
    { at: 1.42, label: "T3" },
    { at: 1.46, label: "T4" },
    { at: 1.48, label: "T5 · Reeves" },
  ];
  const max = 1.80;

  return (
    <div className="space-y-3">
      <div className="flex items-baseline justify-between">
        <span className="text-[10px] uppercase tracking-wide text-jungle-dim">Chest : Waist</span>
        <span className="font-mono text-sm font-semibold">
          {(ratio * 100).toFixed(1)}%
        </span>
      </div>
      <div className="relative h-3 rounded bg-jungle-dim/15">
        <div
          className="absolute h-3 rounded bg-jungle-accent/80"
          style={{ width: `${Math.min(100, (ratio / max) * 100)}%` }}
        />
        {bands.map((b) => (
          <div
            key={b.at}
            className="absolute top-0 h-3 w-px bg-jungle-deeper"
            style={{ left: `${(b.at / max) * 100}%` }}
          />
        ))}
      </div>
      <div className="flex justify-between text-[9px] text-jungle-dim">
        {bands.map((b) => (
          <span key={b.at}>{b.label}</span>
        ))}
      </div>
      <div className="text-xs text-jungle-dim">
        Target: <span className="text-jungle-muted">{(target * 100).toFixed(0)}%</span>
        {" · "}
        You: <span className={ratio >= target ? "text-emerald-400" : "text-jungle-muted"}>
          {Math.round(pct_of_target)}% of target
        </span>
      </div>
    </div>
  );
}


// ---------------------------------------------------------------------------
// Carb cycle — high/medium/low day macros
// ---------------------------------------------------------------------------
interface CarbCycleDay {
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  target_calories: number;
}

interface CarbCycleProps {
  high_day: CarbCycleDay | null;
  medium_day: CarbCycleDay | null;
  low_day: CarbCycleDay | null;
  days_per_week?: { high: number; medium: number; low: number };
}

export function CarbCycleCard({ high_day, medium_day, low_day, days_per_week }: CarbCycleProps) {
  if (!high_day || !medium_day || !low_day) {
    return <div className="text-xs text-jungle-dim italic">Carb cycle unavailable.</div>;
  }
  const days = days_per_week || { high: 2, medium: 3, low: 2 };
  const rows: Array<[string, CarbCycleDay, number, string]> = [
    ["High",   high_day,   days.high,   "bg-emerald-500/20 text-emerald-400"],
    ["Medium", medium_day, days.medium, "bg-amber-500/20 text-amber-400"],
    ["Low",    low_day,    days.low,    "bg-sky-500/20 text-sky-400"],
  ];
  const maxCarbs = Math.max(high_day.carbs_g, medium_day.carbs_g, low_day.carbs_g, 1);

  return (
    <div className="space-y-2">
      {rows.map(([label, day, d, tone]) => (
        <div key={label} className="border border-jungle-dim/20 rounded-md p-2">
          <div className="flex items-center justify-between text-xs">
            <div className="flex items-center gap-2">
              <span className={`px-1.5 py-0.5 rounded text-[10px] ${tone}`}>{label}</span>
              <span className="text-jungle-dim">{d}×/wk</span>
            </div>
            <span className="font-mono text-jungle-muted">{Math.round(day.target_calories)} kcal</span>
          </div>
          <div className="mt-1 h-1 rounded bg-jungle-dim/15">
            <div
              className="h-1 rounded bg-jungle-accent"
              style={{ width: `${(day.carbs_g / maxCarbs) * 100}%` }}
            />
          </div>
          <div className="mt-1 grid grid-cols-3 gap-1 text-[10px] text-jungle-muted">
            <div>P {Math.round(day.protein_g)}g</div>
            <div>C {Math.round(day.carbs_g)}g</div>
            <div>F {Math.round(day.fat_g)}g</div>
          </div>
        </div>
      ))}
    </div>
  );
}


// ---------------------------------------------------------------------------
// Conditioning style (Classic only)
// ---------------------------------------------------------------------------
type ConditioningStyle = "full" | "tight" | "dry" | "grainy";

interface ConditioningProps {
  style: ConditioningStyle | null;
  onChange?: (next: ConditioningStyle) => void;
}

const CONDITIONING_OPTIONS: Array<{
  value: ConditioningStyle;
  icon: string;
  label: string;
  blurb: string;
  classicBonus: number;
}> = [
  { value: "full",   icon: "●",  label: "Full",   blurb: "Judges reward this in Classic.", classicBonus: +10 },
  { value: "tight",  icon: "◉",  label: "Tight",  blurb: "Balanced — neutral.",               classicBonus: 0 },
  { value: "dry",    icon: "◎",  label: "Dry",    blurb: "Balanced — neutral.",               classicBonus: 0 },
  { value: "grainy", icon: "○",  label: "Grainy", blurb: "Open-level — penalized in Classic.", classicBonus: -10 },
];

export function ConditioningStyleCard({ style, onChange }: ConditioningProps) {
  return (
    <div className="space-y-2">
      <div className="grid grid-cols-2 gap-2">
        {CONDITIONING_OPTIONS.map((opt) => {
          const active = style === opt.value;
          const bonusTone =
            opt.classicBonus > 0 ? "text-emerald-400" :
            opt.classicBonus < 0 ? "text-amber-400" : "text-jungle-dim";
          return (
            <button
              key={opt.value}
              type="button"
              onClick={() => onChange?.(opt.value)}
              className={`text-left p-2 rounded-md border transition ${
                active
                  ? "border-jungle-accent bg-jungle-accent/10"
                  : "border-jungle-dim hover:border-jungle-accent"
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="text-xl leading-none">{opt.icon}</span>
                <span className={`text-[10px] font-mono ${bonusTone}`}>
                  {opt.classicBonus > 0 ? "+" : ""}{opt.classicBonus}
                </span>
              </div>
              <div className="text-sm font-medium mt-1">{opt.label}</div>
              <div className="text-[10px] text-jungle-dim">{opt.blurb}</div>
            </button>
          );
        })}
      </div>
      <p className="text-[10px] text-jungle-dim">
        Per ANBF / IFBB rulebook — "ripped / shredded / grainy" is flagged as
        non-Classic. Judges want "full and tight".
      </p>
    </div>
  );
}


// ---------------------------------------------------------------------------
// Natural ceiling gauge — Casey Butt prediction vs division cap
// ---------------------------------------------------------------------------
interface NaturalCeilingProps {
  predictedStageKg: number | null;
  tierRequiredKg: number | null;
  divisionCapKg: number | null;
  attainable: boolean;
  ffmiPredicted?: number | null;
  ffmiRequired?: number | null;
}

export function NaturalCeilingCard({
  predictedStageKg,
  tierRequiredKg,
  divisionCapKg,
  attainable,
  ffmiPredicted,
  ffmiRequired,
}: NaturalCeilingProps) {
  if (!predictedStageKg || !divisionCapKg) {
    return (
      <div className="text-xs text-jungle-dim italic">
        Log wrist and ankle measurements to estimate your natural ceiling.
      </div>
    );
  }

  const predictedPct = Math.min(100, (predictedStageKg / divisionCapKg) * 100);
  const tierPct = tierRequiredKg ? (tierRequiredKg / divisionCapKg) * 100 : null;
  const tone = attainable ? "text-emerald-400" : "text-amber-400";

  return (
    <div className="space-y-2">
      <div className="flex justify-between items-baseline">
        <span className="text-[10px] uppercase tracking-wide text-jungle-dim">Natural ceiling</span>
        <span className={`text-sm font-mono font-semibold ${tone}`}>
          {attainable ? "Attainable" : "Above ceiling"}
        </span>
      </div>
      <div className="relative h-4 rounded bg-jungle-dim/15">
        {/* Predicted natural max */}
        <div
          className="absolute h-4 rounded bg-jungle-accent/70"
          style={{ width: `${predictedPct}%` }}
        />
        {/* Tier requirement mark */}
        {tierPct !== null && (
          <div
            className="absolute top-0 h-4 w-0.5 bg-amber-400"
            style={{ left: `${Math.min(100, tierPct)}%` }}
          />
        )}
      </div>
      <div className="grid grid-cols-2 gap-1 text-[10px] text-jungle-dim">
        <div>Casey Butt max:</div>
        <div className="text-right font-mono text-jungle-muted">{predictedStageKg.toFixed(1)} kg</div>
        {tierRequiredKg !== null && (
          <>
            <div>Tier requires:</div>
            <div className="text-right font-mono text-amber-400">{tierRequiredKg.toFixed(1)} kg</div>
          </>
        )}
        <div>Division cap:</div>
        <div className="text-right font-mono text-jungle-muted">{divisionCapKg.toFixed(1)} kg</div>
        {ffmiPredicted !== null && ffmiPredicted !== undefined && (
          <>
            <div>FFMI predicted / required:</div>
            <div className="text-right font-mono">
              <span className={ffmiRequired && ffmiPredicted >= ffmiRequired ? "text-emerald-400" : "text-amber-400"}>
                {ffmiPredicted.toFixed(1)}
              </span>
              <span className="text-jungle-dim"> / {ffmiRequired?.toFixed(1)}</span>
            </div>
          </>
        )}
      </div>
    </div>
  );
}


// ---------------------------------------------------------------------------
// Small wrapper — re-export TierReadinessCard under one name for dashboard use
// ---------------------------------------------------------------------------
export function TierReadinessSummary({ readiness }: { readiness: TierReadiness }) {
  return (
    <div className="space-y-2">
      <div className="flex justify-between items-baseline">
        <span className="text-[10px] uppercase tracking-wide text-jungle-dim">Limiting factor</span>
        <span className="text-xs text-jungle-muted">{readiness.limiting_factor}</span>
      </div>
      <div className="text-sm font-medium">
        {readiness.metrics_met}/{readiness.metrics_total} thresholds met
      </div>
      <div className="h-1.5 bg-jungle-dim/20 rounded">
        <div
          className="h-1.5 bg-jungle-accent rounded"
          style={{ width: `${Math.round(readiness.pct_met * 100)}%` }}
        />
      </div>
    </div>
  );
}
