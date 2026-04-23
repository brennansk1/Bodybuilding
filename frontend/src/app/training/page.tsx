"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import NavBar from "@/components/NavBar";
import ViltrumLoader from "@/components/ViltrumLoader";
import PageTitle from "@/components/PageTitle";
import PlateLoadingSVG from "@/components/PlateLoadingSVG";
import SessionProgressRing from "@/components/SessionProgressRing";
import SessionSummary from "@/components/SessionSummary";
import ExerciseSwapModal from "@/components/ExerciseSwapModal";
import { api } from "@/lib/api";
import { showToast } from "@/components/Toast";

// ─── Interfaces ──────────────────────────────────────────────────────────────

interface TrainingSet {
  id: string;
  exercise_id?: string;
  exercise_name: string;
  muscle_group: string;
  set_number: number;
  prescribed_reps: number;
  prescribed_weight_kg: number | null;
  prescribed_rir?: number | null;
  prescribed_rpe?: number | null;
  tempo?: string | null;
  set_technique?: string | null;
  technique_cue?: string | null;
  actual_reps: number | null;
  actual_weight_kg: number | null;
  rpe: number | null;
  is_warmup?: boolean;
  equipment?: string;
  movement_pattern?: string;
  load_type?: string;
  is_fst7?: boolean;
  rest_seconds?: number | null;
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
  completed_at?: string | null;
  started_at?: string | null;
  pump_quality?: number | null;
  session_difficulty?: number | null;
  joint_comfort?: number | null;
  sets: TrainingSet[];
  stale_baselines?: boolean;
  dup_profile?: string;
  estimated_duration_min?: number;
  workout_window?: {
    anchor_mode: "start" | "end";
    start_time: string | null;
    end_time: string | null;
  };
}

