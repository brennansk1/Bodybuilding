"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import NavBar from "@/components/NavBar";
import PageTitle from "@/components/PageTitle";
import { api } from "@/lib/api";

// ─── Interfaces ──────────────────────────────────────────────────────────────

interface TimelineEntry {
  date: string;
  type: "weight" | "weekly_checkin" | "daily_checkin" | "pds";
  // weight
  weight_kg?: number;
  // weekly_checkin
  week_number?: number;
  body_weight_kg?: number;
  pds_score?: number | null;
  ari_score?: number | null;
  nutrition_adherence_pct?: number | null;
  training_adherence_pct?: number | null;
  notes?: string | null;
  photos?: {
    front?: string | null;
    back?: string | null;
    side_left?: string | null;
    side_right?: string | null;
    front_pose?: string | null;
    back_pose?: string | null;
  };
  // daily_checkin
  rmssd?: number;
  sleep_quality?: number | null;
  soreness_score?: number | null;
  // pds
  tier?: string | null;
}

interface CompareSelection {
  date: string;
  photos: NonNullable<TimelineEntry["photos"]>;
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function formatDate(dateStr: string): string {
  const d = new Date(dateStr + "T00:00:00");
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

function formatDay(dateStr: string): string {
  const d = new Date(dateStr + "T00:00:00");
  return d.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" });
}

// Categorical palette — one family per entry type. Legion is reserved for
// PDS (the hero score). Secondary entry types use the semantic family so the
// timeline doesn't read as one uniform red column.
const TYPE_STYLES: Record<string, { label: string; cls: string; dotCls: string }> = {
  pds:            { label: "PDS Score",       cls: "bg-blush text-centurion",              dotCls: "bg-legion" },
  weekly_checkin: { label: "Weekly Check-In", cls: "bg-viltrum-laurel-bg text-laurel",     dotCls: "bg-laurel" },
  daily_checkin:  { label: "Daily Check-In",  cls: "bg-viltrum-adriatic-bg text-adriatic", dotCls: "bg-adriatic" },
  weight:         { label: "Weight",          cls: "bg-viltrum-aureus-bg text-aureus",     dotCls: "bg-aureus" },
};

// ─── Main Component ──────────────────────────────────────────────────────────

export default function TimelinePage() {
  const router = useRouter();
  const { user, loading, logout } = useAuth();
  const [entries, setEntries] = useState<TimelineEntry[]>([]);
  const [fetching, setFetching] = useState(true);
  const [filter, setFilter] = useState<string>("all");
  const [useLbs, setUseLbs] = useState(false);

  // Pose comparison state
  const [compareMode, setCompareMode] = useState(false);
  const [compareA, setCompareA] = useState<CompareSelection | null>(null);
  const [compareB, setCompareB] = useState<CompareSelection | null>(null);
  const [showCompare, setShowCompare] = useState(false);

  useEffect(() => {
    setUseLbs(localStorage.getItem("useLbs") === "true");
  }, []);

  useEffect(() => {
    if (!loading && !user) { router.push("/auth/login"); return; }
    if (!user) return;

    api.get<{ entries: TimelineEntry[] }>("/checkin/timeline?days=365")
      .then(res => setEntries(res.entries))
      .catch(() => {})
      .finally(() => setFetching(false));
  }, [user, loading, router]);

  if (loading || !user) return null;

  const m = useLbs ? 2.20462 : 1;
  const unit = useLbs ? "lbs" : "kg";

  const filtered = filter === "all" ? entries : entries.filter(e => e.type === filter);

  // Group entries by date — and collapse duplicates within the same date+type.
  // Multiple weekly-checkin rows on the same day, or two PDS scores from the
  // same diagnostic run, were rendering as visible duplicates. Keep the most
  // useful representative per (date, type): highest PDS, latest weight, first
  // weekly, latest daily.
  const grouped: Record<string, TimelineEntry[]> = {};
  for (const entry of filtered) {
    if (!grouped[entry.date]) grouped[entry.date] = [];
    grouped[entry.date].push(entry);
  }
  const dedupe = (rows: TimelineEntry[]): TimelineEntry[] => {
    const byKey = new Map<string, TimelineEntry>();
    for (const r of rows) {
      const key = `${r.date}|${r.type}`;
      const prev = byKey.get(key);
      if (!prev) { byKey.set(key, r); continue; }
      if (r.type === "pds") {
        if ((r.pds_score ?? 0) > (prev.pds_score ?? 0)) byKey.set(key, r);
      } else if (r.type === "weight") {
        if ((r.weight_kg ?? 0) !== (prev.weight_kg ?? 0)) byKey.set(key, r);
      } else {
        // weekly / daily checkin — keep the one with more data populated.
        const score = (x: TimelineEntry) => Object.values(x).filter(v => v != null && v !== "").length;
        if (score(r) > score(prev)) byKey.set(key, r);
      }
    }
    return Array.from(byKey.values());
  };
  for (const d of Object.keys(grouped)) grouped[d] = dedupe(grouped[d]);
  const dates = Object.keys(grouped).sort((a, b) => b.localeCompare(a));

  const weeklyWithPhotos = entries.filter(
    e => e.type === "weekly_checkin" && e.photos && Object.values(e.photos).some(Boolean)
  );

  const handleCompareSelect = (entry: TimelineEntry) => {
    if (!entry.photos) return;
    const sel: CompareSelection = { date: entry.date, photos: entry.photos };
    if (!compareA) {
      setCompareA(sel);
    } else if (!compareB && compareA.date !== entry.date) {
      setCompareB(sel);
      setShowCompare(true);
    } else {
      // Reset and start new comparison
      setCompareA(sel);
      setCompareB(null);
      setShowCompare(false);
    }
  };

  return (
    <div className="min-h-screen">
      <NavBar username={user.username} onLogout={() => { logout(); router.push("/"); }} />

      <main className="max-w-lg mx-auto px-4 py-6 space-y-4">
        {/* Header */}
        <div className="flex items-center justify-between">
          <PageTitle text="Timeline" subtitle={`${entries.length} entries`} className="mb-0" />
          <button
            onClick={() => {
              setCompareMode(!compareMode);
              setCompareA(null);
              setCompareB(null);
              setShowCompare(false);
            }}
            className={`text-xs px-3 py-1.5 rounded-lg border transition-colors ${
              compareMode
                ? "bg-jungle-accent/20 border-jungle-accent text-jungle-accent"
                : "bg-jungle-card border-jungle-border text-jungle-muted hover:border-jungle-accent"
            }`}
          >
            {compareMode ? "Cancel Compare" : "Compare Poses"}
          </button>
        </div>

        {/* Compare mode instructions */}
        {compareMode && (
          <div className="bg-jungle-accent/10 border border-jungle-accent/30 rounded-lg p-3 text-xs text-jungle-accent">
            {!compareA
              ? "Select the first check-in to compare (must have photos)"
              : !compareB
              ? `First: ${formatDate(compareA.date)} — now select the second check-in`
              : "Both selected! Viewing comparison."}
          </div>
        )}

        {/* Filters */}
        <div className="flex gap-1 overflow-x-auto pb-1">
          {[
            { key: "all", label: "All" },
            { key: "weekly_checkin", label: "Weekly" },
            { key: "daily_checkin", label: "Daily" },
            { key: "weight", label: "Weight" },
            { key: "pds", label: "PDS" },
          ].map(f => (
            <button
              key={f.key}
              onClick={() => setFilter(f.key)}
              className={`px-3 py-1.5 rounded-lg text-[10px] font-medium transition-colors whitespace-nowrap ${
                filter === f.key
                  ? "bg-jungle-accent text-white"
                  : "bg-jungle-deeper text-jungle-muted hover:text-jungle-accent"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>

        {/* Loading */}
        {fetching && (
          <div className="space-y-3">
            {[1, 2, 3, 4, 5].map(i => (
              <div key={i} className="card animate-pulse h-16" />
            ))}
          </div>
        )}

        {/* Empty state */}
        {!fetching && dates.length === 0 && (
          <div className="card text-center py-12">
            <p className="text-jungle-muted text-lg font-medium">No timeline data yet</p>
            <p className="text-jungle-dim text-sm mt-1">Complete check-ins to build your history.</p>
            <a href="/checkin" className="btn-primary inline-block mt-4">Start Check-In</a>
          </div>
        )}

        {/* Timeline */}
        {!fetching && dates.length > 0 && (
          <div className="relative">
            {/* Vertical line */}
            <div className="absolute left-3 top-0 bottom-0 w-px bg-jungle-border" />

            <div className="space-y-1">
              {dates.map(dateStr => (
                <div key={dateStr} className="relative pl-8">
                  {/* Date label */}
                  <div className="flex items-center gap-2 mb-1 -ml-8 pl-8">
                    <div className="absolute left-1.5 w-3 h-3 rounded-full bg-jungle-border border-2 border-jungle-card z-10" />
                    <p className="text-[10px] text-jungle-dim font-semibold uppercase tracking-wider">
                      {formatDay(dateStr)}
                    </p>
                  </div>

                  {/* Entries for this date */}
                  <div className="space-y-1.5 mb-3">
                    {grouped[dateStr].map((entry, i) => {
                      const style = TYPE_STYLES[entry.type] || TYPE_STYLES.weight;
                      const isWeeklyWithPhotos = entry.type === "weekly_checkin" && entry.photos && Object.values(entry.photos).some(Boolean);

                      return (
                        <div
                          key={`${entry.type}-${i}`}
                          className={`card py-2.5 px-3 ${
                            compareMode && isWeeklyWithPhotos ? "cursor-pointer hover:border-jungle-accent" : ""
                          } ${
                            compareMode && (compareA?.date === entry.date || compareB?.date === entry.date) && entry.type === "weekly_checkin"
                              ? "border-jungle-accent bg-jungle-accent/5"
                              : ""
                          }`}
                          onClick={() => compareMode && isWeeklyWithPhotos ? handleCompareSelect(entry) : undefined}
                        >
                          <div className="flex items-center justify-between mb-1">
                            <span className={`text-[9px] px-1.5 py-0.5 rounded font-medium ${style.cls}`}>
                              {style.label}
                            </span>
                            {entry.type === "weekly_checkin" && entry.week_number && (
                              <span className="text-[9px] text-jungle-dim">Week {entry.week_number}</span>
                            )}
                          </div>

                          {/* Weight entry */}
                          {entry.type === "weight" && (
                            <p className="text-sm font-semibold text-jungle-text">
                              {(entry.weight_kg! * m).toFixed(1)} {unit}
                            </p>
                          )}

                          {/* Daily check-in */}
                          {entry.type === "daily_checkin" && (
                            <div className="flex gap-3 text-xs text-jungle-muted">
                              {entry.rmssd && <span>HRV: <span className="text-jungle-text font-medium">{entry.rmssd}</span></span>}
                              {entry.sleep_quality && <span>Sleep: <span className="text-jungle-text font-medium">{entry.sleep_quality}/10</span></span>}
                              {entry.soreness_score && <span>Soreness: <span className="text-jungle-text font-medium">{entry.soreness_score}/10</span></span>}
                            </div>
                          )}

                          {/* Weekly check-in */}
                          {entry.type === "weekly_checkin" && (
                            <>
                              <div className="flex gap-3 text-xs text-jungle-muted flex-wrap">
                                {entry.body_weight_kg && (
                                  <span>Weight: <span className="text-jungle-text font-medium">{(entry.body_weight_kg * m).toFixed(1)} {unit}</span></span>
                                )}
                                {entry.pds_score != null && (
                                  <span>PDS: <span className="text-jungle-accent font-medium">{entry.pds_score}</span></span>
                                )}
                                {entry.ari_score != null && (
                                  <span>ARI: <span className="text-jungle-text font-medium">{entry.ari_score}</span></span>
                                )}
                                {entry.nutrition_adherence_pct != null && (
                                  <span>Adherence: <span className="text-jungle-text font-medium">{entry.nutrition_adherence_pct?.toFixed(0)}%</span></span>
                                )}
                              </div>

                              {/* Photo thumbnails */}
                              {entry.photos && Object.values(entry.photos).some(Boolean) && (
                                <div className="flex gap-1 mt-2">
                                  {Object.entries(entry.photos)
                                    .filter(([, url]) => url)
                                    .slice(0, 4)
                                    .map(([key, url]) => (
                                      <div key={key} className="w-10 h-14 rounded overflow-hidden bg-jungle-deeper border border-jungle-border">
                                        <img src={url!} alt={key} className="w-full h-full object-cover" />
                                      </div>
                                    ))}
                                  {Object.values(entry.photos).filter(Boolean).length > 4 && (
                                    <div className="w-10 h-14 rounded bg-jungle-deeper border border-jungle-border flex items-center justify-center text-[9px] text-jungle-dim">
                                      +{Object.values(entry.photos).filter(Boolean).length - 4}
                                    </div>
                                  )}
                                </div>
                              )}
                            </>
                          )}

                          {/* PDS entry */}
                          {entry.type === "pds" && (
                            <div className="flex items-center gap-2">
                              <p className="text-sm font-bold text-jungle-accent">{entry.pds_score}</p>
                              {entry.tier && (
                                <span className="text-[9px] text-jungle-dim capitalize">{entry.tier}</span>
                              )}
                            </div>
                          )}

                          {/* Notes */}
                          {entry.notes && (
                            <p className="text-[10px] text-jungle-dim mt-1 italic truncate">
                              &ldquo;{entry.notes}&rdquo;
                            </p>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </main>

      {/* ── Pose Comparison Modal ── */}
      {showCompare && compareA && compareB && (
        <div className="fixed inset-0 z-50 bg-viltrum-obsidian/55 flex flex-col" onClick={() => setShowCompare(false)}>
          <div className="flex items-center justify-between px-4 py-3 bg-jungle-card/90 border-b border-jungle-border" onClick={e => e.stopPropagation()}>
            <h3 className="text-sm font-bold text-jungle-text">
              Pose Comparison: <span className="text-jungle-accent">{formatDate(compareA.date)}</span> vs <span className="text-jungle-accent">{formatDate(compareB.date)}</span>
            </h3>
            <button onClick={() => setShowCompare(false)} className="text-jungle-dim hover:text-white text-xl">×</button>
          </div>

          <div className="flex-1 overflow-y-auto p-4" onClick={e => e.stopPropagation()}>
            <div className="max-w-2xl mx-auto space-y-4">
              {(["front", "back", "side_left", "side_right", "front_pose", "back_pose"] as const).map(pose => {
                const urlA = compareA.photos[pose];
                const urlB = compareB.photos[pose];
                if (!urlA && !urlB) return null;
                return (
                  <div key={pose}>
                    <p className="text-xs text-jungle-dim uppercase tracking-wider mb-1 text-center">
                      {pose.replace(/_/g, " ")}
                    </p>
                    <div className="grid grid-cols-2 gap-2">
                      <div className="relative aspect-[3/4] bg-jungle-deeper rounded-lg overflow-hidden">
                        {urlA ? (
                          <img src={urlA} alt={`${pose} A`} className="w-full h-full object-cover" />
                        ) : (
                          <div className="w-full h-full flex items-center justify-center text-jungle-dim text-xs">No photo</div>
                        )}
                        <span className="absolute bottom-1 left-1 text-[8px] bg-viltrum-obsidian/40 px-1.5 py-0.5 rounded text-white">
                          {formatDate(compareA.date)}
                        </span>
                      </div>
                      <div className="relative aspect-[3/4] bg-jungle-deeper rounded-lg overflow-hidden">
                        {urlB ? (
                          <img src={urlB} alt={`${pose} B`} className="w-full h-full object-cover" />
                        ) : (
                          <div className="w-full h-full flex items-center justify-center text-jungle-dim text-xs">No photo</div>
                        )}
                        <span className="absolute bottom-1 left-1 text-[8px] bg-viltrum-obsidian/40 px-1.5 py-0.5 rounded text-white">
                          {formatDate(compareB.date)}
                        </span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
