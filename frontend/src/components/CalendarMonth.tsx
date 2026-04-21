"use client";

import { useState } from "react";
import { api } from "@/lib/api";

// ─── Types ──────────────────────────────────────────────────────────────────

interface ScheduledSession {
  id: string;
  session_date: string;
  session_type: string;
  completed: boolean;
  is_deload: boolean;
  primary_muscles?: string[];
}

interface SessionSet {
  exercise_name: string;
  muscle_group: string;
  set_number: number;
  prescribed_reps: number | null;
  prescribed_weight_kg: number | null;
  is_warmup: boolean;
}

interface SessionPreview {
  session_type: string;
  session_date: string;
  week_number: number;
  completed: boolean;
  sets: SessionSet[];
}

interface CalendarMonthProps {
  sessions: ScheduledSession[];
  today: string;
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function formatSessionType(type: string): string {
  return type.split("_").map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(" ");
}

function dotColor(session: ScheduledSession, today: string): string {
  if (session.completed) return "bg-green-400";
  if (session.session_date < today) return "bg-jungle-dim";
  if (session.session_date === today) return "bg-jungle-accent animate-pulse";
  return "bg-jungle-accent/60";
}

function sessionsByDate(sessions: ScheduledSession[]): Record<string, ScheduledSession> {
  const map: Record<string, ScheduledSession> = {};
  for (const s of sessions) map[s.session_date] = s;
  return map;
}

// ─── Component ───────────────────────────────────────────────────────────────

export default function CalendarMonth({ sessions, today }: CalendarMonthProps) {
  const now = new Date(today + "T00:00:00");
  const [viewYear, setViewYear] = useState(now.getFullYear());
  const [viewMonth, setViewMonth] = useState(now.getMonth()); // 0-indexed
  const [previewDate, setPreviewDate] = useState<string | null>(null);
  const [preview, setPreview] = useState<SessionPreview | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);

  const sessionMap = sessionsByDate(sessions);

  // Build calendar grid
  const firstDay = new Date(viewYear, viewMonth, 1);
  const lastDay = new Date(viewYear, viewMonth + 1, 0);
  const startDow = (firstDay.getDay() + 6) % 7; // Mon=0

  const cells: (number | null)[] = [
    ...Array(startDow).fill(null),
    ...Array.from({ length: lastDay.getDate() }, (_, i) => i + 1),
  ];
  // Pad to complete row
  while (cells.length % 7 !== 0) cells.push(null);

  const monthLabel = firstDay.toLocaleDateString("en-US", { month: "long", year: "numeric" });
  const DAY_HEADERS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

  function toISO(day: number): string {
    const m = String(viewMonth + 1).padStart(2, "0");
    const d = String(day).padStart(2, "0");
    return `${viewYear}-${m}-${d}`;
  }

  function prevMonth() {
    if (viewMonth === 0) { setViewYear(y => y - 1); setViewMonth(11); }
    else setViewMonth(m => m - 1);
  }

  function nextMonth() {
    if (viewMonth === 11) { setViewYear(y => y + 1); setViewMonth(0); }
    else setViewMonth(m => m + 1);
  }

  async function openPreview(dateStr: string) {
    const session = sessionMap[dateStr];
    if (!session) return;
    setPreviewDate(dateStr);
    setPreview(null);
    setPreviewLoading(true);
    try {
      const data = await api.get<SessionPreview>(`/engine2/session/${dateStr}`);
      setPreview(data);
    } catch {
      // session data unavailable
    } finally {
      setPreviewLoading(false);
    }
  }

  // Group sets by exercise for the preview modal
  const previewExercises: Record<string, SessionSet[]> = {};
  if (preview) {
    for (const set of preview.sets) {
      if (set.is_warmup) continue;
      if (!previewExercises[set.exercise_name]) previewExercises[set.exercise_name] = [];
      previewExercises[set.exercise_name].push(set);
    }
  }

