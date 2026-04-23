"use client";

import { useState } from "react";
import type { TierReadiness, TierProjection, ReadinessState } from "@/lib/types";
import { AlertTriangle, Check } from "./icons";

// V4 / Claude Design — per-gate static coaching copy. Used by the inline
// click-to-expand panel so each of the 10 gates can teach the athlete what
// the metric is, why it matters at their target tier, and how to close the
// gap. No new backend data — all derivable from the existing `per_metric`
// payload.
const GATE_DETAILS: Record<string, { what: string; how: string }> = {
  weight_cap_pct: {
    what: "Your projected stage weight as a fraction of your IFBB Classic Physique weight cap. Stage weight is your current LBM grossed up to ~5% body fat.",
    how: "Add lean mass — keep training intensity high and stay in a controlled surplus until BF approaches the offseason ceiling, then mini-cut and rebuild.",
  },
  ffmi: {
    what: "Normalized Fat-Free Mass Index — LBM in kg ÷ height² in m, normalized to 6'0\" so it's comparable across heights.",
    how: "Same as weight: add LBM. FFMI moves slowly; expect ~0.5/year at your training age under elite execution.",
  },
  shoulder_waist: {
    what: "Shoulder circumference ÷ waist circumference. The defining Classic silhouette.",
    how: "Two levers: side delt + back specialization (numerator) and waist control via vacuum work + low BF (denominator).",
  },
  chest_waist: {
    what: "Chest circumference ÷ waist circumference. Reeves' classical ideal is 1.48; modern Classic winners run 1.74+.",
    how: "Upper-chest emphasis (incline pressing) + waist control. Dropping BF lowers waist circumference proportionally.",
  },
  arm_calf_neck_parity: {
    what: "Reeves' equal-circumference rule — arm, calf, and neck should match. Classic judges look for it specifically.",
    how: "Identify the smallest of the three and run a structural-priority cycle on it. This is a 5-year project at your frame; tag the lagging site as a permanent priority muscle.",
  },
  illusion_score: {
    what: "X-frame ratio: (shoulders × hips) ÷ waist². Captures the silhouette that lets a lighter athlete beat a heavier one with worse proportions.",
    how: "Driven by the same proportions as V-taper — shoulders/back up, waist down. Hips matter too: glute training contributes to the X.",
  },
  hqi: {
    what: "Hypertrophy Quality Index — visibility-weighted average of how close each judged site is to your tier's ideal lean circumference.",
    how: "Run diagnostics regularly so this number is fresh. Per-site gap analysis (Muscle Gaps card) tells you which sites are dragging the average.",
  },
  training_years: {
    what: "Chronological years of consistent training. Soft gate — won't block tier classification on its own but matters for projection math.",
    how: "Time. Genuine training years can't be shortcut. Adherence factors (consistency × intensity × programming) determine your effective training age.",
  },
  mass_distribution: {
    what: "Worst-site percentage of ideal across your seven primary sites. Catches lopsided physiques that score well on average HQI but have one site lagging badly.",
    how: "Open the Muscle Gaps card, identify the lowest pct site, and run a specialization cycle focused there.",
  },
  conditioning_pct: {
    what: "Fraction of the offseason→stage body-fat range you've closed. 0% = at offseason ceiling; 100% = at stage target BF.",
    how: "Cut. Maintain a controlled deficit until BF reaches your division's stage target. Carb-cycle to preserve performance through the cut.",
  },
};

const STATE: Record<ReadinessState, { label: string; badge: string; ring: string }> = {
  not_ready:   { label: "Not Ready",    badge: "bg-viltrum-limestone text-viltrum-iron",     ring: "border-viltrum-ash" },
  developing:  { label: "Developing",   badge: "bg-viltrum-adriatic-bg text-viltrum-adriatic", ring: "border-viltrum-adriatic/30" },
  approaching: { label: "Approaching",  badge: "bg-viltrum-aureus-bg text-viltrum-aureus",   ring: "border-viltrum-aureus/30" },
  stage_ready: { label: "Stage Ready",  badge: "bg-viltrum-laurel-bg text-viltrum-laurel",   ring: "border-viltrum-laurel/40" },
};

