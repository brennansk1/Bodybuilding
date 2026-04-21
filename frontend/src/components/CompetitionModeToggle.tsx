"use client";

import { useState } from "react";
import type { CompetitiveTier, TrainingStatus, NaturalAttainability } from "@/lib/types";

interface Props {
  initialMode: "competition" | "ppm";
  initialDate?: string | null;
  initialTier?: CompetitiveTier | null;
  initialStatus?: TrainingStatus;
  onChange: (payload: {
    mode: "competition" | "ppm";
    competition_date: string | null;
    ppm_enabled: boolean;
    target_tier: CompetitiveTier | null;
    training_status: TrainingStatus;
    acknowledge_natural_gap?: boolean;
  }) => void;
  runAttainabilityCheck?: (tier: CompetitiveTier, status: TrainingStatus) => Promise<NaturalAttainability | null>;
}

const TIER_COPY: Record<CompetitiveTier, { label: string; blurb: string }> = {
  1: { label: "T1 — Local NPC", blurb: "First-show ready. Competitive at local/regional NPC shows." },
  2: { label: "T2 — Regional NPC", blurb: "Top-3 potential at regional shows." },
  3: { label: "T3 — National NPC", blurb: "Class-winner potential at USA / North Americans / Nationals." },
  4: { label: "T4 — Pro Qualifier", blurb: "Pro-card contention. Within 1-3 lb of cap." },
  5: { label: "T5 — Olympia", blurb: "Pro-card holder competing at the highest level." },
};

