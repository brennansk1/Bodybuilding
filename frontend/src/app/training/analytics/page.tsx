"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import NavBar from "@/components/NavBar";
import VolumeChart from "@/components/VolumeChart";
import MiniLineChart from "@/components/MiniLineChart";
import { api } from "@/lib/api";

// ─── Interfaces ──────────────────────────────────────────────────────────────

interface VolumeWeek {
  week_number: number;
  total_sets: number;
  by_muscle: Record<string, number>;
}

interface VolumeHistoryResponse {
  weeks: VolumeWeek[];
}

interface StrengthPoint {
  date: string;
  estimated_1rm: number;
  weight_kg: number;
  reps: number;
}

interface StrengthHistoryResponse {
  exercises: Record<string, StrengthPoint[]>;
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function TrainingAnalyticsPage() {
  const router = useRouter();
  const { user, loading, logout } = useAuth();

  const [volumeData, setVolumeData] = useState<VolumeHistoryResponse | null>(null);
  const [strengthData, setStrengthData] = useState<StrengthHistoryResponse | null>(null);
  const [fetching, setFetching] = useState(true);
  const [selectedWeek, setSelectedWeek] = useState<number | null>(null);
  const [useLbs, setUseLbs] = useState(false);

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
      Promise.all([
        api.get<VolumeHistoryResponse>("/engine2/volume-history").catch(() => null),
        api.get<StrengthHistoryResponse>("/engine2/strength-history").catch(() => null),
      ])
        .then(([vol, str]) => {
          if (vol) {
            setVolumeData(vol);
            // Default to most recent week
            if (vol.weeks.length > 0) {
              setSelectedWeek(vol.weeks[vol.weeks.length - 1].week_number);
            }
          }
          if (str) setStrengthData(str);
        })
        .finally(() => setFetching(false));
    }
  }, [user, loading, router]);

  if (loading || !user) return null;

  const m = useLbs ? 2.20462 : 1;
  const unit = useLbs ? "lbs" : "kg";

  // Current week volume data
  const currentWeekData = volumeData?.weeks.find((w) => w.week_number === selectedWeek);
  const volumeChartData = currentWeekData
    ? Object.entries(currentWeekData.by_muscle).map(([muscle, sets]) => ({
        muscle,
        sets,
      }))
    : [];

  // Total volume trend across weeks
  const volumeTrend = volumeData?.weeks.map((w) => ({
    label: `Wk ${w.week_number}`,
    value: w.total_sets,
  })) ?? [];

  // Strength exercises
  const strengthExercises = strengthData ? Object.keys(strengthData.exercises) : [];

  return (
    <div className="min-h-screen">
      <NavBar username={user.username} onLogout={() => { logout(); router.push("/"); }} />

      <main className="px-3 py-4 pb-20">
        <div className="max-w-lg mx-auto space-y-4">
          {/* Header */}
          <div className="flex items-center gap-3">
            <a href="/training" className="text-jungle-muted hover:text-jungle-accent transition-colors" aria-label="Back">
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
            </a>
            <div>
              <h1 className="text-xl font-bold">
                <span className="text-jungle-accent">Training</span> Analytics
              </h1>
              <p className="text-jungle-muted text-xs mt-0.5">
                Volume trends and strength progression
              </p>
            </div>
          </div>

          {/* Loading */}
          {fetching && (
            <div className="space-y-4">
              {[1, 2, 3].map((i) => (
                <div key={i} className="card animate-pulse space-y-3">
                  <div className="h-4 bg-jungle-deeper rounded w-24" />
                  <div className="h-28 bg-jungle-deeper rounded-lg" />
                </div>
              ))}
            </div>
          )}

          {/* No data */}
          {!fetching && !volumeData && !strengthData && (
            <div className="card text-center py-12">
              <p className="text-jungle-muted text-lg font-medium">No analytics yet</p>
              <p className="text-jungle-dim text-sm mt-1">
                Complete a few training sessions to see your trends.
              </p>
              <a href="/training" className="btn-primary inline-block mt-4">
                Go to Training
              </a>
            </div>
          )}

          {!fetching && (
            <>
              {/* ── Weekly Volume Total Trend ── */}
              {volumeTrend.length >= 2 && (
                <div className="card space-y-3">
                  <h3 className="text-xs font-semibold text-jungle-muted uppercase tracking-wider">
                    Weekly Volume Trend
                  </h3>
                  <p className="text-[10px] text-jungle-dim">Total working sets per week</p>
                  <MiniLineChart data={volumeTrend} height={100} color="#c8a84e" />
                </div>
              )}

              {/* ── Volume by Muscle Group ── */}
              {volumeData && volumeData.weeks.length > 0 && (
                <div className="card space-y-3">
                  <div className="flex items-center justify-between">
                    <h3 className="text-xs font-semibold text-jungle-muted uppercase tracking-wider">
                      Volume by Muscle
                    </h3>

                    {/* Week selector */}
                    <div className="flex gap-1">
                      {volumeData.weeks.slice(-4).map((w) => (
                        <button
                          key={w.week_number}
                          onClick={() => setSelectedWeek(w.week_number)}
                          className={`px-2 py-0.5 rounded text-[10px] font-medium transition-colors ${
                            selectedWeek === w.week_number
                              ? "bg-jungle-accent text-white"
                              : "bg-jungle-deeper text-jungle-dim hover:text-jungle-muted"
                          }`}
                        >
                          Wk {w.week_number}
                        </button>
                      ))}
                    </div>
                  </div>

                  {volumeChartData.length > 0 ? (
                    <VolumeChart data={volumeChartData} />
                  ) : (
                    <p className="text-jungle-dim text-xs text-center py-4">No data for this week</p>
                  )}

                  {currentWeekData && (
                    <p className="text-[10px] text-jungle-dim text-center">
                      Total: {currentWeekData.total_sets} working sets
                    </p>
                  )}
                </div>
              )}

              {/* ── Strength Progression ── */}
              {strengthExercises.length > 0 && (
                <div className="card space-y-3">
                  <h3 className="text-xs font-semibold text-jungle-muted uppercase tracking-wider">
                    Strength Progression
                  </h3>
                  <p className="text-[10px] text-jungle-dim">Estimated 1RM trends for your top lifts</p>

                  <div className="space-y-4">
                    {strengthExercises.map((exercise) => {
                      const points = strengthData!.exercises[exercise];
                      if (points.length < 2) return null;

                      const chartData = points.map((p) => ({
                        label: p.date,
                        value: Math.round(p.estimated_1rm * m),
                      }));

                      const latest = points[points.length - 1];
                      const first = points[0];
                      const delta = latest.estimated_1rm - first.estimated_1rm;

                      return (
                        <div key={exercise}>
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-xs text-jungle-text font-medium truncate">{exercise}</span>
                            <div className="flex items-center gap-2 shrink-0">
                              <span className="text-xs text-jungle-accent font-bold">
                                {(latest.estimated_1rm * m).toFixed(0)} {unit}
                              </span>
                              {delta !== 0 && (
                                <span className={`text-[10px] font-semibold ${delta > 0 ? "text-green-400" : "text-red-400"}`}>
                                  {delta > 0 ? "+" : ""}{(delta * m).toFixed(0)}
                                </span>
                              )}
                            </div>
                          </div>
                          <MiniLineChart data={chartData} height={80} color={delta >= 0 ? "#4ade80" : "#f87171"} showPoints={false} />
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Quick links */}
              <div className="flex gap-3">
                <a href="/training" className="flex-1 btn-secondary text-center text-sm py-2.5">
                  Today&apos;s Workout
                </a>
                <a href="/training/history" className="flex-1 btn-secondary text-center text-sm py-2.5">
                  Session History
                </a>
              </div>
            </>
          )}
        </div>
      </main>
    </div>
  );
}
