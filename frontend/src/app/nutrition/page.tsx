"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import NavBar from "@/components/NavBar";
import { api } from "@/lib/api";

// ─── Interfaces ────────────────────────────────────────────────────────────────

interface DayMacros {
  calories: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
}

interface PeriWorkoutTiming {
  pre_workout_carbs_g: number;
  intra_workout_carbs_g: number;
  post_workout_carbs_g: number;
  other_carbs_g: number;
}

interface DivisionNutrition {
  carb_cycling_factor: number;
  meal_frequency_target: number;
  mps_threshold_g: number;
  notes: string[];
}

interface Prescription {
  tdee: number;
  target_calories: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  peri_workout_carb_pct: number;
  phase: string;
  training_day_macros?: DayMacros;
  rest_day_macros?: DayMacros;
  peri_workout_timing?: PeriWorkoutTiming;
  division_nutrition?: DivisionNutrition;
}

interface Ingredient {
  id: string;
  name: string;
  category: string;
  calories_per_100g: number;
  protein_per_100g: number;
  carbs_per_100g: number;
  fat_per_100g: number;
}

interface DailyTotals {
  date: string;
  total_calories: number;
  total_protein_g: number;
  total_carbs_g: number;
  total_fat_g: number;
  target_calories: number | null;
  remaining_calories: number | null;
}

interface PreworkoutData {
  brand: string;
  serving_g: string;
  calories: string;
  protein: string;
  carbs: string;
  caffeine: string;
}

// ─── Meal plan helpers ─────────────────────────────────────────────────────────

const MEAL_TEMPLATES = [
  { label: "Breakfast", time: "7:00am", periTag: null, foods: ["Eggs (3-4 whole)", "Oatmeal (80g)", "Greek Yogurt (150g)"] },
  { label: "Pre-Workout", time: "11:00am", periTag: "🏋️ Peri-Workout", foods: ["Chicken Breast (150g)", "White Rice (200g)", "Banana"] },
  { label: "Post-Workout", time: "1:30pm", periTag: "⚡ Post-WO", foods: ["Whey Protein Shake (40g)", "Rice Cakes (4)", "Gatorade (500ml)"] },
  { label: "Lunch", time: "4:00pm", periTag: null, foods: ["Ground Turkey (180g)", "Sweet Potato (200g)", "Broccoli (150g)"] },
  { label: "Dinner", time: "7:30pm", periTag: null, foods: ["Salmon or Tilapia (180g)", "Jasmine Rice (150g)", "Asparagus (100g)"] },
];

// Distributes macros evenly across N meals; pre-workout gets extra peri carbs
function buildMealPlan(
  macros: DayMacros,
  mealCount: number,
  periPct: number,
  periTiming?: PeriWorkoutTiming,
) {
  const count = Math.max(1, Math.min(mealCount, MEAL_TEMPLATES.length));
  const templates = MEAL_TEMPLATES.slice(0, count);

  // Carb distribution: pre-workout meal gets peri_workout_carb_pct of carbs,
  // post-workout gets same amount, remaining spread across other meals.
  const periCarbs = periTiming
    ? periTiming.pre_workout_carbs_g + periTiming.post_workout_carbs_g
    : macros.carbs_g * periPct;

  const preCarbs = periTiming
    ? periTiming.pre_workout_carbs_g
    : Math.round(macros.carbs_g * periPct * 0.4);
  const postCarbs = periTiming
    ? periTiming.post_workout_carbs_g
    : Math.round(macros.carbs_g * periPct * 0.6);
  const remainingCarbs = macros.carbs_g - periCarbs;
  const otherMealCount = count - (count >= 3 ? 2 : 0); // meals that aren't pre/post
  const baseCarbs = otherMealCount > 0 ? remainingCarbs / otherMealCount : remainingCarbs;

  // Protein spread evenly
  const baseProtein = macros.protein_g / count;
  // Fat spread evenly
  const baseFat = macros.fat_g / count;

  return templates.map((t, i) => {
    let carbs = baseCarbs;
    let protein = baseProtein;
    let fat = baseFat;

    if (count >= 3) {
      if (i === 1) { carbs = preCarbs; } // Pre-workout
      if (i === 2) { carbs = postCarbs; fat = baseFat * 0.5; } // Post-workout: low fat
    }

    return {
      ...t,
      protein: Math.round(protein),
      carbs: Math.round(carbs),
      fat: Math.round(fat),
      foods: t.foods,
    };
  });
}

// ─── Cardio helpers ────────────────────────────────────────────────────────────

const CARDIO_RECS: Record<string, string> = {
  cut: "2-3x steady-state cardio, 30-45 min at 65% max HR (Zone 2) + 1x HIIT, 20 min",
  bulk: "1-2x low-intensity cardio, 20-30 min for cardiovascular health",
  peak: "1x light cardio (30 min walk), then taper completely 3 days out",
  maintain: "2x moderate cardio, 30 min at 70% max HR",
};

const CAL_PER_MIN: Record<string, number> = {
  Low: 3,
  Moderate: 6,
  High: 9,
};

// ─── Tooltip component ────────────────────────────────────────────────────────

