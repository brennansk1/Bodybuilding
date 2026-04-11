"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import NavBar from "@/components/NavBar";
import { showError, showSuccess } from "@/components/Toast";
import { api } from "@/lib/api";
import { validateRequired, validateRanges, extractErrorMessage } from "@/lib/validation";

// ─── Types ────────────────────────────────────────────────────────────────────

interface Profile {
  sex: string;
  age: number | null;
  height_cm: number;
  division: string;
  competition_date: string | null;
  program_start_date: string | null;
  training_experience_years: number;
  wrist_circumference_cm: number | null;
  ankle_circumference_cm: number | null;
  manual_body_fat_pct: number | null;
  training_start_time: string | null;
  training_end_time: string | null;
  training_time_anchor: string | null;
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
    fasted_cardio?: boolean;
    cut_threshold_bf_pct?: number;
    cheat_meals_per_week?: number;
    intra_workout_nutrition?: boolean;
    initial_phase?: string;
    preferred_proteins?: string[];
    preferred_carbs?: string[];
    preferred_fats?: string[];
    blacklisted_foods?: string[];
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

const PROTEIN_SOURCES = [
  "Chicken Breast", "Turkey Breast", "Lean Ground Turkey", "Lean Ground Beef",
  "Flank Steak", "Sirloin Steak", "Tilapia", "Cod", "Salmon", "Shrimp",
  "Tuna (canned)", "Egg Whites", "Whole Eggs", "Greek Yogurt (nonfat)",
  "Cottage Cheese (low-fat)", "Tofu (firm)", "Tempeh", "Seitan",
];

const CARB_SOURCES = [
  "White Rice", "Jasmine Rice", "Brown Rice", "Oats (rolled)",
  "Cream of Rice", "Sweet Potato", "Red Potato (boiled)", "Quinoa",
  "Ezekiel Bread", "Banana",
];

const FAT_SOURCES = [
  "Extra Virgin Olive Oil", "Avocado", "Almonds", "Peanut Butter",
  "Almond Butter", "Walnuts", "Coconut Oil", "Chia Seeds", "Flax Seeds",
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
  const [programStartDate, setProgramStartDate] = useState("");
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
  const [trainingEndTime, setTrainingEndTime] = useState("11:15");
  const [trainingTimeAnchor, setTrainingTimeAnchor] = useState<"start" | "end">("start");
  const [trainingDuration, setTrainingDuration] = useState("75");
  const [cardioMachine, setCardioMachine] = useState("treadmill");
  const [fastedCardio, setFastedCardio] = useState(true);
  const [intraWorkout, setIntraWorkout] = useState(false);
  const [equipment, setEquipment] = useState<string[]>([]);
  const [dislikedRaw, setDislikedRaw] = useState("");
  const [injuryRaw, setInjuryRaw] = useState("");

  // ── Nutrition fields ────────────────────────────────────────────────────────
  const [mealCount, setMealCount] = useState("5");
  const [dietaryRestrictions, setDietaryRestrictions] = useState<string[]>([]);
  const [cheatMeals, setCheatMeals] = useState("0");
  const [preferredProteins, setPreferredProteins] = useState<string[]>([]);
  const [preferredCarbs, setPreferredCarbs] = useState<string[]>([]);
  const [preferredFats, setPreferredFats] = useState<string[]>([]);
  const [blacklistedFoods, setBlacklistedFoods] = useState<string[]>([]);

  // ── Dashboard visualizations ────────────────────────────────────────────────
  const [dashViz, setDashViz] = useState<Record<string, boolean>>({});
  const [dashVizSaving, setDashVizSaving] = useState(false);

  // ── Telegram bot ────────────────────────────────────────────────────────────
  interface TelegramStatus {
    enabled: boolean;
    linked: boolean;
    bot_username: string | null;
    notify: Record<string, boolean>;
  }
  const [telegramStatus, setTelegramStatus] = useState<TelegramStatus | null>(null);
  const [telegramCode, setTelegramCode] = useState<string | null>(null);
  const [telegramDeepLink, setTelegramDeepLink] = useState<string | null>(null);
  const [telegramLoading, setTelegramLoading] = useState(false);

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
        setProgramStartDate(p.program_start_date ?? "");
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
        setTrainingEndTime(p.training_end_time ?? "11:15");
        setTrainingTimeAnchor((p.training_time_anchor as "start" | "end") ?? "start");
        setTrainingDuration(p.training_duration_min?.toString() ?? "75");
        setCardioMachine(prefs.cardio_machine ?? "treadmill");
        setFastedCardio(prefs.fasted_cardio ?? true);
        setIntraWorkout(prefs.intra_workout_nutrition ?? false);
        setEquipment(p.available_equipment ?? []);
        setDislikedRaw((p.disliked_exercises ?? []).join(", "));
        setInjuryRaw((p.injury_history ?? []).join(", "));
        // Nutrition
        setMealCount(prefs.meal_count?.toString() ?? "5");
        setDietaryRestrictions(prefs.dietary_restrictions ?? []);
        setCheatMeals(prefs.cheat_meals_per_week?.toString() ?? "0");
        setPreferredProteins(prefs.preferred_proteins ?? []);
        setPreferredCarbs(prefs.preferred_carbs ?? []);
        setPreferredFats(prefs.preferred_fats ?? []);
        setBlacklistedFoods(prefs.blacklisted_foods ?? []);
        // Dashboard visualizations — preferences.dashboard_viz
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        setDashViz(((prefs as any).dashboard_viz as Record<string, boolean>) ?? {});
      }).catch(() => {});

      if (typeof window !== "undefined") {
        setNotifyCheckin(localStorage.getItem("notify_checkin") === "true");
        setNotifyTraining(localStorage.getItem("notify_training") === "true");
        setNotifyMeals(localStorage.getItem("notify_meals") === "true");
        if ("Notification" in window) setNotifPermission(Notification.permission);
        else setNotifPermission("unavailable");
      }

      // Telegram link status
      api.get<TelegramStatus>("/telegram/status").then(setTelegramStatus).catch(() => {});
    }
  }, [user, loading, router]);

  if (loading || !user) return null;

  // ── Telegram helpers ────────────────────────────────────────────────────────
  const generateTelegramCode = async () => {
    setTelegramLoading(true);
    try {
      const res = await api.post<{
        code: string;
        deep_link: string;
        bot_username: string;
      }>("/telegram/link/generate", {});
      setTelegramCode(res.code);
      setTelegramDeepLink(res.deep_link);
    } catch (err) {
      showError(extractErrorMessage(err, "Couldn't generate a link code. Telegram may not be configured on this server."));
    } finally {
      setTelegramLoading(false);
    }
  };

  const unlinkTelegram = async () => {
    setTelegramLoading(true);
    try {
      await api.post("/telegram/unlink", {});
      setTelegramCode(null);
      setTelegramDeepLink(null);
      const fresh = await api.get<TelegramStatus>("/telegram/status");
      setTelegramStatus(fresh);
      showSuccess("Telegram disconnected");
    } catch (err) {
      showError(extractErrorMessage(err, "Couldn't unlink Telegram"));
    } finally {
      setTelegramLoading(false);
    }
  };

  const toggleTelegramNotify = async (key: string, value: boolean) => {
    if (!telegramStatus) return;
    const next = { ...telegramStatus.notify, [key]: value };
    setTelegramStatus({ ...telegramStatus, notify: next });
    try {
      await api.patch("/telegram/notifications", { [key]: value });
    } catch (err) {
      showError(extractErrorMessage(err, "Couldn't save Telegram preferences"));
      setTelegramStatus(telegramStatus);
    }
  };

  const TELEGRAM_NOTIFY_OPTIONS: { key: string; label: string }[] = [
    { key: "workout_reminder", label: "Workout start reminder" },
    { key: "tomorrow_workout", label: "Tomorrow's workout preview" },
    { key: "meal_reminder", label: "Meal time reminders" },
    { key: "weekly_checkin", label: "Weekly check-in reminder" },
    { key: "missed_checkin", label: "Missed check-in nudge" },
  ];

  // ── Dashboard viz toggle helper ─────────────────────────────────────────────
  const toggleDashViz = async (key: string, value: boolean) => {
    const next = { ...dashViz, [key]: value };
    setDashViz(next);
    setDashVizSaving(true);
    try {
      await api.patch("/onboarding/profile", { preferences: { dashboard_viz: next } });
    } catch (err) {
      showError(extractErrorMessage(err, "Couldn't save dashboard settings"));
      setDashViz(dashViz); // revert
    } finally {
      setDashVizSaving(false);
    }
  };

  const DASH_VIZ_OPTIONS: { key: string; label: string; desc: string }[] = [
    { key: "spider", label: "Proportion Spider", desc: "% of Ideal per muscle site" },
    { key: "muscle_gaps", label: "Muscle Gaps", desc: "Lean size vs. division ideal" },
    { key: "pds_trajectory", label: "PDS Trajectory", desc: "Glide path over time" },
    { key: "heatmap", label: "Hypertrophy Heatmap", desc: "Body map colored by gap" },
    { key: "symmetry", label: "Bilateral Symmetry", desc: "Left vs. right balance" },
    { key: "phase_rec", label: "Phase Recommendation", desc: "Current phase + urgency" },
    { key: "comp_class", label: "Competition Class", desc: "Division + weight cap" },
    { key: "growth_projection", label: "Growth Projection", desc: "Per-site % of ideal" },
    { key: "detail_metrics", label: "Detail Metrics", desc: "Lat spread, VMO" },
    { key: "ari", label: "Autonomic Fuel Gauge", desc: "ARI recovery readiness" },
    { key: "adherence", label: "Adherence Grid", desc: "12-week compliance" },
    { key: "prep_timeline", label: "Prep Timeline", desc: "Competition countdown" },
    { key: "strength_progression", label: "Strength Progression", desc: "e1RM of top lifts (new)" },
    { key: "body_weight_trend", label: "Body Weight Trend", desc: "Rolling avg + phase (new)" },
    { key: "macro_adherence", label: "Macro Adherence", desc: "30-day P/C/F target hit (new)" },
    { key: "weekly_volume", label: "Weekly Volume vs Landmarks", desc: "Sets vs MEV/MAV/MRV (new)" },
    { key: "recovery_trend", label: "Recovery Trend", desc: "ARI composite over time (new)" },
  ];

  // ── Save ────────────────────────────────────────────────────────────────────
  const saveProfile = async () => {
    // Validate required + ranges before hitting the API.
    const requiredErr = validateRequired(
      {
        sex,
        age: age,
        height_cm: heightCm,
        division,
      },
      {
        sex: "Sex",
        age: "Age",
        height_cm: "Height",
        division: "Division",
      }
    );
    if (requiredErr) {
      showError(requiredErr);
      return;
    }
    const rangeErr = validateRanges(
      {
        age: age ? parseInt(age) : null,
        height_cm: heightCm ? parseFloat(heightCm) : null,
        manual_body_fat_pct: manualBF ? parseFloat(manualBF) : null,
        training_duration_min: trainingDuration ? parseInt(trainingDuration) : null,
      },
      {
        age: { min: 14, max: 100, label: "Age" },
        height_cm: { min: 120, max: 230, label: "Height (cm)" },
        manual_body_fat_pct: { min: 3, max: 60, label: "Body fat %" },
        training_duration_min: { min: 20, max: 240, label: "Session duration" },
      }
    );
    if (rangeErr) {
      showError(rangeErr);
      return;
    }
    setSaving(true);
    try {
      await api.patch("/onboarding/profile", {
        sex,
        age: age ? parseInt(age) : null,
        height_cm: heightCm ? parseFloat(heightCm) : null,
        division,
        competition_date: compDate || null,
        program_start_date: programStartDate || null,
        training_experience_years: expYears ? parseInt(expYears) : 0,
        wrist_circumference_cm: wrist ? parseFloat(wrist) : null,
        ankle_circumference_cm: ankle ? parseFloat(ankle) : null,
        manual_body_fat_pct: manualBF ? parseFloat(manualBF) : null,
        training_start_time: trainingStartTime || null,
        training_end_time: trainingEndTime || null,
        training_time_anchor: trainingTimeAnchor,
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
          fasted_cardio: fastedCardio,
          cut_threshold_bf_pct: cutThreshold ? parseFloat(cutThreshold) : null,
          cheat_meals_per_week: cheatMeals ? parseInt(cheatMeals) : 0,
          intra_workout_nutrition: intraWorkout,
          initial_phase: currentPhase || null,
          preferred_proteins: preferredProteins,
          preferred_carbs: preferredCarbs,
          preferred_fats: preferredFats,
          blacklisted_foods: blacklistedFoods,
        },
      });
      setSaved(true);
      showSuccess("Profile saved");
      setTimeout(() => setSaved(false), 2500);
    } catch (err) {
      showError(extractErrorMessage(err, "Couldn't save profile"));
      setSaving(false);
      return;
    } finally {
      setSaving(false);
    }

    // Decouple: only run engines whose inputs actually changed.
    //  - Structural (training) fields → trigger Engine 1 + Engine 2 regen
    //  - Nutrition fields            → trigger Engine 3 meal plan regen
    //  - Identity-only fields (display_name, cycle tracking) → no regen
    const originalPrefs = profile?.preferences || {};
    const structuralKeysChanged =
      profile?.sex !== sex ||
      profile?.age !== (age ? parseInt(age) : null) ||
      profile?.height_cm !== (heightCm ? parseFloat(heightCm) : null) ||
      profile?.division !== division ||
      profile?.manual_body_fat_pct !== (manualBF ? parseFloat(manualBF) : null) ||
      profile?.wrist_circumference_cm !== (wrist ? parseFloat(wrist) : null) ||
      profile?.ankle_circumference_cm !== (ankle ? parseFloat(ankle) : null) ||
      (originalPrefs.training_days_per_week ?? 4) !== parseInt(daysPerWeek) ||
      (originalPrefs.preferred_split ?? "auto") !== split ||
      JSON.stringify(profile?.available_equipment ?? []) !== JSON.stringify(equipment) ||
      JSON.stringify(profile?.disliked_exercises ?? []) !== JSON.stringify(
        dislikedRaw ? dislikedRaw.split(",").map(s => s.trim()).filter(Boolean) : []
      ) ||
      JSON.stringify(profile?.injury_history ?? []) !== JSON.stringify(
        injuryRaw ? injuryRaw.split(",").map(s => s.trim()).filter(Boolean) : []
      );

    const nutritionChanged =
      (originalPrefs.meal_count ?? 5) !== parseInt(mealCount) ||
      JSON.stringify(originalPrefs.dietary_restrictions ?? []) !== JSON.stringify(dietaryRestrictions) ||
      JSON.stringify(originalPrefs.preferred_proteins ?? []) !== JSON.stringify(preferredProteins) ||
      JSON.stringify(originalPrefs.preferred_carbs ?? []) !== JSON.stringify(preferredCarbs) ||
      JSON.stringify(originalPrefs.preferred_fats ?? []) !== JSON.stringify(preferredFats) ||
      JSON.stringify(originalPrefs.blacklisted_foods ?? []) !== JSON.stringify(blacklistedFoods) ||
      (originalPrefs.cheat_meals_per_week ?? 0) !== parseInt(cheatMeals || "0") ||
      (originalPrefs.intra_workout_nutrition ?? false) !== intraWorkout ||
      (originalPrefs.initial_phase ?? "") !== (currentPhase || "") ||
      structuralKeysChanged;   // body composition changes affect macros

    const structuralChanged = structuralKeysChanged;

    // Nothing meaningful changed → skip the engine round-trip entirely.
    if (!structuralChanged && !nutritionChanged) {
      return;
    }

    setSyncing(true);
    const engineErrors: string[] = [];
    try {
      if (structuralChanged) {
        try {
          await api.post("/engine1/run", {});
        } catch (err) {
          engineErrors.push(`Engine 1: ${extractErrorMessage(err, "run failed")}`);
        }
        try {
          await api.post("/engine2/program/generate", {});
        } catch (err) {
          engineErrors.push(`Engine 2: ${extractErrorMessage(err, "program generation failed")}`);
        }
      }
      if (nutritionChanged) {
        try {
          await api.post("/engine3/meal-plan/invalidate", {});
          await api.post("/engine3/meal-plan/generate", {});
        } catch (err) {
          engineErrors.push(`Engine 3: ${extractErrorMessage(err, "meal plan generation failed")}`);
        }
      }
      if (engineErrors.length === 0) {
        showSuccess(
          structuralChanged && nutritionChanged
            ? "Saved & resynced training + nutrition"
            : structuralChanged
              ? "Saved & training program updated"
              : "Saved & meal plan updated"
        );
      } else {
        showError(engineErrors.join("; "));
      }
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } finally {
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
              <p className="text-jungle-muted text-sm mt-1">Manage your profile, training, and nutrition preferences</p>
            </div>
            <a href="/dashboard" className="btn-secondary text-sm px-3 py-2">Dashboard</a>
          </div>

          {/* Section tabs — with icons */}
          <div className="grid grid-cols-4 gap-1 bg-jungle-deeper border border-jungle-border rounded-xl p-1">
            {([
              { key: "profile" as const, label: "Profile", icon: "M" },
              { key: "training" as const, label: "Training", icon: "T" },
              { key: "nutrition" as const, label: "Nutrition", icon: "N" },
              { key: "account" as const, label: "Account", icon: "A" },
            ]).map(({ key, label, icon }) => (
              <button
                key={key}
                onClick={() => setActiveSection(key)}
                className={`py-2.5 rounded-lg transition-all text-center ${
                  activeSection === key
                    ? "bg-jungle-accent text-jungle-dark shadow-sm"
                    : "text-jungle-muted hover:text-jungle-accent hover:bg-jungle-card/50"
                }`}
              >
                <span className={`block text-lg font-bold leading-none ${activeSection === key ? "" : "opacity-50"}`}>{icon}</span>
                <span className="block text-[10px] mt-0.5 font-medium">{label}</span>
              </button>
            ))}
          </div>

          {/* ── PROFILE ── */}
          {activeSection === "profile" && (
            <div className="space-y-5">
              <div className="card space-y-4">
                <SectionHeader description="Basic profile information used across all engines">Identity</SectionHeader>

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
                <SectionHeader description="Competition details drive peak week protocol timing">Competition</SectionHeader>

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
                  <label className="label-field">Program Start Date</label>
                  <input
                    type="date"
                    value={programStartDate}
                    onChange={(e) => setProgramStartDate(e.target.value)}
                    className="input-field mt-1"
                  />
                  <p className="text-[10px] text-jungle-dim mt-0.5">When your training program begins. Defaults to today if empty.</p>
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
                <SectionHeader description="Structural measurements for genetic ceiling calculations">Body Composition</SectionHeader>

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
                    <p className="text-[10px] text-jungle-dim mt-1">
                      BF% at which engine recommends a mini-cut.
                      {!cutThreshold && " Leave empty to auto-compute from your weight cap."}
                    </p>
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
                <SectionHeader description="Training frequency and timing — drives meal plan scheduling">Schedule</SectionHeader>

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

                <div>
                  <label className="label-field">Anchor workout timing by</label>
                  <div className="grid grid-cols-2 gap-2 mt-1">
                    <button
                      type="button"
                      onClick={() => setTrainingTimeAnchor("start")}
                      className={`py-2 rounded-lg text-sm font-medium border transition-colors ${
                        trainingTimeAnchor === "start"
                          ? "border-jungle-accent bg-jungle-accent/15 text-jungle-accent"
                          : "border-jungle-border bg-jungle-deeper text-jungle-muted hover:border-jungle-accent/50"
                      }`}
                    >
                      Start Time
                    </button>
                    <button
                      type="button"
                      onClick={() => setTrainingTimeAnchor("end")}
                      className={`py-2 rounded-lg text-sm font-medium border transition-colors ${
                        trainingTimeAnchor === "end"
                          ? "border-jungle-accent bg-jungle-accent/15 text-jungle-accent"
                          : "border-jungle-border bg-jungle-deeper text-jungle-muted hover:border-jungle-accent/50"
                      }`}
                    >
                      End Time
                    </button>
                  </div>
                  <p className="text-[10px] text-jungle-dim mt-1">
                    Pick which side of the workout you schedule around — the other is estimated from set + rest durations.
                  </p>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  {trainingTimeAnchor === "start" ? (
                    <div>
                      <label className="label-field">Training Start Time</label>
                      <input
                        type="time"
                        value={trainingStartTime}
                        onChange={(e) => setTrainingStartTime(e.target.value)}
                        className="input-field mt-1"
                      />
                      <p className="text-[10px] text-jungle-dim mt-1">End time is computed from sets + rests.</p>
                    </div>
                  ) : (
                    <div>
                      <label className="label-field">Training End Time</label>
                      <input
                        type="time"
                        value={trainingEndTime}
                        onChange={(e) => setTrainingEndTime(e.target.value)}
                        className="input-field mt-1"
                      />
                      <p className="text-[10px] text-jungle-dim mt-1">Start time is computed from sets + rests.</p>
                    </div>
                  )}
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
                    <p className="text-[10px] text-jungle-dim mt-1">Default estimate (overridden by live calc).</p>
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
                  <label className="label-field">Preferred Cardio Machine</label>
                  <select
                    value={cardioMachine}
                    onChange={(e) => setCardioMachine(e.target.value)}
                    className="input-field mt-1"
                  >
                    <option value="treadmill">Treadmill (incline walk)</option>
                    <option value="stairmaster">StairMaster</option>
                    <option value="stationary_bike">Stationary Bike</option>
                    <option value="elliptical">Elliptical</option>
                  </select>
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <label className="label-field">Fasted Morning Cardio</label>
                    <p className="text-[10px] text-jungle-dim mt-0.5">AM cardio before eating — maximizes fat oxidation during prep</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setFastedCardio(!fastedCardio)}
                    className={`w-12 h-6 rounded-full transition-colors shrink-0 ml-3 ${fastedCardio ? "bg-jungle-accent" : "bg-jungle-border"}`}
                  >
                    <div className={`w-5 h-5 rounded-full bg-white shadow transition-transform ${fastedCardio ? "translate-x-6" : "translate-x-0.5"}`} />
                  </button>
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
                  <div className="grid grid-cols-7 gap-1.5 mt-2">
                    <button
                      onClick={() => setMealCount("0")}
                      className={`py-2.5 rounded-xl text-[10px] font-semibold transition-colors col-span-1 ${
                        mealCount === "0"
                          ? "bg-jungle-accent text-jungle-dark"
                          : "bg-jungle-deeper border border-jungle-border hover:border-jungle-accent text-jungle-muted"
                      }`}
                    >
                      Auto
                    </button>
                    {[3, 4, 5, 6, 7, 8].map((n) => (
                      <button
                        key={n}
                        onClick={() => setMealCount(n.toString())}
                        className={`py-2.5 rounded-xl text-sm font-semibold transition-colors ${
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
                    {mealCount === "0"
                      ? "Auto: engine calculates optimal meals based on your macros, weight, and MPS research"
                      : parseInt(mealCount) >= 6
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

              {/* Food Source Preferences */}
              <div className="card space-y-4">
                <SectionHeader description="Select your preferred foods — the meal planner will prioritize these choices">Food Source Preferences</SectionHeader>
                <p className="text-[10px] text-jungle-dim -mt-2">
                  Select your preferred sources for each macro. The meal planner will prioritize these choices.
                </p>

                {/* Protein Sources */}
                <div>
                  <label className="label-field">Primary Protein Sources</label>
                  <div className="flex flex-wrap gap-1.5 mt-2">
                    {PROTEIN_SOURCES.map((item) => (
                      <button
                        key={item}
                        onClick={() => {
                          if (blacklistedFoods.includes(item)) return;
                          setPreferredProteins((prev) =>
                            prev.includes(item) ? prev.filter((x) => x !== item) : [...prev, item]
                          );
                        }}
                        className={`px-2.5 py-1.5 rounded-lg text-[11px] font-medium border transition-colors ${
                          blacklistedFoods.includes(item)
                            ? "bg-red-500/10 border-red-500/30 text-red-400/50 line-through cursor-not-allowed"
                            : preferredProteins.includes(item)
                            ? "bg-blue-500/20 border-blue-500/50 text-blue-400"
                            : "bg-jungle-deeper border-jungle-border text-jungle-muted hover:border-blue-500/30"
                        }`}
                      >
                        {item}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Carb Sources */}
                <div>
                  <label className="label-field">Primary Carb Sources</label>
                  <div className="flex flex-wrap gap-1.5 mt-2">
                    {CARB_SOURCES.map((item) => (
                      <button
                        key={item}
                        onClick={() => {
                          if (blacklistedFoods.includes(item)) return;
                          setPreferredCarbs((prev) =>
                            prev.includes(item) ? prev.filter((x) => x !== item) : [...prev, item]
                          );
                        }}
                        className={`px-2.5 py-1.5 rounded-lg text-[11px] font-medium border transition-colors ${
                          blacklistedFoods.includes(item)
                            ? "bg-red-500/10 border-red-500/30 text-red-400/50 line-through cursor-not-allowed"
                            : preferredCarbs.includes(item)
                            ? "bg-amber-500/20 border-amber-500/50 text-amber-400"
                            : "bg-jungle-deeper border-jungle-border text-jungle-muted hover:border-amber-500/30"
                        }`}
                      >
                        {item}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Fat Sources */}
                <div>
                  <label className="label-field">Primary Fat Sources</label>
                  <div className="flex flex-wrap gap-1.5 mt-2">
                    {FAT_SOURCES.map((item) => (
                      <button
                        key={item}
                        onClick={() => {
                          if (blacklistedFoods.includes(item)) return;
                          setPreferredFats((prev) =>
                            prev.includes(item) ? prev.filter((x) => x !== item) : [...prev, item]
                          );
                        }}
                        className={`px-2.5 py-1.5 rounded-lg text-[11px] font-medium border transition-colors ${
                          blacklistedFoods.includes(item)
                            ? "bg-red-500/10 border-red-500/30 text-red-400/50 line-through cursor-not-allowed"
                            : preferredFats.includes(item)
                            ? "bg-rose-500/20 border-rose-500/50 text-rose-400"
                            : "bg-jungle-deeper border-jungle-border text-jungle-muted hover:border-rose-500/30"
                        }`}
                      >
                        {item}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Blacklisted Foods */}
                <div>
                  <label className="label-field">Blacklist (never include)</label>
                  <p className="text-[10px] text-jungle-dim mt-0.5 mb-2">
                    Long-press or click any food above, then tap here to blacklist it
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {[...PROTEIN_SOURCES, ...CARB_SOURCES, ...FAT_SOURCES]
                      .filter((f) => !preferredProteins.includes(f) && !preferredCarbs.includes(f) && !preferredFats.includes(f))
                      .map((item) => (
                        <button
                          key={item}
                          onClick={() =>
                            setBlacklistedFoods((prev) =>
                              prev.includes(item) ? prev.filter((x) => x !== item) : [...prev, item]
                            )
                          }
                          className={`px-2 py-1 rounded-lg text-[10px] font-medium border transition-colors ${
                            blacklistedFoods.includes(item)
                              ? "bg-red-500/20 border-red-500/50 text-red-400"
                              : "bg-jungle-deeper border-jungle-border text-jungle-dim hover:border-red-500/30"
                          }`}
                        >
                          {blacklistedFoods.includes(item) ? "✕ " : ""}{item}
                        </button>
                      ))}
                  </div>
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

              {/* Telegram Bot */}
              <div className="card space-y-3">
                <div className="flex items-center justify-between">
                  <SectionHeader>Telegram Bot</SectionHeader>
                  {telegramStatus?.linked && (
                    <span className="text-[10px] px-2 py-0.5 rounded font-semibold bg-green-500/20 text-green-400">
                      Linked
                    </span>
                  )}
                  {telegramStatus && !telegramStatus.enabled && (
                    <span className="text-[10px] px-2 py-0.5 rounded font-semibold bg-jungle-border/40 text-jungle-muted">
                      Disabled on server
                    </span>
                  )}
                </div>
                {telegramStatus && !telegramStatus.enabled ? (
                  <p className="text-xs text-jungle-dim">
                    The bot isn&apos;t configured on this deployment. Ask the admin to set
                    <code className="mx-1 px-1 bg-jungle-deeper rounded text-jungle-accent">TELEGRAM_BOT_TOKEN</code>
                    in the backend environment.
                  </p>
                ) : telegramStatus?.linked ? (
                  <>
                    <p className="text-xs text-jungle-dim">
                      Your Coronado account is linked to Telegram. Adjust which reminders
                      you receive below, or disconnect the chat.
                    </p>
                    <div className="space-y-2">
                      {TELEGRAM_NOTIFY_OPTIONS.map((opt) => (
                        <div
                          key={opt.key}
                          className="flex items-center justify-between py-1.5 border-b border-jungle-border/30 last:border-b-0"
                        >
                          <span className="text-sm text-jungle-text">{opt.label}</span>
                          <Toggle
                            label=""
                            checked={telegramStatus.notify[opt.key] !== false}
                            onChange={(v) => toggleTelegramNotify(opt.key, v)}
                          />
                        </div>
                      ))}
                    </div>
                    <button
                      onClick={unlinkTelegram}
                      disabled={telegramLoading}
                      className="w-full py-2 text-sm text-red-400 border border-red-500/30 rounded-lg hover:bg-red-500/10 transition-colors disabled:opacity-50"
                    >
                      {telegramLoading ? "Disconnecting..." : "Disconnect Telegram"}
                    </button>
                  </>
                ) : (
                  <>
                    <p className="text-xs text-jungle-dim">
                      Link your Coronado account to Telegram to get workout previews,
                      meal reminders, and check-in nudges directly in chat. Generate a
                      one-time code and send it to the bot.
                    </p>
                    {telegramCode ? (
                      <div className="space-y-2">
                        <div className="flex items-center justify-between rounded-lg bg-jungle-deeper px-3 py-3">
                          <div>
                            <p className="text-[10px] text-jungle-dim uppercase tracking-wide">Link code</p>
                            <p className="text-2xl font-mono font-bold text-jungle-accent tracking-widest">{telegramCode}</p>
                          </div>
                          <span className="text-[10px] text-jungle-dim">Expires in 15 min</span>
                        </div>
                        {telegramDeepLink && (
                          <a
                            href={telegramDeepLink}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="btn-primary block text-center"
                          >
                            Open in Telegram
                          </a>
                        )}
                        <p className="text-[10px] text-jungle-dim text-center">
                          Or message @{telegramStatus?.bot_username || "the bot"} with: <code>/start {telegramCode}</code>
                        </p>
                      </div>
                    ) : (
                      <button
                        onClick={generateTelegramCode}
                        disabled={telegramLoading}
                        className="btn-primary w-full disabled:opacity-50"
                      >
                        {telegramLoading ? "Generating..." : "Generate Link Code"}
                      </button>
                    )}
                  </>
                )}
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

              {/* Dashboard Visualizations */}
              <div className="card space-y-3">
                <div className="flex items-center justify-between">
                  <SectionHeader>Dashboard Visualizations</SectionHeader>
                  {dashVizSaving && (
                    <span className="text-[10px] text-jungle-accent">Saving...</span>
                  )}
                </div>
                <p className="text-xs text-jungle-dim">
                  Toggle cards on or off. Changes save immediately. Some newer
                  visualizations require additional data (strength logs, recent check-ins).
                </p>
                <div className="space-y-2">
                  {DASH_VIZ_OPTIONS.map((opt) => (
                    <div
                      key={opt.key}
                      className="flex items-center justify-between py-1.5 border-b border-jungle-border/30 last:border-b-0"
                    >
                      <div className="min-w-0 flex-1 pr-3">
                        <p className="text-sm text-jungle-text font-medium">{opt.label}</p>
                        <p className="text-[10px] text-jungle-dim">{opt.desc}</p>
                      </div>
                      <Toggle
                        label=""
                        checked={dashViz[opt.key] !== false}
                        onChange={(v) => toggleDashViz(opt.key, v)}
                      />
                    </div>
                  ))}
                </div>
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

        </div>
      </main>

      {/* Sticky save bar — professional apps keep save always visible */}
      {activeSection !== "account" && (
        <div className="fixed bottom-0 left-0 right-0 z-30 bg-jungle-card/95 backdrop-blur-md border-t border-jungle-border safe-bottom">
          <div className="max-w-2xl mx-auto px-4 py-3 flex items-center gap-3">
            <div className="flex-1 text-xs text-jungle-dim">
              {saved ? (
                <span className="text-green-400 font-medium">All changes saved and engines updated</span>
              ) : syncing ? (
                <span className="text-jungle-accent">Syncing with training and nutrition engines...</span>
              ) : (
                <span>Changes will sync training program and meal plan</span>
              )}
            </div>
            <button
              onClick={saveProfile}
              disabled={saving || syncing}
              className={`px-6 py-2.5 rounded-xl text-sm font-bold transition-all active:scale-95 disabled:opacity-50 ${
                saved
                  ? "bg-green-500/20 text-green-400 border border-green-500/30"
                  : "bg-jungle-accent text-jungle-dark hover:bg-jungle-accent-hover shadow-lg shadow-jungle-accent/20"
              }`}
            >
              {saved ? "Saved" : syncing ? "Syncing..." : saving ? "Saving..." : "Save Changes"}
            </button>
          </div>
        </div>
      )}

      <div className="h-20" />
    </div>
  );
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function SectionHeader({ children, description }: { children: React.ReactNode; description?: string }) {
  return (
    <div className="mb-1">
      <h2 className="text-xs font-semibold text-jungle-muted uppercase tracking-wider">{children}</h2>
      {description && <p className="text-[10px] text-jungle-dim mt-0.5">{description}</p>}
    </div>
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