// V3 — 4-tier status classification per metric. Lets the user see at a
// glance which gates are met, which are close, which need work, and which
// are far from target. Previously every unmet metric rendered the same
// "red bar" regardless of distance, so a 99%-complete metric looked no
// different from a 20%-complete one.
type MetricStatus = "met" | "close" | "developing" | "far";

function classifyMetric(pct: number, met: boolean): MetricStatus {
  if (met) return "met";
  if (pct >= 0.85) return "close";
  if (pct >= 0.60) return "developing";
  return "far";
}

const STATUS_COPY: Record<MetricStatus, {
  label: string; glyph: string; textClass: string; barClass: string; rowBorderClass: string;
}> = {
  met: {
    label: "Met",
    glyph: "✓",
    textClass: "text-viltrum-laurel",
    barClass: "bg-viltrum-laurel",
    rowBorderClass: "border-l-viltrum-laurel",
  },
  close: {
    label: "Close",
    glyph: "◐",
    textClass: "text-viltrum-aureus",
    barClass: "bg-viltrum-aureus",
    rowBorderClass: "border-l-viltrum-aureus",
  },
  developing: {
    label: "Developing",
    glyph: "◔",
    textClass: "text-viltrum-adriatic",
    barClass: "bg-viltrum-adriatic",
    rowBorderClass: "border-l-viltrum-adriatic",
  },
  far: {
    label: "Far",
    glyph: "○",
    textClass: "text-viltrum-centurion",
    barClass: "bg-viltrum-centurion",
    rowBorderClass: "border-l-viltrum-centurion",
  },
};

const METRIC_LABELS: Record<string, string> = {
  weight_cap_pct:       "Stage-projected weight",
  ffmi:                 "FFMI",
  shoulder_waist:       "Shoulder : Waist",
  chest_waist:          "Chest : Waist",
  arm_calf_neck_parity: "Arm · Calf · Neck parity",
  illusion_score:       "Illusion (X-frame)",
  hqi:                  "HQI (last diagnostic)",
  training_years:       "Training years",
  mass_distribution:    "Mass distribution (worst site)",
  conditioning_pct:     "Conditioning progress",
};

const GROUPS: Array<{ title: string; keys: string[] }> = [
  { title: "Mass",        keys: ["weight_cap_pct", "ffmi", "mass_distribution"] },
  { title: "Proportions", keys: ["shoulder_waist", "chest_waist", "arm_calf_neck_parity", "illusion_score"] },
  { title: "Readiness",   keys: ["conditioning_pct", "hqi", "training_years"] },
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
  if (key === "illusion_score") return m.current.toFixed(2);
  if (key === "conditioning_pct") return `${(m.current * 100).toFixed(0)}%`;
  return String(m.current);
}

