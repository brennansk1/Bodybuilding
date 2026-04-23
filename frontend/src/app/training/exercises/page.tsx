"use client";

import { useEffect, useMemo, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import NavBar from "@/components/NavBar";
import PageTitle from "@/components/PageTitle";
import ViltrumLoader from "@/components/ViltrumLoader";
import { api } from "@/lib/api";

interface Exercise {
  id: string;
  name: string;
  primary_muscle: string;
  secondary_muscles: string[];
  equipment: string;
  movement_type: string;
  compound: boolean;
}

const MUSCLE_GROUPS = [
  "all",
  "chest",
  "back",
  "shoulders",
  "biceps",
  "triceps",
  "forearms",
  "quads",
  "hamstrings",
  "glutes",
  "calves",
  "abs",
  "traps",
] as const;

const EQUIPMENT_LABELS: Record<string, string> = {
  barbell: "Barbell",
  dumbbell: "Dumbbell",
  cable: "Cable",
  machine: "Machine",
  bodyweight: "Bodyweight",
  e_z_curl_bar: "EZ Bar",
  kettlebell: "Kettlebell",
  bands: "Bands",
  other: "Other",
};

function muscleLabel(muscle: string): string {
  return muscle.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

/** Equipment badge — Viltrum semantic families, muted so the exercise name wins */
function equipmentBadge(equipment: string): string {
  switch (equipment) {
    case "barbell":    return "bg-limestone text-obsidian border-pumice";
    case "dumbbell":   return "bg-viltrum-adriatic-bg text-adriatic border-adriatic/30";
    case "cable":      return "bg-viltrum-aureus-bg text-aureus border-aureus/30";
    case "machine":    return "bg-alabaster text-iron border-ash";
    case "bodyweight": return "bg-viltrum-laurel-bg text-laurel border-laurel/30";
    case "kettlebell": return "bg-blush text-centurion border-terracotta";
    default:           return "bg-alabaster text-travertine border-ash";
  }
}

export default function ExercisesPage() {
  const router = useRouter();
  const { user, loading, logout } = useAuth();
  const [exercises, setExercises] = useState<Exercise[]>([]);
  const [searchQ, setSearchQ] = useState("");
  const [selectedMuscle, setSelectedMuscle] = useState<string>("all");
  const [compoundOnly, setCompoundOnly] = useState(false);
  const [fetching, setFetching] = useState(false);
  const [selectedExercise, setSelectedExercise] = useState<Exercise | null>(null);

  const fetchExercises = useCallback(async () => {
    setFetching(true);
    try {
      if (searchQ.length >= 2) {
        const params = new URLSearchParams({ q: searchQ });
        if (selectedMuscle !== "all") params.set("muscle", selectedMuscle);
        const data = await api.get<Exercise[]>(`/engine2/exercises/search?${params}`);
        setExercises(data);
      } else {
        const params = new URLSearchParams();
        if (selectedMuscle !== "all") params.set("muscle", selectedMuscle);
        const data = await api.get<Exercise[]>(`/engine2/exercises?${params}`);
        setExercises(data);
      }
    } catch {
      //
    } finally {
      setFetching(false);
    }
  }, [searchQ, selectedMuscle]);

  useEffect(() => {
    if (!loading && !user) { router.push("/auth/login"); return; }
    if (user) {
      const timer = setTimeout(fetchExercises, searchQ.length >= 2 ? 300 : 0);
      return () => clearTimeout(timer);
    }
  }, [user, loading, router, fetchExercises, searchQ]);

  if (loading || !user) return null;

  const filtered = useMemo(
    () => (compoundOnly ? exercises.filter((e) => e.compound) : exercises),
    [exercises, compoundOnly]
  );

  // Group by muscle for display (for the "browse" view). In search mode we
  // render a flat grid — search ranking is more valuable than alphabetical.
  const grouped = useMemo(() => {
    const g: Record<string, Exercise[]> = {};
    filtered.forEach((ex) => {
      const key = ex.primary_muscle;
      if (!g[key]) g[key] = [];
      g[key].push(ex);
    });
    return g;
  }, [filtered]);

  // Left-rail muscle counts — derived from everything fetched so the rail
  // shows the full library, not just the post-filter slice.
  const muscleCounts = useMemo(() => {
    const counts: Record<string, number> = { all: exercises.length };
    exercises.forEach((e) => {
      counts[e.primary_muscle] = (counts[e.primary_muscle] ?? 0) + 1;
    });
    return counts;
  }, [exercises]);

  const searchMode = searchQ.length >= 2;
  const visibleGroups = selectedMuscle === "all"
    ? Object.entries(grouped).sort(([a], [b]) => a.localeCompare(b))
    : Object.entries(grouped).filter(([m]) => m === selectedMuscle);

  return (
    <div className="min-h-screen">
      <NavBar username={user.username} onLogout={() => { logout(); router.push("/"); }} />

      <main className="container-app py-6">
        <PageTitle
          text="Exercise Library"
          subtitle={`${exercises.length} movements · filter by muscle, equipment, or pattern`}
          actions={<a href="/training" className="btn-secondary text-sm px-3 py-2">← Training</a>}
        />

        {/* Search + compound toggle */}
        <div className="card mb-5 flex flex-col md:flex-row md:items-center gap-3">
          <div className="relative flex-1">
            <svg
              className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-travertine pointer-events-none"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth={1.75}
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <circle cx="11" cy="11" r="7" />
              <path d="M21 21l-4-4" />
            </svg>
            <input
              type="text"
              placeholder="Search — e.g. bench press, squat, row…"
              value={searchQ}
              onChange={(e) => setSearchQ(e.target.value)}
              className="input-field w-full pl-9"
            />
            {searchQ && (
              <button
                onClick={() => setSearchQ("")}
                aria-label="Clear search"
                className="absolute right-3 top-1/2 -translate-y-1/2 text-travertine hover:text-obsidian text-[10px] tracking-[0.15em] uppercase"
              >
                Clear
              </button>
            )}
          </div>

          <button
            onClick={() => setCompoundOnly(!compoundOnly)}
            className={`flex items-center gap-2 px-3 py-2 rounded-button text-xs tracking-[0.1em] uppercase border transition-colors shrink-0 ${
              compoundOnly
                ? "border-legion bg-blush text-centurion"
                : "border-ash text-iron hover:border-pumice"
            }`}
          >
            <span
              className={`w-3.5 h-3.5 rounded border flex items-center justify-center ${
                compoundOnly ? "bg-legion border-legion" : "border-pewter"
              }`}
              aria-hidden
            >
              {compoundOnly && (
                <svg viewBox="0 0 16 16" className="w-2.5 h-2.5 text-white" fill="none" stroke="currentColor" strokeWidth={3}>
                  <path d="M3 8l3 3 7-7" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              )}
            </span>
            Compound only
          </button>

          <span className="text-[10px] tracking-[0.15em] uppercase text-travertine shrink-0">
            {filtered.length} results
          </span>
        </div>

        {/* Two-column layout: sticky muscle rail + results grid */}
        <div className="grid grid-cols-1 md:grid-cols-[200px_1fr] gap-5">
          {/* Muscle rail */}
          <aside className="md:sticky md:top-24 self-start">
            {/* Mobile: horizontal scrolling chips */}
            <div className="md:hidden -mx-4 px-4 overflow-x-auto scrollbar-hide">
              <div className="flex gap-1.5 pb-2 w-max">
                {MUSCLE_GROUPS.map((m) => (
                  <button
                    key={m}
                    onClick={() => setSelectedMuscle(m)}
                    className={`px-3 py-1.5 rounded-button text-[11px] tracking-[0.08em] uppercase whitespace-nowrap transition-colors shrink-0 border ${
                      selectedMuscle === m
                        ? "bg-obsidian border-obsidian text-white"
                        : "bg-white border-ash text-iron hover:border-pumice"
                    }`}
                  >
                    {m === "all" ? "All" : muscleLabel(m)}
                    {muscleCounts[m] != null && (
                      <span className="ml-1.5 opacity-60">{muscleCounts[m]}</span>
                    )}
                  </button>
                ))}
              </div>
            </div>

            {/* Desktop: vertical list */}
            <nav className="hidden md:block card p-0 overflow-hidden">
              <p className="h-section px-4 pt-4 pb-2 text-travertine">Muscle Group</p>
              <ul className="divide-y divide-ash">
                {MUSCLE_GROUPS.map((m) => {
                  const active = selectedMuscle === m;
                  return (
                    <li key={m}>
                      <button
                        onClick={() => setSelectedMuscle(m)}
                        className={`w-full text-left px-4 py-2.5 text-sm flex items-center justify-between transition-colors ${
                          active
                            ? "bg-blush text-centurion border-l-2 border-legion pl-[14px]"
                            : "text-iron hover:bg-alabaster"
                        }`}
                      >
                        <span className={active ? "font-medium" : ""}>
                          {m === "all" ? "All movements" : muscleLabel(m)}
                        </span>
                        <span className={`text-[10px] tabular-nums ${active ? "text-centurion" : "text-travertine"}`}>
                          {muscleCounts[m] ?? 0}
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            </nav>
          </aside>

          {/* Results */}
          <section>
            {fetching ? (
              <div className="card">
                <ViltrumLoader variant="inline" />
              </div>
            ) : searchMode ? (
              // Search mode — flat grid, ranked by API
              filtered.length === 0 ? (
                <div className="card text-center py-16 space-y-2">
                  <p className="h-display-sm">No matches</p>
                  <p className="body-serif-sm italic text-iron max-w-md mx-auto">
                    Nothing matched &ldquo;{searchQ}&rdquo;. Try a shorter keyword, or clear the search and browse by muscle group.
                  </p>
                </div>
              ) : (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                  {filtered.map((ex) => (
                    <ExerciseCard
                      key={ex.id}
                      exercise={ex}
                      onClick={() => setSelectedExercise(selectedExercise?.id === ex.id ? null : ex)}
                      expanded={selectedExercise?.id === ex.id}
                    />
                  ))}
                </div>
              )
            ) : visibleGroups.length === 0 ? (
              <div className="card text-center py-16">
                <p className="body-serif-sm italic text-iron">No exercises in this group.</p>
              </div>
            ) : (
              <div className="space-y-6">
                {visibleGroups.map(([muscle, exs]) => (
                  <div key={muscle}>
                    <div className="flex items-baseline justify-between mb-3 px-1">
                      <h3 className="h-card text-obsidian">
                        {muscleLabel(muscle)}
                      </h3>
                      <span className="text-[10px] tracking-[0.2em] uppercase text-travertine tabular-nums">
                        {exs.length}
                      </span>
                    </div>
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                      {exs.map((ex) => (
                        <ExerciseCard
                          key={ex.id}
                          exercise={ex}
                          onClick={() => setSelectedExercise(selectedExercise?.id === ex.id ? null : ex)}
                          expanded={selectedExercise?.id === ex.id}
                        />
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>
        </div>
      </main>

      <div className="md:hidden h-16" />
    </div>
  );
}

function ExerciseCard({
  exercise,
  onClick,
  expanded,
}: {
  exercise: Exercise;
  onClick: () => void;
  expanded: boolean;
}) {
  return (
    <div
      className={`card transition-all ${expanded ? "border-legion ring-1 ring-legion/20" : "hover:border-pumice"}`}
    >
      <button
        onClick={onClick}
        className="w-full text-left"
        aria-expanded={expanded}
      >
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-medium text-sm text-obsidian leading-snug">{exercise.name}</span>
              {exercise.compound && (
                <span className="text-[9px] font-medium tracking-[0.15em] uppercase px-1.5 py-0.5 rounded bg-blush text-centurion border border-terracotta shrink-0">
                  Compound
                </span>
              )}
            </div>
            <div className="flex items-center gap-2 mt-1.5 flex-wrap">
              <span className="text-[11px] tracking-[0.08em] uppercase text-iron">{muscleLabel(exercise.primary_muscle)}</span>
              <span className="w-1 h-1 rounded-full bg-pewter" aria-hidden />
              <span
                className={`text-[10px] tracking-[0.1em] uppercase px-1.5 py-0.5 rounded border ${equipmentBadge(exercise.equipment)}`}
              >
                {EQUIPMENT_LABELS[exercise.equipment] ?? exercise.equipment}
              </span>
              {exercise.movement_type && (
                <span className="text-[10px] tracking-[0.1em] uppercase text-travertine">
                  {exercise.movement_type.replace(/_/g, " ")}
                </span>
              )}
            </div>
          </div>
          <svg
            className={`w-4 h-4 text-travertine shrink-0 mt-0.5 transition-transform ${expanded ? "rotate-180" : ""}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </button>

      {expanded && (
        <div className="mt-3 pt-3 border-t border-ash space-y-3">
          {exercise.secondary_muscles?.length > 0 && (
            <div>
              <p className="h-section text-travertine mb-1">Secondary</p>
              <p className="text-xs text-iron">
                {exercise.secondary_muscles.map((m) => muscleLabel(m)).join(" · ")}
              </p>
            </div>
          )}
          <div className="grid grid-cols-2 gap-2">
            <div className="bg-alabaster rounded-button border border-ash px-3 py-2">
              <p className="h-section text-travertine">Primary</p>
              <p className="text-xs text-obsidian font-medium mt-1">{muscleLabel(exercise.primary_muscle)}</p>
            </div>
            <div className="bg-alabaster rounded-button border border-ash px-3 py-2">
              <p className="h-section text-travertine">Equipment</p>
              <p className="text-xs text-obsidian font-medium mt-1">{EQUIPMENT_LABELS[exercise.equipment] ?? exercise.equipment}</p>
            </div>
          </div>
          <E1RMTrend exerciseName={exercise.name} />
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// V3.P7 — Per-lift e1RM trend sparkline
// Lazy-loaded; fetches only when the exercise card is expanded.
// ---------------------------------------------------------------------------
interface StrengthRow { date: string; estimated_1rm: number; weight_kg: number; reps: number }

function E1RMTrend({ exerciseName }: { exerciseName: string }) {
  const [rows, setRows] = useState<StrengthRow[] | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api.get<StrengthRow[]>(`/engine2/strength-log?exercise_name=${encodeURIComponent(exerciseName)}&limit=30`)
      .then((data) => setRows(Array.isArray(data) ? data : null))
      .catch(() => setRows([]))
      .finally(() => setLoading(false));
  }, [exerciseName]);

  if (loading) {
    return (
      <div className="bg-alabaster rounded-button border border-ash px-3 py-2 animate-pulse">
        <div className="h-2 w-24 bg-ash rounded" />
        <div className="h-8 mt-2 bg-ash rounded" />
      </div>
    );
  }

  if (!rows || rows.length < 2) {
    return (
      <div className="bg-alabaster rounded-button border border-ash px-3 py-2">
        <p className="h-section text-travertine mb-0.5">Strength Trend</p>
        <p className="text-[11px] text-iron body-serif-sm italic">
          Log two sets of this lift to start seeing your estimated-1RM trend.
        </p>
      </div>
    );
  }

  const sorted = [...rows].sort((a, b) => a.date.localeCompare(b.date));
  const values = sorted.map(r => r.estimated_1rm);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = Math.max(0.5, max - min);
  const w = 240;
  const h = 46;
  const path = values.map((v, i) => {
    const x = (i / Math.max(1, values.length - 1)) * w;
    const y = h - ((v - min) / range) * h;
    return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
  const latest = values[values.length - 1];
  const first = values[0];
  const delta = latest - first;
  const deltaPct = first > 0 ? (delta / first) * 100 : 0;
  const up = delta > 0.1;
  const down = delta < -0.1;

  return (
    <div className="bg-alabaster rounded-button border border-ash px-3 py-2.5">
      <div className="flex items-baseline justify-between mb-1.5">
        <p className="h-section text-travertine">Estimated 1RM</p>
        <span className="text-[10px] tracking-[0.1em] uppercase text-iron tabular-nums">
          {sorted.length} entries
        </span>
      </div>
      <div className="flex items-baseline justify-between gap-3">
        <div>
          <div className="text-lg font-semibold tabular-nums text-obsidian">
            {latest.toFixed(1)}<span className="text-[11px] ml-1 text-travertine">kg</span>
          </div>
          <div className={`text-[10px] tracking-wider uppercase tabular-nums ${up ? "text-laurel" : down ? "text-terracotta" : "text-travertine"}`}>
            {up ? "+" : ""}{delta.toFixed(1)}kg · {up ? "+" : ""}{deltaPct.toFixed(1)}%
          </div>
        </div>
        <svg width="60%" viewBox={`0 0 ${w} ${h}`} className={up ? "text-laurel" : down ? "text-terracotta" : "text-adriatic"}>
          <path d={path} fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" />
        </svg>
      </div>
    </div>
  );
}