interface FinishSessionResponse {
  message: string;
  progressions: Progression[];
  session_duration_seconds?: number;
  total_volume_kg?: number;
  sets_completed?: number;
  sets_total?: number;
  muscles_trained?: string[];
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
    <div className="fixed inset-0 z-50 flex items-end bg-viltrum-obsidian/30" onClick={onClose}>
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
                ? "bg-jungle-accent text-white"
                : "bg-jungle-deeper border border-jungle-border text-jungle-muted"
            }`}
          >
            Men&apos;s bar ({defaultBar} {unit})
          </button>
          <button
            onClick={() => setBarWeight(altBar)}
            className={`flex-1 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              barWeight === altBar
                ? "bg-jungle-accent text-white"
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
  isFst7,
  label,
  onSkip,
}: {
  seconds: number;
  isCompound: boolean;
  isFst7?: boolean;
  label?: string;
  onSkip: () => void;
}) {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  const display = `${mins}:${secs.toString().padStart(2, "0")}`;
  const isDone = seconds <= 0;

  const protocolLabel = label || (isFst7
    ? `FST-7 finisher: ${seconds}s`
    : isCompound
    ? `Heavy compound: ${mins}:${secs.toString().padStart(2, "0")}`
    : `Isolation: ${mins}:${secs.toString().padStart(2, "0")}`);

  return (
    <div className="fixed bottom-16 left-0 right-0 z-40 flex justify-center px-3">
      <div className={`w-full max-w-lg mx-auto border rounded-xl px-4 py-2.5 flex items-center justify-between shadow-2xl ${
        isFst7 ? "bg-purple-900/80 border-purple-500/50" : "bg-jungle-card border-jungle-border"
      }`}>
        <div>
          <p className={`text-[10px] uppercase tracking-wider ${isFst7 ? "text-purple-300" : "text-jungle-dim"}`}>
            {protocolLabel}
          </p>
          {isDone ? (
            <p className="text-green-400 font-semibold text-sm">Rest complete — go!</p>
          ) : (
            <p className={`text-xl font-bold font-mono ${isFst7 ? "text-purple-300" : "text-jungle-accent"}`}>{display}</p>
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

  // ── Pre-workout readiness (ARI) ──
  const [readiness, setReadiness] = useState<{
    ari_score: number;
    zone: "green" | "yellow" | "red";
    components?: Record<string, number>;
    recommendation?: string;
  } | null>(null);

  // ── Cardio prescription + logging state ──
  const [cardioPrescription, setCardioPrescription] = useState<{
    cardio: {
      sessions_per_week: number; duration_min: number; modality: string;
      modality_options: string[]; fasted: boolean; notes: string[];
      estimated_weekly_burn_kcal: number;
    };
    neat: { step_target: number; kcal_estimate: number; note: string };
    summary: { total_weekly_expenditure_kcal: number; cardio_sessions: number; step_target: number };
  } | null>(null);
  const [cardioMachine, setCardioMachine] = useState("treadmill");
  const [cardioSpeed, setCardioSpeed] = useState("3.0");
  const [cardioIncline, setCardioIncline] = useState("12");
  const [cardioStairLevel, setCardioStairLevel] = useState("6");
  const [cardioBikeResistance, setCardioBikeResistance] = useState("10");
  const [cardioBikeRpm, setCardioBikeRpm] = useState("80");
  const [cardioEllipticalResistance, setCardioEllipticalResistance] = useState("8");
  const [cardioEllipticalIncline, setCardioEllipticalIncline] = useState("6");
  const [cardioRowerPace, setCardioRowerPace] = useState("2:15");
  const [cardioRowerDamper, setCardioRowerDamper] = useState("5");
  const [cardioDuration, setCardioDuration] = useState("30");
  const [cardioFasted, setCardioFasted] = useState(true);
  const [cardioLogged, setCardioLogged] = useState(false);
  const [cardioLogging, setCardioLogging] = useState(false);

  // ── Set completion (no sequential locking — any set, any order) ──
  // Persisted to localStorage so in-progress workout survives logout/phone-off
  // Session restore now happens in the data fetch effect (derives from server + localStorage)
  const [completedSets, setCompletedSets] = useState<Record<string, { reps: string; weight: string; rpe: string }>>({});

  // ── Previous session ghosts ──
  const [previousSets, setPreviousSets] = useState<Record<string, { reps: number; weight: number }>>({});

  // ── Rest timer ──
  const [restTimer, setRestTimer] = useState<{ active: boolean; seconds: number; isCompound: boolean; isFst7: boolean }>({
    active: false, seconds: 0, isCompound: true, isFst7: false,
  });

  // ── Plate calculator ──
  const [plateCalc, setPlateCalc] = useState<{ open: boolean; weight: number }>({ open: false, weight: 0 });

  // ── Session notes ──
  const [sessionNotes, setSessionNotes] = useState("");

  // Post-session summary state
  interface SessionSummaryData {
    duration_seconds: number | null;
    total_volume_kg: number | null;
    sets_completed: number;
    sets_total: number;
    muscles_trained: string[];
    progressions: Progression[];
  }
  const [showSummary, setShowSummary] = useState(false);
  const [sessionSummary, setSessionSummary] = useState<SessionSummaryData | null>(null);

  // Exercise swap modal state (B5)
  const [swapTarget, setSwapTarget] = useState<{
    exerciseId: string; exerciseName: string; primaryMuscle: string;
  } | null>(null);

  const reloadSession = async () => {
    if (!session) return;
    try {
      const fresh = await api.get<TrainingSession>(`/engine2/session/${session.id}`);
      setSession(fresh);
    } catch {
      /* ignore */
    }
  };
  const [showNotes, setShowNotes] = useState(false);

  // ── Machine taken / alternative exercise ──
  const [machineTaken, setMachineTaken] = useState<Set<string>>(new Set());
  const [altLog, setAltLog] = useState<Record<string, { name: string; weight: string; reps: string; rpe: string; logged: boolean }>>({});

  // ── Day navigation ──
  const [viewOffset, setViewOffset] = useState(0); // 0 = today, +1 = tomorrow, -1 = yesterday
  const viewDate = (() => {
    const d = new Date();
    d.setDate(d.getDate() + viewOffset);
    // Build YYYY-MM-DD in local timezone (not UTC) to avoid timezone shift
    const yyyy = d.getFullYear();
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    const dd = String(d.getDate()).padStart(2, "0");
    return `${yyyy}-${mm}-${dd}`;
  })();
  const isToday = viewOffset === 0;
  const viewLabel = isToday
    ? "Today"
    : viewOffset === 1
    ? "Tomorrow"
    : viewOffset === -1
    ? "Yesterday"
    : new Date(viewDate + "T00:00:00").toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" });

  // ── Gym mode & Unit ──
  const [gymMode, setGymMode] = useState(false);
  const [useLbs, setUseLbs] = useState(false);

  // ── Accordion ──
  const [expandedExercise, setExpandedExercise] = useState<string | null>(null);
  const [expandedWarmups, setExpandedWarmups] = useState<Set<string>>(new Set());
  const [cardioExpanded, setCardioExpanded] = useState(false); // collapsed by default on training days

  // ── Now Playing mode ──
  const [nowPlaying, setNowPlaying] = useState(false);
  const [currentSetIndex, setCurrentSetIndex] = useState(0);
  const [showHistory, setShowHistory] = useState(false);
  const [exerciseHistory, setExerciseHistory] = useState<StrengthEntry[]>([]);
  const [historyExercise, setHistoryExercise] = useState<string>("");
  const [pendingAdvance, setPendingAdvance] = useState(false);

  // ── Finish Session modal ──
  const [showFinishModal, setShowFinishModal] = useState(false);
  const [finishing, setFinishing] = useState(false);

  // ── Auto-save: debounced PATCH for input changes ──
  const debounceTimers = useRef<Record<string, ReturnType<typeof setTimeout>>>({});
  const patchInFlight = useRef<Set<string>>(new Set());

  const patchSet = useCallback(async (setId: string, data: { reps: string; weight: string; rpe: string }) => {
    if (!session || patchInFlight.current.has(setId)) return;
    patchInFlight.current.add(setId);
    try {
      const setObj = session.sets.find(s => s.id === setId);
      const exName = setObj?.exercise_name || "";
      const isTaken = machineTaken.has(exName);
      const altName = isTaken ? altLog[exName]?.name : undefined;

      await api.patch(`/engine2/session/${session.id}/set/${setId}`, {
        actual_reps: data.reps ? parseInt(data.reps) : null,
        actual_weight_kg: data.weight ? parseFloat(data.weight) / (useLbs ? 2.20462 : 1) : null,
        rpe: data.rpe ? parseFloat(data.rpe) : null,
        actual_exercise_name: altName || undefined,
      });
    } catch {
      // Silent fail — data is still in localStorage as fallback
    } finally {
      patchInFlight.current.delete(setId);
    }
  }, [session, machineTaken, altLog, useLbs]);

  const debouncedPatchSet = useCallback((setId: string, data: { reps: string; weight: string; rpe: string }) => {
    if (debounceTimers.current[setId]) clearTimeout(debounceTimers.current[setId]);
    debounceTimers.current[setId] = setTimeout(() => {
      patchSet(setId, data);
    }, 1500);
  }, [patchSet]);

  const today = (() => {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  })();

  // Auto-save workout progress to localStorage (survives logout/phone-off)
  // BUG-05 fix: include session_id so restore validates against correct session
  useEffect(() => {
    if (Object.keys(completedSets).length > 0 && session) {
      localStorage.setItem("cpos_workout_completed", JSON.stringify({ _date: today, _session_id: session.id, ...completedSets }));
    }
  }, [completedSets, today, session]);

  useEffect(() => {
    if (Object.keys(sets).length > 0 && session) {
      localStorage.setItem("cpos_workout_sets", JSON.stringify({ _date: today, _session_id: session.id, ...sets }));
    }
  }, [sets, today, session]);

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
      api.get<typeof cardioPrescription>("/engine3/cardio/prescription").then(rx => {
        if (rx) {
          setCardioPrescription(rx);
          setCardioDuration(String(rx.cardio?.duration_min || 30));
          setCardioFasted(rx.cardio?.fasted ?? true);
        }
      }).catch(() => {});
      // Pre-workout readiness: latest ARI zone + recommendation
      api.get<{
        ari_score: number;
        zone: "green" | "yellow" | "red";
        components?: Record<string, number>;
        recommendation?: string;
      }>("/engine2/ari")
        .then(setReadiness)
        .catch(() => setReadiness(null));
      // BUG-03 fix: check if cardio already logged today (localStorage-based)
      try {
        const lastCardio = localStorage.getItem("cpos_cardio_logged_date");
        if (lastCardio === new Date().toISOString().split("T")[0]) setCardioLogged(true);
      } catch { /* ignore */ }
      // Reset session state before fetching new date
      setSession(null);
      setSets({});
      setPreviousSets({});
      setExpandedExercise(null);
      setNowPlaying(false);
      setShowFinishModal(false);

      api.get<TrainingSession>(`/engine2/session/${viewDate}`)
        .then((s) => {
          setSession(s);
          const lbs = localStorage.getItem("useLbs") === "true";
          const m = lbs ? 2.20462 : 1;

          const initial: Record<string, { reps: string; weight: string; rpe: string }> = {};
          const prevData: Record<string, { reps: number; weight: number }> = {};
          // Fix 1.6: Derive completion state from server actual_* values
          const serverCompleted: Record<string, { reps: string; weight: string; rpe: string }> = {};
          s.sets.forEach((set) => {
            let weightStr = "";
            if (set.actual_weight_kg) weightStr = (set.actual_weight_kg * m).toFixed(1);
            else if (set.prescribed_weight_kg) weightStr = (set.prescribed_weight_kg * m).toFixed(1);

            initial[set.id] = {
              reps: set.actual_reps?.toString() || set.prescribed_reps.toString(),
              weight: weightStr,
              rpe: set.rpe?.toString() || "",
            };
            // If server has actual values, this set is completed
            if (set.actual_reps != null && set.actual_weight_kg != null && !set.is_warmup) {
              serverCompleted[set.id] = initial[set.id];
            }
            if (set.last_actual_reps != null && set.last_actual_weight_kg != null) {
              prevData[set.id] = { reps: set.last_actual_reps, weight: Number((set.last_actual_weight_kg * m).toFixed(1)) };
            }
          });
          // Merge with any in-progress data saved to localStorage
          // BUG-05 fix: validate session_id matches before restoring
          try {
            const savedSets = localStorage.getItem("cpos_workout_sets");
            if (savedSets) {
              const parsed = JSON.parse(savedSets);
              if (parsed._date === viewDate && parsed._session_id === s.id) {
                const { _date, _session_id, ...restored } = parsed;
                for (const [id, data] of Object.entries(restored)) {
                  if (initial[id]) {
                    initial[id] = data as { reps: string; weight: string; rpe: string };
                  }
                }
              }
            }
          } catch { /* ignore */ }

          // Restore completed sets from localStorage OR derive from server
          let restoredCompleted: Record<string, { reps: string; weight: string; rpe: string }> = {};
          try {
            const savedCompleted = localStorage.getItem("cpos_workout_completed");
            if (savedCompleted) {
              const parsed = JSON.parse(savedCompleted);
              if (parsed._date === viewDate && parsed._session_id === s.id) {
                const { _date, _session_id, ...rest } = parsed;
                restoredCompleted = rest;
              }
            }
          } catch { /* ignore */ }
          // Merge: server-completed sets always take precedence
          setCompletedSets({ ...restoredCompleted, ...serverCompleted });

          setSets(initial);
          setPreviousSets(prevData);

          const firstEx = s.sets.find((st) => !st.is_warmup);
          if (firstEx) setExpandedExercise(firstEx.exercise_name);
        })
        .catch(() => {
          setSession(null);
          setCompletedSets({});
        });
    }
  }, [user, loading, router, viewDate, today]);

  // ── Rest timer countdown ──
  useEffect(() => {
    if (!restTimer.active || restTimer.seconds <= 0) return;
    const interval = setInterval(() => {
      setRestTimer((prev) => {
        if (prev.seconds <= 1) {
          clearInterval(interval);
          // Rest timer alert: vibrate + audio beep
          try {
            if (navigator.vibrate) navigator.vibrate([200, 100, 200]);
            const ctx = new (window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext)();
            const osc = ctx.createOscillator();
            osc.type = "sine";
            osc.frequency.value = 880;
            osc.connect(ctx.destination);
            osc.start();
            osc.stop(ctx.currentTime + 0.15);
          } catch { /* audio not available */ }
          setTimeout(() => setRestTimer({ active: false, seconds: 0, isCompound: true, isFst7: false }), 3000);
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
    const group = exerciseGroups.find(g => g.name === exerciseName);
    if (!group) return exerciseGroups.length > 0 && exerciseGroups[0].name === exerciseName;
    const firstSet = group.workingSets[0] || group.warmupSets[0];
    if (!firstSet?.movement_pattern) return exerciseGroups[0]?.name === exerciseName;
    const compoundPatterns = new Set(["push", "pull", "squat", "hinge", "lunge", "carry"]);
    return compoundPatterns.has(firstSet.movement_pattern.toLowerCase());
  };

  // ── Handlers ──

  const logSet = (setId: string, field: string, value: string) => {
    setSets((prev) => {
      const updated = { ...prev, [setId]: { ...prev[setId], [field]: value } };
      // Fire debounced auto-save PATCH (1.5s idle)
      if (isToday && session) debouncedPatchSet(setId, updated[setId]);
      return updated;
    });
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
      // Fire immediate PATCH on set completion
      if (isToday) patchSet(set.id, data);
      const compound = isCompoundExercise(set.exercise_name);
      const restSec = set.rest_seconds ?? (compound ? 180 : 90);
      setRestTimer({ active: true, seconds: restSec, isCompound: compound, isFst7: !!set.is_fst7 });
    }
  };

  const dismissTimer = () => {
    setRestTimer({ active: false, seconds: 0, isCompound: true, isFst7: false });
    if (pendingAdvance) {
      setPendingAdvance(false);
      // Auto-advance to next INCOMPLETE set in Now Playing mode. The previous
      // logic had a dead loop that returned on the first iteration, so the
      // pointer never skipped past already-logged sets.
      setCurrentSetIndex((prev) => {
        for (let i = prev + 1; i < allWorkingSets.length; i++) {
          if (!completedSets[allWorkingSets[i].id]) return i;
        }
        // No incomplete sets remaining — stay on current (user can finish).
        return prev;
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
    if (allWorkingSets.length === 0) return;  // BUG-A4 guard
    setCurrentSetIndex(findFirstIncomplete());
    setNowPlaying(true);
    setShowHistory(false);
    // Track session duration — set started_at on backend
    if (session && isToday) {
      api.post(`/engine2/session/${session.id}/start`).catch(() => {});
    }
  };

  const markSetDoneNowPlaying = (set: TrainingSet) => {
    const data = sets[set.id] || { reps: "", weight: "", rpe: "" };
    setCompletedSets((p) => ({ ...p, [set.id]: data }));
    // Fire immediate PATCH on set completion
    if (isToday) patchSet(set.id, data);
    const compound = isCompoundExercise(set.exercise_name);
    const restSec = set.rest_seconds ?? (compound ? 180 : 90);
    setRestTimer({ active: true, seconds: restSec, isCompound: compound, isFst7: !!set.is_fst7 });
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
    } catch {
      showToast("Failed to log strength test", "error");
    } finally { setSLogging(false); }
  };

  const generateProgram = async () => {
    setGenerating(true);
    try {
      const p = await api.post<Program & { sessions_created: number; message: string }>("/engine2/program/generate");
      setProgram(p);
    } catch {
      showToast("Failed to generate program", "error");
    } finally { setGenerating(false); }
  };

  const finishSession = async () => {
    if (!session) return;
    setFinishing(true);
    try {
      // Flush any pending debounced PATCHes before finishing
      for (const [setId, timer] of Object.entries(debounceTimers.current)) {
        clearTimeout(timer);
        const data = sets[setId];
        if (data) await patchSet(setId, data);
      }
      debounceTimers.current = {};

      const result = await api.post<FinishSessionResponse>(
        `/engine2/session/${session.id}/finish`,
        { notes: sessionNotes || undefined }
      );
      setProgressions(result.progressions || []);
      // V3.P7 — PR celebration. Every session with progressions gets a
      // prominent success toast; users kept missing the quiet card below.
      if ((result.progressions ?? []).length > 0) {
        const lifts = (result.progressions ?? []).map(p => p.exercise).slice(0, 3).join(", ");
        const extra = (result.progressions ?? []).length > 3 ? ` +${(result.progressions ?? []).length - 3} more` : "";
        showToast(`🏆 Progression unlocked: ${lifts}${extra}`, "success");
      }
      // BUG-F1: update local session state so completed badge shows + sticky
      // bar and start button hide immediately. Also stash summary stats from
      // the finish response for the SessionSummary component.
      const completedAt = new Date().toISOString();
      setSession((prev) => prev ? { ...prev, completed: true, completed_at: completedAt } : prev);
      setSessionSummary({
        duration_seconds: result.session_duration_seconds ?? null,
        total_volume_kg: result.total_volume_kg ?? null,
        sets_completed: result.sets_completed ?? completedCount,
        sets_total: result.sets_total ?? totalCount,
        muscles_trained: result.muscles_trained ?? [],
        progressions: result.progressions ?? [],
      });
      setShowSummary(true);
      setShowFinishModal(false);
      // Clear localStorage after successful finish — workout is persisted to server
      localStorage.removeItem("cpos_workout_completed");
      localStorage.removeItem("cpos_workout_sets");
    } catch {
      showToast("Failed to finish session", "error");
    } finally { setFinishing(false); }
  };

  const submitSubjectiveFeedback = async (
    pump: number,
    difficulty: number,
    comfort: number,
  ) => {
    if (!session) return;
    try {
      await api.patch(`/engine2/session/${session.id}/feedback`, {
        pump_quality: pump,
        session_difficulty: difficulty,
        joint_comfort: comfort,
      });
      setSession((prev) => prev ? {
        ...prev,
        pump_quality: pump,
        session_difficulty: difficulty,
        joint_comfort: comfort,
      } : prev);
      showToast("Feedback saved", "success");
    } catch {
      showToast("Couldn't save feedback", "error");
    }
  };

  // Legacy save handler — kept for backwards compat with the "Save Progress" flow
  // Now just PATCHes all sets in bulk and does NOT mark session complete
  const saveSession = async () => {
    if (!session) return;
    setSaving(true);
    try {
      const setEntries = Object.entries(sets);
      await Promise.all(
        setEntries.map(([id, data]) => patchSet(id, data))
      );
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch {
      showToast("Failed to save workout session", "error");
    } finally { setSaving(false); }
  };

  // ── Helpers ──

  const exerciseCompletedCount = (exName: string) => {
    const group = exerciseGroups.find((g) => g.name === exName);
    if (!group) return 0;
    return group.workingSets.filter((s) => completedSets[s.id]).length;
  };

  const logCardioSession = async () => {
    setCardioLogging(true);
    try {
      const payload: Record<string, unknown> = {
        activity_type: cardioMachine,
        duration_min: parseInt(cardioDuration) || 30,
        intensity: "low",
        recorded_date: new Date().toISOString().split("T")[0],
        fasted: cardioFasted,
      };
      if (cardioMachine === "treadmill") {
        payload.speed_mph = parseFloat(cardioSpeed) || 3.0;
        payload.incline_pct = parseInt(cardioIncline) || 12;
      } else if (cardioMachine === "stairmaster") {
        payload.stair_level = parseInt(cardioStairLevel) || 6;
      } else if (cardioMachine === "stationary_bike") {
        payload.resistance_level = parseInt(cardioBikeResistance) || 10;
        payload.rpm = parseInt(cardioBikeRpm) || 80;
      } else if (cardioMachine === "elliptical") {
        payload.resistance_level = parseInt(cardioEllipticalResistance) || 8;
        payload.incline_pct = parseInt(cardioEllipticalIncline) || 6;
      } else if (cardioMachine === "rowing") {
        payload.damper = parseInt(cardioRowerDamper) || 5;
        payload.pace_500m = cardioRowerPace || "2:15";
      }
      await api.post("/engine3/cardio/log", payload);
      setCardioLogged(true);
      localStorage.setItem("cpos_cardio_logged_date", new Date().toISOString().split("T")[0]);
    } catch {
      showToast("Failed to log cardio", "error");
    } finally {
      setCardioLogging(false);
    }
  };

  // Estimate calorie burn
  const estCardioBurn = (() => {
    const dur = parseInt(cardioDuration) || 30;
    const basePerMin = cardioMachine === "stairmaster" ? 8.5
      : cardioMachine === "treadmill" ? (parseFloat(cardioSpeed) >= 4.0 ? 8 : 6.5)
      : 7;
    return Math.round(dur * basePerMin);
  })();

  // ── Render ──
  return (
    <div className="min-h-screen">
      <NavBar username={user.username} onLogout={() => { logout(); router.push("/"); }} />

      <main className="px-3 py-4 pb-24">
        <div className="max-w-lg mx-auto space-y-4">

          {/* Header — title on its own row, toolbar (day nav + unit toggles)
              on a second row so the Contrail title has breathing room. */}
          <div className="space-y-3 mb-4">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0 flex-1">
                <PageTitle
                  text="Training"
                  subtitle={
                    program ? (
                      <span className="truncate">
                        {program.name} — Wk {program.current_week}/{program.mesocycle_weeks} · {program.split_type} · {program.days_per_week}d/wk
                      </span>
                    ) : (
                      <span>No active program</span>
                    )
                  }
                  className="mb-0"
                />
              </div>
            </div>
            {/* Toolbar row — day nav on the left, unit + gym-mode toggles on the right */}
            <div className="flex items-center justify-between gap-2 flex-wrap">
              <div className="flex items-center gap-1">
                <button
                  onClick={() => setViewOffset((o) => o - 1)}
                  className="w-7 h-7 rounded-lg bg-white border border-viltrum-ash text-viltrum-iron hover:text-viltrum-obsidian hover:border-viltrum-obsidian flex items-center justify-center text-sm transition-colors"
                  aria-label="Previous day"
                >
                  ‹
                </button>
                <button
                  onClick={() => setViewOffset(0)}
                  className={`px-2 h-7 rounded-lg text-[11px] font-medium transition-colors ${
                    isToday
                      ? "bg-viltrum-blush text-viltrum-centurion border border-viltrum-legion/30"
                      : "bg-white border border-viltrum-ash text-viltrum-iron hover:text-viltrum-obsidian hover:border-viltrum-obsidian"
                  }`}
                >
                  {viewLabel}
                </button>
                <button
                  onClick={() => setViewOffset((o) => o + 1)}
                  className="w-7 h-7 rounded-lg bg-white border border-viltrum-ash text-viltrum-iron hover:text-viltrum-obsidian hover:border-viltrum-obsidian flex items-center justify-center text-sm transition-colors"
                  aria-label="Next day"
                >
                  ›
                </button>
              </div>
              <div className="flex items-center gap-1.5 flex-shrink-0">
                <button
                  onClick={toggleUnit}
                  className={`px-2 h-8 rounded-lg flex items-center justify-center text-[10px] font-bold transition-colors ${
                    useLbs
                      ? "bg-viltrum-obsidian text-white"
                      : "bg-white border border-viltrum-ash text-viltrum-iron hover:border-viltrum-obsidian"
                  }`}
                >
                  {useLbs ? "LBS" : "KG"}
                </button>
                <button
                  onClick={toggleGymMode}
                  className={`px-2 h-8 rounded-lg flex items-center justify-center text-[10px] font-bold tracking-wide transition-colors ${
                    gymMode
                      ? "bg-viltrum-obsidian text-white"
                      : "bg-white border border-viltrum-ash text-viltrum-iron hover:border-viltrum-obsidian"
                  }`}
                >
                  {gymMode ? "GYM ✓" : "GYM"}
                </button>
              </div>
            </div>
          </div>

          {/* ── Cardio Prescription + Logger (collapsed by default on training days) ── */}
          {isToday && cardioPrescription && (
            <div className="card">
              <button
                onClick={() => setCardioExpanded(!cardioExpanded)}
                className="w-full flex items-center justify-between"
              >
                <h2 className="text-sm font-bold text-jungle-text uppercase tracking-wide">
                  Cardio {cardioLogged && <span className="text-green-400 text-xs ml-1">Done</span>}
                </h2>
                <div className="flex items-center gap-2">
                  <span className="text-[9px] px-2 py-0.5 rounded bg-jungle-accent/15 text-jungle-accent font-medium">
                    {cardioPrescription.cardio.sessions_per_week}x/week • {cardioPrescription.cardio.duration_min}min
                  </span>
                  {cardioPrescription.cardio.fasted && (
                    <span className="text-[9px] px-2 py-0.5 rounded bg-blue-500/15 text-blue-400 font-medium">Fasted AM</span>
                  )}
                  <svg className={`w-4 h-4 text-jungle-dim transition-transform ${cardioExpanded ? "rotate-180" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </div>
              </button>

              {cardioExpanded && (<div className="space-y-3 mt-3">
              {/* Prescription notes */}
              {cardioPrescription.cardio.notes.length > 0 && (
                <div className="space-y-1">
                  {cardioPrescription.cardio.notes.slice(0, 2).map((note, i) => (
                    <p key={i} className="text-[10px] text-jungle-dim leading-relaxed">{note}</p>
                  ))}
                </div>
              )}

              {/* NEAT / Steps */}
              <div className="flex items-center justify-between bg-jungle-deeper rounded-lg px-3 py-2">
                <div>
                  <p className="text-[9px] text-jungle-dim uppercase tracking-wider">Daily Steps</p>
                  <p className="text-lg font-bold text-jungle-accent">{cardioPrescription.neat.step_target.toLocaleString()}</p>
                </div>
                <div className="text-right">
                  <p className="text-[9px] text-jungle-dim uppercase tracking-wider">Weekly Burn</p>
                  <p className="text-sm font-semibold text-jungle-muted">{cardioPrescription.summary.total_weekly_expenditure_kcal.toLocaleString()} kcal</p>
                </div>
              </div>

              {/* Logger */}
              {cardioLogged ? (
                <div className="text-center py-2">
                  <p className="text-xs text-green-400 font-medium">Cardio logged for today</p>
                </div>
              ) : (
                <div className="space-y-2 border-t border-jungle-border pt-3">
                  <div className="grid grid-cols-2 gap-2">
                    {/* Machine selector */}
                    <div>
                      <label className="text-[9px] text-jungle-dim uppercase">Machine</label>
                      <select value={cardioMachine} onChange={e => setCardioMachine(e.target.value)}
                        className="input-field mt-0.5 text-xs">
                        <option value="treadmill">Treadmill</option>
                        <option value="stairmaster">StairMaster</option>
                        <option value="stationary_bike">Stationary Bike</option>
                        <option value="elliptical">Elliptical</option>
                        <option value="rowing">Rowing Machine</option>
                      </select>
                    </div>
                    {/* Duration */}
                    <div>
                      <label className="text-[9px] text-jungle-dim uppercase">Duration (min)</label>
                      <input type="number" value={cardioDuration}
                        onChange={e => setCardioDuration(e.target.value)}
                        className="input-field mt-0.5 text-xs" />
                    </div>
                  </div>

                  {/* Treadmill-specific controls */}
                  {cardioMachine === "treadmill" && (
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label className="text-[9px] text-jungle-dim uppercase">Speed (mph)</label>
                        <select value={cardioSpeed} onChange={e => setCardioSpeed(e.target.value)}
                          className="input-field mt-0.5 text-xs">
                          <option value="2.5">2.5 — Slow walk</option>
                          <option value="3.0">3.0 — Walk</option>
                          <option value="3.3">3.3 — Brisk walk</option>
                          <option value="3.5">3.5 — Power walk</option>
                          <option value="3.8">3.8 — Fast walk</option>
                          <option value="4.0">4.0 — Walk/jog</option>
                          <option value="4.3">4.3 — Light jog</option>
                          <option value="5.0">5.0 — Jog</option>
                          <option value="6.0">6.0 — Run</option>
                        </select>
                      </div>
                      <div>
                        <label className="text-[9px] text-jungle-dim uppercase">Incline (%)</label>
                        <select value={cardioIncline} onChange={e => setCardioIncline(e.target.value)}
                          className="input-field mt-0.5 text-xs">
                          <option value="0">0% — Flat</option>
                          <option value="3">3%</option>
                          <option value="6">6%</option>
                          <option value="8">8%</option>
                          <option value="10">10%</option>
                          <option value="12">12% — Standard LISS</option>
                          <option value="15">15% — Steep</option>
                        </select>
                      </div>
                    </div>
                  )}

                  {/* StairMaster-specific controls */}
                  {cardioMachine === "stairmaster" && (
                    <div>
                      <label className="text-[9px] text-jungle-dim uppercase">Level / Speed</label>
                      <select value={cardioStairLevel} onChange={e => setCardioStairLevel(e.target.value)}
                        className="input-field mt-0.5 text-xs">
                        <option value="3">Level 3 — Easy</option>
                        <option value="4">Level 4 — Light</option>
                        <option value="5">Level 5 — Moderate</option>
                        <option value="6">Level 6 — Standard LISS</option>
                        <option value="7">Level 7 — Brisk</option>
                        <option value="8">Level 8 — Hard</option>
                        <option value="9">Level 9 — Very hard</option>
                        <option value="10">Level 10 — Max</option>
                      </select>
                    </div>
                  )}

                  {/* Stationary bike controls */}
                  {cardioMachine === "stationary_bike" && (
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label className="text-[9px] text-jungle-dim uppercase">Resistance</label>
                        <select
                          value={cardioBikeResistance}
                          onChange={e => setCardioBikeResistance(e.target.value)}
                          className="input-field mt-0.5 text-xs"
                        >
                          {[3, 5, 7, 9, 10, 12, 14, 16, 18, 20].map(level => (
                            <option key={level} value={String(level)}>
                              Level {level}{level === 10 ? " — Zone 2" : level >= 16 ? " — Hard" : ""}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <label className="text-[9px] text-jungle-dim uppercase">Cadence (RPM)</label>
                        <input
                          type="number"
                          value={cardioBikeRpm}
                          onChange={e => setCardioBikeRpm(e.target.value)}
                          placeholder="80"
                          className="input-field mt-0.5 text-xs"
                        />
                      </div>
                    </div>
                  )}

                  {/* Elliptical controls */}
                  {cardioMachine === "elliptical" && (
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label className="text-[9px] text-jungle-dim uppercase">Resistance</label>
                        <select
                          value={cardioEllipticalResistance}
                          onChange={e => setCardioEllipticalResistance(e.target.value)}
                          className="input-field mt-0.5 text-xs"
                        >
                          {[3, 5, 7, 8, 10, 12, 14, 16, 18, 20].map(level => (
                            <option key={level} value={String(level)}>
                              Level {level}{level === 8 ? " — Standard" : ""}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <label className="text-[9px] text-jungle-dim uppercase">Incline / Ramp</label>
                        <select
                          value={cardioEllipticalIncline}
                          onChange={e => setCardioEllipticalIncline(e.target.value)}
                          className="input-field mt-0.5 text-xs"
                        >
                          {[0, 3, 6, 9, 12, 15, 18, 20].map(inc => (
                            <option key={inc} value={String(inc)}>
                              {inc}%
                            </option>
                          ))}
                        </select>
                      </div>
                    </div>
                  )}

                  {/* Rowing machine controls */}
                  {cardioMachine === "rowing" && (
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label className="text-[9px] text-jungle-dim uppercase">Damper</label>
                        <select
                          value={cardioRowerDamper}
                          onChange={e => setCardioRowerDamper(e.target.value)}
                          className="input-field mt-0.5 text-xs"
                        >
                          {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map(d => (
                            <option key={d} value={String(d)}>
                              {d}{d === 5 ? " — Standard" : d >= 8 ? " — Heavy" : ""}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <label className="text-[9px] text-jungle-dim uppercase">Pace /500m</label>
                        <input
                          type="text"
                          value={cardioRowerPace}
                          onChange={e => setCardioRowerPace(e.target.value)}
                          placeholder="2:15"
                          className="input-field mt-0.5 text-xs"
                        />
                      </div>
                    </div>
                  )}

                  {/* Fasted toggle + log button */}
                  <div className="flex items-center justify-between pt-1">
                    <div className="flex items-center gap-2">
                      <button type="button" onClick={() => setCardioFasted(!cardioFasted)}
                        className={`w-9 h-5 rounded-full transition-colors ${cardioFasted ? "bg-blue-500" : "bg-jungle-border"}`}>
                        <div className={`w-4 h-4 rounded-full bg-white shadow transition-transform ${cardioFasted ? "translate-x-4" : "translate-x-0.5"}`} />
                      </button>
                      <span className="text-[10px] text-jungle-muted">Fasted</span>
                      <span className="text-[10px] text-jungle-dim ml-2">Est. {estCardioBurn} kcal</span>
                    </div>
                    <button onClick={logCardioSession} disabled={cardioLogging}
                      className="btn-primary text-xs px-4 py-1.5 disabled:opacity-50">
                      {cardioLogging ? "Logging..." : "Log Cardio"}
                    </button>
                  </div>
                </div>
              )}
              </div>)}
            </div>
          )}

          {/* Read-only banner for non-today views */}
          {!isToday && session && (
            <div className="bg-jungle-accent/10 border border-jungle-accent/20 rounded-xl px-4 py-2 text-center">
              <p className="text-jungle-accent text-xs font-medium">Viewing {viewLabel}&apos;s workout — read only</p>
            </div>
          )}

          {/* No program */}
          {!program && (
            <div className="card text-center py-12 space-y-4">
              <div className="mx-auto w-14 h-14 rounded-full bg-blush flex items-center justify-center">
                <svg className="w-6 h-6 text-legion" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 4v16M4 12h16" />
                </svg>
              </div>
              <div className="space-y-1.5">
                <p className="h-display-sm">No active program</p>
                <p className="body-serif-sm italic text-iron max-w-md mx-auto">
                  Generate your first program and the three engines come online — training, nutrition, and physique scoring.
                </p>
              </div>
              <button
                onClick={generateProgram}
                disabled={generating}
                className="btn-accent disabled:opacity-60 inline-flex items-center justify-center gap-2"
              >
                {generating ? (
                  <>
                    <ViltrumLoader variant="compact" label="Generating your program" />
                    <span>Generating…</span>
                  </>
                ) : "Generate Program"}
              </button>
            </div>
          )}

          {/* No session today — Rest Day */}
          {program && !session && (
            <div className="card text-center py-12 space-y-3">
              <div className="mx-auto w-14 h-14 rounded-full bg-alabaster border border-ash flex items-center justify-center">
                <svg className="w-6 h-6 text-iron" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 12.5A9 9 0 0111.5 3a7 7 0 109.5 9.5z" />
                </svg>
              </div>
              <div className="space-y-1.5">
                <p className="h-display-sm">Rest Day</p>
                <p className="body-serif-sm italic text-iron max-w-md mx-auto">
                  No session scheduled — recovery is the work today. Tomorrow&apos;s split is queued and waiting.
                </p>
              </div>
            </div>
          )}

          {/* Pre-workout readiness banner — only on today's session */}
          {session && isToday && readiness && (
            <div
              className={`card py-3 border-l-4 ${
                readiness.zone === "green"
                  ? "border-green-500/70"
                  : readiness.zone === "yellow"
                    ? "border-yellow-500/70"
                    : "border-red-500/80"
              }`}
            >
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-3 min-w-0">
                  <div
                    className={`w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold ${
                      readiness.zone === "green"
                        ? "bg-green-500/20 text-green-400"
                        : readiness.zone === "yellow"
                          ? "bg-yellow-500/20 text-yellow-400"
                          : "bg-red-500/20 text-red-400"
                    }`}
                  >
                    {Math.round(readiness.ari_score)}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-[10px] text-jungle-dim uppercase tracking-wider">
                      Readiness · {readiness.zone}
                    </p>
                    <p className="text-xs text-jungle-text leading-tight">
                      {readiness.recommendation || "Log today's check-in for a readiness score."}
                    </p>
                  </div>
                </div>
                {readiness.zone !== "red" && (
                  <a
                    href="/checkin"
                    className="text-[10px] text-jungle-accent whitespace-nowrap hover:underline"
                  >
                    Update
                  </a>
                )}
              </div>
            </div>
          )}

          {/* Session */}
          {session && (
            <>
              {/* Session info bar */}
              <div className={`card py-3 ${gymMode ? "gym-mode" : ""}`}>
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-3 min-w-0">
                    <SessionProgressRing completed={completedCount} total={totalCount} size={gymMode ? 56 : 48} />
                    <div className="min-w-0">
                      <h2 className="font-semibold capitalize text-base truncate">
                        {session.session_type.replace(/_/g, " ")} Day
                      </h2>
                      <p className="text-jungle-dim text-[11px]">
                        Wk {session.week_number} · {completedCount}/{totalCount} sets
                        {session.estimated_duration_min ? ` · ~${session.estimated_duration_min} min` : ""}
                      </p>
                      {session.workout_window?.start_time && session.workout_window?.end_time && (
                        <p className="text-[11px] text-jungle-accent font-mono mt-0.5">
                          {session.workout_window.start_time}
                          <span className="text-jungle-dim mx-1">→</span>
                          {session.workout_window.end_time}
                          <span className="text-jungle-dim ml-1.5 text-[9px]">
                            ({session.workout_window.anchor_mode === "end" ? "end anchored" : "start anchored"})
                          </span>
                        </p>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    {isToday && !session.completed && totalCount > 0 && (
                      <button
                        onClick={nowPlaying ? () => setNowPlaying(false) : startNowPlaying}
                        className={`px-4 py-2 rounded-xl text-sm font-bold transition-all ${
                          nowPlaying
                            ? "bg-jungle-deeper border border-jungle-border text-jungle-dim"
                            : "bg-jungle-accent text-white hover:bg-jungle-accent-hover active:scale-95"
                        }`}
                      >
                        {nowPlaying ? "Overview" : "▶ Start"}
                      </button>
                    )}
                    {session.completed && (
                      <span className="px-3 py-1.5 rounded-xl text-xs font-bold bg-green-500/20 text-green-400">
                        Complete
                      </span>
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
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-[10px] text-jungle-dim uppercase tracking-wide">Target:</span>
                          <span className="text-sm font-semibold text-jungle-muted">
                            {useLbs ? (currentSet.prescribed_weight_kg * 2.20462).toFixed(1) : currentSet.prescribed_weight_kg.toFixed(1)} {unit} × {currentSet.prescribed_reps}
                          </span>
                          {currentSet.prescribed_rir !== null && currentSet.prescribed_rir !== undefined && (
                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-jungle-accent/10 text-jungle-accent font-semibold">
                              @ RIR {currentSet.prescribed_rir} · RPE {currentSet.prescribed_rpe}
                            </span>
                          )}
                          {currentSet.tempo && (
                            <span className="text-[10px] text-jungle-dim font-mono">
                              tempo {currentSet.tempo}
                            </span>
                          )}
                          {prev && (
                            <span className="text-[10px] text-jungle-dim ml-auto">
                              Last: {prev.weight}{unit} × {prev.reps}
                            </span>
                          )}
                        </div>
                      )}

                      {/* Intensification technique cue */}
                      {currentSet.technique_cue && (
                        <div className="rounded-lg bg-red-500/10 border border-red-500/30 px-3 py-2">
                          <p className="text-[10px] text-red-400 uppercase tracking-wider font-bold mb-0.5">
                            {currentSet.set_technique?.replace(/_/g, " ")} — last set
                          </p>
                          <p className="text-[11px] text-jungle-text leading-tight">
                            {currentSet.technique_cue}
                          </p>
                        </div>
                      )}

                      {/* Inputs — large tap targets for gym use */}
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
                            disabled={!isToday}
                            className="input-field text-lg py-3.5 text-center font-bold disabled:opacity-50"
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
                            disabled={!isToday}
                            className="input-field text-lg py-3.5 text-center font-bold disabled:opacity-50"
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
                            disabled={!isToday}
                            className={`${rpeClass(sets[currentSet.id]?.rpe || "")} text-lg py-3.5 text-center font-bold disabled:opacity-50`}
                            placeholder="RPE"
                          />
                          {/* RIR indicator */}
                          {sets[currentSet.id]?.rpe && parseFloat(sets[currentSet.id].rpe) > 0 && (
                            <p className="text-[9px] text-jungle-dim text-center mt-1">
                              RIR: {Math.max(0, 10 - parseFloat(sets[currentSet.id].rpe)).toFixed(0)}
                            </p>
                          )}
                        </div>
                      </div>

                      {/* Plates link */}
                      {/* Plate loading visual */}
                      {currentWeight && currentSet.equipment && (
                        <div className="flex flex-col items-center gap-1">
                          <PlateLoadingSVG
                            targetWeight={parseFloat(currentWeight) || 0}
                            equipment={currentSet.equipment}
                            useLbs={useLbs}
                          />
                          {isBarbell && (
                            <button
                              onClick={() => setPlateCalc({ open: true, weight: parseFloat(currentWeight) || 0 })}
                              className="text-[10px] text-jungle-dim hover:text-jungle-accent transition-colors"
                            >
                              Expand calculator
                            </button>
                          )}
                        </div>
                      )}

                      {/* Set Done button — extra large for gym use */}
                      <button
                        onClick={() => isCompleted ? markSetDone(currentSet) : markSetDoneNowPlaying(currentSet)}
                        className={`set-done-btn w-full py-5 rounded-2xl text-lg font-bold transition-all ${
                          isCompleted
                            ? "bg-green-500/20 text-green-400 border-2 border-green-500/30 active:scale-95"
                            : "bg-jungle-accent text-white hover:bg-jungle-accent-hover active:scale-[0.97] shadow-lg shadow-jungle-accent/20"
                        }`}
                      >
                        {isCompleted ? "✓ Done — Tap to Undo" : "Log Set ▶"}
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
                  const hasFst7 = workingSets.some(s => s.is_fst7);

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
                              {hasFst7 && (
                                <span className="ml-2 inline-block text-[9px] font-bold bg-purple-500/20 text-purple-300 border border-purple-500/30 px-1.5 py-0.5 rounded-full uppercase tracking-wider align-middle">
                                  FST-7
                                </span>
                              )}
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
                          {/* Machine taken + swap — only when today */}
                          {isToday && (
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
                              {(() => {
                                const exId = workingSets[0]?.exercise_id || warmupSets[0]?.exercise_id;
                                if (!exId) return null;
                                return (
                                  <button
                                    onClick={() => setSwapTarget({
                                      exerciseId: exId,
                                      exerciseName: name,
                                      primaryMuscle: muscle,
                                    })}
                                    className="text-[10px] px-2.5 py-1 rounded-lg border border-jungle-border text-jungle-dim hover:border-jungle-accent/50 hover:text-jungle-accent transition-colors"
                                  >
                                    ⇄ Swap
                                  </button>
                                );
                              })()}
                            </div>
                          )}

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
                                    <div key={ws.id} className="text-[11px] text-viltrum-iron bg-viltrum-limestone border border-viltrum-ash rounded-lg px-3 py-1 flex justify-between">
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
                                    ? "border-viltrum-laurel/30 bg-viltrum-laurel-bg"
                                    : "border-viltrum-ash bg-viltrum-limestone"
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
                                  {isToday ? (
                                    <button
                                      onClick={() => markSetDone(set)}
                                      className={`px-4 py-1.5 rounded-xl text-xs font-bold transition-all active:scale-95 ${
                                        isCompleted
                                          ? "bg-green-500/20 text-green-400 border border-green-500/30"
                                          : "bg-jungle-accent text-white hover:bg-jungle-accent-hover"
                                      }`}
                                    >
                                      {isCompleted ? "Undo" : "Done ✓"}
                                    </button>
                                  ) : (
                                    <span className="text-[10px] text-jungle-dim">Preview</span>
                                  )}
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
                                        disabled={!isToday}
                                        className="input-field text-sm py-2.5 flex-1 min-w-0 disabled:opacity-50"
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
                                      disabled={!isToday}
                                      className="input-field text-sm py-2.5 disabled:opacity-50"
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
                                      disabled={!isToday}
                                      className={`${rpeClass(sets[set.id]?.rpe || "")} disabled:opacity-50`}
                                      placeholder="RPE"
                                    />
                                    {sets[set.id]?.rpe && parseFloat(sets[set.id].rpe) > 0 && (
                                      <p className="text-[8px] text-jungle-dim text-center mt-0.5">
                                        RIR {Math.max(0, 10 - parseFloat(sets[set.id].rpe)).toFixed(0)}
                                      </p>
                                    )}
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

              {/* Progression readouts — V3.P7 prominence lift */}
              {progressions.length > 0 && (
                <div className="card border-laurel bg-viltrum-laurel-bg">
                  <div className="flex items-baseline justify-between mb-3">
                    <h3 className="h-card text-laurel flex items-center gap-2">
                      <span aria-hidden>🏆</span>
                      Progression Unlocked
                    </h3>
                    <span className="text-[10px] tracking-[0.15em] uppercase text-laurel/80">
                      Next session
                    </span>
                  </div>
                  <div className="space-y-1.5">
                    {progressions.map((p) => (
                      <div key={p.exercise} className="flex justify-between items-baseline gap-2 text-sm border-b border-laurel/15 last:border-0 pb-1.5 last:pb-0">
                        <span className="text-viltrum-obsidian text-[12px] truncate">{p.exercise}</span>
                        <div className="flex items-baseline gap-2 flex-shrink-0">
                          <span className="text-[10px] text-viltrum-pewter tabular-nums">
                            e1RM {useLbs ? (p.estimated_1rm * 2.20462).toFixed(0) : p.estimated_1rm.toFixed(1)}{unit}
                          </span>
                          <span className="text-laurel font-semibold text-[13px] tabular-nums">
                            → {useLbs ? (p.next_weight_kg * 2.20462).toFixed(1) : p.next_weight_kg}{unit} × {p.next_reps}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
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
                          <span className="text-jungle-muted">
                            {useLbs ? `${(entry.weight_kg * 2.20462).toFixed(0)}lbs` : `${entry.weight_kg}kg`} × {entry.reps}
                          </span>
                          <span className="text-jungle-accent font-bold ml-2">
                            e1RM: {useLbs ? `${(entry.estimated_1rm * 2.20462).toFixed(0)}lbs` : `${entry.estimated_1rm}kg`}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Quick links — editorial tile grid */}
          <div>
            <p className="h-section text-travertine mb-2 px-1">Explore</p>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              {[
                {
                  href: "/training/program",
                  label: "Program",
                  desc: "Mesocycle map",
                  icon: (
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" className="w-4 h-4">
                      <rect x="4" y="5" width="16" height="16" rx="1.5" />
                      <path d="M4 10h16M9 3v4M15 3v4" />
                    </svg>
                  ),
                },
                {
                  href: "/training/history",
                  label: "History",
                  desc: "Past sessions",
                  icon: (
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" className="w-4 h-4">
                      <circle cx="12" cy="12" r="9" />
                      <path d="M12 7v5l3 2" />
                    </svg>
                  ),
                },
                {
                  href: "/training/exercises",
                  label: "Exercises",
                  desc: "Movement library",
                  icon: (
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" className="w-4 h-4">
                      <path d="M4 9v6M20 9v6M7 7v10M17 7v10M7 12h10" />
                    </svg>
                  ),
                },
                {
                  href: "/training/analytics",
                  label: "Analytics",
                  desc: "Volume & 1RM",
                  icon: (
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
                      <path d="M4 20V10M10 20V4M16 20v-7M22 20H2" />
                    </svg>
                  ),
                },
              ].map(({ href, label, desc, icon }) => (
                <a
                  key={href}
                  href={href}
                  className="group card hover:border-pumice transition-colors px-3 py-3 text-left flex flex-col gap-1.5"
                >
                  <div className="flex items-center gap-2 text-iron group-hover:text-centurion transition-colors">
                    {icon}
                    <span className="h-card">{label}</span>
                  </div>
                  <span className="text-[10px] tracking-[0.1em] uppercase text-travertine">
                    {desc}
                  </span>
                </a>
              ))}
            </div>
          </div>

        </div>
      </main>

      {/* ── Sticky bottom bar: progress + save (today only, not yet completed) ── */}
      {isToday && session && !session.completed && totalCount > 0 && (
        <div className="fixed bottom-0 left-0 right-0 z-30 bg-jungle-card/95 backdrop-blur-md border-t border-jungle-border safe-bottom">
          <div className="max-w-lg mx-auto px-4 py-3 flex items-center gap-3">
            {/* Progress bar */}
            <div className="flex-1">
              <div className="h-2 bg-jungle-deeper rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-500 ${
                    allWorkingSetsComplete ? "bg-green-400" : "bg-jungle-accent"
                  }`}
                  style={{ width: `${(completedCount / totalCount) * 100}%` }}
                />
              </div>
              <p className="text-[10px] text-jungle-dim mt-0.5">
                {completedCount}/{totalCount} sets {allWorkingSetsComplete && "— all done"}
              </p>
            </div>
            {/* Finish + Save buttons. When all sets are done, one primary
                "Finish Session" button. When sets are still incomplete, show
                BOTH "Save Progress" (keep going later) AND "Finish Early"
                (wrap up the workout now, anything blank won't count). */}
            {allWorkingSetsComplete ? (
              <button
                onClick={() => setShowFinishModal(true)}
                disabled={saving || finishing || !isToday}
                className="px-6 py-2.5 rounded-xl text-sm font-bold transition-all active:scale-95 disabled:opacity-50 bg-jungle-accent text-white shadow-lg shadow-jungle-accent/20"
              >
                {saved ? "Saved ✓" : finishing ? "Finishing..." : "Finish Session"}
              </button>
            ) : (
              <div className="flex items-center gap-2">
                <button
                  onClick={saveSession}
                  disabled={saving || finishing || !isToday}
                  className="px-4 py-2.5 rounded-xl text-xs font-semibold transition-all active:scale-95 disabled:opacity-50 bg-jungle-deeper border border-jungle-border text-jungle-muted hover:border-jungle-accent"
                >
                  {saved ? "Saved ✓" : saving ? "Saving..." : "Save"}
                </button>
                <button
                  onClick={() => setShowFinishModal(true)}
                  disabled={saving || finishing || !isToday || completedCount === 0}
                  className="px-4 py-2.5 rounded-xl text-xs font-bold transition-all active:scale-95 disabled:opacity-40 bg-jungle-accent/20 border border-jungle-accent/60 text-jungle-accent hover:bg-jungle-accent hover:text-white"
                  title={completedCount === 0 ? "Log at least one set before finishing" : "End the session now — unlogged sets won't count"}
                >
                  {finishing ? "Finishing..." : "Finish Early"}
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Finish Session Confirmation Modal */}
      {showFinishModal && (
        <div className="fixed inset-0 bg-viltrum-obsidian/45 backdrop-blur-sm z-[60] flex items-center justify-center p-4">
          <div className="bg-jungle-card border border-jungle-border rounded-2xl p-6 max-w-sm w-full">
            <h3 className="text-lg font-bold text-jungle-text mb-2">
              {allWorkingSetsComplete ? "Finish Session?" : "Finish Early?"}
            </h3>
            <p className="text-sm text-jungle-muted mb-1">
              {completedCount}/{totalCount} sets completed
              {!allWorkingSetsComplete && ` · ${totalCount - completedCount} will be marked skipped`}.
            </p>
            {allWorkingSetsComplete ? (
              <p className="text-xs text-jungle-dim mb-4">
                This will mark the session as done and check for progressive overload opportunities.
              </p>
            ) : (
              <div className="text-xs mb-4 space-y-2">
                <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg px-3 py-2 text-amber-400">
                  <p className="font-semibold mb-0.5">⚠ Ending workout early</p>
                  <p className="text-amber-400/80 text-[11px] leading-snug">
                    Unlogged sets won&apos;t count toward weekly volume and progressive overload will
                    base next session&apos;s prescription on the sets you DID complete.
                  </p>
                </div>
                <p className="text-jungle-dim leading-snug">
                  If you&apos;re running low on time or energy, finishing early is fine — consistency
                  matters more than perfection. Jot a note below so your coaching feedback has context.
                </p>
              </div>
            )}
            <textarea
              placeholder={allWorkingSetsComplete
                ? "Session notes (optional)..."
                : "Why did you end early? (low energy, time, pain, etc.)"}
              value={sessionNotes}
              onChange={(e) => setSessionNotes(e.target.value)}
              className="input-field w-full text-sm mb-4 resize-none"
              rows={2}
            />
            <div className="flex gap-3">
              <button
                onClick={() => setShowFinishModal(false)}
                className="flex-1 py-2.5 rounded-xl text-sm font-medium bg-jungle-deeper border border-jungle-border text-jungle-muted"
              >
                Cancel
              </button>
              <button
                onClick={finishSession}
                disabled={finishing}
                className={`flex-1 py-2.5 rounded-xl text-sm font-bold active:scale-95 disabled:opacity-50 ${
                  allWorkingSetsComplete
                    ? "bg-jungle-accent text-white"
                    : "bg-amber-500 text-white"
                }`}
              >
                {finishing ? "Finishing..." : allWorkingSetsComplete ? "Finish" : "Finish Early"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Exercise Swap Modal */}
      {swapTarget && session && (
        <ExerciseSwapModal
          sessionId={session.id}
          oldExerciseId={swapTarget.exerciseId}
          oldExerciseName={swapTarget.exerciseName}
          primaryMuscle={swapTarget.primaryMuscle}
          onClose={() => setSwapTarget(null)}
          onSwapped={(result) => {
            setSwapTarget(null);
            reloadSession();
            if (result.auto_disliked) {
              showToast("Added to disliked — we won't pick it again", "info");
            } else {
              showToast(`Swapped — ${result.sets_updated} sets updated`, "success");
            }
          }}
        />
      )}

      {/* Post-Session Summary */}
      {showSummary && sessionSummary && (
        <SessionSummary
          durationSeconds={sessionSummary.duration_seconds}
          totalVolumeKg={sessionSummary.total_volume_kg}
          setsCompleted={sessionSummary.sets_completed}
          setsTotal={sessionSummary.sets_total}
          musclesTrained={sessionSummary.muscles_trained}
          progressions={sessionSummary.progressions}
          useLbs={useLbs}
          onSubmitFeedback={submitSubjectiveFeedback}
          onClose={() => setShowSummary(false)}
          onGoToDashboard={() => router.push("/dashboard")}
        />
      )}

      {/* Rest Timer (above sticky bar) */}
      {restTimer.active && (
        <RestTimer
          seconds={restTimer.seconds}
          isCompound={restTimer.isCompound}
          isFst7={restTimer.isFst7}
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
