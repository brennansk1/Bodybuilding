"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import NavBar from "@/components/NavBar";
import { api } from "@/lib/api";

interface PeakWeekDay {
  day: string;
  date: string | null;
  protocol_day: string;
  carbs_g: number;
  protein_g: number;
  fat_g: number;
  sodium_mg: number;
  water_ml: number;
  total_calories: number;
  notes: string;
}

interface PeakWeekResponse {
  protocol: PeakWeekDay[];
  show_date: string;
  days_out: number;
}

function protocolPhase(protocolDay: string): { label: string; className: string } {
  const d = protocolDay.toLowerCase();
  if (d.includes("deplet")) return { label: "Depletion", className: "bg-red-500/20 text-red-400" };
  if (d.includes("transit")) return { label: "Transition", className: "bg-yellow-500/20 text-yellow-400" };
  if (d.includes("load")) return { label: "Load", className: "bg-green-500/20 text-green-400" };
  if (d.includes("show")) return { label: "Show Day", className: "bg-jungle-accent/20 text-jungle-accent" };
  return { label: protocolDay.replace(/_/g, " "), className: "bg-jungle-deeper text-jungle-muted" };
}

function sodiumColor(mg: number): string {
  if (mg < 1000) return "text-green-400";
  if (mg < 2000) return "text-yellow-400";
  return "text-jungle-muted";
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "";
  const d = new Date(dateStr + "T00:00:00");
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function MacroPill({ label, value, unit, color }: { label: string; value: number; unit: string; color: string }) {
  return (
    <div className={`px-2 py-1 rounded-md bg-jungle-deeper text-center`}>
      <p className="text-[9px] text-jungle-dim uppercase tracking-wide">{label}</p>
      <p className={`text-xs font-bold ${color}`}>
        {Math.round(value)}<span className="font-normal text-jungle-dim">{unit}</span>
      </p>
    </div>
  );
}

function DayCard({ day, isToday }: { day: PeakWeekDay; isToday: boolean }) {
  const [open, setOpen] = useState(false);
  const phase = protocolPhase(day.protocol_day);

  return (
    <div
      className={`card space-y-3 ${isToday ? "border border-jungle-accent ring-1 ring-jungle-accent/30" : ""}`}
    >
      {/* Day header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-semibold text-sm">{day.day}</span>
            {isToday && (
              <span className="px-1.5 py-0.5 rounded bg-jungle-accent/20 text-jungle-accent text-[10px] font-medium">
                Today
              </span>
            )}
            {day.date && (
              <span className="text-xs text-jungle-dim">{formatDate(day.date)}</span>
            )}
          </div>
        </div>
        <span className={`px-2 py-0.5 rounded text-[10px] font-medium ${phase.className}`}>
          {phase.label}
        </span>
      </div>

      {/* Macro pills */}
      <div className="grid grid-cols-4 gap-1.5">
        <MacroPill label="Carbs" value={day.carbs_g} unit="g" color="text-jungle-accent" />
        <MacroPill label="Protein" value={day.protein_g} unit="g" color="text-green-400" />
        <MacroPill label="Fat" value={day.fat_g} unit="g" color="text-red-400" />
        <MacroPill label="Cal" value={day.total_calories} unit="" color="text-jungle-muted" />
      </div>

      {/* Sodium + Water */}
      <div className="flex items-center gap-4 text-xs">
        <div className="flex items-center gap-1">
          <span className="text-jungle-dim">Sodium:</span>
          <span className={`font-semibold ${sodiumColor(day.sodium_mg)}`}>
            {day.sodium_mg.toLocaleString()}mg
          </span>
        </div>
        <div className="flex items-center gap-1">
          <span className="text-jungle-dim">Water:</span>
          <span className="font-semibold text-jungle-muted">{day.water_ml.toLocaleString()}mL</span>
        </div>
      </div>

      {/* Collapsible notes */}
      {day.notes && (
        <div>
          <button
            onClick={() => setOpen(!open)}
            className="flex items-center gap-1.5 text-xs text-jungle-muted hover:text-jungle-accent transition-colors"
          >
            <svg
              className={`w-3.5 h-3.5 transition-transform ${open ? "rotate-180" : ""}`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
            Coaching Notes
          </button>
          {open && (
            <p className="mt-2 text-xs text-jungle-muted bg-jungle-deeper rounded-lg p-3 leading-relaxed">
              {day.notes}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

export default function PeakWeekPage() {
  const router = useRouter();
  const { user, loading, logout } = useAuth();
  const [data, setData] = useState<PeakWeekResponse | null>(null);
  const [fetching, setFetching] = useState(true);

  const today = new Date().toISOString().split("T")[0];

  useEffect(() => {
    if (!loading && !user) { router.push("/auth/login"); return; }
    if (user) {
      api.get<PeakWeekResponse>("/engine3/peak-week")
        .then(setData)
        .catch(() => {})
        .finally(() => setFetching(false));
    }
  }, [user, loading, router]);

  if (loading || !user) return null;

  const daysOut = data?.days_out ?? null;
  const showDate = data?.show_date ?? null;

  const badgeClass =
    daysOut !== null && daysOut <= 7
      ? "bg-red-500/20 text-red-400"
      : "bg-jungle-accent/20 text-jungle-accent";

  return (
    <div className="min-h-screen bg-jungle-dark">
      <NavBar username={user.username} onLogout={() => { logout(); router.push("/"); }} />

      <main className="container-app py-6">
        <div className="max-w-3xl mx-auto space-y-6">

          {/* Header */}
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-center gap-3">
              <a
                href="/nutrition"
                className="text-jungle-muted hover:text-jungle-accent transition-colors"
                aria-label="Back to Nutrition"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                </svg>
              </a>
              <div>
                <h1 className="text-2xl font-bold">
                  <span className="text-jungle-accent">Peak Week</span> Protocol
                </h1>
                {showDate && (
                  <p className="text-jungle-muted text-sm mt-0.5">
                    Show date: {formatDate(showDate)}
                  </p>
                )}
              </div>
            </div>
            {daysOut !== null && (
              <span className={`shrink-0 px-3 py-1.5 rounded-full text-sm font-bold ${badgeClass}`}>
                {daysOut}d out
              </span>
            )}
          </div>

          {/* Loading */}
          {fetching && (
            <div className="space-y-4">
              {[1, 2, 3, 4, 5, 6, 7].map((i) => (
                <div key={i} className="card animate-pulse space-y-3">
                  <div className="flex justify-between">
                    <div className="h-4 bg-jungle-deeper rounded w-20" />
                    <div className="h-5 bg-jungle-deeper rounded w-24" />
                  </div>
                  <div className="grid grid-cols-4 gap-1.5">
                    {[1, 2, 3, 4].map((j) => (
                      <div key={j} className="h-10 bg-jungle-deeper rounded-md" />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* No data */}
          {!fetching && !data && (
            <div className="card text-center py-16">
              <p className="text-jungle-muted text-lg font-medium">No peak week protocol available.</p>
              <p className="text-jungle-dim text-sm mt-2">
                A protocol will appear when your competition is within 21 days.
              </p>
              <a href="/nutrition" className="btn-secondary inline-block mt-5">
                Back to Nutrition
              </a>
            </div>
          )}

          {/* 7-day protocol */}
          {!fetching && data && (
            <>
              {/* Desktop: horizontal scroll container; stacks vertically on mobile */}
              <div className="hidden md:grid md:grid-cols-2 gap-4">
                {data.protocol.map((day) => (
                  <DayCard
                    key={day.day}
                    day={day}
                    isToday={day.date === today}
                  />
                ))}
              </div>
              <div className="md:hidden space-y-4">
                {data.protocol.map((day) => (
                  <DayCard
                    key={day.day}
                    day={day}
                    isToday={day.date === today}
                  />
                ))}
              </div>
            </>
          )}

          <a href="/nutrition" className="btn-secondary w-full text-center block">
            Back to Nutrition
          </a>

        </div>
      </main>

      <div className="md:hidden h-16" />
    </div>
  );
}
