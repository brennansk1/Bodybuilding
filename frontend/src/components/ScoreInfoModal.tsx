"use client";

/**
 * ScoreInfoModal — central glossary for algorithm/score terms used across
 * the dashboard. Opens from info buttons on widgets. Each entry has:
 *   - plain-English name
 *   - one-sentence "what it tells you"
 *   - "what's good" range
 *   - "how it's computed" (one-liner, no math)
 *
 * Users aren't expected to know what HQI, PDS, Illusion, etc. mean.
 * Every score widget should link here so that's a fixable problem.
 */

import { ReactNode, useEffect, useState } from "react";
import { Info } from "./icons";

export type ScoreKey =
  | "hqi"
  | "pds"
  | "illusion"
  | "xframe"
  | "vtaper"
  | "waist_height"
  | "conditioning_pct"
  | "ffmi"
  | "mev_mav_mrv"
  | "ari"
  | "energy_availability"
  | "parity"
  | "casey_butt"
  | "kouri_band"
  | "ceiling_envelope"
  | "tier_readiness"
  | "carb_cycle"
  | "e1rm"
  | "natural_attainability";

interface Entry {
  name: string;
  what: string;
  good: string;
  how: string;
}

const ENTRIES: Record<ScoreKey, Entry> = {
  hqi: {
    name: "HQI — Hypertrophy Quality Index",
    what: "A single 0–100 score summarizing how close your current lean muscle size is to your division-specific ideal across all judged sites.",
    good: "70+ is competitive at Tier 2, 82+ for Tier 4, 90+ for Olympia-level.",
    how: "Visibility-weighted average of current vs. ideal circumference per site. Sites your division judges weigh more.",
  },
  pds: {
    name: "PDS — Physique Development Score",
    what: "Tracks your progress toward your division's target proportion vector — the ideal shoulder/waist/chest/arm/leg ratios, not raw size.",
    good: "Higher = your shape matches the judged silhouette. Different from HQI (which is about size).",
    how: "Distance in multi-dimensional ratio space between your current vector and your division's ideal.",
  },
  illusion: {
    name: "Illusion Score",
    what: "How much your frame 'tricks the eye' into looking bigger than you are. Combines V-taper, X-frame, and waist-to-height.",
    good: "A strong illusion lets a lighter athlete beat a heavier one with worse proportions.",
    how: "Weighted average of three classical ratios (see V-taper, X-frame, waist:height).",
  },
  xframe: {
    name: "X-Frame",
    what: "The 'X' silhouette pose judges love: wide shoulders + wide hips contrasted against a small waist.",
    good: "2.15 = competitive Tier 2; 2.55 = Olympia range. Formula: (shoulders × hips) ÷ waist².",
    how: "Product of shoulder and hip circumferences divided by the square of waist circumference.",
  },
  vtaper: {
    name: "V-Taper",
    what: "The classic shoulder-to-waist ratio. Grecian ideal is 1.618 (φ); modern Olympia Classic winners run 1.70–1.79.",
    good: "≥1.50 for Tier 2, ≥1.60 for Tier 4, ≥1.618 (Grecian) for Tier 5.",
    how: "Shoulder circumference ÷ waist circumference.",
  },
  waist_height: {
    name: "Waist-to-Height Ratio",
    what: "Tracks whether your waist is small relative to your frame. A small waist is the single biggest Classic Physique differentiator.",
    good: "≤0.43 is competitive. CBum runs 0.40 at 6'1\".",
    how: "Waist circumference ÷ height, both in same units.",
  },
  conditioning_pct: {
    name: "Conditioning %",
    what: "How much of the 'offseason → stage' body-fat range you've closed. 100% = at stage BF; 0% = at offseason ceiling.",
    good: "≥95% on show day for Classic. 70% at 12 weeks out is on track.",
    how: "(Offseason ceiling − current BF%) ÷ (Offseason ceiling − stage target BF%).",
  },
  ffmi: {
    name: "FFMI — Fat-Free Mass Index (normalized)",
    what: "How much muscle you carry for your height. Normalized to 6'0\" so it's comparable across heights.",
    good: "22 = Tier 1, 25.5 = Tier 3, 28.5+ = Olympia. Natural ceiling (Kouri) is ~25.",
    how: "LBM (kg) ÷ height² (m), normalized to standard height.",
  },
  mev_mav_mrv: {
    name: "MEV / MAV / MRV",
    what: "Volume landmarks (weekly working sets per muscle). MEV = minimum effective, MAV = productive range, MRV = maximum recoverable.",
    good: "Cycle progresses MEV → MAV → MRV over 10 weeks, then deload.",
    how: "From RP landmarks, scaled by your experience and enhancement status.",
  },
  ari: {
    name: "ARI — Adherence / Recovery Index",
    what: "A 0–100 composite score of how you're actually recovering vs. how hard you've been training.",
    good: "70+ = green light. <50 = fatigue accumulating; deload suggested.",
    how: "Rolling blend of HRV, resting HR, sleep, training session RPE, and weekly rate-of-loss.",
  },
  energy_availability: {
    name: "Energy Availability",
    what: "Calories left over for physiology after training burn. RED-S territory below 30 kcal/kg LBM.",
    good: "45+ offseason, 30-40 during prep. <25 = hormonal risk.",
    how: "(Dietary kcal − training kcal burn) ÷ LBM (kg).",
  },
  parity: {
    name: "Arm-Calf-Neck Parity",
    what: "The Reeves-standard rule: arm, calf, and neck circumferences should match. Classic judges specifically look at this.",
    good: "All three within 1.5\" = Tier 1. Within 0.5\" = Tier 3+. Matched = Olympia.",
    how: "Max of pairwise absolute differences between the three sites, in inches.",
  },
  casey_butt: {
    name: "Casey Butt Natural Ceiling",
    what: "Your predicted natural-max LBM based on wrist, ankle, and height. Useful as an honesty gate — some tiers aren't naturally attainable for all frames.",
    good: "Informational. If your Butt-predicted stage weight is far below a tier's requirement, that tier is flagged as not naturally reachable.",
    how: "Casey Butt regression (2004): LBM as function of height × (√(wrist/22.67) + √(ankle/17.01)).",
  },
  kouri_band: {
    name: "Kouri FFMI Band",
    what: "The natural FFMI ceiling. Kouri 1995 found 25 is the ~99th percentile of drug-free athletes.",
    good: "Informational. Reaching 25+ is rare; 28+ is physiologically suggestive of enhancement.",
    how: "Kouri et al. FFMI normalization: 6.3 × (1.8 − height_m).",
  },
  ceiling_envelope: {
    name: "Ceiling Envelope",
    what: "Blended natural ceiling from four models: Butt 1st & 4th edition, Kouri FFMI bands, and Berkhan height-in-cm −100.",
    good: "The median is your best single-number estimate. The range tells you uncertainty.",
    how: "Median (and min/max) of all four independent natural-ceiling models.",
  },
  tier_readiness: {
    name: "Tier Readiness",
    what: "How close your physique is to the entry standard for your target competitive tier (local NPC → Olympia).",
    good: "STAGE_READY at 100% of gates met. APPROACHING at 85%.",
    how: "Fraction of tier gates met (weight, FFMI, conditioning, ratios, parity, HQI, training-age).",
  },
  carb_cycle: {
    name: "Carb Cycle (High / Medium / Low)",
    what: "Varying daily carbs by training demand. High = big-muscle day (back/legs), Medium = small-muscle day, Low = rest.",
    good: "Universal in elite prep. Keeps weekly avg at your phase target while front-loading carbs where they matter most.",
    how: "±20% carb swing around phase average. Protein and fat stay constant.",
  },
  e1rm: {
    name: "Estimated 1RM (e1RM)",
    what: "Your projected one-rep max for a lift, derived from submaximal sets. Lets you track strength progression without testing true 1RM.",
    good: "Rising e1RM over 4-week window = training is productive.",
    how: "Epley formula: weight × (1 + reps ÷ 30). Ignored below 60% effort.",
  },
  natural_attainability: {
    name: "Natural Attainability Gate",
    what: "Before selecting a tier, the app checks whether your frame (wrist, ankle, height) can naturally produce the required stage weight + FFMI.",
    good: "Green = attainable. Red = tier is likely beyond natural ceiling for your frame; consider a different tier or federation.",
    how: "Casey Butt + Kouri FFMI vs. tier threshold, with honesty copy on borderline cases.",
  },
};

