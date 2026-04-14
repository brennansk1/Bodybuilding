"use client";

import { useState } from "react";

interface Progression {
  exercise: string;
  action: string;
  next_weight_kg: number;
  next_reps: number;
  estimated_1rm: number;
}

interface SessionSummaryProps {
  durationSeconds: number | null;
  totalVolumeKg: number | null;
  setsCompleted: number;
  setsTotal: number;
  musclesTrained: string[];
  progressions: Progression[];
  useLbs?: boolean;
  onSubmitFeedback: (pump: number, difficulty: number, comfort: number) => Promise<void> | void;
  onClose: () => void;
  onGoToDashboard: () => void;
}

const PUMP_LABELS = ["Flat", "Moderate", "Skin-Splitting"];
const DIFFICULTY_LABELS = ["Easy", "Challenging", "Brutal"];
const COMFORT_LABELS = ["Pain", "Stiff", "Good"];

function formatDuration(seconds: number | null): string {
  if (!seconds || seconds <= 0) return "—";
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  if (m < 60) return `${m}:${String(s).padStart(2, "0")}`;
  const h = Math.floor(m / 60);
  const mm = m % 60;
  return `${h}h ${mm}m`;
}

function formatMuscle(m: string): string {
  return m.split("_").map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(" ");
}

export default function SessionSummary({
  durationSeconds,
  totalVolumeKg,
  setsCompleted,
  setsTotal,
  musclesTrained,
  progressions,
  useLbs = false,
  onSubmitFeedback,
  onClose,
  onGoToDashboard,
}: SessionSummaryProps) {
  const [pump, setPump] = useState<number>(2);
  const [difficulty, setDifficulty] = useState<number>(2);
  const [comfort, setComfort] = useState<number>(3);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  const submit = async () => {
    setSubmitting(true);
    try {
      await onSubmitFeedback(pump, difficulty, comfort);
      setSubmitted(true);
    } finally {
      setSubmitting(false);
    }
  };

  const volumeDisplay = totalVolumeKg
    ? useLbs
      ? `${Math.round(totalVolumeKg * 2.20462).toLocaleString()} lbs`
      : `${Math.round(totalVolumeKg).toLocaleString()} kg`
    : "—";

  return (
    <div className="fixed inset-0 z-[70] bg-jungle-dark/95 backdrop-blur-md overflow-y-auto">
      <div className="max-w-2xl mx-auto p-4 sm:p-6 pb-24 space-y-5">
        {/* Header */}
        <div className="text-center pt-4">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-green-500/20 border border-green-500/40 mb-3">
            <span className="text-green-400 text-sm">✓</span>
            <span className="text-green-400 text-xs font-bold uppercase tracking-wider">Session Complete</span>
          </div>
          <h1 className="text-2xl font-bold text-jungle-text">Nice work.</h1>
        </div>

        {/* Subjective feedback (collected first, before stats) */}
        {!submitted && (
          <div className="card space-y-4">
            <div>
              <h2 className="text-sm font-bold text-jungle-text uppercase tracking-wider">How did it go?</h2>
              <p className="text-[11px] text-jungle-dim mt-0.5">
                Rate this session — feeds future volume autoregulation.
              </p>
            </div>

            {/* Pump */}
            <div>
              <div className="flex justify-between items-baseline mb-1">
                <label className="text-xs font-medium text-jungle-muted">Pump Quality</label>
                <span className="text-xs text-jungle-accent font-semibold">{PUMP_LABELS[pump - 1]}</span>
              </div>
              <div className="grid grid-cols-3 gap-2">
                {[1, 2, 3].map((v) => (
                  <button
                    key={v}
                    onClick={() => setPump(v)}
                    className={`py-2 rounded-lg text-xs font-medium border transition-colors ${
                      pump === v
                        ? "bg-jungle-accent/20 border-jungle-accent text-jungle-accent"
                        : "bg-jungle-deeper border-jungle-border text-jungle-muted hover:border-jungle-accent/50"
                    }`}
                  >
                    {PUMP_LABELS[v - 1]}
                  </button>
                ))}
              </div>
            </div>

            {/* Difficulty */}
            <div>
              <div className="flex justify-between items-baseline mb-1">
                <label className="text-xs font-medium text-jungle-muted">Session Difficulty</label>
                <span className="text-xs text-jungle-accent font-semibold">{DIFFICULTY_LABELS[difficulty - 1]}</span>
              </div>
              <div className="grid grid-cols-3 gap-2">
                {[1, 2, 3].map((v) => (
                  <button
                    key={v}
                    onClick={() => setDifficulty(v)}
                    className={`py-2 rounded-lg text-xs font-medium border transition-colors ${
                      difficulty === v
                        ? "bg-jungle-accent/20 border-jungle-accent text-jungle-accent"
                        : "bg-jungle-deeper border-jungle-border text-jungle-muted hover:border-jungle-accent/50"
                    }`}
                  >
                    {DIFFICULTY_LABELS[v - 1]}
                  </button>
                ))}
              </div>
            </div>

            {/* Joint comfort */}
            <div>
              <div className="flex justify-between items-baseline mb-1">
                <label className="text-xs font-medium text-jungle-muted">Joint Comfort</label>
                <span className="text-xs text-jungle-accent font-semibold">{COMFORT_LABELS[comfort - 1]}</span>
              </div>
              <div className="grid grid-cols-3 gap-2">
                {[1, 2, 3].map((v) => (
                  <button
                    key={v}
                    onClick={() => setComfort(v)}
                    className={`py-2 rounded-lg text-xs font-medium border transition-colors ${
                      comfort === v
                        ? "bg-jungle-accent/20 border-jungle-accent text-jungle-accent"
                        : "bg-jungle-deeper border-jungle-border text-jungle-muted hover:border-jungle-accent/50"
                    }`}
                  >
                    {COMFORT_LABELS[v - 1]}
                  </button>
                ))}
              </div>
            </div>

            <button
              onClick={submit}
              disabled={submitting}
              className="btn-primary w-full text-sm py-2.5 disabled:opacity-50"
            >
              {submitting ? "Saving…" : "Save feedback"}
            </button>
          </div>
        )}

        {/* Stats */}
        <div className="card">
          <h2 className="text-sm font-bold text-jungle-text uppercase tracking-wider mb-3">Session stats</h2>
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-jungle-deeper rounded-lg p-3">
              <p className="text-[10px] text-jungle-dim uppercase tracking-wider">Duration</p>
              <p className="text-lg font-bold text-jungle-text">{formatDuration(durationSeconds)}</p>
            </div>
            <div className="bg-jungle-deeper rounded-lg p-3">
              <p className="text-[10px] text-jungle-dim uppercase tracking-wider">Total volume</p>
              <p className="text-lg font-bold text-jungle-text">{volumeDisplay}</p>
            </div>
            <div className="bg-jungle-deeper rounded-lg p-3">
              <p className="text-[10px] text-jungle-dim uppercase tracking-wider">Sets done</p>
              <p className="text-lg font-bold text-jungle-text">{setsCompleted} / {setsTotal}</p>
            </div>
            <div className="bg-jungle-deeper rounded-lg p-3">
              <p className="text-[10px] text-jungle-dim uppercase tracking-wider">Muscles hit</p>
              <p className="text-lg font-bold text-jungle-text">{musclesTrained.length}</p>
            </div>
          </div>
          {musclesTrained.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {musclesTrained.map((m) => (
                <span key={m} className="text-[10px] px-2 py-0.5 rounded-full bg-jungle-accent/15 text-jungle-accent">
                  {formatMuscle(m)}
                </span>
              ))}
            </div>
          )}
        </div>

        {/* Progressions */}
        {progressions.length > 0 && (
          <div className="card space-y-3">
            <div>
              <h2 className="text-sm font-bold text-jungle-text uppercase tracking-wider">
                Next session prescriptions
              </h2>
              <p className="text-[11px] text-jungle-dim mt-0.5">
                Based on what you hit today.
              </p>
            </div>
            <div className="space-y-2">
              {progressions.map((p, i) => (
                <div key={i} className="bg-jungle-deeper rounded-lg p-3 flex items-center justify-between">
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-jungle-text truncate">{p.exercise}</p>
                    <p className="text-[11px] text-jungle-muted">{p.action}</p>
                  </div>
                  <div className="text-right shrink-0 ml-3">
                    <p className="text-sm font-bold text-jungle-accent font-mono">
                      {useLbs
                        ? `${(p.next_weight_kg * 2.20462).toFixed(1)} lbs`
                        : `${p.next_weight_kg.toFixed(1)} kg`}
                    </p>
                    <p className="text-[10px] text-jungle-dim font-mono">× {p.next_reps}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Actions */}
        <div className="grid grid-cols-2 gap-3 pt-2">
          <button
            onClick={onClose}
            className="btn-secondary text-sm py-3"
          >
            Back to workout
          </button>
          <button
            onClick={onGoToDashboard}
            className="btn-primary text-sm py-3"
          >
            Go to dashboard
          </button>
        </div>
      </div>
    </div>
  );
}