  return (
    <div className="space-y-3">
      {/* Month navigation */}
      <div className="flex items-center justify-between">
        <button
          onClick={prevMonth}
          className="p-1.5 rounded-lg hover:bg-jungle-deeper text-jungle-muted hover:text-jungle-accent transition-colors"
          aria-label="Previous month"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </button>
        <span className="text-sm font-semibold text-jungle-text">{monthLabel}</span>
        <button
          onClick={nextMonth}
          className="p-1.5 rounded-lg hover:bg-jungle-deeper text-jungle-muted hover:text-jungle-accent transition-colors"
          aria-label="Next month"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
        </button>
      </div>

      {/* Day headers */}
      <div className="grid grid-cols-7 gap-0.5">
        {DAY_HEADERS.map((d) => (
          <div key={d} className="text-center text-[9px] font-bold text-jungle-dim uppercase py-1">
            {d}
          </div>
        ))}
      </div>

      {/* Calendar grid */}
      <div className="grid grid-cols-7 gap-0.5">
        {cells.map((day, idx) => {
          if (!day) {
            return <div key={idx} className="aspect-square" />;
          }
          const dateStr = toISO(day);
          const session = sessionMap[dateStr];
          const isToday = dateStr === today;
          const isFuture = dateStr > today;
          const isClickable = !!session;

          return (
            <button
              key={idx}
              onClick={() => isClickable && openPreview(dateStr)}
              disabled={!isClickable}
              className={`
                aspect-square rounded-lg flex flex-col items-center justify-center gap-0.5 transition-all
                ${isToday ? "ring-2 ring-jungle-accent" : ""}
                ${session
                  ? isFuture
                    ? "bg-jungle-deeper border border-jungle-accent/30 hover:border-jungle-accent/60 cursor-pointer active:scale-95"
                    : session.completed
                    ? "bg-green-500/10 border border-green-500/30 cursor-pointer"
                    : "bg-jungle-deeper border border-jungle-border cursor-pointer hover:border-jungle-muted"
                  : "bg-jungle-deeper/30 border border-jungle-border/10"
                }
              `}
            >
              <span className={`text-[10px] font-semibold leading-none ${
                isToday ? "text-jungle-accent" : session ? "text-jungle-muted" : "text-jungle-dim/50"
              }`}>
                {day}
              </span>
              {session && (
                <div className={`w-1.5 h-1.5 rounded-full ${dotColor(session, today)}`} />
              )}
            </button>
          );
        })}
      </div>

      {/* Legend */}
      <div className="flex gap-3 text-[9px] text-jungle-dim flex-wrap">
        <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-green-400 inline-block" /> Done</span>
        <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-jungle-accent/60 inline-block" /> Upcoming</span>
        <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-jungle-dim inline-block" /> Missed</span>
      </div>

      {/* Preview modal */}
      {previewDate && (
        <div
          className="fixed inset-0 bg-viltrum-obsidian/45 z-50 flex items-end justify-center p-4 sm:items-center"
          onClick={() => setPreviewDate(null)}
        >
          <div
            className="bg-jungle-card border border-jungle-border rounded-2xl w-full max-w-sm max-h-[80vh] overflow-y-auto p-4 space-y-3"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-jungle-muted">
                  {new Date(previewDate + "T00:00:00").toLocaleDateString("en-US", { weekday: "long", month: "short", day: "numeric" })}
                </p>
                {preview && (
                  <p className="text-base font-bold text-jungle-text mt-0.5">
                    {formatSessionType(preview.session_type)}
                    {preview.completed && <span className="ml-2 text-xs text-green-400 font-normal">✓ Completed</span>}
                  </p>
                )}
              </div>
              <button
                onClick={() => setPreviewDate(null)}
                className="p-1.5 rounded-lg text-jungle-muted hover:text-jungle-text transition-colors"
                aria-label="Close"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {previewLoading ? (
              <div className="space-y-2 animate-pulse">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="h-10 bg-jungle-deeper rounded-lg" />
                ))}
              </div>
            ) : preview ? (
              <div className="space-y-2">
                {Object.entries(previewExercises).map(([exName, sets]) => {
                  const firstSet = sets[0];
                  return (
                    <div key={exName} className="bg-jungle-deeper rounded-lg px-3 py-2">
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <p className="text-xs font-semibold text-jungle-text">{exName}</p>
                          <p className="text-[10px] text-jungle-dim capitalize">{firstSet.muscle_group}</p>
                        </div>
                        <div className="text-right shrink-0">
                          <p className="text-xs font-bold text-jungle-accent">
                            {sets.length} × {firstSet.prescribed_reps ?? "AMRAP"}
                          </p>
                          {firstSet.prescribed_weight_kg != null && firstSet.prescribed_weight_kg > 0 && (
                            <p className="text-[10px] text-jungle-muted">
                              {firstSet.prescribed_weight_kg}kg
                            </p>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
                {Object.keys(previewExercises).length === 0 && (
                  <p className="text-xs text-jungle-dim text-center py-2">No exercise details yet</p>
                )}
              </div>
            ) : (
              <p className="text-xs text-jungle-dim text-center py-4">Session preview unavailable</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
