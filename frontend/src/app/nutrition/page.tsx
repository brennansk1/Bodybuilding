"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import NavBar from "@/components/NavBar";
import PageTitle from "@/components/PageTitle";
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
  coach_warnings?: string[];
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

interface ProteinDistributionSummary {
  all_meals_pass: boolean;
  target_per_meal_g: number;
  total_protein_g: number;
  mps_dose_count: number;
  recommended_meal_count: number;
  violations: { label: string; protein_g: number }[];
  explanation: string;
}

interface MicroCoverage {
  coverage: Record<string, { intake: number; target: number; coverage_pct: number; deficient: boolean }>;
  deficiencies: string[];
  rdi_notes: string[];
}

interface HydrationPrescription {
  baseline_ml: number;
  training_add_ml: number;
  total_ml: number;
  total_oz: number;
  per_hour_awake_ml: number;
  coaching_note: string;
}

interface MealPlan {
  phase: string;
  training_day: MealData[];
  rest_day: MealData[];
  protein_distribution?: {
    training: ProteinDistributionSummary | null;
    rest: ProteinDistributionSummary | null;
  } | null;
  hydration?: HydrationPrescription | null;
  micronutrients?: {
    training: MicroCoverage | null;
    rest: MicroCoverage | null;
  } | null;
  filtered_picks?: {
    proteins: string[];
    carbs: string[];
    fats: string[];
    vegetables: string[];
  } | null;
}

interface DailyTotals {
  total_calories: number;
  total_protein_g: number;
  total_carbs_g: number;
  total_fat_g: number;
}

// ─── Macro Pie Chart (SVG) ───────────────────────────────────────────────────

function MacroPieChart({ pPct, cPct, fPct }: { pPct: number; cPct: number; fPct: number }) {
  const r = 40;
  const cx = 50;
  const cy = 50;
  const circumference = 2 * Math.PI * r;

  const pLen = (pPct / 100) * circumference;
  const cLen = (cPct / 100) * circumference;
  const fLen = (fPct / 100) * circumference;

  const pOff = 0;
  const cOff = pLen;
  const fOff = pLen + cLen;

  return (
    <svg
      viewBox="0 0 100 100"
      className="w-24 h-24"
      role="img"
      aria-label={`Macro split: ${Math.round(pPct)}% protein, ${Math.round(cPct)}% carbs, ${Math.round(fPct)}% fat`}
    >
      <title>{`Macro split: ${Math.round(pPct)}% protein, ${Math.round(cPct)}% carbs, ${Math.round(fPct)}% fat`}</title>
      {/* Track — ash so the empty ring reads on marble */}
      <circle cx={cx} cy={cy} r={r} fill="none" stroke="var(--viltrum-border)" strokeWidth="14" />
      {/* Protein (adriatic blue) */}
      <circle cx={cx} cy={cy} r={r} fill="none" stroke="var(--viltrum-info)" strokeWidth="14"
        strokeDasharray={`${pLen} ${circumference - pLen}`}
        strokeDashoffset={-pOff}
        transform={`rotate(-90 ${cx} ${cy})`} strokeLinecap="butt" />
      {/* Carbs (aureus gold) */}
      <circle cx={cx} cy={cy} r={r} fill="none" stroke="var(--viltrum-warning)" strokeWidth="14"
        strokeDasharray={`${cLen} ${circumference - cLen}`}
        strokeDashoffset={-cOff}
        transform={`rotate(-90 ${cx} ${cy})`} strokeLinecap="butt" />
      {/* Fat (legion red) */}
      <circle cx={cx} cy={cy} r={r} fill="none" stroke="var(--viltrum-accent)" strokeWidth="14"
        strokeDasharray={`${fLen} ${circumference - fLen}`}
        strokeDashoffset={-fOff}
        transform={`rotate(-90 ${cx} ${cy})`} strokeLinecap="butt" />
    </svg>
  );
}

// ─── Phase Macro Explanations ────────────────────────────────────────────────

