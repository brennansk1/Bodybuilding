"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import NavBar from "@/components/NavBar";
import { api } from "@/lib/api";

// ─── Interfaces ──────────────────────────────────────────────────────────────

interface TrainingSet {
  id: string;
  exercise_name: string;
  muscle_group: string;
  set_number: number;
  prescribed_reps: number;
  prescribed_weight_kg: number | null;
  actual_reps: number | null;
  actual_weight_kg: number | null;
  rpe: number | null;
  is_warmup?: boolean;
  last_actual_reps?: number;
  last_actual_weight_kg?: number;
}

interface TrainingSession {
  id: string;
  session_type: string;
  session_date: string;
  week_number: number;
  day_number: number;
  completed: boolean;
  sets: TrainingSet[];
  stale_baselines?: boolean;
}

interface Program {
  id: string;
  name: string;
  split_type: string;
  days_per_week: number;
  current_week: number;
  mesocycle_weeks: number;
}

interface Progression {
  exercise: string;
  action: string;
  next_weight_kg: number;
  next_reps: number;
  estimated_1rm: number;
}

interface StrengthEntry {
  date: string;
  exercise: string;
  weight_kg: number;
  reps: number;
  rpe: number | null;
  estimated_1rm: number;
}

// ─── Helper: RPE colour class ─────────────────────────────────────────────────

function rpeClass(rpe: string): string {
  const val = parseFloat(rpe);
  if (!rpe || isNaN(val) || val <= 6) return "input-field text-sm py-1.5";
  if (val <= 8) return "input-field text-sm py-1.5 border-yellow-500/50 bg-yellow-500/5";
  if (val < 9.5) return "input-field text-sm py-1.5 border-orange-500/50 bg-orange-500/5";
  return "input-field text-sm py-1.5 border-red-500/50 bg-red-500/5";
}

// ─── Plate Calculator sub-component ──────────────────────────────────────────

const PLATE_SIZES = [25, 20, 15, 10, 5, 2.5, 1.25];

const PLATE_COLOURS: Record<number, string> = {
  25: "bg-red-600 text-white",
  20: "bg-blue-600 text-white",
  15: "bg-yellow-500 text-black",
  10: "bg-green-600 text-white",
  5: "bg-white text-black",
  2.5: "bg-red-400 text-white",
  1.25: "bg-gray-400 text-black",
};

const PLATE_WIDTHS: Record<number, string> = {
  25: "w-10",
  20: "w-9",
  15: "w-8",
  10: "w-7",
  5: "w-6",
  2.5: "w-5",
  1.25: "w-4",
};

function PlateCalculator({
  targetWeight,
  onClose,
}: {
  targetWeight: number;
  onClose: () => void;
}) {
  const [barWeight, setBarWeight] = useState(20);

  const plates: number[] = [];
  let remaining = Math.max(0, (targetWeight - barWeight) / 2);
  for (const plate of PLATE_SIZES) {
    while (remaining >= plate - 0.001) {
      plates.push(plate);
      remaining -= plate;
      remaining = Math.round(remaining * 1000) / 1000;
    }
  }

  const totalLoaded = barWeight + plates.reduce((s, p) => s + p, 0) * 2;

  return (
    <div className="fixed inset-0 z-50 flex items-end" onClick={onClose}>
      <div
        className="w-full max-w-lg mx-auto bg-jungle-card border border-jungle-border rounded-t-2xl p-5 space-y-4 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
        style={{ animation: "slideUp 0.2s ease-out" }}
      >
        <div className="flex items-center justify-between">
          <h3 className="font-semibold text-jungle-accent">Plate Calculator</h3>
          <button onClick={onClose} className="text-jungle-dim hover:text-jungle-muted text-xl leading-none">×</button>
        </div>

        {/* Bar toggle */}
        <div className="flex gap-2">
          <button
            onClick={() => setBarWeight(20)}
            className={`flex-1 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              barWeight === 20
                ? "bg-jungle-accent text-jungle-dark"
                : "bg-jungle-deeper border border-jungle-border text-jungle-muted"
            }`}
          >
            Men's bar (20 kg)
          </button>
          <button
            onClick={() => setBarWeight(15)}
            className={`flex-1 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              barWeight === 15
                ? "bg-jungle-accent text-jungle-dark"
                : "bg-jungle-deeper border border-jungle-border text-jungle-muted"
            }`}
          >
            Women's bar (15 kg)
          </button>
        </div>

        {/* Target display */}
        <div className="text-center">
          <p className="text-jungle-dim text-xs uppercase tracking-wider">Target</p>
          <p className="text-2xl font-bold text-jungle-text">{targetWeight} kg</p>
          {Math.abs(totalLoaded - targetWeight) > 0.01 && (
            <p className="text-jungle-warning text-xs mt-0.5">
              Closest loadable: {totalLoaded} kg
            </p>
          )}
        </div>

        {/* Plates per side */}
        <div>
          <p className="text-jungle-dim text-xs mb-2">Per side:</p>
          {plates.length === 0 ? (
            <p className="text-jungle-muted text-sm">Bar only</p>
          ) : (
            <div className="flex flex-wrap gap-1.5 items-center">
              {plates.map((plate, i) => (
                <div
                  key={i}
                  className={`${PLATE_COLOURS[plate]} ${PLATE_WIDTHS[plate]} h-12 flex items-center justify-center rounded text-xs font-bold shadow`}
                >
                  {plate}
                </div>
              ))}
            </div>
          )}
        </div>

        <p className="text-jungle-dim text-xs text-center">
          Bar {barWeight} kg + {plates.reduce((s, p) => s + p, 0) * 2} kg plates = {totalLoaded} kg total
        </p>
      </div>

      <style>{`
        @keyframes slideUp {
          from { transform: translateY(100%); opacity: 0; }
          to   { transform: translateY(0);    opacity: 1; }
        }
      `}</style>
    </div>
  );
}

