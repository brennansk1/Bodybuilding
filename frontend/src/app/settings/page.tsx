"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import NavBar from "@/components/NavBar";
import PageTitle from "@/components/PageTitle";
import { showError, showSuccess } from "@/components/Toast";
import CompetitionModeToggle from "@/components/CompetitionModeToggle";
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
    fasted_training?: boolean;
    rep_range_style?: "auto" | "heavy" | "moderate" | "high_rep";
    initial_phase?: string;
    preferred_proteins?: string[];
    preferred_carbs?: string[];
    preferred_fats?: string[];
    preferred_vegetables?: string[];
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

const VEGETABLE_SOURCES = [
  "Broccoli", "Asparagus", "Spinach", "Green Beans", "Bell Peppers",
  "Zucchini", "Cucumber", "Kale", "Cauliflower",
];

// Foods typically eaten at breakfast. Used by the Settings UI to warn
// the user when they haven't picked at least one breakfast-friendly
// option — a meal plan with zero breakfast staples will fall back to
// plating chicken + rice at 7 AM, which is unpleasant.
const BREAKFAST_PROTEINS = new Set([
  "Egg Whites", "Whole Eggs", "Greek Yogurt (nonfat)", "Cottage Cheese (low-fat)",
]);
const BREAKFAST_CARBS = new Set([
  "Oats (rolled)", "Cream of Rice", "Ezekiel Bread", "Banana",
]);

// Foods greyed out during strict phases (prep, cut, peak week).
// Coaches avoid high-fat proteins, fibrous slow-GI carbs, and
// calorie-dense cooking fats once calories are tight. The buttons
// stay clickable (the user can override) but render in a muted
// "not recommended" state so the phase signal is visible.
const STRICT_PHASE_NOT_RECOMMENDED: Record<"protein" | "carb" | "fat", Set<string>> = {
  protein: new Set(["Whole Eggs", "Salmon", "Lean Ground Beef", "Flank Steak", "Sirloin Steak"]),
  carb: new Set(["Ezekiel Bread", "Brown Rice", "Quinoa", "Banana"]),
  fat: new Set(["Peanut Butter", "Coconut Oil", "Almond Butter"]),
};
const STRICT_PHASES = new Set(["cut", "peak_week", "contest"]);

// Coach-recommended staple limits — elite prep rotates 2-3 proteins,
// 2-3 carbs, 1-2 fats, 2 vegetables. Picking more does not add variety;
// it just destabilizes the meal planner's repetition.
const MAX_PREFERRED_PROTEINS = 3;
const MAX_PREFERRED_CARBS = 3;
const MAX_PREFERRED_FATS = 2;
const MAX_PREFERRED_VEGETABLES = 3;

// Phase-optimized default combos a coach would prescribe per division.
// Pressing "Use recommended" on each staple list populates these.
const RECOMMENDED_STAPLES: Record<string, { proteins: string[]; carbs: string[]; fats: string[]; vegetables: string[] }> = {
  mens_open: {
    proteins: ["Chicken Breast", "Lean Ground Beef", "Egg Whites"],
    carbs: ["White Rice", "Sweet Potato", "Oats (rolled)"],
    fats: ["Almonds", "Extra Virgin Olive Oil"],
    vegetables: ["Broccoli", "Asparagus"],
  },
  classic_physique: {
    proteins: ["Chicken Breast", "Tilapia", "Egg Whites"],
    carbs: ["Jasmine Rice", "Sweet Potato", "Oats (rolled)"],
    fats: ["Almonds", "Extra Virgin Olive Oil"],
    vegetables: ["Broccoli", "Asparagus"],
  },
  mens_physique: {
    proteins: ["Chicken Breast", "Cod", "Egg Whites"],
    carbs: ["Jasmine Rice", "Sweet Potato", "Oats (rolled)"],
    fats: ["Almonds", "Extra Virgin Olive Oil"],
    vegetables: ["Broccoli", "Green Beans"],
  },
  womens_bikini: {
    proteins: ["Chicken Breast", "Tilapia", "Egg Whites"],
    carbs: ["Jasmine Rice", "Sweet Potato", "Oats (rolled)"],
    fats: ["Almonds", "Avocado"],
    vegetables: ["Asparagus", "Spinach"],
  },
  womens_figure: {
    proteins: ["Chicken Breast", "Cod", "Egg Whites"],
    carbs: ["Jasmine Rice", "Sweet Potato", "Oats (rolled)"],
    fats: ["Almonds", "Extra Virgin Olive Oil"],
    vegetables: ["Broccoli", "Asparagus"],
  },
  womens_wellness: {
    proteins: ["Chicken Breast", "Lean Ground Turkey", "Egg Whites"],
    carbs: ["White Rice", "Sweet Potato", "Oats (rolled)"],
    fats: ["Almonds", "Avocado"],
    vegetables: ["Broccoli", "Spinach"],
  },
};

