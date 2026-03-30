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
    <svg viewBox="0 0 100 100" className="w-24 h-24">
      <circle cx={cx} cy={cy} r={r} fill="none" stroke="#1a3328" strokeWidth="14" />
      {/* Protein (blue) */}
      <circle cx={cx} cy={cy} r={r} fill="none" stroke="#60a5fa" strokeWidth="14"
        strokeDasharray={`${pLen} ${circumference - pLen}`}
        strokeDashoffset={-pOff}
        transform={`rotate(-90 ${cx} ${cy})`} strokeLinecap="butt" />
      {/* Carbs (amber) */}
      <circle cx={cx} cy={cy} r={r} fill="none" stroke="#fbbf24" strokeWidth="14"
        strokeDasharray={`${cLen} ${circumference - cLen}`}
        strokeDashoffset={-cOff}
        transform={`rotate(-90 ${cx} ${cy})`} strokeLinecap="butt" />
      {/* Fat (red) */}
      <circle cx={cx} cy={cy} r={r} fill="none" stroke="#f87171" strokeWidth="14"
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
  const [cheatLogged, setCheatLogged] = useState(false);

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

  const meals = mealPlan ? (dayTab === "training" ? mealPlan.training_day : mealPlan.rest_day) : [];
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

        {!rx ? (
          <div className="card text-center py-8">
            <p className="text-jungle-muted text-sm">No nutrition prescription yet.</p>
            <p className="text-jungle-dim text-xs mt-1">Complete a check-in to generate your macros.</p>
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
                    className={`flex-1 py-1.5 rounded-lg text-xs font-medium transition-colors ${dayTab === tab ? "bg-jungle-accent text-jungle-dark" : "text-jungle-muted hover:text-jungle-text"}`}>
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
                    <div className="text-center bg-jungle-deeper rounded-xl py-2">
                      <p className="text-lg font-bold text-blue-400">{Math.round(activeMacros.protein_g)}g</p>
                      <p className="text-[9px] text-jungle-dim">Protein ({pPct}%)</p>
                    </div>
                    <div className="text-center bg-jungle-deeper rounded-xl py-2">
                      <p className="text-lg font-bold text-amber-400">{Math.round(activeMacros.carbs_g)}g</p>
                      <p className="text-[9px] text-jungle-dim">Carbs ({cPct}%)</p>
                    </div>
                    <div className="text-center bg-jungle-deeper rounded-xl py-2">
                      <p className="text-lg font-bold text-red-400">{Math.round(activeMacros.fat_g)}g</p>
                      <p className="text-[9px] text-jungle-dim">Fat ({fPct}%)</p>
                    </div>
                  </div>

                  {/* Pie Chart + Macro Explanation */}
                  <div className="flex items-center gap-4 pt-2 border-t border-jungle-border/40">
                    <MacroPieChart pPct={pPct} cPct={cPct} fPct={fPct} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1.5">
                        <div className="flex gap-1.5">
                          <span className="flex items-center gap-1 text-[9px]"><span className="w-2 h-2 rounded-full bg-blue-400" />P</span>
                          <span className="flex items-center gap-1 text-[9px]"><span className="w-2 h-2 rounded-full bg-amber-400" />C</span>
                          <span className="flex items-center gap-1 text-[9px]"><span className="w-2 h-2 rounded-full bg-red-400" />F</span>
                        </div>
                      </div>
                      <p className="text-[10px] text-jungle-muted leading-relaxed">
                        {PHASE_MACRO_EXPLANATIONS[rx.phase] || PHASE_MACRO_EXPLANATIONS.maintain}
                      </p>
                    </div>
                  </div>
                </>
              )}
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

              {mealPlanLoading ? (
                <p className="text-jungle-dim text-xs text-center py-4">Loading meal plan...</p>
              ) : meals.length === 0 ? (
                <p className="text-jungle-dim text-xs text-center py-4">No meal plan generated yet.</p>
              ) : (
                <>
                  <p className="text-[10px] text-jungle-dim">{loggedCount} of {meals.length} meals logged</p>
                  <div className="space-y-2">
                    {meals.map(meal => {
                      const adh = mealAdherence[meal.meal_number] || 0;
                      const isLogged = adh > 0;
                      return (
                        <div key={meal.meal_number}
                          className={`rounded-2xl border transition-colors ${isLogged ? "border-green-500/30 bg-green-500/5" : meal.is_peri ? "border-jungle-accent/30 bg-jungle-accent/5" : "border-jungle-border/50 bg-jungle-deeper/50"}`}>
                          <div className="flex items-center justify-between px-3 py-2">
                            <div className="flex items-center gap-2">
                              <span className="text-xs font-semibold text-jungle-text">{meal.label}</span>
                              {meal.is_peri && <span className="text-[9px] px-1.5 py-0.5 rounded-lg bg-jungle-accent/20 text-jungle-accent">Peri-WO</span>}
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
                              <div key={i} className={`flex items-center justify-between text-[11px] py-0.5 ${i > 0 ? "border-t border-jungle-border/20" : ""}`}>
                                <span className={`flex-1 ${isLogged && adh >= 8 ? "text-jungle-dim line-through" : "text-jungle-muted"}`}>{ing.name}</span>
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

                          {/* ── Adherence Slider (1-10) ── */}
                          <div className="px-3 pb-3 pt-1 border-t border-jungle-border/20">
                            <div className="flex items-center gap-2">
                              <span className="text-[9px] text-jungle-dim w-16 shrink-0">
                                {adh === 0 ? "Not eaten" : adh <= 3 ? "Barely ate" : adh <= 6 ? "Partial" : adh <= 8 ? "Most of it" : "All of it"}
                              </span>
                              <input
                                type="range"
                                min="0"
                                max="10"
                                step="1"
                                value={adh}
                                onChange={(e) => setAdherence(meal.meal_number, parseInt(e.target.value))}
                                className="flex-1 accent-jungle-accent h-1.5"
                              />
                              <span className={`text-xs font-bold w-8 text-right ${
                                adh === 0 ? "text-jungle-dim" : adh >= 8 ? "text-green-400" : adh >= 5 ? "text-jungle-accent" : "text-red-400"
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

            {/* ── Cheat Meal Logger ── */}
            <div className="card">
              <button onClick={() => setShowCheatForm(!showCheatForm)}
                className="w-full flex items-center justify-between text-left">
                <div>
                  <h3 className="text-xs font-semibold text-jungle-muted uppercase tracking-wider">Cheat Meal</h3>
                  <p className="text-[10px] text-jungle-dim mt-0.5">Log off-plan meals for accurate tracking</p>
                </div>
                <svg className={`w-4 h-4 text-jungle-dim transition-transform ${showCheatForm ? "rotate-180" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>
              {showCheatForm && !cheatLogged && (
                <div className="mt-3 pt-3 border-t border-jungle-border/40 space-y-2">
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
                    onClick={() => { setCheatLogged(true); showToast("Cheat meal logged", "info"); }}
                    disabled={!cheatDesc}
                    className="btn-primary w-full text-xs py-2 disabled:opacity-50">
                    Log Cheat Meal
                  </button>
                </div>
              )}
              {cheatLogged && (
                <div className="mt-3 pt-3 border-t border-jungle-border/40 text-center">
                  <p className="text-xs text-jungle-accent">{cheatDesc} — ~{cheatCals || "?"} kcal logged</p>
                  <p className="text-[9px] text-jungle-dim mt-1">Factored into today&apos;s adherence calculation</p>
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
                onClick={() => showToast("Shopping list generating...", "info")}
                className="btn-secondary text-center text-xs py-2.5"
              >
                Shopping List
              </button>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
