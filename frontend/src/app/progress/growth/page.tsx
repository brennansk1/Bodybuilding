"use client";

/**
 * V3.P11 — Per-muscle growth timeline.
 *
 * For each body site the user tracks, render a 52-week line chart of
 * circumference over time with acceleration windows annotated. Answers
 * "what worked?" by showing the growth rate vs baseline for each period.
 */

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import NavBar from "@/components/NavBar";
import PageTitle from "@/components/PageTitle";
import ViltrumLoader from "@/components/ViltrumLoader";
import { api } from "@/lib/api";
import type { MuscleTimelineResponse } from "@/lib/types";

const SITES: Array<{ key: string; label: string }> = [
  { key: "shoulders",   label: "Shoulders" },
  { key: "chest",       label: "Chest" },
  { key: "waist",       label: "Waist" },
  { key: "bicep_left",  label: "Bicep (L)" },
  { key: "bicep_right", label: "Bicep (R)" },
  { key: "forearm_left",label: "Forearm (L)" },
  { key: "forearm_right",label:"Forearm (R)" },
  { key: "thigh_left",  label: "Thigh (L)" },
  { key: "thigh_right", label: "Thigh (R)" },
  { key: "calf_left",   label: "Calf (L)" },
  { key: "calf_right",  label: "Calf (R)" },
  { key: "neck",        label: "Neck" },
  { key: "glutes",      label: "Glutes" },
  { key: "hips",        label: "Hips" },
  { key: "back_width",  label: "Back Width" },
];

