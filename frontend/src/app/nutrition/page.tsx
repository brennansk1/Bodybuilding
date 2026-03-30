"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import NavBar from "@/components/NavBar";
import { api } from "@/lib/api";
import { showToast } from "@/components/Toast";

// ─── Interfaces ────────────────────────────────────────────────────────────────

interface DayMacros {
  calories: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
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
  division_nutrition?: DivisionNutrition;
}

interface MealIngredient {
  name: string;
  quantity_g: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  calories: number;
}

interface MealData {
  meal_number: number;
  label: string;
  time: string;
  is_peri: boolean;
  ingredients: MealIngredient[];
  totals: { calories: number; protein_g: number; carbs_g: number; fat_g: number };
}

interface MealPlan {
  phase: string;
  training_day: MealData[];
  rest_day: MealData[];
}

interface DailyTotals {
  total_calories: number;
  total_protein_g: number;
  total_carbs_g: number;
  total_fat_g: number;
}

// ─── Component ─────────────────────────────────────────────────────────────────

const today = new Date().toISOString().slice(0, 10);

export default function NutritionPage() {
  const router = useRouter();
  const { user, loading, logout } = useAuth();

  const [rx, setRx] = useState<Prescription | null>(null);
  const [dailyTotals, setDailyTotals] = useState<DailyTotals | null>(null);
  const [fetching, setFetching] = useState(true);
  const [mealPlan, setMealPlan] = useState<MealPlan | null>(null);
  const [mealPlanLoading, setMealPlanLoading] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [dayTab, setDayTab] = useState<"training" | "rest">("training");
  const [eatenMeals, setEatenMeals] = useState<Set<number>>(new Set());

  // Cardio
  const [cardioType, setCardioType] = useState("Running");
  const [cardioDuration, setCardioDuration] = useState("30");
  const [cardioIntensity, setCardioIntensity] = useState<"Low" | "Moderate" | "High">("Moderate");
  const [cardioLogged, setCardioLogged] = useState(false);

  useEffect(() => {
    if (!loading && !user) { router.push("/auth/login"); return; }
    if (!user) return;

    setFetching(true);
    Promise.all([
      api.get<Prescription>("/engine3/prescription/current").catch(() => null),
      api.get<DailyTotals>(`/engine3/daily-totals/${today}`).catch(() => null),
    ]).then(([resRx, tot]) => {
      if (resRx) {
        setRx(resRx);
        setMealPlanLoading(true);
        api.get<MealPlan>("/engine3/meal-plan/current")
          .then(setMealPlan)
          .catch(() => {})
          .finally(() => setMealPlanLoading(false));
      }
      if (tot) setDailyTotals(tot);
    }).finally(() => setFetching(false));
  }, [user, loading, router]);

  const regenerateMealPlan = async () => {
    setRegenerating(true);
    try {
      const res = await api.post<MealPlan>("/engine3/meal-plan/generate", {});
      setMealPlan(res);
    } catch {
      showToast("Failed to regenerate meal plan", "error");
    }
    setRegenerating(false);
  };

  const toggleEaten = (n: number) => {
    setEatenMeals(prev => {
      const next = new Set(prev);
      next.has(n) ? next.delete(n) : next.add(n);
      return next;
    });
  };

  const logCardio = async () => {
    try {
      await api.post("/engine3/cardio/log", {
        activity_type: cardioType,
        duration_min: parseInt(cardioDuration) || 30,
        intensity: cardioIntensity.toLowerCase(),
        recorded_date: today,
      });
      setCardioLogged(true);
    } catch {
      showToast("Failed to log cardio", "error");
    }
  };

  if (loading || !user || fetching) return null;

  const activeMacros: DayMacros | null = (() => {
    if (!rx) return null;
    if (dayTab === "training" && rx.training_day_macros) return rx.training_day_macros;
    if (dayTab === "rest" && rx.rest_day_macros) return rx.rest_day_macros;
    return { calories: rx.target_calories, protein_g: rx.protein_g, carbs_g: rx.carbs_g, fat_g: rx.fat_g };
  })();

  const meals = mealPlan ? (dayTab === "training" ? mealPlan.training_day : mealPlan.rest_day) : [];
  const eatenCount = eatenMeals.size;

  const pPct = activeMacros ? Math.round((activeMacros.protein_g * 4 / activeMacros.calories) * 100) : 0;
  const cPct = activeMacros ? Math.round((activeMacros.carbs_g * 4 / activeMacros.calories) * 100) : 0;
  const fPct = activeMacros ? 100 - pPct - cPct : 0;

  const estCardioKcal = Math.round((parseInt(cardioDuration) || 30) * (cardioIntensity === "High" ? 10 : cardioIntensity === "Moderate" ? 7 : 5));

  return (
    <div className="min-h-screen">
      <NavBar username={user.username} onLogout={() => { logout(); router.push("/"); }} />
      <main className="max-w-lg mx-auto px-4 py-6 space-y-4">

        {!rx ? (
          <div className="card text-center py-8">
            <p className="text-jungle-muted text-sm">No nutrition prescription yet.</p>
            <p className="text-jungle-dim text-xs mt-1">Complete a check-in to generate your macros.</p>
          </div>
        ) : (
          <>
            {/* ── Macro Prescription ── */}
            <div className="card space-y-3">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-bold text-jungle-text uppercase tracking-wide">Daily Macros</h2>
                <span className="text-[10px] px-2 py-0.5 rounded bg-jungle-accent/20 text-jungle-accent font-medium capitalize">{rx.phase}</span>
              </div>

              <div className="flex gap-1 bg-jungle-deeper rounded-lg p-0.5">
                {(["training", "rest"] as const).map(tab => (
                  <button key={tab} onClick={() => setDayTab(tab)}
                    className={`flex-1 py-1.5 rounded-md text-xs font-medium transition-colors ${dayTab === tab ? "bg-jungle-accent text-jungle-dark" : "text-jungle-muted hover:text-jungle-text"}`}>
                    {tab === "training" ? "Training Day" : "Rest Day"}
                  </button>
                ))}
              </div>

              {activeMacros && (
                <>
                  <div className="text-center">
                    <p className="text-3xl font-bold text-jungle-text">{Math.round(activeMacros.calories)}</p>
                    <p className="text-[10px] text-jungle-dim">kcal target</p>
                  </div>
                  <div className="grid grid-cols-3 gap-2">
                    <div className="text-center bg-jungle-deeper rounded-lg py-2">
                      <p className="text-lg font-bold text-blue-400">{Math.round(activeMacros.protein_g)}g</p>
                      <p className="text-[9px] text-jungle-dim">Protein ({pPct}%)</p>
                    </div>
                    <div className="text-center bg-jungle-deeper rounded-lg py-2">
                      <p className="text-lg font-bold text-amber-400">{Math.round(activeMacros.carbs_g)}g</p>
                      <p className="text-[9px] text-jungle-dim">Carbs ({cPct}%)</p>
                    </div>
                    <div className="text-center bg-jungle-deeper rounded-lg py-2">
                      <p className="text-lg font-bold text-red-400">{Math.round(activeMacros.fat_g)}g</p>
                      <p className="text-[9px] text-jungle-dim">Fat ({fPct}%)</p>
                    </div>
                  </div>
                </>
              )}
            </div>

            {/* ── Today's Intake vs Target ── */}
            {dailyTotals && activeMacros && (
              <div className="card space-y-3">
                <h2 className="text-sm font-bold text-jungle-text uppercase tracking-wide">Today&apos;s Progress</h2>
                <div className="space-y-2">
                  {[
                    { label: "Calories", actual: dailyTotals.total_calories, target: activeMacros.calories, unit: "kcal", color: "bg-jungle-accent" },
                    { label: "Protein", actual: dailyTotals.total_protein_g, target: activeMacros.protein_g, unit: "g", color: "bg-blue-400" },
                    { label: "Carbs", actual: dailyTotals.total_carbs_g, target: activeMacros.carbs_g, unit: "g", color: "bg-amber-400" },
                    { label: "Fat", actual: dailyTotals.total_fat_g, target: activeMacros.fat_g, unit: "g", color: "bg-red-400" },
                  ].map(({ label, actual, target, unit: u, color }) => {
                    const pct = target > 0 ? Math.min((actual / target) * 100, 120) : 0;
                    const isOver = actual > target * 1.05;
                    const isClose = actual >= target * 0.95 && actual <= target * 1.05;
                    return (
                      <div key={label}>
                        <div className="flex items-center justify-between mb-0.5">
                          <span className="text-[10px] text-jungle-muted">{label}</span>
                          <span className={`text-[10px] font-semibold ${isClose ? "text-green-400" : isOver ? "text-red-400" : "text-jungle-muted"}`}>
                            {Math.round(actual)} / {Math.round(target)} {u}
                          </span>
                        </div>
                        <div className="h-2 bg-jungle-deeper rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full transition-all duration-500 ${isOver ? "bg-red-400" : isClose ? "bg-green-400" : color}`}
                            style={{ width: `${Math.min(pct, 100)}%` }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* ── Meal Plan ── */}
            <div className="card space-y-3">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-bold text-jungle-text uppercase tracking-wide">Meal Plan</h2>
                <button onClick={regenerateMealPlan} disabled={regenerating}
                  className="text-[10px] text-jungle-accent hover:text-jungle-accent/80 font-medium disabled:opacity-50">
                  {regenerating ? "Generating..." : "Regenerate"}
                </button>
              </div>

              {mealPlanLoading ? (
                <p className="text-jungle-dim text-xs text-center py-4">Loading meal plan...</p>
              ) : meals.length === 0 ? (
                <p className="text-jungle-dim text-xs text-center py-4">No meal plan generated yet.</p>
              ) : (
                <>
                  <p className="text-[10px] text-jungle-dim">{eatenCount} of {meals.length} meals completed</p>
                  <div className="space-y-2">
                    {meals.map(meal => {
                      const eaten = eatenMeals.has(meal.meal_number);
                      return (
                        <div key={meal.meal_number}
                          className={`rounded-xl border transition-colors ${eaten ? "border-green-500/30 bg-green-500/5" : meal.is_peri ? "border-jungle-accent/30 bg-jungle-accent/5" : "border-jungle-border bg-jungle-deeper"}`}>
                          <div className="flex items-center justify-between px-3 py-2">
                            <div className="flex items-center gap-2">
                              <span className="text-xs font-semibold text-jungle-text">{meal.label}</span>
                              {meal.is_peri && <span className="text-[9px] px-1.5 py-0.5 rounded bg-jungle-accent/20 text-jungle-accent">Peri-WO</span>}
                            </div>
                            <div className="flex items-center gap-2">
                              <span className="text-[10px] text-jungle-dim">{meal.time}</span>
                              <span className="text-[10px] text-jungle-muted font-mono">{Math.round(meal.totals.calories)} kcal</span>
                            </div>
                          </div>
                          <div className="flex gap-3 px-3 pb-1 text-[9px] text-jungle-dim">
                            <span className="text-blue-400">{Math.round(meal.totals.protein_g)}g P</span>
                            <span className="text-amber-400">{Math.round(meal.totals.carbs_g)}g C</span>
                            <span className="text-red-400">{Math.round(meal.totals.fat_g)}g F</span>
                          </div>
                          <div className="px-3 pb-2 space-y-0.5">
                            {meal.ingredients.map((ing, i) => (
                              <div key={i} className={`flex items-center justify-between text-[11px] py-0.5 ${i > 0 ? "border-t border-jungle-border/30" : ""}`}>
                                <span className={`flex-1 ${eaten ? "text-jungle-dim line-through" : "text-jungle-muted"}`}>{ing.name}</span>
                                <div className="flex items-center gap-2 shrink-0">
                                  <span className="text-jungle-dim font-mono w-10 text-right">{ing.quantity_g}g</span>
                                  <span className="text-[9px] text-blue-400/70 w-6 text-right">{Math.round(ing.protein_g)}p</span>
                                  <span className="text-[9px] text-amber-400/70 w-6 text-right">{Math.round(ing.carbs_g)}c</span>
                                  <span className="text-[9px] text-red-400/70 w-6 text-right">{Math.round(ing.fat_g)}f</span>
                                  <span className="text-[9px] text-jungle-dim w-10 text-right">{Math.round(ing.calories)}</span>
                                </div>
                              </div>
                            ))}
                          </div>
                          <div className="px-3 pb-2">
                            <button onClick={() => toggleEaten(meal.meal_number)}
                              className={`w-full py-1.5 rounded-lg text-[10px] font-medium transition-colors ${eaten ? "bg-green-500/20 text-green-400" : "bg-jungle-card border border-jungle-border text-jungle-muted hover:border-jungle-accent hover:text-jungle-accent"}`}>
                              {eaten ? "Completed" : "Mark as Eaten"}
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </>
              )}
            </div>

            {/* ── Cardio ── */}
            <div className="card space-y-3">
              <h2 className="text-sm font-bold text-jungle-text uppercase tracking-wide">Cardio</h2>
              {cardioLogged ? (
                <p className="text-xs text-green-400 text-center py-2">Cardio logged for today</p>
              ) : (
                <div className="space-y-2">
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="text-[9px] text-jungle-dim uppercase">Type</label>
                      <select value={cardioType} onChange={e => setCardioType(e.target.value)} className="input-field mt-0.5 text-xs">
                        <option>Running</option><option>Walking</option><option>Cycling</option>
                        <option>StairMaster</option><option>Elliptical</option><option>Swimming</option>
                      </select>
                    </div>
                    <div>
                      <label className="text-[9px] text-jungle-dim uppercase">Duration (min)</label>
                      <input type="number" value={cardioDuration} onChange={e => setCardioDuration(e.target.value)} className="input-field mt-0.5 text-xs" />
                    </div>
                  </div>
                  <div>
                    <label className="text-[9px] text-jungle-dim uppercase">Intensity</label>
                    <div className="flex gap-1 mt-0.5">
                      {(["Low", "Moderate", "High"] as const).map(level => (
                        <button key={level} onClick={() => setCardioIntensity(level)}
                          className={`flex-1 py-1.5 rounded text-[10px] font-medium transition-colors ${cardioIntensity === level ? "bg-jungle-accent text-jungle-dark" : "bg-jungle-deeper text-jungle-muted"}`}>
                          {level}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] text-jungle-dim">Est. {estCardioKcal} kcal</span>
                    <button onClick={logCardio} className="btn-primary text-xs px-4 py-1.5">Log Cardio</button>
                  </div>
                </div>
              )}
            </div>

            {/* ── Coaching Notes ── */}
            {rx.division_nutrition?.notes && rx.division_nutrition.notes.length > 0 && (
              <div className="card space-y-2">
                <h2 className="text-sm font-bold text-jungle-text uppercase tracking-wide">Coaching Notes</h2>
                <div className="space-y-1.5">
                  {rx.division_nutrition.notes.map((note, i) => (
                    <p key={i} className="text-[11px] text-jungle-muted leading-relaxed">{note}</p>
                  ))}
                </div>
                <div className="grid grid-cols-2 gap-2 pt-1 text-[9px] text-jungle-dim">
                  <span>Meals/day: {rx.division_nutrition.meal_frequency_target}</span>
                  <span>MPS: {rx.division_nutrition.mps_threshold_g}g/meal</span>
                  <span>Carb swing: ±{Math.round(rx.division_nutrition.carb_cycling_factor * 100)}%</span>
                </div>
              </div>
            )}
            {/* ── Quick Links ── */}
            <div className="flex gap-3">
              <a href="/nutrition/peak-week" className="flex-1 btn-secondary text-center text-sm py-2.5">
                Peak Week
              </a>
              <a href="/checkin/review" className="flex-1 btn-secondary text-center text-sm py-2.5">
                Weekly Review
              </a>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
