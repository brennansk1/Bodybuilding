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
  equipment?: string;
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
  if (!rpe || isNaN(val) || val <= 6) return "input-field text-sm py-2.5";
  if (val <= 8) return "input-field text-sm py-2.5 border-yellow-500/50 bg-yellow-500/5";
  if (val < 9.5) return "input-field text-sm py-2.5 border-orange-500/50 bg-orange-500/5";
  return "input-field text-sm py-2.5 border-red-500/50 bg-red-500/5";
}

// ─── Plate Calculator ────────────────────────────────────────────────────────

const PLATE_SIZES_KG = [25, 20, 15, 10, 5, 2.5, 1.25];
const PLATE_SIZES_LBS = [45, 35, 25, 10, 5, 2.5];

const PLATE_COLOURS_KG: Record<number, string> = {
  25: "bg-red-600 text-white",
  20: "bg-blue-600 text-white",
  15: "bg-yellow-500 text-black",
  10: "bg-green-600 text-white",
  5: "bg-white text-black",
  2.5: "bg-red-400 text-white",
  1.25: "bg-gray-400 text-black",
};

const PLATE_COLOURS_LBS: Record<number, string> = {
  45: "bg-blue-600 text-white",
  35: "bg-yellow-500 text-black",
  25: "bg-green-600 text-white",
  10: "bg-white text-black",
  5: "bg-red-400 text-white",
  2.5: "bg-gray-400 text-black",
};

function PlateCalculator({
  targetWeight,
  onClose,
  useLbs,
}: {
  targetWeight: number;
  onClose: () => void;
  useLbs: boolean;
}) {
  const plateSizes = useLbs ? PLATE_SIZES_LBS : PLATE_SIZES_KG;
  const plateColours = useLbs ? PLATE_COLOURS_LBS : PLATE_COLOURS_KG;
  const unit = useLbs ? "lbs" : "kg";
  const defaultBar = useLbs ? 45 : 20;
  const altBar = useLbs ? 35 : 15;
  const [barWeight, setBarWeight] = useState(defaultBar);

  const plates: number[] = [];
  let remaining = Math.max(0, (targetWeight - barWeight) / 2);
  for (const plate of plateSizes) {
    while (remaining >= plate - 0.001) {
      plates.push(plate);
      remaining -= plate;
      remaining = Math.round(remaining * 1000) / 1000;
    }
  }

  const totalLoaded = barWeight + plates.reduce((s, p) => s + p, 0) * 2;

  return (
    <div className="fixed inset-0 z-50 flex items-end bg-black/40" onClick={onClose}>
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
            onClick={() => setBarWeight(defaultBar)}
            className={`flex-1 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              barWeight === defaultBar
                ? "bg-jungle-accent text-jungle-dark"
                : "bg-jungle-deeper border border-jungle-border text-jungle-muted"
            }`}
          >
            Men&apos;s bar ({defaultBar} {unit})
          </button>
          <button
            onClick={() => setBarWeight(altBar)}
            className={`flex-1 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              barWeight === altBar
                ? "bg-jungle-accent text-jungle-dark"
                : "bg-jungle-deeper border border-jungle-border text-jungle-muted"
            }`}
          >
            Women&apos;s bar ({altBar} {unit})
          </button>
        </div>

        {/* Target display */}
        <div className="text-center">
          <p className="text-jungle-dim text-xs uppercase tracking-wider">Target</p>
          <p className="text-2xl font-bold text-jungle-text">{targetWeight} {unit}</p>
          {Math.abs(totalLoaded - targetWeight) > 0.01 && (
            <p className="text-jungle-warning text-xs mt-0.5">
              Closest loadable: {totalLoaded} {unit}
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
                  className={`${plateColours[plate] || "bg-gray-500 text-white"} px-3 h-12 flex items-center justify-center rounded text-xs font-bold shadow`}
                >
                  {plate}
                </div>
              ))}
            </div>
          )}
        </div>

        <p className="text-jungle-dim text-xs text-center">
          Bar {barWeight} {unit} + {plates.reduce((s, p) => s + p, 0) * 2} {unit} plates = {totalLoaded} {unit} total
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

