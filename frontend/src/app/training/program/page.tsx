"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import NavBar from "@/components/NavBar";
import { api } from "@/lib/api";

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

function formatSessionType(type: string): string {
  return type
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

function formatShortDate(dateStr: string): string {
  const d = new Date(dateStr + "T00:00:00");
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function sessionDotColor(session: ScheduledSession, today: string): string {
  if (session.completed) return "bg-green-400";
  const isPast = session.session_date < today;
  if (isPast) return "bg-jungle-dim";
  return "bg-jungle-accent";
}

// Determine phase color for macro cycle boxes
function getPhaseColor(phase: string): string {
  switch (phase) {
    case "offseason": return "bg-blue-500";
    case "lean_bulk": return "bg-cyan-500";
    case "cut": return "bg-orange-500";
    case "peak_week": return "bg-red-500";
    case "contest": return "bg-yellow-400";
    case "restoration": return "bg-green-500";
    default: return "bg-jungle-border";
  }
}

function getPhaseLabel(phase: string): string {
  switch (phase) {
    case "offseason": return "Bulk";
    case "lean_bulk": return "Lean Bulk";
    case "cut": return "Cut";
    case "peak_week": return "Peak";
    case "contest": return "Show";
    case "restoration": return "Restoration";
    default: return phase;
  }
}

// Tooltip component
function Tooltip({ text, children }: { text: string; children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="relative inline-flex items-center">
      {children}
      <button
        onClick={() => setOpen(!open)}
        className="ml-1.5 w-4 h-4 rounded-full bg-jungle-border/40 text-jungle-dim text-[10px] flex items-center justify-center hover:bg-jungle-accent/20 hover:text-jungle-accent transition-colors"
      >
        i
      </button>
      {open && (
        <div className="absolute left-0 top-6 z-20 w-64 bg-jungle-deeper border border-jungle-border rounded-xl p-3 shadow-xl">
          <p className="text-xs text-jungle-muted leading-relaxed">{text}</p>
          <button
            onClick={() => setOpen(false)}
            className="mt-2 text-[10px] text-jungle-dim hover:text-jungle-accent"
          >
            Dismiss
          </button>
        </div>
      )}
    </div>
  );
}

const DAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export default function ProgramPage() {
  const router = useRouter();
  const { user, loading, logout } = useAuth();
  const [program, setProgram] = useState<Program | null>(null);
  const [sessions, setSessions] = useState<ScheduledSession[]>([]);
  const [fetching, setFetching] = useState(true);
  const [generating, setGenerating] = useState(false);

  const [calendar, setCalendar] = useState<AnnualCalendarResponse | null>(null);

  const today = new Date().toISOString().split("T")[0];

  useEffect(() => {
    if (!loading && !user) { router.push("/auth/login"); return; }
    if (user) {
      Promise.all([
        api.get<ScheduleResponse>("/engine2/program/schedule").catch(() => null),
        api.get<Program>("/engine2/program/current").catch(() => null),
        api.get<AnnualCalendarResponse>("/engine1/annual-calendar").catch(() => null),
      ]).then(([scheduleRes, programRes, calendarRes]) => {
        if (scheduleRes) {
          setProgram(scheduleRes.program);
          setSessions(scheduleRes.sessions);
        } else if (programRes) {
          setProgram(programRes);
        }
        if (calendarRes) {
          setCalendar(calendarRes);
        }
      }).finally(() => setFetching(false));
    }
  }, [user, loading, router]);

  const generateProgram = async () => {
    setGenerating(true);
    try {
      const p = await api.post<Program & { sessions_created: number; message: string }>(
        "/engine2/program/generate"
      );
      setProgram(p);
      // Re-fetch schedule
      const scheduleRes = await api.get<ScheduleResponse>("/engine2/program/schedule").catch(() => null);
      if (scheduleRes) {
        setProgram(scheduleRes.program);
        setSessions(scheduleRes.sessions);
      }
    } catch {
      // silent
    } finally {
      setGenerating(false);
    }
  };

  if (loading || !user) return null;

  // Group sessions by week_number
  const byWeek: Record<number, ScheduledSession[]> = {};
  sessions.forEach((s) => {
    if (!byWeek[s.week_number]) byWeek[s.week_number] = [];
    byWeek[s.week_number].push(s);
  });
  const weeks = Object.keys(byWeek).map(Number).sort((a, b) => a - b);

  const totalWeeks = program?.mesocycle_weeks ?? weeks.length;
  const currentWeek = program?.current_week ?? 1;
  const progressPct = totalWeeks > 0 ? Math.round((currentWeek / totalWeeks) * 100) : 0;

  const splitLabel = program
    ? program.split_type.replace(/_/g, "/").replace(/\b\w/g, (c) => c.toUpperCase())
    : "";

  // Macro cycle: derived from actual calendar
  const macroPhases = calendar?.calendar.flatMap(block => 
    Array(block.weeks).fill(block.phase)
  ) ?? Array(16).fill("offseason"); // Fallback

  const MACRO_WEEKS = macroPhases.length;
  // If we are far into the future, we might need a way to find where "today" is in macroPhases.
  // For now, assume currentWeek is the offset into the first phase or similar.
  // Better: find how many weeks since the start of the calendar.
  // Calculate current week relative to anchored start (52w out)
  const startAnchor = calendar?.calendar[0]?.start_date;
  let macroCurrentWeek = 1;
  if (startAnchor) {
    const start = new Date(startAnchor + "T00:00:00");
    const now = new Date();
    const diffDays = Math.floor((now.getTime() - start.getTime()) / (1000 * 60 * 60 * 24));
    macroCurrentWeek = Math.max(1, Math.floor(diffDays / 7) + 1);
  }
  
  // Clamp to max weeks in calendar
  macroCurrentWeek = Math.min(macroCurrentWeek, macroPhases.length);
  const currentPhaseName = macroPhases[macroCurrentWeek - 1] || "offseason";

  // Current mesocycle sessions (current week)
  const currentWeekSessions = byWeek[currentWeek] ?? [];

  // Micro cycle: sessions for this week, mapped to day slots
  const microDaySessions: (ScheduledSession | null)[] = DAY_LABELS.map((_, idx) => {
    return currentWeekSessions.find((s) => {
      const d = new Date(s.session_date + "T00:00:00");
      // getDay(): 0=Sun,1=Mon,...6=Sat; idx 0=Mon so shift
      return (d.getDay() + 6) % 7 === idx;
    }) ?? null;
  });

  return (
    <div className="min-h-screen bg-jungle-dark">
      <NavBar username={user.username} onLogout={() => { logout(); router.push("/"); }} />

      <main className="container-app py-6">
        <div className="max-w-3xl mx-auto space-y-6">

          {/* Header */}
          <div className="flex items-center gap-3">
            <a
              href="/training"
              className="text-jungle-muted hover:text-jungle-accent transition-colors"
              aria-label="Back to Training"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
            </a>
            <div>
              <h1 className="text-2xl font-bold">
                <span className="text-jungle-accent">Program</span> Schedule
              </h1>
              {program && (
                <p className="text-jungle-muted text-sm mt-0.5">
                  {program.name} &mdash; {splitLabel} &middot; {program.days_per_week} days/week
                </p>
              )}
            </div>
          </div>

          {/* Loading state */}
          {fetching && (
            <div className="space-y-4">
              {[1, 2, 3].map((i) => (
                <div key={i} className="card animate-pulse space-y-3">
                  <div className="h-4 bg-jungle-deeper rounded w-24" />
                  <div className="flex gap-2">
                    {[1, 2, 3, 4].map((j) => (
                      <div key={j} className="flex-1 h-16 bg-jungle-deeper rounded-lg" />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* No program state */}
          {!fetching && !program && (
            <div className="card text-center py-16">
              <p className="text-jungle-muted text-lg font-medium">No active program</p>
              <p className="text-jungle-dim text-sm mt-2">
                Generate a program to see your full mesocycle schedule here.
              </p>
              <button
                onClick={generateProgram}
                disabled={generating}
                className="btn-primary mt-5 disabled:opacity-50"
              >
                {generating ? "Generating..." : "Generate Program"}
              </button>
            </div>
          )}

          {/* Program overview */}
          {!fetching && program && (
            <>
              {/* ── MACRO CYCLE ── */}
              <div className="card space-y-3">
                <div className="flex items-center">
                  <h3 className="font-semibold text-sm">Macro Cycle</h3>
                  <Tooltip text="The full competition prep plan spanning months — bulk, cut, and peak phases.">
                    <span />
                  </Tooltip>
                </div>

                {/* Phase legend */}
                <div className="flex gap-x-4 gap-y-1.5 text-[10px] text-jungle-dim flex-wrap">
                  <div className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-blue-500 inline-block" /> Bulk</div>
                  <div className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-cyan-500 inline-block" /> Lean Bulk</div>
                  <div className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-orange-500 inline-block" /> Cut</div>
                  <div className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-red-500 inline-block" /> Peak</div>
                  <div className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-green-500 inline-block" /> Restoration</div>
                </div>

                {/* Week boxes */}
                <div className="flex gap-1 flex-wrap">
                  {macroPhases.map((phase, i) => {
                    const weekNum = i + 1;
                    const isCurrent = weekNum === macroCurrentWeek;
                    const isPast = weekNum < macroCurrentWeek;
                    const color = getPhaseColor(phase);
                    const label = getPhaseLabel(phase);
                    return (
                      <div
                        key={weekNum}
                        title={`Week ${weekNum} — ${label}`}
                        className={`relative flex-shrink-0 w-7 h-7 rounded flex items-center justify-center text-[9px] font-bold transition-all ${
                          isCurrent
                            ? `${color} text-white ring-2 ring-white/60 shadow-lg shadow-white/20`
                            : isPast
                            ? `${color}/40 text-white/40`
                            : `${color}/50 text-white/60`
                        }`}
                      >
                        {weekNum}
                      </div>
                    );
                  })}
                </div>
                <p className="text-[10px] text-jungle-dim">
                  Week {macroCurrentWeek} &mdash; {getPhaseLabel(currentPhaseName)} phase
                </p>
              </div>

              {/* ── MESOCYCLE ── */}
              <div className="card space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center">
                    <h3 className="font-semibold text-sm">Mesocycle</h3>
                    <Tooltip text="A 4-week training block with progressive volume overload, ending in a deload week.">
                      <span />
                    </Tooltip>
                  </div>
                  <span className="text-xs text-jungle-accent font-bold">
                    Week {currentWeek} of {totalWeeks}
                  </span>
                </div>

                <div className="grid grid-cols-4 gap-2">
                  {Array.from({ length: totalWeeks }, (_, i) => {
                    const weekNum = i + 1;
                    const isCurrent = weekNum === currentWeek;
                    const isPast = weekNum < currentWeek;
                    const isDeloadWeek = byWeek[weekNum]?.some((s) => s.is_deload) ?? (weekNum === totalWeeks);
                    const completedInWeek = byWeek[weekNum]?.filter((s) => s.completed).length ?? 0;
                    const totalInWeek = byWeek[weekNum]?.length ?? 0;

                    return (
                      <div
                        key={weekNum}
                        className={`rounded-lg p-3 text-center space-y-1 transition-all ${
                          isCurrent
                            ? "bg-jungle-accent/15 border border-jungle-accent/50"
                            : isDeloadWeek
                            ? "bg-blue-500/10 border border-blue-500/20"
                            : "bg-jungle-deeper border border-jungle-border"
                        }`}
                      >
                        <p className={`text-xs font-bold ${isCurrent ? "text-jungle-accent" : "text-jungle-muted"}`}>
                          Wk {weekNum}
                        </p>
                        {isDeloadWeek && (
                          <p className="text-[9px] text-blue-400 font-semibold">DELOAD</p>
                        )}
                        {totalInWeek > 0 && (
                          <p className="text-[9px] text-jungle-dim">
                            {completedInWeek}/{totalInWeek}
                          </p>
                        )}
                        {/* Volume indicator dots */}
                        <div className="flex justify-center gap-0.5 mt-1">
                          {Array.from({ length: isDeloadWeek ? 2 : Math.min(weekNum, 4) }, (_, j) => (
                            <div
                              key={j}
                              className={`w-1 h-1 rounded-full ${
                                isPast || isCurrent ? "bg-jungle-accent" : "bg-jungle-border"
                              }`}
                            />
                          ))}
                        </div>
                      </div>
                    );
                  })}
                </div>

                {/* Mesocycle progress bar */}
                <div>
                  <div className="h-1.5 bg-jungle-deeper rounded-full overflow-hidden">
                    <div
                      className="h-full bg-jungle-accent rounded-full transition-all"
                      style={{ width: `${progressPct}%` }}
                    />
                  </div>
                  <p className="text-[10px] text-jungle-dim text-right mt-1">{progressPct}% complete</p>
                </div>
              </div>

              {/* ── MICROCYCLE ── */}
              <div className="card space-y-3">
                <div className="flex items-center">
                  <h3 className="font-semibold text-sm">Microcycle — Week {currentWeek}</h3>
                  <Tooltip text="Your weekly training schedule — individual sessions and their focus.">
                    <span />
                  </Tooltip>
                </div>

                <div className="grid grid-cols-7 gap-1">
                  {DAY_LABELS.map((dayLabel, idx) => {
                    const session = microDaySessions[idx];
                    const isToday = session?.session_date === today;
                    return (
                      <div
                        key={dayLabel}
                        className={`rounded-lg p-2 text-center space-y-1 ${
                          session
                            ? isToday
                              ? "bg-jungle-accent/15 border border-jungle-accent/50"
                              : "bg-jungle-deeper border border-jungle-border"
                            : "bg-jungle-deeper/40 border border-jungle-border/30"
                        }`}
                      >
                        <p className={`text-[9px] font-semibold uppercase ${isToday ? "text-jungle-accent" : "text-jungle-dim"}`}>
                          {dayLabel}
                        </p>
                        {session ? (
                          <>
                            <div className={`w-1.5 h-1.5 rounded-full mx-auto ${sessionDotColor(session, today)}`} />
                            <p className="text-[8px] text-jungle-muted leading-tight">
                              {formatSessionType(session.session_type)}
                            </p>
                            {session.completed && (
                              <p className="text-[8px] text-green-400 font-bold">Done</p>
                            )}
                          </>
                        ) : (
                          <p className="text-[8px] text-jungle-dim/50">Rest</p>
                        )}
                      </div>
                    );
                  })}
                </div>

                {currentWeekSessions.length > 0 && (
                  <div className="space-y-2 pt-2 border-t border-jungle-border">
                    {currentWeekSessions
                      .sort((a, b) => a.day_number - b.day_number)
                      .map((session) => {
                        const dotColor = sessionDotColor(session, today);
                        const isToday = session.session_date === today;
                        return (
                          <div
                            key={session.id}
                            className={`flex items-center gap-3 px-3 py-2.5 rounded-lg ${
                              isToday ? "bg-jungle-accent/10 border border-jungle-accent/30" : "bg-jungle-deeper"
                            }`}
                          >
                            <div className={`w-2 h-2 rounded-full shrink-0 ${dotColor}`} />
                            <div className="flex-1 min-w-0">
                              <p className={`text-xs font-semibold ${isToday ? "text-jungle-accent" : "text-jungle-muted"}`}>
                                {formatSessionType(session.session_type)}
                                {isToday && <span className="ml-1.5 text-[9px] bg-jungle-accent/20 text-jungle-accent px-1.5 py-0.5 rounded-full font-medium uppercase tracking-wide">Today</span>}
                              </p>
                              {session.primary_muscles?.length > 0 && (
                                <p className="text-[10px] text-jungle-dim mt-0.5 capitalize">
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

              {/* Split reason banner */}
              <div className="card flex items-start gap-3 border border-jungle-accent/20">
                <svg className="w-4 h-4 text-jungle-accent mt-0.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M12 2a10 10 0 110 20A10 10 0 0112 2z" />
                </svg>
                <p className="text-xs text-jungle-muted leading-relaxed">
                  Split selected based on your physique gaps
                </p>
              </div>

              {/* Week cards */}
              {weeks.map((week) => {
                const weekSessions = byWeek[week];
                const isDeload = weekSessions.some((s) => s.is_deload);
                const totalSets = weekSessions.reduce((acc, s) => {
                  return acc + (s.primary_muscles?.length ?? 0);
                }, 0);
                const completedCount = weekSessions.filter((s) => s.completed).length;

                return (
                  <div
                    key={week}
                    className={`card space-y-4 ${isDeload ? "border border-blue-500/30 bg-blue-500/5" : ""}`}
                  >
                    {/* Week header */}
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <h3 className="font-semibold text-sm">Week {week}</h3>
                        {week === currentWeek && (
                          <span className="px-2 py-0.5 rounded bg-jungle-accent/20 text-jungle-accent text-[10px] font-medium uppercase tracking-wide">
                            Current
                          </span>
                        )}
                        {isDeload && (
                          <span className="px-2 py-0.5 rounded bg-blue-500/20 text-blue-300 text-[10px] font-medium uppercase tracking-wide">
                            Deload
                          </span>
                        )}
                      </div>
                      <span className="text-xs text-jungle-dim">
                        {completedCount}/{weekSessions.length} done
                      </span>
                    </div>

                    {/* Day cards row */}
                    <div className="grid gap-2" style={{ gridTemplateColumns: `repeat(${weekSessions.length}, minmax(0, 1fr))` }}>
                      {weekSessions.sort((a, b) => a.day_number - b.day_number).map((session) => {
                        const dotColor = sessionDotColor(session, today);
                        const isToday = session.session_date === today;
                        return (
                          <div
                            key={session.id}
                            className={`rounded-lg p-2.5 text-center space-y-1.5 ${
                              isDeload ? "bg-blue-950/40" : "bg-jungle-deeper"
                            } ${isToday ? "ring-1 ring-jungle-accent/60" : ""}`}
                          >
                            <div className={`w-2 h-2 rounded-full ${dotColor} mx-auto`} />
                            <p className="text-[10px] font-semibold leading-tight text-jungle-muted">
                              {formatSessionType(session.session_type)}
                            </p>
                            <p className="text-[9px] text-jungle-dim">
                              {formatShortDate(session.session_date)}
                            </p>
                          </div>
                        );
                      })}
                    </div>

                    {/* Weekly summary */}
                    <div className="flex items-center justify-between text-xs text-jungle-dim pt-1 border-t border-jungle-border">
                      <span>{weekSessions.length} sessions planned</span>
                      {totalSets > 0 && <span>{totalSets} planned sets est.</span>}
                    </div>
                  </div>
                );
              })}

              {/* Regenerate */}
              {sessions.length === 0 && (
                <button
                  onClick={generateProgram}
                  disabled={generating}
                  className="btn-primary w-full disabled:opacity-50"
                >
                  {generating ? "Generating..." : "Generate Program"}
                </button>
              )}
            </>
          )}

        </div>
      </main>

      <div className="md:hidden h-16" />
    </div>
  );
}
