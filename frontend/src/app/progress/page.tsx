"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import NavBar from "@/components/NavBar";
import { api } from "@/lib/api";
import MiniLineChart from "@/components/MiniLineChart";

interface WeightEntry { date: string; weight_kg: number }
interface PDSEntry { date: string; pds_score: number; tier: string }
interface PDSData {
  current: { pds_score: number; tier: string; components: Record<string, number> };
  history: PDSEntry[];
}
interface LCSAEntry {
  date: string;
  site_values: Record<string, number>;
  total: number;
}
interface LCSAData { current: LCSAEntry; history: LCSAEntry[] }
interface FeasibilityResult {
  feasible: boolean;
  expected_pds_gain: number;
  max_weekly_gain: number;
  estimated_weeks: number;
  confidence: number;
  current_pds: number;
  target_pds: number;
  weeks_available: number;
  competition_date?: string;
}
interface PhaseInfo {
  label: string;
  description: string;
  nutrition_cue: string;
  training_cue: string;
  calorie_modifier: number;
}
interface DiagnosticResult {
  body_fat?: {
    body_fat_pct: number;
    category: string;
    lean_mass_kg: number | null;
  };
  prep_timeline?: {
    current_phase: string;
    weeks_out: number | null;
    phase_info: PhaseInfo;
  };
}
interface AestheticVector {
  actual: Record<string, number>;
  ideal: Record<string, number>;
  delta: Record<string, number>;
  priorities: string[];           // sorted site names, highest priority first
  priority_scores: Record<string, number>;
  body_fat_pct: number | null;
}

const TIER_LABELS: Record<string, string> = {
  novice: "Novice (0–50)",
  intermediate: "Intermediate (50–70)",
  advanced: "Advanced (70–85)",
  elite: "Elite (85+)",
};

const PHASE_STYLES: Record<string, { label: string; cls: string }> = {
  offseason: { label: "Off-Season", cls: "bg-blue-500/20 text-blue-400" },
  lean_bulk: { label: "Lean Bulk", cls: "bg-green-500/20 text-green-400" },
  cut: { label: "Cut", cls: "bg-orange-500/20 text-orange-400" },
  peak_week: { label: "Peak Week", cls: "bg-jungle-accent/20 text-jungle-accent" },
  contest: { label: "Contest", cls: "bg-red-500/20 text-red-400" },
};

const BF_CATEGORY = (bf: number): { label: string; cls: string } => {
  if (bf < 8) return { label: "Stage-Ready", cls: "bg-green-500/20 text-green-400" };
  if (bf < 12) return { label: "Lean", cls: "bg-jungle-accent/20 text-jungle-accent" };
  if (bf < 18) return { label: "Moderate", cls: "bg-yellow-500/20 text-yellow-400" };
  return { label: "Offseason", cls: "bg-blue-500/20 text-blue-400" };
};

function GapColor({ pct }: { pct: number }) {
  const abs = Math.abs(pct);
  const cls = abs <= 5 ? "text-green-400" : abs <= 15 ? "text-yellow-400" : "text-red-400";
  return (
    <span className={`font-semibold ${cls}`}>
      {pct > 0 ? "+" : ""}{pct.toFixed(1)}%
    </span>
  );
}

// Simple arc gauge using SVG
function ArcGauge({ value, target, max = 100 }: { value: number; target: number; max?: number }) {
  const r = 54;
  const cx = 64;
  const cy = 64;
  const startAngle = -210;
  const sweepAngle = 240;

  const polarToXY = (deg: number) => {
    const rad = (deg * Math.PI) / 180;
    return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
  };

  const arcPath = (fromDeg: number, toDeg: number) => {
    const start = polarToXY(fromDeg);
    const end = polarToXY(toDeg);
    const largeArc = Math.abs(toDeg - fromDeg) > 180 ? 1 : 0;
    return `M ${start.x} ${start.y} A ${r} ${r} 0 ${largeArc} 1 ${end.x} ${end.y}`;
  };

  const valueDeg = startAngle + (value / max) * sweepAngle;
  const targetDeg = startAngle + (target / max) * sweepAngle;
  const endDeg = startAngle + sweepAngle;

  return (
    <svg viewBox="0 0 128 96" className="w-48 mx-auto">
      {/* Track */}
      <path d={arcPath(startAngle, endDeg)} fill="none" stroke="#2a3a2a" strokeWidth="10" strokeLinecap="round" />
      {/* Value fill */}
      <path d={arcPath(startAngle, valueDeg)} fill="none" stroke="#c8a84e" strokeWidth="10" strokeLinecap="round" />
      {/* Target marker */}
      <circle
        cx={polarToXY(targetDeg).x}
        cy={polarToXY(targetDeg).y}
        r={5}
        fill="#4ade80"
        stroke="#1a2a1a"
        strokeWidth={2}
      />
      {/* Center text */}
      <text x={cx} y={cy - 6} textAnchor="middle" className="fill-white" fontSize="18" fontWeight="bold">{Math.round(value)}</text>
      <text x={cx} y={cy + 10} textAnchor="middle" fill="#8a9a8a" fontSize="8">PDS</text>
    </svg>
  );
}

