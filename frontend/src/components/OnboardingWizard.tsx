"use client";

import { useState } from "react";

// ─── Wizard steps ─────────────────────────────────────────────────────────────

const WIZARD_STEPS = [
  {
    key: "dashboard",
    title: "Your Dashboard",
    icon: "📊",
    description:
      "This is your home base. At a glance you'll see today's workout, your macros, your Physique Development Score (a 0-100 rating of how close you are to stage-ready for your division), and which muscles need the most work.",
    highlight: "Your PDS updates automatically after every check-in.",
  },
  {
    key: "checkin",
    title: "Daily Check-In",
    icon: "📋",
    description:
      "Every morning, log your fasted weight, sleep quality, and soreness. This takes about 30 seconds. The system uses this data to adjust your training volume and nutrition — just like a coach reviewing your daily updates.",
    highlight: "Consistency is key — check in daily for the best results.",
  },
  {
    key: "training",
    title: "Your Workouts",
    icon: "🏋️",
    description:
      "Open the Training tab to see today's session. Tap 'Start' to enter Now Playing mode — it guides you set by set with weight, reps, and RPE logging. Rest timers start automatically between sets. Use Gym Mode for bigger buttons during your workout.",
    highlight: "Navigate with arrows to preview upcoming workouts.",
  },
  {
    key: "program",
    title: "Your Program",
    icon: "📅",
    description:
      "Your training runs in 6-week cycles that progressively increase volume, then deload for recovery. The Program tab shows your full schedule, which muscles are prioritized, and where you are in the cycle.",
    highlight: "Your split is designed around your weakest muscle groups.",
  },
  {
    key: "nutrition",
    title: "Meal Plan & Macros",
    icon: "🥩",
    description:
      "Your daily calories, protein, carbs, and fat are calculated based on your phase (bulk, cut, or maintain). The meal planner generates real meals with gram weights using the foods you selected during setup. Training days and rest days have different plans.",
    highlight: "Regenerate your meal plan anytime from the Nutrition tab.",
  },
  {
    key: "settings",
    title: "Settings & Preferences",
    icon: "⚙️",
    description:
      "Update your competition date, division, food preferences, or training schedule anytime. When you save, all three engines recalculate — your program, meals, and scores update automatically.",
    highlight: "Set a competition date to activate the peak week protocol.",
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