const PHASE_MACRO_EXPLANATIONS: Record<string, string> = {
  cut: "High protein preserves muscle during the deficit. Moderate carbs fuel training intensity. Fat at the minimum floor to protect hormones.",
  peak: "Maximum protein for muscle preservation. Carbs are strategically loaded for glycogen supercompensation. Fat at absolute floor — 7 days only.",
  bulk: "Moderate protein (growth stimulus is covered). High carbs drive training performance and insulin-mediated anabolism. Healthy fats support testosterone.",
  lean_bulk: "Slightly elevated protein to maximize lean tissue gain. Controlled carbs to limit fat spillover. Adequate fat for hormonal health.",
  maintain: "Balanced split to hold current physique. Protein supports ongoing recovery without surplus-driven growth.",
  restoration: "Gradual calorie increase via carbs. Protein tapers as anabolic environment improves. Fat elevated to rebuild hormonal function post-show.",
};

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

  // Meal adherence: 0 = not logged, 1-10 = how much was eaten
  const [mealAdherence, setMealAdherence] = useState<Record<number, number>>({});

  // Cheat meal
  const [showCheatForm, setShowCheatForm] = useState(false);
  const [cheatDesc, setCheatDesc] = useState("");
  const [cheatCals, setCheatCals] = useState("");
  const [cheatLogging, setCheatLogging] = useState(false);
  interface CheatStats {
    allowed: number;
    used_this_week: number;
    remaining: number;
    week_start: string;
    recent: { date: string; description: string; calories: number }[];
  }
  const [cheatStats, setCheatStats] = useState<CheatStats | null>(null);
  const [shoppingOpen, setShoppingOpen] = useState(false);
  const [shoppingLoading, setShoppingLoading] = useState(false);
  const [shoppingList, setShoppingList] = useState<Record<string, unknown[]> | null>(null);

  useEffect(() => {
    if (!loading && !user) { router.push("/auth/login"); return; }
    if (!user) return;

    setFetching(true);
    api.get<CheatStats>("/engine3/cheat-meal/stats").then(setCheatStats).catch(() => {});
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

  const logCheatMeal = async () => {
    if (!cheatDesc.trim()) return;
    setCheatLogging(true);
    try {
      const stats = await api.post<CheatStats>("/engine3/cheat-meal", {
        description: cheatDesc.trim(),
        calories: parseInt(cheatCals || "0") || 0,
      });
      setCheatStats(stats);
      setCheatDesc("");
      setCheatCals("");
      setShowCheatForm(false);
      const verb = stats.used_this_week > stats.allowed ? "logged (over allowance)" : "logged";
      showToast(`Cheat meal ${verb}`, stats.used_this_week > stats.allowed ? "warning" : "success");
    } catch {
      showToast("Couldn't log cheat meal", "error");
    } finally {
      setCheatLogging(false);
    }
  };

  const regenerateMealPlan = async () => {
    if (!window.confirm("Regenerate meal plan? Your current plan will be replaced.")) return;
    setRegenerating(true);
    try {
      const res = await api.post<MealPlan>("/engine3/meal-plan/generate", {});
      setMealPlan(res);
      showToast("Meal plan regenerated", "success");
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      showToast(detail || "Failed to regenerate meal plan", "error");
    }
    setRegenerating(false);
  };

  const loadShoppingList = async () => {
    setShoppingLoading(true);
    try {
      const res = await api.get<Record<string, unknown[]>>("/engine3/shopping-list/weekly");
      setShoppingList(res);
      setShoppingOpen(true);
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      showToast(detail || "Failed to load shopping list", "error");
    } finally {
      setShoppingLoading(false);
    }
  };

  const setAdherence = (mealNum: number, value: number) => {
    setMealAdherence(prev => ({ ...prev, [mealNum]: value }));
  };

  if (loading || !user || fetching) return null;

  const activeMacros: DayMacros | null = (() => {
    if (!rx) return null;
    if (dayTab === "training" && rx.training_day_macros) return rx.training_day_macros;
    if (dayTab === "rest" && rx.rest_day_macros) return rx.rest_day_macros;
    return { calories: rx.target_calories, protein_g: rx.protein_g, carbs_g: rx.carbs_g, fat_g: rx.fat_g };
  })();

  const rawMeals = mealPlan ? (dayTab === "training" ? mealPlan.training_day : mealPlan.rest_day) : [];
  // Hide blank meals (e.g., fasted pre-workout for early-morning lifters).
  const meals = rawMeals.filter(m => m.ingredients && m.ingredients.length > 0);
  const gramsToOz = (g: number) => (g / 28.3495).toFixed(1);
  const loggedCount = Object.values(mealAdherence).filter(v => v > 0).length;

  const pPct = activeMacros ? Math.round((activeMacros.protein_g * 4 / activeMacros.calories) * 100) : 0;
  const cPct = activeMacros ? Math.round((activeMacros.carbs_g * 4 / activeMacros.calories) * 100) : 0;
  const fPct = activeMacros ? 100 - pPct - cPct : 0;

  // Compute average adherence for the day
  const adherenceValues = Object.values(mealAdherence).filter(v => v > 0);
  const avgAdherence = adherenceValues.length > 0
    ? Math.round((adherenceValues.reduce((a, b) => a + b, 0) / adherenceValues.length) * 10)
    : null;

  return (
    <div className="min-h-screen">
      <NavBar username={user.username} onLogout={() => { logout(); router.push("/"); }} />
      <main className="max-w-lg mx-auto px-4 py-6 space-y-4">
        <PageTitle text="Nutrition" />

        <NutritionOverrideBanner />
        <CarbCycleWeekView />

        {!rx ? (
          <div className="card text-center py-8 space-y-3">
            <p className="text-jungle-muted text-sm">No nutrition prescription yet.</p>
            <p className="text-jungle-dim text-xs">
              Log a body weight and run your first check-in to generate personalized macros.
            </p>
            <button
              type="button"
              onClick={() => router.push("/checkin")}
              className="btn-primary w-full"
            >
              Go to Check-in
            </button>
          </div>
        ) : (
          <>
            {/* ── Macro Prescription + Pie Chart ── */}
            <div className="card space-y-3">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-bold text-jungle-text uppercase tracking-wide">Daily Macros</h2>
                <span className="text-[10px] px-2 py-0.5 rounded-lg bg-jungle-accent/20 text-jungle-accent font-medium capitalize">{rx.phase}</span>
              </div>

              <div className="flex gap-1 bg-jungle-deeper rounded-xl p-0.5">
                {(["training", "rest"] as const).map(tab => (
                  <button key={tab} onClick={() => setDayTab(tab)}
                    className={`flex-1 py-1.5 rounded-lg text-xs font-medium transition-colors ${dayTab === tab ? "bg-jungle-accent text-white" : "text-jungle-muted hover:text-jungle-text"}`}>
                    {tab === "training" ? "Training Day" : "Rest Day"}
                  </button>
                ))}
              </div>

              {activeMacros && (() => {
                const protCals = Math.round(activeMacros.protein_g * 4);
                const carbCals = Math.round(activeMacros.carbs_g * 4);
                const fatCals = Math.round(activeMacros.fat_g * 9);
                const totalCals = protCals + carbCals + fatCals;
                // Segment widths for the stacked horizontal bar
                const pWidth = totalCals ? (protCals / totalCals) * 100 : 0;
                const cWidth = totalCals ? (carbCals / totalCals) * 100 : 0;
                const fWidth = totalCals ? (fatCals / totalCals) * 100 : 0;
                return (
                  <>
                    {/* Calorie hero */}
                    <div className="flex items-end gap-3 justify-center pb-2">
                      <p className="text-4xl font-bold text-jungle-text leading-none">{Math.round(activeMacros.calories)}</p>
                      <div className="pb-0.5">
                        <p className="text-[10px] text-jungle-dim uppercase tracking-wider leading-tight">kcal target</p>
                        <p className="text-[10px] text-jungle-accent leading-tight">{dayTab === "training" ? "Training Day" : "Rest Day"}</p>
                      </div>
                    </div>

                    {/* Stacked macro bar */}
                    <div>
                      <div className="flex h-3 rounded-full overflow-hidden bg-jungle-deeper">
                        <div style={{ width: `${pWidth}%` }} className="bg-blue-400" />
                        <div style={{ width: `${cWidth}%` }} className="bg-amber-400" />
                        <div style={{ width: `${fWidth}%` }} className="bg-red-400" />
                      </div>
                      <div className="flex justify-between text-[9px] text-jungle-dim mt-1">
                        <span>{pPct}% P</span>
                        <span>{cPct}% C</span>
                        <span>{fPct}% F</span>
                      </div>
                    </div>

                    {/* Macro cards with per-kg metric — categorical colors matching the pie */}
                    <div className="grid grid-cols-3 gap-2">
                      <div className="bg-alabaster rounded-button p-3 border-t-2 border-adriatic">
                        <div className="flex items-baseline gap-1">
                          <p className="metric-md text-adriatic">{Math.round(activeMacros.protein_g)}</p>
                          <p className="text-[10px] text-travertine">g</p>
                        </div>
                        <p className="text-[9px] text-iron uppercase tracking-[0.15em] mt-0.5">Protein</p>
                        <p className="text-[9px] text-travertine">{protCals} kcal</p>
                      </div>
                      <div className="bg-alabaster rounded-button p-3 border-t-2 border-aureus">
                        <div className="flex items-baseline gap-1">
                          <p className="metric-md text-aureus">{Math.round(activeMacros.carbs_g)}</p>
                          <p className="text-[10px] text-travertine">g</p>
                        </div>
                        <p className="text-[9px] text-iron uppercase tracking-[0.15em] mt-0.5">Carbs</p>
                        <p className="text-[9px] text-travertine">{carbCals} kcal</p>
                      </div>
                      <div className="bg-alabaster rounded-button p-3 border-t-2 border-legion">
                        <div className="flex items-baseline gap-1">
                          <p className="metric-md text-legion">{Math.round(activeMacros.fat_g)}</p>
                          <p className="text-[10px] text-travertine">g</p>
                        </div>
                        <p className="text-[9px] text-iron uppercase tracking-[0.15em] mt-0.5">Fat</p>
                        <p className="text-[9px] text-travertine">{fatCals} kcal</p>
                      </div>
                    </div>

                    {/* Coach explanation */}
                    <p className="text-[10px] text-jungle-muted leading-relaxed pt-2 border-t border-jungle-border/40">
                      {PHASE_MACRO_EXPLANATIONS[rx.phase] || PHASE_MACRO_EXPLANATIONS.maintain}
                    </p>
                  </>
                );
              })()}
            </div>

            {/* ── Today's Intake vs Target ── */}
            {dailyTotals && activeMacros && (
              <div className="card space-y-3">
                <div className="flex items-center justify-between">
                  <h2 className="text-sm font-bold text-jungle-text uppercase tracking-wide">Today&apos;s Progress</h2>
                  {avgAdherence !== null && (
                    <span className={`text-[10px] px-2 py-0.5 rounded-lg font-medium ${
                      avgAdherence >= 90 ? "bg-green-500/15 text-green-400" :
                      avgAdherence >= 70 ? "bg-jungle-accent/15 text-jungle-accent" :
                      "bg-red-500/15 text-red-400"
                    }`}>
                      {avgAdherence}% adherence
                    </span>
                  )}
                </div>
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

              {mealPlan?.filtered_picks && (() => {
                const fp = mealPlan.filtered_picks;
                const all = [
                  ...fp.proteins.map((n) => ({ name: n, kind: "protein" })),
                  ...fp.carbs.map((n) => ({ name: n, kind: "carb" })),
                  ...fp.fats.map((n) => ({ name: n, kind: "fat" })),
                  ...fp.vegetables.map((n) => ({ name: n, kind: "vegetable" })),
                ];
                if (all.length === 0) return null;
                return (
                  <div className="bg-amber-500/10 border border-amber-500/40 rounded-lg px-3 py-2">
                    <p className="text-[11px] text-amber-400 font-semibold mb-1">
                      ⚠ {all.length} pick{all.length > 1 ? "s" : ""} not available in {mealPlan.phase.replace(/_/g, " ")}
                    </p>
                    <p className="text-[10px] text-jungle-muted leading-snug">
                      These staples were filtered out because coaches drop them during this phase:{" "}
                      <span className="text-amber-400">{all.map((e) => e.name).join(", ")}</span>. Pick leaner alternatives in Settings → Your Coach&apos;s Staples, or transition phases.
                    </p>
                  </div>
                );
              })()}

              {mealPlanLoading ? (
                <p className="text-jungle-dim text-xs text-center py-4">Loading meal plan...</p>
              ) : meals.length === 0 ? (
                <p className="text-jungle-dim text-xs text-center py-4">No meal plan generated yet.</p>
              ) : (
                <>
                  <p className="text-[10px] text-jungle-dim">{loggedCount} of {meals.length} meals logged</p>
                  <div className="space-y-2">
                    {meals.map((meal, mealIdx) => {
                      const adh = mealAdherence[meal.meal_number] || 0;
                      const isLogged = adh > 0;
                      // Alternating row tint — tames the visual monotony of a long meal stack
                      // without losing the logged/peri state cues.
                      const stateCls = isLogged
                        ? "border-laurel/30 bg-viltrum-laurel-bg"
                        : meal.is_peri
                          ? "border-legion/30 bg-blush"
                          : mealIdx % 2 === 0
                            ? "border-ash bg-white"
                            : "border-ash bg-alabaster";
                      return (
                        <div key={meal.meal_number}
                          className={`rounded-card border transition-colors ${stateCls}`}>
                          <div className="flex items-center justify-between px-3 py-2">
                            <div className="flex items-center gap-2">
                              <span className="h-card text-obsidian">{meal.label}</span>
                              {meal.is_peri && (
                                <span className="text-[9px] tracking-[0.15em] uppercase px-1.5 py-0.5 rounded bg-legion text-white font-medium">
                                  Peri-WO
                                </span>
                              )}
                              {isLogged && (
                                <span className="text-[9px] tracking-[0.15em] uppercase text-laurel">Logged</span>
                              )}
                            </div>
                            <div className="flex items-center gap-2">
                              <span className="text-[10px] tracking-[0.1em] uppercase text-travertine">{meal.time}</span>
                              <span className="text-[10px] text-iron font-mono tabular-nums">{Math.round(meal.totals.calories)} kcal</span>
                            </div>
                          </div>
                          <div className="flex gap-3 px-3 pb-1 text-[10px] font-medium">
                            <span className="text-adriatic">{Math.round(meal.totals.protein_g)}g P</span>
                            <span className="text-aureus">{Math.round(meal.totals.carbs_g)}g C</span>
                            <span className="text-legion">{Math.round(meal.totals.fat_g)}g F</span>
                          </div>
                          <div className="px-3 pb-2 space-y-0.5">
                            {meal.ingredients.map((ing, i) => (
                              <div key={i} className={`flex items-center justify-between text-[11px] py-0.5 ${i > 0 ? "border-t border-ash/60" : ""}`}>
                                <span className={`flex-1 ${isLogged && adh >= 8 ? "text-travertine line-through" : "text-charcoal"}`}>{ing.name}</span>
                                <div className="flex items-center gap-2 shrink-0">
                                  <span className="text-iron font-mono tabular-nums w-10 text-right">{ing.quantity_g}g</span>
                                  <span className="text-[9px] text-travertine font-mono tabular-nums w-10 text-right">{gramsToOz(ing.quantity_g)}oz</span>
                                  <span className="text-[9px] text-adriatic/80 tabular-nums w-6 text-right">{Math.round(ing.protein_g)}p</span>
                                  <span className="text-[9px] text-aureus/80 tabular-nums w-6 text-right">{Math.round(ing.carbs_g)}c</span>
                                  <span className="text-[9px] text-legion/80 tabular-nums w-6 text-right">{Math.round(ing.fat_g)}f</span>
                                  <span className="text-[9px] text-travertine tabular-nums w-10 text-right">{Math.round(ing.calories)}</span>
                                </div>
                              </div>
                            ))}
                          </div>

                          {/* ── Adherence Slider (1-10) ── */}
                          <div className="px-3 pb-3 pt-1 border-t border-ash/60">
                            <div className="flex items-center gap-2">
                              <span className="text-[9px] tracking-[0.1em] uppercase text-travertine w-20 shrink-0">
                                {adh === 0 ? "Not eaten" : adh <= 3 ? "Barely ate" : adh <= 6 ? "Partial" : adh <= 8 ? "Most of it" : "All of it"}
                              </span>
                              <input
                                type="range"
                                min="0"
                                max="10"
                                step="1"
                                value={adh}
                                onChange={(e) => setAdherence(meal.meal_number, parseInt(e.target.value))}
                                className="flex-1 accent-legion h-1.5"
                              />
                              <span className={`text-xs font-bold tabular-nums w-8 text-right ${
                                adh === 0 ? "text-travertine" : adh >= 8 ? "text-laurel" : adh >= 5 ? "text-centurion" : "text-aureus"
                              }`}>
                                {adh === 0 ? "—" : `${adh * 10}%`}
                              </span>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </>
              )}
            </div>

            {/* ── Coach Warnings ── */}
            {rx.coach_warnings && rx.coach_warnings.length > 0 && (
              <div className="card border-l-4 border-amber-500/70 space-y-1.5">
                <h3 className="text-[10px] text-amber-400 uppercase tracking-wider font-bold">
                  Coach Notes
                </h3>
                {rx.coach_warnings.map((note, i) => (
                  <p key={i} className="text-[11px] text-jungle-muted leading-snug">
                    {note}
                  </p>
                ))}
              </div>
            )}

            {/* ── Protein Distribution + Hydration ── */}
            {mealPlan && (mealPlan.protein_distribution || mealPlan.hydration) && (
              <div className="card space-y-3">
                <h2 className="text-sm font-bold text-jungle-text uppercase tracking-wide">
                  Coach Checks
                </h2>
                {mealPlan.protein_distribution && mealPlan.protein_distribution[dayTab] && (
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] text-jungle-dim uppercase tracking-wider">Protein Distribution</span>
                      <span className={`text-[10px] font-bold ${mealPlan.protein_distribution[dayTab]!.all_meals_pass ? "text-green-400" : "text-amber-400"}`}>
                        {mealPlan.protein_distribution[dayTab]!.mps_dose_count}/{mealPlan.protein_distribution[dayTab]!.recommended_meal_count} MPS doses
                      </span>
                    </div>
                    <p className="text-[10px] text-jungle-muted leading-tight">
                      {mealPlan.protein_distribution[dayTab]!.explanation}
                    </p>
                    {mealPlan.protein_distribution[dayTab]!.violations.length > 0 && (
                      <div className="text-[10px] text-amber-400">
                        Low-protein meals: {mealPlan.protein_distribution[dayTab]!.violations.map(v => v.label).join(", ")}
                      </div>
                    )}
                  </div>
                )}
                {mealPlan.hydration && (
                  <div className="border-t border-jungle-border/30 pt-2.5 space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] text-jungle-dim uppercase tracking-wider">Hydration</span>
                      <span className="text-sm font-bold text-blue-400">{(mealPlan.hydration.total_ml / 1000).toFixed(1)} L · {mealPlan.hydration.total_oz} oz</span>
                    </div>
                    <p className="text-[10px] text-jungle-muted leading-tight">
                      ~{mealPlan.hydration.per_hour_awake_ml} ml/hour awake. {mealPlan.hydration.coaching_note}
                    </p>
                  </div>
                )}
                {mealPlan.micronutrients && mealPlan.micronutrients[dayTab] && mealPlan.micronutrients[dayTab]!.deficiencies.length > 0 && (
                  <div className="border-t border-jungle-border/30 pt-2.5 space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] text-jungle-dim uppercase tracking-wider">Micronutrient Gaps</span>
                      <span className="text-[10px] text-amber-400 font-semibold">
                        {mealPlan.micronutrients[dayTab]!.deficiencies.length} flagged
                      </span>
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {mealPlan.micronutrients[dayTab]!.deficiencies.map((k) => {
                        const data = mealPlan.micronutrients![dayTab]!.coverage[k];
                        return (
                          <span key={k} className="text-[10px] px-2 py-0.5 rounded-md bg-amber-500/10 text-amber-400">
                            {k.replace(/_/g, " ")} {data.coverage_pct.toFixed(0)}%
                          </span>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* ── Cheat Meal Logger ── */}
            <div className="card">
              <button onClick={() => setShowCheatForm(!showCheatForm)}
                className="w-full flex items-center justify-between text-left">
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <h3 className="text-xs font-semibold text-jungle-muted uppercase tracking-wider">Cheat Meal</h3>
                    {cheatStats && (() => {
                      const { used_this_week, allowed } = cheatStats;
                      const over = used_this_week > allowed;
                      const at = used_this_week === allowed && allowed > 0;
                      const color = allowed === 0
                        ? "bg-jungle-deeper text-jungle-dim border-jungle-border"
                        : over
                        ? "bg-red-500/20 text-red-400 border-red-500/50"
                        : at
                        ? "bg-amber-500/20 text-amber-400 border-amber-500/50"
                        : "bg-green-500/20 text-green-400 border-green-500/50";
                      return (
                        <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full border ${color}`}>
                          {used_this_week} / {allowed} this week
                        </span>
                      );
                    })()}
                  </div>
                  <p className="text-[10px] text-jungle-dim mt-0.5">
                    {cheatStats?.allowed === 0
                      ? "No cheat meals budgeted this week — strict phase"
                      : "Log off-plan meals for accurate tracking"}
                  </p>
                </div>
                <svg className={`w-4 h-4 text-jungle-dim transition-transform ${showCheatForm ? "rotate-180" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>
              {showCheatForm && (
                <div className="mt-3 pt-3 border-t border-jungle-border/40 space-y-2">
                  {cheatStats?.allowed === 0 ? (
                    <p className="text-[11px] text-jungle-muted">
                      Your current phase has no cheat meal allowance. Adjust in Settings → Nutrition if you&apos;re in maintenance or off-season.
                    </p>
                  ) : (
                    <>
                      <div>
                        <label className="text-[9px] text-jungle-dim uppercase">What did you eat?</label>
                        <input type="text" value={cheatDesc} onChange={e => setCheatDesc(e.target.value)}
                          className="input-field mt-0.5 text-xs" placeholder="e.g. Pizza, burger and fries, ice cream..." />
                      </div>
                      <div>
                        <label className="text-[9px] text-jungle-dim uppercase">Estimated calories</label>
                        <input type="number" value={cheatCals} onChange={e => setCheatCals(e.target.value)}
                          className="input-field mt-0.5 text-xs" placeholder="e.g. 1200" />
                      </div>
                      <button
                        onClick={logCheatMeal}
                        disabled={!cheatDesc || cheatLogging}
                        className="btn-primary w-full text-xs py-2 disabled:opacity-50">
                        {cheatLogging ? "Logging…" : "Log Cheat Meal"}
                      </button>
                      {cheatStats && cheatStats.used_this_week >= cheatStats.allowed && cheatStats.allowed > 0 && (
                        <p className="text-[10px] text-amber-400">
                          You&apos;ve already hit your weekly cheat allowance. Logging another puts you over.
                        </p>
                      )}
                    </>
                  )}
                </div>
              )}
              {cheatStats && cheatStats.recent.length > 0 && !showCheatForm && (
                <div className="mt-3 pt-3 border-t border-jungle-border/40 space-y-1">
                  <p className="text-[9px] text-jungle-dim uppercase">Recent</p>
                  {cheatStats.recent.slice(0, 3).map((entry, i) => (
                    <div key={i} className="flex justify-between text-[10px]">
                      <span className="text-jungle-muted truncate pr-2">{entry.date} · {entry.description}</span>
                      <span className="text-jungle-dim">~{entry.calories} kcal</span>
                    </div>
                  ))}
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
                  <span>Carb swing: +/-{Math.round(rx.division_nutrition.carb_cycling_factor * 100)}%</span>
                </div>
              </div>
            )}

            {/* ── Quick Links ── */}
            <div className="grid grid-cols-3 gap-2">
              <a href="/nutrition/peak-week" className="btn-secondary text-center text-xs py-2.5">
                Peak Week
              </a>
              <a href="/checkin/review" className="btn-secondary text-center text-xs py-2.5">
                Weekly Review
              </a>
              <button
                onClick={loadShoppingList}
                disabled={shoppingLoading}
                className="btn-secondary text-center text-xs py-2.5 disabled:opacity-50"
              >
                {shoppingLoading ? "Loading..." : "Shopping List"}
              </button>
            </div>
          </>
        )}
      </main>

      {shoppingOpen && (
        <div
          className="fixed inset-0 z-50 bg-viltrum-obsidian/45 backdrop-blur-sm flex items-end sm:items-center justify-center p-3"
          onClick={() => setShoppingOpen(false)}
        >
          <div
            className="bg-jungle-card border border-jungle-border rounded-2xl w-full max-w-lg max-h-[85vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="sticky top-0 bg-jungle-card/95 backdrop-blur-md border-b border-jungle-border px-4 py-3 flex items-center justify-between">
              <h3 className="text-sm font-bold text-jungle-text uppercase tracking-wide">Weekly Shopping List</h3>
              <button
                onClick={() => setShoppingOpen(false)}
                className="text-jungle-dim hover:text-jungle-accent text-xl leading-none px-2"
                aria-label="Close shopping list"
              >
                ×
              </button>
            </div>
            <div className="p-4 space-y-4">
              {shoppingList && Object.keys(shoppingList).length > 0 ? (
                Object.entries(shoppingList).map(([section, items]) => (
                  <div key={section}>
                    <p className="text-[10px] text-jungle-dim uppercase tracking-wider mb-1.5">
                      {section.replace(/_/g, " ")}
                    </p>
                    <ul className="space-y-1">
                      {(items as Array<{ name: string; quantity_g: number; quantity_display?: string }>).map((item, i) => (
                        <li key={i} className="flex items-center justify-between text-sm border-b border-jungle-border/30 py-1.5">
                          <span className="text-jungle-text">{item.name}</span>
                          <span className="text-jungle-dim font-mono text-xs">
                            {item.quantity_display || `${Math.round(item.quantity_g)}g`}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </div>
                ))
              ) : (
                <p className="text-jungle-dim text-xs text-center py-8">No shopping list generated yet.</p>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}


// ---------------------------------------------------------------------------
// V3 — Manual nutrition mode override banner
// ---------------------------------------------------------------------------
function NutritionOverrideBanner() {
  interface PPMStatus {
    nutrition_mode_override?: string | null;
    current_phase?: string;
  }
  const [status, setStatus] = useState<PPMStatus | null>(null);
  useEffect(() => {
    api.get<PPMStatus>("/ppm/status").then(setStatus).catch(() => {});
  }, []);

  if (!status) return null;

  const override = status.nutrition_mode_override;
  if (!override) return null;

  const label = override === "bulk"
    ? "Manual: Bulk"
    : override === "cut"
      ? "Manual: Cut"
      : override === "maintain"
        ? "Manual: Maintain"
        : "Manual Override";
  const subtitle = "Engine phase detection suppressed. You set this. Clear in Settings → Nutrition.";
  const color = "border-aureus bg-viltrum-aureus-bg text-aureus";

  return (
    <div className={`border ${color} rounded-card p-3 flex items-start gap-3`}>
      <svg className="w-5 h-5 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
      </svg>
      <div className="flex-1 min-w-0">
        <div className="text-sm font-semibold">{label}</div>
        <p className="text-[11px] body-serif-sm italic leading-snug opacity-80">{subtitle}</p>
      </div>
    </div>
  );
}


// ---------------------------------------------------------------------------
// V3 — Carb cycle weekly calendar (H/M/L day breakdown)
// ---------------------------------------------------------------------------
function CarbCycleWeekView() {
  interface DayMacros { protein_g: number; carbs_g: number; fat_g: number; target_calories: number }
  interface CarbCycle {
    high_day: DayMacros | null;
    medium_day: DayMacros | null;
    low_day: DayMacros | null;
    days_per_week?: { high: number; medium: number; low: number };
  }
  const [cc, setCc] = useState<CarbCycle | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get<CarbCycle>("/engine3/carb-cycle")
      .then(setCc)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading || !cc || (!cc.high_day && !cc.medium_day && !cc.low_day)) return null;

  // Week template: H, M, H, L, M, H, L (2H 3M 2L default; adapted to training split)
  // This is a display convention — actual assignment happens in the backend.
  const weekTemplate = ["H", "M", "H", "L", "M", "H", "L"];
  const days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

  const dayData: Record<string, DayMacros | null> = {
    H: cc.high_day,
    M: cc.medium_day,
    L: cc.low_day,
  };
  const colors: Record<string, string> = {
    H: "bg-viltrum-aureus-bg border-aureus text-aureus",
    M: "bg-viltrum-adriatic-bg border-adriatic text-adriatic",
    L: "bg-viltrum-alabaster border-viltrum-ash text-viltrum-iron",
  };

  return (
    <div className="card space-y-3">
      <div className="flex items-baseline justify-between">
        <h2 className="text-sm font-bold text-jungle-text uppercase tracking-wide">Carb Cycle — This Week</h2>
        <span className="text-[10px] text-viltrum-travertine uppercase tracking-[2px]">H / M / L</span>
      </div>
      <p className="text-[11px] text-viltrum-iron body-serif-sm italic leading-snug">
        Carbs swing with training load. High on big-muscle days, medium on small-muscle days, low on rest. Protein + fat stay constant.
      </p>
      <div className="grid grid-cols-7 gap-1.5">
        {weekTemplate.map((type, i) => (
          <div
            key={i}
            className={`rounded-lg border text-center py-2 ${colors[type]}`}
            title={`${days[i]} — ${type === "H" ? "High" : type === "M" ? "Medium" : "Low"} carb day`}
          >
            <div className="text-[9px] uppercase tracking-widest opacity-70">{days[i]}</div>
            <div className="text-base font-bold leading-none mt-0.5">{type}</div>
            {dayData[type] && (
              <div className="text-[9px] mt-1 tabular-nums">
                {Math.round(dayData[type]!.carbs_g)}c
              </div>
            )}
          </div>
        ))}
      </div>
      <div className="grid grid-cols-3 gap-2 pt-2 border-t border-viltrum-ash text-[11px]">
        {(["H", "M", "L"] as const).map((t) => {
          const d = dayData[t];
          if (!d) return null;
          return (
            <div key={t} className={`rounded-lg px-2 py-1.5 border ${colors[t]}`}>
              <div className="text-[9px] uppercase tracking-widest opacity-70 mb-0.5">
                {t === "H" ? "High Day" : t === "M" ? "Medium" : "Low"}
              </div>
              <div className="tabular-nums">{Math.round(d.target_calories)} kcal</div>
              <div className="tabular-nums opacity-80">{Math.round(d.carbs_g)}C / {Math.round(d.protein_g)}P / {Math.round(d.fat_g)}F</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
