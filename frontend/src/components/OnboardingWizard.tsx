"use client";

import { useState } from "react";

// ─── Wizard steps ─────────────────────────────────────────────────────────────

type StepGlyph = "dashboard" | "checkin" | "training" | "program" | "nutrition" | "settings";

const WIZARD_STEPS: Array<{
  key: StepGlyph;
  title: string;
  eyebrow: string;
  description: string;
  highlight: string;
}> = [
  {
    key: "dashboard",
    eyebrow: "I",
    title: "Your Dashboard",
    description:
      "Your home base. At a glance: today's workout, your macros, your Physique Development Score (0–100 against your division), and the muscles asking for attention.",
    highlight: "PDS updates automatically after every check-in.",
  },
  {
    key: "checkin",
    eyebrow: "II",
    title: "Daily Check-In",
    description:
      "Each morning, log fasted weight, sleep, and soreness. About thirty seconds. The system reads this and adjusts training and nutrition the way a coach would.",
    highlight: "Consistency is the variable that matters most.",
  },
  {
    key: "training",
    eyebrow: "III",
    title: "Your Workouts",
    description:
      "The Training tab holds today's session. Tap Start to enter Now Playing — it walks you set by set with weight, reps, and RPE. Rest timers run themselves.",
    highlight: "Gym Mode enlarges touch targets for lifting.",
  },
  {
    key: "program",
    eyebrow: "IV",
    title: "Your Program",
    description:
      "Training runs in six-week cycles: progressive volume, then deload. The Program tab shows the full schedule, prioritized muscles, and where you are in the arc.",
    highlight: "Your split orbits around your weakest links.",
  },
  {
    key: "nutrition",
    eyebrow: "V",
    title: "Meal Plan & Macros",
    description:
      "Calories and macros are set by phase — bulk, cut, maintain. The meal planner builds real meals in grams from the foods you chose. Training and rest days diverge.",
    highlight: "Regenerate the plan from the Nutrition tab anytime.",
  },
  {
    key: "settings",
    eyebrow: "VI",
    title: "Settings & Preferences",
    description:
      "Update competition date, division, food preferences, or training schedule whenever life shifts. All three engines recalculate on save.",
    highlight: "Set a show date to arm the peak-week protocol.",
  },
];

const STORAGE_KEY = "coronado_wizard_completed";

function storageKeyFor(userId?: string) {
  return userId ? `${STORAGE_KEY}_${userId}` : STORAGE_KEY;
}

// ─── Glyph — small editorial mark per step ────────────────────────────────────

function StepGlyph({ kind }: { kind: StepGlyph }) {
  const common = "w-6 h-6";
  const stroke = "#C44040";
  switch (kind) {
    case "dashboard":
      return (
        <svg className={common} viewBox="0 0 24 24" fill="none" stroke={stroke} strokeWidth={1.5} strokeLinecap="round">
          <path d="M3 13a9 9 0 1118 0" />
          <path d="M12 13l4-4" />
          <circle cx="12" cy="13" r="1" fill={stroke} />
        </svg>
      );
    case "checkin":
      return (
        <svg className={common} viewBox="0 0 24 24" fill="none" stroke={stroke} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
          <rect x="5" y="4" width="14" height="17" rx="1.5" />
          <path d="M9 4v2h6V4" />
          <path d="M8.5 11.5l2 2 4-4" />
        </svg>
      );
    case "training":
      return (
        <svg className={common} viewBox="0 0 24 24" fill="none" stroke={stroke} strokeWidth={1.5} strokeLinecap="round">
          <path d="M4 9v6M20 9v6M7 7v10M17 7v10M7 12h10" />
        </svg>
      );
    case "program":
      return (
        <svg className={common} viewBox="0 0 24 24" fill="none" stroke={stroke} strokeWidth={1.5} strokeLinecap="round">
          <rect x="4" y="5" width="16" height="16" rx="1.5" />
          <path d="M4 10h16M9 3v4M15 3v4" />
        </svg>
      );
    case "nutrition":
      return (
        <svg className={common} viewBox="0 0 24 24" fill="none" stroke={stroke} strokeWidth={1.5} strokeLinecap="round">
          <path d="M12 3c3 0 5 2.5 5 6a5 5 0 01-1 3c2 1 3 3 3 5.5 0 2-1 3.5-3 3.5H8c-2 0-3-1.5-3-3.5C5 15 6 13 8 12a5 5 0 01-1-3c0-3.5 2-6 5-6z" />
        </svg>
      );
    case "settings":
      return (
        <svg className={common} viewBox="0 0 24 24" fill="none" stroke={stroke} strokeWidth={1.5} strokeLinecap="round">
          <circle cx="12" cy="12" r="3" />
          <path d="M12 3v2M12 19v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M3 12h2M19 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4" />
        </svg>
      );
  }
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
      localStorage.setItem(STORAGE_KEY, "1");
    } catch { /* ignore */ }
    onDismiss();
  }

  return (
    <div
      className="fixed inset-0 bg-obsidian/55 backdrop-blur-[2px] z-50 flex items-center justify-center p-4"
      onClick={complete}
    >
      <div
        className="bg-white border border-ash rounded-card w-full max-w-sm p-7 space-y-6 shadow-[0_24px_60px_rgba(26,24,22,0.18)]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="h-section text-obsidian">Viltrum</span>
            <span className="h-section text-travertine">Tour</span>
          </div>
          <button
            onClick={complete}
            className="text-travertine hover:text-charcoal transition-colors text-[10px] tracking-[0.15em] uppercase"
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
              className={`h-1 rounded-full transition-all ${
                i === step
                  ? "bg-legion w-6"
                  : i < step
                  ? "bg-terracotta w-1.5"
                  : "bg-ash w-1.5"
              }`}
              aria-label={`Step ${i + 1}`}
            />
          ))}
        </div>

        {/* Content */}
        <div className="text-center space-y-4">
          <div className="mx-auto w-11 h-11 rounded-full bg-blush flex items-center justify-center">
            <StepGlyph kind={current.key} />
          </div>
          <div className="space-y-1.5">
            <p className="h-section text-travertine">Step {current.eyebrow}</p>
            <h2 className="h-display-sm">{current.title}</h2>
          </div>
          <p className="body-serif-sm text-iron">{current.description}</p>
          <div className="border-l-2 border-terracotta bg-blush/60 px-3 py-2 text-left">
            <p className="text-[11px] text-centurion font-medium leading-snug">{current.highlight}</p>
          </div>
        </div>

        {/* Navigation */}
        <div className="flex gap-3">
          {step > 0 && (
            <button
              onClick={() => setStep((s) => s - 1)}
              className="btn-secondary flex-1 text-sm"
            >
              Back
            </button>
          )}
          <button
            onClick={handleNext}
            className="btn-accent flex-1 text-sm"
          >
            {isLast ? "Get Started" : "Next"}
          </button>
        </div>

        <p className="text-center text-[10px] tracking-[0.2em] uppercase text-travertine">
          {step + 1} of {WIZARD_STEPS.length}
        </p>
      </div>
    </div>
  );
}

// ─── Helper to check if wizard should show ───────────────────────────────────

export function shouldShowWizard(userId?: string): boolean {
  try {
    if (localStorage.getItem(storageKeyFor(userId))) return false;
    if (localStorage.getItem(STORAGE_KEY)) return false;
    return true;
  } catch {
    return false;
  }
}