export default function GrowthTimelinePage() {
  const router = useRouter();
  const { user, loading, logout } = useAuth();
  const [site, setSite] = useState<string>("bicep_left");
  const [weeks, setWeeks] = useState<number>(52);
  const [data, setData] = useState<MuscleTimelineResponse | null>(null);
  const [fetching, setFetching] = useState(true);

  useEffect(() => {
    if (!loading && !user) { router.push("/auth/login"); return; }
    if (!user) return;
    setFetching(true);
    api.get<MuscleTimelineResponse>(`/insights/muscle-timeline/${site}?weeks=${weeks}`)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setFetching(false));
  }, [user, loading, router, site, weeks]);

  if (loading || !user) return null;

  return (
    <div className="min-h-screen">
      <NavBar username={user.username} onLogout={() => { logout(); router.push("/"); }} />
      <main className="container-app py-6">
        <div className="max-w-3xl mx-auto space-y-5">
          <PageTitle
            text="Growth Timeline"
            actions={
              <a href="/progress" className="btn-secondary text-sm px-3 py-2">
                ← Progress
              </a>
            }
          />

          <p className="body-serif-sm italic text-iron text-sm leading-relaxed">
            Per-site circumference over time. The app flags acceleration windows — periods when growth outpaced
            baseline — so you can correlate progress with the split + volume you ran at the time.
          </p>

          <div className="card space-y-3">
            <div className="flex items-baseline justify-between gap-3 flex-wrap">
              <div>
                <label className="h-section text-travertine">Site</label>
                <select
                  value={site}
                  onChange={(e) => setSite(e.target.value)}
                  className="input-field text-sm py-2 px-3 mt-1 bg-white"
                >
                  {SITES.map((s) => (
                    <option key={s.key} value={s.key}>{s.label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="h-section text-travertine">Window</label>
                <div className="flex gap-1 mt-1">
                  {[12, 26, 52, 104].map((w) => (
                    <button
                      key={w}
                      type="button"
                      onClick={() => setWeeks(w)}
                      className={`px-2.5 py-1.5 text-xs rounded border tabular-nums ${
                        weeks === w
                          ? "bg-adriatic text-white border-adriatic"
                          : "border-ash hover:border-pewter text-iron"
                      }`}
                    >
                      {w}w
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {fetching ? (
              <div className="py-16 flex justify-center"><ViltrumLoader variant="compact" /></div>
            ) : (
              <TimelineChart data={data} />
            )}
          </div>
        </div>
      </main>
      <div className="md:hidden h-16" />
    </div>
  );
}

function TimelineChart({ data }: { data: MuscleTimelineResponse | null }) {
  const series = useMemo(() => data?.series ?? [], [data]);

  if (series.length < 2) {
    return (
      <div className="text-center py-10">
        <p className="text-sm text-travertine">Not enough data yet.</p>
        <p className="text-[11px] text-iron body-serif-sm italic mt-1">
          Log at least two tape measurements for this site to see a trend.
        </p>
      </div>
    );
  }

  const values = series.map((p) => p.value_cm);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = Math.max(0.5, max - min);

  const W = 720;
  const H = 220;
  const pad = 24;
  const scaleX = (i: number) => pad + (i / Math.max(1, series.length - 1)) * (W - pad * 2);
  const scaleY = (v: number) => H - pad - ((v - min) / range) * (H - pad * 2);

  const path = values.map((v, i) => `${i === 0 ? "M" : "L"}${scaleX(i).toFixed(1)},${scaleY(v).toFixed(1)}`).join(" ");

  // Highlight acceleration windows — find series index ranges by date
  const dateIndex = new Map(series.map((p, i) => [p.date, i]));
  const accelRects = (data?.acceleration_windows ?? []).map((w) => {
    const a = dateIndex.get(w.start_date);
    const b = dateIndex.get(w.end_date);
    if (a == null || b == null) return null;
    return {
      x1: scaleX(a),
      x2: scaleX(b),
      rate: w.rate_vs_baseline,
    };
  }).filter(Boolean);

  const first = values[0];
  const latest = values[values.length - 1];
  const delta = latest - first;
  const pct = first > 0 ? (delta / first) * 100 : 0;

  return (
    <div className="space-y-3">
      <div className="flex items-baseline justify-between gap-3">
        <div>
          <div className="text-2xl font-semibold tabular-nums text-obsidian">
            {latest.toFixed(1)}<span className="text-sm ml-1 text-travertine">cm</span>
          </div>
          <div className="text-[10px] uppercase tracking-[0.15em] text-travertine">Current</div>
        </div>
        <div className="text-right">
          <div className={`text-sm font-semibold tabular-nums ${delta > 0 ? "text-laurel" : delta < 0 ? "text-terracotta" : "text-travertine"}`}>
            {delta > 0 ? "+" : ""}{delta.toFixed(1)}cm · {delta > 0 ? "+" : ""}{pct.toFixed(1)}%
          </div>
          <div className="text-[10px] uppercase tracking-[0.15em] text-travertine">Over window</div>
        </div>
      </div>

      <svg viewBox={`0 0 ${W} ${H}`} className="w-full text-adriatic">
        {/* Gridlines */}
        {[0.25, 0.5, 0.75].map((f) => (
          <line
            key={f}
            x1={pad} x2={W - pad}
            y1={H - pad - f * (H - pad * 2)}
            y2={H - pad - f * (H - pad * 2)}
            stroke="#e5e2dd" strokeDasharray="2 3"
          />
        ))}
        {/* Acceleration windows */}
        {accelRects.map((r, i) => r && (
          <rect
            key={i}
            x={r.x1} y={pad}
            width={r.x2 - r.x1} height={H - pad * 2}
            fill="#b8860b" opacity={0.08}
          />
        ))}
        {/* Line */}
        <path d={path} fill="none" stroke="currentColor" strokeWidth={2.25} strokeLinecap="round" />
        {/* Data points */}
        {series.map((p, i) => (
          <circle
            key={i}
            cx={scaleX(i)} cy={scaleY(p.value_cm)}
            r={2.5} fill="currentColor"
          />
        ))}
        {/* X-axis labels: first, middle, last */}
        <text x={pad} y={H - 4} fontSize="10" fill="#9b938a" fontFamily="sans-serif">
          {series[0].date.slice(2)}
        </text>
        <text x={W - pad} y={H - 4} fontSize="10" fill="#9b938a" fontFamily="sans-serif" textAnchor="end">
          {series[series.length - 1].date.slice(2)}
        </text>
      </svg>

      {accelRects.length > 0 && (
        <div className="bg-alabaster rounded-button border border-ash px-3 py-2.5">
          <p className="h-section text-travertine mb-1">Acceleration windows</p>
          <p className="text-[11px] body-serif-sm italic text-iron leading-snug mb-2">
            Gold-tinted periods grew faster than your baseline rate. Check your training log from those weeks to
            see what split / volume / phase you were running.
          </p>
          <div className="space-y-1">
            {(data?.acceleration_windows ?? []).map((w, i) => (
              <div key={i} className="flex items-baseline justify-between text-[11px] border-b border-ash/50 last:border-0 py-1">
                <span className="text-iron tabular-nums">
                  {w.start_date.slice(5)} → {w.end_date.slice(5)}
                </span>
                <span className="text-aureus font-semibold tabular-nums">
                  {w.rate_vs_baseline.toFixed(2)}× baseline
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
