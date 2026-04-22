"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import NavBar from "@/components/NavBar";
import PageTitle from "@/components/PageTitle";
import MeasurementInstructions from "@/components/MeasurementInstructions";
import AppleWatchGuide from "@/components/AppleWatchGuide";
import { api } from "@/lib/api";

interface QuickCheckinResult {
  weight_kg?: number;
  ari_score?: number;
  zone?: string;
  message?: string;
}

const MUSCLE_GROUPS = ["Chest", "Back", "Quads", "Hamstrings", "Delts", "Arms", "Calves", "Abs", "Glutes", "Lower Back"];

const FEEDBACK_ICON_MAP: Record<string, { cls: string; svg: string }> = {
  check: { cls: "bg-green-500/20 text-green-400", svg: "M5 13l4 4L19 7" },
  warning: { cls: "bg-yellow-500/20 text-yellow-400", svg: "M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" },
  info: { cls: "bg-blue-500/20 text-blue-400", svg: "M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" },
  change: { cls: "bg-jungle-accent/20 text-jungle-accent", svg: "M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" },
};

function FeedbackReportModal({
  report,
  onClose,
}: {
  report: { week: number; summary: string; items: { category: string; icon: string; text: string }[] };
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-viltrum-obsidian/40 p-4" onClick={onClose}>
      <div
        className="bg-jungle-card border border-jungle-border rounded-2xl max-w-lg w-full max-h-[85vh] overflow-y-auto shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="sticky top-0 bg-jungle-card border-b border-jungle-border px-5 py-4 flex items-center justify-between rounded-t-2xl">
          <div>
            <h2 className="text-lg font-bold text-jungle-text">
              Week {report.week} <span className="text-jungle-accent">Feedback Report</span>
            </h2>
            <p className="text-[10px] text-jungle-dim mt-0.5">{report.summary}</p>
          </div>
          <button onClick={onClose} className="text-jungle-dim hover:text-jungle-muted text-xl leading-none ml-3">×</button>
        </div>
        <div className="px-5 py-4 space-y-3">
          {report.items.map((item, i) => {
            const icon = FEEDBACK_ICON_MAP[item.icon] || FEEDBACK_ICON_MAP.info;
            return (
              <div key={i} className="flex gap-3 items-start">
                <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${icon.cls}`}>
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={icon.svg} />
                  </svg>
                </div>
                <div className="flex-1 min-w-0">
                  <span className="text-[9px] text-jungle-dim uppercase tracking-wider font-medium">{item.category.replace(/_/g, " ")}</span>
                  <p className="text-sm text-jungle-text leading-relaxed mt-0.5">{item.text}</p>
                </div>
              </div>
            );
          })}
          {report.items.length === 0 && (
            <p className="text-jungle-muted text-sm text-center py-6">No feedback items this week. Keep doing what you&apos;re doing.</p>
          )}
        </div>
        <div className="px-5 pb-5 pt-2 border-t border-jungle-border">
          <div className="flex gap-3">
            <button onClick={onClose} className="flex-1 btn-secondary text-sm">Close</button>
            <a href="/dashboard" className="flex-1 btn-primary text-center text-sm">Dashboard</a>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function CheckinPage() {
  const router = useRouter();
  const { user, loading, logout } = useAuth();
  const [mode, setMode] = useState<"quick" | "full" | "fit3d" | null>(null);
  // Apple Watch guide modal
  type AwTab = "hrv" | "rhr" | "sleep" | "apps";
  const [awGuide, setAwGuide] = useState<AwTab | null>(null);
  const [step, setStep] = useState(1);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [showFeedbackReport, setShowFeedbackReport] = useState(false);

  // Gap detection (Block 4)
  const [gaps, setGaps] = useState<{
    missing_daily_checkins: string[];
    missed_workouts: string[];
    total_gaps: number;
  } | null>(null);
  const [backfilling, setBackfilling] = useState(false);
  const [backfillDate, setBackfillDate] = useState<string | null>(null);
  const [backfillWeight, setBackfillWeight] = useState("");
  const [backfillAdherence, setBackfillAdherence] = useState("80");

  // Unit preference
  const [useLbs, setUseLbs] = useState(false);
  useEffect(() => {
    setUseLbs(localStorage.getItem("useLbs") === "true");
  }, []);
  const unit = useLbs ? "lbs" : "kg";
  const toKg = (val: number) => useLbs ? val / 2.20462 : val;

  // Quick mode state
  const [quickWeight, setQuickWeight] = useState("");
  const [quickRmssd, setQuickRmssd] = useState("");
  const [quickRestingHr, setQuickRestingHr] = useState("");
  const [quickSleep, setQuickSleep] = useState("7");
  const [quickSleepHours, setQuickSleepHours] = useState("8");
  const [quickSoreness, setQuickSoreness] = useState("3");
  const [quickStress, setQuickStress] = useState("4");
  const [quickMood, setQuickMood] = useState("7");
  const [quickEnergy, setQuickEnergy] = useState("7");
  const [quickSoreMuscles, setQuickSoreMuscles] = useState<string[]>([]);
  const [quickNotes, setQuickNotes] = useState("");
  const [quickResult, setQuickResult] = useState<QuickCheckinResult | null>(null);
  const [quickSubmitting, setQuickSubmitting] = useState(false);
  const [quickError, setQuickError] = useState("");

  // Biological
  const [bodyWeight, setBodyWeight] = useState("");
  const [tape, setTape] = useState<Record<string, string>>({});
  const [originalTape, setOriginalTape] = useState<Record<string, string>>({});
  const [skinfolds, setSkinfolds] = useState<Record<string, string>>({});
  const [originalSkinfolds, setOriginalSkinfolds] = useState<Record<string, string>>({});

  // Photos
  const [frontPhoto, setFrontPhoto] = useState("");
  const [backPhoto, setBackPhoto] = useState("");
  const [sideLeftPhoto, setSideLeftPhoto] = useState("");
  const [sideRightPhoto, setSideRightPhoto] = useState("");
  const [frontPosePhoto, setFrontPosePhoto] = useState("");
  const [backPosePhoto, setBackPosePhoto] = useState("");
  const [photoUploading, setPhotoUploading] = useState<Record<string, boolean>>({});

  // HRV / Recovery
  const [rmssd, setRmssd] = useState("");
  const [restingHr, setRestingHr] = useState("");
  const [sleepQuality, setSleepQuality] = useState("7");
  const [soreness, setSoreness] = useState("3");
  const [soreMuscles, setSoreMuscles] = useState<string[]>([]);

  // Adherence
  const [nutritionAdherence, setNutritionAdherence] = useState("90");
  const [trainingAdherence, setTrainingAdherence] = useState("90");
  const [notes, setNotes] = useState("");

  // Posing practice state
  const [posingRec, setPosingRec] = useState<{
    division: string; weeks_out: number | null; frequency: string;
    duration_min: number; hold_seconds: number; intensity: string;
    notes: string; poses: { name: string; cue: string }[];
  } | null>(null);
  const [posingPracticed, setPosingPracticed] = useState<Set<string>>(new Set());
  const [posingDuration, setPosingDuration] = useState("");

  // Fit3D-specific state (all in original Fit3D units: lbs + inches)
  const [fit3dWeightLbs, setFit3dWeightLbs] = useState("");
  const [fit3dBodyFatPct, setFit3dBodyFatPct] = useState("");
  const [fit3dLeanMassLbs, setFit3dLeanMassLbs] = useState("");
  const [fit3dFatMassLbs, setFit3dFatMassLbs] = useState("");
  const [fit3dInch, setFit3dInch] = useState<Record<string, string>>({});
  const [fit3dShouldersCm, setFit3dShouldersCm] = useState(""); // not measured by Fit3D
  const [lastShouldersCm, setLastShouldersCm] = useState<number | null>(null);
  const [fit3dDone, setFit3dDone] = useState(false);

  const toggleSoreMuscle = (m: string) => {
    if (mode === "quick") {
      setQuickSoreMuscles(p => p.includes(m) ? p.filter(x => x !== m) : [...p, m]);
    } else {
      setSoreMuscles(p => p.includes(m) ? p.filter(x => x !== m) : [...p, m]);
    }
  };

  useEffect(() => {
    if (!loading && !user) router.push("/auth/login");
  }, [user, loading, router]);

  // Fetch check-in gaps on load
  useEffect(() => {
    if (user) {
      api.get<typeof gaps>("/checkin/gaps").then(setGaps).catch(() => {});
    }
  }, [user]);

  const handleBackfill = async (gapDate: string) => {
    setBackfilling(true);
    try {
      await api.post("/checkin/daily/backfill", {
        recorded_date: gapDate,
        body_weight_kg: backfillWeight ? parseFloat(backfillWeight) : null,
        nutrition_adherence_pct: parseFloat(backfillAdherence) || 80,
        training_adherence_pct: parseFloat(backfillAdherence) || 80,
      });
      // Remove from gaps
      setGaps(prev => prev ? {
        ...prev,
        missing_daily_checkins: prev.missing_daily_checkins.filter(d => d !== gapDate),
        total_gaps: prev.total_gaps - 1,
      } : null);
      setBackfillDate(null);
      setBackfillWeight("");
    } catch { /* toast? */ }
    finally { setBackfilling(false); }
  };

  // Fetch posing recommendation when any check-in mode is selected
  useEffect(() => {
    if (mode === "quick" || mode === "full") {
      api.get<typeof posingRec>("/checkin/posing-recommendation")
        .then(setPosingRec)
        .catch(() => {});
    }
  }, [mode]);

  useEffect(() => {
    if (mode === "fit3d") {
      api.get<{tape: Record<string, number>}>("/checkin/weekly/previous")
        .then(res => {
          if (res.tape?.shoulders) setLastShouldersCm(res.tape.shoulders);
        })
        .catch(() => {});
    }
    if (mode === "full") {
      api.get<{tape: Record<string, number>; skinfolds: Record<string, number>}>("/checkin/weekly/previous")
        .then(res => {
          const t: Record<string, string> = {};
          const ot: Record<string, string> = {};
          for (const [k, v] of Object.entries(res.tape || {})) {
            t[k] = String(v);
            ot[k] = String(v);
          }
          setTape(t);
          setOriginalTape(ot);

          const s: Record<string, string> = {};
          const os: Record<string, string> = {};
          for (const [k, v] of Object.entries(res.skinfolds || {})) {
            s[k] = String(v);
            os[k] = String(v);
          }
          setSkinfolds(s);
          setOriginalSkinfolds(os);
        })
        .catch(console.error);
    }
  }, [mode]);

  const [showAdvanced, setShowAdvanced] = useState(false);

  useEffect(() => {
    const saved = localStorage.getItem("cpos_showAdvancedMeasurements");
    if (saved) setShowAdvanced(saved === "true");
  }, []);

  if (loading || !user) return null;

  const tapeSites = [
    "neck", "shoulders", "chest", "left_bicep", "right_bicep",
    "left_forearm", "right_forearm", "waist", "hips",
    "left_thigh", "right_thigh", "left_calf", "right_calf",
  ];

  const FIT3D_SITES = [
    { key: "neck", label: "Neck" },
    { key: "chest", label: "Chest" },
    { key: "waist", label: "Waist" },
    { key: "hips", label: "Hips" },
    { key: "left_bicep", label: "Left Biceps" },
    { key: "right_bicep", label: "Right Biceps" },
    { key: "left_forearm", label: "Left Forearm" },
    { key: "right_forearm", label: "Right Forearm" },
    { key: "left_thigh", label: "Left Thigh" },
    { key: "right_thigh", label: "Right Thigh" },
    { key: "left_calf", label: "Left Calf" },
    { key: "right_calf", label: "Right Calf" },
  ];

  const advancedTapeSites = [
    { key: "chest_relaxed", label: "Chest (relaxed)", hint: "Lats relaxed — isolates pecs" },
    { key: "chest_lat_spread", label: "Chest (lat spread)", hint: "Lats flared — full torso" },
    { key: "back_width", label: "Back width", hint: "Linear breadth between rear axillary folds" },
    { key: "left_proximal_thigh", label: "L proximal thigh", hint: "Just below glute fold" },
    { key: "right_proximal_thigh", label: "R proximal thigh", hint: "Just below glute fold" },
    { key: "left_distal_thigh", label: "L distal thigh (VMO)", hint: "Just above patella" },
    { key: "right_distal_thigh", label: "R distal thigh (VMO)", hint: "Just above patella" },
  ];

  const sfSites = ["chest", "midaxillary", "tricep", "subscapular", "abdominal", "suprailiac", "thigh"];
  const advancedSfSites = [
    { key: "bicep", label: "Bicep", hint: "Anterior midline over belly" },
    { key: "lower_back", label: "Lower back", hint: "2 in. lateral to spine" },
    { key: "calf", label: "Calf", hint: "Medial aspect at max girth" },
  ];

  const toggleAdvanced = () => {
    const next = !showAdvanced;
    setShowAdvanced(next);
    localStorage.setItem("cpos_showAdvancedMeasurements", String(next));
  };

  const submitQuickCheckin = async () => {
    setQuickSubmitting(true);
    setQuickError("");
    try {
      const res = await api.post<QuickCheckinResult>("/checkin/daily", {
        body_weight_kg: quickWeight ? toKg(parseFloat(quickWeight)) : undefined,
        rmssd: quickRmssd ? parseFloat(quickRmssd) : undefined,
        resting_hr: quickRestingHr ? parseFloat(quickRestingHr) : undefined,
        sleep_quality: parseFloat(quickSleep),
        sleep_hours: quickSleepHours ? parseFloat(quickSleepHours) : undefined,
        soreness_score: parseFloat(quickSoreness),
        stress_score: quickStress ? parseFloat(quickStress) : undefined,
        mood_score: quickMood ? parseFloat(quickMood) : undefined,
        energy_score: quickEnergy ? parseFloat(quickEnergy) : undefined,
        sore_muscles: quickSoreMuscles,
        notes: quickNotes || undefined,
      });
      setQuickResult(res);
    } catch (e: unknown) {
      setQuickError(e instanceof Error ? e.message : "Daily check-in failed");
    } finally {
      setQuickSubmitting(false);
    }
  };

  const submitCheckin = async () => {
    setSubmitting(true);
    setError("");
    try {
      if (mode === "fit3d") {
        // ── Fit3D scan submission ──
        const IN_TO_CM = 2.54;
        const LBS_TO_KG = 0.453592;
        const weightKg = fit3dWeightLbs ? parseFloat(fit3dWeightLbs) * LBS_TO_KG : undefined;

        // Submit daily with weight only
        if (weightKg) {
          await api.post("/checkin/daily", { body_weight_kg: Math.round(weightKg * 10) / 10 });
        }

        // Convert inch circumferences to cm
        const tapeNums: Record<string, number | null> = {};
        for (const [k, v] of Object.entries(fit3dInch)) {
          if (v) tapeNums[k] = Math.round(parseFloat(v) * IN_TO_CM * 10) / 10;
        }
        // Shoulders: manual entry (cm), fallback to last measurement, then estimate from chest
        if (fit3dShouldersCm) {
          tapeNums.shoulders = parseFloat(fit3dShouldersCm);
        } else if (lastShouldersCm) {
          tapeNums.shoulders = lastShouldersCm;
        } else if (tapeNums.chest) {
          // Coaching heuristic: shoulder girth ≈ chest × 1.18 for typical male physiques
          tapeNums.shoulders = Math.round(tapeNums.chest * 1.18 * 10) / 10;
        }

        const res = await api.post<Record<string, unknown>>("/checkin/weekly", {
          ...tapeNums,
          body_fat_pct: fit3dBodyFatPct ? parseFloat(fit3dBodyFatPct) : undefined,
          lean_mass_kg: fit3dLeanMassLbs ? Math.round(parseFloat(fit3dLeanMassLbs) * LBS_TO_KG * 10) / 10 : undefined,
          fat_mass_kg: fit3dFatMassLbs ? Math.round(parseFloat(fit3dFatMassLbs) * LBS_TO_KG * 10) / 10 : undefined,
          scan_source: "fit3d",
        });
        setResult(res);
        setFit3dDone(true);
      } else {
        // ── Standard full check-in ──
        // 1. Submit Daily touchpoint (weight + HRV + adherence)
        await api.post("/checkin/daily", {
          body_weight_kg: bodyWeight ? toKg(parseFloat(bodyWeight)) : undefined,
          rmssd: rmssd ? parseFloat(rmssd) : undefined,
          resting_hr: restingHr ? parseFloat(restingHr) : undefined,
          sleep_quality: parseFloat(sleepQuality),
          soreness_score: parseFloat(soreness),
          sore_muscles: soreMuscles,
          nutrition_adherence_pct: parseFloat(nutritionAdherence),
          training_adherence_pct: parseFloat(trainingAdherence),
          notes,
        });

        // 2. Submit Weekly touchpoint (tape, skinfolds, photos)
        const tapeNums: Record<string, number | null> = {};
        for (const [k, v] of Object.entries(tape)) {
          tapeNums[k] = v ? parseFloat(v) : null;
        }
        const sfNums: Record<string, number | null> = {};
        for (const [k, v] of Object.entries(skinfolds)) {
          sfNums[`sf_${k}`] = v ? parseFloat(v) : null;
        }

        const res = await api.post<Record<string, unknown>>("/checkin/weekly", {
          ...tapeNums,
          ...sfNums,
          front_photo_url: frontPhoto || undefined,
          back_photo_url: backPhoto || undefined,
          side_left_photo_url: sideLeftPhoto || undefined,
          side_right_photo_url: sideRightPhoto || undefined,
          front_pose_photo_url: frontPosePhoto || undefined,
          back_pose_photo_url: backPosePhoto || undefined,
          notes,
        });
        setResult(res);
        setStep(5);
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Check-in failed");
    } finally {
      setSubmitting(false);
    }
  };

  const uploadPhoto = async (e: React.ChangeEvent<HTMLInputElement>, setter: (v: string) => void, key: string) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setPhotoUploading(prev => ({ ...prev, [key]: true }));
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await api.postFormData<{url: string}>("/upload", formData);
      const baseUrl = "http://localhost:8000";
      setter(`${baseUrl}${res.url}`);
    } catch (err) {
      console.error(err);
      setError("Photo upload failed");
    } finally {
      setPhotoUploading(prev => ({ ...prev, [key]: false }));
    }
  };

  return (
    <div className="min-h-screen">
      <NavBar username={user.username} onLogout={() => { logout(); router.push("/"); }} />

      <main className="container-app py-6">
        <div className="max-w-2xl mx-auto space-y-6">

          {/* Gap resolution banner (Block 4) */}
          {gaps && gaps.total_gaps > 0 && mode === null && (
            <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-xl p-4">
              <div className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-full bg-yellow-500/20 flex items-center justify-center flex-shrink-0">
                  <span className="text-yellow-400 text-sm font-bold">{gaps.total_gaps}</span>
                </div>
                <div className="flex-1">
                  <h3 className="text-sm font-bold text-yellow-400">Missed Check-ins</h3>
                  <p className="text-xs text-jungle-muted mt-0.5">
                    {gaps.missing_daily_checkins.length > 0 && `${gaps.missing_daily_checkins.length} daily check-in(s) missed`}
                    {gaps.missing_daily_checkins.length > 0 && gaps.missed_workouts.length > 0 && " · "}
                    {gaps.missed_workouts.length > 0 && `${gaps.missed_workouts.length} workout(s) not logged`}
                  </p>
                  <div className="flex flex-wrap gap-1.5 mt-2">
                    {gaps.missing_daily_checkins.slice(0, 7).map(d => (
                      <button
                        key={d}
                        onClick={() => { setBackfillDate(d); setBackfillWeight(""); }}
                        className={`text-[10px] px-2 py-1 rounded border transition-colors ${
                          backfillDate === d
                            ? "bg-yellow-500/20 border-yellow-500/50 text-yellow-300"
                            : "bg-jungle-deeper border-jungle-border text-jungle-muted hover:border-yellow-500/30"
                        }`}
                      >
                        {new Date(d + "T00:00:00").toLocaleDateString("en-US", { month: "short", day: "numeric" })}
                      </button>
                    ))}
                  </div>
                  {backfillDate && (
                    <div className="mt-3 flex items-center gap-2">
                      <input
                        type="number"
                        placeholder={`Weight (${useLbs ? "lbs" : "kg"})`}
                        value={backfillWeight}
                        onChange={e => setBackfillWeight(e.target.value)}
                        className="input-field text-xs w-28"
                      />
                      <button
                        onClick={() => handleBackfill(backfillDate)}
                        disabled={backfilling}
                        className="btn-primary text-xs px-3 py-1.5 disabled:opacity-50"
                      >
                        {backfilling ? "..." : "Backfill"}
                      </button>
                      <button onClick={() => setBackfillDate(null)} className="text-jungle-dim text-xs hover:text-jungle-muted">
                        Skip
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Mode selector — shown when mode is null */}
          {mode === null && (
            <>
              <PageTitle text="Check-in" subtitle="Choose your check-in mode" />
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <button
                  onClick={() => setMode("quick")}
                  className="card text-left hover:border-jungle-accent transition-colors border border-jungle-border group"
                >
                  <div className="flex items-center gap-3 mb-2">
                    <div className="w-9 h-9 rounded-lg bg-jungle-accent/15 flex items-center justify-center shrink-0">
                      <svg className="w-5 h-5 text-jungle-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 10V3L4 14h7v7l9-11h-7z" />
                      </svg>
                    </div>
                    <div>
                      <p className="font-semibold text-sm group-hover:text-jungle-accent transition-colors">
                        Daily Check-In
                      </p>
                      <p className="text-[10px] text-jungle-dim">~2 min</p>
                    </div>
                  </div>
                  <p className="text-xs text-jungle-muted">
                    Log weight, HRV, sleep, and soreness. Get your readiness score instantly.
                  </p>
                </button>

                <button
                  onClick={() => setMode("full")}
                  className="card text-left hover:border-jungle-accent transition-colors border border-jungle-border group"
                >
                  <div className="flex items-center gap-3 mb-2">
                    <div className="w-9 h-9 rounded-lg bg-jungle-accent/15 flex items-center justify-center shrink-0">
                      <svg className="w-5 h-5 text-jungle-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                      </svg>
                    </div>
                    <div>
                      <p className="font-semibold text-sm group-hover:text-jungle-accent transition-colors">
                        Weekly Full Check-In
                      </p>
                      <p className="text-[10px] text-jungle-dim">~10 min</p>
                    </div>
                  </div>
                  <p className="text-xs text-jungle-muted">
                    Full check-in: tape measurements, skinfolds, HRV, adherence, and progress photos. Recalibrates all engines.
                  </p>
                </button>

                <button
                  onClick={() => setMode("fit3d")}
                  className="card text-left hover:border-blue-400 transition-colors border border-jungle-border group"
                >
                  <div className="flex items-center gap-3 mb-2">
                    <div className="w-9 h-9 rounded-lg bg-blue-500/15 flex items-center justify-center shrink-0">
                      <svg className="w-5 h-5 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
                      </svg>
                    </div>
                    <div>
                      <p className="font-semibold text-sm group-hover:text-blue-400 transition-colors">
                        Fit 3D Scan Upload
                      </p>
                      <p className="text-[10px] text-blue-400/70">Twice per mesocycle</p>
                    </div>
                  </div>
                  <p className="text-xs text-jungle-muted">
                    Upload Fit 3D scan results (circumferences, body composition). Hard-recalibrates all three engines.
                  </p>
                </button>
              </div>
            </>
          )}

          {/* Daily check-in mode */}
          {mode === "quick" && !quickResult && (
            <>
              <div className="flex items-center gap-3">
                <button
                  onClick={() => setMode(null)}
                  className="text-jungle-muted hover:text-jungle-accent transition-colors"
                >
                  ←
                </button>
                <div>
                  <PageTitle text="Daily Check-In" subtitle="Quick tracking, 2 minutes" className="mb-0" />
                </div>
              </div>

              {quickError && (
                <p className="text-jungle-danger text-sm bg-jungle-danger/10 py-2 px-4 rounded-lg">{quickError}</p>
              )}

              <div className="card space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="label-field">Weight ({unit})</label>
                    <input
                      type="number"
                      step="0.1"
                      value={quickWeight}
                      onChange={(e) => setQuickWeight(e.target.value)}
                      className="input-field mt-1"
                      placeholder={useLbs ? "e.g. 200" : "e.g. 90.5"}
                    />
                  </div>
                  <div>
                    <div className="flex items-center justify-between">
                      <label className="label-field mb-0">HRV (ms)</label>
                      <button
                        type="button"
                        onClick={() => setAwGuide("hrv")}
                        className="text-[10px] text-jungle-dim hover:text-jungle-accent flex items-center gap-1"
                      >
                        ⌚ How to find
                      </button>
                    </div>
                    <input
                      type="number"
                      value={quickRmssd}
                      onChange={(e) => setQuickRmssd(e.target.value)}
                      className="input-field mt-1"
                      placeholder="e.g. 65"
                    />
                    <p className="text-[10px] text-jungle-dim mt-1">
                      Apple Watch reports SDNN. Enter that value — trends work the same.
                    </p>
                  </div>
                  <div>
                    <div className="flex items-center justify-between">
                      <label className="label-field mb-0">Resting HR (bpm)</label>
                      <button
                        type="button"
                        onClick={() => setAwGuide("rhr")}
                        className="text-[10px] text-jungle-dim hover:text-jungle-accent"
                      >
                        ⌚ How to find
                      </button>
                    </div>
                    <input
                      type="number"
                      value={quickRestingHr}
                      onChange={(e) => setQuickRestingHr(e.target.value)}
                      className="input-field mt-1"
                      placeholder="e.g. 58"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <div className="flex items-center justify-between">
                      <label className="label-field mb-0">Sleep Quality (1–10)</label>
                      <button
                        type="button"
                        onClick={() => setAwGuide("sleep")}
                        className="text-[10px] text-jungle-dim hover:text-jungle-accent"
                      >
                        ⌚ How to find
                      </button>
                    </div>
                    <input
                      type="range"
                      min="1"
                      max="10"
                      value={quickSleep}
                      onChange={(e) => setQuickSleep(e.target.value)}
                      className="w-full accent-jungle-accent mt-2"
                    />
                    <p className="text-center text-sm text-jungle-accent font-semibold mt-1">{quickSleep}/10</p>
                  </div>
                  <div>
                    <label className="label-field">Hours Slept</label>
                    <input
                      type="number"
                      step="0.25"
                      min="0"
                      max="16"
                      value={quickSleepHours}
                      onChange={(e) => setQuickSleepHours(e.target.value)}
                      className="input-field mt-1"
                      placeholder="8"
                    />
                  </div>
                </div>

                <div>
                  <label className="label-field">Soreness (1–10)</label>
                  <input
                    type="range"
                    min="1"
                    max="10"
                    value={quickSoreness}
                    onChange={(e) => setQuickSoreness(e.target.value)}
                    className="w-full accent-jungle-accent mt-2"
                  />
                  <p className="text-center text-sm text-jungle-accent font-semibold mt-1">{quickSoreness}/10</p>
                </div>

                <div className="grid grid-cols-3 gap-3">
                  <div>
                    <label className="label-field text-xs">Stress</label>
                    <input
                      type="range"
                      min="1"
                      max="10"
                      value={quickStress}
                      onChange={(e) => setQuickStress(e.target.value)}
                      className="w-full accent-jungle-accent mt-2"
                    />
                    <p className="text-center text-xs text-jungle-muted mt-0.5">{quickStress}/10 <span className="text-jungle-dim">(1=calm)</span></p>
                  </div>
                  <div>
                    <label className="label-field text-xs">Mood</label>
                    <input
                      type="range"
                      min="1"
                      max="10"
                      value={quickMood}
                      onChange={(e) => setQuickMood(e.target.value)}
                      className="w-full accent-jungle-accent mt-2"
                    />
                    <p className="text-center text-xs text-jungle-muted mt-0.5">{quickMood}/10</p>
                  </div>
                  <div>
                    <label className="label-field text-xs">Energy</label>
                    <input
                      type="range"
                      min="1"
                      max="10"
                      value={quickEnergy}
                      onChange={(e) => setQuickEnergy(e.target.value)}
                      className="w-full accent-jungle-accent mt-2"
                    />
                    <p className="text-center text-xs text-jungle-muted mt-0.5">{quickEnergy}/10</p>
                  </div>
                </div>

                <div className="pt-2">
                  <label className="label-field block flex items-center gap-1 mb-2">
                    Sore / Fatigued Muscles
                    <span className="text-[10px] text-jungle-dim font-normal ml-1 border px-1 rounded-sm relative -top-0.5">Select all</span>
                  </label>
                  <div className="flex flex-wrap gap-2">
                    {MUSCLE_GROUPS.map(m => (
                      <button
                        key={m}
                        type="button"
                        onClick={() => toggleSoreMuscle(m)}
                        className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors border ${
                          quickSoreMuscles.includes(m)
                            ? "bg-red-500/10 border-red-500/50 text-red-400"
                            : "bg-jungle-deeper border-jungle-border text-jungle-muted hover:border-jungle-accent/30 hover:text-jungle-accent/80"
                        }`}
                      >
                        {m}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Posing Practice */}
                {posingRec && posingRec.poses.length > 0 && (
                  <div className="pt-3 border-t border-jungle-border">
                    <div className="flex items-center justify-between mb-2">
                      <label className="label-field">Posing Practice</label>
                      <span className="text-[9px] px-2 py-0.5 rounded bg-jungle-accent/15 text-jungle-accent font-medium">
                        {posingRec.frequency} • {posingRec.duration_min} min
                      </span>
                    </div>
                    {posingRec.weeks_out !== null && (
                      <p className="text-[10px] text-jungle-dim mb-2">
                        {posingRec.weeks_out} weeks out — {posingRec.notes}
                      </p>
                    )}
                    <div className="space-y-1">
                      {posingRec.poses.map(pose => (
                        <button
                          key={pose.name}
                          type="button"
                          onClick={() => setPosingPracticed(prev => {
                            const next = new Set(prev);
                            next.has(pose.name) ? next.delete(pose.name) : next.add(pose.name);
                            return next;
                          })}
                          className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg text-left transition-colors border text-xs ${
                            posingPracticed.has(pose.name)
                              ? "bg-green-500/10 border-green-500/30 text-green-400"
                              : "bg-jungle-deeper border-jungle-border text-jungle-muted hover:border-jungle-accent/30"
                          }`}
                        >
                          <div className={`w-4 h-4 rounded border flex items-center justify-center shrink-0 ${
                            posingPracticed.has(pose.name) ? "bg-green-500/30 border-green-500" : "border-jungle-border"
                          }`}>
                            {posingPracticed.has(pose.name) && (
                              <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                              </svg>
                            )}
                          </div>
                          <div className="flex-1 min-w-0">
                            <span className="font-medium">{pose.name}</span>
                            <span className="text-jungle-dim ml-2">— {pose.cue}</span>
                          </div>
                        </button>
                      ))}
                    </div>
                    <div className="mt-2">
                      <label className="text-[9px] text-jungle-dim uppercase">Duration (min)</label>
                      <input
                        type="number"
                        value={posingDuration}
                        onChange={(e) => setPosingDuration(e.target.value)}
                        className="input-field mt-0.5 text-sm"
                        placeholder={String(posingRec.duration_min)}
                      />
                    </div>
                  </div>
                )}

                <div className="pt-2">
                  <label className="label-field">Notes (optional)</label>
                  <textarea
                    value={quickNotes}
                    onChange={(e) => setQuickNotes(e.target.value)}
                    rows={2}
                    className="input-field resize-none text-sm mt-1"
                    placeholder="How are you feeling today? Any observations..."
                  />
                </div>

                <button
                  onClick={submitQuickCheckin}
                  disabled={quickSubmitting}
                  className="btn-primary w-full disabled:opacity-50 mt-4"
                >
                  {quickSubmitting ? "Logging..." : "Submit Daily Check-In"}
                </button>
              </div>
            </>
          )}

          {/* Daily check-in result */}
          {mode === "quick" && quickResult && (
            <>
              <div>
                <PageTitle text="Daily Check-In" subtitle="All done!" className="mb-0" />
              </div>
              <div className="card space-y-4">
                <div className="text-center">
                  <div className="w-14 h-14 mx-auto rounded-full bg-green-500/20 flex items-center justify-center mb-3">
                    <svg className="w-7 h-7 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                  </div>
                  <h2 className="text-lg font-semibold text-green-400">Logged</h2>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  {quickResult.weight_kg !== undefined && (
                    <div className="bg-jungle-deeper rounded-lg p-3 text-center">
                      <p className="text-[10px] text-jungle-muted uppercase tracking-wider">Weight</p>
                      <p className="text-xl font-bold text-jungle-accent mt-1">{useLbs ? (quickResult.weight_kg! * 2.20462).toFixed(1) : quickResult.weight_kg}{unit}</p>
                    </div>
                  )}
                  {quickResult.ari_score !== undefined && (
                    <div className="bg-jungle-deeper rounded-lg p-3 text-center">
                      <p className="text-[10px] text-jungle-muted uppercase tracking-wider">ARI Score</p>
                      <p className="text-xl font-bold text-jungle-accent mt-1">{quickResult.ari_score}</p>
                      {quickResult.zone && (
                        <span className={`text-xs px-2 py-0.5 rounded mt-1 inline-block font-medium ${
                          quickResult.zone === "green"
                            ? "bg-green-500/20 text-green-400"
                            : quickResult.zone === "yellow"
                            ? "bg-yellow-500/20 text-yellow-400"
                            : "bg-red-500/20 text-red-400"
                        }`}>
                          {quickResult.zone} zone
                        </span>
                      )}
                    </div>
                  )}
                </div>

                <a href="/dashboard" className="btn-primary w-full text-center block">
                  Done — View Dashboard
                </a>
              </div>
            </>
          )}

          {/* Full check-in mode */}
          {mode === "full" && (
            <>
              <div className="flex items-center gap-3">
                {step === 1 && (
                  <button
                    onClick={() => setMode(null)}
                    className="text-jungle-muted hover:text-jungle-accent transition-colors"
                  >
                    ←
                  </button>
                )}
                <div>
                  <h1 className="text-2xl font-bold">Weekly <span className="text-jungle-accent">Check-In</span></h1>
                  <p className="text-jungle-muted text-sm mt-1">Record your progress to recalibrate all three engines</p>
                </div>
              </div>

              <div className="flex gap-1.5">
                {["Biological", "Recovery", "Adherence & Photos", "Submit"].map((label, i) => (
                  <button
                    key={label}
                    onClick={() => i + 1 < step && setStep(i + 1)}
                    className={`h-1.5 rounded-full transition-all ${
                      i + 1 <= step ? "flex-[2] bg-jungle-accent" : "flex-1 bg-jungle-border"
                    }`}
                  />
                ))}
              </div>

              {error && (
                <p className="text-jungle-danger text-sm bg-jungle-danger/10 py-2 px-4 rounded-lg">{error}</p>
              )}

              <div className="card space-y-4">
                {step === 1 && (
                  <>
                    <h2 className="text-lg font-semibold">Biological Data</h2>
                    <div>
                      <label className="label-field">Body Weight ({unit})</label>
                      <input type="number" step="0.1" value={bodyWeight} onChange={(e) => setBodyWeight(e.target.value)} className="input-field" placeholder="90.0" />
                    </div>
                    <h3 className="text-sm font-semibold text-jungle-accent uppercase tracking-wide pt-2">Tape (cm)</h3>
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                      {tapeSites.map((s) => (
                        <div key={s}>
                          <label className="block text-xs text-jungle-muted mb-1 capitalize">
                            <MeasurementInstructions siteKey={s} label={s.replace(/_/g, " ")} />
                          </label>
                          <div className="relative">
                            <input type="number" step="0.1" value={tape[s] || ""} onChange={(e) => setTape({ ...tape, [s]: e.target.value })} className={`input-field text-sm ${tape[s] && tape[s] === originalTape[s] ? 'text-jungle-muted' : 'text-blue-400 font-medium pr-8'}`} />
                            {tape[s] && originalTape[s] && tape[s] !== originalTape[s] && (
                              <button type="button" onClick={() => setTape({ ...tape, [s]: originalTape[s] })} className="absolute right-2 top-1/2 -translate-y-1/2 text-jungle-dim hover:text-blue-400 transition-colors" title="Revert to pre-filled value">
                                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6" /></svg>
                              </button>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                    <h3 className="text-sm font-semibold text-jungle-accent uppercase tracking-wide pt-2">Skinfolds (mm)</h3>
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                      {sfSites.map((s) => (
                        <div key={s}>
                          <label className="block text-xs text-jungle-muted mb-1 capitalize">
                            <MeasurementInstructions siteKey={`skinfold_${s}`} label={s} />
                          </label>
                          <div className="relative">
                            <input type="number" step="0.1" value={skinfolds[s] || ""} onChange={(e) => setSkinfolds({ ...skinfolds, [s]: e.target.value })} className={`input-field text-sm ${skinfolds[s] && skinfolds[s] === originalSkinfolds[s] ? 'text-jungle-muted' : 'text-blue-400 font-medium pr-8'}`} />
                            {skinfolds[s] && originalSkinfolds[s] && skinfolds[s] !== originalSkinfolds[s] && (
                              <button type="button" onClick={() => setSkinfolds({ ...skinfolds, [s]: originalSkinfolds[s] })} className="absolute right-2 top-1/2 -translate-y-1/2 text-jungle-dim hover:text-blue-400 transition-colors" title="Revert to pre-filled value">
                                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6" /></svg>
                              </button>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>

                    {/* Advanced measurements toggle */}
                    <button
                      type="button"
                      onClick={toggleAdvanced}
                      className="flex items-center gap-2 text-xs text-jungle-dim hover:text-jungle-accent transition-colors pt-3"
                    >
                      <svg className={`w-3 h-3 transition-transform ${showAdvanced ? "rotate-90" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                      </svg>
                      Advanced Measurements (isolation tracking)
                    </button>

                    {showAdvanced && (
                      <>
                        <h3 className="text-sm font-semibold text-jungle-accent uppercase tracking-wide pt-1">Advanced Tape (cm)</h3>
                        <p className="text-[10px] text-jungle-dim -mt-2">Isolate chest vs back, track quad regionality (VMO teardrop)</p>
                        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                          {advancedTapeSites.map((s) => (
                            <div key={s.key}>
                              <label className="block text-xs text-jungle-muted mb-1">
                                <MeasurementInstructions siteKey={s.key} label={s.label} />
                              </label>
                              <div className="relative">
                                <input type="number" step="0.1" value={tape[s.key] || ""} onChange={(e) => setTape({ ...tape, [s.key]: e.target.value })} className={`input-field text-sm ${tape[s.key] && tape[s.key] === originalTape[s.key] ? 'text-jungle-muted' : 'text-blue-400 font-medium pr-8'}`} placeholder={s.hint} />
                                {tape[s.key] && originalTape[s.key] && tape[s.key] !== originalTape[s.key] && (
                                  <button type="button" onClick={() => setTape({ ...tape, [s.key]: originalTape[s.key] })} className="absolute right-2 top-1/2 -translate-y-1/2 text-jungle-dim hover:text-blue-400 transition-colors" title="Revert to pre-filled value">
                                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6" /></svg>
                                  </button>
                                )}
                              </div>
                            </div>
                          ))}
                        </div>

                        <h3 className="text-sm font-semibold text-jungle-accent uppercase tracking-wide pt-2">Additional Skinfolds (mm)</h3>
                        <p className="text-[10px] text-jungle-dim -mt-2">Enables site-specific lean girth + Parrillo 9-site body fat</p>
                        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                          {advancedSfSites.map((s) => (
                            <div key={s.key}>
                              <label className="block text-xs text-jungle-muted mb-1">
                                <MeasurementInstructions siteKey={`skinfold_${s.key}`} label={s.label} />
                              </label>
                              <div className="relative">
                                <input type="number" step="0.1" value={skinfolds[s.key] || ""} onChange={(e) => setSkinfolds({ ...skinfolds, [s.key]: e.target.value })} className={`input-field text-sm ${skinfolds[s.key] && skinfolds[s.key] === originalSkinfolds[s.key] ? 'text-jungle-muted' : 'text-blue-400 font-medium pr-8'}`} placeholder={s.hint} />
                                {skinfolds[s.key] && originalSkinfolds[s.key] && skinfolds[s.key] !== originalSkinfolds[s.key] && (
                                  <button type="button" onClick={() => setSkinfolds({ ...skinfolds, [s.key]: originalSkinfolds[s.key] })} className="absolute right-2 top-1/2 -translate-y-1/2 text-jungle-dim hover:text-blue-400 transition-colors" title="Revert to pre-filled value">
                                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6" /></svg>
                                  </button>
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      </>
                    )}
                  </>
                )}

                {step === 2 && (
                  <>
                    <h2 className="text-lg font-semibold">Recovery & HRV</h2>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      <div>
                        <div className="flex items-center justify-between">
                          <label className="label-field mb-0">HRV (ms)</label>
                          <button
                            type="button"
                            onClick={() => setAwGuide("hrv")}
                            className="text-[10px] text-jungle-dim hover:text-jungle-accent"
                          >
                            ⌚ How
                          </button>
                        </div>
                        <input type="number" value={rmssd} onChange={(e) => setRmssd(e.target.value)} className="input-field" placeholder="65" />
                        <p className="text-[10px] text-jungle-dim mt-1">Apple Watch reports SDNN — works for trends.</p>
                      </div>
                      <div>
                        <label className="label-field">Resting HR (bpm)</label>
                        <input type="number" value={restingHr} onChange={(e) => setRestingHr(e.target.value)} className="input-field" placeholder="58" />
                      </div>
                      <div>
                        <label className="label-field">Sleep Quality (1-10)</label>
                        <input type="range" min="1" max="10" value={sleepQuality} onChange={(e) => setSleepQuality(e.target.value)} className="w-full accent-jungle-accent" />
                        <p className="text-center text-sm text-jungle-accent font-semibold">{sleepQuality}/10</p>
                      </div>
                      <div>
                        <label className="label-field">Soreness Overall (1-10)</label>
                        <input type="range" min="1" max="10" value={soreness} onChange={(e) => setSoreness(e.target.value)} className="w-full accent-jungle-accent" />
                        <p className="text-center text-sm text-jungle-accent font-semibold">{soreness}/10</p>
                      </div>
                    </div>
                    
                    <div className="pt-2">
                      <label className="label-field block flex items-center gap-1 mb-2">
                        Sore / Fatigued Muscles
                        <span className="text-[10px] text-jungle-dim font-normal ml-1 border px-1 rounded-sm relative -top-0.5">Select all</span>
                      </label>
                      <div className="flex flex-wrap gap-2">
                        {MUSCLE_GROUPS.map(m => (
                          <button
                            key={m}
                            type="button"
                            onClick={() => toggleSoreMuscle(m)}
                            className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors border ${
                              soreMuscles.includes(m)
                                ? "bg-red-500/10 border-red-500/50 text-red-400"
                                : "bg-jungle-deeper border-jungle-border text-jungle-muted hover:border-jungle-accent/30 hover:text-jungle-accent/80"
                            }`}
                          >
                            {m}
                          </button>
                        ))}
                      </div>
                    </div>
                  </>
                )}

                {step === 3 && (
                  <>
                    <h2 className="text-lg font-semibold border-b border-jungle-border pb-2">Adherence & Photos</h2>
                    
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-4">
                      <div>
                        <label className="label-field">Nutrition Adherence (%)</label>
                        <input type="number" min="0" max="100" value={nutritionAdherence} onChange={(e) => setNutritionAdherence(e.target.value)} className="input-field" />
                      </div>
                      <div>
                        <label className="label-field">Training Adherence (%)</label>
                        <input type="number" min="0" max="100" value={trainingAdherence} onChange={(e) => setTrainingAdherence(e.target.value)} className="input-field" />
                      </div>
                    </div>

                    <div className="mt-4">
                      <h3 className="text-sm font-semibold text-jungle-accent uppercase tracking-wide">Physique Photos</h3>
                      <p className="text-[10px] text-jungle-dim -mt-0.5 mb-2">Upload 6 required poses directly to your vault</p>
                      
                      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                        {[
                          { label: 'Front Relaxed', key: 'front', state: frontPhoto, setter: setFrontPhoto },
                          { label: 'Back Relaxed', key: 'back', state: backPhoto, setter: setBackPhoto },
                          { label: 'Side Left Relaxed', key: 'sideLeft', state: sideLeftPhoto, setter: setSideLeftPhoto },
                          { label: 'Side Right Relaxed', key: 'sideRight', state: sideRightPhoto, setter: setSideRightPhoto },
                          { label: 'Front Pose', key: 'frontPose', state: frontPosePhoto, setter: setFrontPosePhoto },
                          { label: 'Back Pose', key: 'backPose', state: backPosePhoto, setter: setBackPosePhoto },
                        ].map(p => (
                          <div key={p.key} className="relative">
                            <label className="block text-xs text-jungle-muted mb-1">{p.label}</label>
                            {p.state ? (
                              <div className="relative rounded-lg overflow-hidden border border-jungle-border aspect-[3/4] bg-jungle-deeper group">
                                <img src={p.state} alt={p.label} className="absolute inset-0 w-full h-full object-cover" />
                                <div className="absolute inset-0 bg-viltrum-obsidian/40 opacity-0 group-hover:opacity-100 transition-opacity flex flex-col items-center justify-center gap-2">
                                  <span className="text-xs text-white/90 font-medium px-2 text-center">{p.label}</span>
                                  <button type="button" onClick={() => p.setter("")} className="btn-secondary text-xs bg-red-500/80 hover:bg-red-500 text-white border-none py-1.5 px-3 rounded-full">Remove</button>
                                </div>
                              </div>
                            ) : (
                              <div className="relative">
                                <input 
                                  type="file" 
                                  accept="image/*" 
                                  onChange={(e) => uploadPhoto(e, p.setter, p.key)} 
                                  className="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-10" 
                                />
                                <div className={`flex flex-col gap-2 items-center justify-center border-2 border-dashed border-jungle-border rounded-lg aspect-[3/4] p-4 text-center text-sm text-jungle-muted hover:border-jungle-accent transition-colors ${photoUploading[p.key] ? 'opacity-50' : ''}`}>
                                  <svg className="w-8 h-8 text-jungle-dim mb-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
                                  </svg>
                                  {photoUploading[p.key] ? 'Uploading...' : 'Tap to Upload'}
                                </div>
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Posing Practice (weekly) */}
                    {posingRec && posingRec.poses.length > 0 && (
                      <div className="mt-4">
                        <div className="flex items-center justify-between mb-2">
                          <h3 className="text-sm font-semibold text-jungle-accent uppercase tracking-wide">Posing Practice</h3>
                          <span className="text-[9px] px-2 py-0.5 rounded bg-jungle-accent/15 text-jungle-accent font-medium">
                            {posingRec.frequency} • {posingRec.duration_min} min
                          </span>
                        </div>
                        {posingRec.weeks_out !== null && (
                          <p className="text-[10px] text-jungle-dim mb-2">
                            {posingRec.weeks_out} weeks out — {posingRec.notes}
                          </p>
                        )}
                        <div className="space-y-1">
                          {posingRec.poses.map(pose => (
                            <button
                              key={pose.name}
                              type="button"
                              onClick={() => setPosingPracticed(prev => {
                                const next = new Set(prev);
                                next.has(pose.name) ? next.delete(pose.name) : next.add(pose.name);
                                return next;
                              })}
                              className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg text-left transition-colors border text-xs ${
                                posingPracticed.has(pose.name)
                                  ? "bg-green-500/10 border-green-500/30 text-green-400"
                                  : "bg-jungle-deeper border-jungle-border text-jungle-muted hover:border-jungle-accent/30"
                              }`}
                            >
                              <div className={`w-4 h-4 rounded border flex items-center justify-center shrink-0 ${
                                posingPracticed.has(pose.name) ? "bg-green-500/30 border-green-500" : "border-jungle-border"
                              }`}>
                                {posingPracticed.has(pose.name) && (
                                  <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                                  </svg>
                                )}
                              </div>
                              <div className="flex-1 min-w-0">
                                <span className="font-medium">{pose.name}</span>
                                <span className="text-jungle-dim ml-2">— {pose.cue}</span>
                              </div>
                            </button>
                          ))}
                        </div>
                        <div className="grid grid-cols-2 gap-2 mt-2">
                          <div>
                            <label className="text-[9px] text-jungle-dim uppercase">Duration (min)</label>
                            <input
                              type="number"
                              value={posingDuration}
                              onChange={(e) => setPosingDuration(e.target.value)}
                              className="input-field mt-0.5 text-sm"
                              placeholder={String(posingRec.duration_min)}
                            />
                          </div>
                          <div>
                            <label className="text-[9px] text-jungle-dim uppercase">Poses practiced</label>
                            <p className="text-sm text-jungle-accent font-semibold mt-1.5">
                              {posingPracticed.size} / {posingRec.poses.length}
                            </p>
                          </div>
                        </div>
                      </div>
                    )}

                    <div className="mt-4">
                      <label className="label-field">Diary / Notes (optional)</label>
                      <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={3} className="input-field resize-none text-sm" placeholder="Anything noteworthy this week regarding sleep, performance, or bloating..." />
                    </div>
                  </>
                )}

                {step === 4 && (
                  <div className="text-center py-6 space-y-4">
                    <h2 className="text-lg font-semibold">Review & Submit</h2>
                    <div className="grid grid-cols-2 gap-3 text-sm max-w-sm mx-auto">
                      <div className="card text-center">
                        <p className="text-jungle-muted text-xs">Weight</p>
                        <p className="font-semibold">{bodyWeight || "—"} kg</p>
                      </div>
                      <div className="card text-center">
                        <p className="text-jungle-muted text-xs">HRV</p>
                        <p className="font-semibold">{rmssd || "—"} ms</p>
                      </div>
                      <div className="card text-center">
                        <p className="text-jungle-muted text-xs">Nutrition</p>
                        <p className="font-semibold">{nutritionAdherence}%</p>
                      </div>
                      <div className="card text-center">
                        <p className="text-jungle-muted text-xs">Training</p>
                        <p className="font-semibold">{trainingAdherence}%</p>
                      </div>
                    </div>
                    {frontPhoto || backPhoto || sideLeftPhoto || sideRightPhoto || frontPosePhoto || backPosePhoto ? (
                      <p className="text-xs text-green-400 font-medium">✓ Photos attached</p>
                    ) : (
                      <p className="text-[10px] text-yellow-400 border border-yellow-500/20 bg-yellow-500/5 rounded-md py-1 max-w-[200px] mx-auto">
                        ⚠ Warning: No photos attached.
                      </p>
                    )}
                  </div>
                )}

                {step === 5 && result && (
                  <div className="py-4 space-y-5">
                    <div className="text-center">
                      <div className="w-14 h-14 mx-auto rounded-full bg-green-500/20 flex items-center justify-center mb-3">
                        <svg className="w-7 h-7 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                        </svg>
                      </div>
                      <h2 className="text-lg font-semibold text-green-400">Check-in Processed</h2>
                      <p className="text-jungle-muted text-sm mt-1">
                        Week {result.week as number} • All engines recalibrated
                      </p>
                    </div>

                    {/* Engine results grid */}
                    <div className="grid grid-cols-2 gap-3">
                      {/* PDS */}
                      {!!result.pds && (
                        <div className="card text-center col-span-2">
                          <p className="text-[10px] text-jungle-muted uppercase tracking-wider">Physique Development Score</p>
                          <p className="text-4xl font-bold text-jungle-accent mt-1">
                            {(result.pds as { score: number }).score}
                          </p>
                          <p className="text-xs text-jungle-fern capitalize mt-1">
                            {(result.pds as { tier: string }).tier} tier
                          </p>
                        </div>
                      )}

                      {/* ARI */}
                      {!!result.ari && (
                        <div className="card text-center">
                          <p className="text-[10px] text-jungle-muted uppercase tracking-wider mb-1">ARI Score</p>
                          <p className="text-2xl font-bold text-jungle-accent">
                            {(result.ari as { score: number }).score}
                          </p>
                          <span className={`text-xs px-2 py-0.5 rounded mt-1 inline-block font-medium ${
                            (result.ari as { zone: string }).zone === "green"
                              ? "bg-green-500/20 text-green-400"
                              : (result.ari as { zone: string }).zone === "yellow"
                              ? "bg-yellow-500/20 text-yellow-400"
                              : "bg-red-500/20 text-red-400"
                          }`}>
                            {(result.ari as { zone: string }).zone} zone
                          </span>
                        </div>
                      )}

                      {/* Calorie adjustment */}
                      {result.calorie_adjustment !== undefined ? (
                        <div className="card text-center">
                          <p className="text-[10px] text-jungle-muted uppercase tracking-wider mb-1">Calorie Adjustment</p>
                          <p className={`text-2xl font-bold ${
                            (result.calorie_adjustment as number) > 0 ? "text-red-400" : "text-green-400"
                          }`}>
                            {(result.calorie_adjustment as number) > 0 ? "+" : ""}{result.calorie_adjustment as number}
                          </p>
                          <p className="text-[10px] text-jungle-dim mt-1">kcal/day</p>
                        </div>
                      ) : !result.ari ? (
                        <div className="card text-center">
                          <p className="text-[10px] text-jungle-muted uppercase tracking-wider mb-1">Body Weight</p>
                          <p className="text-2xl font-bold">{useLbs ? ((result.body_weight_kg as number) * 2.20462).toFixed(1) : String(result.body_weight_kg)}{unit}</p>
                        </div>
                      ) : null}
                    </div>

                    {/* Adherence lock warning */}
                    {!!result.adherence_lock && (
                      <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-3 text-xs text-yellow-400">
                        ⚠ {result.adherence_lock as string}
                      </div>
                    )}

                    {/* Feedback report button */}
                    {!!(result as Record<string, unknown>).feedback_report && (
                      <button
                        onClick={() => setShowFeedbackReport(true)}
                        className="btn-primary w-full"
                      >
                        View Weekly Feedback Report
                      </button>
                    )}

                    <a href="/dashboard" className="btn-secondary w-full text-center block">
                      Go to Dashboard
                    </a>
                  </div>
                )}

                {step < 5 && (
                  <div className="flex justify-between pt-4 border-t border-jungle-border mt-6">
                    {step > 1 ? (
                      <button onClick={() => setStep(step - 1)} className="btn-secondary">Back</button>
                    ) : (
                      <div />
                    )}
                    {step < 4 ? (
                      <button onClick={() => setStep(step + 1)} className="btn-primary">Continue</button>
                    ) : (
                      <button onClick={submitCheckin} disabled={submitting} className="btn-primary disabled:opacity-50">
                        {submitting ? "Processing..." : "Submit Check-in"}
                      </button>
                    )}
                  </div>
                )}
              </div>
            </>
          )}

          {/* Fit 3D Scan Upload mode */}
          {mode === "fit3d" && (
            <>
              <div className="flex items-center gap-3">
                <button onClick={() => { setMode(null); setFit3dDone(false); }} className="text-jungle-muted hover:text-jungle-accent transition-colors">
                  ←
                </button>
                <div>
                  <h2 className="text-xl font-bold">
                    <span className="text-blue-400">Fit 3D</span> Scan Upload
                  </h2>
                  <p className="text-jungle-muted text-xs mt-0.5">
                    Paste your Fit 3D report values (inches & lbs) — we convert automatically
                  </p>
                </div>
              </div>

              {fit3dDone && result ? (
                <div className="card space-y-5 py-4">
                  <div className="text-center">
                    <div className="w-14 h-14 mx-auto rounded-full bg-green-500/20 flex items-center justify-center mb-3">
                      <svg className="w-7 h-7 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                      </svg>
                    </div>
                    <h2 className="text-lg font-semibold text-green-400">Scan Processed</h2>
                    <p className="text-jungle-muted text-sm mt-1">All three engines recalibrated from Fit 3D data</p>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    {!!result.pds && (
                      <div className="card text-center col-span-2">
                        <p className="text-[10px] text-jungle-muted uppercase tracking-wider">Physique Development Score</p>
                        <p className="text-4xl font-bold text-jungle-accent mt-1">
                          {(result.pds as { score: number }).score}
                        </p>
                        <p className="text-xs text-jungle-fern capitalize mt-1">
                          {(result.pds as { tier: string }).tier} tier
                        </p>
                      </div>
                    )}
                    <div className="card text-center">
                      <p className="text-[10px] text-jungle-muted uppercase tracking-wider mb-1">Body Weight</p>
                      <p className="text-2xl font-bold text-jungle-accent">{fit3dWeightLbs} lbs</p>
                      <p className="text-[10px] text-jungle-dim">{(parseFloat(fit3dWeightLbs || "0") * 0.453592).toFixed(1)} kg</p>
                    </div>
                    <div className="card text-center">
                      <p className="text-[10px] text-jungle-muted uppercase tracking-wider mb-1">Body Fat</p>
                      <p className="text-2xl font-bold text-jungle-accent">{fit3dBodyFatPct}%</p>
                      <p className="text-[10px] text-jungle-dim">{fit3dLeanMassLbs ? `${(parseFloat(fit3dLeanMassLbs) * 0.453592).toFixed(1)} kg lean` : ""}</p>
                    </div>
                  </div>

                  {result.calorie_adjustment !== undefined && (
                    <div className="card text-center">
                      <p className="text-[10px] text-jungle-muted uppercase tracking-wider mb-1">Calorie Adjustment</p>
                      <p className={`text-2xl font-bold ${(result.calorie_adjustment as number) > 0 ? "text-red-400" : "text-green-400"}`}>
                        {(result.calorie_adjustment as number) > 0 ? "+" : ""}{result.calorie_adjustment as number} kcal/day
                      </p>
                    </div>
                  )}

                  <a href="/dashboard" className="btn-primary w-full text-center block">View Dashboard</a>
                </div>
              ) : (
              <div className="card space-y-4">
                <div className="bg-blue-500/10 border border-blue-500/20 rounded-lg p-3">
                  <p className="text-xs text-blue-400 font-medium">Scan Timing</p>
                  <p className="text-[10px] text-jungle-muted mt-1">
                    Upload twice per mesocycle: Scan 1 at MEV baseline (Week 1) and Scan 2 at MRV peak (deload week).
                    This measures the exact hypertrophic yield of each training block.
                  </p>
                </div>

                {/* Body Composition */}
                <div>
                  <p className="text-xs text-jungle-dim uppercase tracking-wide mb-2">Body Composition</p>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="label-field">Weight (lbs)</label>
                      <input type="number" step="0.1" value={fit3dWeightLbs} onChange={e => setFit3dWeightLbs(e.target.value)} className="input-field mt-1" placeholder="e.g. 206.2" />
                      {fit3dWeightLbs && <p className="text-[9px] text-jungle-dim mt-0.5">{(parseFloat(fit3dWeightLbs) * 0.453592).toFixed(1)} kg</p>}
                    </div>
                    <div>
                      <label className="label-field">Body Fat %</label>
                      <input type="number" step="0.01" value={fit3dBodyFatPct} onChange={e => setFit3dBodyFatPct(e.target.value)} className="input-field mt-1" placeholder="e.g. 22.71" />
                    </div>
                    <div>
                      <label className="label-field">Lean Mass (lbs)</label>
                      <input type="number" step="0.1" value={fit3dLeanMassLbs} onChange={e => setFit3dLeanMassLbs(e.target.value)} className="input-field mt-1" placeholder="e.g. 159.4" />
                      {fit3dLeanMassLbs && <p className="text-[9px] text-jungle-dim mt-0.5">{(parseFloat(fit3dLeanMassLbs) * 0.453592).toFixed(1)} kg</p>}
                    </div>
                    <div>
                      <label className="label-field">Fat Mass (lbs)</label>
                      <input type="number" step="0.1" value={fit3dFatMassLbs} onChange={e => setFit3dFatMassLbs(e.target.value)} className="input-field mt-1" placeholder="e.g. 46.8" />
                      {fit3dFatMassLbs && <p className="text-[9px] text-jungle-dim mt-0.5">{(parseFloat(fit3dFatMassLbs) * 0.453592).toFixed(1)} kg</p>}
                    </div>
                  </div>
                </div>

                {/* Circumferences in inches */}
                <div>
                  <p className="text-xs text-jungle-dim uppercase tracking-wide mb-2">Circumferences (inches → auto-converted to cm)</p>
                  <div className="grid grid-cols-2 gap-3">
                    {FIT3D_SITES.map(({ key, label }) => (
                      <div key={key}>
                        <label className="label-field">{label} (in)</label>
                        <input
                          type="number" step="0.1"
                          value={fit3dInch[key] || ""}
                          onChange={e => setFit3dInch(p => ({...p, [key]: e.target.value}))}
                          className="input-field mt-1"
                          placeholder="inches"
                        />
                        {fit3dInch[key] && <p className="text-[9px] text-jungle-dim mt-0.5">{(parseFloat(fit3dInch[key]) * 2.54).toFixed(1)} cm</p>}
                      </div>
                    ))}
                  </div>
                </div>

                {/* Shoulders — not measured by Fit3D */}
                <div className="bg-yellow-500/10 border border-yellow-500/20 rounded-lg p-3">
                  <div className="flex items-center justify-between mb-1">
                    <p className="text-xs text-yellow-400 font-medium">Shoulders (Manual)</p>
                    {lastShouldersCm && !fit3dShouldersCm && (
                      <button
                        onClick={() => setFit3dShouldersCm(String(lastShouldersCm))}
                        className="text-[10px] text-jungle-accent hover:text-jungle-accent/80 font-medium transition-colors"
                      >
                        Use Last ({lastShouldersCm} cm)
                      </button>
                    )}
                  </div>
                  <p className="text-[10px] text-jungle-muted mb-2">
                    Not measured by Fit 3D. Measure at the widest point of your deltoids for V-taper analysis.
                  </p>
                  <input
                    type="number" step="0.1"
                    value={fit3dShouldersCm}
                    onChange={e => setFit3dShouldersCm(e.target.value)}
                    className="input-field"
                    placeholder="Shoulder circumference (cm)"
                  />
                  {fit3dShouldersCm && lastShouldersCm && (
                    <p className="text-[9px] text-jungle-dim mt-1">
                      {parseFloat(fit3dShouldersCm) > lastShouldersCm ? "+" : ""}{(parseFloat(fit3dShouldersCm) - lastShouldersCm).toFixed(1)} cm vs last
                    </p>
                  )}
                </div>

                {/* Lean adjustment info */}
                <div className="bg-jungle-deeper rounded-lg p-3 border border-jungle-border">
                  <p className="text-[10px] text-jungle-dim uppercase tracking-wide mb-1">Lean Girth Normalization</p>
                  <p className="text-[10px] text-jungle-muted">
                    Fit 3D measures total circumferences including fat tissue. The engine applies a global lean adjustment
                    using your scan BF%: <span className="text-jungle-accent font-mono">C_lean = C_raw × √(1 − BF%)</span>.
                    For site-specific corrections, add caliper skinfolds via a Full Check-In.
                  </p>
                </div>

                {/* Engine recalibration summary */}
                <div className="bg-jungle-deeper rounded-lg p-3 border border-jungle-border">
                  <p className="text-[10px] text-jungle-dim uppercase tracking-wide mb-1">What happens next</p>
                  <ul className="text-[10px] text-jungle-muted space-y-1">
                    <li><span className="text-jungle-accent font-medium">Engine 1:</span> PDS recalibrated. Muscle gaps updated against lean Ghost Model ideals.</li>
                    <li><span className="text-jungle-accent font-medium">Engine 2:</span> Volume re-routed based on new gap priorities.</li>
                    <li><span className="text-jungle-accent font-medium">Engine 3:</span> Katch-McArdle BMR recalculated from scan LBM. Macros adjusted.</li>
                  </ul>
                </div>

                {error && <p className="text-red-400 text-xs">{error}</p>}

                <button
                  onClick={submitCheckin}
                  disabled={submitting || !fit3dWeightLbs}
                  className="btn-primary w-full disabled:opacity-50"
                >
                  {submitting ? "Recalibrating Engines..." : "Upload Scan & Recalibrate"}
                </button>
              </div>
              )}
            </>
          )}
        </div>
      </main>

      {/* ── Weekly Feedback Report Modal ── */}
      {(() => {
        if (!showFeedbackReport || !result) return null;
        const fr = (result as Record<string, unknown>).feedback_report;
        if (!fr) return null;
        return (
          <FeedbackReportModal
            report={fr as { week: number; summary: string; items: { category: string; icon: string; text: string }[] }}
            onClose={() => setShowFeedbackReport(false)}
          />
        );
      })()}

      {/* Apple Watch guide modal */}
      {awGuide && (
        <AppleWatchGuide initialTab={awGuide} onClose={() => setAwGuide(null)} />
      )}
    </div>
  );
}