// ─── Rest Timer sub-component ─────────────────────────────────────────────────

function RestTimer({
  seconds,
  isCompound,
  onSkip,
}: {
  seconds: number;
  isCompound: boolean;
  onSkip: () => void;
}) {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  const display = `${mins}:${secs.toString().padStart(2, "0")}`;
  const isDone = seconds <= 0;

  return (
    <div className="fixed bottom-0 left-0 right-0 z-40 flex justify-center pb-safe">
      <div className="w-full max-w-lg mx-auto bg-jungle-card border-t border-jungle-border px-5 py-3 flex items-center justify-between shadow-2xl">
        <div>
          <p className="text-[10px] text-jungle-dim uppercase tracking-wider">
            {isCompound ? "Compound rest" : "Isolation rest"}
          </p>
          {isDone ? (
            <p className="text-green-400 font-semibold text-sm">Rest complete — begin next set</p>
          ) : (
            <p className="text-2xl font-bold font-mono text-jungle-accent">{display}</p>
          )}
        </div>
        <button
          onClick={onSkip}
          className="btn-secondary text-sm px-4 py-1.5"
        >
          Skip
        </button>
      </div>
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function TrainingPage() {
  const router = useRouter();
  const { user, loading, logout } = useAuth();

  // ── Core state ──
  const [program, setProgram] = useState<Program | null>(null);
  const [session, setSession] = useState<TrainingSession | null>(null);
  const [sets, setSets] = useState<Record<string, { reps: string; weight: string; rpe: string }>>({});
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [progressions, setProgressions] = useState<Progression[]>([]);

  // ── Strength log state ──
  const [strengthLog, setStrengthLog] = useState<StrengthEntry[]>([]);
  const [showStrengthForm, setShowStrengthForm] = useState(false);
  const [sExercise, setSExercise] = useState("");
  const [sWeight, setSWeight] = useState("");
  const [sReps, setSReps] = useState("");
  const [sRpe, setSRpe] = useState("");
  const [sLogging, setSLogging] = useState(false);
  const [sLogged, setSLogged] = useState(false);

  // ── Set-by-set logging ──
  const [activeSetIndex, setActiveSetIndex] = useState(0);
  const [completedSets, setCompletedSets] = useState<Record<string, { reps: string; weight: string; rpe: string }>>({});

  // ── Previous session ghosts ──
  const [previousSets, setPreviousSets] = useState<Record<string, { reps: number; weight: number }>>({});

  // ── Rest timer ──
  const [restTimer, setRestTimer] = useState<{ active: boolean; seconds: number; isCompound: boolean }>({
    active: false,
    seconds: 0,
    isCompound: true,
  });

  // ── Plate calculator ──
  const [plateCalc, setPlateCalc] = useState<{ open: boolean; weight: number }>({ open: false, weight: 0 });

  // ── Session notes ──
  const [sessionNotes, setSessionNotes] = useState("");
  const [showNotes, setShowNotes] = useState(false);

  // ── Machine taken / alternative exercise ──
  const [machineTaken, setMachineTaken] = useState<Set<string>>(new Set());
  const [altLog, setAltLog] = useState<Record<string, { name: string; weight: string; reps: string; rpe: string; logged: boolean }>>({});

  // ── Gym mode ──
  const [gymMode, setGymMode] = useState(false);

  const today = new Date().toISOString().split("T")[0];

  // Initialise gym mode from localStorage
  useEffect(() => {
    const stored = localStorage.getItem("gymMode");
    if (stored === "true") setGymMode(true);
  }, []);

  const toggleGymMode = () => {
    const next = !gymMode;
    setGymMode(next);
    localStorage.setItem("gymMode", String(next));
  };

  // ── Auth + data fetch ──
  useEffect(() => {
    if (!loading && !user) { router.push("/auth/login"); return; }
    if (user) {
      api.get<Program>("/engine2/program/current").then(setProgram).catch(() => {});
      api.get<StrengthEntry[]>("/engine2/strength-log?limit=10").then(setStrengthLog).catch(() => {});
      api.get<TrainingSession>(`/engine2/session/${today}`)
        .then((s) => {
          setSession(s);
          const initial: Record<string, { reps: string; weight: string; rpe: string }> = {};
          const prevData: Record<string, { reps: number; weight: number }> = {};
          s.sets.forEach((set) => {
            initial[set.id] = {
              reps: set.actual_reps?.toString() || set.prescribed_reps.toString(),
              weight: set.actual_weight_kg?.toString() || set.prescribed_weight_kg?.toString() || "",
              rpe: set.rpe?.toString() || "",
            };
            // Populate previous session ghost values if backend returns them
            if (set.last_actual_reps != null && set.last_actual_weight_kg != null) {
              prevData[set.id] = { reps: set.last_actual_reps, weight: set.last_actual_weight_kg };
            }
          });
          setSets(initial);
          setPreviousSets(prevData);
        })
        .catch(() => {});
    }
  }, [user, loading, router, today]);

  // ── Rest timer countdown ──
  useEffect(() => {
    if (!restTimer.active || restTimer.seconds <= 0) return;
    const interval = setInterval(() => {
      setRestTimer((prev) => {
        if (prev.seconds <= 1) {
          clearInterval(interval);
          // Auto-dismiss after 3 s when timer hits 0
          setTimeout(() => setRestTimer({ active: false, seconds: 0, isCompound: true }), 3000);
          return { ...prev, seconds: 0 };
        }
        return { ...prev, seconds: prev.seconds - 1 };
      });
    }, 1000);
    return () => clearInterval(interval);
  }, [restTimer.active, restTimer.seconds]);

  if (loading || !user) return null;

  // ── Group sets by exercise (preserving order), separating warmup vs working ──
  const exerciseGroups: {
    name: string;
    muscle: string;
    warmupSets: TrainingSet[];
    workingSets: TrainingSet[];
  }[] = [];
  const seenExercises: Record<string, number> = {};

  session?.sets.forEach((set) => {
    if (!(set.exercise_name in seenExercises)) {
      seenExercises[set.exercise_name] = exerciseGroups.length;
      exerciseGroups.push({ name: set.exercise_name, muscle: set.muscle_group, warmupSets: [], workingSets: [] });
    }
    const idx = seenExercises[set.exercise_name];
    if (set.is_warmup) {
      exerciseGroups[idx].warmupSets.push(set);
    } else {
      exerciseGroups[idx].workingSets.push(set);
    }
  });

  // Ordered list of working sets only (for active set index tracking)
  const allWorkingSets: TrainingSet[] = exerciseGroups.flatMap((g) => g.workingSets);
  const allWorkingSetsComplete = allWorkingSets.length > 0 && allWorkingSets.every((s) => completedSets[s.id]);

  // Determine if an exercise is "compound" (first in its group = position 0 in exerciseGroups)
  const isCompoundExercise = (exerciseName: string): boolean => {
    return exerciseGroups.length > 0 && exerciseGroups[0].name === exerciseName;
  };

  // ── Handlers ──

  const logSet = (setId: string, field: string, value: string) => {
    setSets((prev) => ({ ...prev, [setId]: { ...prev[setId], [field]: value } }));
  };

  const markSetDone = (set: TrainingSet) => {
    const data = sets[set.id] || { reps: "", weight: "", rpe: "" };
    setCompletedSets((prev) => ({ ...prev, [set.id]: data }));
    setActiveSetIndex((prev) => prev + 1);

    // Start rest timer
    const compound = isCompoundExercise(set.exercise_name);
    setRestTimer({ active: true, seconds: compound ? 180 : 90, isCompound: compound });
  };

  const dismissTimer = () => {
    setRestTimer({ active: false, seconds: 0, isCompound: true });
  };

  const toggleMachineTaken = (exerciseName: string) => {
    setMachineTaken((prev) => {
      const next = new Set(prev);
      if (next.has(exerciseName)) { next.delete(exerciseName); } else { next.add(exerciseName); }
      return next;
    });
    setAltLog((prev) => ({
      ...prev,
      [exerciseName]: prev[exerciseName] ?? { name: "", weight: "", reps: "", rpe: "", logged: false },
    }));
  };

  const logAlternative = async (exerciseName: string) => {
    const alt = altLog[exerciseName];
    if (!alt || !alt.name || !alt.weight || !alt.reps) return;
    try {
      await api.post("/engine2/strength-log", {
        exercise_name: alt.name,
        weight_kg: parseFloat(alt.weight),
        reps: parseInt(alt.reps),
        rpe: alt.rpe ? parseFloat(alt.rpe) : null,
      });
      setAltLog((prev) => ({ ...prev, [exerciseName]: { ...prev[exerciseName], logged: true } }));
    } catch { /* silent */ }
  };

  const logStrengthTest = async () => {
    if (!sExercise || !sWeight || !sReps) return;
    setSLogging(true);
    try {
      const res = await api.post<{ message: string; exercise: string; estimated_1rm: number; weight_kg: number; reps: number }>(
        "/engine2/strength-log",
        { exercise_name: sExercise, weight_kg: parseFloat(sWeight), reps: parseInt(sReps), rpe: sRpe ? parseFloat(sRpe) : null }
      );
      setSLogged(true);
      setSExercise(""); setSWeight(""); setSReps(""); setSRpe("");
      setStrengthLog((prev) => [{
        date: new Date().toISOString().split("T")[0],
        exercise: res.exercise,
        weight_kg: res.weight_kg,
        reps: res.reps,
        rpe: sRpe ? parseFloat(sRpe) : null,
        estimated_1rm: res.estimated_1rm,
      }, ...prev.slice(0, 9)]);
      setTimeout(() => setSLogged(false), 2500);
    } catch { /* silent */ } finally { setSLogging(false); }
  };

  const generateProgram = async () => {
    setGenerating(true);
    try {
      const p = await api.post<Program & { sessions_created: number; message: string }>(
        "/engine2/program/generate"
      );
      setProgram(p);
    } catch {
      //
    } finally {
      setGenerating(false);
    }
  };

  const saveSession = async () => {
    if (!session) return;
    setSaving(true);
    try {
      const loggedSets = Object.entries(sets).map(([id, data]) => ({
        set_id: id,
        actual_reps: data.reps ? parseInt(data.reps) : null,
        actual_weight_kg: data.weight ? parseFloat(data.weight) : null,
        rpe: data.rpe ? parseFloat(data.rpe) : null,
      }));
      const result = await api.post<{ message: string; progressions: Progression[] }>(
        `/engine2/session/${session.id}/log`,
        { sets: loggedSets, notes: sessionNotes || undefined }
      );
      setProgressions(result.progressions || []);
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch {
      //
    } finally {
      setSaving(false);
    }
  };

  // ── Render ──
  return (
    <div className="min-h-screen bg-jungle-dark">
      <NavBar username={user.username} onLogout={() => { logout(); router.push("/"); }} />

      <main className="container-app py-6">
        <div className="max-w-3xl mx-auto space-y-6">

          {/* Header */}
          <div className="flex flex-col sm:flex-row justify-between gap-4">
            <div>
              <h1 className="text-2xl font-bold">
                <span className="text-jungle-accent">Training</span>
              </h1>
              {program ? (
                <p className="text-jungle-muted text-sm mt-1">
                  {program.name} — Week {program.current_week}/{program.mesocycle_weeks} —{" "}
                  {program.split_type.replace("_", "/")} · {program.days_per_week} days/week
                </p>
              ) : (
                <p className="text-jungle-muted text-sm mt-1">No active program</p>
              )}
            </div>
            {!program && (
              <button
                onClick={generateProgram}
                disabled={generating}
                className="btn-primary disabled:opacity-50"
              >
                {generating ? "Generating..." : "Generate Program"}
              </button>
            )}
          </div>

          {/* No session today */}
          {!session ? (
            <div className="card text-center py-12">
              <p className="text-jungle-muted text-lg">Rest day</p>
              <p className="text-jungle-dim text-sm mt-2">
                {program
                  ? "No session scheduled for today — enjoy your recovery"
                  : "Generate a program to get started"}
              </p>
              {!program && (
                <button
                  onClick={generateProgram}
                  disabled={generating}
                  className="btn-primary mt-4 disabled:opacity-50"
                >
                  {generating ? "Generating..." : "Generate Program"}
                </button>
              )}
            </div>
          ) : (
            <>
              {/* Stale baseline warning */}
              {session.stale_baselines && (
                <div className="rounded-xl border border-yellow-500/40 bg-yellow-500/10 px-4 py-3 text-sm text-yellow-300">
                  ⚠️ Strength baselines are 90+ days old. Prescribed weights may be inaccurate — consider re-testing.
                </div>
              )}

              {/* Session header */}
              <div className={`card ${gymMode ? "gym-mode" : ""}`}>
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="font-semibold capitalize text-lg">
                      {session.session_type.replace(/_/g, " ")} Day
                    </h2>
                    <p className="text-jungle-muted text-xs">
                      Week {session.week_number} • Day {session.day_number} • {allWorkingSets.length} working sets
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    {/* Gym mode toggle */}
                    <button
                      onClick={toggleGymMode}
                      title={gymMode ? "Gym Mode ON" : "Gym Mode OFF"}
                      className={`w-9 h-9 rounded-lg flex items-center justify-center text-lg transition-colors ${
                        gymMode
                          ? "bg-jungle-accent text-jungle-dark"
                          : "bg-jungle-deeper border border-jungle-border text-jungle-dim hover:border-jungle-accent"
                      }`}
                    >
                      {gymMode ? "✓" : "💪"}
                    </button>
                    <span
                      className={`px-2 py-1 rounded text-xs font-medium ${
                        session.completed
                          ? "bg-green-500/20 text-green-400"
                          : "bg-jungle-accent/20 text-jungle-accent"
                      }`}
                    >
                      {session.completed ? "Completed" : "In Progress"}
                    </span>
                  </div>
                </div>
              </div>

              {/* Exercise blocks */}
              <div className={gymMode ? "gym-mode" : ""}>
                {exerciseGroups.map(({ name, muscle, warmupSets, workingSets }) => {
                  const isMachineTaken = machineTaken.has(name);
                  const alt = altLog[name] ?? { name: "", weight: "", reps: "", rpe: "", logged: false };
                  return (
                  <div key={name} className={`card mb-4 ${isMachineTaken ? "opacity-60 border-yellow-500/30" : ""}`}>
                    <div className="flex items-center justify-between mb-3">
                      <div>
                        <h3 className={`font-semibold ${isMachineTaken ? "line-through text-jungle-dim" : "text-jungle-accent"}`}>{name}</h3>
                        <span className="text-[10px] text-jungle-dim uppercase tracking-wide capitalize">
                          {muscle.replace(/_/g, " ")}
                        </span>
                      </div>
                      <button
                        onClick={() => toggleMachineTaken(name)}
                        className={`text-[10px] px-2 py-1 rounded-lg border transition-colors ${
                          isMachineTaken
                            ? "border-yellow-500/50 bg-yellow-500/10 text-yellow-400"
                            : "border-jungle-border text-jungle-dim hover:border-yellow-500/40 hover:text-yellow-400"
                        }`}
                      >
                        {isMachineTaken ? "Machine Taken" : "Machine Taken?"}
                      </button>
                    </div>

                    {/* Alternative exercise form when machine is taken */}
                    {isMachineTaken && (
                      <div className="mb-3 p-3 bg-yellow-500/5 border border-yellow-500/20 rounded-lg">
                        <p className="text-[10px] text-yellow-400 uppercase tracking-wide mb-2">Log Alternative Exercise</p>
                        <div className="grid grid-cols-2 gap-2 mb-2">
                          <div className="col-span-2">
                            <input
                              type="text"
                              value={alt.name}
                              onChange={(e) => setAltLog((prev) => ({ ...prev, [name]: { ...prev[name], name: e.target.value } }))}
                              placeholder="Alternative exercise name"
                              className="input-field text-sm py-1.5 w-full"
                            />
                          </div>
                          <input
                            type="number" step="0.5" value={alt.weight}
                            onChange={(e) => setAltLog((prev) => ({ ...prev, [name]: { ...prev[name], weight: e.target.value } }))}
                            placeholder="Weight (kg)" className="input-field text-sm py-1.5"
                          />
                          <input
                            type="number" value={alt.reps}
                            onChange={(e) => setAltLog((prev) => ({ ...prev, [name]: { ...prev[name], reps: e.target.value } }))}
                            placeholder="Reps" className="input-field text-sm py-1.5"
                          />
                        </div>
                        <button
                          onClick={() => logAlternative(name)}
                          disabled={!alt.name || !alt.weight || !alt.reps || alt.logged}
                          className="btn-secondary text-xs py-1 px-3 disabled:opacity-40"
                        >
                          {alt.logged ? "Logged!" : "Log Alternative"}
                        </button>
                      </div>
                    )}

                    {/* Column headers */}
                    <div className="grid grid-cols-[auto_1fr_1fr_1fr_auto] gap-2 text-xs text-jungle-muted px-1 mb-2">
                      <span className="w-16">Set</span>
                      <span>Weight (kg)</span>
                      <span>Reps</span>
                      <span>RPE</span>
                      <span />
                    </div>

                    <div className="space-y-2">
                      {/* Warm-up sets (display only) */}
                      {warmupSets.map((set) => (
                        <div
                          key={set.id}
                          className="grid grid-cols-[auto_1fr_1fr_1fr_auto] gap-2 items-center opacity-50 bg-jungle-deeper/50 rounded-lg px-2 py-1.5"
                        >
                          <span className="w-16 text-xs text-jungle-dim font-medium uppercase tracking-wide">
                            Warm-up
                          </span>
                          <span className="text-xs text-jungle-dim">{set.prescribed_weight_kg ?? "—"} kg</span>
                          <span className="text-xs text-jungle-dim">{set.prescribed_reps} reps</span>
                          <span className="text-xs text-jungle-dim">—</span>
                          <span />
                        </div>
                      ))}

                      {/* Working sets */}
                      {workingSets.map((set) => {
                        const globalIdx = allWorkingSets.findIndex((s) => s.id === set.id);
                        const isCompleted = !!completedSets[set.id];
                        const isActive = globalIdx === activeSetIndex;
                        const isPending = globalIdx > activeSetIndex;
                        const prev = previousSets[set.id];
                        const currentWeight = sets[set.id]?.weight || "";

                        return (
                          <div
                            key={set.id}
                            className={`grid grid-cols-[auto_1fr_1fr_1fr_auto] gap-2 items-start rounded-lg transition-all ${
                              isCompleted
                                ? "opacity-50"
                                : isPending
                                ? "opacity-60"
                                : ""
                            }`}
                          >
                            {/* Set label */}
                            <div className="w-16 pt-1.5">
                              <span className="text-sm text-jungle-muted pl-1 block">
                                {set.set_number}
                              </span>
                              <span className="text-jungle-dim text-xs ml-1 block">
                                ({set.prescribed_weight_kg ?? "—"}×{set.prescribed_reps})
                              </span>
                            </div>

                            {isCompleted ? (
                              /* Completed row — show greyed values */
                              <>
                                <span className="text-jungle-dim text-sm pt-1.5">{completedSets[set.id].weight || "—"} kg</span>
                                <span className="text-jungle-dim text-sm pt-1.5">{completedSets[set.id].reps || "—"}</span>
                                <span className="text-jungle-dim text-sm pt-1.5">RPE {completedSets[set.id].rpe || "—"}</span>
                                {/* Green checkmark */}
                                <div className="flex items-center justify-center pt-1.5">
                                  <span className="w-7 h-7 rounded-full bg-green-500/20 text-green-400 flex items-center justify-center text-sm">✓</span>
                                </div>
                              </>
                            ) : (
                              /* Active / pending row — show inputs */
                              <>
                                {/* Weight input + plate calc button */}
                                <div>
                                  <div className="flex gap-1">
                                    <input
                                      type="number"
                                      step="0.5"
                                      value={sets[set.id]?.weight || ""}
                                      onChange={(e) => logSet(set.id, "weight", e.target.value)}
                                      className="input-field text-sm py-1.5 flex-1 min-w-0"
                                      placeholder="kg"
                                      disabled={isPending}
                                    />
                                    <button
                                      onClick={() =>
                                        setPlateCalc({
                                          open: true,
                                          weight: parseFloat(currentWeight) || 0,
                                        })
                                      }
                                      className="flex-shrink-0 w-8 h-8 flex items-center justify-center rounded-lg bg-jungle-deeper border border-jungle-border text-jungle-dim hover:border-jungle-accent hover:text-jungle-accent transition-colors text-sm"
                                      title="Plate calculator"
                                      disabled={isPending}
                                    >
                                      🏋️
                                    </button>
                                  </div>
                                  {prev && (
                                    <p className="text-jungle-dim text-xs mt-0.5 pl-0.5">
                                      Last: {prev.weight}kg × {prev.reps}
                                    </p>
                                  )}
                                </div>

                                {/* Reps input */}
                                <div>
                                  <input
                                    type="number"
                                    value={sets[set.id]?.reps || ""}
                                    onChange={(e) => logSet(set.id, "reps", e.target.value)}
                                    className="input-field text-sm py-1.5"
                                    placeholder="reps"
                                    disabled={isPending}
                                  />
                                  {prev && (
                                    <p className="text-jungle-dim text-xs mt-0.5 pl-0.5 invisible">
                                      &nbsp;
                                    </p>
                                  )}
                                </div>

                                {/* RPE input with live colour */}
                                <div>
                                  <input
                                    type="number"
                                    step="0.5"
                                    min="1"
                                    max="10"
                                    value={sets[set.id]?.rpe || ""}
                                    onChange={(e) => logSet(set.id, "rpe", e.target.value)}
                                    className={rpeClass(sets[set.id]?.rpe || "")}
                                    placeholder="RPE"
                                    disabled={isPending}
                                  />
                                  {prev && (
                                    <p className="text-jungle-dim text-xs mt-0.5 pl-0.5 invisible">
                                      &nbsp;
                                    </p>
                                  )}
                                </div>

                                {/* Done button */}
                                <div className="flex items-start pt-0.5">
                                  {isActive ? (
                                    <button
                                      onClick={() => markSetDone(set)}
                                      className="btn-primary text-xs px-3 py-1.5 whitespace-nowrap"
                                    >
                                      Done
                                    </button>
                                  ) : (
                                    <div className="w-14" />
                                  )}
                                </div>
                              </>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                  );
                })}
              </div>

              {/* Session Notes (collapsible) */}
              <div className="card">
                <button
                  onClick={() => setShowNotes(!showNotes)}
                  className="w-full flex items-center justify-between text-left"
                >
                  <div>
                    <h3 className="text-xs font-semibold text-jungle-muted uppercase tracking-wider">
                      Session Notes
                    </h3>
                    <p className="text-[10px] text-jungle-dim mt-0.5">Add free-form notes for this session</p>
                  </div>
                  <svg
                    className={`w-4 h-4 text-jungle-dim transition-transform ${showNotes ? "rotate-180" : ""}`}
                    fill="none" viewBox="0 0 24 24" stroke="currentColor"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </button>
                {showNotes && (
                  <div className="mt-4 pt-4 border-t border-jungle-border">
                    <textarea
                      value={sessionNotes}
                      onChange={(e) => setSessionNotes(e.target.value)}
                      rows={4}
                      placeholder="How did the session feel? Any observations…"
                      className="input-field text-sm resize-none"
                    />
                  </div>
                )}
              </div>

              {/* Progression readouts */}
              {progressions.length > 0 && (
                <div className="card border-jungle-accent/40">
                  <h3 className="text-xs font-semibold text-jungle-accent uppercase tracking-wider mb-3">
                    Progression Unlocked
                  </h3>
                  {progressions.map((p) => (
                    <div key={p.exercise} className="flex justify-between items-center py-1.5 text-sm border-b border-jungle-border last:border-0">
                      <span className="text-jungle-muted">{p.exercise}</span>
                      <span className="text-green-400 font-semibold">
                        → {p.next_weight_kg}kg × {p.next_reps} reps
                      </span>
                    </div>
                  ))}
                </div>
              )}

              {/* Progress indicator + Log Session (always visible) */}
              {allWorkingSets.length > 0 && (
                <div className="space-y-3">
                  <div className="flex items-center gap-3">
                    <div className="flex-1 h-1.5 bg-jungle-deeper rounded-full overflow-hidden">
                      <div
                        className="h-full bg-jungle-accent rounded-full transition-all"
                        style={{
                          width: `${(Object.keys(completedSets).length / allWorkingSets.length) * 100}%`,
                        }}
                      />
                    </div>
                    <span className="text-jungle-dim text-xs shrink-0">
                      {Object.keys(completedSets).length}/{allWorkingSets.length} sets
                    </span>
                  </div>
                  {!allWorkingSetsComplete && (
                    <p className="text-jungle-dim text-[10px]">
                      Missing sets will use prescribed values — machine-taken exercises are excluded.
                    </p>
                  )}
                  <button
                    onClick={saveSession}
                    disabled={saving}
                    className={`w-full disabled:opacity-50 ${allWorkingSetsComplete ? "btn-primary" : "btn-secondary"}`}
                  >
                    {saved ? "Session Saved!" : saving ? "Saving..." : allWorkingSetsComplete ? "Log Session" : "Log Session (Partial)"}
                  </button>
                </div>
              )}
            </>
          )}

          {/* Strength Test Logger */}
          <div className="card">
            <button
              onClick={() => setShowStrengthForm(!showStrengthForm)}
              className="w-full flex items-center justify-between text-left"
            >
              <div>
                <h3 className="text-xs font-semibold text-jungle-muted uppercase tracking-wider">
                  Strength Tests / 1RM Log
                </h3>
                <p className="text-[10px] text-jungle-dim mt-0.5">Log max-effort sets outside your program</p>
              </div>
              <svg className={`w-4 h-4 text-jungle-dim transition-transform ${showStrengthForm ? "rotate-180" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>

            {showStrengthForm && (
              <div className="mt-4 space-y-4 pt-4 border-t border-jungle-border">
                <div className="grid grid-cols-2 gap-3">
                  <div className="col-span-2">
                    <label className="label-field">Exercise Name</label>
                    <input
                      type="text"
                      value={sExercise}
                      onChange={(e) => setSExercise(e.target.value)}
                      placeholder="e.g. Barbell Back Squat"
                      className="input-field mt-1 text-sm"
                    />
                  </div>
                  <div>
                    <label className="label-field">Weight (kg)</label>
                    <input type="number" step="0.5" value={sWeight} onChange={(e) => setSWeight(e.target.value)} className="input-field mt-1 text-sm" placeholder="e.g. 120" />
                  </div>
                  <div>
                    <label className="label-field">Reps</label>
                    <input type="number" value={sReps} onChange={(e) => setSReps(e.target.value)} className="input-field mt-1 text-sm" placeholder="e.g. 3" />
                  </div>
                  <div>
                    <label className="label-field">RPE (optional)</label>
                    <input type="number" step="0.5" min="1" max="10" value={sRpe} onChange={(e) => setSRpe(e.target.value)} className="input-field mt-1 text-sm" placeholder="e.g. 9" />
                  </div>
                  <div className="flex items-end">
                    <button onClick={logStrengthTest} disabled={sLogging || !sExercise || !sWeight || !sReps} className="btn-primary w-full text-sm disabled:opacity-50">
                      {sLogged ? "Logged!" : sLogging ? "Saving..." : "Log Test"}
                    </button>
                  </div>
                </div>

                {strengthLog.length > 0 && (
                  <div className="space-y-1">
                    <p className="text-[10px] text-jungle-dim uppercase tracking-wider">Recent Tests</p>
                    {strengthLog.map((entry, i) => (
                      <div key={i} className="flex items-center justify-between py-1.5 px-2 bg-jungle-deeper rounded text-xs">
                        <div>
                          <span className="font-medium">{entry.exercise}</span>
                          <span className="text-jungle-dim ml-2">{entry.date}</span>
                        </div>
                        <div className="text-right">
                          <span className="text-jungle-muted">{entry.weight_kg}kg × {entry.reps}</span>
                          <span className="text-jungle-accent font-bold ml-2">e1RM: {entry.estimated_1rm}kg</span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Quick links */}
          <div className="flex gap-3">
            <a href="/training/exercises" className="flex-1 btn-secondary text-center text-sm py-2.5">
              Exercise Library
            </a>
            <a href="/progress" className="flex-1 btn-secondary text-center text-sm py-2.5">
              Progress History
            </a>
          </div>

        </div>
      </main>

      {/* Rest Timer (fixed bottom) */}
      {restTimer.active && (
        <RestTimer
          seconds={restTimer.seconds}
          isCompound={restTimer.isCompound}
          onSkip={dismissTimer}
        />
      )}

      {/* Plate Calculator modal */}
      {plateCalc.open && (
        <PlateCalculator
          targetWeight={plateCalc.weight}
          onClose={() => setPlateCalc({ open: false, weight: 0 })}
        />
      )}

      <div className="md:hidden h-16" />
    </div>
  );
}
