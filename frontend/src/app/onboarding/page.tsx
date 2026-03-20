"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import Logo from "@/components/Logo";

const DIVISIONS = [
  { value: "mens_open", label: "Men's Open" },
  { value: "classic_physique", label: "Classic Physique" },
  { value: "mens_physique", label: "Men's Physique" },
  { value: "womens_figure", label: "Women's Figure" },
  { value: "womens_bikini", label: "Women's Bikini" },
  { value: "womens_physique", label: "Women's Physique" },
];

const SPLITS = [
  { value: "auto", label: "Auto — Let the engine decide" },
  { value: "ppl", label: "Push/Pull/Legs" },
  { value: "upper_lower", label: "Upper/Lower" },
  { value: "full_body", label: "Full Body" },
  { value: "bro_split", label: "Bro Split" },
];

const CORE_LIFTS = [
  "Bench press",
  "Barbell back squat",
  "Barbell Deadlift",
  "Military press",
  "Barbell bent-over row",
];

const TAPE_SITES = [
  "neck", "shoulders", "chest", "left_bicep", "right_bicep",
  "left_forearm", "right_forearm", "waist", "hips",
  "left_thigh", "right_thigh", "left_calf", "right_calf",
];

const SF_SITES = [
  "chest", "midaxillary", "tricep", "subscapular",
  "abdominal", "suprailiac", "thigh",
];

