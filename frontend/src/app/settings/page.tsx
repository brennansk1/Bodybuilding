"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import NavBar from "@/components/NavBar";
import { api } from "@/lib/api";

// ─── Types ────────────────────────────────────────────────────────────────────

interface Profile {
  sex: string;
  age: number | null;
  height_cm: number;
  division: string;
  competition_date: string | null;
  training_experience_years: number;
  wrist_circumference_cm: number | null;
  ankle_circumference_cm: number | null;
  manual_body_fat_pct: number | null;
  training_start_time: string | null;
  training_duration_min: number | null;
  cycle_tracking_enabled: boolean;
  cycle_start_date: string | null;
  available_equipment: string[];
  disliked_exercises: string[];
  injury_history: string[];
  preferences: {
    training_days_per_week?: number;
    preferred_split?: string;
    meal_count?: number;
    dietary_restrictions?: string[];
    display_name?: string;
    cardio_machine?: string;
    cut_threshold_bf_pct?: number;
    cheat_meals_per_week?: number;
    intra_workout_nutrition?: boolean;
    initial_phase?: string;
  };
}

interface ShareTokenResponse {
  share_token: string;
  expires_at: string;
}

// ─── Constants ────────────────────────────────────────────────────────────────

const DIVISIONS = [
  { value: "mens_open", label: "Men's Open" },
  { value: "classic_physique", label: "Men's Classic Physique" },
  { value: "mens_physique", label: "Men's Physique" },
  { value: "womens_bikini", label: "Women's Bikini" },
  { value: "womens_figure", label: "Women's Figure" },
  { value: "womens_physique", label: "Women's Physique" },
];

const SPLITS = [
  { value: "auto", label: "Auto — Algorithmic Split" },
  { value: "ppl", label: "Push / Pull / Legs" },
  { value: "upper_lower", label: "Upper / Lower" },
  { value: "full_body", label: "Full Body" },
  { value: "bro_split", label: "Bro Split (1 muscle/day)" },
];

const PHASES = [
  { value: "", label: "Auto — Engine decides" },
  { value: "bulk", label: "Bulk (Aggressive surplus)" },
  { value: "lean_bulk", label: "Lean Bulk (Moderate surplus)" },
  { value: "cut", label: "Cut (Deficit)" },
  { value: "maintain", label: "Maintain (TDEE)" },
  { value: "restoration", label: "Restoration (Post-show)" },
];

const EQUIPMENT_OPTIONS = [
  "barbell", "dumbbell", "cable", "machine", "smith_machine",
  "pull_up_bar", "bands", "bodyweight", "leg_press", "hack_squat",
];

