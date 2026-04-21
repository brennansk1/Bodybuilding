"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import NavBar from "@/components/NavBar";
import CalendarMonth from "@/components/CalendarMonth";
import { api } from "@/lib/api";

// ─── Interfaces ──────────────────────────────────────────────────────────────

interface Program {
  id: string;
  name: string;
  split_type: string;
  days_per_week: number;
  current_week: number;
  mesocycle_weeks: number;
}

interface ScheduledSession {
  id: string;
  session_date: string;
  session_type: string;
  week_number: number;
  day_number: number;
  completed: boolean;
  is_deload: boolean;
  primary_muscles: string[];
}

interface CalendarBlock {
  phase: string;
  start_date: string;
  end_date: string;
  weeks: number;
  description: string;
}

interface AnnualCalendarResponse {
  competition_date: string | null;
  current_phase: string;
  weeks_out: number | null;
  calendar: CalendarBlock[];
}

interface ScheduleResponse {
  program: Program;
  sessions: ScheduledSession[];
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function formatSessionType(type: string): string {
  return type.split("_").map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(" ");
}

function formatShortDate(dateStr: string): string {
  const d = new Date(dateStr + "T00:00:00");
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function sessionDotColor(session: ScheduledSession, today: string): string {
  if (session.completed) return "bg-green-400";
  return session.session_date < today ? "bg-jungle-dim" : "bg-jungle-accent";
}

// Use hex colors instead of Tailwind classes — template literals with
// opacity modifiers (e.g. `bg-blue-500/50`) don't reliably compile in JIT.
const PHASE_HEX: Record<string, string> = {
  offseason: "#3b82f6",
  bulk: "#3b82f6",
  lean_bulk: "#06b6d4",
  mini_cut: "#f97316",
  cut: "#f97316",
  peak_week: "#ef4444",
  peak: "#ef4444",
  contest: "#eab308",
  restoration: "#22c55e",
};

function getPhaseColor(phase: string): string {
  // Still used by calendar overlays that need Tailwind classes
  switch (phase) {
    case "offseason": case "bulk": return "bg-blue-500";
    case "lean_bulk": return "bg-cyan-500";
    case "mini_cut": case "cut": return "bg-orange-500";
    case "peak_week": case "peak": return "bg-red-500";
    case "contest": return "bg-yellow-400";
    case "restoration": return "bg-green-500";
    default: return "bg-jungle-border";
  }
}

function getPhaseLabel(phase: string | null | undefined): string {
  switch (phase) {
    case "offseason": case "bulk": return "Bulk";
    case "lean_bulk": return "Lean Bulk";
    case "mini_cut": return "Mini Cut";
    case "cut": return "Cut";
    case "peak_week": case "peak": return "Peak";
    case "contest": return "Show";
    case "restoration": return "Restoration";
    // Perpetual Progression Mode sub-phases
    case "ppm_assessment": return "Assessment";
    case "ppm_accumulation": return "Accumulation";
    case "ppm_intensification": return "Intensification";
    case "ppm_deload": return "Deload";
    case "ppm_checkpoint": return "Checkpoint";
    case "ppm_mini_cut": return "Mini Cut";
    default:
      // Defensive — an empty calendar can surface undefined here.
      return typeof phase === "string" ? phase.replace(/_/g, " ") : "—";
  }
}

// ─── Mesocycle phase config (mirrors backend MESO_PHASE_MAP) ─────────────────

interface MesoPhase {
  label: string;
  name: string;
  description: string;
  color: string;
  textColor: string;
}

const MESO_PHASES: Record<number, MesoPhase & { coachingDescription: string }> = {
  1: { 
    label: "MEV", 
    name: "Minimum Effective Volume", 
    description: "3 working sets · 2 RIR · Moderate FST-7", 
    coachingDescription: "This phase targets the lowest volume needed to stimulate growth, typically 3 sets per muscle. We prioritize perfect execution and a 2 RIR (Reps In Reserve) buffer to solidify movement patterns and prime the CNS for the heavier loading to come. It's the foundation of the mesocycle.",
    color: "bg-emerald-500/20 border-emerald-500/40", 
    textColor: "text-emerald-400" 
  },
  2: { 
    label: "MEV", 
    name: "Minimum Effective Volume", 
    description: "3 working sets · 2 RIR · Moderate FST-7", 
    coachingDescription: "Maintaining MEV while increasing absolute intensity. We continue with 3 sets but focus on progressive overload via weight increases. The goal is maximum tension with zero systemic fatigue accumulation before we ramp volume in the MAV phase.",
    color: "bg-emerald-500/20 border-emerald-500/40", 
    textColor: "text-emerald-400" 
  },
  3: { 
    label: "MAV", 
    name: "Maximum Adaptive Volume", 
    description: "+1 set · Loads ↑ · 1 RIR · Aggressive FST-7 (45s rest)", 
    coachingDescription: "The 'Sweet Spot' of hypertrophy. Volume increments by 1 set as we drop the buffer to 1 RIR. We introduce aggressive FST-7 finishers with strict 45-second rests to maximize fascial stretch and blood flow. This is where the most significant tissue adaptation occurs.",
    color: "bg-yellow-500/20 border-yellow-500/40", 
    textColor: "text-yellow-400" 
  },
  4: { 
    label: "MAV", 
    name: "Maximum Adaptive Volume", 
    description: "+1 set · Loads ↑ · 1 RIR · Aggressive FST-7 (45s rest)", 
    coachingDescription: "Pushing the upper limit of adaptive volume. We maintain the +1 set increase and 1 RIR intensity. The training focus shifts to maintaining performance under higher metabolic stress, preparing the body for the final MRV push.",
    color: "bg-yellow-500/20 border-yellow-500/40", 
    textColor: "text-yellow-400" 
  },
  5: { 
    label: "MRV", 
    name: "Maximum Recoverable Volume", 
    description: "All sets to failure · 0 RIR · Forced reps + negatives", 
    coachingDescription: "The Overreach Phase. Every set is taken to absolute muscular failure (0 RIR) with advanced intensity techniques like forced repetitions and assisted negatives. This phase pushes your recovery capacity to its limit to trigger a massive supercompensation effect.",
    color: "bg-red-500/20 border-red-500/40", 
    textColor: "text-red-400" 
  },
  6: { 
    label: "DELOAD", 
    name: "Deload & Recovery", 
    description: "50% volume · 60% loads · No FST-7 · Supercompensation", 
    coachingDescription: "Strategic Recovery. Volume is slashed by 50% and intensity reduced to a RPE 6. We remove FST-7 and all failure-training to allow systemic fatigue and connective tissue inflammation to dissipate. This enables you to start the next mesocycle with a higher baseline.",
    color: "bg-blue-500/20 border-blue-500/40", 
    textColor: "text-blue-400" 
  },
};

const DAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function ProgramPage() {
  const router = useRouter();
  const { user, loading, logout } = useAuth();
  const [program, setProgram] = useState<Program | null>(null);
  const [sessions, setSessions] = useState<ScheduledSession[]>([]);
  const [fetching, setFetching] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [calendar, setCalendar] = useState<AnnualCalendarResponse | null>(null);
  const [expandedWeek, setExpandedWeek] = useState<number | null>(null);
  const [selectedMesoWeek, setSelectedMesoWeek] = useState<number | null>(null);
  const [muscleGaps, setMuscleGaps] = useState<any>(null);
  const [trainingStartTime, setTrainingStartTime] = useState("10:00");
  const [trainingDuration, setTrainingDuration] = useState(75);
  const [savingPrefs, setSavingPrefs] = useState(false);
  const [calendarOverlay, setCalendarOverlay] = useState<"none" | "macrocycle" | "mesocycle" | "microcycle" | "split">("none");
  const [calendarMonthOffset, setCalendarMonthOffset] = useState(0);

  // Volume landmark data — MEV/MAV/MRV + current weekly sets (B3.5)
  interface LandmarkMuscle {
    name: string;
    mev: number;
    mav_low: number;
    mav_high: number;
    mrv: number;
    current_weekly_sets: number;
    zone: "below_mev" | "mev_to_mav" | "mav_productive" | "mav_to_mrv" | "above_mrv";
    week_number: number | null;
  }
  interface LandmarksResponse {
    training_years: number | null;
    week_start: string;
    week_end: string;
    muscles: LandmarkMuscle[];
  }
  const [landmarks, setLandmarks] = useState<LandmarksResponse | null>(null);

  const today = new Date().toISOString().split("T")[0];

  useEffect(() => {
    if (!loading && !user) { router.push("/auth/login"); return; }
    if (user) {
      // Reset state to prevent bleedthrough from previous user
      setProgram(null);
      setSessions([]);
      setMuscleGaps(null);
      setFetching(true);
      Promise.all([
        api.get<ScheduleResponse>("/engine2/program/schedule").catch(() => null),
        api.get<Program>("/engine2/program/current").catch(() => null),
        api.get<AnnualCalendarResponse>("/engine1/annual-calendar").catch(() => null),
        api.get<any>("/engine1/muscle-gaps").catch(() => null),
        api.get<LandmarksResponse>("/engine2/volume-landmarks").catch(() => null),
      ]).then(([scheduleRes, programRes, calendarRes, gapsRes, landmarksRes]) => {
        if (landmarksRes) setLandmarks(landmarksRes);
        if (scheduleRes) {
          setProgram(scheduleRes.program);
          setSessions(scheduleRes.sessions);
          setSelectedMesoWeek(scheduleRes.program.current_week);
        } else if (programRes) {
          setProgram(programRes);
          setSelectedMesoWeek(programRes.current_week);
        }
        if (calendarRes) setCalendar(calendarRes);
        if (gapsRes) setMuscleGaps(gapsRes);
        
        // Fetch profile for training preferences
        api.get<any>("/onboarding/profile").then((p) => {
          if (p.training_start_time) setTrainingStartTime(p.training_start_time);
          if (p.training_duration_min) setTrainingDuration(p.training_duration_min);
        }).catch(() => {});

        // Auto-expand the current week
        const current = scheduleRes?.program?.current_week ?? programRes?.current_week ?? 1;
        setExpandedWeek(current);
      }).finally(() => setFetching(false));
    }
  }, [user, loading, router]);

  const generateProgram = async () => {
    setGenerating(true);
    try {
      const p = await api.post<Program & { sessions_created: number }>("/engine2/program/generate");
      setProgram(p);
      const scheduleRes = await api.get<ScheduleResponse>("/engine2/program/schedule").catch(() => null);
      if (scheduleRes) { setProgram(scheduleRes.program); setSessions(scheduleRes.sessions); }
    } catch { /* */ } finally { setGenerating(false); }
  };

  const savePreferences = async () => {
    setSavingPrefs(true);
    try {
      await api.patch("/onboarding/profile", {
        training_start_time: trainingStartTime,
        training_duration_min: trainingDuration,
      });
    } catch { /* */ } finally { setSavingPrefs(false); }
  };

  if (loading || !user) return null;

  // Group sessions by week
  const byWeek: Record<number, ScheduledSession[]> = {};
  sessions.forEach((s) => {
    if (!byWeek[s.week_number]) byWeek[s.week_number] = [];
    byWeek[s.week_number].push(s);
  });

  const totalWeeks = program?.mesocycle_weeks ?? 6;
  const currentWeek = program?.current_week ?? 1;
  const progressPct = totalWeeks > 0 ? Math.round((currentWeek / totalWeeks) * 100) : 0;

  // Macro cycle weeks.
  // For PPM users the backend returns `calendar: []` since there's no
  // competition date — `??` would not fall through because `[]` is truthy,
  // leaving macroPhases empty and macroPhases[0] undefined. Explicitly
  // fall back when the array is empty to keep the macrocycle block rendering.
  const _calBlocks = calendar?.calendar ?? [];
  const macroPhases = _calBlocks.length > 0
    ? _calBlocks.flatMap(block => Array(block.weeks).fill(block.phase))
    : Array(16).fill("offseason");

  const startAnchor = calendar?.calendar[0]?.start_date;
  let macroCurrentWeek = 1;
  if (startAnchor) {
    const start = new Date(startAnchor + "T00:00:00");
    const now = new Date();
    macroCurrentWeek = Math.max(1, Math.floor((now.getTime() - start.getTime()) / (1000 * 60 * 60 * 24 * 7)) + 1);
  }
  macroCurrentWeek = Math.min(macroCurrentWeek, macroPhases.length);
  const currentPhaseName = macroPhases[macroCurrentWeek - 1] || "offseason";

  // Current week sessions for microcycle
  const currentWeekSessions = byWeek[currentWeek] ?? [];
  const microDaySessions: (ScheduledSession | null)[] = DAY_LABELS.map((_, idx) => {
    return currentWeekSessions.find((s) => {
      const d = new Date(s.session_date + "T00:00:00");
      return (d.getDay() + 6) % 7 === idx;
    }) ?? null;
  });

  return (
    <div className="min-h-screen">
      <NavBar username={user.username} onLogout={() => { logout(); router.push("/"); }} />

      <main className="px-3 py-4">
        <div className="max-w-lg mx-auto space-y-4">

          {/* Header */}
          <div className="flex items-center gap-3">
            <a href="/training" className="text-jungle-muted hover:text-jungle-accent transition-colors" aria-label="Back">
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
            </a>
            <div className="min-w-0 flex-1">
              <h1 className="text-xl font-bold">
                <span className="text-jungle-accent">Program</span> Schedule
              </h1>
              {program && (
                <p className="text-jungle-muted text-xs mt-0.5 truncate">
                  {program.name} · {program.split_type} · {program.days_per_week}d/wk
                </p>
              )}
            </div>
            
            <div className="flex gap-2">
              <div className="bg-jungle-deeper border border-jungle-border rounded-xl p-2 flex-1 flex items-center gap-2">
                <input
                  type="time"
                  value={trainingStartTime}
                  onChange={(e) => setTrainingStartTime(e.target.value)}
                  className="bg-transparent text-jungle-accent font-bold text-sm outline-none"
                />
                <span className="text-jungle-dim text-[10px] uppercase tracking-tighter">Start</span>
              </div>
              <div className="bg-jungle-deeper border border-jungle-border rounded-xl p-2 flex-1 flex items-center gap-2">
                <input
                  type="number"
                  value={trainingDuration}
                  onChange={(e) => setTrainingDuration(parseInt(e.target.value))}
                  className="bg-transparent text-jungle-accent font-bold text-sm outline-none w-8"
                />
                <span className="text-jungle-dim text-[10px] uppercase tracking-tighter">Min</span>
              </div>
              <button 
                onClick={savePreferences}
                disabled={savingPrefs}
                className="btn-secondary text-[10px] px-3 py-1.5 h-auto transition-all active:scale-95 disabled:opacity-50"
              >
                {savingPrefs ? "..." : "Save"}
              </button>
            </div>
          </div>

          {/* Loading */}
          {fetching && (
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <div key={i} className="card animate-pulse space-y-2">
                  <div className="h-4 bg-jungle-deeper rounded w-20" />
                  <div className="h-12 bg-jungle-deeper rounded-lg" />
                </div>
              ))}
            </div>
          )}