function getRecommendedStaples(division: string) {
  return RECOMMENDED_STAPLES[division] || RECOMMENDED_STAPLES.mens_open;
}

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
  // PPM (Perpetual Progression Mode) state
  const [ppmEnabled, setPpmEnabled] = useState<boolean>(false);
  const [targetTier, setTargetTier] = useState<number | null>(null);
  const [trainingStatus, setTrainingStatus] = useState<"natural" | "enhanced">("natural");
  const [acknowledgeGap, setAcknowledgeGap] = useState<boolean>(false);
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
  const [fastedTraining, setFastedTraining] = useState(false);
  // B4.1: user-selectable training style rep-range override
  const [repRangeStyle, setRepRangeStyle] = useState<"auto" | "heavy" | "moderate" | "high_rep">("auto");
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
  const [preferredVegetables, setPreferredVegetables] = useState<string[]>([]);

  // ── Dashboard visualizations ────────────────────────────────────────────────

  // ── HealthKit API keys ───────────────────────────────────────────────────────
  interface HealthKitKey {
    id: string;
    key_prefix: string;
    label: string;
    last_used_at: string | null;
    created_at: string | null;
  }
  const [healthkitKeys, setHealthkitKeys] = useState<HealthKitKey[]>([]);
  const [newHealthKitKey, setNewHealthKitKey] = useState<string | null>(null);
  const [healthkitLoading, setHealthkitLoading] = useState(false);
  const [showShortcutGuide, setShowShortcutGuide] = useState(false);

  // ── Telegram bot ────────────────────────────────────────────────────────────
  interface TelegramStatus {
    enabled: boolean;
    shared_bot_available?: boolean;
    linked: boolean;
    has_own_bot?: boolean;
    bot_username: string | null;
    notify: Record<string, boolean>;
  }
  const [telegramStatus, setTelegramStatus] = useState<TelegramStatus | null>(null);
  const [telegramBotTokenInput, setTelegramBotTokenInput] = useState("");
  const [telegramLinkedUsername, setTelegramLinkedUsername] = useState<string | null>(null);
  const [telegramDeepLink, setTelegramDeepLink] = useState<string | null>(null);
  const [telegramLoading, setTelegramLoading] = useState(false);
  const [telegramLinkError, setTelegramLinkError] = useState("");
  const [showTelegramGuide, setShowTelegramGuide] = useState(false);

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
        // PPM hydration (fields added by backend in this release; fall back if absent)
        // @ts-expect-error new PPM fields on Profile
        setPpmEnabled(Boolean(p.ppm_enabled));
        // @ts-expect-error new PPM fields on Profile
        setTargetTier(p.target_tier ?? null);
        // @ts-expect-error new PPM fields on Profile
        setTrainingStatus(p.training_status ?? "natural");
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
        setFastedTraining(prefs.fasted_training ?? false);
        setRepRangeStyle((prefs.rep_range_style as typeof repRangeStyle) ?? "auto");
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
        setPreferredVegetables(prefs.preferred_vegetables ?? []);
        // Dashboard visualizations — preferences.dashboard_viz
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        // dashboard_viz is loaded implicitly — the Edit Dashboard mode on
        // the dashboard page itself reads from dashboard_settings.viz.
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
      loadHealthKitKeys();
    }
  }, [user, loading, router]);

  if (loading || !user) return null;

  // ── HealthKit helpers ───────────────────────────────────────────────────────
  const loadHealthKitKeys = async () => {
    try {
      const keys = await api.get<HealthKitKey[]>("/auth/api-keys");
      setHealthkitKeys(keys || []);
    } catch {
      // silently fail if not logged in yet
    }
  };

  const createHealthKitKey = async () => {
    setHealthkitLoading(true);
    try {
      const res = await api.post<{ api_key: string }>("/auth/api-keys", {
        label: "iPhone Shortcut",
      });
      setNewHealthKitKey(res.api_key);
      await loadHealthKitKeys();
      showSuccess("API key created — copy it now!");
    } catch (err) {
      showError(extractErrorMessage(err, "Couldn't create API key"));
    } finally {
      setHealthkitLoading(false);
    }
  };

  const revokeHealthKitKey = async (id: string) => {
    if (!window.confirm("Revoke this API key? Any iPhone Shortcut using it will stop working.")) return;
    try {
      await api.delete(`/auth/api-keys/${id}`);
      await loadHealthKitKeys();
      showSuccess("API key revoked");
    } catch (err) {
      showError(extractErrorMessage(err, "Couldn't revoke key"));
    }
  };

  // ── Telegram helpers ────────────────────────────────────────────────────────
  // Per-user bot flow: user pastes a BotFather token, we validate + register
  // the webhook server-side, and route all subsequent messages through
  // their own bot. The legacy /link/generate shared-bot flow is no longer
  // reachable from this UI (it 503'd because the shared bot isn't set).
  const linkTelegramWithToken = async () => {
    const token = telegramBotTokenInput.trim();
    if (!token || !token.includes(":")) {
      setTelegramLinkError("That doesn't look like a BotFather token (expected format: 123456:ABC…)");
      return;
    }
    setTelegramLoading(true);
    setTelegramLinkError("");
    try {
      const res = await api.post<{
        linked: boolean;
        bot_username: string;
        deep_link: string;
      }>("/telegram/link/token", { bot_token: token });
      setTelegramLinkedUsername(res.bot_username);
      setTelegramDeepLink(res.deep_link);
      setTelegramBotTokenInput("");
      const fresh = await api.get<TelegramStatus>("/telegram/status");
      setTelegramStatus(fresh);
      showSuccess(`Linked to @${res.bot_username}`);
    } catch (err) {
      const msg = extractErrorMessage(err, "Couldn't link that bot. Check the token and try again.");
      setTelegramLinkError(msg);
    } finally {
      setTelegramLoading(false);
    }
  };

  const unlinkTelegram = async () => {
    setTelegramLoading(true);
    try {
      await api.post("/telegram/unlink", {});
      setTelegramLinkedUsername(null);
      setTelegramDeepLink(null);
      setTelegramBotTokenInput("");
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

  // Dashboard viz toggles moved to the dashboard's Edit Dashboard mode.
  // The legacy `dashboard_viz` key in preferences is still loaded above for
  // back-compat with older users who haven't migrated to dashboard_settings yet.

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
        competition_date: ppmEnabled ? null : (compDate || null),
        program_start_date: programStartDate || null,
        training_experience_years: expYears ? parseInt(expYears) : 0,
        wrist_circumference_cm: wrist ? parseFloat(wrist) : null,
        ankle_circumference_cm: ankle ? parseFloat(ankle) : null,
        manual_body_fat_pct: manualBF ? parseFloat(manualBF) : null,
        // PPM (Perpetual Progression Mode)
        ppm_enabled: ppmEnabled,
        target_tier: ppmEnabled ? targetTier : null,
        training_status: trainingStatus,
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
          fasted_training: fastedTraining,
          rep_range_style: repRangeStyle,
          initial_phase: currentPhase || null,
          preferred_proteins: preferredProteins,
          preferred_carbs: preferredCarbs,
          preferred_fats: preferredFats,
          preferred_vegetables: preferredVegetables,
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
      JSON.stringify(originalPrefs.preferred_vegetables ?? []) !== JSON.stringify(preferredVegetables) ||
      (originalPrefs.cheat_meals_per_week ?? 0) !== parseInt(cheatMeals || "0") ||
      (originalPrefs.intra_workout_nutrition ?? false) !== intraWorkout ||
      (originalPrefs.fasted_training ?? false) !== fastedTraining ||
      (originalPrefs.rep_range_style ?? "auto") !== repRangeStyle ||
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
            <PageTitle text="Settings" subtitle="Manage your profile, training, and nutrition preferences" className="mb-0" />
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
                    ? "bg-jungle-accent text-white shadow-sm"
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
                            ? "bg-jungle-accent text-white border-jungle-accent"
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
                  <label className="label-field">Competition Mode</label>
                  <div className="mt-2">
                    <CompetitionModeToggle
                      initialMode={ppmEnabled ? "ppm" : "competition"}
                      initialDate={compDate}
                      initialTier={(targetTier as 1 | 2 | 3 | 4 | 5 | null) ?? undefined}
                      initialStatus={trainingStatus}
                      onChange={(next) => {
                        setPpmEnabled(next.ppm_enabled);
                        setCompDate(next.competition_date || "");
                        setTargetTier(next.target_tier);
                        setTrainingStatus(next.training_status);
                        setAcknowledgeGap(Boolean(next.acknowledge_natural_gap));
                      }}
                      runAttainabilityCheck={async (tier) => {
                        try {
                          return await api.post("/ppm/attainability", { target_tier: tier });
                        } catch {
                          return null;
                        }
                      }}
                    />
                  </div>
                  {!ppmEnabled && daysLeft !== null && (
                    <p className="text-xs mt-2">
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
                            ? "bg-jungle-accent text-white"
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
                <SectionHeader description="How you like to train — overrides the auto rep prescription">
                  Training Style
                </SectionHeader>
                <div>
                  <label className="label-field mb-2 block">Rep Range Preference</label>
                  <div className="grid grid-cols-2 gap-2">
                    {([
                      { v: "auto", label: "Auto", sub: "Engine decides" },
                      { v: "heavy", label: "Heavy", sub: "4–8 reps" },
                      { v: "moderate", label: "Moderate", sub: "8–12 reps" },
                      { v: "high_rep", label: "High Rep", sub: "12–20 reps" },
                    ] as const).map((opt) => (
                      <button
                        key={opt.v}
                        type="button"
                        onClick={() => setRepRangeStyle(opt.v)}
                        className={`py-2.5 rounded-lg text-xs font-medium border transition-colors ${
                          repRangeStyle === opt.v
                            ? "bg-jungle-accent/20 border-jungle-accent text-jungle-accent"
                            : "bg-jungle-deeper border-jungle-border text-jungle-muted hover:border-jungle-accent/50"
                        }`}
                      >
                        <div className="font-semibold">{opt.label}</div>
                        <div className="text-[10px] text-jungle-dim mt-0.5">{opt.sub}</div>
                      </button>
                    ))}
                  </div>
                  <p className="text-[10px] text-jungle-dim mt-2">
                    Auto uses Daily Undulating Periodization (rotates heavy / moderate / light across days).
                    Pick a specific range to lock it for every working set.
                  </p>
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

                <div className="flex items-start gap-2">
                  <div className="flex-1">
                    <Toggle
                      label="Fasted training (skip pre-workout meal)"
                      checked={fastedTraining}
                      onChange={setFastedTraining}
                    />
                    <p className="text-[10px] text-jungle-dim mt-1 ml-0">
                      Leave OFF to get a real pre-workout breakfast (oats + whey + banana). Turn ON only if you explicitly want to train on an empty stomach.
                    </p>
                  </div>
                </div>

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
                          ? "bg-jungle-accent text-white"
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
                            ? "bg-jungle-accent text-white"
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
                            ? "bg-jungle-accent text-white"
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

              {/* Your Coach's Staples */}
              {(() => {
                const rec = getRecommendedStaples(division);
                const proteinFull = preferredProteins.length >= MAX_PREFERRED_PROTEINS;
                const carbFull = preferredCarbs.length >= MAX_PREFERRED_CARBS;
                const fatFull = preferredFats.length >= MAX_PREFERRED_FATS;
                const vegFull = preferredVegetables.length >= MAX_PREFERRED_VEGETABLES;

                const isStrictPhase = STRICT_PHASES.has(currentPhase);
                const hasBreakfastProtein = preferredProteins.some((p) => BREAKFAST_PROTEINS.has(p));
                const hasBreakfastCarb = preferredCarbs.some((c) => BREAKFAST_CARBS.has(c));

                const Badge = ({ count, max, full }: { count: number; max: number; full: boolean }) => (
                  <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full border ${
                    full
                      ? "bg-jungle-accent/20 text-jungle-accent border-jungle-accent/60"
                      : "bg-jungle-deeper text-jungle-muted border-jungle-border"
                  }`}>
                    {count} of {max}
                  </span>
                );

                type StapleKind = "protein" | "carb" | "fat" | "vegetable";
                const COLORS: Record<StapleKind, { sel: string; hover: string; rec: string; label: string }> = {
                  protein:   { sel: "bg-blue-500/20 border-blue-500/50 text-blue-400",     hover: "hover:border-blue-500/30",   rec: "bg-blue-500/10 border-blue-500/30 text-blue-400 hover:bg-blue-500/20",     label: "🍗 Proteins" },
                  carb:      { sel: "bg-amber-500/20 border-amber-500/50 text-amber-400",  hover: "hover:border-amber-500/30",  rec: "bg-amber-500/10 border-amber-500/30 text-amber-400 hover:bg-amber-500/20",  label: "🍚 Carbs" },
                  fat:       { sel: "bg-rose-500/20 border-rose-500/50 text-rose-400",     hover: "hover:border-rose-500/30",   rec: "bg-rose-500/10 border-rose-500/30 text-rose-400 hover:bg-rose-500/20",      label: "🥑 Fats" },
                  vegetable: { sel: "bg-green-500/20 border-green-500/50 text-green-400",  hover: "hover:border-green-500/30",  rec: "bg-green-500/10 border-green-500/30 text-green-400 hover:bg-green-500/20",  label: "🥦 Vegetables" },
                };

                const StapleButton = ({
                  item,
                  kind,
                  selected,
                  listFull,
                  onToggle,
                }: {
                  item: string;
                  kind: StapleKind;
                  selected: boolean;
                  listFull: boolean;
                  onToggle: () => void;
                }) => {
                  const notRecommended =
                    isStrictPhase &&
                    kind !== "vegetable" &&
                    STRICT_PHASE_NOT_RECOMMENDED[kind].has(item);
                  const capped = listFull && !selected;
                  return (
                    <button
                      onClick={onToggle}
                      title={notRecommended ? `Not recommended during ${currentPhase.replace(/_/g, " ")}` : undefined}
                      className={`px-2.5 py-1.5 rounded-lg text-[11px] font-medium border transition-colors relative ${
                        selected
                          ? COLORS[kind].sel
                          : capped
                          ? "bg-jungle-deeper/40 border-jungle-border/40 text-jungle-dim/50 cursor-not-allowed"
                          : notRecommended
                          ? "bg-jungle-deeper/60 border-jungle-border/50 text-jungle-dim/60 italic"
                          : `bg-jungle-deeper border-jungle-border text-jungle-muted ${COLORS[kind].hover}`
                      }`}
                    >
                      {notRecommended && !selected && <span className="mr-1">⚠</span>}
                      {item}
                    </button>
                  );
                };

                return (
              <div className="card space-y-5">
                <SectionHeader description="Elite prep rotates 2-3 proteins, 2-3 carbs, 1-2 fats, and 2 vegetables across every meal — not 10. Pick your top staples. The meal planner will only pull from these choices.">
                  Your Coach&apos;s Staples
                </SectionHeader>

                {isStrictPhase && (
                  <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg px-3 py-2 text-[11px] text-amber-400">
                    You&apos;re in <span className="font-bold capitalize">{currentPhase.replace(/_/g, " ")}</span>. Italicized items with ⚠ are not typically recommended during strict phases — you can still pick them, but the coach-preferred staples are highlighted.
                  </div>
                )}

                {/* Protein Sources */}
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="label-field mb-0">{COLORS.protein.label} (max {MAX_PREFERRED_PROTEINS})</label>
                    <Badge count={preferredProteins.length} max={MAX_PREFERRED_PROTEINS} full={proteinFull} />
                  </div>
                  <p className="text-[10px] text-jungle-dim mb-2">
                    💡 Include at least one breakfast-friendly protein — Egg Whites, Greek Yogurt, or Cottage Cheese — so the planner has something light to plate at 7 AM.
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {PROTEIN_SOURCES.map((item) => (
                      <StapleButton
                        key={item}
                        item={item}
                        kind="protein"
                        selected={preferredProteins.includes(item)}
                        listFull={proteinFull}
                        onToggle={() =>
                          setPreferredProteins((prev) => {
                            if (prev.includes(item)) return prev.filter((x) => x !== item);
                            if (prev.length >= MAX_PREFERRED_PROTEINS) return prev;
                            return [...prev, item];
                          })
                        }
                      />
                    ))}
                  </div>
                  {!hasBreakfastProtein && preferredProteins.length > 0 && (
                    <p className="text-[10px] text-amber-400 mt-1.5">
                      ⚠ No breakfast-friendly protein picked. Consider adding Egg Whites or Greek Yogurt.
                    </p>
                  )}
                  <button
                    onClick={() => setPreferredProteins(rec.proteins.slice(0, MAX_PREFERRED_PROTEINS))}
                    className={`mt-2 text-[10px] px-2 py-1 rounded-md border ${COLORS.protein.rec}`}
                  >
                    ✨ Use recommended: {rec.proteins.join(" + ")}
                  </button>
                </div>

                {/* Carb Sources */}
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="label-field mb-0">{COLORS.carb.label} (max {MAX_PREFERRED_CARBS})</label>
                    <Badge count={preferredCarbs.length} max={MAX_PREFERRED_CARBS} full={carbFull} />
                  </div>
                  <p className="text-[10px] text-jungle-dim mb-2">
                    💡 Include at least one breakfast-friendly carb — Oats, Cream of Rice, or Ezekiel Bread — so early meals don&apos;t default to plain white rice.
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {CARB_SOURCES.map((item) => (
                      <StapleButton
                        key={item}
                        item={item}
                        kind="carb"
                        selected={preferredCarbs.includes(item)}
                        listFull={carbFull}
                        onToggle={() =>
                          setPreferredCarbs((prev) => {
                            if (prev.includes(item)) return prev.filter((x) => x !== item);
                            if (prev.length >= MAX_PREFERRED_CARBS) return prev;
                            return [...prev, item];
                          })
                        }
                      />
                    ))}
                  </div>
                  {!hasBreakfastCarb && preferredCarbs.length > 0 && (
                    <p className="text-[10px] text-amber-400 mt-1.5">
                      ⚠ No breakfast-friendly carb picked. Consider adding Oats (rolled) or Cream of Rice.
                    </p>
                  )}
                  <button
                    onClick={() => setPreferredCarbs(rec.carbs.slice(0, MAX_PREFERRED_CARBS))}
                    className={`mt-2 text-[10px] px-2 py-1 rounded-md border ${COLORS.carb.rec}`}
                  >
                    ✨ Use recommended: {rec.carbs.join(" + ")}
                  </button>
                </div>

                {/* Fat Sources */}
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="label-field mb-0">{COLORS.fat.label} (max {MAX_PREFERRED_FATS})</label>
                    <Badge count={preferredFats.length} max={MAX_PREFERRED_FATS} full={fatFull} />
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {FAT_SOURCES.map((item) => (
                      <StapleButton
                        key={item}
                        item={item}
                        kind="fat"
                        selected={preferredFats.includes(item)}
                        listFull={fatFull}
                        onToggle={() =>
                          setPreferredFats((prev) => {
                            if (prev.includes(item)) return prev.filter((x) => x !== item);
                            if (prev.length >= MAX_PREFERRED_FATS) return prev;
                            return [...prev, item];
                          })
                        }
                      />
                    ))}
                  </div>
                  <button
                    onClick={() => setPreferredFats(rec.fats.slice(0, MAX_PREFERRED_FATS))}
                    className={`mt-2 text-[10px] px-2 py-1 rounded-md border ${COLORS.fat.rec}`}
                  >
                    ✨ Use recommended: {rec.fats.join(" + ")}
                  </button>
                </div>

                {/* Vegetable Sources */}
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="label-field mb-0">{COLORS.vegetable.label} (max {MAX_PREFERRED_VEGETABLES})</label>
                    <Badge count={preferredVegetables.length} max={MAX_PREFERRED_VEGETABLES} full={vegFull} />
                  </div>
                  <p className="text-[10px] text-jungle-dim mb-2">
                    Every lunch, dinner, and snack gets a vegetable plated with it. Veg carbs are subtracted from that meal&apos;s carb budget so your macros stay on target. Breakfast stays clean.
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {VEGETABLE_SOURCES.map((item) => (
                      <StapleButton
                        key={item}
                        item={item}
                        kind="vegetable"
                        selected={preferredVegetables.includes(item)}
                        listFull={vegFull}
                        onToggle={() =>
                          setPreferredVegetables((prev) => {
                            if (prev.includes(item)) return prev.filter((x) => x !== item);
                            if (prev.length >= MAX_PREFERRED_VEGETABLES) return prev;
                            return [...prev, item];
                          })
                        }
                      />
                    ))}
                  </div>
                  <button
                    onClick={() => setPreferredVegetables(rec.vegetables.slice(0, MAX_PREFERRED_VEGETABLES))}
                    className={`mt-2 text-[10px] px-2 py-1 rounded-md border ${COLORS.vegetable.rec}`}
                  >
                    ✨ Use recommended: {rec.vegetables.join(" + ")}
                  </button>
                </div>
              </div>
                );
              })()}

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
                {telegramStatus?.linked ? (
                  <>
                    <p className="text-xs text-jungle-dim">
                      Your Viltrum account is linked to <strong>@{telegramStatus.bot_username}</strong>.
                      Adjust which reminders you receive below, or disconnect.
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
                      Get workout previews, meal reminders, and readiness alerts in Telegram.
                      You bring your own bot from BotFather (free, takes 30 seconds) — the chat
                      is 100% yours.
                    </p>
                    <button
                      type="button"
                      onClick={() => setShowTelegramGuide(true)}
                      className="w-full py-2 text-xs text-jungle-accent border border-jungle-accent/40 rounded-lg hover:bg-jungle-accent/10 transition-colors"
                    >
                      📖 How to create a Telegram bot (BotFather guide)
                    </button>
                    <div className="space-y-1.5">
                      <label className="text-[10px] text-jungle-dim uppercase tracking-wider">
                        Paste your BotFather token
                      </label>
                      <input
                        type="text"
                        value={telegramBotTokenInput}
                        onChange={(e) => {
                          setTelegramBotTokenInput(e.target.value);
                          setTelegramLinkError("");
                        }}
                        placeholder="123456:ABC-..."
                        className="input-field text-xs font-mono"
                        autoComplete="off"
                        spellCheck={false}
                      />
                      {telegramLinkError && (
                        <p className="text-[10px] text-red-400">{telegramLinkError}</p>
                      )}
                    </div>
                    <button
                      onClick={linkTelegramWithToken}
                      disabled={telegramLoading || !telegramBotTokenInput.trim()}
                      className="btn-primary w-full disabled:opacity-50"
                    >
                      {telegramLoading ? "Linking..." : "Link Bot"}
                    </button>
                    {telegramLinkedUsername && telegramDeepLink && (
                      <a
                        href={telegramDeepLink}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="block text-center text-xs text-jungle-accent hover:underline"
                      >
                        Open @{telegramLinkedUsername} in Telegram → send /start
                      </a>
                    )}
                  </>
                )}
              </div>

              {/* HealthKit / iPhone Shortcut */}
              <div className="card space-y-3">
                <div className="flex items-center justify-between">
                  <SectionHeader>HealthKit — iPhone Shortcut</SectionHeader>
                  {healthkitKeys.length > 0 && (
                    <span className="text-[10px] px-2 py-0.5 rounded font-semibold bg-green-500/20 text-green-400">
                      {healthkitKeys.length} key{healthkitKeys.length === 1 ? "" : "s"}
                    </span>
                  )}
                </div>
                <p className="text-xs text-jungle-dim">
                  Automate your morning check-in: an iPhone Shortcut reads body weight, HRV,
                  resting heart rate and sleep duration from Apple HealthKit and posts them
                  to Viltrum. Create an API key below and follow the setup guide.
                </p>

                {/* Existing keys */}
                {healthkitKeys.length > 0 && (
                  <div className="space-y-1.5">
                    {healthkitKeys.map((k) => (
                      <div
                        key={k.id}
                        className="flex items-center justify-between py-2 px-3 bg-jungle-deeper rounded-lg"
                      >
                        <div className="min-w-0 flex-1">
                          <p className="text-sm text-jungle-text font-medium truncate">{k.label}</p>
                          <p className="text-[10px] text-jungle-dim font-mono">
                            {k.key_prefix}… · {k.last_used_at ? `last used ${new Date(k.last_used_at).toLocaleDateString()}` : "never used"}
                          </p>
                        </div>
                        <button
                          type="button"
                          onClick={() => revokeHealthKitKey(k.id)}
                          className="text-[10px] px-2 py-1 rounded text-red-400 border border-red-500/30 hover:bg-red-500/10 transition-colors"
                        >
                          Revoke
                        </button>
                      </div>
                    ))}
                  </div>
                )}

                {/* Newly-created plaintext key (shown once) */}
                {newHealthKitKey && (
                  <div className="rounded-lg bg-jungle-accent/10 border border-jungle-accent/40 p-3 space-y-2">
                    <div className="flex items-center justify-between">
                      <p className="text-[10px] text-jungle-accent font-bold uppercase tracking-wider">Your new API key</p>
                      <button
                        type="button"
                        onClick={() => setNewHealthKitKey(null)}
                        className="text-[10px] text-jungle-dim hover:text-jungle-accent"
                      >
                        Dismiss
                      </button>
                    </div>
                    <code className="block text-[11px] font-mono text-jungle-text bg-jungle-deeper/80 px-2 py-2 rounded break-all">
                      {newHealthKitKey}
                    </code>
                    <button
                      type="button"
                      onClick={() => {
                        navigator.clipboard?.writeText(newHealthKitKey).catch(() => {});
                        showSuccess("Copied to clipboard");
                      }}
                      className="btn-secondary w-full text-xs py-2"
                    >
                      Copy to clipboard
                    </button>
                    <p className="text-[10px] text-jungle-dim">
                      ⚠️ This key is shown <strong>once</strong>. Paste it into your iPhone
                      Shortcut now. If you lose it, generate a new one and revoke the old.
                    </p>
                  </div>
                )}

                {/* Actions */}
                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={createHealthKitKey}
                    disabled={healthkitLoading}
                    className="btn-primary text-xs py-2 disabled:opacity-50"
                  >
                    {healthkitLoading ? "Creating..." : "+ New API Key"}
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowShortcutGuide(true)}
                    className="btn-secondary text-xs py-2"
                  >
                    📱 Setup Guide
                  </button>
                </div>
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
                  : "bg-jungle-accent text-white hover:bg-jungle-accent-hover shadow-lg shadow-jungle-accent/20"
              }`}
            >
              {saved ? "Saved" : syncing ? "Syncing..." : saving ? "Saving..." : "Save Changes"}
            </button>
          </div>
        </div>
      )}

      <div className="h-20" />

      {/* iPhone Shortcut setup guide modal */}
      {showTelegramGuide && (
        <div
          className="fixed inset-0 z-50 bg-viltrum-obsidian/50 backdrop-blur-sm flex items-end sm:items-center justify-center p-3"
          onClick={() => setShowTelegramGuide(false)}
        >
          <div
            className="bg-jungle-card border border-jungle-border rounded-2xl w-full max-w-xl max-h-[90vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="sticky top-0 bg-jungle-card/95 backdrop-blur-md border-b border-jungle-border px-4 py-3 flex items-center justify-between z-10">
              <h3 className="text-sm font-bold text-jungle-text">🤖 BotFather — Create a Telegram Bot</h3>
              <button
                type="button"
                onClick={() => setShowTelegramGuide(false)}
                className="text-jungle-dim hover:text-jungle-accent text-2xl leading-none px-2"
                aria-label="Close guide"
              >
                ×
              </button>
            </div>
            <div className="p-4 space-y-5 text-[12px] text-jungle-text leading-relaxed">
              <section className="space-y-2">
                <h4 className="text-jungle-accent text-xs font-bold uppercase tracking-wider">What is this?</h4>
                <p className="text-jungle-muted">
                  BotFather is Telegram&apos;s official bot for creating bots. You&apos;ll chat
                  with it to create a brand-new private bot that belongs to you. Viltrum
                  then uses that bot to send you coaching messages (workout previews,
                  readiness alerts, meal reminders). The bot is 100% yours — no one else
                  can see your chats or data.
                </p>
              </section>

              <section className="space-y-2">
                <h4 className="text-jungle-accent text-xs font-bold uppercase tracking-wider">Step 1 — Open BotFather</h4>
                <ol className="list-decimal ml-5 space-y-1.5 text-jungle-muted">
                  <li>Open Telegram on your phone or desktop.</li>
                  <li>
                    Search for <strong>@BotFather</strong> (the real one has a blue
                    checkmark).
                  </li>
                  <li>Tap <strong>Start</strong> or send <code className="bg-jungle-deeper px-1.5 py-0.5 rounded text-jungle-accent">/start</code>.</li>
                </ol>
              </section>

              <section className="space-y-2">
                <h4 className="text-jungle-accent text-xs font-bold uppercase tracking-wider">Step 2 — Create the bot</h4>
                <ol className="list-decimal ml-5 space-y-1.5 text-jungle-muted">
                  <li>
                    Send <code className="bg-jungle-deeper px-1.5 py-0.5 rounded text-jungle-accent">/newbot</code> to BotFather.
                  </li>
                  <li>
                    BotFather asks for a <strong>name</strong> (displayed in chat).
                    Pick whatever you like — e.g. <em>Viltrum Coach</em>.
                  </li>
                  <li>
                    Next, BotFather asks for a <strong>username</strong>. It must end in
                    <code className="mx-1 bg-jungle-deeper px-1 rounded">bot</code> and be globally unique.
                    Try something like <code className="bg-jungle-deeper px-1 rounded">yourname_coronado_bot</code>.
                  </li>
                </ol>
              </section>

              <section className="space-y-2">
                <h4 className="text-jungle-accent text-xs font-bold uppercase tracking-wider">Step 3 — Copy the token</h4>
                <p className="text-jungle-muted">
                  BotFather replies with a congratulations message that includes a line like:
                </p>
                <pre className="text-[10px] bg-jungle-deeper px-3 py-2.5 rounded overflow-x-auto text-jungle-accent leading-snug">{`Use this token to access the HTTP API:
1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ1234567890

Keep your token secure and store it safely...`}</pre>
                <p className="text-jungle-muted">
                  The long string (<code className="bg-jungle-deeper px-1 rounded">1234567890:ABC…</code>)
                  is your <strong>bot token</strong>. Tap and hold it in Telegram to copy.
                </p>
                <p className="text-[10px] text-jungle-dim">
                  ⚠️ Treat this token like a password. Anyone with it can control your bot.
                </p>
              </section>

              <section className="space-y-2">
                <h4 className="text-jungle-accent text-xs font-bold uppercase tracking-wider">Step 4 — Paste it into Viltrum</h4>
                <ol className="list-decimal ml-5 space-y-1.5 text-jungle-muted">
                  <li>Close this guide.</li>
                  <li>
                    Paste the token into the <strong>BotFather token</strong> input below
                    and tap <strong>Link Bot</strong>.
                  </li>
                  <li>
                    If the token is valid, Viltrum registers a webhook on your bot and
                    the link is live immediately.
                  </li>
                  <li>
                    <strong>One more step:</strong> open your bot chat in Telegram and send
                    <code className="mx-1 bg-jungle-deeper px-1 rounded">/start</code>.
                    This tells Viltrum which chat ID to send messages to.
                  </li>
                </ol>
              </section>

              <section className="space-y-2">
                <h4 className="text-jungle-accent text-xs font-bold uppercase tracking-wider">Troubleshooting</h4>
                <ul className="list-disc ml-5 space-y-1 text-jungle-muted">
                  <li>
                    <strong>&quot;Telegram rejected that bot token&quot;</strong> — check for
                    typos or extra whitespace. The token should start with digits, have
                    a <code className="bg-jungle-deeper px-1 rounded">:</code>, and contain
                    only letters/digits/underscores/hyphens.
                  </li>
                  <li>
                    <strong>&quot;failed to register a webhook&quot;</strong> — the backend&apos;s
                    public URL isn&apos;t reachable from Telegram&apos;s servers. Admin needs to
                    set <code className="bg-jungle-deeper px-1 rounded">PUBLIC_BASE_URL</code>
                    to a publicly-routable HTTPS address.
                  </li>
                  <li>
                    <strong>Bot doesn&apos;t respond to /start</strong> — double-check you&apos;re
                    messaging the right bot (the username you just created, not @BotFather).
                  </li>
                </ul>
              </section>

              <div className="pt-2 border-t border-jungle-border">
                <button
                  type="button"
                  onClick={() => setShowTelegramGuide(false)}
                  className="btn-primary w-full"
                >
                  Got it — back to settings
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {showShortcutGuide && (
        <div
          className="fixed inset-0 z-50 bg-viltrum-obsidian/50 backdrop-blur-sm flex items-end sm:items-center justify-center p-3"
          onClick={() => setShowShortcutGuide(false)}
        >
          <div
            className="bg-jungle-card border border-jungle-border rounded-2xl w-full max-w-xl max-h-[90vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="sticky top-0 bg-jungle-card/95 backdrop-blur-md border-b border-jungle-border px-4 py-3 flex items-center justify-between z-10">
              <h3 className="text-sm font-bold text-jungle-text">📱 iPhone Shortcut Setup Guide</h3>
              <button
                type="button"
                onClick={() => setShowShortcutGuide(false)}
                className="text-jungle-dim hover:text-jungle-accent text-2xl leading-none px-2"
                aria-label="Close guide"
              >
                ×
              </button>
            </div>
            <div className="p-4 space-y-5 text-[12px] text-jungle-text leading-relaxed">
              <section className="space-y-2">
                <h4 className="text-jungle-accent text-xs font-bold uppercase tracking-wider">What this does</h4>
                <p className="text-jungle-muted">
                  Runs every morning at 7 AM. Pulls last night&apos;s body weight, HRV, resting heart rate and sleep duration
                  from Apple HealthKit and posts them to Viltrum — your daily check-in is filled in automatically.
                </p>
              </section>

              <section className="space-y-2">
                <h4 className="text-jungle-accent text-xs font-bold uppercase tracking-wider">Before you start</h4>
                <ol className="list-decimal ml-5 space-y-1 text-jungle-muted">
                  <li>Create an API key above (tap <strong>+ New API Key</strong>) and copy it — it&apos;s only shown once.</li>
                  <li>Make sure Apple Health has recent body weight + HRV data (a watch helps).</li>
                </ol>
              </section>

              <section className="space-y-2">
                <h4 className="text-jungle-accent text-xs font-bold uppercase tracking-wider">Step 1 — Create the Shortcut</h4>
                <ol className="list-decimal ml-5 space-y-1.5 text-jungle-muted">
                  <li>Open the <strong>Shortcuts</strong> app on your iPhone.</li>
                  <li>Tap <strong>+</strong> (top right) to create a new shortcut.</li>
                  <li>Name it <code className="bg-jungle-deeper px-1.5 py-0.5 rounded text-jungle-accent">Viltrum Morning Sync</code>.</li>
                </ol>
              </section>

              <section className="space-y-2">
                <h4 className="text-jungle-accent text-xs font-bold uppercase tracking-wider">Step 2 — Pull HealthKit data</h4>
                <p className="text-jungle-muted">
                  Add these actions in order. Search each action name in the <em>Add Action</em> panel.
                </p>
                <ol className="list-decimal ml-5 space-y-1.5 text-jungle-muted">
                  <li>
                    <strong>Find Health Samples</strong> — set category <code className="bg-jungle-deeper px-1 rounded">Body Mass</code>,
                    sort by <em>End Date (Latest First)</em>, limit <em>1</em>.
                  </li>
                  <li>Tap <em>Get details of Health Sample</em> — select <em>Value</em>. Rename the magic variable to <code className="bg-jungle-deeper px-1 rounded">Weight</code>.</li>
                  <li>
                    <strong>Find Health Samples</strong> — category <code className="bg-jungle-deeper px-1 rounded">Heart Rate Variability</code>,
                    latest 1, get <em>Value</em> → rename <code className="bg-jungle-deeper px-1 rounded">HRV</code>.
                  </li>
                  <li>
                    <strong>Find Health Samples</strong> — category <code className="bg-jungle-deeper px-1 rounded">Resting Heart Rate</code>,
                    latest 1, get <em>Value</em> → rename <code className="bg-jungle-deeper px-1 rounded">RestingHR</code>.
                  </li>
                  <li>
                    <strong>Find Health Samples</strong> — category <code className="bg-jungle-deeper px-1 rounded">Sleep Analysis</code>,
                    last 24 hours, all samples. Then <strong>Calculate</strong> the total <em>Duration</em> in hours →
                    rename <code className="bg-jungle-deeper px-1 rounded">SleepHours</code>.
                  </li>
                </ol>
              </section>

              <section className="space-y-2">
                <h4 className="text-jungle-accent text-xs font-bold uppercase tracking-wider">Step 3 — POST to Viltrum</h4>
                <ol className="list-decimal ml-5 space-y-1.5 text-jungle-muted">
                  <li>Add a <strong>Text</strong> action and paste this JSON body (keep the magic variables):</li>
                </ol>
                <pre className="text-[10px] bg-jungle-deeper px-3 py-2.5 rounded overflow-x-auto text-jungle-text leading-snug">{`{
  "body_weight_kg": [Weight],
  "hrv_sdnn_ms":    [HRV],
  "resting_hr":     [RestingHR],
  "sleep_hours":    [SleepHours]
}`}</pre>
                <ol start={2} className="list-decimal ml-5 space-y-1.5 text-jungle-muted">
                  <li>Add <strong>Get Contents of URL</strong>. Configure:</li>
                </ol>
                <div className="bg-jungle-deeper/60 border border-jungle-border rounded-lg p-3 space-y-1 text-[11px] font-mono text-jungle-muted">
                  <div>URL: <span className="text-jungle-accent">https://your-coronado-host/api/v1/checkin/daily/healthkit</span></div>
                  <div>Method: <span className="text-jungle-accent">POST</span></div>
                  <div>Headers:</div>
                  <div className="pl-3"><span className="text-jungle-accent">X-API-Key</span> : <em>(paste the API key from above)</em></div>
                  <div className="pl-3"><span className="text-jungle-accent">Content-Type</span> : application/json</div>
                  <div>Request Body: <span className="text-jungle-accent">JSON</span> → attach the Text action from step 1</div>
                </div>
                <p className="text-[10px] text-jungle-dim">
                  💡 Replace <code>your-coronado-host</code> with your actual backend URL
                  (for local access that&apos;s <code className="text-jungle-accent">http://<server-ip>:8000</code>).
                  Shortcuts needs an <strong>https://</strong> URL if you&apos;re outside your home network.
                </p>
              </section>

              <section className="space-y-2">
                <h4 className="text-jungle-accent text-xs font-bold uppercase tracking-wider">Step 4 — Automate it</h4>
                <ol className="list-decimal ml-5 space-y-1.5 text-jungle-muted">
                  <li>In the Shortcuts app, tap the <strong>Automation</strong> tab.</li>
                  <li>Tap <strong>+</strong> → <em>Create Personal Automation</em>.</li>
                  <li>Pick <strong>Time of Day</strong> → set to <strong>7:00 AM</strong>, repeat <strong>Daily</strong>.</li>
                  <li>Next → add action <strong>Run Shortcut</strong> → pick <em>Viltrum Morning Sync</em>.</li>
                  <li>Toggle <strong>Run Immediately</strong> ON (so it fires without a notification prompt).</li>
                  <li>Done. It&apos;ll fire every morning silently.</li>
                </ol>
              </section>

              <section className="space-y-2">
                <h4 className="text-jungle-accent text-xs font-bold uppercase tracking-wider">Test it</h4>
                <p className="text-jungle-muted">
                  Run the shortcut manually from the Shortcuts app. If it succeeds, your Viltrum daily check-in will show today&apos;s weight + HRV right away.
                  If it fails, open <strong>Show Result</strong> on the Get Contents of URL action to see the error message.
                </p>
              </section>

              <section className="space-y-2">
                <h4 className="text-jungle-accent text-xs font-bold uppercase tracking-wider">Troubleshooting</h4>
                <ul className="list-disc ml-5 space-y-1 text-jungle-muted">
                  <li><strong>401 Unauthorized</strong> — API key typo or revoked. Create a new one.</li>
                  <li><strong>422 Unprocessable Entity</strong> — one of the HealthKit values is missing. Make sure Apple Health has weight/HRV data for the last 24 hours.</li>
                  <li><strong>SDNN vs rMSSD</strong> — Apple reports SDNN. Viltrum auto-converts (SDNN × 0.8 ≈ rMSSD) and notes this on your check-in. No action needed.</li>
                  <li><strong>No sleep data</strong> — the field is optional. The check-in still works without it.</li>
                </ul>
              </section>

              <div className="pt-2 border-t border-jungle-border">
                <button
                  type="button"
                  onClick={() => setShowShortcutGuide(false)}
                  className="btn-primary w-full"
                >
                  Got it
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
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