interface Props {
  open: boolean;
  onClose: () => void;
  scoreKey: ScoreKey | null;
  /** Optional: render multiple entries if the widget covers several concepts */
  extraKeys?: ScoreKey[];
}

export default function ScoreInfoModal({ open, onClose, scoreKey, extraKeys = [] }: Props) {
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onClose]);

  if (!open || !scoreKey) return null;

  const keys = [scoreKey, ...extraKeys];
  const entries = keys.map((k) => ENTRIES[k]).filter(Boolean);

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-viltrum-obsidian/40 backdrop-blur-sm"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
    >
      <div
        className="bg-white border border-viltrum-ash rounded-card shadow-card max-w-lg w-full max-h-[80vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="p-5 border-b border-viltrum-ash flex items-center justify-between">
          <h3 className="h-card text-viltrum-obsidian">What this score means</h3>
          <button
            onClick={onClose}
            className="text-viltrum-pewter hover:text-viltrum-obsidian text-xl leading-none"
            aria-label="Close"
          >
            ×
          </button>
        </div>

        <div className="p-5 space-y-5">
          {entries.map((e, i) => (
            <div key={i} className={i > 0 ? "pt-5 border-t border-viltrum-ash" : ""}>
              <div className="h-display-sm text-viltrum-obsidian mb-2">{e.name}</div>
              <div className="space-y-2 text-[13px] leading-relaxed">
                <p className="text-viltrum-iron">
                  <span className="uppercase tracking-wider text-[10px] text-viltrum-travertine mr-1.5">What</span>
                  {e.what}
                </p>
                <p className="text-viltrum-iron">
                  <span className="uppercase tracking-wider text-[10px] text-laurel mr-1.5">Good</span>
                  {e.good}
                </p>
                <p className="text-viltrum-iron italic body-serif-sm">
                  <span className="uppercase tracking-wider text-[10px] text-viltrum-travertine mr-1.5 not-italic">How</span>
                  {e.how}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/** Button trigger — drop-in replacement for Tooltip when you want the rich modal. */
export function ScoreInfoButton({
  scoreKey,
  extraKeys,
  className = "",
  children,
}: {
  scoreKey: ScoreKey;
  extraKeys?: ScoreKey[];
  className?: string;
  children?: ReactNode;
}) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <button
        type="button"
        onClick={(e) => { e.stopPropagation(); setOpen(true); }}
        aria-label="Explain this score"
        className={`inline-flex items-center text-viltrum-pewter hover:text-viltrum-obsidian focus:outline-none focus-visible:ring-2 focus-visible:ring-viltrum-centurion rounded-full ${className}`}
      >
        {children ?? <Info className="w-4 h-4" />}
      </button>
      <ScoreInfoModal
        open={open}
        onClose={() => setOpen(false)}
        scoreKey={scoreKey}
        extraKeys={extraKeys}
      />
    </>
  );
}