function formatTarget(key: string, m: MetricShape): string {
  if (key === "weight_cap_pct") return `${(m.target * 100).toFixed(0)}%`;
  if (key === "arm_calf_neck_parity") return `${m.target.toFixed(2)}"`;
  if (key === "training_years") return `${m.target.toFixed(0)} yr`;
  if (key === "mass_distribution") return `${(m.target * 100).toFixed(0)}%`;
  if (key === "illusion_score") return m.target.toFixed(2);
  if (key === "conditioning_pct") return `${(m.target * 100).toFixed(0)}%`;
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

  // V3 — compute per-metric status distribution for the at-a-glance summary.
  // Shows the user "1 met · 3 close · 2 developing · 4 far" so they see
  // how many gates are in each band without counting checkmarks.
  const statusCounts: Record<MetricStatus, number> = { met: 0, close: 0, developing: 0, far: 0 };
  for (const m of Object.values(readiness.per_metric)) {
    if (!m) continue;
    const s = classifyMetric(m.pct_progress, m.met);
    statusCounts[s]++;
  }

  // V4 / Claude Design — click-to-expand gate detail panel. Only one open
  // at a time. Toggling the same key closes it.
  const [openGate, setOpenGate] = useState<string | null>(null);
  const tierLabel = readiness.tier.replace(/_/g, " ");

  // V2 recalibration notice — shown once per browser session since the
  // readiness metric count grew (8 → 10/11) and users need to know why
  // their pct_met looks lower at first glance.
  const showV2Notice =
    typeof window !== "undefined" &&
    readiness.per_metric.illusion_score &&
    !window.localStorage.getItem("v2_readiness_recalibrated_seen");

  return (
    <div className="jungle-card">
      {showV2Notice && (
        <div className="mb-3 p-2 rounded-card bg-viltrum-blush/60 border border-viltrum-centurion/40 text-[11px] text-viltrum-obsidian flex items-start gap-2">
          <span className="shrink-0 mt-0.5">ⓘ</span>
          <div className="flex-1">
            Recalibrated with v2 metrics — adds Illusion (X-frame) and
            Conditioning %. Your readiness % may look different from the
            previous version; the denominator is larger now.
          </div>
          <button
            onClick={() => {
              window.localStorage.setItem("v2_readiness_recalibrated_seen", "1");
              // Force a re-render by using a no-op state update if needed —
              // the notice disappears on next render anyway once localStorage is set.
            }}
            className="text-[10px] uppercase tracking-[2px] text-viltrum-travertine hover:text-viltrum-obsidian"
          >
            Got it
          </button>
        </div>
      )}
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

      {/* V3 — Status distribution strip. Tells the user at a glance how
          many gates are met / close / developing / far without them having
          to count checkmarks down the list. */}
      <div className="py-3 border-b border-viltrum-ash">
        <div className="text-[10px] uppercase tracking-[2px] text-viltrum-travertine mb-2">
          Gate status
        </div>
        <div className="grid grid-cols-4 gap-1.5">
          {(["met", "close", "developing", "far"] as MetricStatus[]).map((s) => {
            const copy = STATUS_COPY[s];
            const count = statusCounts[s];
            const dim = count === 0 ? "opacity-40" : "";
            return (
              <div
                key={s}
                className={`rounded-card border border-viltrum-ash px-2 py-1.5 text-center ${dim}`}
              >
                <div className={`text-[16px] leading-none ${copy.textClass}`}>
                  {copy.glyph}
                </div>
                <div className="text-[10px] font-mono tabular-nums text-viltrum-obsidian mt-0.5">
                  {count}
                </div>
                <div className="text-[9px] uppercase tracking-[0.1em] text-viltrum-travertine">
                  {copy.label}
                </div>
              </div>
            );
          })}
        </div>
      </div>

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

      {/* Metric groups — two columns on desktop, stacked on mobile.
          V3: each row carries its status glyph + color in a left border
          stripe so the state is legible without having to read the numbers. */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-4 py-4">
        {GROUPS.map((group) => (
          <div key={group.title} className="space-y-2">
            <h4 className="h-section">{group.title}</h4>
            {group.keys.map((key) => {
              const m = readiness.per_metric[key] as MetricShape | undefined;
              if (!m) return null;
              const pct = Math.round(m.pct_progress * 100);
              const label = METRIC_LABELS[key] || key;
              const status = classifyMetric(m.pct_progress, m.met);
              const copy = STATUS_COPY[status];
              const isOpen = openGate === key;
              const detail = GATE_DETAILS[key];
              const gapHint = (() => {
                if (m.met) return `Met — at or above the ${tierLabel} threshold of ${formatTarget(key, m)}.`;
                const cur = formatMetricValue(key, m);
                const tgt = formatTarget(key, m);
                return `At ${cur} of ${tgt} — ${100 - pct}% to gate. ${pct >= 85 ? "Close." : pct >= 60 ? "Developing." : "Far."}`;
              })();
              return (
                <div key={key} className={`pl-2 border-l-[3px] ${copy.rowBorderClass}`}>
                  <button
                    type="button"
                    onClick={() => setOpenGate(isOpen ? null : key)}
                    className="w-full text-left hover:bg-viltrum-alabaster transition-colors rounded -mx-1 px-1 py-0.5 focus:outline-none focus-visible:ring-1 focus-visible:ring-viltrum-obsidian"
                    aria-expanded={isOpen}
                  >
                    <div className="flex justify-between items-baseline gap-2 text-[11px]">
                      <div className="flex items-baseline gap-1.5 min-w-0">
                        <span
                          className={`text-[13px] leading-none flex-shrink-0 ${copy.textClass}`}
                          aria-label={copy.label}
                        >
                          {copy.glyph}
                        </span>
                        <span className="text-viltrum-iron truncate">{label}</span>
                        <span
                          aria-hidden
                          className={`ml-1 text-[9px] text-viltrum-pewter transition-transform ${isOpen ? "rotate-90" : ""}`}
                        >
                          ▸
                        </span>
                      </div>
                      <span className={m.met ? "text-viltrum-laurel font-semibold shrink-0" : "text-viltrum-obsidian shrink-0"}>
                        <span className="font-mono">{formatMetricValue(key, m)}</span>
                        <span className="text-viltrum-pewter"> / </span>
                        <span className="font-mono">{formatTarget(key, m)}</span>
                      </span>
                    </div>
                    <div className="flex items-center gap-2 mt-1">
                      <div className="flex-1 h-1 bg-viltrum-limestone rounded">
                        <div
                          className={`h-1 rounded ${copy.barClass}`}
                          style={{ width: `${Math.min(100, pct)}%` }}
                        />
                      </div>
                      <span className={`text-[9px] font-mono tabular-nums ${copy.textClass} flex-shrink-0 w-9 text-right`}>
                        {pct}%
                      </span>
                    </div>
                  </button>
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
                  {/* V4 / Claude Design — click-to-expand detail panel */}
                  {isOpen && detail && (
                    <div
                      className="mt-2 p-2.5 rounded-card border border-viltrum-ash bg-viltrum-alabaster"
                      style={{ borderLeftWidth: 0 }}
                    >
                      <div className="space-y-1.5">
                        <div>
                          <div className="text-[9px] uppercase tracking-[0.15em] text-viltrum-travertine">What it is</div>
                          <p className="text-[11px] text-viltrum-iron leading-snug body-serif-sm italic mt-0.5">{detail.what}</p>
                        </div>
                        <div>
                          <div className="text-[9px] uppercase tracking-[0.15em] text-viltrum-travertine">Why at {tierLabel}</div>
                          <p className={`text-[11px] leading-snug mt-0.5 ${copy.textClass}`}>{gapHint}</p>
                        </div>
                        <div>
                          <div className="text-[9px] uppercase tracking-[0.15em] text-viltrum-travertine">How to close it</div>
                          <p className="text-[11px] text-viltrum-iron leading-snug mt-0.5">{detail.how}</p>
                        </div>
                      </div>
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
              {/* V2.S4 — surface logistic-model inputs so the user can
                  see why the projection landed where it did. */}
              {projection.t_effective_years != null && (
                <span className="block text-[10px] text-viltrum-travertine mt-0.5">
                  t<sub>eff</sub> {projection.t_effective_years} yr
                  {projection.ceiling_lbm_kg_used != null && (
                    <> · ceiling {projection.ceiling_lbm_kg_used} kg LBM</>
                  )}
                  {projection.muscle_fraction_used != null && (
                    <> · p-ratio {Math.round(projection.muscle_fraction_used * 100)}%</>
                  )}
                </span>
              )}
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