function Tooltip({ text }: { text: string }) {
  const [visible, setVisible] = useState(false);
  return (
    <span className="relative inline-flex items-center ml-1">
      <button
        type="button"
        onMouseEnter={() => setVisible(true)}
        onMouseLeave={() => setVisible(false)}
        onFocus={() => setVisible(true)}
        onBlur={() => setVisible(false)}
        className="w-4 h-4 rounded-full border border-jungle-muted text-jungle-muted text-[9px] font-bold flex items-center justify-center hover:border-jungle-accent hover:text-jungle-accent transition-colors"
        aria-label="Info"
      >
        i
      </button>
      {visible && (
        <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-64 bg-jungle-deeper border border-jungle-border text-jungle-muted text-[11px] leading-relaxed rounded-lg px-3 py-2 shadow-lg z-50 pointer-events-none">
          {text}
        </span>
      )}
    </span>
  );
}

// ─── MacroTile ─────────────────────────────────────────────────────────────────

function MacroTile({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="bg-jungle-deeper rounded-lg p-3 text-center">
      <p className="text-xs text-jungle-muted">{label}</p>
      <p className="text-xl font-bold mt-0.5" style={{ color }}>
        {Math.round(value)}<span className="text-xs font-normal text-jungle-muted">g</span>
      </p>
    </div>
  );
}

// ─── MacroBar (active-tab-aware) ───────────────────────────────────────────────

