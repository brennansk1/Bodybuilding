"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import NavBar from "@/components/NavBar";
import WeightTrendChart from "@/components/WeightTrendChart";
import CoachingFeedbackCard, { type CoachingMessage } from "@/components/CoachingFeedbackCard";
import { api } from "@/lib/api";

// ─── Interfaces ──────────────────────────────────────────────────────────────

interface WeightPoint {
  date: string;
  weight_kg: number;
  rolling_avg?: number;
}

interface ReviewData {
  week_number: number;
  weight: {
    current_avg: number;
    previous_avg: number | null;
    delta_kg: number | null;
    trend: WeightPoint[];
  };
  training: {
    sessions_completed: number;
    sessions_scheduled: number;
    completion_pct: number;
    total_sets: number;
  };
  nutrition: {
    avg_adherence_pct: number;
    days_logged: number;
    entries: { date: string; nutrition: number; training: number; overall: number }[];
  };
  photos: {
    front_photo_url: string | null;
    back_photo_url: string | null;
    side_left_photo_url: string | null;
    side_right_photo_url: string | null;
  };
  pds: {
    current: number | null;
    previous: number | null;
    delta: number | null;
    tier: string | null;
  };
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function DeltaBadge({ value, unit, inverse = false }: { value: number | null; unit: string; inverse?: boolean }) {
  if (value == null || value === 0) return <span className="text-jungle-dim text-xs">—</span>;
  // For weight in a cut, negative is good (inverse=true). For PDS, positive is good.
  const isGood = inverse ? value < 0 : value > 0;
  const color = isGood ? "text-green-400" : "text-red-400";
  const arrow = value > 0 ? "↑" : "↓";
  return (
    <span className={`text-xs font-semibold ${color}`}>
      {arrow} {Math.abs(value).toFixed(1)}{unit}
    </span>
  );
}

function StatCard({
  label,
  value,
  sub,
  accent = false,
}: {
  label: string;
  value: string | number;
  sub?: React.ReactNode;
  accent?: boolean;
}) {
  return (
    <div className="bg-jungle-deeper rounded-xl p-3 text-center">
      <p className="text-[10px] text-jungle-dim uppercase tracking-wider">{label}</p>
      <p className={`text-lg font-bold mt-0.5 ${accent ? "text-jungle-accent" : "text-jungle-text"}`}>
        {value}
      </p>
      {sub && <div className="mt-0.5">{sub}</div>}
    </div>
  );
}

function AdherenceBar({ pct }: { pct: number }) {
  const color =
    pct >= 90 ? "bg-green-400" : pct >= 75 ? "bg-jungle-accent" : pct >= 60 ? "bg-yellow-400" : "bg-red-400";
  return (
    <div className="h-2 bg-jungle-deeper rounded-full overflow-hidden">
      <div className={`h-full rounded-full transition-all duration-500 ${color}`} style={{ width: `${Math.min(pct, 100)}%` }} />
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function WeeklyReviewPage() {
  const router = useRouter();
  const { user, loading, logout } = useAuth();
  const [review, setReview] = useState<ReviewData | null>(null);
  const [fetching, setFetching] = useState(true);
  const [useLbs, setUseLbs] = useState(false);
  const [photoCompare, setPhotoCompare] = useState<string | null>(null);
  const [coachingFeedbackId, setCoachingFeedbackId] = useState<string | null>(null);
  const [coachingMessages, setCoachingMessages] = useState<CoachingMessage[]>([]);

  useEffect(() => {
    if (typeof window !== "undefined") {
      setUseLbs(localStorage.getItem("useLbs") === "true");
    }
  }, []);

  useEffect(() => {
    if (!loading && !user) {
      router.push("/auth/login");
      return;
    }
    if (user) {
      api
        .get<ReviewData>("/checkin/weekly/review")
        .then(setReview)
        .catch(() => {})
        .finally(() => setFetching(false));
      api
        .get<{ id: string | null; messages: CoachingMessage[] }>("/checkin/coaching-feedback")
        .then((r) => { setCoachingFeedbackId(r.id); setCoachingMessages(r.messages || []); })
        .catch(() => {});
    }
  }, [user, loading, router]);

  if (loading || !user) return null;

  const m = useLbs ? 2.20462 : 1;
  const unit = useLbs ? "lbs" : "kg";

  return (
    <div className="min-h-screen">
      <NavBar username={user.username} onLogout={() => { logout(); router.push("/"); }} />

      <main className="px-3 py-4 pb-20">
        <div className="max-w-lg mx-auto space-y-4">
          {/* Header */}
          <div className="flex items-center gap-3">
            <a href="/checkin" className="text-jungle-muted hover:text-jungle-accent transition-colors" aria-label="Back">
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
            </a>
            <div>
              <h1 className="text-xl font-bold">
                <span className="text-jungle-accent">Weekly</span> Review
              </h1>
              {review && (
                <p className="text-jungle-muted text-xs mt-0.5">
                  Week {review.week_number} Summary
                </p>
              )}
            </div>
          </div>

          {/* Coaching feedback — surfaced at the top of review */}
          {coachingMessages.length > 0 && (
            <div className="card mb-4">
              <CoachingFeedbackCard
                feedbackId={coachingFeedbackId}
                messages={coachingMessages}
                onDismiss={() => { setCoachingMessages([]); setCoachingFeedbackId(null); }}
              />
            </div>
          )}

          {/* Loading */}
          {fetching && (
            <div className="space-y-4">
              {[1, 2, 3].map((i) => (
                <div key={i} className="card animate-pulse space-y-3">
                  <div className="h-4 bg-jungle-deeper rounded w-24" />
                  <div className="h-20 bg-jungle-deeper rounded-lg" />
                </div>
              ))}
            </div>
          )}

          {/* No data */}
          {!fetching && !review && (
            <div className="card text-center py-12">
              <p className="text-jungle-muted text-lg font-medium">No review data yet</p>
              <p className="text-jungle-dim text-sm mt-1">
                Complete a weekly check-in to see your review here.
              </p>
              <a href="/checkin" className="btn-primary inline-block mt-4">
                Go to Check-In
              </a>
            </div>
          )}

          {/* Review Content */}
          {review && (
            <>
              {/* ── Weight Panel ── */}
              <div className="card space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-semibold text-jungle-muted uppercase tracking-wider">Weight</h3>
                  <DeltaBadge value={review.weight.delta_kg ? review.weight.delta_kg * m : null} unit={unit} inverse />
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <StatCard
                    label="This Week Avg"
                    value={`${(review.weight.current_avg * m).toFixed(1)} ${unit}`}
                    accent
                  />
                  <StatCard
                    label="Last Week Avg"
                    value={
                      review.weight.previous_avg
                        ? `${(review.weight.previous_avg * m).toFixed(1)} ${unit}`
                        : "—"
                    }
                  />
                </div>

                {review.weight.trend.length >= 2 && (
                  <WeightTrendChart data={review.weight.trend} useLbs={useLbs} height={140} />
                )}
              </div>

              {/* ── Training Panel ── */}
              <div className="card space-y-3">
                <h3 className="text-xs font-semibold text-jungle-muted uppercase tracking-wider">Training</h3>

                <div className="grid grid-cols-3 gap-2">
                  <StatCard
                    label="Sessions"
                    value={`${review.training.sessions_completed}/${review.training.sessions_scheduled}`}
                    accent
                  />
                  <StatCard
                    label="Completion"
                    value={`${review.training.completion_pct}%`}
                    sub={<AdherenceBar pct={review.training.completion_pct} />}
                  />
                  <StatCard label="Total Sets" value={review.training.total_sets} />
                </div>
              </div>

              {/* ── Nutrition Panel ── */}
              <div className="card space-y-3">
                <h3 className="text-xs font-semibold text-jungle-muted uppercase tracking-wider">Nutrition Adherence</h3>

                <div className="grid grid-cols-2 gap-2">
                  <StatCard
                    label="Avg Adherence"
                    value={review.nutrition.avg_adherence_pct != null ? `${review.nutrition.avg_adherence_pct.toFixed(0)}%` : "—"}
                    sub={review.nutrition.avg_adherence_pct != null ? <AdherenceBar pct={review.nutrition.avg_adherence_pct} /> : undefined}
                    accent
                  />
                  <StatCard label="Days Logged" value={`${review.nutrition.days_logged}/7`} />
                </div>

                {/* Daily adherence bars */}
                {review.nutrition.entries.length > 0 && (
                  <div className="space-y-1">
                    <p className="text-[10px] text-jungle-dim uppercase tracking-wider">Daily</p>
                    {review.nutrition.entries.map((entry) => {
                      const dayLabel = new Date(entry.date + "T00:00:00").toLocaleDateString("en-US", {
                        weekday: "short",
                      });
                      return (
                        <div key={entry.date} className="flex items-center gap-2">
                          <span className="text-[10px] text-jungle-dim w-7 shrink-0">{dayLabel}</span>
                          <div className="flex-1">
                            <AdherenceBar pct={entry.overall} />
                          </div>
                          <span className="text-[10px] text-jungle-muted w-8 text-right shrink-0">
                            {entry.overall.toFixed(0)}%
                          </span>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* ── PDS Panel ── */}
              {review.pds.current != null && (
                <div className="card space-y-3">
                  <div className="flex items-center justify-between">
                    <h3 className="text-xs font-semibold text-jungle-muted uppercase tracking-wider">
                      Physique Score
                    </h3>
                    <DeltaBadge value={review.pds.delta} unit="pts" />
                  </div>

                  <div className="grid grid-cols-2 gap-2">
                    <StatCard
                      label="Current PDS"
                      value={review.pds.current.toFixed(1)}
                      sub={
                        review.pds.tier && (
                          <span className="text-[10px] text-jungle-accent capitalize">{review.pds.tier}</span>
                        )
                      }
                      accent
                    />
                    <StatCard
                      label="Previous"
                      value={review.pds.previous != null ? review.pds.previous.toFixed(1) : "—"}
                    />
                  </div>
                </div>
              )}

              {/* ── Photos Panel ── */}
              {(review.photos.front_photo_url || review.photos.back_photo_url) && (
                <div className="card space-y-3">
                  <h3 className="text-xs font-semibold text-jungle-muted uppercase tracking-wider">Check-In Photos</h3>

                  <div className="grid grid-cols-2 gap-2">
                    {[
                      { url: review.photos.front_photo_url, label: "Front" },
                      { url: review.photos.back_photo_url, label: "Back" },
                      { url: review.photos.side_left_photo_url, label: "Left" },
                      { url: review.photos.side_right_photo_url, label: "Right" },
                    ]
                      .filter((p) => p.url)
                      .map((photo) => (
                        <button
                          key={photo.label}
                          onClick={() => setPhotoCompare(photo.url)}
                          className="relative aspect-[3/4] bg-jungle-deeper rounded-lg overflow-hidden border border-jungle-border hover:border-jungle-accent transition-colors"
                        >
                          <img
                            src={photo.url!}
                            alt={photo.label}
                            className="w-full h-full object-cover"
                          />
                          <span className="absolute bottom-1 left-1 text-[9px] bg-viltrum-obsidian/40 px-1.5 py-0.5 rounded text-white">
                            {photo.label}
                          </span>
                        </button>
                      ))}
                  </div>
                </div>
              )}

              {/* ── Quick Actions ── */}
              <div className="flex gap-3">
                <a href="/checkin" className="flex-1 btn-secondary text-center text-sm py-2.5">
                  New Check-In
                </a>
                <a href="/progress" className="flex-1 btn-secondary text-center text-sm py-2.5">
                  Full Progress
                </a>
              </div>
            </>
          )}
        </div>
      </main>

      {/* Photo fullscreen modal */}
      {photoCompare && (
        <div className="fixed inset-0 z-50 bg-viltrum-obsidian/55 flex items-center justify-center p-4" onClick={() => setPhotoCompare(null)}>
          <img src={photoCompare} alt="Photo" className="max-w-full max-h-full object-contain rounded-lg" />
          <button
            onClick={() => setPhotoCompare(null)}
            className="absolute top-4 right-4 text-white/60 hover:text-white text-2xl"
          >
            ×
          </button>
        </div>
      )}
    </div>
  );
}
