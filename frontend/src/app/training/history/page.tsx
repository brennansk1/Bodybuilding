"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import NavBar from "@/components/NavBar";
import PageTitle from "@/components/PageTitle";
import ViltrumLoader from "@/components/ViltrumLoader";
import { api } from "@/lib/api";

interface SessionSummary {
  id: string;
  session_date: string;
  session_type: string;
  week_number: number;
  completed: boolean;
  set_count: number;
  exercises: string[];
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr + "T00:00:00");
  return d.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" });
}

function formatSessionType(type: string): string {
  return type
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

function SkeletonCard() {
  return (
    <div className="card animate-pulse space-y-3">
      <div className="flex items-center justify-between">
        <div className="h-4 bg-limestone rounded w-32" />
        <div className="h-5 bg-limestone rounded w-20" />
      </div>
      <div className="flex gap-2">
        <div className="h-4 bg-limestone rounded w-16" />
        <div className="h-4 bg-limestone rounded w-24" />
      </div>
      <div className="flex gap-1 flex-wrap">
        <div className="h-5 bg-limestone rounded w-20" />
        <div className="h-5 bg-limestone rounded w-28" />
        <div className="h-5 bg-limestone rounded w-16" />
      </div>
    </div>
  );
}

/** Soft categorical tint for session type — keeps history from reading as a column of red */
function sessionTypeBadge(type: string): string {
  const t = type.toLowerCase();
  if (t.includes("push") || t.includes("chest") || t.includes("shoulder")) return "bg-blush text-centurion border-terracotta";
  if (t.includes("pull") || t.includes("back") || t.includes("bicep"))     return "bg-viltrum-adriatic-bg text-adriatic border-adriatic/30";
  if (t.includes("leg")  || t.includes("quad") || t.includes("glute"))     return "bg-viltrum-laurel-bg text-laurel border-laurel/30";
  if (t.includes("arm")  || t.includes("tricep"))                          return "bg-viltrum-aureus-bg text-aureus border-aureus/30";
  return "bg-alabaster text-iron border-ash";
}

export default function TrainingHistoryPage() {
  const router = useRouter();
  const { user, loading, logout } = useAuth();
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [fetching, setFetching] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const LIMIT = 20;

  useEffect(() => {
    if (!loading && !user) { router.push("/auth/login"); return; }
    if (user) {
      api.get<SessionSummary[]>(`/engine2/sessions/history?limit=${LIMIT}&offset=0`)
        .then((data) => {
          setSessions(data);
          setOffset(data.length);
          setHasMore(data.length === LIMIT);
        })
        .catch(() => {})
        .finally(() => setFetching(false));
    }
  }, [user, loading, router]);

  const loadMore = async () => {
    setLoadingMore(true);
    try {
      const data = await api.get<SessionSummary[]>(
        `/engine2/sessions/history?limit=${LIMIT}&offset=${offset}`
      );
      setSessions((prev) => [...prev, ...data]);
      setOffset((prev) => prev + data.length);
      setHasMore(data.length === LIMIT);
    } catch {
      // silent
    } finally {
      setLoadingMore(false);
    }
  };

  if (loading || !user) return null;

  // Group sessions by week_number
  const byWeek: Record<number, SessionSummary[]> = {};
  sessions.forEach((s) => {
    if (!byWeek[s.week_number]) byWeek[s.week_number] = [];
    byWeek[s.week_number].push(s);
  });
  const weeks = Object.keys(byWeek)
    .map(Number)
    .sort((a, b) => b - a); // most recent week first

  return (
    <div className="min-h-screen">
      <NavBar username={user.username} onLogout={() => { logout(); router.push("/"); }} />

      <main className="container-app py-6">
        <div className="max-w-3xl mx-auto space-y-6">

          {/* Header */}
          <PageTitle
            text="Training History"
            actions={
              <a
                href="/training"
                className="btn-secondary text-sm px-3 py-2"
                aria-label="Back to Training"
              >
                ← Training
              </a>
            }
          />

          {/* Loading skeleton */}
          {fetching && (
            <div className="space-y-4">
              <SkeletonCard />
              <SkeletonCard />
              <SkeletonCard />
            </div>
          )}

          {/* Empty state */}
          {!fetching && sessions.length === 0 && (
            <div className="card text-center py-14 space-y-4">
              <div className="mx-auto w-14 h-14 rounded-full bg-blush flex items-center justify-center">
                <svg className="w-6 h-6 text-centurion" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
                  <path d="M3 3v18h18" />
                  <path d="M7 14l3-3 4 4 5-5" />
                </svg>
              </div>
              <div className="space-y-1.5">
                <p className="h-display-sm">No history yet</p>
                <p className="body-serif-sm italic text-iron max-w-md mx-auto">
                  Finish your first session and it lives here — every rep, every week, ready to compound.
                </p>
              </div>
              <a href="/training" className="btn-accent inline-block">
                Go to Training
              </a>
            </div>
          )}

          {/* Sessions grouped by week */}
          {!fetching && weeks.map((week) => (
            <div key={week} className="space-y-3">
              {/* Week divider */}
              <div className="flex items-center gap-3">
                <div className="flex-1 h-px bg-ash" />
                <span className="h-section text-travertine px-2">Week {week}</span>
                <div className="flex-1 h-px bg-ash" />
              </div>

              {byWeek[week].map((session) => (
                <div key={session.id} className="card hover:border-pumice transition-colors">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0 space-y-2">
                      {/* Date + completion */}
                      <div className="flex items-center gap-2.5 flex-wrap">
                        <span className="h-card text-obsidian">{formatDate(session.session_date)}</span>
                        {session.completed ? (
                          <span className="inline-flex items-center gap-1 text-[10px] tracking-[0.15em] uppercase text-laurel">
                            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                            </svg>
                            Done
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-[10px] tracking-[0.15em] uppercase text-travertine">
                            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                              <circle cx="12" cy="12" r="9" />
                            </svg>
                            Incomplete
                          </span>
                        )}
                      </div>

                      {/* Session type + week label */}
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className={`px-2 py-0.5 rounded text-[10px] tracking-[0.1em] uppercase font-medium border ${sessionTypeBadge(session.session_type)}`}>
                          {formatSessionType(session.session_type)}
                        </span>
                        <span className="text-[10px] tracking-[0.1em] uppercase text-travertine">Week {session.week_number}</span>
                        <span className="w-1 h-1 rounded-full bg-pewter" aria-hidden />
                        <span className="text-[10px] tracking-[0.1em] uppercase text-iron tabular-nums">{session.set_count} sets</span>
                      </div>

                      {/* Exercise tags */}
                      {session.exercises.length > 0 && (
                        <div className="flex flex-wrap gap-1 pt-1">
                          {session.exercises.map((ex) => (
                            <span
                              key={ex}
                              className="px-2 py-0.5 rounded bg-alabaster border border-ash text-[10px] text-iron"
                            >
                              {ex}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ))}

          {/* Load More */}
          {!fetching && hasMore && (
            <button
              onClick={loadMore}
              disabled={loadingMore}
              className="btn-secondary w-full disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {loadingMore ? (
                <>
                  <ViltrumLoader variant="compact" label="Loading more sessions" />
                  <span>Loading</span>
                </>
              ) : "Load More"}
            </button>
          )}

        </div>
      </main>

      <div className="md:hidden h-16" />
    </div>
  );
}
