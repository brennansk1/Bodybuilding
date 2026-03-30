"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import Logo from "@/components/Logo";

const DIVISIONS = [
  { value: "mens_open", label: "Men's Open", desc: "Maximum muscle mass and conditioning" },
  { value: "classic_physique", label: "Classic Physique", desc: "Aesthetic V-taper with size limits" },
  { value: "mens_physique", label: "Men's Physique", desc: "Beach muscle — upper body focus" },
  { value: "womens_figure", label: "Women's Figure", desc: "Athletic muscle with X-frame" },
  { value: "womens_bikini", label: "Women's Bikini", desc: "Lean, toned with rounded glutes" },
  { value: "womens_physique", label: "Women's Physique", desc: "Full muscularity and balance" },
  { value: "wellness", label: "Wellness", desc: "Lower body dominant — large glutes and thighs" },
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
  const [manualBodyFatPct, setManualBodyFatPct] = useState("");
  const [currentPhase, setCurrentPhase] = useState("");

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
  const [fastedCardio, setFastedCardio] = useState(true);
  const [preferredProteins, setPreferredProteins] = useState<string[]>([]);
  const [preferredCarbs, setPreferredCarbs] = useState<string[]>([]);
  const [preferredFats, setPreferredFats] = useState<string[]>([]);

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

    // Step-specific validation
    if (step === 1) {
      if (!heightCm || parseFloat(heightCm) < 100 || parseFloat(heightCm) > 250) {
        setError("Please enter a valid height between 100–250 cm.");
        return;
      }
      if (age && (parseInt(age) < 14 || parseInt(age) > 80)) {
        setError("Age must be between 14 and 80.");
        return;
      }
      if (manualBodyFatPct && (parseFloat(manualBodyFatPct) < 3 || parseFloat(manualBodyFatPct) > 50)) {
        setError("Body fat % must be between 3 and 50.");
        return;
      }
    }
    if (step === 2 && (!bodyWeight || parseFloat(bodyWeight) < 30)) {
      setError("Please enter your body weight (minimum 30 kg).");
      return;
    }

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
          manual_body_fat_pct: manualBodyFatPct ? parseFloat(manualBodyFatPct) : null,
          current_phase: currentPhase || null,
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
          fasted_cardio: fastedCardio,
          preferred_proteins: preferredProteins,
          preferred_carbs: preferredCarbs,
          preferred_fats: preferredFats,
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

  const stepInfo = [
    { title: "Profile", desc: "Tell us about yourself — height, division, and competition goals" },
    { title: "Measurements", desc: "Body weight, tape measurements, and optional skinfold data" },
    { title: "Strength Baselines", desc: "Your current estimated 1RM for key compound lifts" },
    { title: "Preferences", desc: "Training schedule, food choices, and meal plan setup" },
    { title: "Launch", desc: "Review and activate your personalized coaching system" },
  ];

  return (
    <main className="min-h-screen bg-canopy-gradient p-4 sm:p-8">
      <div className="max-w-2xl mx-auto space-y-6">
        <div className="text-center">
          <Logo size="md" />
          <h2 className="text-xl font-semibold mt-4">
            {stepInfo[step - 1].title}
          </h2>
          <p className="text-jungle-dim text-sm mt-1">{stepInfo[step - 1].desc}</p>
          {/* Progress bar */}
          <div className="flex gap-1 justify-center mt-4">
            {stepInfo.map((s, i) => (
              <div key={i} className="flex flex-col items-center gap-1 flex-1">
                <div
                  className={`h-1.5 w-full rounded-full transition-all duration-300 ${
                    i + 1 <= step ? "bg-jungle-accent" : "bg-jungle-border"
                  }`}
                />
                <span className={`text-[8px] font-medium ${i + 1 <= step ? "text-jungle-accent" : "text-jungle-dim"}`}>
                  {s.title}
                </span>
              </div>
            ))}
          </div>
          <p className="text-[10px] text-jungle-dim mt-2">Step {step} of 5</p>
        </div>

        <div className="card space-y-4">
          {error && (
            <p className="text-jungle-danger text-sm text-center bg-jungle-danger/10 py-2 rounded-lg">
              {error}
            </p>
          )}

          {step === 1 && (
            <div className="space-y-5">
              {/* Basic Info */}
              <div>
                <h3 className="text-xs font-semibold text-jungle-accent uppercase tracking-wider mb-3">Basic Info</h3>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
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
                    <label className="label-field">Height (cm) *</label>
                    <input type="number" value={heightCm} onChange={(e) => setHeightCm(e.target.value)} required className="input-field" placeholder="178" />
                  </div>
                </div>
              </div>

              {/* Division Selection */}
              <div>
                <h3 className="text-xs font-semibold text-jungle-accent uppercase tracking-wider mb-3">Competition Division</h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {DIVISIONS.filter(d => sex === "male" ? !d.value.startsWith("womens") && d.value !== "wellness" : d.value.startsWith("womens") || d.value === "wellness").map((d) => (
                    <button
                      key={d.value}
                      type="button"
                      onClick={() => setDivision(d.value)}
                      className={`text-left p-3 rounded-xl border transition-all ${
                        division === d.value
                          ? "border-jungle-accent bg-jungle-accent/10"
                          : "border-jungle-border bg-jungle-deeper hover:border-jungle-accent/40"
                      }`}
                    >
                      <p className={`text-sm font-semibold ${division === d.value ? "text-jungle-accent" : "text-jungle-text"}`}>{d.label}</p>
                      <p className="text-[10px] text-jungle-dim mt-0.5">{d.desc}</p>
                    </button>
                  ))}
                </div>
              </div>

              {/* Experience & Competition */}
              <div>
                <h3 className="text-xs font-semibold text-jungle-accent uppercase tracking-wider mb-3">Experience & Competition</h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="label-field">Training Experience (years)</label>
                    <input type="number" value={experience} onChange={(e) => setExperience(e.target.value)} className="input-field" placeholder="5" />
                  </div>
                  <div>
                    <label className="label-field">Competition Date (optional)</label>
                    <input type="date" value={competitionDate} onChange={(e) => setCompetitionDate(e.target.value)} className="input-field" />
                  </div>
                  <div>
                    <label className="label-field">Current Phase</label>
                    <select value={currentPhase} onChange={(e) => setCurrentPhase(e.target.value)} className="input-field">
                      <option value="">Auto-detect from competition date</option>
                      <option value="bulk">Bulk (Off-Season)</option>
                      <option value="lean_bulk">Lean Bulk</option>
                      <option value="cut">Cut (Contest Prep)</option>
                      <option value="maintain">Maintain</option>
                    </select>
                  </div>
                </div>
              </div>

              {/* Structural Measurements */}
              <div>
                <h3 className="text-xs font-semibold text-jungle-accent uppercase tracking-wider mb-3">Structural Anchors (optional)</h3>
                <p className="text-[10px] text-jungle-dim -mt-2 mb-3">Wrist and ankle circumference help calculate your genetic muscle ceiling. Body fat is estimated from measurements if left blank.</p>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <div>
                    <label className="label-field">Wrist (cm)</label>
                    <input type="number" step="0.1" value={wrist} onChange={(e) => setWrist(e.target.value)} className="input-field" placeholder="17.5" />
                  </div>
                  <div>
                    <label className="label-field">Ankle (cm)</label>
                    <input type="number" step="0.1" value={ankle} onChange={(e) => setAnkle(e.target.value)} className="input-field" placeholder="23.0" />
                  </div>
                  <div>
                    <label className="label-field">Body Fat %</label>
                    <input type="number" step="0.5" min="3" max="50" value={manualBodyFatPct} onChange={(e) => setManualBodyFatPct(e.target.value)} className="input-field" placeholder="e.g. 15" />
                  </div>
                </div>
              </div>
            </div>
          )}

          {step === 2 && (
            <>
              <div>
                <label className="label-field">Body Weight (kg) *</label>
                <input type="number" step="0.1" value={bodyWeight} onChange={(e) => setBodyWeight(e.target.value)} required className="input-field" placeholder="90.0" />
                <p className="text-[10px] text-jungle-dim mt-1">Fasted morning weight is most accurate</p>
              </div>
              <h3 className="text-sm font-semibold text-jungle-accent uppercase tracking-wide pt-2">Tape Measurements (cm)</h3>
              <p className="text-[10px] text-jungle-dim -mt-1 mb-2">Measure relaxed, at the widest point of each site. All measurements are optional but improve accuracy.</p>

              <p className="text-[10px] text-jungle-muted font-semibold uppercase tracking-wider mb-1">Upper Body</p>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-3">
                {["neck", "shoulders", "chest", "left_bicep", "right_bicep", "left_forearm", "right_forearm"].map((site) => (
                  <div key={site}>
                    <label className="block text-xs text-jungle-muted mb-1 capitalize">{site.replace(/_/g, " ")}</label>
                    <input type="number" step="0.1" value={tape[site] || ""} onChange={(e) => setTape({ ...tape, [site]: e.target.value })} className="input-field text-sm" placeholder="cm" />
                  </div>
                ))}
              </div>

              <p className="text-[10px] text-jungle-muted font-semibold uppercase tracking-wider mb-1">Lower Body</p>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                {["waist", "hips", "left_thigh", "right_thigh", "left_calf", "right_calf"].map((site) => (
                  <div key={site}>
                    <label className="block text-xs text-jungle-muted mb-1 capitalize">{site.replace(/_/g, " ")}</label>
                    <input type="number" step="0.1" value={tape[site] || ""} onChange={(e) => setTape({ ...tape, [site]: e.target.value })} className="input-field text-sm" placeholder="cm" />
                  </div>
                ))}
              </div>
              <h3 className="text-sm font-semibold text-jungle-accent uppercase tracking-wide pt-2">Skinfolds (mm) — optional</h3>
              <p className="text-xs text-jungle-dim -mt-2">Use a caliper. Pinch skin + subcutaneous fat (not muscle). Measure on right side of body.</p>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                {SF_SITES.map((site) => {
                  const guides: Record<string, string> = {
                    chest: "Diagonal fold midway between nipple and armpit",
                    midaxillary: "Vertical fold on mid-axillary line at xiphoid level",
                    tricep: "Vertical fold on back of arm, halfway between shoulder and elbow",
                    subscapular: "Diagonal fold 1–2 cm below right shoulder blade",
                    abdominal: "Vertical fold 2 cm to the right of navel",
                    suprailiac: "Diagonal fold just above iliac crest at mid-axillary line",
                    thigh: "Vertical fold on front of thigh, midway between hip and knee",
                  };
                  return (
                    <div key={site}>
                      <label className="block text-xs text-jungle-muted mb-0.5 capitalize">{site.replace(/_/g, " ")}</label>
                      {guides[site] && <p className="text-[9px] text-jungle-dim mb-1 leading-tight">{guides[site]}</p>}
                      <input type="number" step="0.1" value={skinfolds[site] || ""} onChange={(e) => setSkinfolds({ ...skinfolds, [site]: e.target.value })} className="input-field text-sm" placeholder="mm" />
                    </div>
                  );
                })}
              </div>
            </>
          )}

          {step === 3 && (
            <>
              <p className="text-sm text-jungle-muted">Enter your estimated 1-rep max (1RM) for each lift in kg.</p>
              <div className="bg-jungle-deeper border border-jungle-border rounded-lg px-3 py-2 mb-2">
                <p className="text-[10px] text-jungle-dim leading-relaxed">
                  If you don't know your 1RM, estimate from your best working set:
                  multiply your weight by (1 + reps/30). Example: 100kg x 8 reps = ~127kg estimated 1RM.
                  Leave blank if unsure — baselines can be set later.
                </p>
              </div>
              <div className="space-y-3">
                {CORE_LIFTS.map((lift) => (
                  <div key={lift} className="flex items-center gap-3">
                    <label className="label-field mb-0 w-40 shrink-0 text-sm">{lift}</label>
                    <input type="number" step="0.5" value={strengths[lift] || ""} onChange={(e) => setStrengths({ ...strengths, [lift]: e.target.value })} placeholder="kg" className="input-field flex-1" />
                  </div>
                ))}
              </div>
              <p className="text-[10px] text-jungle-dim mt-2">These baselines are used to calculate your initial training loads. The system refines them as you log workouts.</p>
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
                <label className="label-field">Preferred Cardio Machine</label>
                <select value={cardioMachine} onChange={(e) => setCardioMachine(e.target.value)} className="input-field">
                  <option value="treadmill">Treadmill (incline walk)</option>
                  <option value="stairmaster">StairMaster</option>
                  <option value="stationary_bike">Stationary Bike</option>
                  <option value="elliptical">Elliptical</option>
                </select>
              </div>
              <div className="flex items-center justify-between">
                <div>
                  <label className="label-field">Fasted Morning Cardio</label>
                  <p className="text-[10px] text-jungle-dim">Do cardio before eating (maximizes fat oxidation during prep)</p>
                </div>
                <button
                  type="button"
                  onClick={() => setFastedCardio(!fastedCardio)}
                  className={`w-12 h-6 rounded-full transition-colors ${fastedCardio ? "bg-jungle-accent" : "bg-jungle-border"}`}
                >
                  <div className={`w-5 h-5 rounded-full bg-white shadow transition-transform ${fastedCardio ? "translate-x-6" : "translate-x-0.5"}`} />
                </button>
              </div>

              {/* Food Source Preferences */}
              <div className="border-t border-jungle-border pt-4 mt-4">
                <h3 className="text-sm font-semibold text-jungle-accent mb-1">Food Preferences</h3>
                <p className="text-[10px] text-jungle-dim mb-3">Select your go-to sources. You can change these later in Settings.</p>

                <div className="space-y-3">
                  <div>
                    <label className="label-field text-[11px]">Protein Sources</label>
                    <div className="flex flex-wrap gap-1.5 mt-1">
                      {["Chicken Breast", "Turkey Breast", "Lean Ground Beef", "Flank Steak", "Tilapia", "Cod", "Salmon", "Shrimp", "Egg Whites", "Greek Yogurt (nonfat)", "Tofu (firm)", "Tempeh"].map((item) => (
                        <button key={item} type="button" onClick={() => setPreferredProteins((p) => p.includes(item) ? p.filter((x) => x !== item) : [...p, item])}
                          className={`px-2 py-1 rounded-lg text-[10px] font-medium border transition-colors ${
                            preferredProteins.includes(item) ? "bg-blue-500/20 border-blue-500/50 text-blue-400" : "bg-jungle-deeper border-jungle-border text-jungle-muted hover:border-blue-500/30"
                          }`}>{item}</button>
                      ))}
                    </div>
                  </div>
                  <div>
                    <label className="label-field text-[11px]">Carb Sources</label>
                    <div className="flex flex-wrap gap-1.5 mt-1">
                      {["White Rice", "Jasmine Rice", "Brown Rice", "Oats (rolled)", "Cream of Rice", "Sweet Potato", "Red Potato (boiled)", "Quinoa"].map((item) => (
                        <button key={item} type="button" onClick={() => setPreferredCarbs((p) => p.includes(item) ? p.filter((x) => x !== item) : [...p, item])}
                          className={`px-2 py-1 rounded-lg text-[10px] font-medium border transition-colors ${
                            preferredCarbs.includes(item) ? "bg-amber-500/20 border-amber-500/50 text-amber-400" : "bg-jungle-deeper border-jungle-border text-jungle-muted hover:border-amber-500/30"
                          }`}>{item}</button>
                      ))}
                    </div>
                  </div>
                  <div>
                    <label className="label-field text-[11px]">Fat Sources</label>
                    <div className="flex flex-wrap gap-1.5 mt-1">
                      {["Extra Virgin Olive Oil", "Avocado", "Almonds", "Peanut Butter", "Almond Butter", "Coconut Oil"].map((item) => (
                        <button key={item} type="button" onClick={() => setPreferredFats((p) => p.includes(item) ? p.filter((x) => x !== item) : [...p, item])}
                          className={`px-2 py-1 rounded-lg text-[10px] font-medium border transition-colors ${
                            preferredFats.includes(item) ? "bg-rose-500/20 border-rose-500/50 text-rose-400" : "bg-jungle-deeper border-jungle-border text-jungle-muted hover:border-rose-500/30"
                          }`}>{item}</button>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {step === 5 && (
            <div className="text-center py-6 space-y-5">
              <div className="w-16 h-16 mx-auto rounded-full bg-jungle-accent/20 flex items-center justify-center">
                <svg className="w-8 h-8 text-jungle-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
              </div>
              <h3 className="text-lg font-semibold">Ready to Launch</h3>
              <p className="text-jungle-muted text-sm max-w-sm mx-auto">
                When you click Launch, Coronado will run all three engines and build your personalized system. This takes about 10 seconds.
              </p>
              <div className="text-left max-w-sm mx-auto space-y-2">
                {[
                  { engine: "Engine 1", action: "Analyze your physique against division standards" },
                  { engine: "Engine 2", action: "Generate your training program and split" },
                  { engine: "Engine 3", action: "Calculate macros and build your meal plan" },
                ].map(({ engine, action }) => (
                  <div key={engine} className="flex items-start gap-2 bg-jungle-deeper rounded-lg px-3 py-2">
                    <span className="text-jungle-accent text-[10px] font-bold shrink-0 mt-0.5">{engine}</span>
                    <span className="text-xs text-jungle-muted">{action}</span>
                  </div>
                ))}
              </div>
              <p className="text-[10px] text-jungle-dim">You can update all of these settings later from the Settings page.</p>
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
