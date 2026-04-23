"use client";

/**
 * TierBadge — compact chip showing current achieved tier with optional
 * target tier shown as an outlined arrow. Drop on any widget that
 * represents tier-scoped progress (TierReadinessCard, MuscleGaps,
 * Heatmap, IllusionCard).
 */

import type { CompetitiveTier } from "@/lib/types";

const TIER_LABEL: Record<CompetitiveTier, string> = {
  1: "T1 · Local",
  2: "T2 · Regional",
  3: "T3 · National",
  4: "T4 · Pro Qualifier",
  5: "T5 · Olympia",
};

const TIER_SHORT: Record<CompetitiveTier, string> = {
  1: "T1", 2: "T2", 3: "T3", 4: "T4", 5: "T5",
};

interface Props {
  /** Accepts narrow `CompetitiveTier` or raw number (from API); unknown values are ignored. */
  achieved?: CompetitiveTier | number | null;
  target?: CompetitiveTier | number | null;
  compact?: boolean;
  className?: string;
}

function coerce(v: CompetitiveTier | number | null | undefined): CompetitiveTier | null {
  if (v == null) return null;
  const n = Math.round(Number(v));
  if (n >= 1 && n <= 5) return n as CompetitiveTier;
  return null;
}

export default function TierBadge(props: Props) {
  const { compact = false, className = "" } = props;
  const achieved = coerce(props.achieved);
  const target = coerce(props.target);
  const hasAchieved = achieved != null;
  const hasTarget = target != null;

  if (!hasAchieved && !hasTarget) return null;

  if (compact) {
    return (
      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] tracking-[0.1em] uppercase border ${className}`}>
        {hasAchieved ? (
          <span className="text-aureus font-semibold">{TIER_SHORT[achieved!]}</span>
        ) : (
          <span className="text-viltrum-pewter">—</span>
        )}
        {hasTarget && (
          <>
            <span className="text-viltrum-pewter mx-0.5">→</span>
            <span className="text-viltrum-iron">{TIER_SHORT[target!]}</span>
          </>
        )}
      </span>
    );
  }

  return (
    <span className={`inline-flex items-center gap-1.5 ${className}`}>
      {hasAchieved && (
        <span
          className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium tracking-wide bg-viltrum-aureus-bg text-aureus border border-aureus/30"
          title={`Currently demonstrated: ${TIER_LABEL[achieved!]}`}
        >
          {TIER_LABEL[achieved!]}
        </span>
      )}
      {hasTarget && hasAchieved && target !== achieved && (
        <span className="text-viltrum-pewter text-[10px]" aria-hidden>→</span>
      )}
      {hasTarget && (!hasAchieved || target !== achieved) && (
        <span
          className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium tracking-wide border border-viltrum-ash text-viltrum-iron"
          title={`Targeting: ${TIER_LABEL[target!]}`}
        >
          {TIER_LABEL[target!]}
        </span>
      )}
    </span>
  );
}