export default function ProgressPage() {
  const router = useRouter();
  const { user, loading, logout } = useAuth();
  const [weights, setWeights] = useState<WeightEntry[]>([]);
  const [pds, setPds] = useState<PDSData | null>(null);
  const [lcsa, setLcsa] = useState<LCSAData | null>(null);
  const [activeTab, setActiveTab] = useState<"weight" | "pds" | "measurements" | "feasibility" | "condition" | "photos">("weight");
  const [diagnostic, setDiagnostic] = useState<DiagnosticResult | null>(null);
  const [feasibility, setFeasibility] = useState<FeasibilityResult | null>(null);
  const [targetPds, setTargetPds] = useState("");
  const [feasLoading, setFeasLoading] = useState(false);
  const [aestheticVector, setAestheticVector] = useState<AestheticVector | null>(null);
  const [showPdsTooltip, setShowPdsTooltip] = useState(false);

  // Photos state
  const [photos, setPhotos] = useState<{ url: string; date: string }[]>([]);
  const [compareA, setCompareA] = useState<string | null>(null);
  const [compareB, setCompareB] = useState<string | null>(null);
  const [compareMode, setCompareMode] = useState(false);
  const [compareModalOpen, setCompareModalOpen] = useState(false);
  const photoInputRef = useRef<HTMLInputElement>(null);
  const [photoUploading, setPhotoUploading] = useState(false);

  useEffect(() => {
    if (!loading && !user) { router.push("/auth/login"); return; }
    if (user) {
      api.get<WeightEntry[]>("/checkin/weight-history?days=120").then(setWeights).catch(() => {});
      api.get<PDSData>("/engine1/pds").then(setPds).catch(() => {});
      api.get<LCSAData>("/engine1/lcsa").then(setLcsa).catch(() => {});
      api.get<DiagnosticResult>("/engine1/diagnostic").then(setDiagnostic).catch(() => {});
    }
  }, [user, loading, router]);

  // Fetch aesthetic vector when condition tab is active
  useEffect(() => {
    if (activeTab === "condition" && user && !aestheticVector) {
      api.get<AestheticVector>("/engine1/aesthetic-vector").then(setAestheticVector).catch(() => {});
    }
  }, [activeTab, user, aestheticVector]);

  if (loading || !user) return null;

  const weightData = weights.map((w) => ({ label: w.date.slice(5), value: w.weight_kg }));
  const pdsData = pds
    ? pds.history.map((e) => ({ label: e.date.slice(5), value: e.pds_score }))
    : [];

  // Get all LCSA sites from latest entry (using site_values)
  const lcsaSites = lcsa?.current?.site_values
    ? Object.keys(lcsa.current.site_values)
    : [];

  // Build per-site history lines
  const siteHistoryData = (site: string) =>
    lcsa?.history?.map((entry) => ({
      label: entry.date.slice(5),
      value: entry.site_values[site] ?? 0,
    })) ?? [];

  // LCSA total history for trend chart
  const lcsaTotalHistory = lcsa?.history?.map((entry) => ({
    label: entry.date.slice(5),
    value: entry.total,
  })) ?? [];

  const latestWeight = weights[weights.length - 1]?.weight_kg;
  const firstWeight = weights[0]?.weight_kg;
  const weightChange = latestWeight !== undefined && firstWeight !== undefined
    ? latestWeight - firstWeight
    : null;

  const currentTotal = lcsa?.current?.total ?? 0;
  // Muscle mass score (0-100) from PDS components — how close to ghost model ideal
  const proportionScore = pds?.current?.components?.muscle_mass != null
    ? Math.round(pds.current.components.muscle_mass)
    : null;

  const currentPds = pds?.current.pds_score ?? 0;
  const targetPdsForGauge = feasibility?.target_pds ?? Math.min(100, currentPds + 15);

  // Determine next tier threshold — must match backend pds.py
  const TIER_THRESHOLDS: { tier: string; min: number; max: number }[] = [
    { tier: "novice",       min: 0,  max: 50  },
    { tier: "intermediate", min: 50, max: 70  },
    { tier: "advanced",     min: 70, max: 85  },
    { tier: "elite",        min: 85, max: 100 },
  ];
  const nextTierInfo = TIER_THRESHOLDS.find((t) => currentPds < t.max);
  const pointsToNextTier = nextTierInfo ? Math.max(0, nextTierInfo.max - currentPds) : 0;

  // Photos logic
  const handlePhotoSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setPhotoUploading(true);
    try {
      const formData = new FormData();
      formData.append("photo", file);
      await api.postFormData("/auth/upload-photo", formData);
      // Optimistic local preview
      const url = URL.createObjectURL(file);
      setPhotos((prev) => [...prev, { url, date: new Date().toISOString().split("T")[0] }]);
    } catch {
      // silent — placeholder UI
    } finally {
      setPhotoUploading(false);
      if (photoInputRef.current) photoInputRef.current.value = "";
    }
  };

  const handlePhotoClick = (url: string) => {
    if (!compareMode) return;
    if (!compareA) {
      setCompareA(url);
    } else if (!compareB && url !== compareA) {
      setCompareB(url);
      setCompareModalOpen(true);
    }
  };

  const resetCompare = () => {
    setCompareA(null);
    setCompareB(null);
    setCompareModalOpen(false);
  };

  const tabLabels: Record<string, string> = {
    weight: "Weight",
    pds: "PDS Score",
    measurements: "Measures",
    feasibility: "Feasibility",
    condition: "Condition",
    photos: "Photos",
  };

  return (
    <div className="min-h-screen bg-jungle-dark">
      <NavBar username={user.username} onLogout={() => { logout(); router.push("/"); }} />

      <main className="container-app py-6">
        <div className="max-w-3xl mx-auto space-y-6">
          {/* Header */}
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold">
                <span className="text-jungle-accent">Progress</span> History
              </h1>
              <p className="text-jungle-muted text-sm mt-1">Trend tracking across all metrics</p>
            </div>
            <a href="/dashboard" className="btn-secondary text-sm px-3 py-2">← Dashboard</a>
          </div>

          {/* Summary cards */}
          <div className="grid grid-cols-3 gap-3">
            <div className="card text-center">
              <p className="text-[10px] text-jungle-muted uppercase tracking-wide">Current PDS</p>
              <p className="text-2xl font-bold text-jungle-accent mt-1">
                {pds?.current.pds_score ?? "—"}
              </p>
              <p className="text-xs text-jungle-fern capitalize mt-0.5">
                {pds?.current.tier ?? ""}
              </p>
            </div>
            <div className="card text-center">
              <p className="text-[10px] text-jungle-muted uppercase tracking-wide">Body Weight</p>
              <p className="text-2xl font-bold mt-1">
                {latestWeight !== undefined ? `${latestWeight}kg` : "—"}
              </p>
              {weightChange !== null && (
                <p className={`text-xs mt-0.5 ${weightChange > 0 ? "text-red-400" : weightChange < 0 ? "text-green-400" : "text-jungle-dim"}`}>
                  {weightChange > 0 ? "+" : ""}{weightChange.toFixed(1)}kg
                </p>
              )}
            </div>
            <div className="card text-center">
              <p className="text-[10px] text-jungle-muted uppercase tracking-wide">Overall LCSA</p>
              <p className="text-2xl font-bold mt-1">
                {lcsa?.current.total ? Math.round(lcsa.current.total) : "—"}
              </p>
              <p className="text-xs text-jungle-dim mt-0.5">lean cross-section</p>
            </div>
          </div>

          {/* Tabs */}
          <div className="flex gap-1 bg-jungle-deeper border border-jungle-border rounded-xl p-1 flex-wrap">
            {(["weight", "pds", "measurements", "feasibility", "condition", "photos"] as const).map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`flex-1 min-w-[50px] py-2 text-xs sm:text-sm rounded-lg transition-colors ${
                  activeTab === tab
                    ? "bg-jungle-accent text-jungle-dark font-semibold"
                    : "text-jungle-muted hover:text-jungle-accent"
                }`}
              >
                {tabLabels[tab]}
              </button>
            ))}
          </div>

          {/* Weight Tab */}
          {activeTab === "weight" && (
            <div className="card">
              <div className="flex items-baseline justify-between mb-4">
                <h3 className="text-sm font-semibold">Body Weight Trend</h3>
                <span className="text-xs text-jungle-muted">Last 120 days</span>
              </div>
              {weightData.length >= 2 ? (
                <>
                  <MiniLineChart data={weightData} height={160} color="#c8a84e" />
                  <div className="grid grid-cols-3 gap-3 mt-4">
                    <div className="bg-jungle-deeper rounded-lg p-3 text-center">
                      <p className="text-[10px] text-jungle-muted">Start</p>
                      <p className="font-bold">{firstWeight}kg</p>
                    </div>
                    <div className="bg-jungle-deeper rounded-lg p-3 text-center">
                      <p className="text-[10px] text-jungle-muted">Change</p>
                      <p className={`font-bold ${weightChange && weightChange < 0 ? "text-green-400" : weightChange && weightChange > 0 ? "text-red-400" : ""}`}>
                        {weightChange !== null ? `${weightChange > 0 ? "+" : ""}${weightChange.toFixed(1)}kg` : "—"}
                      </p>
                    </div>
                    <div className="bg-jungle-deeper rounded-lg p-3 text-center">
                      <p className="text-[10px] text-jungle-muted">Current</p>
                      <p className="font-bold text-jungle-accent">{latestWeight}kg</p>
                    </div>
                  </div>

                  {/* Weight log table */}
                  <div className="mt-4 space-y-1 max-h-48 overflow-y-auto">
                    <div className="grid grid-cols-2 text-[10px] text-jungle-dim uppercase px-2 pb-1 border-b border-jungle-border">
                      <span>Date</span>
                      <span className="text-right">Weight</span>
                    </div>
                    {[...weights].reverse().map((w) => (
                      <div key={w.date} className="grid grid-cols-2 text-sm px-2 py-1.5 hover:bg-jungle-deeper rounded">
                        <span className="text-jungle-muted">{w.date}</span>
                        <span className="text-right font-medium">{w.weight_kg}kg</span>
                      </div>
                    ))}
                  </div>
                </>
              ) : (
                <div className="flex items-center justify-center h-40 text-jungle-dim text-sm border border-dashed border-jungle-border rounded-lg">
                  Log body weight during check-in to track trends
                </div>
              )}
            </div>
          )}

          {/* PDS Tab */}
          {activeTab === "pds" && (
            <div className="space-y-4">
              {/* Arc Gauge + Goal PDS */}
              <div className="card">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-sm font-semibold">Physique Development Score</h3>
                  <div className="relative">
                    <button
                      onClick={() => setShowPdsTooltip(!showPdsTooltip)}
                      className="w-5 h-5 rounded-full bg-jungle-border/40 text-jungle-dim text-xs flex items-center justify-center hover:bg-jungle-accent/20 hover:text-jungle-accent transition-colors"
                    >
                      i
                    </button>
                    {showPdsTooltip && (
                      <div className="absolute right-0 top-7 z-10 w-72 bg-jungle-deeper border border-jungle-border rounded-xl p-3 shadow-xl">
                        <p className="text-xs text-jungle-muted leading-relaxed">
                          PDS (Physique Development Score) combines muscle mass score (35%), conditioning (25%), symmetry (20%), and proportion/HQI (20%) into a single 0–100 stage readiness metric.
                        </p>
                        <button
                          onClick={() => setShowPdsTooltip(false)}
                          className="mt-2 text-[10px] text-jungle-dim hover:text-jungle-accent"
                        >
                          Dismiss
                        </button>
                      </div>
                    )}
                  </div>
                </div>

                {pds ? (
                  <>
                    <ArcGauge value={currentPds} target={targetPdsForGauge} />
                    <div className="flex items-center justify-center gap-6 mt-1 text-xs text-jungle-dim">
                      <div className="flex items-center gap-1.5">
                        <div className="w-3 h-1.5 rounded-full bg-jungle-accent" />
                        <span>Current ({Math.round(currentPds)})</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <div className="w-3 h-3 rounded-full bg-green-400" />
                        <span>Target ({Math.round(targetPdsForGauge)})</span>
                      </div>
                    </div>
                    {nextTierInfo && (
                      <p className="text-center text-xs text-jungle-muted mt-3">
                        <span className="font-semibold text-jungle-accent">{pointsToNextTier.toFixed(1)} points</span> to next tier ({nextTierInfo.tier})
                      </p>
                    )}
                  </>
                ) : (
                  <div className="flex items-center justify-center h-32 text-jungle-dim text-sm border border-dashed border-jungle-border rounded-lg">
                    Run diagnostics to see PDS score
                  </div>
                )}
              </div>

              <div className="card">
                <div className="flex items-baseline justify-between mb-4">
                  <h3 className="text-sm font-semibold">PDS Score Over Time</h3>
                  <span className="text-xs text-jungle-muted">{pds?.history.length ?? 0} data points</span>
                </div>
                {pdsData.length >= 2 ? (
                  <MiniLineChart data={pdsData} height={160} domain={[0, 100]} />
                ) : (
                  <div className="flex items-center justify-center h-40 text-jungle-dim text-sm border border-dashed border-jungle-border rounded-lg">
                    Run diagnostics to track PDS score
                  </div>
                )}
              </div>

              {/* PDS Component breakdown */}
              {pds && (
                <div className="card">
                  <h3 className="text-sm font-semibold mb-3">Component Scores</h3>
                  <div className="space-y-2">
                    {Object.entries(pds.current.components).map(([key, val]) => {
                      const pct = Math.min(100, Math.max(0, val));
                      return (
                        <div key={key}>
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-xs text-jungle-muted capitalize">{key.replace(/_/g, " ")}</span>
                            <span className="text-xs font-semibold">{Math.round(val)}</span>
                          </div>
                          <div className="h-1.5 bg-jungle-deeper rounded-full overflow-hidden">
                            <div
                              className="h-full rounded-full"
                              style={{
                                width: `${pct}%`,
                                backgroundColor: pct >= 75 ? "#4ade80" : pct >= 50 ? "#c8a84e" : "#ef4444",
                              }}
                            />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Tier reference */}
              <div className="card">
                <h3 className="text-xs font-semibold text-jungle-muted uppercase tracking-wider mb-3">Tier Reference</h3>
                <div className="space-y-2">
                  {Object.entries(TIER_LABELS).map(([tier, label]) => (
                    <div
                      key={tier}
                      className={`flex items-center justify-between px-3 py-2 rounded-lg text-xs ${
                        pds?.current.tier === tier
                          ? "bg-jungle-accent/15 border border-jungle-accent/40 text-jungle-accent font-semibold"
                          : "bg-jungle-deeper text-jungle-dim"
                      }`}
                    >
                      <span className="capitalize">{tier}</span>
                      <span>{label}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Feasibility Tab */}
          {activeTab === "feasibility" && (
            <div className="space-y-4">
              <div className="card space-y-4">
                <h3 className="text-sm font-semibold">Goal Feasibility Assessment</h3>
                <p className="text-xs text-jungle-muted">
                  Enter a target PDS score to assess whether it&apos;s achievable by your competition date using Engine 1 diminishing-returns modeling.
                </p>
                <div className="flex gap-3 items-end">
                  <div className="flex-1">
                    <label className="label-field">Target PDS Score (0–100)</label>
                    <input
                      type="number"
                      min={1}
                      max={100}
                      step={1}
                      value={targetPds}
                      onChange={(e) => setTargetPds(e.target.value)}
                      className="input-field mt-1"
                      placeholder={`e.g. ${pds ? Math.min(100, pds.current.pds_score + 15) : 65}`}
                    />
                  </div>
                  <button
                    onClick={async () => {
                      if (!targetPds) return;
                      setFeasLoading(true);
                      try {
                        const res = await api.post<FeasibilityResult>("/engine1/feasibility", {
                          target_pds: parseFloat(targetPds),
                        });
                        setFeasibility(res);
                      } catch { /* silent */ }
                      finally { setFeasLoading(false); }
                    }}
                    disabled={feasLoading || !targetPds}
                    className="btn-primary disabled:opacity-50 whitespace-nowrap"
                  >
                    {feasLoading ? "Assessing..." : "Assess"}
                  </button>
                </div>

                {feasibility && (
                  <div className="space-y-4 pt-2 border-t border-jungle-border">
                    {/* Verdict */}
                    <div className={`rounded-lg p-4 text-center border ${
                      feasibility.feasible
                        ? "bg-green-500/10 border-green-500/30"
                        : "bg-red-500/10 border-red-500/30"
                    }`}>
                      <p className={`text-2xl font-bold mb-1 ${feasibility.feasible ? "text-green-400" : "text-red-400"}`}>
                        {feasibility.feasible ? "Achievable" : "Tight Timeline"}
                      </p>
                      <p className="text-sm text-jungle-muted">
                        {feasibility.feasible
                          ? `Target PDS ${feasibility.target_pds} achievable in ~${feasibility.estimated_weeks} weeks`
                          : `Needs ~${feasibility.estimated_weeks} weeks, only ${feasibility.weeks_available} available`}
                      </p>
                    </div>

                    {/* Metrics */}
                    <div className="grid grid-cols-2 gap-3">
                      <div className="bg-jungle-deeper rounded-lg p-3 text-center">
                        <p className="text-[10px] text-jungle-muted uppercase">Current PDS</p>
                        <p className="text-xl font-bold text-jungle-accent">{feasibility.current_pds}</p>
                      </div>
                      <div className="bg-jungle-deeper rounded-lg p-3 text-center">
                        <p className="text-[10px] text-jungle-muted uppercase">Target PDS</p>
                        <p className="text-xl font-bold">{feasibility.target_pds}</p>
                      </div>
                      <div className="bg-jungle-deeper rounded-lg p-3 text-center">
                        <p className="text-[10px] text-jungle-muted uppercase">Max Weekly Gain</p>
                        <p className="text-xl font-bold">{feasibility.max_weekly_gain}</p>
                        <p className="text-[10px] text-jungle-dim">pts/week</p>
                      </div>
                      <div className="bg-jungle-deeper rounded-lg p-3 text-center">
                        <p className="text-[10px] text-jungle-muted uppercase">Expected Gain</p>
                        <p className="text-xl font-bold text-jungle-fern">+{feasibility.expected_pds_gain}</p>
                        <p className="text-[10px] text-jungle-dim">in {feasibility.weeks_available}w</p>
                      </div>
                    </div>

                    {/* Confidence bar */}
                    <div>
                      <div className="flex justify-between text-xs text-jungle-muted mb-1">
                        <span>Model Confidence</span>
                        <span>{Math.round(feasibility.confidence * 100)}%</span>
                      </div>
                      <div className="h-2 bg-jungle-deeper rounded-full overflow-hidden">
                        <div
                          className="h-full rounded-full"
                          style={{
                            width: `${feasibility.confidence * 100}%`,
                            backgroundColor: feasibility.confidence >= 0.7 ? "#4ade80" : feasibility.confidence >= 0.4 ? "#c8a84e" : "#ef4444"
                          }}
                        />
                      </div>
                      <p className="text-[10px] text-jungle-dim mt-1">
                        Confidence decreases near division ideal ceiling (PDS 90+)
                      </p>
                    </div>

                    {feasibility.competition_date && (
                      <p className="text-xs text-jungle-dim text-center">
                        Calculated to competition date: {feasibility.competition_date} ({feasibility.weeks_available} weeks)
                      </p>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Condition Tab */}
          {activeTab === "condition" && (
            <div className="space-y-4">
              {/* Body Fat */}
              <div className="card">
                <h3 className="text-sm font-semibold mb-3">Body Composition</h3>
                {diagnostic?.body_fat ? (
                  <div className="flex items-center gap-4">
                    <div className="text-center">
                      <p className="text-[10px] text-jungle-muted uppercase tracking-wider mb-1">Body Fat</p>
                      <p className="text-4xl font-bold text-jungle-accent">
                        {diagnostic.body_fat.body_fat_pct.toFixed(1)}%
                      </p>
                    </div>
                    <div className="space-y-1.5">
                      {(() => {
                        const cat = BF_CATEGORY(diagnostic.body_fat!.body_fat_pct);
                        return (
                          <span className={`text-xs px-2.5 py-1 rounded-full font-semibold ${cat.cls}`}>
                            {cat.label}
                          </span>
                        );
                      })()}
                      {diagnostic.body_fat.lean_mass_kg !== null && (
                        <p className="text-[10px] text-jungle-dim">
                          Lean mass: {diagnostic.body_fat.lean_mass_kg.toFixed(1)}kg
                        </p>
                      )}
                      <p className="text-[10px] text-jungle-dim">From latest skinfold data</p>
                    </div>
                  </div>
                ) : (
                  <div className="flex items-center justify-center h-20 text-jungle-dim text-sm border border-dashed border-jungle-border rounded-lg">
                    Submit skinfold measurements to see body fat estimate
                  </div>
                )}
              </div>

              {/* Prep Timeline */}
              <div className="card">
                <h3 className="text-sm font-semibold mb-3">Prep Timeline</h3>
                {diagnostic?.prep_timeline ? (
                  <div className="space-y-3">
                    <div className="flex items-center gap-3 flex-wrap">
                      {(() => {
                        const phase = diagnostic.prep_timeline!.current_phase;
                        const style = PHASE_STYLES[phase] ?? { label: phase, cls: "bg-jungle-border/40 text-jungle-muted" };
                        return (
                          <span className={`text-xs px-2.5 py-1 rounded-full font-semibold ${style.cls}`}>
                            {style.label}
                          </span>
                        );
                      })()}
                      {diagnostic.prep_timeline.weeks_out !== null && (
                        <span className="text-sm font-semibold text-jungle-accent">
                          {diagnostic.prep_timeline.weeks_out}w out
                        </span>
                      )}
                    </div>

                    {diagnostic.prep_timeline.phase_info?.description && (
                      <p className="text-xs text-jungle-muted leading-relaxed">
                        {diagnostic.prep_timeline.phase_info.description}
                      </p>
                    )}

                    {(diagnostic.prep_timeline as DiagnosticResult["prep_timeline"] & { season_position?: number })?.season_position !== undefined && (
                      <div>
                        <div className="flex justify-between text-[10px] text-jungle-dim mb-1">
                          <span>Season start</span>
                          <span>Contest</span>
                        </div>
                        <div className="h-2 bg-jungle-deeper rounded-full overflow-hidden">
                          <div
                            className="h-full rounded-full transition-all"
                            style={{
                              width: `${Math.min(100, Math.max(0, ((diagnostic.prep_timeline as DiagnosticResult["prep_timeline"] & { season_position?: number })!.season_position ?? 0) * 100))}%`,
                              backgroundColor:
                                diagnostic.prep_timeline.current_phase === "peak_week" || diagnostic.prep_timeline.current_phase === "contest"
                                  ? "#c8a84e"
                                  : diagnostic.prep_timeline.current_phase === "cut"
                                  ? "#f97316"
                                  : "#4ade80",
                            }}
                          />
                        </div>
                      </div>
                    )}

                    {diagnostic.prep_timeline.phase_info?.nutrition_cue && (
                      <div className="grid grid-cols-2 gap-2 pt-1">
                        <div className="bg-jungle-deeper rounded-lg p-2.5">
                          <p className="text-[10px] text-jungle-dim uppercase mb-1">Nutrition cue</p>
                          <p className="text-xs text-jungle-muted">{diagnostic.prep_timeline.phase_info.nutrition_cue}</p>
                        </div>
                        <div className="bg-jungle-deeper rounded-lg p-2.5">
                          <p className="text-[10px] text-jungle-dim uppercase mb-1">Training cue</p>
                          <p className="text-xs text-jungle-muted">{diagnostic.prep_timeline.phase_info.training_cue}</p>
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center h-24 text-jungle-dim text-sm border border-dashed border-jungle-border rounded-lg gap-2">
                    <span>Run diagnostics to see prep timeline.</span>
                    <a href="/dashboard" className="text-xs text-jungle-accent hover:underline">
                      Go to Dashboard
                    </a>
                  </div>
                )}
              </div>

              {/* Ideal Physique Comparison */}
              <div className="card">
                <h3 className="text-sm font-semibold mb-3">Ideal Physique Comparison</h3>
                <p className="text-xs text-jungle-muted mb-3">
                  Site ratios vs. division ideal. Gap shows how far each measurement is from the target proportion.
                </p>
                {aestheticVector ? (
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="border-b border-jungle-border">
                          <th className="text-left py-2 text-jungle-dim font-medium">Site</th>
                          <th className="text-right py-2 text-jungle-dim font-medium">Your Ratio</th>
                          <th className="text-right py-2 text-jungle-dim font-medium">Division Ideal</th>
                          <th className="text-right py-2 text-jungle-dim font-medium">Gap</th>
                        </tr>
                      </thead>
                      <tbody>
                        {Object.entries(aestheticVector.ideal).map(([site, idealVal]) => {
                          const actualVal = aestheticVector.actual[site];
                          const deltaVal = aestheticVector.delta[site];
                          const gapPct = idealVal !== 0
                            ? ((actualVal - idealVal) / idealVal) * 100
                            : 0;
                          return (
                            <tr key={site} className="border-b border-jungle-border/40 hover:bg-jungle-deeper/50">
                              <td className="py-2 text-jungle-muted capitalize">{site.replace(/_/g, " ")}</td>
                              <td className="py-2 text-right font-medium">{actualVal?.toFixed(3) ?? "—"}</td>
                              <td className="py-2 text-right text-jungle-dim">{idealVal.toFixed(3)}</td>
                              <td className="py-2 text-right">
                                {actualVal !== undefined ? (
                                  <GapColor pct={gapPct} />
                                ) : (
                                  <span className="text-jungle-dim">—</span>
                                )}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                    <div className="flex gap-4 mt-3 text-[10px] text-jungle-dim">
                      <div className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-green-400 inline-block" /> Within 5%</div>
                      <div className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-yellow-400 inline-block" /> 5–15% off</div>
                      <div className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-red-400 inline-block" /> {">"}15% off</div>
                    </div>
                    {aestheticVector.priorities?.length > 0 && (
                      <div className="mt-3 pt-3 border-t border-jungle-border">
                        <p className="text-[10px] text-jungle-dim uppercase mb-1">Priority Sites</p>
                        <div className="flex flex-wrap gap-1">
                          {aestheticVector.priorities.map((p) => (
                            <span key={p} className="text-[10px] px-2 py-0.5 bg-jungle-accent/10 text-jungle-accent rounded-full capitalize">
                              {p.replace(/_/g, " ")}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="flex items-center justify-center h-20 text-jungle-dim text-sm border border-dashed border-jungle-border rounded-lg">
                    Loading aesthetic vector data...
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Measurements Tab */}
          {activeTab === "measurements" && (
            <div className="space-y-4">
              {/* Overall LCSA summary */}
              {lcsa?.current && (
                <div className="card">
                  <div className="flex items-baseline justify-between mb-3">
                    <h3 className="text-sm font-semibold">Overall LCSA</h3>
                    <span className="text-xs text-jungle-muted">Lean Cross-Sectional Area</span>
                  </div>
                  <div className="grid grid-cols-2 gap-3 mb-4">
                    <div className="bg-jungle-deeper rounded-lg p-3 text-center">
                      <p className="text-[10px] text-jungle-muted uppercase">Total LCSA</p>
                      <p className="text-2xl font-bold text-jungle-accent">{Math.round(lcsa.current.total)}</p>
                    </div>
                    <div className="bg-jungle-deeper rounded-lg p-3 text-center">
                      <p className="text-[10px] text-jungle-muted uppercase">Mass Score</p>
                      <p className="text-2xl font-bold text-jungle-fern">{proportionScore ?? "—"}</p>
                      <p className="text-[10px] text-jungle-dim">/ 100</p>
                    </div>
                  </div>

                  {/* LCSA total trend chart */}
                  {lcsaTotalHistory.length >= 2 ? (
                    <div>
                      <p className="text-[10px] text-jungle-dim uppercase tracking-wide mb-2">Total LCSA Over Time</p>
                      <MiniLineChart data={lcsaTotalHistory} height={90} color="#c8a84e" />
                    </div>
                  ) : null}
                </div>
              )}

              {/* Per-site bars */}
              {lcsa?.current?.site_values && Object.keys(lcsa.current.site_values).length > 0 && (
                <div className="card">
                  <h3 className="text-sm font-semibold mb-3">Site Values</h3>
                  <div className="space-y-2.5">
                    {Object.entries(lcsa.current.site_values).map(([site, val]) => {
                      const maxVal = Math.max(...Object.values(lcsa.current.site_values));
                      const barPct = maxVal > 0 ? (val / maxVal) * 100 : 0;
                      return (
                        <div key={site}>
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-xs text-jungle-muted capitalize">{site.replace(/_/g, " ")}</span>
                            <span className="text-xs font-semibold">{Math.round(val)}</span>
                          </div>
                          <div className="h-1.5 bg-jungle-deeper rounded-full overflow-hidden">
                            <div
                              className="h-full rounded-full transition-all"
                              style={{ width: `${barPct}%`, backgroundColor: "#c8a84e" }}
                            />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Per-site trend charts */}
              {lcsaSites.length > 0 ? (
                lcsaSites.map((site) => {
                  const history = siteHistoryData(site);
                  const currentScore = lcsa?.current.site_values[site];
                  return (
                    <div key={site} className="card">
                      <div className="flex items-baseline justify-between mb-2">
                        <h3 className="text-sm font-semibold capitalize">{site.replace(/_/g, " ")}</h3>
                        {currentScore !== undefined && (
                          <span
                            className={`text-xs font-bold px-2 py-0.5 rounded ${
                              currentScore >= 80
                                ? "text-green-400 bg-green-500/10"
                                : currentScore >= 60
                                ? "text-jungle-accent bg-jungle-accent/10"
                                : "text-red-400 bg-red-500/10"
                            }`}
                          >
                            {Math.round(currentScore)}
                          </span>
                        )}
                      </div>
                      {history.length >= 2 ? (
                        <MiniLineChart
                          data={history}
                          height={90}
                          color={currentScore !== undefined && currentScore >= 75 ? "#4ade80" : "#c8a84e"}
                          showPoints={history.length <= 10}
                        />
                      ) : (
                        <div className="h-14 flex items-center text-jungle-dim text-xs border border-dashed border-jungle-border rounded-lg px-3">
                          Not enough data yet
                        </div>
                      )}
                    </div>
                  );
                })
              ) : (
                <div className="card text-center py-12">
                  <p className="text-jungle-muted">No measurement data</p>
                  <p className="text-jungle-dim text-sm mt-2">
                    Submit tape measurements during check-in to see site-by-site LCSA trends
                  </p>
                  <a href="/checkin" className="btn-primary mt-4 inline-block px-6">
                    Start Check-in
                  </a>
                </div>
              )}
            </div>
          )}

          {/* Photos Tab */}
          {activeTab === "photos" && (
            <div className="space-y-4">
              <div className="card">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-semibold">Check-in Photos</h3>
                  <div className="flex gap-2">
                    {photos.length >= 2 && (
                      <button
                        onClick={() => {
                          setCompareMode(!compareMode);
                          resetCompare();
                        }}
                        className={`text-xs px-3 py-1.5 rounded-lg border transition-colors ${
                          compareMode
                            ? "bg-jungle-accent/20 border-jungle-accent text-jungle-accent"
                            : "border-jungle-border text-jungle-muted hover:border-jungle-accent hover:text-jungle-accent"
                        }`}
                      >
                        {compareMode ? "Cancel Compare" : "Compare"}
                      </button>
                    )}
                  </div>
                </div>

                {compareMode && (
                  <div className="mb-4 px-3 py-2 bg-jungle-accent/10 border border-jungle-accent/30 rounded-lg text-xs text-jungle-accent">
                    {!compareA
                      ? "Click a photo to select the first comparison image."
                      : !compareB
                      ? "Now click a second photo to compare."
                      : "Comparing selected photos."}
                  </div>
                )}

                {photos.length > 0 ? (
                  <div className="grid grid-cols-2 gap-3">
                    {photos.map((photo, idx) => {
                      const isSelected = compareA === photo.url || compareB === photo.url;
                      return (
                        <div
                          key={idx}
                          onClick={() => handlePhotoClick(photo.url)}
                          className={`rounded-xl overflow-hidden border-2 transition-all ${
                            compareMode ? "cursor-pointer" : ""
                          } ${
                            isSelected ? "border-jungle-accent" : "border-jungle-border"
                          }`}
                        >
                          {/* eslint-disable-next-line @next/next/no-img-element */}
                          <img
                            src={photo.url}
                            alt={`Check-in ${photo.date}`}
                            className="w-full aspect-[3/4] object-cover"
                          />
                          <div className="px-2 py-1.5 bg-jungle-deeper">
                            <p className="text-[10px] text-jungle-dim">{photo.date}</p>
                            {isSelected && (
                              <p className="text-[10px] text-jungle-accent font-semibold">Selected</p>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center py-16 border border-dashed border-jungle-border rounded-xl text-center gap-3">
                    <svg className="w-10 h-10 text-jungle-border" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                    </svg>
                    <div>
                      <p className="text-sm text-jungle-muted font-medium">No photos yet</p>
                      <p className="text-xs text-jungle-dim mt-1 max-w-xs">
                        Track your progress with check-in photos. Log your daily check-in to add photos.
                      </p>
                    </div>
                    <a href="/checkin" className="btn-primary text-sm px-5">
                      Go to Daily Check-In
                    </a>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Compare Modal */}
          {compareModalOpen && compareA && compareB && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4">
              <div className="bg-jungle-deeper border border-jungle-border rounded-2xl max-w-2xl w-full overflow-hidden">
                <div className="flex items-center justify-between px-4 py-3 border-b border-jungle-border">
                  <h3 className="text-sm font-semibold">Photo Comparison</h3>
                  <button onClick={resetCompare} className="text-jungle-muted hover:text-jungle-accent transition-colors">
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>
                <div className="grid grid-cols-2 gap-0">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={compareA} alt="Photo A" className="w-full aspect-[3/4] object-cover border-r border-jungle-border" />
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={compareB} alt="Photo B" className="w-full aspect-[3/4] object-cover" />
                </div>
                <div className="grid grid-cols-2 text-center text-[10px] text-jungle-dim border-t border-jungle-border">
                  <div className="py-2 border-r border-jungle-border">Before</div>
                  <div className="py-2">After</div>
                </div>
              </div>
            </div>
          )}
        </div>
      </main>

      <div className="md:hidden h-16" />
    </div>
  );
}