const DIETARY_OPTIONS = [
  "vegetarian", "vegan", "gluten_free", "dairy_free",
  "no_shellfish", "no_pork", "halal", "kosher",
];

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function SettingsPage() {
  const router = useRouter();
  const { user, loading, logout } = useAuth();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [activeSection, setActiveSection] = useState<"profile" | "training" | "nutrition" | "account">("profile");

  // ── Profile fields ──────────────────────────────────────────────────────────
  const [sex, setSex] = useState("male");
  const [age, setAge] = useState("");
  const [heightCm, setHeightCm] = useState("");
  const [division, setDivision] = useState("mens_open");
  const [compDate, setCompDate] = useState("");
  const [expYears, setExpYears] = useState("");
  const [wrist, setWrist] = useState("");
  const [ankle, setAnkle] = useState("");
  const [manualBF, setManualBF] = useState("");
  const [cutThreshold, setCutThreshold] = useState("");
  const [currentPhase, setCurrentPhase] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [cycleEnabled, setCycleEnabled] = useState(false);
  const [cycleStartDate, setCycleStartDate] = useState("");

  // ── Training fields ─────────────────────────────────────────────────────────
  const [daysPerWeek, setDaysPerWeek] = useState("4");
  const [split, setSplit] = useState("ppl");
  const [trainingStartTime, setTrainingStartTime] = useState("10:00");
  const [trainingDuration, setTrainingDuration] = useState("75");
  const [cardioMachine, setCardioMachine] = useState("treadmill");
  const [intraWorkout, setIntraWorkout] = useState(false);
  const [equipment, setEquipment] = useState<string[]>([]);
  const [dislikedRaw, setDislikedRaw] = useState("");
  const [injuryRaw, setInjuryRaw] = useState("");

  // ── Nutrition fields ────────────────────────────────────────────────────────
  const [mealCount, setMealCount] = useState("5");
  const [dietaryRestrictions, setDietaryRestrictions] = useState<string[]>([]);
  const [cheatMeals, setCheatMeals] = useState("0");

  // ── Notifications ───────────────────────────────────────────────────────────
  const [notifyCheckin, setNotifyCheckin] = useState(false);
  const [notifyTraining, setNotifyTraining] = useState(false);
  const [notifyMeals, setNotifyMeals] = useState(false);
  const [notifPermission, setNotifPermission] = useState<NotificationPermission | "unavailable">("default");
  const [enablingNotif, setEnablingNotif] = useState(false);

  // ── Account ─────────────────────────────────────────────────────────────────
  const [exporting, setExporting] = useState(false);
  const [shareToken, setShareToken] = useState("");
  const [shareExpiry, setShareExpiry] = useState("");
  const [generatingShare, setGeneratingShare] = useState(false);
  const [shareCopied, setShareCopied] = useState(false);

  // ── Load ────────────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!loading && !user) { router.push("/auth/login"); return; }
    if (user) {
      api.get<Profile>("/onboarding/profile").then((p) => {
        setProfile(p);
        const prefs = p.preferences || {};
        // Profile
        setSex(p.sex || "male");
        setAge(p.age?.toString() ?? "");
        setHeightCm(p.height_cm?.toString() ?? "");
        setDivision(p.division || "mens_open");
        setCompDate(p.competition_date ?? "");
        setExpYears(p.training_experience_years?.toString() ?? "");
        setWrist(p.wrist_circumference_cm?.toString() ?? "");
        setAnkle(p.ankle_circumference_cm?.toString() ?? "");
        setManualBF(p.manual_body_fat_pct?.toString() ?? "");
        setCutThreshold(prefs.cut_threshold_bf_pct?.toString() ?? "");
        setCurrentPhase(prefs.initial_phase ?? "");
        setDisplayName(prefs.display_name ?? "");
        setCycleEnabled(p.cycle_tracking_enabled ?? false);
        setCycleStartDate(p.cycle_start_date ?? "");
        // Training
        setDaysPerWeek(prefs.training_days_per_week?.toString() ?? "4");
        setSplit(prefs.preferred_split ?? "auto");
        setTrainingStartTime(p.training_start_time ?? "10:00");
        setTrainingDuration(p.training_duration_min?.toString() ?? "75");
        setCardioMachine(prefs.cardio_machine ?? "treadmill");
        setIntraWorkout(prefs.intra_workout_nutrition ?? false);
        setEquipment(p.available_equipment ?? []);
        setDislikedRaw((p.disliked_exercises ?? []).join(", "));
        setInjuryRaw((p.injury_history ?? []).join(", "));
        // Nutrition
        setMealCount(prefs.meal_count?.toString() ?? "5");
        setDietaryRestrictions(prefs.dietary_restrictions ?? []);
        setCheatMeals(prefs.cheat_meals_per_week?.toString() ?? "0");
      }).catch(() => {});

      if (typeof window !== "undefined") {
        setNotifyCheckin(localStorage.getItem("notify_checkin") === "true");
        setNotifyTraining(localStorage.getItem("notify_training") === "true");
        setNotifyMeals(localStorage.getItem("notify_meals") === "true");
        if ("Notification" in window) setNotifPermission(Notification.permission);
        else setNotifPermission("unavailable");
      }
    }
  }, [user, loading, router]);

  if (loading || !user) return null;

  // ── Save ────────────────────────────────────────────────────────────────────
  const saveProfile = async () => {
    setSaving(true);
    try {
      await api.patch("/onboarding/profile", {
        sex,
        age: age ? parseInt(age) : null,
        height_cm: heightCm ? parseFloat(heightCm) : null,
        division,
        competition_date: compDate || null,
        training_experience_years: expYears ? parseInt(expYears) : 0,
        wrist_circumference_cm: wrist ? parseFloat(wrist) : null,
        ankle_circumference_cm: ankle ? parseFloat(ankle) : null,
        manual_body_fat_pct: manualBF ? parseFloat(manualBF) : null,
        training_start_time: trainingStartTime || null,
        training_duration_min: trainingDuration ? parseInt(trainingDuration) : null,
        cycle_tracking_enabled: cycleEnabled,
        cycle_start_date: cycleStartDate || null,
        available_equipment: equipment,
        disliked_exercises: dislikedRaw ? dislikedRaw.split(",").map(s => s.trim()).filter(Boolean) : [],
        injury_history: injuryRaw ? injuryRaw.split(",").map(s => s.trim()).filter(Boolean) : [],
        preferences: {
          display_name: displayName,
          preferred_split: split,
          training_days_per_week: parseInt(daysPerWeek),
          meal_count: parseInt(mealCount),
          dietary_restrictions: dietaryRestrictions,
          cardio_machine: cardioMachine,
          cut_threshold_bf_pct: cutThreshold ? parseFloat(cutThreshold) : null,
          cheat_meals_per_week: cheatMeals ? parseInt(cheatMeals) : 0,
          intra_workout_nutrition: intraWorkout,
          initial_phase: currentPhase || null,
        },
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } finally {
      setSaving(false);
    }

    setSyncing(true);
    try {
      await api.post("/engine1/run");
      await api.post("/engine2/program/generate");
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch { /* ignore */ } finally {
      setSyncing(false);
    }
  };

  // ── Helpers ─────────────────────────────────────────────────────────────────
  const toggleEquipment = (item: string) => {
    setEquipment(prev =>
      prev.includes(item) ? prev.filter(e => e !== item) : [...prev, item]
    );
  };

  const toggleDietary = (item: string) => {
    setDietaryRestrictions(prev =>
      prev.includes(item) ? prev.filter(d => d !== item) : [...prev, item]
    );
  };

  const handleEnableNotifications = async () => {
    if (!("Notification" in window)) return;
    setEnablingNotif(true);
    try {
      const perm = await Notification.requestPermission();
      setNotifPermission(perm);
      if (perm === "granted") {
        if (notifyCheckin) localStorage.setItem("notify_checkin", "true"); else localStorage.removeItem("notify_checkin");
        if (notifyTraining) localStorage.setItem("notify_training", "true"); else localStorage.removeItem("notify_training");
        if (notifyMeals) localStorage.setItem("notify_meals", "true"); else localStorage.removeItem("notify_meals");
      }
    } finally { setEnablingNotif(false); }
  };

  const handleExport = async () => {
    setExporting(true);
    try {
      const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null;
      const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
      const res = await fetch(`${baseUrl}/export/report`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) throw new Error("Export failed");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = "coronado-progress-report.pdf";
      document.body.appendChild(a); a.click();
      document.body.removeChild(a); URL.revokeObjectURL(url);
    } catch { /* */ } finally { setExporting(false); }
  };

  const handleGenerateShareLink = async () => {
    setGeneratingShare(true);
    try {
      const res = await api.post<ShareTokenResponse>("/auth/share-token");
      setShareToken(res.share_token); setShareExpiry(res.expires_at);
    } catch { /* */ } finally { setGeneratingShare(false); }
  };

  const shareUrl = shareToken
    ? `${typeof window !== "undefined" ? window.location.origin : ""}/share/${shareToken}`
    : "";

  const handleCopyShare = async () => {
    if (!shareUrl) return;
    try { await navigator.clipboard.writeText(shareUrl); setShareCopied(true); setTimeout(() => setShareCopied(false), 2000); }
    catch { /* */ }
  };

  const daysLeft = compDate
    ? Math.max(0, Math.round((new Date(compDate).getTime() - Date.now()) / 86400000))
    : null;

  // ── Render ───────────────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen">
      <NavBar username={user.username} onLogout={() => { logout(); router.push("/"); }} />

      <main className="container-app py-6">
        <div className="max-w-2xl mx-auto space-y-5">

          {/* Header */}
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold"><span className="text-jungle-accent">Settings</span></h1>
              <p className="text-jungle-muted text-sm mt-1">Profile & training preferences</p>
            </div>
            <a href="/dashboard" className="btn-secondary text-sm px-3 py-2">← Dashboard</a>
          </div>

          {/* Section tabs */}
          <div className="flex gap-1 bg-jungle-deeper border border-jungle-border rounded-xl p-1">
            {(["profile", "training", "nutrition", "account"] as const).map((sec) => (
              <button
                key={sec}
                onClick={() => setActiveSection(sec)}
                className={`flex-1 py-2 text-xs sm:text-sm rounded-lg transition-colors capitalize font-medium ${
                  activeSection === sec
                    ? "bg-jungle-accent text-jungle-dark"
                    : "text-jungle-muted hover:text-jungle-accent"
                }`}
              >
                {sec}
              </button>
            ))}
          </div>

          {/* ── PROFILE ── */}
          {activeSection === "profile" && (
            <div className="space-y-5">
              <div className="card space-y-4">
                <SectionHeader>Identity</SectionHeader>

                {/* Display name */}
                <div>
                  <label className="label-field">Display Name</label>
                  <input
                    type="text"
                    value={displayName}
                    onChange={(e) => setDisplayName(e.target.value)}
                    className="input-field mt-1"
                    placeholder="e.g. Alex"
                  />
                  <p className="text-[10px] text-jungle-dim mt-1">Shown on dashboard greeting</p>
                </div>

                {/* Sex */}
                <div>
                  <label className="label-field">Biological Sex</label>
                  <div className="grid grid-cols-2 gap-2 mt-2">
                    {[{ v: "male", l: "Male" }, { v: "female", l: "Female" }].map(({ v, l }) => (
                      <button
                        key={v}
                        onClick={() => setSex(v)}
                        className={`py-2.5 rounded-lg text-sm font-semibold border transition-colors ${
                          sex === v
                            ? "bg-jungle-accent text-jungle-dark border-jungle-accent"
                            : "bg-jungle-deeper border-jungle-border text-jungle-muted hover:border-jungle-accent/50"
                        }`}
                      >
                        {l}
                      </button>
                    ))}
                  </div>
                  <p className="text-[10px] text-jungle-dim mt-1">Used in all body fat and LBM calculations</p>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="label-field">Age</label>
                    <input
                      type="number"
                      value={age}
                      onChange={(e) => setAge(e.target.value)}
                      className="input-field mt-1"
                      placeholder="e.g. 28"
                      min={14} max={80}
                    />
                  </div>
                  <div>
                    <label className="label-field">Height (cm)</label>
                    <input
                      type="number"
                      step="0.5"
                      value={heightCm}
                      onChange={(e) => setHeightCm(e.target.value)}
                      className="input-field mt-1"
                      placeholder="e.g. 180"
                      min={100} max={250}
                    />
                    <p className="text-[10px] text-jungle-dim mt-1">Used in Navy BF% and weight cap</p>
                  </div>
                  <div>
                    <label className="label-field">Training Experience (yrs)</label>
                    <input
                      type="number"
                      value={expYears}
                      onChange={(e) => setExpYears(e.target.value)}
                      className="input-field mt-1"
                      placeholder="e.g. 5"
                      min={0} max={40}
                    />
                  </div>
                </div>
              </div>

              <div className="card space-y-4">
                <SectionHeader>Competition</SectionHeader>

                <div>
                  <label className="label-field">Division</label>
                  <select
                    value={division}
                    onChange={(e) => setDivision(e.target.value)}
                    className="input-field mt-1"
                  >
                    {DIVISIONS.map((d) => (
                      <option key={d.value} value={d.value}>{d.label}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="label-field">Competition Date</label>
                  <input
                    type="date"
                    value={compDate}
                    onChange={(e) => setCompDate(e.target.value)}
                    className="input-field mt-1"
                  />
                  {daysLeft !== null && (
                    <p className="text-xs mt-1">
                      <span className={daysLeft <= 14 ? "text-red-400" : daysLeft <= 56 ? "text-yellow-400" : "text-jungle-accent"}>
                        {daysLeft} days out
                      </span>
                      {daysLeft <= 21 && <span className="text-jungle-dim ml-1">— peak week protocol active</span>}
                    </p>
                  )}
                </div>

                <div>
                  <label className="label-field">Current Phase Override</label>
                  <select
                    value={currentPhase}
                    onChange={(e) => setCurrentPhase(e.target.value)}
                    className="input-field mt-1"
                  >
                    {PHASES.map((p) => (
                      <option key={p.value} value={p.value}>{p.label}</option>
                    ))}
                  </select>
                  <p className="text-[10px] text-jungle-dim mt-1">
                    Overrides the engine&apos;s recommended phase. Clear to restore auto mode.
                  </p>
                </div>
              </div>

              <div className="card space-y-4">
                <SectionHeader>Body Composition</SectionHeader>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="label-field">Wrist (cm)</label>
                    <input
                      type="number"
                      step="0.1"
                      value={wrist}
                      onChange={(e) => setWrist(e.target.value)}
                      className="input-field mt-1"
                      placeholder="e.g. 17.5"
                    />
                    <p className="text-[10px] text-jungle-dim mt-1">Structural frame anchor</p>
                  </div>
                  <div>
                    <label className="label-field">Ankle (cm)</label>
                    <input
                      type="number"
                      step="0.1"
                      value={ankle}
                      onChange={(e) => setAnkle(e.target.value)}
                      className="input-field mt-1"
                      placeholder="e.g. 22.0"
                    />
                    <p className="text-[10px] text-jungle-dim mt-1">Structural frame anchor</p>
                  </div>
                  <div>
                    <label className="label-field">Manual Body Fat %</label>
                    <input
                      type="number"
                      step="0.1"
                      value={manualBF}
                      onChange={(e) => setManualBF(e.target.value)}
                      className="input-field mt-1"
                      placeholder="e.g. 15.0"
                      min={3} max={50}
                    />
                    <p className="text-[10px] text-jungle-dim mt-1">Overrides caliper/tape globally</p>
                  </div>
                  <div>
                    <label className="label-field">Cut Threshold BF %</label>
                    <input
                      type="number"
                      step="0.1"
                      value={cutThreshold}
                      onChange={(e) => setCutThreshold(e.target.value)}
                      className="input-field mt-1"
                      placeholder="e.g. 18.0"
                    />
                    <p className="text-[10px] text-jungle-dim mt-1">BF% at which engine recommends a cut</p>
                  </div>
                </div>

                {/* Female-only: cycle tracking */}
                {sex === "female" && (
                  <div className="border-t border-jungle-border pt-4 space-y-3">
                    <Toggle
                      label="Menstrual cycle tracking"
                      checked={cycleEnabled}
                      onChange={setCycleEnabled}
                    />
                    <p className="text-[10px] text-jungle-dim -mt-1">
                      Enables cycle-phase water retention adjustments in weight trending
                    </p>
                    {cycleEnabled && (
                      <div>
                        <label className="label-field">Last period start date</label>
                        <input
                          type="date"
                          value={cycleStartDate}
                          onChange={(e) => setCycleStartDate(e.target.value)}
                          className="input-field mt-1"
                        />
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* ── TRAINING ── */}
          {activeSection === "training" && (
            <div className="space-y-5">
              <div className="card space-y-4">
                <SectionHeader>Schedule</SectionHeader>

                <div>
                  <label className="label-field">Training Days per Week</label>
                  <div className="grid grid-cols-5 gap-2 mt-2">
                    {[2, 3, 4, 5, 6].map((d) => (
                      <button
                        key={d}
                        onClick={() => setDaysPerWeek(d.toString())}
                        className={`py-2.5 rounded-lg text-sm font-semibold transition-colors ${
                          daysPerWeek === d.toString()
                            ? "bg-jungle-accent text-jungle-dark"
                            : "bg-jungle-deeper border border-jungle-border hover:border-jungle-accent text-jungle-muted"
                        }`}
                      >
                        {d}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="label-field">Training Start Time</label>
                    <input
                      type="time"
                      value={trainingStartTime}
                      onChange={(e) => setTrainingStartTime(e.target.value)}
                      className="input-field mt-1"
                    />
                    <p className="text-[10px] text-jungle-dim mt-1">Used for meal timing windows</p>
                  </div>
                  <div>
                    <label className="label-field">Session Duration (min)</label>
                    <input
                      type="number"
                      value={trainingDuration}
                      onChange={(e) => setTrainingDuration(e.target.value)}
                      className="input-field mt-1"
                      placeholder="75"
                      min={30} max={240}
                    />
                    <p className="text-[10px] text-jungle-dim mt-1">Affects peri-workout carb window</p>
                  </div>
                </div>
              </div>

              <div className="card space-y-4">
                <SectionHeader>Split Preference</SectionHeader>
                <div className="space-y-2">
                  {SPLITS.map((s) => (
                    <button
                      key={s.value}
                      onClick={() => setSplit(s.value)}
                      className={`w-full flex items-center gap-3 py-3 px-4 rounded-lg text-sm text-left border transition-colors ${
                        split === s.value
                          ? "border-jungle-accent bg-jungle-accent/10 text-jungle-accent"
                          : "border-jungle-border bg-jungle-deeper text-jungle-muted hover:border-jungle-accent/50"
                      }`}
                    >
                      <span className={`w-3 h-3 rounded-full border-2 shrink-0 ${
                        split === s.value ? "border-jungle-accent bg-jungle-accent" : "border-jungle-border"
                      }`} />
                      {s.label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="card space-y-4">
                <SectionHeader>Equipment & Preferences</SectionHeader>

                <div>
                  <label className="label-field mb-2 block">Available Equipment</label>
                  <div className="flex flex-wrap gap-2">
                    {EQUIPMENT_OPTIONS.map((item) => (
                      <button
                        key={item}
                        onClick={() => toggleEquipment(item)}
                        className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
                          equipment.includes(item)
                            ? "bg-jungle-accent/20 border-jungle-accent text-jungle-accent"
                            : "bg-jungle-deeper border-jungle-border text-jungle-muted hover:border-jungle-accent/50"
                        }`}
                      >
                        {item.replace(/_/g, " ")}
                      </button>
                    ))}
                  </div>
                  <p className="text-[10px] text-jungle-dim mt-2">Used to filter exercise selections in your program</p>
                </div>

                <Toggle
                  label="Intra-workout nutrition (sip carbs during training)"
                  checked={intraWorkout}
                  onChange={setIntraWorkout}
                />

                <div>
                  <label className="label-field">Cardio Machine</label>
                  <select
                    value={cardioMachine}
                    onChange={(e) => setCardioMachine(e.target.value)}
                    className="input-field mt-1"
                  >
                    <option value="treadmill">Treadmill</option>
                    <option value="stairmaster">StairMaster</option>
                  </select>
                </div>

                <div>
                  <label className="label-field">Disliked Exercises</label>
                  <input
                    type="text"
                    value={dislikedRaw}
                    onChange={(e) => setDislikedRaw(e.target.value)}
                    className="input-field mt-1"
                    placeholder="e.g. barbell squat, behind-neck press"
                  />
                  <p className="text-[10px] text-jungle-dim mt-1">Comma-separated — engine avoids prescribing these</p>
                </div>

                <div>
                  <label className="label-field">Injury History / Limitations</label>
                  <input
                    type="text"
                    value={injuryRaw}
                    onChange={(e) => setInjuryRaw(e.target.value)}
                    className="input-field mt-1"
                    placeholder="e.g. left shoulder impingement, lower back"
                  />
                  <p className="text-[10px] text-jungle-dim mt-1">Comma-separated — flags for exercise substitution</p>
                </div>
              </div>
            </div>
          )}

          {/* ── NUTRITION ── */}
          {activeSection === "nutrition" && (
            <div className="space-y-5">
              <div className="card space-y-4">
                <SectionHeader>Meal Planning</SectionHeader>

                <div>
                  <label className="label-field">Meals per Day</label>
                  <div className="grid grid-cols-6 gap-2 mt-2">
                    {[3, 4, 5, 6, 7, 8].map((n) => (
                      <button
                        key={n}
                        onClick={() => setMealCount(n.toString())}
                        className={`py-2.5 rounded-lg text-sm font-semibold transition-colors ${
                          mealCount === n.toString()
                            ? "bg-jungle-accent text-jungle-dark"
                            : "bg-jungle-deeper border border-jungle-border hover:border-jungle-accent text-jungle-muted"
                        }`}
                      >
                        {n}
                      </button>
                    ))}
                  </div>
                  <p className="text-[10px] text-jungle-dim mt-2">
                    {parseInt(mealCount) >= 6
                      ? "Competition-level frequency — maximizes MPS stimulation"
                      : parseInt(mealCount) >= 4
                      ? "Optimal for protein distribution across the day"
                      : "Minimum — combine peri-workout meals carefully"}
                  </p>
                </div>

                <div>
                  <label className="label-field">Cheat Meals / Week</label>
                  <div className="grid grid-cols-5 gap-2 mt-2">
                    {[0, 1, 2, 3, 4].map((n) => (
                      <button
                        key={n}
                        onClick={() => setCheatMeals(n.toString())}
                        className={`py-2.5 rounded-lg text-sm font-semibold transition-colors ${
                          cheatMeals === n.toString()
                            ? "bg-jungle-accent text-jungle-dark"
                            : "bg-jungle-deeper border border-jungle-border hover:border-jungle-accent text-jungle-muted"
                        }`}
                      >
                        {n}
                      </button>
                    ))}
                  </div>
                  <p className="text-[10px] text-jungle-dim mt-2">
                    {parseInt(cheatMeals) === 0
                      ? "Strict prep — no cheat meals"
                      : parseInt(cheatMeals) === 1
                      ? "One refeed-style meal — plan around it"
                      : "Multiple — flag in meal plan to track adherence"}
                  </p>
                </div>
              </div>

              <div className="card space-y-4">
                <SectionHeader>Dietary Restrictions</SectionHeader>
                <div className="flex flex-wrap gap-2">
                  {DIETARY_OPTIONS.map((item) => (
                    <button
                      key={item}
                      onClick={() => toggleDietary(item)}
                      className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
                        dietaryRestrictions.includes(item)
                          ? "bg-jungle-accent/20 border-jungle-accent text-jungle-accent"
                          : "bg-jungle-deeper border-jungle-border text-jungle-muted hover:border-jungle-accent/50"
                      }`}
                    >
                      {item.replace(/_/g, " ")}
                    </button>
                  ))}
                </div>
                <p className="text-[10px] text-jungle-dim">
                  Selected restrictions filter food choices in the meal planner
                </p>
              </div>
            </div>
          )}

          {/* ── ACCOUNT ── */}
          {activeSection === "account" && (
            <div className="space-y-5">
              {/* Credentials */}
              <div className="card space-y-3">
                <SectionHeader>Account</SectionHeader>
                <div className="space-y-2">
                  <div className="flex justify-between items-center py-2 text-sm border-b border-jungle-border">
                    <span className="text-jungle-muted">Username</span>
                    <span className="text-jungle-text font-medium">{user.username}</span>
                  </div>
                  <div className="flex justify-between items-center py-2 text-sm">
                    <span className="text-jungle-muted">Email</span>
                    <span className="text-jungle-text font-medium">{user.email}</span>
                  </div>
                </div>
                <button
                  onClick={() => { logout(); router.push("/"); }}
                  className="w-full py-2.5 text-sm text-red-400 border border-red-500/30 rounded-lg hover:bg-red-500/10 transition-colors"
                >
                  Log Out
                </button>
              </div>

              {/* Reminders */}
              <div className="card space-y-4">
                <div className="flex items-center justify-between">
                  <SectionHeader>Reminders</SectionHeader>
                  {notifPermission !== "unavailable" && (
                    <span className={`text-[10px] px-2 py-0.5 rounded font-semibold ${
                      notifPermission === "granted" ? "bg-green-500/20 text-green-400"
                      : notifPermission === "denied" ? "bg-red-500/20 text-red-400"
                      : "bg-jungle-border/40 text-jungle-muted"
                    }`}>
                      {notifPermission === "granted" ? "Allowed" : notifPermission === "denied" ? "Blocked" : "Not set"}
                    </span>
                  )}
                </div>

                {notifPermission === "denied" && (
                  <p className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
                    Notifications blocked — enable in browser settings
                  </p>
                )}

                <div className="space-y-3">
                  <Toggle label="Check-in reminder (Sunday mornings)" checked={notifyCheckin} onChange={(v) => {
                    setNotifyCheckin(v);
                    if (notifPermission === "granted") { if (v) localStorage.setItem("notify_checkin", "true"); else localStorage.removeItem("notify_checkin"); }
                  }} />
                  <Toggle label="Training day reminder" checked={notifyTraining} onChange={(v) => {
                    setNotifyTraining(v);
                    if (notifPermission === "granted") { if (v) localStorage.setItem("notify_training", "true"); else localStorage.removeItem("notify_training"); }
                  }} />
                  <Toggle label="Meal logging reminder (8 PM)" checked={notifyMeals} onChange={(v) => {
                    setNotifyMeals(v);
                    if (notifPermission === "granted") { if (v) localStorage.setItem("notify_meals", "true"); else localStorage.removeItem("notify_meals"); }
                  }} />
                </div>

                {notifPermission !== "granted" && notifPermission !== "unavailable" && (
                  <button
                    onClick={handleEnableNotifications}
                    disabled={enablingNotif || notifPermission === "denied"}
                    className="btn-primary w-full disabled:opacity-50"
                  >
                    {enablingNotif ? "Requesting..." : "Enable Notifications"}
                  </button>
                )}
              </div>

              {/* Export */}
              <div className="card space-y-3">
                <SectionHeader>Data Export</SectionHeader>
                <p className="text-xs text-jungle-dim">
                  Downloads a PDF of your PDS score, measurements, and training program.
                </p>
                <button onClick={handleExport} disabled={exporting} className="btn-primary w-full disabled:opacity-50">
                  {exporting ? "Downloading..." : "Download Progress Report"}
                </button>
              </div>

              {/* Share with coach */}
              <div className="card space-y-3">
                <SectionHeader>Share with Coach</SectionHeader>
                <p className="text-xs text-jungle-dim">
                  Generate a temporary link for read-only coach access to your data.
                </p>
                {!shareToken ? (
                  <button onClick={handleGenerateShareLink} disabled={generatingShare} className="btn-primary w-full disabled:opacity-50">
                    {generatingShare ? "Generating..." : "Generate Share Link"}
                  </button>
                ) : (
                  <div className="space-y-2">
                    <div className="flex gap-2">
                      <input
                        type="text"
                        readOnly
                        value={shareUrl}
                        className="input-field flex-1 text-xs font-mono"
                        onFocus={(e) => e.target.select()}
                      />
                      <button onClick={handleCopyShare} className="btn-secondary px-3 whitespace-nowrap text-xs">
                        {shareCopied ? "Copied!" : "Copy"}
                      </button>
                    </div>
                    {shareExpiry && (
                      <p className="text-[10px] text-jungle-dim">
                        Expires {new Date(shareExpiry).toLocaleDateString()}
                      </p>
                    )}
                    <button onClick={() => { setShareToken(""); setShareExpiry(""); }} className="text-xs text-red-400 hover:underline">
                      Revoke
                    </button>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Save button — profile, training, nutrition tabs */}
          {activeSection !== "account" && (
            <button
              onClick={saveProfile}
              disabled={saving || syncing}
              className="btn-primary w-full disabled:opacity-50"
            >
              {saved
                ? "Saved & Engines Updated!"
                : syncing
                ? "Updating Plan..."
                : saving
                ? "Saving..."
                : "Save Changes"}
            </button>
          )}
        </div>
      </main>

      <div className="md:hidden h-16" />
    </div>
  );
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function SectionHeader({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="text-xs font-semibold text-jungle-muted uppercase tracking-wider">{children}</h2>
  );
}

function Toggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-sm text-jungle-muted">{label}</span>
      <button
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={`relative w-10 h-5 rounded-full transition-colors shrink-0 ${checked ? "bg-jungle-accent" : "bg-jungle-border"}`}
      >
        <span className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform ${checked ? "translate-x-5" : "translate-x-0"}`} />
      </button>
    </div>
  );
}
