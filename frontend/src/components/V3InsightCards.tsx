"use client";

/**
 * V3 Insight Cards — three dashboard widgets that surface the simulation
 * findings and multi-year projections.
 *
 *   - TierTimingCard      — years-to-target across HIGH/MED/LOW adherence
 *   - LeverSensitivityCard — ranked levers that actually move the needle
 *   - WeightTrendCard     — smoothed BW + weekly rate-of-change
 *
 * Each card is self-fetching (handles its own loading/error states) so the
 * dashboard can drop them in without plumbing shared state.
 */

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type {
  TierProjection,
  SensitivityResponse,
  WeightTrendResponse,
} from "@/lib/types";
function InlineSkeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div className="animate-pulse space-y-2 mt-1">
      {Array.from({ length: lines }).map((_, i) => (
        <div key={i} className="h-3 bg-viltrum-ash rounded" style={{ width: `${60 + (i * 13) % 40}%` }} />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// TierTimingCard
// ---------------------------------------------------------------------------
export function TierTimingCard() {
  const [data, setData] = useState<TierProjection | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.get<TierProjection>("/insights/tier-projection")
      .then(setData)
      .catch((e: Error) => setError(e.message || "Failed to load"))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <InlineSkeleton lines={4} />;
  if (error || !data) {
    return (
      <p className="text-xs text-viltrum-pewter italic text-center py-4">
        Enable PPM and set a target tier to see projections.
      </p>
    );
  }

  const { projections } = data;
  const rows: Array<{ key: "high" | "medium" | "low"; label: string; color: string }> = [
    { key: "high",   label: "HIGH",   color: "text-laurel" },
    { key: "medium", label: "MEDIUM", color: "text-aureus" },
    { key: "low",    label: "LOW",    color: "text-terracotta" },
  ];

  return (
    <div className="space-y-2.5 mt-1">
      {rows.map(({ key, label, color }) => {
        const p = projections[key];
        const years = p?.years;
        const display = years === null || years === undefined
          ? "never"
          : years <= 0 ? "now" : `${years.toFixed(1)} y`;
        return (
          <div key={key} className="flex items-baseline justify-between gap-3">
            <div className="flex items-baseline gap-2">
              <span className={`text-[10px] tracking-[0.15em] uppercase font-semibold ${color}`}>
                {label}
              </span>
              <span className="text-[10px] text-viltrum-pewter">
                ({((p?.adherence_product ?? 0) * 100).toFixed(0)}%)
              </span>
            </div>
            <span className="text-sm font-semibold tabular-nums text-viltrum-obsidian">
              {display}
            </span>
          </div>
        );
      })}
      <p className="body-serif-sm italic text-[11px] text-viltrum-iron pt-2 border-t border-viltrum-ash leading-snug">
        {projections.high.limiting_dimension === "mass"
          ? "Mass-bound — cycles add muscle, don't just refine proportions."
          : "Proportion-bound — specialization cycles will close the gap faster than mass gain."}
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// LeverSensitivityCard
// ---------------------------------------------------------------------------
const IMPACT_COLOR: Record<string, string> = {
  very_high: "text-terracotta border-terracotta",
  high:       "text-aureus border-aureus",
  medium:     "text-adriatic border-adriatic",
  low:        "text-viltrum-pewter border-viltrum-ash",
};

export function LeverSensitivityCard() {
  const [data, setData] = useState<SensitivityResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get<SensitivityResponse>("/insights/sensitivity")
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <InlineSkeleton lines={4} />;
  if (!data) return null;

  return (
    <div className="space-y-3 mt-1">
      {data.levers.slice(0, 4).map((l) => (
        <div key={l.lever} className="space-y-1">
          <div className="flex items-baseline justify-between gap-2">
            <div className="flex items-baseline gap-2 min-w-0">
              <span className="text-[10px] tabular-nums text-viltrum-pewter">#{l.rank}</span>
              <span className="text-[13px] font-medium text-viltrum-obsidian truncate">
                {l.label}
              </span>
            </div>
            <span
              className={`px-1.5 py-0.5 rounded text-[9px] tracking-[0.15em] uppercase border ${IMPACT_COLOR[l.impact] ?? IMPACT_COLOR.medium}`}
            >
              {l.impact.replace("_", " ")}
            </span>
          </div>
          <p className="text-[11px] text-viltrum-iron leading-snug body-serif-sm italic">
            {l.reason}
          </p>
          <p className="text-[11px] text-viltrum-travertine">
            <span className="uppercase tracking-wider text-[9px] mr-1.5">Do</span>
            {l.action}
          </p>
        </div>
      ))}
      {data.coaching_summary && (
        <p className="body-serif-sm italic text-[11px] text-viltrum-iron pt-2 border-t border-viltrum-ash leading-snug">
          {data.coaching_summary}
        </p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// WeightTrendCard
// ---------------------------------------------------------------------------
export function WeightTrendCard() {
  const [data, setData] = useState<WeightTrendResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get<WeightTrendResponse>("/insights/weight-trend?days=90")
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <InlineSkeleton lines={3} />;
  if (!data || data.points.length === 0) {
    return (
      <p className="text-xs text-viltrum-pewter italic text-center py-4">
        Log body weight daily to see your trend.
      </p>
    );
  }

  // Mini sparkline from 14d smoothed
  const sm = data.smoothed_14d.filter((v): v is number => v !== null);
  // Need at least 2 points to render a line; otherwise show the current
  // weight only. Protects against SVG `M0,0 L0,0` degenerate geometry.
  if (sm.length < 2) {
    const latestShort = data.points[data.points.length - 1]?.weight_kg;
    return (
      <div className="py-2">
        <div className="text-2xl font-semibold tabular-nums text-viltrum-obsidian">
          {latestShort?.toFixed(1) ?? "—"}<span className="text-sm ml-1 text-viltrum-pewter">kg</span>
        </div>
        <p className="text-[11px] text-viltrum-iron body-serif-sm italic mt-1">
          Log weight for a few more days to see trend + rate.
        </p>
      </div>
    );
  }
  const min = Math.min(...sm);
  const max = Math.max(...sm);
  const range = Math.max(0.1, max - min);
  const w = 180;
  const h = 40;
  const path = sm.map((v, i) => {
    const x = (i / Math.max(1, sm.length - 1)) * w;
    const y = h - ((v - min) / range) * h;
    return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");

  const rateDisplay = data.weekly_rate_pct !== null
    ? `${data.weekly_rate_pct > 0 ? "+" : ""}${data.weekly_rate_pct.toFixed(2)}% / wk`
    : "—";

  const directionColor: Record<string, string> = {
    cutting: "text-adriatic",
    bulking: "text-aureus",
    steady: "text-laurel",
    unknown: "text-viltrum-pewter",
  };

  const latest = data.points[data.points.length - 1]?.weight_kg;

  return (
    <div className="space-y-2 mt-1">
      <div className="flex items-baseline justify-between gap-3">
        <div>
          <div className="text-2xl font-semibold tabular-nums text-viltrum-obsidian">
            {latest?.toFixed(1) ?? "—"}<span className="text-sm ml-1 text-viltrum-pewter">kg</span>
          </div>
          <div className="text-[10px] uppercase tracking-[0.15em] text-viltrum-travertine">
            Current weight
          </div>
        </div>
        <div className="text-right">
          <div className={`text-sm font-semibold tabular-nums ${directionColor[data.direction] ?? ""}`}>
            {rateDisplay}
          </div>
          <div className="text-[10px] uppercase tracking-[0.15em] text-viltrum-travertine">
            {data.direction}
          </div>
        </div>
      </div>

      <svg width="100%" viewBox={`0 0 ${w} ${h}`} className="text-adriatic">
        <path d={path} fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" />
      </svg>

      {data.in_target_band !== null && (
        <p className="text-[11px] text-viltrum-iron leading-snug body-serif-sm italic">
          {data.in_target_band
            ? "In target band (0.5–1.0% / week)."
            : Math.abs(data.weekly_rate_pct ?? 0) < 0.5
              ? "Slower than target — consider a larger deficit or surplus."
              : "Faster than target — ease off; risk of LBM loss (cut) or fat overshoot (bulk)."}
        </p>
      )}
    </div>
  );
}
