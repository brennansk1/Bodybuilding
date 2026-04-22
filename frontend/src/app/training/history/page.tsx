"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import NavBar from "@/components/NavBar";
import PageTitle from "@/components/PageTitle";
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
        <div className="h-4 bg-jungle-deeper rounded w-32" />
        <div className="h-5 bg-jungle-deeper rounded w-20" />
      </div>
      <div className="flex gap-2">
        <div className="h-4 bg-jungle-deeper rounded w-16" />
        <div className="h-4 bg-jungle-deeper rounded w-24" />
      </div>
      <div className="flex gap-1 flex-wrap">
        <div className="h-5 bg-jungle-deeper rounded w-20" />
        <div className="h-5 bg-jungle-deeper rounded w-28" />
        <div className="h-5 bg-jungle-deeper rounded w-16" />
      </div>
    </div>
  );
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
            <div className="card text-center py-16">
              <p className="text-jungle-muted text-lg font-medium">No training history yet.</p>
              <p className="text-jungle-dim text-sm mt-2">
                Complete your first session to see it here.
              </p>
              <a href="/training" className="btn-primary inline-block mt-5">
                Go to Training
              </a>
            </div>
          )}

          {/* Sessions grouped by week */}
          {!fetching && weeks.map((week) => (
            <div key={week} className="space-y-3">
              {/* Week divider */}
              <div className="flex items-center gap-3">
                <div className="flex-1 h-px bg-jungle-border" />
                <span className="text-xs font-semibold text-jungle-muted uppercase tracking-widest px-2">
                  Week {week}
                </span>
                <div className="flex-1 h-px bg-jungle-border" />
              </div>

              {byWeek[week].map((session) => (
                <div key={session.id} className="card">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      {/* Date + completion */}
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-sm font-semibold">{formatDate(session.session_date)}</span>
                        {session.completed ? (
                          <span className="inline-flex items-center gap-1 text-xs text-green-400">
                            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                            </svg>
                            Done
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-xs text-jungle-dim">
                            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <circle cx="12" cy="12" r="9" strokeWidth={2} />
                            </svg>
                            Incomplete
                          </span>
                        )}
                      </div>

                      {/* Session type + week label */}
                      <div className="flex items-center gap-2 mt-1.5 flex-wrap">
                        <span className="px-2 py-0.5 rounded bg-jungle-accent/20 text-jungle-accent text-xs font-medium">
                          {formatSessionType(session.session_type)}
                        </span>
                        <span className="text-xs text-jungle-dim">Week {session.week_number}</span>
                        <span className="text-xs text-jungle-muted">{session.set_count} sets</span>
                      </div>

                      {/* Exercise tags */}
                      {session.exercises.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-2">
                          {session.exercises.map((ex) => (
                            <span
                              key={ex}
                              className="px-1.5 py-0.5 rounded bg-jungle-deeper text-[10px] text-jungle-muted"
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
              className="btn-secondary w-full disabled:opacity-50"
            >
              {loadingMore ? "Loading..." : "Load More"}
            </button>
          )}

        </div>
      </main>

      <div className="md:hidden h-16" />
    </div>
  );
}