export default function CompetitionModeToggle({
  initialMode,
  initialDate,
  initialTier,
  initialStatus = "natural",
  onChange,
  runAttainabilityCheck,
}: Props) {
  const [mode, setMode] = useState<"competition" | "ppm">(initialMode);
  const [date, setDate] = useState<string>(initialDate || "");
  const [tier, setTier] = useState<CompetitiveTier>(initialTier || 1);
  const [status, setStatus] = useState<TrainingStatus>(initialStatus);
  const [attainability, setAttainability] = useState<NaturalAttainability | null>(null);
  const [acknowledged, setAcknowledged] = useState(false);
  const [loading, setLoading] = useState(false);

  const pushChange = (overrides: Partial<{
    mode: "competition" | "ppm"; date: string; tier: CompetitiveTier;
    status: TrainingStatus; acknowledged: boolean;
  }> = {}) => {
    const m = overrides.mode ?? mode;
    const d = overrides.date ?? date;
    const t = overrides.tier ?? tier;
    const s = overrides.status ?? status;
    const ack = overrides.acknowledged ?? acknowledged;
    onChange({
      mode: m,
      competition_date: m === "competition" ? (d || null) : null,
      ppm_enabled: m === "ppm",
      target_tier: m === "ppm" ? t : null,
      training_status: s,
      acknowledge_natural_gap: ack,
    });
  };

  const shouldGate = mode === "ppm" && status === "natural" && tier >= 3;

  const refreshAttainability = async (nextTier: CompetitiveTier, nextStatus: TrainingStatus) => {
    if (!runAttainabilityCheck) return;
    if (nextStatus !== "natural" || nextTier < 3) {
      setAttainability(null);
      return;
    }
    setLoading(true);
    try {
      const result = await runAttainabilityCheck(nextTier, nextStatus);
      setAttainability(result);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <button
          type="button"
          onClick={() => { setMode("competition"); pushChange({ mode: "competition" }); }}
          className={`flex-1 px-4 py-2 rounded-md text-sm font-medium border transition ${
            mode === "competition"
              ? "bg-jungle-accent text-jungle-deeper border-jungle-accent"
              : "border-jungle-dim text-jungle-muted hover:border-jungle-accent"
          }`}
        >
          Competition Date
        </button>
        <button
          type="button"
          onClick={() => { setMode("ppm"); pushChange({ mode: "ppm" }); }}
          className={`flex-1 px-4 py-2 rounded-md text-sm font-medium border transition ${
            mode === "ppm"
              ? "bg-jungle-accent text-jungle-deeper border-jungle-accent"
              : "border-jungle-dim text-jungle-muted hover:border-jungle-accent"
          }`}
        >
          PPM — Perpetual Progression
        </button>
      </div>

      {mode === "competition" && (
        <div className="space-y-2">
          <label className="text-sm text-jungle-muted">Show date</label>
          <input
            type="date"
            value={date}
            onChange={(e) => { setDate(e.target.value); pushChange({ date: e.target.value }); }}
            className="w-full bg-jungle-deeper border border-jungle-dim rounded-md px-3 py-2 text-sm"
          />
          <p className="text-xs text-jungle-dim">
            Phase, macros, and peak-week automation will anchor to this date.
          </p>
        </div>
      )}

      {mode === "ppm" && (
        <div className="space-y-3">
          <div>
            <label className="text-sm text-jungle-muted">Target tier</label>
            <div className="grid grid-cols-1 gap-2 mt-1">
              {([1, 2, 3, 4, 5] as CompetitiveTier[]).map((t) => (
                <button
                  type="button"
                  key={t}
                  onClick={() => {
                    setTier(t);
                    pushChange({ tier: t });
                    void refreshAttainability(t, status);
                  }}
                  className={`px-3 py-2 rounded-md border text-left text-sm transition ${
                    tier === t
                      ? "border-jungle-accent bg-jungle-accent/10"
                      : "border-jungle-dim hover:border-jungle-accent"
                  }`}
                >
                  <div className="font-medium">{TIER_COPY[t].label}</div>
                  <div className="text-xs text-jungle-dim mt-0.5">{TIER_COPY[t].blurb}</div>
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="text-sm text-jungle-muted">Training status</label>
            <div className="flex gap-2 mt-1">
              {(["natural", "enhanced"] as TrainingStatus[]).map((s) => (
                <button
                  type="button"
                  key={s}
                  onClick={() => {
                    setStatus(s);
                    pushChange({ status: s });
                    void refreshAttainability(tier, s);
                  }}
                  className={`flex-1 px-3 py-2 rounded-md border text-sm transition ${
                    status === s
                      ? "border-jungle-accent bg-jungle-accent/10"
                      : "border-jungle-dim hover:border-jungle-accent"
                  }`}
                >
                  {s === "natural" ? "Natural" : "Enhanced"}
                </button>
              ))}
            </div>
            <p className="text-xs text-jungle-dim mt-1">
              Enhanced scales MRV/MAV-high by +20% and adjusts tier training-year gates.
            </p>
          </div>

          {shouldGate && (
            <div className="border border-jungle-dim rounded-md p-3 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">Natural attainability check</span>
                {loading && <span className="text-xs text-jungle-dim">Checking…</span>}
              </div>
              {attainability ? (
                <>
                  <p className={`text-sm ${attainability.overall_attainable ? "text-emerald-400" : "text-amber-400"}`}>
                    {attainability.recommendation}
                  </p>
                  <div className="text-xs text-jungle-dim grid grid-cols-2 gap-1">
                    <div>Predicted max stage weight:</div>
                    <div className="font-mono">{attainability.predicted_natural_max_stage_kg} kg</div>
                    <div>{TIER_COPY[tier].label} requires:</div>
                    <div className="font-mono">{attainability.tier_required_stage_kg} kg</div>
                    <div>Predicted FFMI / required:</div>
                    <div className="font-mono">
                      {attainability.predicted_natural_ffmi} / {attainability.tier_ffmi_requirement}
                    </div>
                  </div>
                  {!attainability.overall_attainable && (
                    <label className="flex items-start gap-2 text-xs text-jungle-muted">
                      <input
                        type="checkbox"
                        checked={acknowledged}
                        onChange={(e) => {
                          setAcknowledged(e.target.checked);
                          pushChange({ acknowledged: e.target.checked });
                        }}
                      />
                      I understand this tier may not be naturally attainable for my frame and want to proceed anyway.
                    </label>
                  )}
                </>
              ) : (
                <button
                  type="button"
                  onClick={() => void refreshAttainability(tier, status)}
                  className="text-sm text-jungle-accent underline"
                >
                  Run check
                </button>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