          {/* No program */}
          {!fetching && !program && (
            <div className="card text-center py-12">
              <p className="text-jungle-muted text-lg font-medium">No active program</p>
              <p className="text-jungle-dim text-sm mt-1">Generate a program to see your mesocycle here.</p>
              <button onClick={generateProgram} disabled={generating} className="btn-primary mt-4 disabled:opacity-50">
                {generating ? "Generating..." : "Generate Program"}
              </button>
            </div>
          )}

          {/* Program content */}
          {!fetching && program && (
            <>
              {/* ── MACRO CYCLE ── */}
              <div className="card space-y-3 py-3">
                <div className="flex items-center justify-between">
                  <h3 className="font-semibold text-xs uppercase tracking-wider text-jungle-muted">Macro Cycle</h3>
                  <span className="text-xs text-jungle-accent font-bold">
                    Wk {macroCurrentWeek} · {getPhaseLabel(currentPhaseName)}
                  </span>
                </div>

                {/* Phase blocks — grouped by phase with labels */}
                <div className="overflow-x-auto pb-1">
                  <div className="flex gap-0.5 min-w-max">
                    {(() => {
                      const blocks: { phase: string; startWeek: number; count: number }[] = [];
                      let currentBlock = { phase: macroPhases[0], startWeek: 1, count: 0 };
                      macroPhases.forEach((phase, i) => {
                        if (phase === currentBlock.phase) {
                          currentBlock.count++;
                        } else {
                          blocks.push({ ...currentBlock });
                          currentBlock = { phase, startWeek: i + 1, count: 1 };
                        }
                      });
                      blocks.push({ ...currentBlock });

                      return blocks.map((block, bi) => {
                        const hex = PHASE_HEX[block.phase] || "#4a6040";
                        return (
                          <div key={bi} className="flex flex-col items-center gap-1">
                            <span className="text-[8px] font-bold uppercase tracking-wider" style={{ color: hex }}>
                              {getPhaseLabel(block.phase)} ({block.count}wk)
                            </span>
                            <div className="flex gap-0.5">
                              {Array.from({ length: block.count }, (_, wi) => {
                                const weekNum = block.startWeek + wi;
                                const isCurrent = weekNum === macroCurrentWeek;
                                const isPast = weekNum < macroCurrentWeek;
                                return (
                                  <div
                                    key={weekNum}
                                    title={`Week ${weekNum} — ${getPhaseLabel(block.phase)}`}
                                    className={`w-7 h-7 rounded-md flex items-center justify-center text-[9px] font-bold transition-all ${
                                      isCurrent ? "ring-2 ring-white/80 shadow-lg scale-110 text-white" : "text-white"
                                    }`}
                                    style={{
                                      backgroundColor: hex,
                                      opacity: isCurrent ? 1 : isPast ? 0.25 : 0.55,
                                    }}
                                  >
                                    {weekNum}
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        );
                      });
                    })()}
                  </div>
                </div>

                {/* Compact legend */}
                <div className="flex gap-x-3 gap-y-1 text-[9px] text-jungle-dim flex-wrap">
                  {[
                    { phase: "offseason", label: "Bulk" },
                    { phase: "lean_bulk", label: "Lean Bulk" },
                    { phase: "cut", label: "Cut" },
                    { phase: "peak", label: "Peak" },
                    { phase: "restoration", label: "Restore" },
                  ].map(({ phase, label }) => (
                    <span key={phase} className="flex items-center gap-1">
                      <span className="w-2.5 h-2.5 rounded inline-block" style={{ backgroundColor: PHASE_HEX[phase] }} />
                      {label}
                    </span>
                  ))}
                </div>

                {/* Progress bar */}
                <div>
                  <div className="h-1.5 bg-jungle-deeper rounded-full overflow-hidden">
                    <div className="h-full bg-jungle-accent rounded-full transition-all" style={{ width: `${Math.min(100, (macroCurrentWeek / macroPhases.length) * 100)}%` }} />
                  </div>
                  <p className="text-[9px] text-jungle-dim text-right mt-0.5">{Math.round((macroCurrentWeek / macroPhases.length) * 100)}% through annual plan</p>
                </div>
              </div>

              {/* ── MESOCYCLE with phase labels ── */}
              <div className="card space-y-3 py-3">
                <div className="flex items-center justify-between">
                  <h3 className="font-semibold text-xs uppercase tracking-wider text-jungle-muted">Mesocycle</h3>
                  <span className="text-xs text-jungle-accent font-bold">Week {currentWeek}/{totalWeeks}</span>
                </div>

                {/* 6-week grid with phase labels */}
                <div className="grid grid-cols-6 gap-1.5">
                  {Array.from({ length: totalWeeks }, (_, i) => {
                    const weekNum = i + 1;
                    const isCurrent = weekNum === currentWeek;
                    const isSelected = weekNum === selectedMesoWeek;
                    const isPast = weekNum < currentWeek;
                    const phase = MESO_PHASES[weekNum] ?? MESO_PHASES[6];
                    const completedInWeek = byWeek[weekNum]?.filter((s) => s.completed).length ?? 0;
                    const totalInWeek = byWeek[weekNum]?.length ?? 0;

                    return (
                      <button
                        key={weekNum}
                        onClick={() => setSelectedMesoWeek(weekNum)}
                        className={`rounded-xl p-2 text-center border transition-all active:scale-95 ${
                          isSelected 
                            ? `${phase.color} ring-1 ring-white/20 border-white/40 shadow-lg shadow-black/20` 
                            : isPast 
                              ? "bg-jungle-deeper/50 border-jungle-border/50 text-jungle-dim" 
                              : "bg-jungle-deeper border-jungle-border"
                        }`}
                      >
                        <p className={`text-[10px] font-bold ${isSelected ? phase.textColor : isPast ? "text-jungle-dim" : "text-jungle-muted"}`}>
                          Wk {weekNum}
                        </p>
                        <p className={`text-[9px] font-bold mt-0.5 ${isSelected ? phase.textColor : "text-jungle-dim"}`}>
                          {phase.label}
                        </p>
                        {totalInWeek > 0 && (
                          <p className="text-[8px] text-jungle-dim mt-0.5">{completedInWeek}/{totalInWeek}</p>
                        )}
                      </button>
                    );
                  })}
                </div>

                {/* Selected Phase Details */}
                {(() => {
                  const weekToShow = selectedMesoWeek || currentWeek || 1;
                  const phase = MESO_PHASES[weekToShow] ?? MESO_PHASES[1];
                  const isCurrent = weekToShow === currentWeek;

                  return (
                    <div className={`rounded-xl border p-4 ${phase.color} transition-all shadow-sm`}>
                      <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center gap-2">
                          <span className={`text-sm font-black tracking-tight ${phase.textColor}`}>{phase.label}</span>
                          <span className="text-xs font-bold text-white/90">{phase.name}</span>
                        </div>
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${isCurrent ? 'bg-white/20 text-white' : 'bg-black/20 text-jungle-dim'}`}>
                          {isCurrent ? "Active Week" : `Week ${weekToShow}`}
                        </span>
                      </div>
                      
                      <div className="space-y-3">
                        <div>
                          <p className="text-[11px] text-jungle-muted font-bold uppercase tracking-wider mb-1">Coaching Strategy</p>
                          <p className="text-[12px] text-white/80 leading-relaxed">
                            {phase.coachingDescription}
                          </p>
                        </div>
                        
                        <div className="pt-2 border-t border-white/10 flex items-center justify-between">
                          <div className="flex flex-col">
                            <span className="text-[9px] text-jungle-muted uppercase font-bold">Prescription</span>
                            <span className="text-[11px] text-white/70 font-medium">{phase.description}</span>
                          </div>
                          {isCurrent && (
                            <div className="flex items-center gap-1.5 px-2 py-1 bg-jungle-accent/20 rounded-lg border border-jungle-accent/30">
                              <span className="w-1.5 h-1.5 rounded-full bg-jungle-accent animate-pulse" />
                              <span className="text-[10px] text-jungle-accent font-bold uppercase">Tracking</span>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })()}

                {/* Progress bar */}
                <div>
                  <div className="h-1.5 bg-jungle-deeper rounded-full overflow-hidden">
                    <div className="h-full bg-jungle-accent rounded-full transition-all" style={{ width: `${progressPct}%` }} />
                  </div>
                  <p className="text-[10px] text-jungle-dim text-right mt-0.5">{progressPct}%</p>
                </div>
              </div>

              {/* ── MICROCYCLE (current week) ── */}
              <div className="card space-y-3 py-3">
                <h3 className="font-semibold text-xs uppercase tracking-wider text-jungle-muted">
                  {(() => {
                    const p = MESO_PHASES[currentWeek];
                    const weekSessions = currentWeekSessions;
                    if (weekSessions.length > 0) {
                      const firstDate = weekSessions[0].session_date;
                      const d = new Date(firstDate + "T00:00:00");
                      const monday = new Date(d);
                      monday.setDate(d.getDate() - ((d.getDay() + 6) % 7));
                      const isThisWeek = (() => {
                        const now = new Date();
                        const thisMonday = new Date(now);
                        thisMonday.setDate(now.getDate() - ((now.getDay() + 6) % 7));
                        return monday.toDateString() === thisMonday.toDateString();
                      })();
                      const label = isThisWeek ? "This Week" : `Week of ${monday.toLocaleDateString("en-US", { month: "short", day: "numeric" })}`;
                      return `${label} — ${p ? p.label : ""}`;
                    }
                    return `Week ${currentWeek} — ${p ? p.label : ""}`;
                  })()}
                </h3>

                {/* Day grid */}
                <div className="grid grid-cols-7 gap-1">
                  {DAY_LABELS.map((dayLabel, idx) => {
                    const session = microDaySessions[idx];
                    const isToday = session?.session_date === today;
                    return (
                      <div
                        key={dayLabel}
                        className={`rounded-lg p-1.5 text-center ${
                          session
                            ? isToday ? "bg-jungle-accent/15 border border-jungle-accent/50" : "bg-jungle-deeper border border-jungle-border"
                            : "bg-jungle-deeper/30 border border-jungle-border/20"
                        }`}
                      >
                        <p className={`text-[8px] font-semibold uppercase ${isToday ? "text-jungle-accent" : "text-jungle-dim"}`}>
                          {dayLabel}
                        </p>
                        {session ? (
                          <>
                            <div className={`w-1.5 h-1.5 rounded-full mx-auto my-0.5 ${sessionDotColor(session, today)}`} />
                            <p className="text-[7px] text-jungle-muted leading-tight">{formatSessionType(session.session_type)}</p>
                          </>
                        ) : (
                          <p className="text-[7px] text-jungle-dim/40 mt-1">Rest</p>
                        )}
                      </div>
                    );
                  })}
                </div>

                {/* Session list */}
                {currentWeekSessions.length > 0 && (
                  <div className="space-y-1.5 pt-2 border-t border-jungle-border">
                    {currentWeekSessions.sort((a, b) => a.day_number - b.day_number).map((session) => {
                      const isToday = session.session_date === today;
                      return (
                        <div
                          key={session.id}
                          className={`flex items-center gap-3 px-3 py-2 rounded-lg ${
                            isToday ? "bg-jungle-accent/10 border border-jungle-accent/30" : "bg-jungle-deeper"
                          }`}
                        >
                          <div className={`w-2 h-2 rounded-full shrink-0 ${sessionDotColor(session, today)}`} />
                          <div className="flex-1 min-w-0">
                            <p className={`text-xs font-semibold ${isToday ? "text-jungle-accent" : "text-jungle-muted"}`}>
                              {formatSessionType(session.session_type)}
                              {isToday && <span className="ml-1.5 text-[8px] bg-jungle-accent/20 text-jungle-accent px-1.5 py-0.5 rounded-full uppercase">Today</span>}
                            </p>
                            {session.primary_muscles?.length > 0 && (
                              <p className="text-[10px] text-jungle-dim mt-0.5 capitalize truncate">
                                {session.primary_muscles.join(", ")}
                              </p>
                            )}
                          </div>
                          <p className="text-[10px] text-jungle-dim shrink-0">{formatShortDate(session.session_date)}</p>
                          {session.completed && (
                            <svg className="w-4 h-4 text-green-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                            </svg>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* ── CALENDAR WITH OVERLAYS ── */}
              {sessions.length > 0 && (
                <div className="card space-y-3 py-3">
                  <h3 className="font-semibold text-xs uppercase tracking-wider text-jungle-muted">
                    Calendar View
                  </h3>

                  {/* Overlay toggle buttons */}
                  <div className="flex gap-1.5 flex-wrap">
                    {([
                      { key: "macrocycle", label: "Macro", icon: "📅" },
                      { key: "mesocycle", label: "Meso", icon: "🔄" },
                      { key: "microcycle", label: "Micro", icon: "📋" },
                      { key: "split", label: "Split", icon: "💪" },
                    ] as const).map(({ key, label, icon }) => (
                      <button
                        key={key}
                        onClick={() => setCalendarOverlay(calendarOverlay === key ? "none" : key)}
                        className={`px-2.5 py-1.5 rounded-lg text-[10px] font-medium border transition-all ${
                          calendarOverlay === key
                            ? "bg-jungle-accent/20 border-jungle-accent/50 text-jungle-accent"
                            : "bg-jungle-deeper border-jungle-border text-jungle-dim hover:border-jungle-accent/30"
                        }`}
                      >
                        {icon} {label}
                      </button>
                    ))}
                  </div>

                  {/* Month navigation for overlay scrolling */}
                  {calendarOverlay !== "none" && (
                    <div className="flex items-center justify-between">
                      <button
                        onClick={() => setCalendarMonthOffset((o) => o - 1)}
                        className="w-8 h-8 rounded-lg bg-jungle-deeper border border-jungle-border text-jungle-muted hover:text-jungle-accent flex items-center justify-center"
                      >
                        ‹
                      </button>
                      <span className="text-xs text-jungle-muted font-medium">
                        {new Date(new Date().getFullYear(), new Date().getMonth() + calendarMonthOffset).toLocaleDateString("en-US", { month: "long", year: "numeric" })}
                      </span>
                      <button
                        onClick={() => setCalendarMonthOffset((o) => o + 1)}
                        className="w-8 h-8 rounded-lg bg-jungle-deeper border border-jungle-border text-jungle-muted hover:text-jungle-accent flex items-center justify-center"
                      >
                        ›
                      </button>
                    </div>
                  )}

                  {/* Overlay content */}
                  {calendarOverlay === "macrocycle" && calendar && (
                    <div className="space-y-2">
                      <div className="grid grid-cols-7 gap-0.5 text-center">
                        {["M", "T", "W", "T", "F", "S", "S"].map((d, i) => (
                          <span key={i} className="text-[8px] text-jungle-dim font-semibold">{d}</span>
                        ))}
                        {(() => {
                          const viewDate = new Date(new Date().getFullYear(), new Date().getMonth() + calendarMonthOffset, 1);
                          const daysInMonth = new Date(viewDate.getFullYear(), viewDate.getMonth() + 1, 0).getDate();
                          const startDay = (viewDate.getDay() + 6) % 7;
                          const cells = [];
                          for (let i = 0; i < startDay; i++) cells.push(<div key={`e${i}`} />);
                          for (let d = 1; d <= daysInMonth; d++) {
                            const date = new Date(viewDate.getFullYear(), viewDate.getMonth(), d);
                            const dateStr = date.toISOString().split("T")[0];
                            const block = calendar.calendar.find(b => dateStr >= b.start_date && dateStr <= b.end_date);
                            const phase = block?.phase || "offseason";
                            const isToday_ = dateStr === today;
                            cells.push(
                              <div key={d} title={`${getPhaseLabel(phase)}`}
                                className={`h-6 rounded flex items-center justify-center text-[8px] font-bold ${getPhaseColor(phase)}${isToday_ ? "/80 ring-1 ring-white/50" : "/40"} text-white/80`}
                              >
                                {d}
                              </div>
                            );
                          }
                          return cells;
                        })()}
                      </div>
                      <div className="flex gap-2 flex-wrap text-[8px] text-jungle-dim justify-center">
                        {calendar.calendar.map((b, i) => (
                          <span key={i} className="flex items-center gap-1">
                            <span className={`w-2 h-2 rounded-sm ${getPhaseColor(b.phase)}`} />
                            {getPhaseLabel(b.phase)} ({b.weeks}wk)
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {calendarOverlay === "mesocycle" && (
                    <div className="space-y-2">
                      <div className="grid grid-cols-7 gap-0.5 text-center">
                        {["M", "T", "W", "T", "F", "S", "S"].map((d, i) => (
                          <span key={i} className="text-[8px] text-jungle-dim font-semibold">{d}</span>
                        ))}
                        {(() => {
                          const viewDate = new Date(new Date().getFullYear(), new Date().getMonth() + calendarMonthOffset, 1);
                          const daysInMonth = new Date(viewDate.getFullYear(), viewDate.getMonth() + 1, 0).getDate();
                          const startDay = (viewDate.getDay() + 6) % 7;
                          const cells = [];
                          for (let i = 0; i < startDay; i++) cells.push(<div key={`e${i}`} />);
                          for (let d = 1; d <= daysInMonth; d++) {
                            const date = new Date(viewDate.getFullYear(), viewDate.getMonth(), d);
                            const dateStr = date.toISOString().split("T")[0];
                            const session = sessions.find(s => s.session_date === dateStr);
                            const phase = session ? (MESO_PHASES[session.week_number] ?? MESO_PHASES[6]) : null;
                            const isToday_ = dateStr === today;
                            cells.push(
                              <div key={d}
                                className={`h-6 rounded flex items-center justify-center text-[8px] font-bold ${
                                  phase ? `${phase.color} ${phase.textColor}` : "bg-jungle-deeper/20 text-jungle-dim/30"
                                }${isToday_ ? " ring-1 ring-white/50" : ""}`}
                              >
                                {d}
                              </div>
                            );
                          }
                          return cells;
                        })()}
                      </div>
                      <div className="flex gap-2 text-[8px] text-jungle-dim justify-center flex-wrap">
                        {[1, 3, 5, 6].map(w => {
                          const p = MESO_PHASES[w];
                          return (
                            <span key={w} className={`${p.textColor} flex items-center gap-1`}>
                              <span className={`w-2 h-2 rounded-sm ${p.color.split(" ")[0]}`} />
                              {p.label}
                            </span>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  {calendarOverlay === "microcycle" && (
                    <div className="space-y-2">
                      <div className="grid grid-cols-7 gap-0.5 text-center">
                        {["M", "T", "W", "T", "F", "S", "S"].map((d, i) => (
                          <span key={i} className="text-[8px] text-jungle-dim font-semibold">{d}</span>
                        ))}
                        {(() => {
                          const viewDate = new Date(new Date().getFullYear(), new Date().getMonth() + calendarMonthOffset, 1);
                          const daysInMonth = new Date(viewDate.getFullYear(), viewDate.getMonth() + 1, 0).getDate();
                          const startDay = (viewDate.getDay() + 6) % 7;
                          const cells = [];
                          for (let i = 0; i < startDay; i++) cells.push(<div key={`e${i}`} />);
                          for (let d = 1; d <= daysInMonth; d++) {
                            const date = new Date(viewDate.getFullYear(), viewDate.getMonth(), d);
                            const dateStr = date.toISOString().split("T")[0];
                            const session = sessions.find(s => s.session_date === dateStr);
                            const isToday_ = dateStr === today;
                            cells.push(
                              <div key={d}
                                className={`h-8 rounded flex flex-col items-center justify-center text-[7px] leading-tight ${
                                  session
                                    ? session.completed
                                      ? "bg-green-500/20 text-green-400 border border-green-500/30"
                                      : isToday_
                                      ? "bg-jungle-accent/20 text-jungle-accent border border-jungle-accent/40"
                                      : "bg-jungle-deeper text-jungle-muted border border-jungle-border"
                                    : "bg-jungle-deeper/20 text-jungle-dim/30"
                                }`}
                              >
                                <span className="font-bold text-[8px]">{d}</span>
                                {session && <span className="truncate w-full text-center px-0.5">{formatSessionType(session.session_type).split(" ")[0]}</span>}
                              </div>
                            );
                          }
                          return cells;
                        })()}
                      </div>
                    </div>
                  )}

                  {calendarOverlay === "split" && (
                    <div className="space-y-2">
                      <div className="grid grid-cols-7 gap-0.5 text-center">
                        {["M", "T", "W", "T", "F", "S", "S"].map((d, i) => (
                          <span key={i} className="text-[8px] text-jungle-dim font-semibold">{d}</span>
                        ))}
                        {(() => {
                          const viewDate = new Date(new Date().getFullYear(), new Date().getMonth() + calendarMonthOffset, 1);
                          const daysInMonth = new Date(viewDate.getFullYear(), viewDate.getMonth() + 1, 0).getDate();
                          const startDay = (viewDate.getDay() + 6) % 7;
                          const cells = [];
                          for (let i = 0; i < startDay; i++) cells.push(<div key={`e${i}`} />);
                          for (let d = 1; d <= daysInMonth; d++) {
                            const date = new Date(viewDate.getFullYear(), viewDate.getMonth(), d);
                            const dateStr = date.toISOString().split("T")[0];
                            const session = sessions.find(s => s.session_date === dateStr);
                            cells.push(
                              <div key={d}
                                className={`h-10 rounded flex flex-col items-center justify-center text-[6px] leading-tight ${
                                  session
                                    ? "bg-jungle-deeper text-jungle-muted border border-jungle-border"
                                    : "bg-jungle-deeper/20 text-jungle-dim/30"
                                }`}
                              >
                                <span className="font-bold text-[8px]">{d}</span>
                                {session && (
                                  <>
                                    <span className="text-jungle-accent font-semibold truncate w-full text-center px-0.5">
                                      {formatSessionType(session.session_type)}
                                    </span>
                                    {session.primary_muscles?.slice(0, 2).map((m, i) => (
                                      <span key={i} className="text-jungle-dim capitalize truncate w-full text-center">{m}</span>
                                    ))}
                                  </>
                                )}
                              </div>
                            );
                          }
                          return cells;
                        })()}
                      </div>
                    </div>
                  )}

                  {/* Default calendar (no overlay) */}
                  {calendarOverlay === "none" && (
                    <CalendarMonth sessions={sessions} today={today} />
                  )}
                </div>
              )}

              {/* ── WEEKLY BREAKDOWN (accordion) ── */}
              {Array.from({ length: totalWeeks }, (_, i) => i + 1).map((week) => {
                const weekSessions = byWeek[week] ?? [];
                const phase = MESO_PHASES[week] ?? MESO_PHASES[6];
                const isExpanded = expandedWeek === week;
                const completedCount = weekSessions.filter((s) => s.completed).length;

                return (
                  <div key={week} className={`rounded-xl border transition-colors ${
                    week === currentWeek ? phase.color : "border-jungle-border bg-jungle-card/60"
                  }`}>
                    <button
                      onClick={() => setExpandedWeek(isExpanded ? null : week)}
                      className="w-full text-left px-4 py-3 flex items-center justify-between"
                    >
                      <div className="flex items-center gap-2">
                        <span className={`text-xs font-bold ${week === currentWeek ? phase.textColor : "text-jungle-muted"}`}>
                          Wk {week}
                        </span>
                        <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${phase.color} ${phase.textColor}`}>
                          {phase.label}
                        </span>
                        {week === currentWeek && (
                          <span className="text-[9px] bg-jungle-accent/20 text-jungle-accent px-1.5 py-0.5 rounded-full uppercase font-medium">Current</span>
                        )}
                      </div>
                      <div className="flex items-center gap-2">
                        {weekSessions.length > 0 && (
                          <span className="text-[10px] text-jungle-dim">{completedCount}/{weekSessions.length}</span>
                        )}
                        <svg className={`w-4 h-4 text-jungle-dim transition-transform ${isExpanded ? "rotate-180" : ""}`}
                          fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                        </svg>
                      </div>
                    </button>

                    {isExpanded && (
                      <div className="px-4 pb-3 space-y-2">
                        {/* Phase info */}
                        <p className="text-[10px] text-jungle-dim">{phase.description}</p>

                        {/* Sessions */}
                        {weekSessions.length > 0 ? (
                          <div className="grid gap-1.5" style={{ gridTemplateColumns: `repeat(${Math.min(weekSessions.length, 4)}, minmax(0, 1fr))` }}>
                            {weekSessions.sort((a, b) => a.day_number - b.day_number).map((session) => {
                              const isToday = session.session_date === today;
                              return (
                                <div
                                  key={session.id}
                                  className={`rounded-lg p-2 text-center bg-jungle-deeper ${isToday ? "ring-1 ring-jungle-accent/60" : ""}`}
                                >
                                  <div className={`w-1.5 h-1.5 rounded-full ${sessionDotColor(session, today)} mx-auto`} />
                                  <p className="text-[9px] font-semibold text-jungle-muted mt-1 leading-tight">
                                    {formatSessionType(session.session_type)}
                                  </p>
                                  <p className="text-[8px] text-jungle-dim">{formatShortDate(session.session_date)}</p>
                                </div>
                              );
                            })}
                          </div>
                        ) : (
                          <p className="text-[10px] text-jungle-dim">No sessions generated for this week yet.</p>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}

              {/* Regenerate */}
              {sessions.length === 0 && (
                <button onClick={generateProgram} disabled={generating} className="btn-primary w-full disabled:opacity-50">
                  {generating ? "Generating..." : "Generate Program"}
                </button>
              )}

              {/* Physique Diagnostic Insights */}
              <div className="card space-y-3 py-4 border-t-2 border-jungle-accent/30 rounded-t-none">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className="w-1.5 h-4 bg-jungle-accent rounded-full" />
                    <h3 className="font-bold text-xs uppercase tracking-wider text-jungle-text">Physique Diagnostic</h3>
                  </div>
                  <span className="text-[10px] bg-jungle-deeper px-2 py-0.5 rounded-full text-jungle-dim border border-jungle-border font-bold">Engine 1 Analysis</span>
                </div>
                
                <div className="p-3 bg-jungle-deeper/40 border border-jungle-border/50 rounded-xl space-y-3">
                  <div className="flex items-start gap-3">
                    <div className="w-8 h-8 rounded-lg bg-jungle-accent/10 flex items-center justify-center shrink-0 border border-jungle-accent/20">
                      <svg className="w-4 h-4 text-jungle-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 8v8m-4-5v5m-4-2v2m-2 4h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                      </svg>
                    </div>
                    <div>
                      <p className="text-xs font-bold text-white mb-0.5">Split Logic: {program.split_type.replace(/_/g, " ").toUpperCase()}</p>
                      <p className="text-[11px] text-jungle-muted leading-relaxed">
                        This split was selected to prioritize your <span className="text-jungle-accent font-bold">Top 3 Physique Gaps</span> while managing systemic fatigue across the 6-week cycle.
                      </p>
                    </div>
                  </div>

                  {muscleGaps && (
                    <div className="space-y-2.5 pt-2 border-t border-white/5">
                      <p className="text-[10px] text-jungle-dim uppercase font-black tracking-widest">Ranked Priority Gaps</p>
                      {muscleGaps.ranked_gaps?.slice(0, 3).map((g: any, i: number) => (
                        <div key={g.site} className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <span className="text-[10px] font-bold text-jungle-dim w-3">{i+1}.</span>
                            <span className="text-xs font-bold text-jungle-muted capitalize">{g.site}</span>
                          </div>
                          <div className="flex items-center gap-3">
                            <div className="w-20 h-1.5 bg-jungle-deeper rounded-full overflow-hidden border border-white/5">
                              <div className="h-full bg-red-500/80 rounded-full shadow-[0_0_8px_rgba(239,68,68,0.4)]" style={{ width: `${Math.min(100, (g.gap_cm / 5) * 100)}%` }} />
                            </div>
                            <span className="text-[10px] font-black text-red-400">+{g.gap_cm}cm</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
                
                <p className="text-[10px] text-jungle-dim italic text-center leading-tight px-4">
                  Volume landmarks (MEV/MAV/MRV) are dynamically adjusted session-by-session based on these HQI metrics.
                </p>
              </div>

              {/* Quick links */}
              <div className="flex gap-3">
                <a href="/training/analytics" className="flex-1 btn-secondary text-center text-sm py-2.5">
                  Analytics
                </a>
                <a href="/training/history" className="flex-1 btn-secondary text-center text-sm py-2.5">
                  History
                </a>
              </div>
            </>
          )}

          {/* ── Volume Landmarks (B3.5) ── */}
          {landmarks && landmarks.muscles.length > 0 && (
            <div className="card mt-5 space-y-3">
              <div className="flex items-baseline justify-between">
                <h2 className="text-sm font-bold text-jungle-text uppercase tracking-wider">
                  Weekly Volume vs Landmarks
                </h2>
                <span className="text-[10px] text-jungle-dim">
                  Week of {landmarks.week_start}
                </span>
              </div>
              <p className="text-[11px] text-jungle-dim">
                MEV → MAV (productive band) → MRV per muscle, scaled to your training experience.
              </p>
              <div className="space-y-2">
                {landmarks.muscles.map((m) => {
                  const axisMax = Math.max(m.mrv + 2, m.current_weekly_sets + 1);
                  const mevPct = (m.mev / axisMax) * 100;
                  const mavLowPct = (m.mav_low / axisMax) * 100;
                  const mavHighPct = (m.mav_high / axisMax) * 100;
                  const mrvPct = (m.mrv / axisMax) * 100;
                  const currentPct = (m.current_weekly_sets / axisMax) * 100;
                  const zoneColor =
                    m.zone === "below_mev" ? "#ef4444" :
                    m.zone === "mev_to_mav" ? "#eab308" :
                    m.zone === "mav_productive" ? "#4ade80" :
                    m.zone === "mav_to_mrv" ? "#22c55e" :
                    "#ef4444";
                  const zoneLabel =
                    m.zone === "below_mev" ? "Below MEV" :
                    m.zone === "mev_to_mav" ? "Sub-productive" :
                    m.zone === "mav_productive" ? "Productive" :
                    m.zone === "mav_to_mrv" ? "High productive" :
                    "Over MRV";
                  return (
                    <div key={m.name}>
                      <div className="flex items-baseline justify-between mb-1">
                        <span className="text-[11px] text-jungle-muted capitalize">
                          {m.name.replace(/_/g, " ")}
                        </span>
                        <span className="text-[10px] font-mono" style={{ color: zoneColor }}>
                          {m.current_weekly_sets} / {m.mrv} · {zoneLabel}
                        </span>
                      </div>
                      <div className="relative h-3 bg-jungle-deeper rounded-full overflow-hidden">
                        {/* Productive band background */}
                        <div
                          className="absolute top-0 bottom-0 bg-green-500/10"
                          style={{
                            left: `${mavLowPct}%`,
                            width: `${mavHighPct - mavLowPct}%`,
                          }}
                        />
                        {/* Current volume fill */}
                        <div
                          className="absolute top-0 bottom-0 rounded-full transition-all"
                          style={{
                            width: `${currentPct}%`,
                            backgroundColor: zoneColor,
                            opacity: 0.85,
                          }}
                        />
                        {/* MEV tick */}
                        <div
                          className="absolute top-0 bottom-0 w-px bg-amber-400/70"
                          style={{ left: `${mevPct}%` }}
                          title={`MEV ${m.mev}`}
                        />
                        {/* MRV tick */}
                        <div
                          className="absolute top-0 bottom-0 w-px bg-red-400/70"
                          style={{ left: `${mrvPct}%` }}
                          title={`MRV ${m.mrv}`}
                        />
                      </div>
                      <div className="flex justify-between text-[9px] text-jungle-dim/70 mt-0.5 font-mono">
                        <span>0</span>
                        <span>MEV {m.mev}</span>
                        <span>MAV {m.mav_low}-{m.mav_high}</span>
                        <span>MRV {m.mrv}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </main>

      <div className="md:hidden h-16" />
    </div>
  );
}

