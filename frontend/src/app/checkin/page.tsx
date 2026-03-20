"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import NavBar from "@/components/NavBar";
import { api } from "@/lib/api";

interface QuickCheckinResult {
  weight_kg?: number;
  ari_score?: number;
  zone?: string;
  message?: string;
}

const MUSCLE_GROUPS = ["Chest", "Back", "Quads", "Hamstrings", "Delts", "Arms", "Calves", "Abs", "Glutes", "Lower Back"];

export default function CheckinPage() {
  const router = useRouter();
  const { user, loading, logout } = useAuth();
  const [mode, setMode] = useState<"quick" | "full" | null>(null);
  const [step, setStep] = useState(1);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<Record<string, unknown> | null>(null);

  // Quick mode state
  const [quickWeight, setQuickWeight] = useState("");
  const [quickRmssd, setQuickRmssd] = useState("");
  const [quickRestingHr, setQuickRestingHr] = useState("");
  const [quickSleep, setQuickSleep] = useState("7");
  const [quickSoreness, setQuickSoreness] = useState("3");
  const [quickSoreMuscles, setQuickSoreMuscles] = useState<string[]>([]);
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

  useEffect(() => {
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

  if (loading || !user) return null;

  const tapeSites = [
    "neck", "shoulders", "chest", "left_bicep", "right_bicep",
    "left_forearm", "right_forearm", "waist", "hips",
    "left_thigh", "right_thigh", "left_calf", "right_calf",
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

  const [showAdvanced, setShowAdvanced] = useState(false);

  useEffect(() => {
    const saved = localStorage.getItem("cpos_showAdvancedMeasurements");
    if (saved) setShowAdvanced(saved === "true");
  }, []);

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
        body_weight_kg: quickWeight ? parseFloat(quickWeight) : undefined,
        rmssd: quickRmssd ? parseFloat(quickRmssd) : undefined,
        resting_hr: quickRestingHr ? parseFloat(quickRestingHr) : undefined,
        sleep_quality: parseFloat(quickSleep),
        soreness_score: parseFloat(quickSoreness),
        sore_muscles: quickSoreMuscles,
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
      // 1. Submit Daily touchpoint (weight + HRV + adherence)
      await api.post("/checkin/daily", {
        body_weight_kg: bodyWeight ? parseFloat(bodyWeight) : undefined,
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
    <div className="min-h-screen bg-jungle-dark">
      <NavBar username={user.username} onLogout={() => { logout(); router.push("/"); }} />

      <main className="container-app py-6">
        <div className="max-w-2xl mx-auto space-y-6">

          {/* Mode selector — shown when mode is null */}
          {mode === null && (
            <>
              <div>
                <h1 className="text-2xl font-bold">
                  <span className="text-jungle-accent">Check-in</span>
                </h1>
                <p className="text-jungle-muted text-sm mt-1">Choose your check-in mode</p>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
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
                        Weekly Check-In
                      </p>
                      <p className="text-[10px] text-jungle-dim">~15 min</p>
                    </div>
                  </div>
                  <p className="text-xs text-jungle-muted">
                    Complete biological, photos, tape, skinfold, HRV, and adherence data. Recalibrates all three engines.
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
                  <h1 className="text-2xl font-bold">
                    Daily <span className="text-jungle-accent">Check-In</span>
                  </h1>
                  <p className="text-jungle-muted text-sm mt-0.5">Quick tracking, 2 minutes</p>
                </div>
              </div>

              {quickError && (
                <p className="text-jungle-danger text-sm bg-jungle-danger/10 py-2 px-4 rounded-lg">{quickError}</p>
              )}

              <div className="card space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="label-field">Weight (kg)</label>
                    <input
                      type="number"
                      step="0.1"
                      value={quickWeight}
                      onChange={(e) => setQuickWeight(e.target.value)}
                      className="input-field mt-1"
                      placeholder="e.g. 90.5"
                    />
                  </div>
                  <div>
                    <label className="label-field">HRV — RMSSD (ms)</label>
                    <input
                      type="number"
                      value={quickRmssd}
                      onChange={(e) => setQuickRmssd(e.target.value)}
                      className="input-field mt-1"
                      placeholder="e.g. 65"
                    />
                  </div>
                  <div>
                    <label className="label-field">Resting HR (bpm)</label>
                    <input
                      type="number"
                      value={quickRestingHr}
                      onChange={(e) => setQuickRestingHr(e.target.value)}
                      className="input-field mt-1"
                      placeholder="e.g. 58"
                    />
                  </div>
                </div>

                <div>
                  <label className="label-field">Sleep Quality (1–10)</label>
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
                <h1 className="text-2xl font-bold">
                  Daily <span className="text-jungle-accent">Check-In</span>
                </h1>
                <p className="text-jungle-muted text-sm mt-1">All done!</p>
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
                      <p className="text-xl font-bold text-jungle-accent mt-1">{quickResult.weight_kg}kg</p>
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
                      <label className="label-field">Body Weight (kg)</label>
                      <input type="number" step="0.1" value={bodyWeight} onChange={(e) => setBodyWeight(e.target.value)} className="input-field" placeholder="90.0" />
                    </div>
                    <h3 className="text-sm font-semibold text-jungle-accent uppercase tracking-wide pt-2">Tape (cm)</h3>
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                      {tapeSites.map((s) => (
                        <div key={s}>
                          <label className="block text-xs text-jungle-muted mb-1 capitalize">{s.replace(/_/g, " ")}</label>
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
                          <label className="block text-xs text-jungle-muted mb-1 capitalize">{s}</label>
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
                              <label className="block text-xs text-jungle-muted mb-1">{s.label}</label>
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
                              <label className="block text-xs text-jungle-muted mb-1">{s.label}</label>
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
                        <label className="label-field">HRV (RMSSD)</label>
                        <input type="number" value={rmssd} onChange={(e) => setRmssd(e.target.value)} className="input-field" placeholder="65" />
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
                                <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity flex flex-col items-center justify-center gap-2">
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
                          <p className="text-2xl font-bold">{result.body_weight_kg as number}kg</p>
                        </div>
                      ) : null}
                    </div>

                    {/* Adherence lock warning */}
                    {!!result.adherence_lock && (
                      <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-3 text-xs text-yellow-400">
                        ⚠ {result.adherence_lock as string}
                      </div>
                    )}

                    <a href="/dashboard" className="btn-primary w-full text-center block">
                      View Dashboard
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
        </div>
      </main>
    </div>
  );
}