// ─── Rest Timer ──────────────────────────────────────────────────────────────

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
    <div className="fixed bottom-16 left-0 right-0 z-40 flex justify-center px-3">
      <div className="w-full max-w-lg mx-auto bg-jungle-card border border-jungle-border rounded-xl px-4 py-2.5 flex items-center justify-between shadow-2xl">
        <div>
          <p className="text-[10px] text-jungle-dim uppercase tracking-wider">
            {isCompound ? "Compound rest" : "Isolation rest"}
          </p>
          {isDone ? (
            <p className="text-green-400 font-semibold text-sm">Rest complete — go!</p>
          ) : (
            <p className="text-xl font-bold font-mono text-jungle-accent">{display}</p>
          )}
        </div>
        <button onClick={onSkip} className="btn-secondary text-sm px-4 py-1.5">
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

  // ── Set completion (no sequential locking — any set, any order) ──
  // Persisted to localStorage so in-progress workout survives logout/phone-off
  const [completedSets, setCompletedSets] = useState<Record<string, { reps: string; weight: string; rpe: string }>>(() => {
    if (typeof window !== "undefined") {
      try {
        const saved = localStorage.getItem("cpos_workout_completed");
        if (saved) {
          const parsed = JSON.parse(saved);
          // Only restore if saved today
          if (parsed._date === new Date().toISOString().split("T")[0]) {
            const { _date, ...rest } = parsed;
            return rest;
          }
        }
      } catch { /* ignore parse errors */ }
    }
    return {};
  });

  // ── Previous session ghosts ──
  const [previousSets, setPreviousSets] = useState<Record<string, { reps: number; weight: number }>>({});

  // ── Rest timer ──
  const [restTimer, setRestTimer] = useState<{ active: boolean; seconds: number; isCompound: boolean }>({
    active: false, seconds: 0, isCompound: true,
  });

  // ── Plate calculator ──
  const [plateCalc, setPlateCalc] = useState<{ open: boolean; weight: number }>({ open: false, weight: 0 });

  // ── Session notes ──
  const [sessionNotes, setSessionNotes] = useState("");
  const [showNotes, setShowNotes] = useState(false);

  // ── Machine taken / alternative exercise ──
  const [machineTaken, setMachineTaken] = useState<Set<string>>(new Set());
  const [altLog, setAltLog] = useState<Record<string, { name: string; weight: string; reps: string; rpe: string; logged: boolean }>>({});

  // ── Gym mode & Unit ──
  const [gymMode, setGymMode] = useState(false);
  const [useLbs, setUseLbs] = useState(false);

  // ── Accordion ──
  const [expandedExercise, setExpandedExercise] = useState<string | null>(null);
  const [expandedWarmups, setExpandedWarmups] = useState<Set<string>>(new Set());

  // ── Now Playing mode ──
  const [nowPlaying, setNowPlaying] = useState(false);
  const [currentSetIndex, setCurrentSetIndex] = useState(0);
  const [showHistory, setShowHistory] = useState(false);
  const [exerciseHistory, setExerciseHistory] = useState<StrengthEntry[]>([]);
  const [historyExercise, setHistoryExercise] = useState<string>("");
  const [progressToast, setProgressToast] = useState<string | null>(null);
  const [pendingAdvance, setPendingAdvance] = useState(false);

  const today = new Date().toISOString().split("T")[0];

  // Auto-save workout progress to localStorage (survives logout/phone-off)
  useEffect(() => {
    if (Object.keys(completedSets).length > 0) {
      localStorage.setItem("cpos_workout_completed", JSON.stringify({ _date: today, ...completedSets }));
    }
  }, [completedSets, today]);

  useEffect(() => {
    if (Object.keys(sets).length > 0) {
      localStorage.setItem("cpos_workout_sets", JSON.stringify({ _date: today, ...sets }));
    }
  }, [sets, today]);

  // Initialise gym mode and unit from localStorage
  useEffect(() => {
    const storedGym = localStorage.getItem("gymMode");
    if (storedGym === "true") setGymMode(true);
    const storedLbs = localStorage.getItem("useLbs");
    if (storedLbs === "true") setUseLbs(true);
  }, []);

  const toggleGymMode = () => {
    const next = !gymMode;
    setGymMode(next);
    localStorage.setItem("gymMode", String(next));
  };

  const toggleUnit = () => {
    const nextLbs = !useLbs;
    setUseLbs(nextLbs);
    localStorage.setItem("useLbs", String(nextLbs));

    // Map current active string inputs to new unit
    setSets((prev) => {
      const next = { ...prev };
      for (const k in next) {
        if (next[k].weight) {
          const w = parseFloat(next[k].weight);
          if (!isNaN(w)) {
            next[k].weight = nextLbs ? (w * 2.20462).toFixed(1) : (w / 2.20462).toFixed(1);
          }
        }
      }
      return next;
    });
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
          const lbs = localStorage.getItem("useLbs") === "true";
          const m = lbs ? 2.20462 : 1;

          const initial: Record<string, { reps: string; weight: string; rpe: string }> = {};
          const prevData: Record<string, { reps: number; weight: number }> = {};
          s.sets.forEach((set) => {
            let weightStr = "";
            if (set.actual_weight_kg) weightStr = (set.actual_weight_kg * m).toFixed(1);
            else if (set.prescribed_weight_kg) weightStr = (set.prescribed_weight_kg * m).toFixed(1);

            initial[set.id] = {
              reps: set.actual_reps?.toString() || set.prescribed_reps.toString(),
              weight: weightStr,
              rpe: set.rpe?.toString() || "",
            };
            if (set.last_actual_reps != null && set.last_actual_weight_kg != null) {
              prevData[set.id] = { reps: set.last_actual_reps, weight: Number((set.last_actual_weight_kg * m).toFixed(1)) };
            }
          });
          // Merge with any in-progress data saved to localStorage
          try {
            const savedSets = localStorage.getItem("cpos_workout_sets");
            if (savedSets) {
              const parsed = JSON.parse(savedSets);
              if (parsed._date === today) {
                const { _date, ...restored } = parsed;
                // Override API defaults with user's in-progress edits
                for (const [id, data] of Object.entries(restored)) {
                  if (initial[id]) {
                    initial[id] = data as { reps: string; weight: string; rpe: string };
                  }
                }
              }
            }
          } catch { /* ignore */ }

          setSets(initial);
          setPreviousSets(prevData);

          // Auto-expand first exercise
          const firstEx = s.sets.find((st) => !st.is_warmup);
          if (firstEx) setExpandedExercise(firstEx.exercise_name);
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
          setTimeout(() => setRestTimer({ active: false, seconds: 0, isCompound: true }), 3000);
          return { ...prev, seconds: 0 };
        }
        return { ...prev, seconds: prev.seconds - 1 };
      });
    }, 1000);
    return () => clearInterval(interval);
  }, [restTimer.active, restTimer.seconds]);

  if (loading || !user) return null;

  // ── Group sets by exercise ──
  const exerciseGroups: {
    name: string;
    muscle: string;
    equipment: string;
    warmupSets: TrainingSet[];
    workingSets: TrainingSet[];
  }[] = [];
  const seenExercises: Record<string, number> = {};

  session?.sets.forEach((set) => {
    if (!(set.exercise_name in seenExercises)) {
      seenExercises[set.exercise_name] = exerciseGroups.length;
      exerciseGroups.push({
        name: set.exercise_name,
        muscle: set.muscle_group,
        equipment: set.equipment || "weight",
        warmupSets: [],
        workingSets: [],
      });
    }
    const idx = seenExercises[set.exercise_name];
    if (set.is_warmup) {
      exerciseGroups[idx].warmupSets.push(set);
    } else {
      exerciseGroups[idx].workingSets.push(set);
    }
  });

  const allWorkingSets: TrainingSet[] = exerciseGroups.flatMap((g) => g.workingSets);
  const completedCount = Object.keys(completedSets).length;
  const totalCount = allWorkingSets.length;
  const allWorkingSetsComplete = totalCount > 0 && completedCount === totalCount;
  const unit = useLbs ? "lbs" : "kg";
  const m = useLbs ? 2.20462 : 1;

  const isCompoundExercise = (exerciseName: string): boolean => {
    return exerciseGroups.length > 0 && exerciseGroups[0].name === exerciseName;
  };

  // ── Handlers ──

  const logSet = (setId: string, field: string, value: string) => {
    setSets((prev) => ({ ...prev, [setId]: { ...prev[setId], [field]: value } }));
  };

  const markSetDone = (set: TrainingSet) => {
    const data = sets[set.id] || { reps: "", weight: "", rpe: "" };
    if (completedSets[set.id]) {
      // Undo — remove from completed
      setCompletedSets((prev) => {
        const next = { ...prev };
        delete next[set.id];
        return next;
      });
    } else {
      setCompletedSets((prev) => ({ ...prev, [set.id]: data }));
      const compound = isCompoundExercise(set.exercise_name);
      setRestTimer({ active: true, seconds: compound ? 180 : 90, isCompound: compound });
    }
  };

  const dismissTimer = () => {
    setRestTimer({ active: false, seconds: 0, isCompound: true });
    if (pendingAdvance) {
      setPendingAdvance(false);
      // Auto-advance to next incomplete set in Now Playing mode
      setCurrentSetIndex((prev) => {
        const next = prev + 1;
        // Find next incomplete starting from next index
        for (let i = next; i < allWorkingSets.length; i++) {
          return i; // advance regardless — let user decide to mark done or skip
        }
        return prev; // last set — stay
      });
    }
  };

  // Find first incomplete set index
  const findFirstIncomplete = (): number => {
    for (let i = 0; i < allWorkingSets.length; i++) {
      if (!completedSets[allWorkingSets[i].id]) return i;
    }
    return 0;
  };

  const startNowPlaying = () => {
    setCurrentSetIndex(findFirstIncomplete());
    setNowPlaying(true);
    setShowHistory(false);
  };

  const markSetDoneNowPlaying = (set: TrainingSet) => {
    const data = sets[set.id] || { reps: "", weight: "", rpe: "" };
    // Progressive overload toast — compare to last session
    const prev = previousSets[set.id];
    if (prev && data.weight) {
      const currentW = parseFloat(data.weight);
      const prevW = prev.weight;
      if (!isNaN(currentW) && currentW > prevW) {
        setProgressToast(`${set.exercise_name} — Leveled up! 🎯`);
        setTimeout(() => setProgressToast(null), 2500);
      }
    }
    setCompletedSets((p) => ({ ...p, [set.id]: data }));
    const compound = isCompoundExercise(set.exercise_name);
    setRestTimer({ active: true, seconds: compound ? 180 : 90, isCompound: compound });
    setPendingAdvance(true);
  };

  // Fetch exercise history for quick history panel in Now Playing
  const fetchExerciseHistory = (exerciseName: string) => {
    if (exerciseName === historyExercise) {
      setShowHistory((p) => !p);
      return;
    }
    setHistoryExercise(exerciseName);
    setShowHistory(true);
    setExerciseHistory([]);
    api.get<StrengthEntry[]>(`/engine2/strength-log?exercise=${encodeURIComponent(exerciseName)}&limit=5`)
      .then(setExerciseHistory)
      .catch(() => {});
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
      const p = await api.post<Program & { sessions_created: number; message: string }>("/engine2/program/generate");
      setProgram(p);
    } catch { /* */ } finally { setGenerating(false); }
  };

  const saveSession = async () => {
    if (!session) return;
    setSaving(true);
    try {
      const loggedSets = Object.entries(sets).map(([id, data]) => {
        const setObj = session.sets.find(s => s.id === id);
        const exName = setObj?.exercise_name || "";
        const isTaken = machineTaken.has(exName);
        const altName = isTaken ? altLog[exName]?.name : undefined;

        return {
          set_id: id,
          actual_reps: data.reps ? parseInt(data.reps) : null,
          actual_weight_kg: data.weight ? parseFloat(data.weight) / (useLbs ? 2.20462 : 1) : null,
          rpe: data.rpe ? parseFloat(data.rpe) : null,
          actual_exercise_name: altName || exName,
        };
      });
      const result = await api.post<{ message: string; progressions: Progression[] }>(
        `/engine2/session/${session.id}/log`,
        { sets: loggedSets, notes: sessionNotes || undefined }
      );
      setProgressions(result.progressions || []);
      setSaved(true);
      // Clear localStorage after successful save — workout is persisted to server
      localStorage.removeItem("cpos_workout_completed");
      localStorage.removeItem("cpos_workout_sets");
      setTimeout(() => setSaved(false), 3000);
    } catch { /* */ } finally { setSaving(false); }
  };

  // ── Helpers ──

  const exerciseCompletedCount = (exName: string) => {
    const group = exerciseGroups.find((g) => g.name === exName);
    if (!group) return 0;
    return group.workingSets.filter((s) => completedSets[s.id]).length;
  };

  // ── Render ──
  return (
    <div className="min-h-screen">
      <NavBar username={user.username} onLogout={() => { logout(); router.push("/"); }} />

      <main className="px-3 py-4 pb-24">
        <div className="max-w-lg mx-auto space-y-4">

          {/* Header */}
          <div className="flex items-start justify-between">
            <div className="min-w-0 flex-1">
              <h1 className="text-xl font-bold">
                <span className="text-jungle-accent">Training</span>
              </h1>
              {program ? (
                <p className="text-jungle-muted text-xs mt-0.5 truncate">
                  {program.name} — Wk {program.current_week}/{program.mesocycle_weeks} · {program.split_type} · {program.days_per_week}d/wk
                </p>
              ) : (
                <p className="text-jungle-muted text-xs mt-0.5">No active program</p>
              )}
            </div>
            <div className="flex items-center gap-1.5 ml-2 flex-shrink-0">
              <button
                onClick={toggleUnit}
                className={`px-2 h-8 rounded-lg flex items-center justify-center text-[10px] font-bold transition-colors ${
                  useLbs
                    ? "bg-jungle-accent text-jungle-dark"
                    : "bg-jungle-deeper border border-jungle-border text-jungle-dim hover:border-jungle-accent"
                }`}
              >
                {useLbs ? "LBS" : "KG"}
              </button>
              <button
                onClick={toggleGymMode}
                className={`px-2 h-8 rounded-lg flex items-center justify-center text-[10px] font-bold tracking-wide transition-colors ${
                  gymMode
                    ? "bg-jungle-accent text-jungle-dark"
                    : "bg-jungle-deeper border border-jungle-border text-jungle-dim hover:border-jungle-accent"
                }`}
              >
                {gymMode ? "GYM ✓" : "GYM"}
              </button>
            </div>
          </div>

          {/* No program */}
          {!program && (
            <div className="card text-center py-10">
              <p className="text-jungle-muted">No active program</p>
              <button onClick={generateProgram} disabled={generating} className="btn-primary mt-4 disabled:opacity-50">
                {generating ? "Generating..." : "Generate Program"}
              </button>
            </div>
          )}

          {/* No session today */}
          {program && !session && (
            <div className="card text-center py-10">
              <p className="text-jungle-muted text-lg">Rest Day 💤</p>
              <p className="text-jungle-dim text-sm mt-1">No session scheduled — enjoy recovery</p>
            </div>
          )}

          {/* Session */}
          {session && (
            <>
              {/* Session info bar */}
              <div className={`card py-3 ${gymMode ? "gym-mode" : ""}`}>
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="font-semibold capitalize text-base">
                      {session.session_type.replace(/_/g, " ")} Day
                    </h2>
                    <p className="text-jungle-dim text-[11px]">
                      Wk {session.week_number} · Day {session.day_number} · {totalCount} working sets
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-medium ${
                        session.completed
                          ? "bg-green-500/20 text-green-400"
                          : "bg-jungle-accent/20 text-jungle-accent"
                      }`}
                    >
                      {session.completed ? "Done" : `${completedCount}/${totalCount}`}
                    </span>
                    {!session.completed && totalCount > 0 && (
                      <button
                        onClick={nowPlaying ? () => setNowPlaying(false) : startNowPlaying}
                        className={`px-3 py-1 rounded-lg text-xs font-bold transition-all ${
                          nowPlaying
                            ? "bg-jungle-deeper border border-jungle-border text-jungle-dim"
                            : "bg-jungle-accent text-jungle-dark"
                        }`}
                      >
                        {nowPlaying ? "Overview" : "▶ Start"}
                      </button>
                    )}
                  </div>
                </div>
              </div>

              {/* Stale baseline warning */}
              {session.stale_baselines && (
                <div className="rounded-xl border border-yellow-500/40 bg-yellow-500/10 px-3 py-2 text-xs text-yellow-300">
                  ⚠️ Strength baselines are 90+ days old — weights may be approximate.
                </div>
              )}

              {/* Progressive Overload Toast */}
              {progressToast && (
                <div className="rounded-xl border border-jungle-accent/40 bg-jungle-accent/10 px-4 py-2.5 text-sm font-semibold text-jungle-accent text-center animate-pulse">
                  {progressToast}
                </div>
              )}

              {/* ── Now Playing Card ── */}
              {nowPlaying && allWorkingSets.length > 0 && (() => {
                const currentSet = allWorkingSets[currentSetIndex] ?? allWorkingSets[0];
                if (!currentSet) return null;
                const exGroup = exerciseGroups.find((g) => g.name === currentSet.exercise_name);
                const isCompleted = !!completedSets[currentSet.id];
                const prev = previousSets[currentSet.id];
                const isBarbell = (currentSet.equipment || "").toLowerCase().includes("barbell");
                const currentWeight = sets[currentSet.id]?.weight || "";
                const totalForEx = exGroup?.workingSets.length || 0;
                const setIdxInEx = (exGroup?.workingSets.findIndex((s) => s.id === currentSet.id) ?? 0) + 1;
                const compound = isCompoundExercise(currentSet.exercise_name);

                return (
                  <div className="space-y-3">
                    {/* Exercise overview dots */}
                    <div className="flex gap-1 overflow-x-auto pb-1">
                      {allWorkingSets.map((s, idx) => (
                        <button
                          key={s.id}
                          onClick={() => setCurrentSetIndex(idx)}
                          className={`shrink-0 w-2.5 h-2.5 rounded-full transition-all ${
                            idx === currentSetIndex
                              ? "bg-jungle-accent scale-125"
                              : completedSets[s.id]
                              ? "bg-green-500/60"
                              : "bg-jungle-deeper border border-jungle-border"
                          }`}
                          title={`${s.exercise_name} set ${idx + 1}`}
                        />
                      ))}
                    </div>

                    {/* Main card */}
                    <div className={`rounded-2xl border-2 p-5 space-y-4 transition-all ${
                      isCompleted
                        ? "border-green-500/40 bg-green-500/5"
                        : "border-jungle-accent/40 bg-jungle-card"
                    }`}>
                      {/* Exercise header */}
                      <div className="flex items-start justify-between">
                        <div>
                          <p className="text-[10px] text-jungle-dim uppercase tracking-widest mb-0.5">
                            {currentSet.muscle_group.replace(/_/g, " ")} · {compound ? "Compound" : "Isolation"}
                          </p>
                          <h2 className="text-xl font-bold text-jungle-text leading-tight">
                            {currentSet.exercise_name}
                          </h2>
                          <p className="text-jungle-accent text-sm font-semibold mt-0.5">
                            Set {setIdxInEx} of {totalForEx}
                            <span className="text-jungle-dim font-normal ml-2">
                              ({currentSetIndex + 1}/{allWorkingSets.length} total)
                            </span>
                          </p>
                        </div>
                        <button
                          onClick={() => fetchExerciseHistory(currentSet.exercise_name)}
                          className={`text-xs px-2.5 py-1 rounded-lg border transition-colors shrink-0 ${
                            showHistory && historyExercise === currentSet.exercise_name
                              ? "border-jungle-accent/50 bg-jungle-accent/10 text-jungle-accent"
                              : "border-jungle-border text-jungle-dim hover:border-jungle-accent/50"
                          }`}
                        >
                          History
                        </button>
                      </div>

                      {/* Quick history panel */}
                      {showHistory && historyExercise === currentSet.exercise_name && (
                        <div className="bg-jungle-deeper rounded-xl p-3 space-y-1.5">
                          <p className="text-[10px] text-jungle-dim uppercase tracking-wide mb-1">Last sessions</p>
                          {exerciseHistory.length === 0 ? (
                            <p className="text-jungle-dim text-xs">No history yet</p>
                          ) : (
                            exerciseHistory.map((e, i) => (
                              <div key={i} className="flex justify-between text-xs">
                                <span className="text-jungle-dim">{e.date}</span>
                                <span className="text-jungle-muted font-medium">
                                  {useLbs ? (e.weight_kg * 2.20462).toFixed(1) : e.weight_kg}{unit} × {e.reps}
                                  {e.rpe && <span className="text-jungle-dim ml-1">@ RPE {e.rpe}</span>}
                                </span>
                              </div>
                            ))
                          )}
                        </div>
                      )}

                      {/* Prescribed target */}
                      {currentSet.prescribed_weight_kg && (
                        <div className="flex items-center gap-2">
                          <span className="text-[10px] text-jungle-dim uppercase tracking-wide">Target:</span>
                          <span className="text-sm font-semibold text-jungle-muted">
                            {useLbs ? (currentSet.prescribed_weight_kg * 2.20462).toFixed(1) : currentSet.prescribed_weight_kg.toFixed(1)} {unit} × {currentSet.prescribed_reps}
                          </span>
                          {prev && (
                            <span className="text-[10px] text-jungle-dim ml-auto">
                              Last: {prev.weight}{unit} × {prev.reps}
                            </span>
                          )}
                        </div>
                      )}

                      {/* Inputs */}
                      <div className="grid grid-cols-3 gap-3">
                        <div>
                          <label className="text-[10px] text-jungle-dim uppercase tracking-wider block mb-1">
                            Weight ({unit})
                          </label>
                          <input
                            type="number"
                            step="0.5"
                            inputMode="decimal"
                            value={sets[currentSet.id]?.weight || ""}
                            onChange={(e) => logSet(currentSet.id, "weight", e.target.value)}
                            className="input-field text-base py-3 text-center font-semibold"
                            placeholder="0"
                          />
                        </div>
                        <div>
                          <label className="text-[10px] text-jungle-dim uppercase tracking-wider block mb-1">
                            Reps
                          </label>
                          <input
                            type="number"
                            inputMode="numeric"
                            value={sets[currentSet.id]?.reps || ""}
                            onChange={(e) => logSet(currentSet.id, "reps", e.target.value)}
                            className="input-field text-base py-3 text-center font-semibold"
                            placeholder={String(currentSet.prescribed_reps)}
                          />
                        </div>
                        <div>
                          <label className="text-[10px] text-jungle-dim uppercase tracking-wider block mb-1">
                            RPE
                          </label>
                          <input
                            type="number"
                            step="0.5"
                            min="1"
                            max="10"
                            inputMode="decimal"
                            value={sets[currentSet.id]?.rpe || ""}
                            onChange={(e) => logSet(currentSet.id, "rpe", e.target.value)}
                            className={`${rpeClass(sets[currentSet.id]?.rpe || "")} text-base py-3 text-center font-semibold`}
                            placeholder="RPE"
                          />
                        </div>
                      </div>

                      {/* Plates link */}
                      {isBarbell && currentWeight && (
                        <button
                          onClick={() => setPlateCalc({ open: true, weight: parseFloat(currentWeight) || 0 })}
                          className="text-xs text-jungle-dim hover:text-jungle-accent transition-colors"
                        >
                          🏋️ View plates
                        </button>
                      )}

                      {/* Set Done button */}
                      <button
                        onClick={() => isCompleted ? markSetDone(currentSet) : markSetDoneNowPlaying(currentSet)}
                        className={`w-full py-4 rounded-xl text-base font-bold transition-all ${
                          isCompleted
                            ? "bg-green-500/20 text-green-400 border-2 border-green-500/30"
                            : "bg-jungle-accent text-jungle-dark hover:bg-jungle-accent/90 active:scale-95"
                        }`}
                      >
                        {isCompleted ? "✓ Set Done — Tap to Undo" : "Set Done ▶"}
                      </button>
                    </div>

                    {/* Nav buttons */}
                    <div className="flex gap-2">
                      <button
                        onClick={() => setCurrentSetIndex(Math.max(0, currentSetIndex - 1))}
                        disabled={currentSetIndex === 0}
                        className="flex-1 btn-secondary text-sm disabled:opacity-30"
                      >
                        ← Prev
                      </button>
                      <button
                        onClick={() => setCurrentSetIndex(Math.min(allWorkingSets.length - 1, currentSetIndex + 1))}
                        disabled={currentSetIndex >= allWorkingSets.length - 1}
                        className="flex-1 btn-secondary text-sm disabled:opacity-30"
                      >
                        Next →
                      </button>
                    </div>
                  </div>
                );
              })()}

              {/* Exercise Accordion (hidden in now playing mode) */}
              <div className={`space-y-2 ${gymMode ? "gym-mode" : ""} ${nowPlaying ? "hidden" : ""}`}>
                {exerciseGroups.map(({ name, muscle, equipment, warmupSets, workingSets }) => {
                  const isExpanded = expandedExercise === name;
                  const isMachineTaken = machineTaken.has(name);
                  const completedForEx = exerciseCompletedCount(name);
                  const totalForEx = workingSets.length;
                  const allDoneForEx = completedForEx === totalForEx && totalForEx > 0;
                  const showWarmups = expandedWarmups.has(name);

                  return (
                    <div key={name} className={`rounded-xl border transition-colors ${
                      isMachineTaken ? "border-yellow-500/30 bg-jungle-card" :
                      allDoneForEx ? "border-green-500/20 bg-jungle-card/80" :
                      isExpanded ? "border-jungle-accent/30 bg-jungle-card" :
                      "border-jungle-border bg-jungle-card/60"
                    }`}>

                      {/* Exercise header — always visible, tap to expand */}
                      <button
                        onClick={() => setExpandedExercise(isExpanded ? null : name)}
                        className="w-full text-left px-4 py-3 flex items-center gap-3"
                      >
                        {/* Completion indicator */}
                        <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 text-xs font-bold ${
                          allDoneForEx ? "bg-green-500/20 text-green-400" :
                          completedForEx > 0 ? "bg-jungle-accent/20 text-jungle-accent" :
                          "bg-jungle-deeper text-jungle-dim"
                        }`}>
                          {allDoneForEx ? "✓" : `${completedForEx}/${totalForEx}`}
                        </div>

                        <div className="flex-1 min-w-0">
                          {isMachineTaken ? (
                            <input
                              type="text"
                              value={altLog[name]?.name || ""}
                              onClick={(e) => e.stopPropagation()}
                              onChange={(e) => setAltLog((prev) => ({ ...prev, [name]: { ...prev[name], name: e.target.value } }))}
                              placeholder={`Sub for ${name}...`}
                              className="bg-transparent text-yellow-400 font-semibold text-sm w-full outline-none border-b border-yellow-500/30 focus:border-yellow-500 placeholder-yellow-500/30"
                            />
                          ) : (
                            <p className={`font-semibold text-sm truncate ${allDoneForEx ? "text-jungle-dim" : "text-jungle-text"}`}>
                              {name}
                            </p>
                          )}
                          <p className="text-[10px] text-jungle-dim uppercase tracking-wide mt-0.5">
                            {muscle.replace(/_/g, " ")} · {equipment}
                          </p>
                        </div>

                        {/* Chevron */}
                        <svg
                          className={`w-4 h-4 text-jungle-dim transition-transform flex-shrink-0 ${isExpanded ? "rotate-180" : ""}`}
                          fill="none" viewBox="0 0 24 24" stroke="currentColor"
                        >
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                        </svg>
                      </button>

                      {/* Expanded content */}
                      {isExpanded && (
                        <div className="px-4 pb-4 space-y-2">
                          {/* Machine taken toggle */}
                          <div className="flex gap-2 mb-1">
                            <button
                              onClick={() => toggleMachineTaken(name)}
                              className={`text-[10px] px-2.5 py-1 rounded-lg border transition-colors ${
                                isMachineTaken
                                  ? "border-yellow-500/50 bg-yellow-500/10 text-yellow-400"
                                  : "border-jungle-border text-jungle-dim hover:border-yellow-500/40"
                              }`}
                            >
                              {isMachineTaken ? "Cancel Sub" : "Machine Taken?"}
                            </button>
                          </div>

                          {/* Compact warmup summary */}
                          {warmupSets.length > 0 && (
                            <div>
                              <button
                                onClick={() => setExpandedWarmups((prev) => {
                                  const next = new Set(prev);
                                  next.has(name) ? next.delete(name) : next.add(name);
                                  return next;
                                })}
                                className="w-full text-left text-[11px] text-jungle-dim bg-jungle-deeper/60 rounded-lg px-3 py-1.5 flex items-center justify-between"
                              >
                                <span>
                                  {warmupSets.length} warm-up set{warmupSets.length > 1 ? "s" : ""} →{" "}
                                  {warmupSets.map((ws) =>
                                    ws.prescribed_weight_kg ? `${(ws.prescribed_weight_kg * m).toFixed(0)}` : "—"
                                  ).join(" → ")} {unit}
                                </span>
                                <svg className={`w-3 h-3 transition-transform ${showWarmups ? "rotate-180" : ""}`}
                                  fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                                </svg>
                              </button>
                              {showWarmups && (
                                <div className="mt-1 space-y-1">
                                  {warmupSets.map((ws) => (
                                    <div key={ws.id} className="text-[11px] text-jungle-dim bg-jungle-deeper/40 rounded-lg px-3 py-1 flex justify-between">
                                      <span>Warm-up</span>
                                      <span>{ws.prescribed_weight_kg ? (ws.prescribed_weight_kg * m).toFixed(1) : "—"} {unit} × {ws.prescribed_reps}</span>
                                    </div>
                                  ))}
                                </div>
                              )}
                            </div>
                          )}

                          {/* Working sets — mobile cards */}
                          {workingSets.map((set, setIdx) => {
                            const isCompleted = !!completedSets[set.id];
                            const prev = previousSets[set.id];
                            const currentWeight = sets[set.id]?.weight || "";
                            const prescribedDisplay = set.prescribed_weight_kg
                              ? `${(set.prescribed_weight_kg * m).toFixed(1)} ${unit} × ${set.prescribed_reps}`
                              : `— × ${set.prescribed_reps}`;

                            return (
                              <div
                                key={set.id}
                                className={`rounded-lg border p-3 transition-all ${
                                  isCompleted
                                    ? "border-green-500/20 bg-green-500/5"
                                    : "border-jungle-border/50 bg-jungle-deeper/30"
                                }`}
                              >
                                {/* Set header */}
                                <div className="flex items-center justify-between mb-2">
                                  <div className="flex items-center gap-2">
                                    <span className={`text-xs font-bold ${isCompleted ? "text-green-400" : "text-jungle-muted"}`}>
                                      Set {setIdx + 1}/{totalForEx}
                                    </span>
                                    <span className="text-[10px] text-jungle-dim">
                                      Target: {prescribedDisplay}
                                    </span>
                                  </div>
                                  <button
                                    onClick={() => markSetDone(set)}
                                    className={`px-3 py-1 rounded-lg text-xs font-bold transition-all ${
                                      isCompleted
                                        ? "bg-green-500/20 text-green-400 border border-green-500/30"
                                        : "bg-jungle-accent text-jungle-dark hover:bg-jungle-accent/90"
                                    }`}
                                  >
                                    {isCompleted ? "Undo" : "Done"}
                                  </button>
                                </div>

                                {/* Inputs — 3 columns, big tap targets */}
                                <div className="grid grid-cols-3 gap-2">
                                  <div>
                                    <label className="text-[9px] text-jungle-dim uppercase tracking-wider block mb-0.5">
                                      Weight ({unit})
                                    </label>
                                    <div className="flex gap-1">
                                      <input
                                        type="number"
                                        step="0.5"
                                        inputMode="decimal"
                                        value={sets[set.id]?.weight || ""}
                                        onChange={(e) => logSet(set.id, "weight", e.target.value)}
                                        className="input-field text-sm py-2.5 flex-1 min-w-0"
                                        placeholder={unit}
                                      />
                                    </div>
                                  </div>
                                  <div>
                                    <label className="text-[9px] text-jungle-dim uppercase tracking-wider block mb-0.5">
                                      Reps
                                    </label>
                                    <input
                                      type="number"
                                      inputMode="numeric"
                                      value={sets[set.id]?.reps || ""}
                                      onChange={(e) => logSet(set.id, "reps", e.target.value)}
                                      className="input-field text-sm py-2.5"
                                      placeholder="reps"
                                    />
                                  </div>
                                  <div>
                                    <label className="text-[9px] text-jungle-dim uppercase tracking-wider block mb-0.5">
                                      RPE
                                    </label>
                                    <input
                                      type="number"
                                      step="0.5"
                                      min="1"
                                      max="10"
                                      inputMode="decimal"
                                      value={sets[set.id]?.rpe || ""}
                                      onChange={(e) => logSet(set.id, "rpe", e.target.value)}
                                      className={rpeClass(sets[set.id]?.rpe || "")}
                                      placeholder="RPE"
                                    />
                                  </div>
                                </div>

                                {/* Bottom row: plates + last session */}
                                <div className="flex items-center justify-between mt-1.5">
                                  {(equipment === "barbell" || equipment === "machine") && currentWeight ? (
                                    <button
                                      onClick={() => setPlateCalc({ open: true, weight: parseFloat(currentWeight) || 0 })}
                                      className="text-[10px] text-jungle-dim hover:text-jungle-accent transition-colors flex items-center gap-1"
                                    >
                                      <span>Plates →</span>
                                    </button>
                                  ) : <span />}
                                  {prev && (
                                    <span className="text-[10px] text-jungle-dim">
                                      Last: {prev.weight}{unit} × {prev.reps}
                                    </span>
                                  )}
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
              {/* End accordion */}

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
                    <p className="text-[10px] text-jungle-dim mt-0.5">How did the session feel?</p>
                  </div>
                  <svg
                    className={`w-4 h-4 text-jungle-dim transition-transform ${showNotes ? "rotate-180" : ""}`}
                    fill="none" viewBox="0 0 24 24" stroke="currentColor"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </button>
                {showNotes && (
                  <div className="mt-3 pt-3 border-t border-jungle-border">
                    <textarea
                      value={sessionNotes}
                      onChange={(e) => setSessionNotes(e.target.value)}
                      rows={3}
                      placeholder="Observations, energy levels, pump quality…"
                      className="input-field text-sm resize-none"
                    />
                  </div>
                )}
              </div>

              {/* Progression readouts */}
              {progressions.length > 0 && (
                <div className="card border-jungle-accent/40">
                  <h3 className="text-xs font-semibold text-jungle-accent uppercase tracking-wider mb-2">
                    Progression Unlocked
                  </h3>
                  {progressions.map((p) => (
                    <div key={p.exercise} className="flex justify-between items-center py-1 text-sm border-b border-jungle-border last:border-0">
                      <span className="text-jungle-muted text-xs">{p.exercise}</span>
                      <span className="text-green-400 font-semibold text-xs">
                        → {useLbs ? (p.next_weight_kg * 2.20462).toFixed(1) : p.next_weight_kg}{unit} × {p.next_reps}
                      </span>
                    </div>
                  ))}
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
              <div className="mt-4 space-y-3 pt-4 border-t border-jungle-border">
                <div className="grid grid-cols-2 gap-3">
                  <div className="col-span-2">
                    <label className="label-field">Exercise Name</label>
                    <input type="text" value={sExercise} onChange={(e) => setSExercise(e.target.value)}
                      placeholder="e.g. Barbell Back Squat" className="input-field mt-1 text-sm" />
                  </div>
                  <div>
                    <label className="label-field">Weight ({unit})</label>
                    <input type="number" step="0.5" value={sWeight} onChange={(e) => setSWeight(e.target.value)}
                      className="input-field mt-1 text-sm" placeholder="e.g. 120" />
                  </div>
                  <div>
                    <label className="label-field">Reps</label>
                    <input type="number" value={sReps} onChange={(e) => setSReps(e.target.value)}
                      className="input-field mt-1 text-sm" placeholder="e.g. 3" />
                  </div>
                  <div>
                    <label className="label-field">RPE (optional)</label>
                    <input type="number" step="0.5" min="1" max="10" value={sRpe} onChange={(e) => setSRpe(e.target.value)}
                      className="input-field mt-1 text-sm" placeholder="e.g. 9" />
                  </div>
                  <div className="flex items-end">
                    <button onClick={logStrengthTest} disabled={sLogging || !sExercise || !sWeight || !sReps}
                      className="btn-primary w-full text-sm disabled:opacity-50">
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

      {/* ── Sticky bottom bar: progress + save ── */}
      {session && totalCount > 0 && (
        <div className="fixed bottom-0 left-0 right-0 z-30 bg-jungle-card/95 backdrop-blur-md border-t border-jungle-border safe-bottom">
          <div className="max-w-lg mx-auto px-4 py-2.5 flex items-center gap-3">
            {/* Progress bar */}
            <div className="flex-1">
              <div className="h-1.5 bg-jungle-deeper rounded-full overflow-hidden">
                <div
                  className="h-full bg-jungle-accent rounded-full transition-all"
                  style={{ width: `${(completedCount / totalCount) * 100}%` }}
                />
              </div>
              <p className="text-[10px] text-jungle-dim mt-0.5">
                {completedCount}/{totalCount} sets
              </p>
            </div>
            {/* Save button */}
            <button
              onClick={saveSession}
              disabled={saving}
              className={`px-5 py-2 rounded-xl text-sm font-bold transition-all disabled:opacity-50 ${
                allWorkingSetsComplete
                  ? "bg-jungle-accent text-jungle-dark"
                  : "bg-jungle-deeper border border-jungle-border text-jungle-muted hover:border-jungle-accent"
              }`}
            >
              {saved ? "Saved ✓" : saving ? "Saving..." : allWorkingSetsComplete ? "Log Session" : "Save Partial"}
            </button>
          </div>
        </div>
      )}

      {/* Rest Timer (above sticky bar) */}
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
          useLbs={useLbs}
        />
      )}
    </div>
  );
}