export default function OnboardingPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Step 1
  const [sex, setSex] = useState("male");
  const [age, setAge] = useState("");
  const [heightCm, setHeightCm] = useState("");
  const [division, setDivision] = useState("mens_open");
  const [experience, setExperience] = useState("");
  const [competitionDate, setCompetitionDate] = useState("");
  const [wrist, setWrist] = useState("");
  const [ankle, setAnkle] = useState("");

  // Step 2
  const [bodyWeight, setBodyWeight] = useState("");
  const [tape, setTape] = useState<Record<string, string>>({});
  const [skinfolds, setSkinfolds] = useState<Record<string, string>>({});

  // Step 3
  const [strengths, setStrengths] = useState<Record<string, string>>({});

  // Step 4
  const [daysPerWeek, setDaysPerWeek] = useState("4");
  const [split, setSplit] = useState("auto");
  const [mealCount, setMealCount] = useState("4");
  const [cheatMealsPerWeek, setCheatMealsPerWeek] = useState("0");
  const [intraWorkoutNutrition, setIntraWorkoutNutrition] = useState(false);
  const [displayName, setDisplayName] = useState("");
  const [cardioMachine, setCardioMachine] = useState("treadmill");

  useEffect(() => {
    if (!authLoading && !user) {
      router.push("/auth/login");
    }
  }, [authLoading, user, router]);

  if (authLoading || !user) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-canopy-gradient">
        <p className="text-jungle-muted">Loading...</p>
      </main>
    );
  }

  const submitStep = async () => {
    setError("");
    setLoading(true);
    try {
      if (step === 1) {
        await api.post("/onboarding/profile", {
          sex,
          age: age ? parseInt(age) : null,
          height_cm: parseFloat(heightCm),
          division,
          competition_date: competitionDate ? competitionDate : null,
          training_experience_years: parseInt(experience) || 0,
          wrist_circumference_cm: wrist ? parseFloat(wrist) : null,
          ankle_circumference_cm: ankle ? parseFloat(ankle) : null,
        });
      } else if (step === 2) {
        const tapeNums: Record<string, number | null> = {};
        for (const [k, v] of Object.entries(tape)) {
          tapeNums[k] = v ? parseFloat(v) : null;
        }
        const sfNums: Record<string, number | null> = {};
        for (const [k, v] of Object.entries(skinfolds)) {
          sfNums[`sf_${k}`] = v ? parseFloat(v) : null;
        }
        await api.post("/onboarding/measurements", {
          body_weight_kg: parseFloat(bodyWeight),
          ...tapeNums,
          ...sfNums,
        });
      } else if (step === 3) {
        const baselines = Object.entries(strengths)
          .filter(([, v]) => v)
          .map(([name, v]) => ({ exercise_name: name, one_rm_kg: parseFloat(v) }));
        if (baselines.length > 0) {
          await api.post("/onboarding/strength-baselines", { baselines });
        }
      } else if (step === 4) {
        await api.post("/onboarding/preferences", {
          training_days_per_week: parseInt(daysPerWeek),
          preferred_split: split,
          meal_count: parseInt(mealCount),
          cheat_meals_per_week: parseInt(cheatMealsPerWeek),
          intra_workout_nutrition: intraWorkoutNutrition,
          display_name: displayName,
          cardio_machine: cardioMachine,
        });
      } else if (step === 5) {
        await api.post("/onboarding/complete");
        router.push("/dashboard");
        return;
      }
      setStep(step + 1);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "An error occurred");
    } finally {
      setLoading(false);
    }
  };

  const stepTitles = ["Profile", "Measurements", "Strength", "Preferences", "Launch"];

  return (
    <main className="min-h-screen bg-canopy-gradient p-4 sm:p-8">
      <div className="max-w-2xl mx-auto space-y-6">
        <div className="text-center">
          <Logo size="md" />
          <h2 className="text-xl font-semibold mt-4">
            {stepTitles[step - 1]}{" "}
            <span className="text-jungle-accent">({step}/5)</span>
          </h2>
          {/* Progress bar */}
          <div className="flex gap-1.5 justify-center mt-4">
            {[1, 2, 3, 4, 5].map((s) => (
              <div
                key={s}
                className={`h-1.5 rounded-full transition-all duration-300 ${
                  s <= step
                    ? "w-14 bg-jungle-accent"
                    : "w-10 bg-jungle-border"
                }`}
              />
            ))}
          </div>
        </div>

        <div className="card space-y-4">
          {error && (
            <p className="text-jungle-danger text-sm text-center bg-jungle-danger/10 py-2 rounded-lg">
              {error}
            </p>
          )}

          {step === 1 && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="label-field">Sex</label>
                <select value={sex} onChange={(e) => setSex(e.target.value)} className="input-field">
                  <option value="male">Male</option>
                  <option value="female">Female</option>
                </select>
              </div>
              <div>
                <label className="label-field">Age</label>
                <input type="number" value={age} onChange={(e) => setAge(e.target.value)} className="input-field" placeholder="25" />
              </div>
              <div>
                <label className="label-field">Height (cm)</label>
                <input type="number" value={heightCm} onChange={(e) => setHeightCm(e.target.value)} required className="input-field" placeholder="178" />
              </div>
              <div>
                <label className="label-field">Division</label>
                <select value={division} onChange={(e) => setDivision(e.target.value)} className="input-field">
                  {DIVISIONS.map((d) => (
                    <option key={d.value} value={d.value}>{d.label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="label-field">Experience (years)</label>
                <input type="number" value={experience} onChange={(e) => setExperience(e.target.value)} className="input-field" placeholder="5" />
              </div>
              <div>
                <label className="label-field">Target Comm Date (optional)</label>
                <input type="date" value={competitionDate} onChange={(e) => setCompetitionDate(e.target.value)} className="input-field" />
              </div>
              <div>
                <label className="label-field">Wrist Circumference (cm)</label>
                <input type="number" step="0.1" value={wrist} onChange={(e) => setWrist(e.target.value)} className="input-field" placeholder="17.5" />
              </div>
              <div>
                <label className="label-field">Ankle Circumference (cm)</label>
                <input type="number" step="0.1" value={ankle} onChange={(e) => setAnkle(e.target.value)} className="input-field" placeholder="23.0" />
              </div>
            </div>
          )}

          {step === 2 && (
            <>
              <div>
                <label className="label-field">Body Weight (kg)</label>
                <input type="number" step="0.1" value={bodyWeight} onChange={(e) => setBodyWeight(e.target.value)} required className="input-field" placeholder="90.0" />
              </div>
              <h3 className="text-sm font-semibold text-jungle-accent uppercase tracking-wide pt-2">Tape Measurements (cm)</h3>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                {TAPE_SITES.map((site) => (
                  <div key={site}>
                    <label className="block text-xs text-jungle-muted mb-1 capitalize">{site.replace(/_/g, " ")}</label>
                    <input type="number" step="0.1" value={tape[site] || ""} onChange={(e) => setTape({ ...tape, [site]: e.target.value })} className="input-field text-sm" />
                  </div>
                ))}
              </div>
              <h3 className="text-sm font-semibold text-jungle-accent uppercase tracking-wide pt-2">Skinfolds (mm) — optional, can add later via check-in</h3>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                {SF_SITES.map((site) => (
                  <div key={site}>
                    <label className="block text-xs text-jungle-muted mb-1 capitalize">{site}</label>
                    <input type="number" step="0.1" value={skinfolds[site] || ""} onChange={(e) => setSkinfolds({ ...skinfolds, [site]: e.target.value })} className="input-field text-sm" />
                  </div>
                ))}
              </div>
            </>
          )}

          {step === 3 && (
            <>
              <p className="text-sm text-jungle-muted">Enter estimated 1RM (kg) for each lift</p>
              <div className="space-y-3">
                {CORE_LIFTS.map((lift) => (
                  <div key={lift}>
                    <label className="label-field">{lift}</label>
                    <input type="number" step="0.5" value={strengths[lift] || ""} onChange={(e) => setStrengths({ ...strengths, [lift]: e.target.value })} placeholder="kg" className="input-field" />
                  </div>
                ))}
              </div>
            </>
          )}

          {step === 4 && (
            <div className="space-y-4">
              <div>
                <label className="label-field">Training Days / Week</label>
                <select value={daysPerWeek} onChange={(e) => setDaysPerWeek(e.target.value)} className="input-field">
                  {[3, 4, 5, 6].map((n) => (<option key={n} value={n}>{n} days</option>))}
                </select>
              </div>
              <div>
                <label className="label-field">Preferred Split</label>
                <select value={split} onChange={(e) => setSplit(e.target.value)} className="input-field">
                  {SPLITS.map((s) => (<option key={s.value} value={s.value}>{s.label}</option>))}
                </select>
                {split === "auto" && (
                  <p className="mt-2 text-xs text-jungle-muted bg-jungle-deeper border border-jungle-border rounded-lg px-3 py-2 leading-relaxed">
                    The engine will calculate your optimal split based on your division, lagging muscle groups, and recovery capacity.
                  </p>
                )}
              </div>
              <div>
                <label className="label-field">Meals / Day</label>
                <select value={mealCount} onChange={(e) => setMealCount(e.target.value)} className="input-field">
                  {[3, 4, 5, 6].map((n) => (<option key={n} value={n}>{n} meals</option>))}
                </select>
              </div>
              <div>
                <label className="label-field">Cheat Meals / Week</label>
                <select value={cheatMealsPerWeek} onChange={(e) => setCheatMealsPerWeek(e.target.value)} className="input-field">
                  <option value="0">0 — Strict</option>
                  <option value="1">1</option>
                  <option value="2">2</option>
                  <option value="3">3</option>
                  <option value="4">4+</option>
                </select>
              </div>
              <div>
                <label className="label-field mb-2">During-Workout Nutrition</label>
                <div className="space-y-2">
                  <label className="flex items-center gap-3 cursor-pointer group">
                    <div
                      onClick={() => setIntraWorkoutNutrition(true)}
                      className={`w-5 h-5 rounded border-2 flex items-center justify-center transition-colors ${
                        intraWorkoutNutrition
                          ? "bg-jungle-accent border-jungle-accent"
                          : "border-jungle-border group-hover:border-jungle-accent/60"
                      }`}
                    >
                      {intraWorkoutNutrition && (
                        <svg className="w-3 h-3 text-jungle-dark" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                        </svg>
                      )}
                    </div>
                    <span className="text-sm text-jungle-muted">Yes — I use intra-workout nutrition</span>
                  </label>
                  <label className="flex items-center gap-3 cursor-pointer group">
                    <div
                      onClick={() => setIntraWorkoutNutrition(false)}
                      className={`w-5 h-5 rounded border-2 flex items-center justify-center transition-colors ${
                        !intraWorkoutNutrition
                          ? "bg-jungle-accent border-jungle-accent"
                          : "border-jungle-border group-hover:border-jungle-accent/60"
                      }`}
                    >
                      {!intraWorkoutNutrition && (
                        <svg className="w-3 h-3 text-jungle-dark" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                        </svg>
                      )}
                    </div>
                    <span className="text-sm text-jungle-muted">No — just pre-workout</span>
                  </label>
                </div>
              </div>
              <div>
                <label className="label-field">Your Name (optional)</label>
                <input
                  type="text"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  className="input-field"
                  placeholder="e.g. Alex"
                />
              </div>
              <div>
                <label className="label-field">Cardio Machine</label>
                <select value={cardioMachine} onChange={(e) => setCardioMachine(e.target.value)} className="input-field">
                  <option value="treadmill">Treadmill</option>
                  <option value="stairmaster">StairMaster</option>
                </select>
              </div>
            </div>
          )}

          {step === 5 && (
            <div className="text-center py-8 space-y-4">
              <div className="w-16 h-16 mx-auto rounded-full bg-jungle-primary/20 flex items-center justify-center">
                <svg className="w-8 h-8 text-jungle-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
              </div>
              <h3 className="text-lg font-semibold">Ready to Launch</h3>
              <p className="text-jungle-muted text-sm max-w-sm mx-auto">
                Coronado will run initial diagnostics, compute your Physique
                Development Score, and generate your first training and
                nutrition prescription.
              </p>
            </div>
          )}

          <div className="flex justify-between pt-4 border-t border-jungle-border">
            {step > 1 ? (
              <button onClick={() => setStep(step - 1)} className="btn-secondary">Back</button>
            ) : (
              <div />
            )}
            <button onClick={submitStep} disabled={loading} className="btn-primary disabled:opacity-50">
              {loading ? "Saving..." : step === 5 ? "Launch Coronado" : "Continue"}
            </button>
          </div>
        </div>
      </div>
    </main>
  );
}
