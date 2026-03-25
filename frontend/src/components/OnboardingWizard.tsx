"use client";

import { useState } from "react";

// ─── Wizard steps ─────────────────────────────────────────────────────────────

const WIZARD_STEPS = [
  {
    key: "dashboard",
    title: "Dashboard",
    icon: "📊",
    description:
      "Your home base. See your Physique Development Score, body composition trends, and the Volumetric Ghost Model — a 3D projection of your physique gaps vs. division standards.",
    highlight: "PDS score updates after every check-in.",
  },
  {
    key: "checkin",
    title: "Daily Check-In",
    icon: "📋",
    description:
      "Log your morning weight, HRV, sleep quality, and soreness. This drives all three engines — nutrition adjusts, training volume adapts, and diagnostics update.",
    highlight: "Check in every morning for best results.",
  },
  {
    key: "training",
    title: "Training",
    icon: "🏋️",
    description:
      "Your workout for today, guided set-by-set in Now Playing mode. Tap 'Start' to enter the flow — log weight, reps, and RPE. Rest timers run automatically.",
    highlight: "Progressive overload is tracked every session.",
  },
  {
    key: "program",
    title: "Program",
    icon: "📅",
    description:
      "Your full 6-week mesocycle: MEV → MAV → MRV → Deload. View the calendar month to see all scheduled sessions and tap any day for a workout preview.",
    highlight: "The split adapts to your physique gap priority.",
  },
  {
    key: "nutrition",
    title: "Nutrition",
    icon: "🥩",
    description:
      "Engine 3 prescribes your macros and generates a coach-level meal plan with real foods and gram weights. Training day and rest day plans are separate.",
    highlight: "Carb cycling and fat isolation built-in.",
  },
  {
    key: "settings",
    title: "Settings",
    icon: "⚙️",
    description:
      "Update your competition date, division, and training preferences. Changes re-run the engines and update all prescriptions automatically.",
    highlight: "Set your show date to activate peak week protocol.",
  },
];

const STORAGE_KEY = "coronado_wizard_completed";

function storageKeyFor(userId?: string) {
  return userId ? `${STORAGE_KEY}_${userId}` : STORAGE_KEY;
}

// ─── Component ────────────────────────────────────────────────────────────────

interface OnboardingWizardProps {
  onDismiss: () => void;
  userId?: string;
}

export default function OnboardingWizard({ onDismiss, userId }: OnboardingWizardProps) {
  const [step, setStep] = useState(0);

  const current = WIZARD_STEPS[step];
  const isLast = step === WIZARD_STEPS.length - 1;

  function handleNext() {
    if (isLast) {
      complete();
    } else {
      setStep((s) => s + 1);
    }
  }

  function complete() {
    try {
      localStorage.setItem(storageKeyFor(userId), "1");
      // Also set the generic key for backwards compatibility
      localStorage.setItem(STORAGE_KEY, "1");
    } catch { /* ignore */ }
    onDismiss();
  }

  return (
    <div
      className="fixed inset-0 bg-black/80 z-50 flex items-center justify-center p-4"
      onClick={complete}
    >
      <div
        className="bg-jungle-card border border-jungle-border rounded-2xl w-full max-w-sm p-6 space-y-5 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-jungle-accent font-black text-sm uppercase tracking-widest">Coronado</span>
            <span className="text-jungle-dim text-xs">Quick Tour</span>
          </div>
          <button
            onClick={complete}
            className="text-jungle-dim hover:text-jungle-muted transition-colors text-xs"
          >
            Skip
          </button>
        </div>

        {/* Step dots */}
        <div className="flex gap-1.5 justify-center">
          {WIZARD_STEPS.map((_, i) => (
            <button
              key={i}
              onClick={() => setStep(i)}
              className={`h-1.5 rounded-full transition-all ${
                i === step
                  ? "bg-jungle-accent w-5"
                  : i < step
                  ? "bg-jungle-accent/40 w-1.5"
                  : "bg-jungle-border w-1.5"
              }`}
              aria-label={`Step ${i + 1}`}
            />
          ))}
        </div>

        {/* Content */}
        <div className="text-center space-y-3">
          <div className="text-4xl">{current.icon}</div>
          <h2 className="text-lg font-bold text-jungle-text">{current.title}</h2>
          <p className="text-sm text-jungle-muted leading-relaxed">{current.description}</p>
          <div className="bg-jungle-deeper border border-jungle-accent/20 rounded-lg px-3 py-2">
            <p className="text-[11px] text-jungle-accent font-medium">{current.highlight}</p>
          </div>
        </div>

        {/* Navigation */}
        <div className="flex gap-3">
          {step > 0 && (
            <button
              onClick={() => setStep((s) => s - 1)}
              className="flex-1 py-2.5 rounded-xl border border-jungle-border text-jungle-muted text-sm font-medium hover:border-jungle-muted transition-colors"
            >
              Back
            </button>
          )}
          <button
            onClick={handleNext}
            className="flex-1 py-2.5 rounded-xl bg-jungle-accent text-jungle-dark text-sm font-bold hover:bg-jungle-accent/90 transition-colors active:scale-95"
          >
            {isLast ? "Get Started" : "Next"}
          </button>
        </div>

        <p className="text-center text-[10px] text-jungle-dim">
          {step + 1} of {WIZARD_STEPS.length}
        </p>
      </div>
    </div>
  );
}

// ─── Helper to check if wizard should show ───────────────────────────────────

export function shouldShowWizard(userId?: string): boolean {
  try {
    // Check both user-specific and generic key
    if (localStorage.getItem(storageKeyFor(userId))) return false;
    if (localStorage.getItem(STORAGE_KEY)) return false;
    return true;
  } catch {
    return false;
  }
}
