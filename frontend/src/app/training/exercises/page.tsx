"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import NavBar from "@/components/NavBar";
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
];

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

function equipmentColor(equipment: string): string {
  switch (equipment) {
    case "barbell": return "text-yellow-400 bg-yellow-500/10 border-yellow-500/30";
    case "dumbbell": return "text-blue-400 bg-blue-500/10 border-blue-500/30";
    case "cable": return "text-purple-400 bg-purple-500/10 border-purple-500/30";
    case "machine": return "text-orange-400 bg-orange-500/10 border-orange-500/30";
    case "bodyweight": return "text-green-400 bg-green-500/10 border-green-500/30";
    default: return "text-jungle-dim bg-jungle-deeper border-jungle-border";
  }
}

export default function ExercisesPage() {
  const router = useRouter();
  const { user, loading, logout } = useAuth();
  const [exercises, setExercises] = useState<Exercise[]>([]);
  const [searchQ, setSearchQ] = useState("");
  const [selectedMuscle, setSelectedMuscle] = useState("all");
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

  const filtered = compoundOnly ? exercises.filter((e) => e.compound) : exercises;

  // Group by muscle for display when no search
  const grouped: Record<string, Exercise[]> = {};
  filtered.forEach((ex) => {
    const key = ex.primary_muscle;
    if (!grouped[key]) grouped[key] = [];
    grouped[key].push(ex);
  });

  return (
    <div className="min-h-screen">
      <NavBar username={user.username} onLogout={() => { logout(); router.push("/"); }} />

      <main className="container-app py-6">
        <div className="max-w-3xl mx-auto">
          {/* Header */}
          <div className="flex items-center justify-between mb-6">
            <div>
              <h1 className="text-2xl font-bold">
                <span className="text-jungle-accent">Exercise</span> Library
              </h1>
              <p className="text-jungle-muted text-sm mt-1">
                {exercises.length} exercises • filtered by muscle group
              </p>
            </div>
            <a href="/training" className="btn-secondary text-sm px-3 py-2">← Training</a>
          </div>

          {/* Search + filters */}
          <div className="card mb-4 space-y-3">
            <input
              type="text"
              placeholder="Search exercises (e.g. bench press, squat...)"
              value={searchQ}
              onChange={(e) => setSearchQ(e.target.value)}
              className="input-field w-full"
            />

            {/* Muscle filter pills */}
            <div className="flex gap-1.5 overflow-x-auto pb-1 scrollbar-hide">
              {MUSCLE_GROUPS.map((m) => (
                <button
                  key={m}
                  onClick={() => setSelectedMuscle(m)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition-colors shrink-0 ${
                    selectedMuscle === m
                      ? "bg-jungle-accent text-jungle-dark"
                      : "bg-jungle-deeper border border-jungle-border text-jungle-muted hover:border-jungle-accent"
                  }`}
                >
                  {m === "all" ? "All" : muscleLabel(m)}
                </button>
              ))}
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={() => setCompoundOnly(!compoundOnly)}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs border transition-colors ${
                  compoundOnly
                    ? "border-jungle-accent bg-jungle-accent/10 text-jungle-accent"
                    : "border-jungle-border text-jungle-muted hover:border-jungle-accent"
                }`}
              >
                <span
                  className={`w-3 h-3 rounded border ${
                    compoundOnly ? "bg-jungle-accent border-jungle-accent" : "border-jungle-muted"
                  }`}
                />
                Compound only
              </button>
              <span className="text-jungle-dim text-xs">{filtered.length} results</span>
            </div>
          </div>

          {/* Exercise list */}
          {fetching ? (
            <div className="flex items-center justify-center py-12 text-jungle-dim">
              <span className="w-2 h-2 rounded-full bg-jungle-accent animate-pulse mr-2" />
              Loading...
            </div>
          ) : searchQ.length >= 2 ? (
            // Flat list for search results
            <div className="space-y-2">
              {filtered.map((ex) => (
                <ExerciseCard
                  key={ex.id}
                  exercise={ex}
                  onClick={() => setSelectedExercise(selectedExercise?.id === ex.id ? null : ex)}
                  expanded={selectedExercise?.id === ex.id}
                />
              ))}
              {filtered.length === 0 && (
                <div className="card text-center py-8 text-jungle-dim">
                  No exercises found for &quot;{searchQ}&quot;
                </div>
              )}
            </div>
          ) : (
            // Grouped by muscle
            <div className="space-y-4">
              {Object.entries(grouped)
                .sort(([a], [b]) => a.localeCompare(b))
                .map(([muscle, exs]) => (
                  <div key={muscle}>
                    <h3 className="text-xs font-semibold text-jungle-muted uppercase tracking-wider mb-2 px-1">
                      {muscleLabel(muscle)} <span className="text-jungle-dim font-normal">({exs.length})</span>
                    </h3>
                    <div className="space-y-1.5">
                      {exs.slice(0, 8).map((ex) => (
                        <ExerciseCard
                          key={ex.id}
                          exercise={ex}
                          onClick={() => setSelectedExercise(selectedExercise?.id === ex.id ? null : ex)}
                          expanded={selectedExercise?.id === ex.id}
                        />
                      ))}
                      {exs.length > 8 && (
                        <button
                          onClick={() => setSelectedMuscle(muscle)}
                          className="text-xs text-jungle-accent hover:underline px-2"
                        >
                          +{exs.length - 8} more — filter by {muscleLabel(muscle)}
                        </button>
                      )}
                    </div>
                  </div>
                ))}
            </div>
          )}
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
    <button
      onClick={onClick}
      className={`w-full text-left card py-3 px-4 transition-all ${
        expanded ? "border-jungle-accent" : "hover:border-jungle-border-hover"
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-medium text-sm leading-tight">{exercise.name}</span>
            {exercise.compound && (
              <span className="text-[9px] font-bold uppercase px-1.5 py-0.5 rounded bg-jungle-accent/15 text-jungle-accent border border-jungle-accent/30 shrink-0">
                Compound
              </span>
            )}
          </div>
          <div className="flex items-center gap-2 mt-1 flex-wrap">
            <span className="text-xs text-jungle-muted capitalize">{muscleLabel(exercise.primary_muscle)}</span>
            <span
              className={`text-[10px] px-1.5 py-0.5 rounded border ${equipmentColor(exercise.equipment)}`}
            >
              {EQUIPMENT_LABELS[exercise.equipment] ?? exercise.equipment}
            </span>
            {exercise.movement_type && (
              <span className="text-[10px] text-jungle-dim capitalize">
                {exercise.movement_type.replace(/_/g, " ")}
              </span>
            )}
          </div>
        </div>
        <svg
          className={`w-4 h-4 text-jungle-dim shrink-0 mt-0.5 transition-transform ${expanded ? "rotate-180" : ""}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </div>

      {expanded && (
        <div className="mt-3 pt-3 border-t border-jungle-border space-y-2">
          {exercise.secondary_muscles?.length > 0 && (
            <div>
              <span className="text-[10px] text-jungle-dim uppercase tracking-wide">Secondary: </span>
              <span className="text-xs text-jungle-muted">
                {exercise.secondary_muscles.map((m) => muscleLabel(m)).join(", ")}
              </span>
            </div>
          )}
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="bg-jungle-deeper rounded p-2">
              <span className="text-jungle-dim">Primary</span>
              <p className="text-jungle-muted font-medium mt-0.5 capitalize">{muscleLabel(exercise.primary_muscle)}</p>
            </div>
            <div className="bg-jungle-deeper rounded p-2">
              <span className="text-jungle-dim">Equipment</span>
              <p className="text-jungle-muted font-medium mt-0.5">{EQUIPMENT_LABELS[exercise.equipment] ?? exercise.equipment}</p>
            </div>
          </div>
        </div>
      )}
    </button>
  );
}