function MacroBar({ protein, carbs, fat }: { protein: number; carbs: number; fat: number }) {
  const total = protein * 4 + carbs * 4 + fat * 9;
  if (total === 0) return null;
  const pPct = Math.round((protein * 4 / total) * 100);
  const cPct = Math.round((carbs * 4 / total) * 100);
  const fPct = Math.round((fat * 9 / total) * 100);
  return (
    <>
      <div className="flex h-3 rounded-full overflow-hidden mt-3">
        <div style={{ width: `${pPct}%` }} className="bg-green-400" />
        <div style={{ width: `${cPct}%` }} className="bg-jungle-accent" />
        <div style={{ width: `${fPct}%` }} className="bg-red-400" />
      </div>
      <div className="flex justify-between mt-1 text-[10px] text-jungle-dim">
        <span>P {pPct}%</span>
        <span>C {cPct}%</span>
        <span>F {fPct}%</span>
      </div>
    </>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function NutritionPage() {
  const router = useRouter();
  const { user, loading, logout } = useAuth();

  // Core data
  const [rx, setRx] = useState<Prescription | null>(null);
  const [dailyTotals, setDailyTotals] = useState<DailyTotals | null>(null);
  const [daysOut, setDaysOut] = useState<number | null>(null);

  // Food logger
  const [searchQ, setSearchQ] = useState("");
  const [ingredients, setIngredients] = useState<Ingredient[]>([]);
  const [selectedIng, setSelectedIng] = useState<Ingredient | null>(null);
  const [quantity, setQuantity] = useState("100");
  const [mealItems, setMealItems] = useState<{ ingredient: Ingredient; quantity_g: number }[]>([]);
  const [mealNumber, setMealNumber] = useState(1);
  const [mealType, setMealType] = useState("standard");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  // Macro tab
  const [macroTab, setMacroTab] = useState<"training" | "rest">("training");

  // Meal plan state
  const [eatenMeals, setEatenMeals] = useState<Set<number>>(new Set());
  const [cheatMeals, setCheatMeals] = useState<Set<number>>(new Set());

  // Cardio state
  const [cardioType, setCardioType] = useState("Running");
  const [cardioDuration, setCardioDuration] = useState("");
  const [cardioIntensity, setCardioIntensity] = useState<"Low" | "Moderate" | "High">("Moderate");
  const [cardioCalories, setCardioCalories] = useState("");
  const [cardioLogged, setCardioLogged] = useState(false);
  const [cardioLoggedKcal, setCardioLoggedKcal] = useState(0);

  // Pre-workout state
  const [preworkoutOpen, setPreworkoutOpen] = useState(false);
  const [usingPreworkout, setUsingPreworkout] = useState(false);
  const [preworkoutForm, setPreworkoutForm] = useState<PreworkoutData>({
    brand: "", serving_g: "", calories: "", protein: "", carbs: "", caffeine: "",
  });
  const [savedPreworkout, setSavedPreworkout] = useState<PreworkoutData | null>(null);

  const today = new Date().toISOString().split("T")[0];
  const preworkoutKey = "coronado_preworkout";

  // Load saved preworkout from localStorage on mount
  const preworkoutLoaded = useRef(false);
  useEffect(() => {
    if (preworkoutLoaded.current) return;
    preworkoutLoaded.current = true;
    try {
      const raw = localStorage.getItem(preworkoutKey);
      if (raw) {
        const data = JSON.parse(raw) as PreworkoutData;
        setSavedPreworkout(data);
        setPreworkoutForm(data);
        setUsingPreworkout(true);
      }
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    if (!loading && !user) { router.push("/auth/login"); return; }
    if (user) {
      api.get<Prescription>("/engine3/prescription/current").then(setRx).catch(() => {});
      api.get<DailyTotals>(`/engine3/daily-totals/${today}`).then(setDailyTotals).catch(() => {});
      api.get<{ days_out: number }>("/engine3/peak-week")
        .then((res) => { if (res.days_out != null) setDaysOut(res.days_out); })
        .catch(() => {});
    }
  }, [user, loading, router, today]);

  useEffect(() => {
    if (!user) return;
    if (searchQ.length < 2) { setIngredients([]); return; }
    const timer = setTimeout(() => {
      api.get<Ingredient[]>(`/engine3/ingredients/search?q=${encodeURIComponent(searchQ)}`)
        .then(setIngredients).catch(() => {});
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQ, user]);

  if (loading || !user) return null;

  // Active macros based on tab selection
  const activeMacros: DayMacros | null = (() => {
    if (!rx) return null;
    if (macroTab === "training" && rx.training_day_macros) return rx.training_day_macros;
    if (macroTab === "rest" && rx.rest_day_macros) return rx.rest_day_macros;
    // Fallback to top-level macros
    return {
      calories: rx.target_calories,
      protein_g: rx.protein_g,
      carbs_g: rx.carbs_g,
      fat_g: rx.fat_g,
    };
  })();

  // Meal plan
  const mealFrequency = rx?.division_nutrition?.meal_frequency_target ?? 5;
  const mealPlan = rx && activeMacros
    ? buildMealPlan(activeMacros, mealFrequency, rx.peri_workout_carb_pct, rx.peri_workout_timing)
    : [];

  // Cheat allowance (simple heuristic: 1 per week during bulk, 0 during cut)
  const cheatAllowedPerWeek = rx?.phase === "bulk" ? 1 : 0;

  const mealTotals = mealItems.reduce(
    (acc, { ingredient, quantity_g }) => {
      const scale = quantity_g / 100;
      return {
        cal: acc.cal + ingredient.calories_per_100g * scale,
        prot: acc.prot + ingredient.protein_per_100g * scale,
        carbs: acc.carbs + ingredient.carbs_per_100g * scale,
        fat: acc.fat + ingredient.fat_per_100g * scale,
      };
    },
    { cal: 0, prot: 0, carbs: 0, fat: 0 },
  );

  const addToMeal = () => {
    if (!selectedIng || !quantity) return;
    setMealItems((prev) => [...prev, { ingredient: selectedIng, quantity_g: parseFloat(quantity) }]);
    setSelectedIng(null);
    setQuantity("100");
    setSearchQ("");
    setIngredients([]);
  };

  const saveMeal = async () => {
    if (!mealItems.length) return;
    setSaving(true);
    try {
      await api.post("/engine3/meals", {
        meal_number: mealNumber,
        meal_type: mealType,
        items: mealItems.map(({ ingredient, quantity_g }) => ({
          ingredient_id: ingredient.id,
          quantity_g,
        })),
      });
      setMealItems([]);
      setMealNumber((n) => n + 1);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
      api.get<DailyTotals>(`/engine3/daily-totals/${today}`).then(setDailyTotals).catch(() => {});
    } catch {
      // silent
    } finally {
      setSaving(false);
    }
  };

  const toggleEaten = (idx: number) => {
    setEatenMeals((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx); else next.add(idx);
      return next;
    });
  };

  const toggleCheat = (idx: number) => {
    setCheatMeals((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx); else next.add(idx);
      return next;
    });
  };

  const logCardio = async () => {
    const mins = parseFloat(cardioDuration);
    if (!mins || mins <= 0) return;
    const kcal = cardioCalories
      ? parseFloat(cardioCalories)
      : Math.round(mins * (CAL_PER_MIN[cardioIntensity] ?? 6));
    setCardioLoggedKcal(kcal);
    setCardioLogged(true);
    try {
      await api.post("/checkin/daily", { notes: `Cardio tracked: ${cardioType} for ${mins} mins (${kcal} kcal burned)` });
    } catch {
      // best-effort
    }
  };

  const savePreworkout = () => {
    try {
      localStorage.setItem(preworkoutKey, JSON.stringify(preworkoutForm));
      setSavedPreworkout({ ...preworkoutForm });
    } catch {
      // ignore
    }
  };

  // Preworkout additional cals for daily progress
  const preworkoutBonusCal =
    savedPreworkout && usingPreworkout ? parseFloat(savedPreworkout.calories || "0") || 0 : 0;
  const preworkoutBonusCarbs =
    savedPreworkout && usingPreworkout ? parseFloat(savedPreworkout.carbs || "0") || 0 : 0;
  const preworkoutBonusProtein =
    savedPreworkout && usingPreworkout ? parseFloat(savedPreworkout.protein || "0") || 0 : 0;

  const effectiveTotalCal = (dailyTotals?.total_calories ?? 0) + preworkoutBonusCal;
  const effectiveTotalProtein = (dailyTotals?.total_protein_g ?? 0) + preworkoutBonusProtein;
  const effectiveTotalCarbs = (dailyTotals?.total_carbs_g ?? 0) + preworkoutBonusCarbs;
  const effectiveTotalFat = dailyTotals?.total_fat_g ?? 0;

  const cardioRec = rx ? (CARDIO_RECS[rx.phase] ?? CARDIO_RECS["maintain"]) : null;

  const NOTE_EMOJIS = ["🔬", "🥩", "🌿", "💧", "⚡", "🎯", "📊", "🏆"];

  return (
    <div className="min-h-screen bg-jungle-dark">
      <NavBar username={user.username} onLogout={() => { logout(); router.push("/"); }} />

      <main className="container-app py-6">
        <div className="max-w-3xl mx-auto space-y-6">
          <div>
            <h1 className="text-2xl font-bold">
              <span className="text-jungle-accent">Nutrition</span> Plan
            </h1>
            <p className="text-jungle-muted text-sm mt-1">Engine 3 macro prescription</p>
          </div>

          {/* ── Daily Progress ── */}
          {dailyTotals && dailyTotals.target_calories && (
            <div className="card bg-jungle-gradient">
              <p className="text-xs text-jungle-muted uppercase tracking-wider mb-2">Today&apos;s Progress</p>
              <div className="flex items-center justify-between mb-2">
                <span className="text-2xl font-bold text-jungle-accent">
                  {Math.round(effectiveTotalCal)}
                </span>
                <span className="text-jungle-muted text-sm">
                  / {Math.round(dailyTotals.target_calories)} kcal
                </span>
              </div>
              {preworkoutBonusCal > 0 && (
                <p className="text-[10px] text-jungle-dim mb-1">
                  Includes {Math.round(preworkoutBonusCal)} kcal pre-workout supplement
                </p>
              )}
              <div className="h-2 bg-jungle-deeper rounded-full overflow-hidden">
                <div
                  className="h-full bg-jungle-accent rounded-full transition-all"
                  style={{
                    width: `${Math.min(100, (effectiveTotalCal / dailyTotals.target_calories) * 100)}%`,
                  }}
                />
              </div>
              <div className="grid grid-cols-3 gap-3 mt-3 text-center">
                <div>
                  <p className="text-xs text-jungle-muted">Protein</p>
                  <p className="text-sm font-semibold text-green-400">{Math.round(effectiveTotalProtein)}g</p>
                </div>
                <div>
                  <p className="text-xs text-jungle-muted">Carbs</p>
                  <p className="text-sm font-semibold text-jungle-accent">{Math.round(effectiveTotalCarbs)}g</p>
                </div>
                <div>
                  <p className="text-xs text-jungle-muted">Fat</p>
                  <p className="text-sm font-semibold text-red-400">{Math.round(effectiveTotalFat)}g</p>
                </div>
              </div>
              {savedPreworkout && usingPreworkout && savedPreworkout.caffeine && (
                <p className="text-[10px] text-yellow-400/70 mt-2 text-center">
                  Caffeine sensitivity: Pre-workout logged. Ensure 6hr pre-sleep cutoff.
                </p>
              )}
            </div>
          )}

          {/* ── Prescription ── */}
          {rx && (
            <>
              <div className="card">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-xs font-semibold text-jungle-muted uppercase tracking-wider">
                    Prescription — {rx.phase}
                  </h3>
                  <span className="text-sm font-bold text-jungle-accent">{Math.round(rx.target_calories)} kcal</span>
                </div>

                {/* Training Day / Rest Day tabs */}
                {(rx.training_day_macros || rx.rest_day_macros) && (
                  <>
                    <div className="flex rounded-lg overflow-hidden border border-jungle-border mb-3">
                      {(["training", "rest"] as const).map((tab) => (
                        <button
                          key={tab}
                          onClick={() => setMacroTab(tab)}
                          className={`flex-1 py-1.5 text-xs font-medium transition-colors ${
                            macroTab === tab
                              ? "bg-jungle-accent text-jungle-dark"
                              : "text-jungle-muted hover:text-jungle-accent"
                          }`}
                        >
                          {tab === "training" ? "Training Day" : "Rest Day"}
                        </button>
                      ))}
                    </div>

                    {macroTab === "training" && rx.training_day_macros && (
                      <>
                        <div className="grid grid-cols-3 gap-3 text-center">
                          <MacroTile label="Protein" value={rx.training_day_macros.protein_g} color="#4ade80" />
                          <MacroTile label="Carbs" value={rx.training_day_macros.carbs_g} color="#c8a84e" />
                          <MacroTile label="Fat" value={rx.training_day_macros.fat_g} color="#ef4444" />
                        </div>
                        <p className="text-xs text-jungle-dim text-center mt-2">
                          {Math.round(rx.training_day_macros.calories)} kcal on training days
                        </p>
                        <MacroBar
                          protein={rx.training_day_macros.protein_g}
                          carbs={rx.training_day_macros.carbs_g}
                          fat={rx.training_day_macros.fat_g}
                        />
                      </>
                    )}

                    {macroTab === "rest" && rx.rest_day_macros && (
                      <>
                        <div className="grid grid-cols-3 gap-3 text-center">
                          <MacroTile label="Protein" value={rx.rest_day_macros.protein_g} color="#4ade80" />
                          <MacroTile label="Carbs" value={rx.rest_day_macros.carbs_g} color="#c8a84e" />
                          <MacroTile label="Fat" value={rx.rest_day_macros.fat_g} color="#ef4444" />
                        </div>
                        <p className="text-xs text-jungle-dim text-center mt-2">
                          {Math.round(rx.rest_day_macros.calories)} kcal on rest days
                        </p>
                        <MacroBar
                          protein={rx.rest_day_macros.protein_g}
                          carbs={rx.rest_day_macros.carbs_g}
                          fat={rx.rest_day_macros.fat_g}
                        />
                      </>
                    )}
                  </>
                )}

                {/* Fallback: no carb-cycling data */}
                {!rx.training_day_macros && !rx.rest_day_macros && (
                  <>
                    <div className="grid grid-cols-3 gap-3 text-center">
                      <MacroTile label="Protein" value={rx.protein_g} color="#4ade80" />
                      <MacroTile label="Carbs" value={rx.carbs_g} color="#c8a84e" />
                      <MacroTile label="Fat" value={rx.fat_g} color="#ef4444" />
                    </div>
                    <MacroBar protein={rx.protein_g} carbs={rx.carbs_g} fat={rx.fat_g} />
                  </>
                )}
              </div>

              {/* ── Prescribed Meal Plan ── */}
              {mealPlan.length > 0 && activeMacros && (
                <div className="card">
                  <div className="flex items-center justify-between mb-1">
                    <h3 className="text-xs font-semibold text-jungle-muted uppercase tracking-wider">
                      Prescribed Meal Plan
                    </h3>
                    <span className="text-[10px] text-jungle-dim">
                      {macroTab === "training" ? "Training Day" : "Rest Day"}
                    </span>
                  </div>

                  {/* Summary bar */}
                  <div className="flex items-center gap-3 text-xs text-jungle-dim bg-jungle-deeper rounded-lg px-3 py-2 mb-4">
                    <span className="text-jungle-muted font-medium">
                      {eatenMeals.size} of {mealPlan.length} meals completed
                    </span>
                    <span className="text-jungle-dim">|</span>
                    <span>
                      {cheatMeals.size} cheat meal{cheatMeals.size !== 1 ? "s" : ""} used
                      {cheatAllowedPerWeek > 0 ? ` (${cheatAllowedPerWeek} allowed this week)` : " (0 allowed this week)"}
                    </span>
                  </div>

                  <div className="space-y-3">
                    {mealPlan.map((meal, idx) => {
                      const isEaten = eatenMeals.has(idx);
                      const isCheat = cheatMeals.has(idx);
                      return (
                        <div
                          key={idx}
                          className={`rounded-lg border p-3 transition-all ${
                            isEaten
                              ? "border-green-500/40 bg-green-500/5"
                              : isCheat
                              ? "border-orange-500/40 bg-orange-500/5"
                              : "border-jungle-border bg-jungle-deeper"
                          }`}
                        >
                          <div className="flex items-start justify-between gap-2 mb-1.5">
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className={`text-sm font-semibold ${isEaten ? "line-through text-jungle-dim" : ""}`}>
                                Meal {idx + 1} — {meal.label}
                              </span>
                              <span className="text-[10px] text-jungle-dim">{meal.time}</span>
                              {meal.periTag && (
                                <span className="px-1.5 py-0.5 rounded bg-yellow-500/15 text-yellow-400 text-[10px] font-medium">
                                  {meal.periTag}
                                </span>
                              )}
                              {isCheat && (
                                <span className="px-1.5 py-0.5 rounded bg-orange-500/20 text-orange-400 text-[10px] font-medium">
                                  Cheat Meal
                                </span>
                              )}
                              {isEaten && (
                                <span className="text-green-400 text-xs font-bold">✓</span>
                              )}
                            </div>
                          </div>
                          <p className="text-xs text-jungle-dim mb-2">
                            Protein: <span className="text-green-400 font-medium">{meal.protein}g</span>
                            {" | "}
                            Carbs: <span className="text-jungle-accent font-medium">{meal.carbs}g</span>
                            {" | "}
                            Fat: <span className="text-red-400 font-medium">{meal.fat}g</span>
                          </p>
                          {meal.foods && meal.foods.length > 0 && (
                            <ul className="mb-2 space-y-0.5">
                              {meal.foods.map((food, fi) => (
                                <li key={fi} className="text-[10px] text-jungle-dim flex items-center gap-1">
                                  <span className="w-1 h-1 rounded-full bg-jungle-border shrink-0 inline-block" />
                                  {food}
                                </li>
                              ))}
                            </ul>
                          )}
                          <div className="flex gap-2">
                            <button
                              onClick={() => toggleEaten(idx)}
                              className={`text-[11px] px-2.5 py-1 rounded-md font-medium transition-colors ${
                                isEaten
                                  ? "bg-green-500/20 text-green-400 hover:bg-green-500/30"
                                  : "bg-jungle-deeper border border-jungle-border text-jungle-muted hover:text-green-400 hover:border-green-500/40"
                              }`}
                            >
                              {isEaten ? "✓ Eaten" : "Mark as Eaten ✓"}
                            </button>
                            <button
                              onClick={() => toggleCheat(idx)}
                              className={`text-[11px] px-2.5 py-1 rounded-md font-medium transition-colors ${
                                isCheat
                                  ? "bg-orange-500/20 text-orange-400 hover:bg-orange-500/30"
                                  : "bg-jungle-deeper border border-jungle-border text-jungle-muted hover:text-orange-400 hover:border-orange-500/40"
                              }`}
                            >
                              {isCheat ? "🍕 Cheat" : "Cheat Meal / Alternate Meal 🍕"}
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* ── Peri-Workout Timing ── */}
              <div className="card">
                <h3 className="text-xs font-semibold text-jungle-muted uppercase tracking-wider mb-3">
                  Peri-Workout Timing
                </h3>

                {rx.peri_workout_timing ? (
                  <div className="grid grid-cols-2 gap-3">
                    {[
                      { label: "Pre-Workout", value: rx.peri_workout_timing.pre_workout_carbs_g, color: "text-yellow-400" },
                      { label: "Intra-Workout", value: rx.peri_workout_timing.intra_workout_carbs_g, color: "text-jungle-accent" },
                      { label: "Post-Workout", value: rx.peri_workout_timing.post_workout_carbs_g, color: "text-green-400" },
                      { label: "Other Meals", value: rx.peri_workout_timing.other_carbs_g, color: "text-jungle-muted" },
                    ].map(({ label, value, color }) => (
                      <div key={label} className="bg-jungle-deeper rounded-lg p-3 text-center">
                        <p className="text-xs text-jungle-muted">{label}</p>
                        <p className={`text-xl font-bold ${color}`}>
                          {Math.round(value)}<span className="text-xs font-normal text-jungle-dim">g</span>
                        </p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="grid grid-cols-2 gap-4">
                    <div className="bg-jungle-deeper rounded-lg p-4 text-center">
                      <p className="text-xs text-jungle-muted">Peri-Workout</p>
                      <p className="text-xl font-bold text-jungle-accent">
                        {Math.round(rx.carbs_g * rx.peri_workout_carb_pct)}g
                      </p>
                      <p className="text-xs text-jungle-dim">{Math.round(rx.peri_workout_carb_pct * 100)}% of carbs</p>
                    </div>
                    <div className="bg-jungle-deeper rounded-lg p-4 text-center">
                      <p className="text-xs text-jungle-muted">Other Meals</p>
                      <p className="text-xl font-bold">
                        {Math.round(rx.carbs_g * (1 - rx.peri_workout_carb_pct))}g
                      </p>
                      <p className="text-xs text-jungle-dim">{Math.round((1 - rx.peri_workout_carb_pct) * 100)}% spread</p>
                    </div>
                  </div>
                )}
              </div>

              {/* ── Cardio Prescription ── */}
              <div className="card">
                <h3 className="text-xs font-semibold text-jungle-muted uppercase tracking-wider mb-3">
                  Cardio &amp; Energy Expenditure
                </h3>

                {cardioRec && (
                  <div className="bg-jungle-deeper rounded-lg px-3 py-2.5 mb-4 flex gap-2 items-start">
                    <span className="text-jungle-accent mt-0.5 shrink-0">›</span>
                    <p className="text-xs text-jungle-muted leading-relaxed">{cardioRec}</p>
                  </div>
                )}

                {cardioLogged ? (
                  <div className="bg-green-500/10 border border-green-500/30 rounded-lg px-3 py-3 text-center">
                    <p className="text-green-400 text-sm font-semibold">
                      Cardio logged! +{cardioLoggedKcal} kcal burned
                    </p>
                    <button
                      onClick={() => { setCardioLogged(false); setCardioDuration(""); setCardioCalories(""); }}
                      className="text-xs text-jungle-muted hover:text-jungle-accent mt-1 transition-colors"
                    >
                      Log another
                    </button>
                  </div>
                ) : (
                  <div className="space-y-3">
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="text-xs text-jungle-muted block mb-1">Type</label>
                        <select
                          value={cardioType}
                          onChange={(e) => setCardioType(e.target.value)}
                          className="input-field text-sm py-1.5 w-full"
                        >
                          {["Running", "Cycling", "StairMaster", "Elliptical", "HIIT", "Walk"].map((t) => (
                            <option key={t} value={t}>{t}</option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <label className="text-xs text-jungle-muted block mb-1">Duration (min)</label>
                        <input
                          type="number"
                          min={1}
                          placeholder="30"
                          value={cardioDuration}
                          onChange={(e) => setCardioDuration(e.target.value)}
                          className="input-field text-sm py-1.5 w-full"
                        />
                      </div>
                    </div>

                    <div>
                      <label className="text-xs text-jungle-muted block mb-1">Intensity</label>
                      <div className="flex gap-2">
                        {(["Low", "Moderate", "High"] as const).map((lvl) => (
                          <button
                            key={lvl}
                            onClick={() => setCardioIntensity(lvl)}
                            className={`flex-1 py-1.5 text-xs rounded-md font-medium transition-colors border ${
                              cardioIntensity === lvl
                                ? "bg-jungle-accent text-jungle-dark border-jungle-accent"
                                : "border-jungle-border text-jungle-muted hover:text-jungle-accent hover:border-jungle-accent/40"
                            }`}
                          >
                            {lvl}
                          </button>
                        ))}
                      </div>
                    </div>

                    <div>
                      <label className="text-xs text-jungle-muted block mb-1">Calories burned (optional)</label>
                      <input
                        type="number"
                        min={0}
                        placeholder={`Est. ${Math.round((parseFloat(cardioDuration) || 30) * (CAL_PER_MIN[cardioIntensity] ?? 6))} kcal`}
                        value={cardioCalories}
                        onChange={(e) => setCardioCalories(e.target.value)}
                        className="input-field text-sm py-1.5 w-full"
                      />
                    </div>

                    <button
                      onClick={logCardio}
                      disabled={!cardioDuration || parseFloat(cardioDuration) <= 0}
                      className="btn-primary w-full disabled:opacity-40"
                    >
                      Log Cardio
                    </button>
                  </div>
                )}
              </div>

              {/* ── Pre-Workout Supplement ── */}
              <div className="card">
                <button
                  onClick={() => setPreworkoutOpen((v) => !v)}
                  className="flex items-center justify-between w-full"
                >
                  <h3 className="text-xs font-semibold text-jungle-muted uppercase tracking-wider">
                    Pre-Workout Supplement
                  </h3>
                  <svg
                    className={`w-4 h-4 text-jungle-muted transition-transform ${preworkoutOpen ? "rotate-180" : ""}`}
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </button>

                {savedPreworkout && usingPreworkout && !preworkoutOpen && (
                  <p className="text-xs text-jungle-dim mt-2">
                    Active pre-workout:{" "}
                    <span className="text-jungle-muted font-medium">{savedPreworkout.brand || "Unnamed"}</span>
                    {" — "}
                    {savedPreworkout.calories || "0"} kcal, {savedPreworkout.carbs || "0"}g carbs
                  </p>
                )}

                {preworkoutOpen && (
                  <div className="mt-4 space-y-3">
                    {/* Toggle */}
                    <div className="flex gap-3">
                      <button
                        onClick={() => setUsingPreworkout(true)}
                        className={`flex-1 py-1.5 text-xs rounded-md font-medium border transition-colors ${
                          usingPreworkout
                            ? "bg-jungle-accent text-jungle-dark border-jungle-accent"
                            : "border-jungle-border text-jungle-muted hover:border-jungle-accent/40"
                        }`}
                      >
                        Yes
                      </button>
                      <button
                        onClick={() => setUsingPreworkout(false)}
                        className={`flex-1 py-1.5 text-xs rounded-md font-medium border transition-colors ${
                          !usingPreworkout
                            ? "bg-jungle-accent text-jungle-dark border-jungle-accent"
                            : "border-jungle-border text-jungle-muted hover:border-jungle-accent/40"
                        }`}
                      >
                        No
                      </button>
                    </div>

                    {usingPreworkout && (
                      <>
                        <div className="grid grid-cols-2 gap-3">
                          <div>
                            <label className="text-xs text-jungle-muted block mb-1">Brand name</label>
                            <input
                              type="text"
                              placeholder="e.g. C4 Original"
                              value={preworkoutForm.brand}
                              onChange={(e) => setPreworkoutForm((f) => ({ ...f, brand: e.target.value }))}
                              className="input-field text-sm py-1.5 w-full"
                            />
                          </div>
                          <div>
                            <label className="text-xs text-jungle-muted block mb-1">Serving size (g)</label>
                            <input
                              type="number"
                              min={0}
                              value={preworkoutForm.serving_g}
                              onChange={(e) => setPreworkoutForm((f) => ({ ...f, serving_g: e.target.value }))}
                              className="input-field text-sm py-1.5 w-full"
                            />
                          </div>
                          <div>
                            <label className="text-xs text-jungle-muted block mb-1">Calories / serving</label>
                            <input
                              type="number"
                              min={0}
                              value={preworkoutForm.calories}
                              onChange={(e) => setPreworkoutForm((f) => ({ ...f, calories: e.target.value }))}
                              className="input-field text-sm py-1.5 w-full"
                            />
                          </div>
                          <div>
                            <label className="text-xs text-jungle-muted block mb-1">Protein / serving (g)</label>
                            <input
                              type="number"
                              min={0}
                              value={preworkoutForm.protein}
                              onChange={(e) => setPreworkoutForm((f) => ({ ...f, protein: e.target.value }))}
                              className="input-field text-sm py-1.5 w-full"
                            />
                          </div>
                          <div>
                            <label className="text-xs text-jungle-muted block mb-1">Carbs / serving (g)</label>
                            <input
                              type="number"
                              min={0}
                              value={preworkoutForm.carbs}
                              onChange={(e) => setPreworkoutForm((f) => ({ ...f, carbs: e.target.value }))}
                              className="input-field text-sm py-1.5 w-full"
                            />
                          </div>
                          <div>
                            <label className="text-xs text-jungle-muted block mb-1">Caffeine (mg, optional)</label>
                            <input
                              type="number"
                              min={0}
                              value={preworkoutForm.caffeine}
                              onChange={(e) => setPreworkoutForm((f) => ({ ...f, caffeine: e.target.value }))}
                              className="input-field text-sm py-1.5 w-full"
                            />
                          </div>
                        </div>

                        <button onClick={savePreworkout} className="btn-primary w-full">
                          Save to Plan
                        </button>

                        {preworkoutForm.caffeine && (
                          <p className="text-[10px] text-yellow-400/80 text-center">
                            Caffeine sensitivity: Pre-workout logged. Ensure 6hr pre-sleep cutoff.
                          </p>
                        )}
                      </>
                    )}
                  </div>
                )}
              </div>

              {/* ── Division Coaching Notes ── */}
              {rx.division_nutrition && rx.division_nutrition.notes.length > 0 && (
                <div className="card">
                  <div className="flex items-center mb-3">
                    <h3 className="text-xs font-semibold text-jungle-muted uppercase tracking-wider">
                      Division Coaching Notes
                    </h3>
                    <Tooltip text="These notes are algorithmically generated based on your competition division's judging criteria and current prep phase." />
                  </div>
                  <div className="space-y-2">
                    <div className="flex gap-4 text-xs text-jungle-dim mb-3 flex-wrap">
                      <span>Meals/day: <span className="text-jungle-muted font-medium">{rx.division_nutrition.meal_frequency_target}</span></span>
                      <span>MPS threshold: <span className="text-jungle-muted font-medium">≥{rx.division_nutrition.mps_threshold_g}g protein/meal</span></span>
                      <span>Carb swing: <span className="text-jungle-muted font-medium">±{Math.round(rx.division_nutrition.carb_cycling_factor * 100)}%</span></span>
                    </div>
                    {rx.division_nutrition.notes.map((note, i) => (
                      <div key={i} className="flex gap-2 text-xs text-jungle-dim leading-relaxed items-start">
                        <span className="shrink-0 mt-0.5">{NOTE_EMOJIS[i % NOTE_EMOJIS.length]}</span>
                        <span>{note}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* ── Peak Week Protocol link ── */}
              {daysOut !== null && daysOut <= 21 && (
                <a
                  href="/nutrition/peak-week"
                  className="card flex items-center justify-between border border-red-500/40 hover:border-jungle-accent/60 transition-colors group"
                >
                  <div>
                    <p className="font-semibold text-sm text-jungle-accent group-hover:text-jungle-accent">
                      Peak Week Protocol
                    </p>
                    <p className="text-xs text-jungle-muted mt-0.5">
                      {daysOut} days to show &mdash; your peaking plan is ready
                    </p>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <span className="px-2.5 py-1 rounded-full bg-red-500/20 text-red-400 text-xs font-bold">
                      {daysOut}d out
                    </span>
                    <svg className="w-4 h-4 text-jungle-muted group-hover:text-jungle-accent transition-colors" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                  </div>
                </a>
              )}
            </>
          )}

          {/* ── Log a Meal ── */}
          <div className="card">
            <h3 className="text-xs font-semibold text-jungle-muted uppercase tracking-wider mb-4">
              Log a Meal
            </h3>

            <div className="grid grid-cols-2 gap-3 mb-4">
              <div>
                <label className="text-xs text-jungle-muted">Meal #</label>
                <input
                  type="number"
                  min={1}
                  max={8}
                  value={mealNumber}
                  onChange={(e) => setMealNumber(parseInt(e.target.value))}
                  className="input-field mt-1 text-sm py-1.5"
                />
              </div>
              <div>
                <label className="text-xs text-jungle-muted">Type</label>
                <select
                  value={mealType}
                  onChange={(e) => setMealType(e.target.value)}
                  className="input-field mt-1 text-sm py-1.5"
                >
                  <option value="standard">Standard</option>
                  <option value="pre_workout">Pre-Workout</option>
                  <option value="post_workout">Post-Workout</option>
                </select>
              </div>
            </div>

            {/* Food search */}
            <div className="space-y-2 mb-4">
              <input
                type="text"
                placeholder="Search food (e.g. chicken breast, oats...)"
                value={searchQ}
                onChange={(e) => setSearchQ(e.target.value)}
                className="input-field text-sm py-2 w-full"
              />
              {ingredients.length > 0 && (
                <div className="border border-jungle-border rounded-lg overflow-hidden">
                  {ingredients.map((ing) => (
                    <button
                      key={ing.id}
                      onClick={() => { setSelectedIng(ing); setSearchQ(ing.name); setIngredients([]); }}
                      className="w-full text-left px-3 py-2 hover:bg-jungle-deeper text-sm flex justify-between items-center border-b border-jungle-border last:border-0"
                    >
                      <span>{ing.name}</span>
                      <span className="text-jungle-dim text-xs">
                        {Math.round(ing.calories_per_100g)} kcal / {Math.round(ing.protein_per_100g)}g P
                      </span>
                    </button>
                  ))}
                </div>
              )}
            </div>

            {selectedIng && (
              <div className="flex gap-2 mb-4">
                <div className="flex-1">
                  <label className="text-xs text-jungle-muted">Quantity (g)</label>
                  <input
                    type="number"
                    value={quantity}
                    onChange={(e) => setQuantity(e.target.value)}
                    className="input-field mt-1 text-sm py-1.5"
                  />
                </div>
                <div className="flex items-end">
                  <button onClick={addToMeal} className="btn-primary py-1.5 px-4">
                    Add
                  </button>
                </div>
              </div>
            )}

            {/* Meal items list */}
            {mealItems.length > 0 && (
              <div className="space-y-1 mb-4">
                {mealItems.map(({ ingredient, quantity_g }, idx) => {
                  const scale = quantity_g / 100;
                  return (
                    <div key={idx} className="flex items-center justify-between py-1.5 px-2 bg-jungle-deeper rounded text-sm">
                      <div>
                        <span className="font-medium">{ingredient.name}</span>
                        <span className="text-jungle-dim ml-2">{quantity_g}g</span>
                      </div>
                      <div className="text-jungle-muted text-xs text-right">
                        {Math.round(ingredient.calories_per_100g * scale)} kcal •{" "}
                        {Math.round(ingredient.protein_per_100g * scale)}P /&nbsp;
                        {Math.round(ingredient.carbs_per_100g * scale)}C /&nbsp;
                        {Math.round(ingredient.fat_per_100g * scale)}F
                      </div>
                    </div>
                  );
                })}

                <div className="flex items-center justify-between pt-2 border-t border-jungle-border text-sm font-semibold">
                  <span className="text-jungle-muted">Meal Total</span>
                  <span className="text-jungle-accent">
                    {Math.round(mealTotals.cal)} kcal &middot; {Math.round(mealTotals.prot)}P /&nbsp;
                    {Math.round(mealTotals.carbs)}C / {Math.round(mealTotals.fat)}F
                  </span>
                </div>

                <button
                  onClick={saveMeal}
                  disabled={saving}
                  className="btn-primary w-full mt-2 disabled:opacity-50"
                >
                  {saved ? "Saved!" : saving ? "Saving..." : `Save Meal ${mealNumber}`}
                </button>
              </div>
            )}
          </div>
        </div>
      </main>

      <div className="md:hidden h-16" />
    </div>
  );
}
