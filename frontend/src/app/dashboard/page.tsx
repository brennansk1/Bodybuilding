"use client";

import { memo, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import { showToast } from "@/components/Toast";
import NavBar from "@/components/NavBar";
import { api } from "@/lib/api";
import SpiderChart from "@/components/SpiderChart";
import MiniLineChart from "@/components/MiniLineChart";
import MuscleHeatmap from "@/components/MuscleHeatmap";
import AdherenceHeatmap from "@/components/AdherenceHeatmap";
import StrengthProgressionChart from "@/components/StrengthProgressionChart";
import BodyWeightTrendChart from "@/components/BodyWeightTrendChart";
import MacroAdherenceChart from "@/components/MacroAdherenceChart";
import WeeklyVolumeChart from "@/components/WeeklyVolumeChart";
import RecoveryTrendChart from "@/components/RecoveryTrendChart";
import SortableCard from "@/components/SortableCard";
import {
  DndContext,
  PointerSensor,
  KeyboardSensor,
  useSensor,
  useSensors,
  closestCenter,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  rectSortingStrategy,
  sortableKeyboardCoordinates,
  arrayMove,
} from "@dnd-kit/sortable";
import OnboardingWizard, { shouldShowWizard } from "@/components/OnboardingWizard";
import CoachingFeedbackCard, { type CoachingMessage } from "@/components/CoachingFeedbackCard";
import TierReadinessCard from "@/components/TierReadinessCard";
import PageTitle from "@/components/PageTitle";
import {
  CycleProgressCard,
  ParityCheckCard,
  ChestWaistCard,
  CarbCycleCard,
  ConditioningStyleCard,
  NaturalCeilingCard,
} from "@/components/PPMCards";
import type { TierReadiness, TierProjection, NaturalAttainability } from "@/lib/types";
import { getQuoteForToday } from "@/lib/quotes";

interface PDSEntry {
  date: string;
  pds_score: number;
  tier: string;
}
interface PDSData {
  current: { pds_score: number; tier: string; components: Record<string, number> };
  history: PDSEntry[];
}
interface MuscleGapSiteData {
  ideal_lean_cm: number;
  current_lean_cm: number;
  gap_cm: number;
  pct_of_ideal: number;
  gap_type: "add_muscle" | "at_ideal" | "above_ideal" | "reduce_girth";
}
interface MuscleGapsData {
  sites: Record<string, MuscleGapSiteData>;
  total_gap_cm: number;
  avg_pct_of_ideal: number;
  ranked_gaps: { site: string; ideal_lean_cm: number; current_lean_cm: number; gap_cm: number; pct_of_ideal: number; gap_type: string }[];
}
interface SymmetryDetail {
  site: string;
  left_cm: number;
  right_cm: number;
  diff_cm: number;
  deviation_pct: number;
  dominant_side: "left" | "right" | "even";
}
interface SymmetryData {
  symmetry_score: number;
  details: SymmetryDetail[];
  lagging_sides: SymmetryDetail[];
}
interface PhaseRecommendation {
  recommended_phase: string;
  reason: string;
  urgency: string;
}
interface ARIData {
  ari_score: number;
  zone: string;
  components?: { hrv: number; sleep: number; soreness: number };
}
interface AdherenceEntry {
  date: string;
  nutrition: number;
  training: number;
  overall: number;
}
interface WeightEntry {
  date: string;
  weight_kg: number;
}
interface ClassEstimate {
  class: string;
  label: string;
  max_weight_kg: number | null;
  max_height_cm: number | null;
  division: string;
}
interface GhostModelData {
  ghost_mass_kg: number;
  allometric_multiplier: number;
  hanavan_volumes: {
    upper_arms: number;
    forearms: number;
    thighs: number;
    calves: number;
    torso: number;
    total: number;
    total_after_lung: number;
  };
  scaled_ghost: Record<string, number>;
}
interface DiagnosticData {
  body_fat?: {
    body_fat_pct: number;
    category: string;
    lean_mass_kg: number | null;
    source: string;
    confidence?: string;
    methods?: string[];
    confidence_interval?: [number, number];
  };
  weight_cap?: {
    weight_cap_kg: number;
    target_lbm_kg: number;
    stage_weight_kg: number;
    ghost_mass_kg?: number;
    allometric_multiplier?: number;
  };
  class_estimate?: ClassEstimate;
  ghost_model?: GhostModelData;
  advanced_measurements?: {
    lat_spread_delta_cm?: number;
    lat_activation_pct?: number;
    lat_activation_score?: number;
    chest_relaxed_cm?: number;
    chest_lat_spread_cm?: number;
    lean_chest_used_cm?: number;
    back_width_cm?: number;
    lean_back_width_cm?: number;
    proximal_thigh_cm?: number;
    distal_thigh_cm?: number;
    quad_vmo_ratio?: number;
    quad_regionality_score?: number;
  };
  prep_timeline?: {
    weeks_out?: number;
    current_phase?: string;
    phase_info?: {
      description?: string;
      nutrition_cue?: string;
      training_cue?: string;
    };
    total_weeks?: number;
    competition_date?: string;
  };
}

// Tier bands match backend pds.py: novice<50, intermediate 50-70, advanced 70-85, elite 85+
const TIER_BANDS: Record<string, [number, number]> = {
  novice:       [0,  50],
  intermediate: [50, 70],
  advanced:     [70, 85],
  elite:        [85, 100],
};

const PHASE_COLORS: Record<string, string> = {
  offseason:   "bg-blue-500/20 text-blue-400",
  lean_bulk:   "bg-green-500/20 text-green-400",
  cut:         "bg-orange-500/20 text-orange-400",
  peak_week:   "bg-yellow-500/20 text-yellow-400",
  contest:     "bg-red-500/20 text-red-400",
  restoration: "bg-purple-500/20 text-purple-400",
  // PPM (Perpetual Progression Mode) sub-phases
  ppm_assessment:      "bg-sky-500/20 text-sky-400",
  ppm_accumulation:    "bg-emerald-500/20 text-emerald-400",
  ppm_intensification: "bg-amber-500/20 text-amber-400",
  ppm_deload:          "bg-slate-500/20 text-slate-400",
  ppm_checkpoint:      "bg-purple-500/20 text-purple-400",
  ppm_mini_cut:        "bg-orange-500/20 text-orange-400",
};

const GAP_TYPE_COLORS: Record<string, string> = {
  add_muscle:   "#ef4444",
  at_ideal:     "#4ade80",
  above_ideal:  "#a3e635",
  reduce_girth: "#f97316",
};

// Heatmap color-scale floor slider — 10% steps from 0 to 110.
// Labels are shown at the anchor stops the user originally requested:
// 0% Gap, 50%, 70%, 85%, 95%, 110% Ideal.
const HEATMAP_FLOOR_STOPS = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110];
const HEATMAP_FLOOR_LABELS: Record<number, string> = {
  0: "Gap",
  50: "50",
  70: "70",
  85: "85",
  95: "95",
  110: "Ideal",
};

// Single source of truth for dashboard card metadata. Drives edit mode
// (labels, default order) and the Settings visibility list.
const CARD_REGISTRY: Array<{ key: string; label: string }> = [
  { key: "workout_tomorrow", label: "Tomorrow's Workout" },
  { key: "macro_adherence", label: "Macro Adherence" },
  { key: "mesocycle_progress", label: "Mesocycle Progress" },
  { key: "tomorrow_split", label: "Tomorrow's Split" },
  { key: "daily_quote", label: "Daily Fire" },
  { key: "goal_photo", label: "Your Goal" },
  { key: "sleep_quality_week", label: "Sleep Quality Week" },
  { key: "spider", label: "Proportion Spider" },
  { key: "muscle_gaps", label: "Muscle Gaps" },
  { key: "pds_trajectory", label: "PDS Trajectory" },
  { key: "heatmap", label: "Hypertrophy Heatmap" },
  { key: "symmetry", label: "Bilateral Symmetry" },
  { key: "phase_rec", label: "Phase Recommendation" },
  { key: "comp_class", label: "Competition Class" },
  { key: "growth_projection", label: "Growth Projection" },
  { key: "detail_metrics", label: "Detail Metrics" },
  { key: "ari", label: "Autonomic Fuel Gauge" },
  { key: "adherence", label: "Adherence Grid" },
  { key: "prep_timeline", label: "Prep Timeline" },
  { key: "strength_progression", label: "Strength Progression" },
  { key: "body_weight_trend", label: "Body Weight Trend" },
  { key: "weekly_volume", label: "Weekly Volume" },
  { key: "recovery_trend", label: "Recovery Trend" },
  { key: "energy_availability", label: "Energy Availability" },
  { key: "training_time", label: "Weekly Training Time" },
  // PPM (Perpetual Progression Mode) widgets — active when profile.ppm_enabled.
  { key: "tier_readiness", label: "Tier Readiness" },
  { key: "cycle_progress", label: "Improvement Cycle" },
  { key: "parity_check", label: "Arm-Calf-Neck Parity" },
  { key: "chest_waist", label: "Chest : Waist Ratio" },
  { key: "carb_cycle", label: "Carb Cycle" },
  { key: "conditioning_style", label: "Conditioning Style" },
  { key: "natural_ceiling", label: "Natural Ceiling" },
];
const DEFAULT_CARD_ORDER = CARD_REGISTRY.map((c) => c.key);

// On first dashboard load, seed only these 3 widgets visible. The user can
// always add more via Edit Dashboard. A fresh install with all 20 widgets
// shown at once is overwhelming.
const ONBOARDING_DEFAULT_VIZ = ["workout_tomorrow", "macro_adherence", "mesocycle_progress"];
const LABEL_OF: Record<string, string> = Object.fromEntries(
  CARD_REGISTRY.map((c) => [c.key, c.label])
);

function pctToBarColor(pct: number): string {
  if (pct >= 95) return "#4ade80";
  if (pct >= 80) return "#a3e635";
  if (pct >= 60) return "#eab308";
  return "#ef4444";
}

function InfoTooltip({ text }: { text: string }) {
  const [show, setShow] = useState(false);
  return (
    <span className="relative inline-block ml-1">
      <button
        onMouseEnter={() => setShow(true)}
        onMouseLeave={() => setShow(false)}
        className="text-jungle-dim hover:text-jungle-accent text-[10px] w-4 h-4 rounded-full border border-current flex items-center justify-center"
      >
        ⓘ
      </button>
      {show && (
        <div className="absolute z-50 bottom-full left-1/2 -translate-x-1/2 mb-1 w-48 bg-jungle-deeper border border-jungle-border rounded-lg p-2 text-[10px] text-jungle-muted shadow-xl">
          {text}
        </div>
      )}
    </span>
  );
}

export default function DashboardPage() {
  const router = useRouter();
  const { user, loading, logout } = useAuth();
  const [pds, setPds] = useState<PDSData | null>(null);
  const [muscleGaps, setMuscleGaps] = useState<MuscleGapsData | null>(null);
  const [symmetry, setSymmetry] = useState<SymmetryData | null>(null);
  const [phaseRec, setPhaseRec] = useState<PhaseRecommendation | null>(null);
  const [ari, setAri] = useState<ARIData | null>(null);
  // Coaching feedback (B6/B7)
  const [coachingFeedbackId, setCoachingFeedbackId] = useState<string | null>(null);
  const [coachingMessages, setCoachingMessages] = useState<CoachingMessage[]>([]);
  const [adherence, setAdherence] = useState<AdherenceEntry[]>([]);
  // dashboard_viz toggle map: visKey -> show/hide. Undefined = show.
  const [vizVisibility, setVizVisibility] = useState<Record<string, boolean>>({});
  const isVizOn = (key: string) => vizVisibility[key] !== false;

  // Heatmap color-scale floor — user-selectable via slider on the heatmap card.
  const [heatmapFloor, setHeatmapFloor] = useState<number>(75);
  const heatmapSaveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const saveHeatmapFloor = (value: number) => {
    if (heatmapSaveTimer.current) clearTimeout(heatmapSaveTimer.current);
    heatmapSaveTimer.current = setTimeout(() => {
      api.patch("/onboarding/profile", {
        preferences: { dashboard_settings: { heatmap_floor: value } },
      }).catch(() => {});
    }, 500);
  };

  // Dashboard edit mode — drag/hide/reorder cards.
  const [editMode, setEditMode] = useState(false);
  const [cardOrder, setCardOrder] = useState<string[]>(DEFAULT_CARD_ORDER);
  const [editSnapshot, setEditSnapshot] = useState<{
    order: string[];
    viz: Record<string, boolean>;
  } | null>(null);
  const [savingLayout, setSavingLayout] = useState(false);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const orderOf = (key: string): number => {
    const idx = cardOrder.indexOf(key);
    return idx === -1 ? cardOrder.length + CARD_REGISTRY.findIndex((c) => c.key === key) : idx;
  };

  const hideCard = (key: string) => {
    setVizVisibility((prev) => ({ ...prev, [key]: false }));
  };

  const showCard = (key: string) => {
    setVizVisibility((prev) => ({ ...prev, [key]: true }));
    // Make sure the card is in the order list so it renders
    setCardOrder((prev) => (prev.includes(key) ? prev : [...prev, key]));
  };

  const enterEditMode = () => {
    setEditSnapshot({ order: [...cardOrder], viz: { ...vizVisibility } });
    setEditMode(true);
  };

  const cancelEditMode = () => {
    if (editSnapshot) {
      setCardOrder(editSnapshot.order);
      setVizVisibility(editSnapshot.viz);
    }
    setEditSnapshot(null);
    setEditMode(false);
  };

  const saveLayout = async () => {
    setSavingLayout(true);
    try {
      await api.patch("/onboarding/profile", {
        preferences: {
          dashboard_settings: {
            order: cardOrder,
            viz: vizVisibility,
            heatmap_floor: heatmapFloor,
          },
        },
      });
      setEditSnapshot(null);
      setEditMode(false);
      showToast("Dashboard layout saved", "success");
    } catch {
      showToast("Couldn't save dashboard layout", "error");
    } finally {
      setSavingLayout(false);
    }
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    setCardOrder((prev) => {
      const oldIdx = prev.indexOf(String(active.id));
      const newIdx = prev.indexOf(String(over.id));
      if (oldIdx < 0 || newIdx < 0) return prev;
      return arrayMove(prev, oldIdx, newIdx);
    });
  };

  const hiddenCards = CARD_REGISTRY.filter((c) => vizVisibility[c.key] === false);

  // New dashboard datasets
  interface StrengthSeries { lift: string; label: string; color: string; data: { date: string; e1rm_kg: number }[]; }
  const [strengthSeries, setStrengthSeries] = useState<StrengthSeries[]>([]);
  interface VolumeRow { muscle: string; sets: number; mev: number; mav: number; mrv: number; }
  const [weeklyVolume, setWeeklyVolume] = useState<VolumeRow[]>([]);
  interface RecoveryPoint { date: string; score: number; }
  const [recoveryTrend, setRecoveryTrend] = useState<RecoveryPoint[]>([]);
  // Mesocycle program state for the new Mesocycle Progress widget
  interface ProgramState { current_week: number; mesocycle_weeks: number; split_type: string; }
  const [program, setProgram] = useState<ProgramState | null>(null);
  // Cardio prescription for the Weekly Training Time widget
  interface CardioPrescriptionState {
    cardio?: { duration_min?: number; sessions_per_week?: number };
    summary?: { cardio_sessions?: number };
  }
  const [cardioPrescription, setCardioPrescription] = useState<CardioPrescriptionState | null>(null);
  const [runningDiag, setRunningDiag] = useState(false);
  const [diagnostic, setDiagnostic] = useState<DiagnosticData | null>(null);
  const [classEstimate, setClassEstimate] = useState<ClassEstimate | null>(null);
  const [dashLoading, setDashLoading] = useState(true);

  // ── PPM (Perpetual Progression Mode) ────────────────────────────────────
  interface PPMStatus {
    ppm_enabled: boolean;
    target_tier: number | null;
    training_status: "natural" | "enhanced";
    current_cycle_number: number;
    current_cycle_start_date: string | null;
    current_cycle_week: number;
    cycle_focus_muscles: string[] | null;
    competition_date: string | null;
    current_phase: string;
  }
  const [ppmStatus, setPpmStatus] = useState<PPMStatus | null>(null);
  const [ppmReadiness, setPpmReadiness] = useState<TierReadiness | null>(null);
  const [ppmProjection, setPpmProjection] = useState<TierProjection | null>(null);
  const [ppmAttain, setPpmAttain] = useState<NaturalAttainability | null>(null);
  interface PPMTape {
    bicep: number | null;
    calf: number | null;
    neck: number | null;
    chest: number | null;
    waist: number | null;
  }
  const [ppmTape, setPpmTape] = useState<PPMTape | null>(null);
  interface CarbCycleData {
    high_day: { protein_g: number; carbs_g: number; fat_g: number; target_calories: number } | null;
    medium_day: { protein_g: number; carbs_g: number; fat_g: number; target_calories: number } | null;
    low_day: { protein_g: number; carbs_g: number; fat_g: number; target_calories: number } | null;
    days_per_week?: { high: number; medium: number; low: number };
  }
  const [carbCycle, setCarbCycle] = useState<CarbCycleData | null>(null);
  const [conditioningStyle, setConditioningStyle] = useState<"full" | "tight" | "dry" | "grainy" | null>(null);
  const [divisionCapKg, setDivisionCapKg] = useState<number | null>(null);

  // Today's session preview
  const [todaySession, setTodaySession] = useState<{ session_type: string; sets: { exercise_name: string }[] } | null>(null);
  const [todayMacros, setTodayMacros] = useState<{ target_calories: number; protein_g: number; carbs_g: number; fat_g: number; phase: string } | null>(null);

  // Tomorrow's session for the Tomorrow's Split + Tomorrow's Workout widgets
  interface TomorrowSession {
    session_type: string;
    workout_window?: { est_minutes?: number };
    sets: { exercise_name: string; is_warmup: boolean }[];
  }
  const [tomorrowSession, setTomorrowSession] = useState<TomorrowSession | null>(null);

  // Sleep week for the Sleep Quality Week widget
  interface SleepWeekDay { date: string; weekday: string; quality: number | null; hours: number | null; }
  interface SleepWeekData { days: SleepWeekDay[]; avg_quality: number | null; avg_hours: number | null; logged_count: number; }
  const [sleepWeek, setSleepWeek] = useState<SleepWeekData | null>(null);

  // Goal + aspiration photo — stored in profile.preferences.aspiration
  interface Aspiration { goal_text?: string; aspiration_photo_url?: string; }
  const [aspiration, setAspiration] = useState<Aspiration | null>(null);
  const [editingGoal, setEditingGoal] = useState(false);
  const [goalDraft, setGoalDraft] = useState("");
  const [goalPhotoDraft, setGoalPhotoDraft] = useState<string | null>(null);
  const [goalSaving, setGoalSaving] = useState(false);

  // Daily inspirational quote — deterministic per day, zero network cost
  const quote = getQuoteForToday();

  // Quick log weight state
  const [quickWeight, setQuickWeight] = useState("");

  // Viltrum onboarding wizard — only shows once per user account
  const [showWizard, setShowWizard] = useState(false);
  useEffect(() => {
    if (user && shouldShowWizard(user.id)) setShowWizard(true);
  }, [user]);

  // kg/lbs toggle — synced with training page via localStorage
  const [useLbs, setUseLbs] = useState(false);
  useEffect(() => {
    setUseLbs(localStorage.getItem("useLbs") === "true");
  }, []);
  const toggleUnit = () => {
    const next = !useLbs;
    setUseLbs(next);
    localStorage.setItem("useLbs", String(next));
  };
  const unit = useLbs ? "lbs" : "kg";
  const wt = (kg: number | null | undefined, decimals = 1): string => {
    if (kg == null) return "—";
    const val = useLbs ? kg * 2.20462 : kg;
    return val.toFixed(decimals);
  };

  // Calculate inflation multiplier for current body -> ideal ghost
  const currentLbm = diagnostic?.body_fat?.lean_mass_kg || 0;
  const targetLbm = diagnostic?.weight_cap?.target_lbm_kg || 0;
  const inflationMultiplier = (currentLbm > 0 && targetLbm > 0)
    ? Math.pow(targetLbm / currentLbm, 1 / 3)
    : diagnostic?.ghost_model?.allometric_multiplier || 1.0;
  const [quickLogging, setQuickLogging] = useState(false);
  const [quickLogged, setQuickLogged] = useState(false);
  const [recentWeights, setRecentWeights] = useState<WeightEntry[]>([]);

  useEffect(() => {
    if (!loading && !user) { router.push("/auth/login"); return; }
    if (!user) return;

    // Reset state before fetching new data to prevent bleedthrough
    setPds(null);
    setMuscleGaps(null);
    setSymmetry(null);
    setPhaseRec(null);
    setAri(null);
    setAdherence([]);
    setDiagnostic(null);
    setClassEstimate(null);
    setRecentWeights([]);
    setTomorrowSession(null);
    setSleepWeek(null);

    // Soft-fail helper: fetch data, set state on success, log on failure.
    // Dashboard widgets are independent — one failure shouldn't block others.
    let failCount = 0;
    const softFetch = <T,>(path: string, setter: (v: T) => void) =>
      api.get<T>(path).then(setter).catch(() => { failCount++; });

    // Load independent data immediately
    softFetch<ARIData>("/engine2/ari", setAri);
    softFetch<{ id: string | null; messages: CoachingMessage[] }>(
      "/checkin/coaching-feedback",
      (r) => { setCoachingFeedbackId(r.id); setCoachingMessages(r.messages || []); },
    );
    softFetch<AdherenceEntry[]>("/engine3/adherence", setAdherence);
    softFetch<WeightEntry[]>("/checkin/weight-history?days=14", setRecentWeights);

    // Pull dashboard viz visibility + heatmap floor + card order from profile.preferences.
    // dashboard_settings is the new rich key; dashboard_viz is the legacy
    // flat map we fall back to for users who haven't migrated yet.
    api.get<{
      preferences?: {
        dashboard_viz?: Record<string, boolean>;
        onboarding_viz_initialized?: boolean;
        aspiration?: Aspiration;
        dashboard_settings?: {
          viz?: Record<string, boolean>;
          heatmap_floor?: number;
          order?: string[];
        };
      };
    }>("/onboarding/profile")
      .then((p) => {
        const prefs = p?.preferences || {};
        const settings = prefs.dashboard_settings || {};
        setAspiration(prefs.aspiration || null);

        const hasSavedViz =
          (settings.viz && Object.keys(settings.viz).length > 0) ||
          (prefs.dashboard_viz && Object.keys(prefs.dashboard_viz).length > 0);
        const isFreshUser = !hasSavedViz && !prefs.onboarding_viz_initialized;

        if (isFreshUser) {
          // First-run: show only 3 beginner widgets so new users aren't
          // overwhelmed. They can opt-in to the rest via Edit Dashboard.
          const seeded: Record<string, boolean> = {};
          for (const key of DEFAULT_CARD_ORDER) {
            seeded[key] = ONBOARDING_DEFAULT_VIZ.includes(key);
          }
          const seededOrder = [
            ...ONBOARDING_DEFAULT_VIZ,
            ...DEFAULT_CARD_ORDER.filter((k) => !ONBOARDING_DEFAULT_VIZ.includes(k)),
          ];
          setVizVisibility(seeded);
          setCardOrder(seededOrder);
          api.patch("/onboarding/profile", {
            preferences: {
              onboarding_viz_initialized: true,
              dashboard_settings: { viz: seeded, order: seededOrder },
            },
          }).catch(() => {});
        } else {
          setVizVisibility(settings.viz || prefs.dashboard_viz || {});
          if (Array.isArray(settings.order) && settings.order.length > 0) {
            // Keep only known keys; append any missing keys at the end so new
            // cards added in future releases still render (but stay hidden
            // unless the user explicitly enables them).
            const known = new Set(DEFAULT_CARD_ORDER);
            const sanitized = settings.order.filter((k: string) => known.has(k));
            const missing = DEFAULT_CARD_ORDER.filter((k) => !sanitized.includes(k));
            setCardOrder([...sanitized, ...missing]);
          }
        }
        if (typeof settings.heatmap_floor === "number") {
          setHeatmapFloor(settings.heatmap_floor);
        }
      })
      .catch(() => {});

    // Tomorrow's session for the Tomorrow widgets
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    const tomorrowStr = tomorrow.toISOString().split("T")[0];
    softFetch<TomorrowSession>(`/engine2/session/${tomorrowStr}`, setTomorrowSession);

    // Sleep quality for the last 7 days
    softFetch<SleepWeekData>("/checkin/sleep-week", setSleepWeek);

    // New dashboard data
    softFetch<{ series: StrengthSeries[] }>("/engine2/strength/progression", (r) => setStrengthSeries(r.series || []));
    softFetch<{ rows: VolumeRow[] }>("/engine2/volume/weekly", (r) => setWeeklyVolume(r.rows || []));
    softFetch<{ data: RecoveryPoint[] }>("/checkin/recovery/trend?days=30", (r) => setRecoveryTrend(r.data || []));
    // For Mesocycle Progress + Weekly Training Time widgets
    softFetch<ProgramState>("/engine2/program/current", setProgram);
    softFetch<CardioPrescriptionState>("/engine3/cardio/prescription", setCardioPrescription);

    // Today's plan previews
    const todayStr = new Date().toISOString().split("T")[0];
    softFetch<any>(`/engine2/session/${todayStr}`, setTodaySession);
    softFetch<any>("/engine3/prescription/current", setTodayMacros);

    // Fetch Engine 1 outputs from cache in parallel. We DO NOT re-run the
    // full Engine 1 compute on every page load — that's an expensive
    // recalculation that only makes sense after a new check-in. The user
    // can click "Re-run Diagnostics" on the diagnostic card if they want
    // a fresh pass. Huge perf win on repeat dashboard visits.
    Promise.all([
      softFetch<PDSData>("/engine1/pds", setPds),
      softFetch<MuscleGapsData>("/engine1/muscle-gaps", setMuscleGaps),
      softFetch<SymmetryData>("/engine1/symmetry", setSymmetry),
      softFetch<PhaseRecommendation>("/engine1/phase-recommendation", setPhaseRec),
      softFetch<DiagnosticData>("/engine1/diagnostic", setDiagnostic),
      softFetch<ClassEstimate>("/engine1/class-estimate", setClassEstimate),
      // PPM status — always fetched; the component renders cards only when enabled.
      api.get<PPMStatus>("/ppm/status")
        .then((s) => {
          setPpmStatus(s);
          if (s.ppm_enabled && s.target_tier != null) {
            // Fetch readiness + honesty + macros once PPM is active.
            interface EvaluateResp {
              readiness: TierReadiness;
              projection: TierProjection;
              tape: { bicep: number | null; calf: number | null; neck: number | null; chest: number | null; waist: number | null };
              weight_cap_kg: number;
            }
            api.post<EvaluateResp>("/ppm/evaluate", {})
              .then((r) => {
                setPpmReadiness(r.readiness);
                setPpmProjection(r.projection);
                setDivisionCapKg(r.weight_cap_kg ?? null);
                setPpmTape({
                  bicep: r.tape?.bicep ?? null,
                  calf: r.tape?.calf ?? null,
                  neck: r.tape?.neck ?? null,
                  chest: r.tape?.chest ?? null,
                  waist: r.tape?.waist ?? null,
                });
              })
              .catch(() => {});
            api.post<NaturalAttainability>("/ppm/attainability", { target_tier: s.target_tier })
              .then(setPpmAttain)
              .catch(() => {});
            // Carb cycle comes back with the current week's plan macros.
            api.get<{
              week_plan: { macros: { carb_cycle: CarbCycleData } };
            }>(`/ppm/plan/${s.current_cycle_week || 1}`)
              .then((p) => setCarbCycle(p.week_plan?.macros?.carb_cycle ?? null))
              .catch(() => {});
          }
        })
        .catch(() => { /* PPM not enabled or endpoint unavailable */ }),
    ]).then(() => {
      if (failCount > 3) {
        showToast("Some dashboard data failed to load. Check your connection.", "warning");
      }
      setDashLoading(false);
    });
  }, [user, loading, router]);

  if (loading || !user) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-jungle-dark">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-jungle-accent animate-pulse" />
          <p className="text-jungle-muted">Loading Viltrum...</p>
        </div>
      </main>
    );
  }

  const runDiagnostics = async () => {
    setRunningDiag(true);
    try {
      await api.post("/engine1/run");
      
      // Update dependent engines after the new state is measured
      await api.post("/engine2/program/generate").catch(() => { /* program may not exist yet */ });
      await api.post("/engine3/autoregulation").catch(() => { /* rx may not exist yet */ });
      
      const [newPds, newGaps, newSymmetry, newPhaseRec, newDiag] = await Promise.all([
        api.get<PDSData>("/engine1/pds"),
        api.get<MuscleGapsData>("/engine1/muscle-gaps"),
        api.get<SymmetryData>("/engine1/symmetry"),
        api.get<PhaseRecommendation>("/engine1/phase-recommendation"),
        api.get<DiagnosticData>("/engine1/diagnostic"),
      ]);
      setPds(newPds);
      setMuscleGaps(newGaps);
      setSymmetry(newSymmetry);
      setPhaseRec(newPhaseRec);
      setDiagnostic(newDiag);
      api.get<ClassEstimate>("/engine1/class-estimate").then(setClassEstimate).catch(() => {});
      api.get<WeightEntry[]>("/checkin/weight-history?days=14").then(setRecentWeights).catch(() => {});
      api.get<ARIData>("/engine2/ari").then(setAri).catch(() => {});
    } catch (e) {
      showToast("Diagnostics failed to run. Try again.", "error");
    } finally {
      setRunningDiag(false);
    }
  };

  const openGoalEditor = () => {
    setGoalDraft(aspiration?.goal_text || "");
    setGoalPhotoDraft(aspiration?.aspiration_photo_url || null);
    setEditingGoal(true);
  };

  const handleGoalPhotoChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const formData = new FormData();
    formData.append("file", file);
    try {
      const res = await api.postFormData<{ url: string }>("/upload", formData);
      setGoalPhotoDraft(res.url);
    } catch {
      showToast("Photo upload failed", "error");
    }
  };

  const saveGoal = async () => {
    setGoalSaving(true);
    try {
      const next: Aspiration = {
        goal_text: goalDraft.trim() || undefined,
        aspiration_photo_url: goalPhotoDraft || undefined,
      };
      await api.patch("/onboarding/profile", { preferences: { aspiration: next } });
      setAspiration(next);
      setEditingGoal(false);
      showToast("Goal saved", "success");
    } catch {
      showToast("Couldn't save goal", "error");
    } finally {
      setGoalSaving(false);
    }
  };

  const handleQuickLog = async () => {
    const val = parseFloat(quickWeight);
    if (isNaN(val) || val <= 0) {
      showToast("Enter a valid body weight", "warning");
      return;
    }
    setQuickLogging(true);
    const kg_val = useLbs ? val / 2.20462 : val;
    try {
      await api.post("/checkin/daily", { body_weight_kg: kg_val });
      setQuickLogged(true);
      setQuickWeight("");
      showToast(`Logged ${val.toFixed(1)} ${unit}`, "success");
      setTimeout(() => setQuickLogged(false), 2000);
      api.get<WeightEntry[]>("/checkin/weight-history?days=14").then(setRecentWeights).catch(() => {});
    } catch (err) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Couldn't log weight";
      showToast(msg, "error");
    } finally {
      setQuickLogging(false);
    }
  };

  // Spider chart: use pct_of_ideal so underdeveloped muscles show correctly
  const spiderData = muscleGaps
    ? Object.entries(muscleGaps.sites).map(([site, data]) => ({
        label: siteLabel(site),
        value: data.pct_of_ideal,
      }))
    : [];

  // PDS line chart data
  const pdsLineData = pds
    ? pds.history.map((e) => ({ label: e.date.slice(5), value: e.pds_score }))
    : [];

  // Current tier band for PDS chart
  const currentTier = pds?.current.tier ?? "novice";
  const tierBand = TIER_BANDS[currentTier] ?? [0, 100];

  // Sparkline for recent weights (last 7 entries)
  const sparklineEntries = recentWeights.slice(-7);
  const sparklinePath = (() => {
    if (sparklineEntries.length < 2) return null;
    const values = sparklineEntries.map((e) => e.weight_kg);
    const min = Math.min(...values);
    const max = Math.max(...values);
    const range = max - min || 1;
    const W = 80;
    const H = 24;
    const pts = values.map((v, i) => {
      const x = (i / (values.length - 1)) * W;
      const y = H - ((v - min) / range) * H;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    });
    return `M${pts.join("L")}`;
  })();

  // Competition countdown data
  const timeline = diagnostic?.prep_timeline;
  const weeksOut = timeline?.weeks_out;
  const currentPhase = timeline?.current_phase ?? "offseason";
  const phaseInfo = timeline?.phase_info;
  const totalWeeks = Math.min(timeline?.total_weeks ?? 52, 52);
  const phaseColorClass = PHASE_COLORS[currentPhase] ?? "bg-blue-500/20 text-blue-400";

  return (
    <div className="min-h-screen">
      {showWizard && <OnboardingWizard onDismiss={() => setShowWizard(false)} userId={user?.id} />}
      <NavBar username={user.username} onLogout={() => { logout(); router.push("/"); }} />

      <main className="container-app py-6">
        {/* Header — Tegaki-animated wordmark + greeting subtitle */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
          <div>
            <PageTitle
              text="Dashboard"
              subtitle={<><span className="text-viltrum-travertine uppercase tracking-[2px] text-[10px] mr-2">Hello,</span><span className="font-medium text-viltrum-obsidian">{user.display_name || user.username}</span></>}
            />
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={toggleUnit}
              className="btn-secondary text-xs px-3 py-1.5 font-mono"
              title="Toggle weight unit"
            >
              {useLbs ? "LBS" : "KG"}
            </button>
            <a href="/checkin" className="btn-primary text-center whitespace-nowrap">
              Daily Check-In
            </a>
          </div>
        </div>

        {/* Today's Plan — quick glance at what needs to happen today */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-6">
          {/* Today's Training */}
          <a href="/training" className="card card-hover flex items-center gap-3 py-3">
            <div className="w-10 h-10 rounded-xl bg-jungle-accent/15 flex items-center justify-center shrink-0">
              <svg className="w-5 h-5 text-jungle-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-xs text-jungle-dim uppercase tracking-wider">Today&apos;s Training</p>
              {todaySession ? (
                <>
                  <p className="text-sm font-semibold text-jungle-text capitalize truncate">
                    {todaySession.session_type.replace(/_/g, " ")} Day
                  </p>
                  <p className="text-[10px] text-jungle-muted">
                    {new Set(todaySession.sets.map(s => s.exercise_name)).size} exercises
                  </p>
                </>
              ) : (
                <p className="text-sm font-medium text-jungle-muted">Rest Day</p>
              )}
            </div>
            <svg className="w-4 h-4 text-jungle-dim shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </a>

          {/* Today's Nutrition */}
          <a href="/nutrition" className="card card-hover flex items-center gap-3 py-3">
            <div className="w-10 h-10 rounded-xl bg-green-500/15 flex items-center justify-center shrink-0">
              <svg className="w-5 h-5 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16m-7 6h7" />
              </svg>
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-xs text-jungle-dim uppercase tracking-wider">Today&apos;s Macros</p>
              {todayMacros ? (
                <>
                  <p className="text-sm font-semibold text-jungle-text">
                    {Math.round(todayMacros.target_calories)} kcal
                  </p>
                  <p className="text-[10px] text-jungle-muted">
                    P {Math.round(todayMacros.protein_g)}g · C {Math.round(todayMacros.carbs_g)}g · F {Math.round(todayMacros.fat_g)}g
                  </p>
                </>
              ) : (
                <p className="text-sm font-medium text-jungle-muted">No prescription yet</p>
              )}
            </div>
            <svg className="w-4 h-4 text-jungle-dim shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </a>
        </div>

        {/* PDS Banner */}
        {dashLoading && !pds ? (
          <div className="card mb-6 animate-pulse">
            <div className="flex flex-col sm:flex-row items-center gap-4 sm:gap-8">
              <div className="text-center sm:text-left shrink-0">
                <div className="h-3 bg-jungle-deeper rounded w-32 mb-2" />
                <div className="h-12 bg-jungle-deeper rounded w-20 mb-2" />
                <div className="h-3 bg-jungle-deeper rounded w-24" />
              </div>
              <div className="flex-1 grid grid-cols-2 sm:grid-cols-4 gap-3 w-full">
                {[1,2,3,4].map(i => (
                  <div key={i} className="text-center">
                    <div className="h-2 bg-jungle-deeper rounded w-16 mx-auto mb-2" />
                    <div className="h-5 bg-jungle-deeper rounded w-10 mx-auto" />
                  </div>
                ))}
              </div>
            </div>
          </div>
        ) : null}
        {pds ? (
          <div className="card mb-6 bg-jungle-gradient space-y-4">
            {/* Row 1 — PDS score + component rings + re-run button */}
            <div className="flex flex-col md:flex-row items-center gap-5 md:gap-6">
              {/* Big PDS ring */}
              <div className="shrink-0 flex items-center gap-4">
                <div className="relative w-24 h-24">
                  <svg viewBox="0 0 100 100" className="w-24 h-24 -rotate-90">
                    <circle cx="50" cy="50" r="42" fill="none" stroke="#1a3328" strokeWidth="8" />
                    <circle
                      cx="50"
                      cy="50"
                      r="42"
                      fill="none"
                      stroke="#c8a84e"
                      strokeWidth="8"
                      strokeLinecap="round"
                      strokeDasharray={`${(pds.current.pds_score / 100) * 263.9} 263.9`}
                    />
                  </svg>
                  <div className="absolute inset-0 flex flex-col items-center justify-center">
                    <span className="text-2xl font-bold text-jungle-accent leading-none">{Math.round(pds.current.pds_score)}</span>
                    <span className="text-[9px] text-jungle-dim uppercase tracking-wider mt-0.5">PDS</span>
                  </div>
                </div>
                <div className="text-left">
                  <p className="text-[10px] text-jungle-muted uppercase tracking-wider">
                    Physique Development Score
                  </p>
                  <p className="text-jungle-fern text-sm capitalize font-semibold mt-0.5">
                    {pds.current.tier} tier
                  </p>
                  {pds.history && pds.history.length >= 2 && (() => {
                    const latest = pds.history[pds.history.length - 1].pds_score;
                    const prev = pds.history[pds.history.length - 2].pds_score;
                    const delta = latest - prev;
                    return (
                      <p className={`text-[11px] mt-0.5 ${delta >= 0 ? "text-green-400" : "text-red-400"}`}>
                        {delta >= 0 ? "▲" : "▼"} {Math.abs(delta).toFixed(1)} vs last
                      </p>
                    );
                  })()}
                </div>
              </div>

              {/* Component mini-rings */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 flex-1 w-full">
                {Object.entries(pds.current.components).map(([key, val]) => {
                  const pct = Math.max(0, Math.min(100, val));
                  const color = pct >= 80 ? "#22c55e" : pct >= 60 ? "#c8a84e" : pct >= 40 ? "#f97316" : "#ef4444";
                  return (
                    <div key={key} className="flex flex-col items-center">
                      <div className="relative w-14 h-14">
                        <svg viewBox="0 0 100 100" className="w-14 h-14 -rotate-90">
                          <circle cx="50" cy="50" r="40" fill="none" stroke="#1a3328" strokeWidth="8" />
                          <circle
                            cx="50" cy="50" r="40"
                            fill="none"
                            stroke={color}
                            strokeWidth="8"
                            strokeLinecap="round"
                            strokeDasharray={`${(pct / 100) * 251.3} 251.3`}
                          />
                        </svg>
                        <div className="absolute inset-0 flex items-center justify-center">
                          <span className="text-sm font-bold" style={{ color }}>{Math.round(val)}</span>
                        </div>
                      </div>
                      <p className="text-[9px] text-jungle-muted uppercase tracking-wider mt-1 text-center capitalize">
                        {key.replace(/_/g, " ")}
                      </p>
                    </div>
                  );
                })}
              </div>

              {/* Actions */}
              <div className="shrink-0 flex md:flex-col gap-2">
                <button
                  onClick={runDiagnostics}
                  disabled={runningDiag}
                  className="btn-secondary text-xs px-3 py-1.5 disabled:opacity-50"
                >
                  {runningDiag ? "Running…" : "↻ Re-run"}
                </button>
                <a href="/progress" className="btn-secondary text-xs px-3 py-1.5 text-center">
                  Progress →
                </a>
              </div>
            </div>

            {/* Row 2 — Body composition strip */}
            {(diagnostic?.body_fat || diagnostic?.weight_cap) && (
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-3 border-t border-jungle-border/50">
                {diagnostic?.body_fat && (
                  <>
                    <div>
                      <p className="text-[9px] text-jungle-dim uppercase tracking-wider">Body Fat</p>
                      <p className="text-lg font-bold text-jungle-text">{diagnostic.body_fat.body_fat_pct.toFixed(1)}%</p>
                      {diagnostic.body_fat.confidence && (
                        <p className="text-[9px] text-jungle-dim capitalize">{diagnostic.body_fat.confidence} conf</p>
                      )}
                    </div>
                    {diagnostic.body_fat.lean_mass_kg && (
                      <div>
                        <p className="text-[9px] text-jungle-dim uppercase tracking-wider">LBM</p>
                        <p className="text-lg font-bold text-jungle-text">{wt(diagnostic.body_fat.lean_mass_kg)} {unit}</p>
                        <p className="text-[9px] text-jungle-dim">current lean mass</p>
                      </div>
                    )}
                  </>
                )}
                {diagnostic?.weight_cap && (
                  <>
                    <div>
                      <p className="text-[9px] text-jungle-dim uppercase tracking-wider">Weight Cap</p>
                      <p className="text-lg font-bold text-jungle-accent">{wt(diagnostic.weight_cap.weight_cap_kg)} {unit}</p>
                      <p className="text-[9px] text-jungle-dim">IFBB division cap</p>
                    </div>
                    <div>
                      <p className="text-[9px] text-jungle-dim uppercase tracking-wider">Target LBM</p>
                      <p className="text-lg font-bold text-green-400">{wt(diagnostic.weight_cap.target_lbm_kg)} {unit}</p>
                      {diagnostic.body_fat?.lean_mass_kg && (
                        <p className="text-[9px] text-jungle-dim">
                          +{wt(diagnostic.weight_cap.target_lbm_kg - diagnostic.body_fat.lean_mass_kg)} {unit} to go
                        </p>
                      )}
                    </div>
                  </>
                )}
              </div>
            )}
          </div>
        ) : (
          <div className="card mb-6 border-dashed border-jungle-border text-center py-8">
            <p className="text-jungle-muted">No diagnostic data yet — diagnostics will run automatically.</p>
          </div>
        )}

        {/* Coaching feedback — top-of-fold, persistent until dismissed (B6/B7) */}
        {coachingMessages.length > 0 && (
          <div className="card mb-4">
            <CoachingFeedbackCard
              feedbackId={coachingFeedbackId}
              messages={coachingMessages}
              onDismiss={() => { setCoachingMessages([]); setCoachingFeedbackId(null); }}
            />
          </div>
        )}

        {/* Edit dashboard controls — desktop only */}
        <div className="hidden md:flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-jungle-muted uppercase tracking-wider">
            Dashboard
          </h2>
          {!editMode ? (
            <button
              onClick={enterEditMode}
              className="text-xs px-3 py-1.5 rounded-lg border border-jungle-border hover:border-jungle-accent text-jungle-muted hover:text-jungle-accent transition-colors"
            >
              ✎ Edit Dashboard
            </button>
          ) : (
            <div className="flex items-center gap-2">
              <span className="text-[10px] text-jungle-dim">
                Drag cards to reorder · click × to hide
              </span>
              <button
                onClick={cancelEditMode}
                className="text-xs px-3 py-1.5 rounded-lg border border-jungle-border hover:border-red-500/60 text-jungle-muted hover:text-red-400 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={saveLayout}
                disabled={savingLayout}
                className="btn-primary text-xs py-1.5 px-3 disabled:opacity-50"
              >
                {savingLayout ? "Saving..." : "Save Layout"}
              </button>
            </div>
          )}
        </div>

        {/* Hidden cards drawer — only visible in edit mode */}
        {editMode && hiddenCards.length > 0 && (
          <div className="hidden md:block mb-4 p-3 bg-jungle-deeper/60 border border-jungle-border rounded-xl">
            <p className="text-[10px] text-jungle-dim uppercase tracking-wider mb-2">
              Hidden cards — click to add back
            </p>
            <div className="flex flex-wrap gap-2">
              {hiddenCards.map((c) => (
                <button
                  key={c.key}
                  onClick={() => showCard(c.key)}
                  className="text-[11px] px-2.5 py-1 rounded-md bg-jungle-card border border-jungle-border hover:border-jungle-accent text-jungle-muted hover:text-jungle-accent"
                >
                  + {c.label}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Charts grid */}
        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragEnd={handleDragEnd}
        >
          <SortableContext
            items={cardOrder.filter((k) => vizVisibility[k] !== false)}
            strategy={rectSortingStrategy}
          >
        <div className="columns-1 md:columns-2 xl:columns-3 gap-4 sm:gap-6">
          {(() => {
            const bodies: Record<string, React.ReactNode> = {};

            if (isVizOn("spider")) bodies.spider = (
          <ChartCard
            title="Proportion Spider"
            subtitle="% of Ideal per Site"
            tooltip="Shows how close each muscle site is to your division-ideal lean circumference from the Volumetric Ghost Model (3D biomechanical scaling to your IFBB weight cap). 100% = at ideal."
          >
            {muscleGaps && spiderData.length >= 3 ? (
              <div className="flex flex-col items-center mt-2">
                <SpiderChart data={spiderData} size={220} />
                <p className="text-xs text-jungle-muted mt-1">
                  Avg % of Ideal:{" "}
                  <span className="text-jungle-accent font-bold">{muscleGaps.avg_pct_of_ideal}%</span>
                  <InfoTooltip text="Visibility-weighted average across all sites. Hidden sites (e.g. legs in Men's Physique) are down-weighted." />
                </p>
              </div>
            ) : (
              <EmptyState label="Complete a check-in to see proportion analysis" />
            )}
          </ChartCard>
            );

            if (isVizOn("muscle_gaps")) bodies.muscle_gaps = (
          <ChartCard
            title="Muscle Gaps"
            subtitle="Lean Size vs. Ideal"
            tooltip="Raw centimetre gaps between your current lean circumference and your Volumetric Ghost Model ideal (3D Hanavan physics scaled to your IFBB weight cap). Larger gaps = higher training priority."
          >
            {dashLoading && !muscleGaps ? (
              <div className="mt-2 space-y-2 animate-pulse">
                {[1,2,3,4,5,6].map(i => (
                  <div key={i} className="flex items-center gap-2">
                    <div className="h-3 bg-jungle-deeper rounded w-16" />
                    <div className="flex-1 h-4 bg-jungle-deeper rounded-full" />
                    <div className="h-3 bg-jungle-deeper rounded w-8" />
                  </div>
                ))}
              </div>
            ) : null}
            {muscleGaps ? (
              <div className="mt-2 space-y-2">
                {Object.entries(muscleGaps.sites)
                  .sort(([, a], [, b]) => b.gap_cm - a.gap_cm)
                  .map(([site, data]) => {
                    const barColor = pctToBarColor(data.pct_of_ideal);
                    return (
                      <div key={site}>
                        <div className="flex items-center justify-between text-[11px] mb-0.5">
                          <span className="font-medium">{siteLabel(site)}</span>
                          <span className="text-jungle-dim flex items-center gap-1">
                            <span>{data.current_lean_cm} / {data.ideal_lean_cm} cm</span>
                            {data.gap_type === "add_muscle" && (
                              <span className="text-red-400 font-medium">+{data.gap_cm} needed</span>
                            )}
                            {data.gap_type === "at_ideal" && (
                              <span className="text-green-400">&#10003; ideal</span>
                            )}
                            {data.gap_type === "above_ideal" && (
                              <span className="text-lime-400">&#10003; above</span>
                            )}
                            {data.gap_type === "reduce_girth" && (
                              <span className="text-orange-400">&#8722;{Math.abs(data.gap_cm)} reduce</span>
                            )}
                          </span>
                        </div>
                        <div className="h-1.5 bg-jungle-deeper rounded-full overflow-hidden">
                          <div
                            className="h-full rounded-full transition-all"
                            style={{ width: `${Math.min(100, data.pct_of_ideal)}%`, backgroundColor: barColor }}
                          />
                        </div>
                      </div>
                    );
                  })}
                {muscleGaps.ranked_gaps.length > 0 && (
                  <div className="border-t border-jungle-border pt-2 mt-3">
                    <p className="text-[10px] text-jungle-dim uppercase tracking-wide mb-1">
                      Top priorities — {muscleGaps.total_gap_cm} cm total to add
                    </p>
                    {muscleGaps.ranked_gaps.slice(0, 3).map((g) => (
                      <div key={g.site} className="flex items-center justify-between text-[11px] py-0.5">
                        <span className="text-jungle-muted">{siteLabel(g.site)}</span>
                        <span className="text-red-400 font-medium">+{g.gap_cm} cm needed</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <EmptyState label="Run diagnostics to see gap priorities" />
            )}
          </ChartCard>
            );

            if (isVizOn("pds_trajectory")) bodies.pds_trajectory = (
          <ChartCard
            title="PDS Trajectory"
            subtitle="PDS Glide Path Over Time"
            tooltip="PDS (Physique Development Score) is your overall stage-readiness score. The ideal glide path represents steady progression toward your physical peak."
          >
            {pds && pdsLineData.length >= 2 ? (
              <div className="mt-3">
                <MiniLineChart
                  data={pdsLineData}
                  height={130}
                  domain={[0, 100]}
                  bandMin={tierBand[0]}
                  bandMax={tierBand[1]}
                  bandColor="#c8a84e18"
                />
                <div className="flex items-center justify-between mt-2 text-[10px] text-jungle-dim">
                  <div className="flex items-center gap-2">
                    <span className="w-3 h-1.5 bg-jungle-accent/30 rounded inline-block" />
                    <span className="capitalize">{currentTier} tier band</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="w-3 border-t border-dashed border-jungle-accent/70 inline-block" />
                    <span>Target Trajectory</span>
                  </div>
                </div>
              </div>
            ) : (
              <EmptyState label="Trajectory builds after multiple check-ins" />
            )}
          </ChartCard>
            );

            if (isVizOn("heatmap")) bodies.heatmap = (
          <ChartCard
            title="Hypertrophy Heatmap"
            subtitle="Muscle Development"
            tooltip="Each muscle section is colored by % of Ideal from the Volumetric Ghost Model — how close you are to your division-optimal lean circumference for that site. Red = major gap, green = at or above ideal."
          >
            {muscleGaps ? (
              <div className="mt-2">
                <MuscleHeatmap
                  siteScores={Object.fromEntries(
                    Object.entries(muscleGaps.sites).map(([s, d]) => [s, d.pct_of_ideal])
                  )}
                  overall={muscleGaps.avg_pct_of_ideal}
                  sex="male"
                  floorPct={heatmapFloor}
                />
                {/* Color-scale floor slider — 10% steps from 0 to 110 */}
                <div className="mt-3 pt-3 border-t border-jungle-border/40 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] text-jungle-dim uppercase tracking-wider">Color scale floor</span>
                    <span className="text-[10px] text-jungle-accent font-mono">{heatmapFloor}% {heatmapFloor === 0 ? "(Gap)" : heatmapFloor >= 110 ? "(Ideal)" : ""}</span>
                  </div>
                  <input
                    type="range"
                    min={0}
                    max={HEATMAP_FLOOR_STOPS.length - 1}
                    step={1}
                    value={Math.max(0, HEATMAP_FLOOR_STOPS.indexOf(heatmapFloor))}
                    onChange={(e) => {
                      const next = HEATMAP_FLOOR_STOPS[parseInt(e.target.value)];
                      setHeatmapFloor(next);
                      saveHeatmapFloor(next);
                    }}
                    className="w-full accent-jungle-accent"
                    aria-label="Heatmap color scale floor"
                  />
                  {/* Labeled stops — only the anchor stops (0/50/70/85/95/110)
                      get labels to avoid label collision. All 12 stops are
                      still reachable via the slider. */}
                  <div className="relative h-7 text-[9px] text-jungle-dim">
                    {HEATMAP_FLOOR_STOPS.map((stop) => {
                      const label = HEATMAP_FLOOR_LABELS[stop];
                      if (!label) return null;
                      const pct = (stop / 110) * 100;
                      return (
                        <span
                          key={stop}
                          className="absolute -translate-x-1/2 text-center leading-tight whitespace-nowrap min-w-[30px]"
                          style={{ left: `${pct}%` }}
                        >
                          <span className="block font-mono">{stop}%</span>
                          {label !== String(stop) && (
                            <span className="block text-jungle-dim/60">{label}</span>
                          )}
                        </span>
                      );
                    })}
                  </div>
                  {/* Gradient legend — reflects current floor */}
                  <div className="pt-3">
                    <div
                      className="h-2 rounded-full"
                      style={{
                        background: `linear-gradient(to right,
                          rgb(120,10,10) 0%,
                          rgb(220,38,38) ${(heatmapFloor / 110) * 100}%,
                          rgb(234,88,12) ${((heatmapFloor + (110 - heatmapFloor) * 0.22) / 110) * 100}%,
                          rgb(234,179,8) ${((heatmapFloor + (110 - heatmapFloor) * 0.42) / 110) * 100}%,
                          rgb(180,210,20) ${((heatmapFloor + (110 - heatmapFloor) * 0.6) / 110) * 100}%,
                          rgb(80,200,60) ${((heatmapFloor + (110 - heatmapFloor) * 0.78) / 110) * 100}%,
                          rgb(34,197,94) ${((heatmapFloor + (110 - heatmapFloor) * 0.9) / 110) * 100}%,
                          rgb(16,185,129) 100%)`,
                      }}
                    />
                    <div className="flex justify-between text-[9px] text-jungle-dim mt-1">
                      <span>Under-developed</span>
                      <span>At ideal</span>
                      <span>Elite</span>
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <EmptyState label="Run diagnostics to generate heatmap" />
            )}
          </ChartCard>
            );

            if (isVizOn("symmetry")) bodies.symmetry = (
          <ChartCard
            title="Bilateral Symmetry"
            subtitle="Left vs. Right Balance"
            tooltip="Compares left and right limb measurements. Deviation > 2% flags a lagging side. Symmetry is factored into your PDS score with division-specific weighting."
          >
            {symmetry ? (
              <div className="mt-2 space-y-3">
                {/* Overall score */}
                <div className="flex items-center justify-between">
                  <span className="text-xs text-jungle-muted">Symmetry Score</span>
                  <span
                    className="text-2xl font-bold"
                    style={{ color: symmetry.symmetry_score >= 90 ? "#4ade80" : symmetry.symmetry_score >= 75 ? "#eab308" : "#ef4444" }}
                  >
                    {symmetry.symmetry_score}
                  </span>
                </div>
                <div className="h-1.5 bg-jungle-deeper rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all"
                    style={{
                      width: `${symmetry.symmetry_score}%`,
                      backgroundColor: symmetry.symmetry_score >= 90 ? "#4ade80" : symmetry.symmetry_score >= 75 ? "#eab308" : "#ef4444",
                    }}
                  />
                </div>

                {/* Per-pair breakdown */}
                <div className="space-y-1.5 mt-2">
                  {symmetry.details.map((d) => (
                    <div key={d.site} className="flex items-center justify-between text-[11px]">
                      <span className="capitalize text-jungle-muted w-16">{d.site}</span>
                      <span className="text-jungle-dim">L {d.left_cm} / R {d.right_cm} cm</span>
                      <span
                        className="font-medium ml-1"
                        style={{ color: d.deviation_pct > 2 ? "#f97316" : "#4ade80" }}
                      >
                        {d.deviation_pct > 0.05 ? `${d.deviation_pct}%` : "even"}
                        {d.deviation_pct > 2 && (
                          <span className="text-jungle-dim ml-1 capitalize">({d.dominant_side} dominant)</span>
                        )}
                      </span>
                    </div>
                  ))}
                </div>

                {/* Lagging sides callout */}
                {symmetry.lagging_sides.length > 0 && (
                  <div className="border-t border-jungle-border pt-2">
                    <p className="text-[10px] text-orange-400 uppercase tracking-wide mb-1">Lagging sides (&gt;2% deviation)</p>
                    {symmetry.lagging_sides.map((d) => (
                      <p key={d.site} className="text-[10px] text-jungle-muted capitalize">
                        {d.site}: {d.dominant_side === "left" ? "right" : "left"} side is lagging by {d.diff_cm} cm
                      </p>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <EmptyState label="Log bilateral measurements to see symmetry analysis" />
            )}
          </ChartCard>
            );

            if (isVizOn("phase_rec")) bodies.phase_rec = (
          <ChartCard
            title="Phase Recommendation"
            subtitle="Cross-Engine Analysis"
            tooltip="Recommended training phase based on your current physique state — muscle gaps, PDS score, and body fat. Cross-engine signal from Engine 1 → Engine 3."
          >
            {phaseRec ? (
              <div className="mt-3 flex flex-col h-full">
                <div className="flex items-center gap-3 mb-2">
                  <span
                    className={`px-2 py-1 rounded text-xs font-bold uppercase ${
                      PHASE_COLORS[phaseRec.recommended_phase] ?? "bg-blue-500/20 text-blue-400"
                    }`}
                  >
                    {phaseRec.recommended_phase.replace(/_/g, " ")}
                  </span>
                  {phaseRec.urgency && (
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] uppercase font-medium ${
                        phaseRec.urgency === "high"
                          ? "bg-red-500/20 text-red-400"
                          : phaseRec.urgency === "medium"
                          ? "bg-yellow-500/20 text-yellow-400"
                          : "bg-jungle-deeper text-jungle-dim"
                      }`}
                    >
                      {phaseRec.urgency} urgency
                    </span>
                  )}
                </div>
                {diagnostic?.prep_timeline && (
                   <div className="grid grid-cols-2 gap-2 mb-3">
                     <div className="bg-jungle-deeper rounded-lg p-2 text-center">
                       <p className="text-[9px] text-jungle-dim uppercase tracking-wide">Timeline</p>
                       <p className="text-sm font-bold text-jungle-muted">{diagnostic.prep_timeline.weeks_out} weeks left</p>
                     </div>
                     <div className="bg-jungle-deeper rounded-lg p-2 text-center">
                       <p className="text-[9px] text-jungle-dim uppercase tracking-wide">Duration</p>
                       <p className="text-sm font-bold text-jungle-muted">{diagnostic.prep_timeline.total_weeks} weeks total</p>
                     </div>
                   </div>
                )}
                {phaseRec.reason && (
                  <p className="text-[11px] text-jungle-muted border-t border-jungle-border pt-2 pb-2">
                    {phaseRec.reason}
                  </p>
                )}
                {diagnostic?.prep_timeline?.phase_info && (
                  <div className="border-t border-jungle-border pt-2 mt-auto space-y-1.5">
                    <p className="text-[10px] text-jungle-dim"><span className="font-semibold text-jungle-muted">Diet:</span> {diagnostic.prep_timeline.phase_info.nutrition_cue}</p>
                    <p className="text-[10px] text-jungle-dim"><span className="font-semibold text-jungle-muted">Training:</span> {diagnostic.prep_timeline.phase_info.training_cue}</p>
                  </div>
                )}
              </div>
            ) : (
              <EmptyState label="Run diagnostics to get a phase recommendation" />
            )}
          </ChartCard>
            );

            if (isVizOn("comp_class") && classEstimate) bodies.comp_class = (
            <ChartCard
              title="Competition Class"
              subtitle="Division & Weight Limits"
              tooltip="Your estimated competition class based on height, weight, and division."
            >
              <div className="mt-3 space-y-3">
                <div className="flex items-center gap-3">
                  <span className="px-4 py-2 rounded-xl bg-jungle-accent/20 text-jungle-accent text-xl font-bold">
                    {classEstimate.label}
                  </span>
                  <div>
                    <p className="text-sm text-jungle-text font-medium capitalize">
                      {classEstimate.division.replace(/_/g, " ")}
                    </p>
                  </div>
                </div>

                {diagnostic?.weight_cap && (
                  <div className="grid grid-cols-2 gap-2 text-center">
                    <div className="bg-jungle-deeper rounded-lg p-2.5">
                      <p className="text-[9px] text-jungle-dim uppercase">Weight Cap</p>
                      <p className="text-base font-bold text-jungle-accent">{wt(diagnostic.weight_cap.weight_cap_kg)} {unit}</p>
                    </div>
                    <div className="bg-jungle-deeper rounded-lg p-2.5">
                      <p className="text-[9px] text-jungle-dim uppercase">Stage Weight</p>
                      <p className="text-base font-bold text-green-400">{wt(diagnostic.weight_cap.stage_weight_kg)} {unit}</p>
                    </div>
                  </div>
                )}
              </div>
            </ChartCard>
            );

            if (isVizOn("growth_projection") && muscleGaps) bodies.growth_projection = (
            <ChartCard
              title="Growth Projection"
              subtitle="Where You Are vs. Where You Need To Be"
              tooltip="Shows your current lean measurements as a percentage of your division-ideal target. Based on your gap analysis and current rate of progress."
            >
              <div className="mt-2 space-y-1.5">
                {muscleGaps.ranked_gaps?.length > 0 ? (
                  <>
                    <div className="flex items-center justify-between text-[10px] text-jungle-dim mb-1">
                      <span>Muscle Site</span>
                      <span>% of Ideal</span>
                    </div>
                    {Object.entries(muscleGaps.sites || {})
                      .filter(([site]) => !["waist", "hips"].includes(site))
                      .sort(([, a]: [string, any], [, b]: [string, any]) => (a.pct_of_ideal || 0) - (b.pct_of_ideal || 0))
                      .map(([site, data]: [string, any]) => {
                        const pct = data.pct_of_ideal || 0;
                        const color = pct >= 98 ? "#4ade80" : pct >= 90 ? "#c8a84e" : pct >= 80 ? "#f97316" : "#ef4444";
                        return (
                          <div key={site} className="flex items-center gap-2">
                            <span className="text-[10px] text-jungle-muted w-20 capitalize truncate">{site.replace(/_/g, " ")}</span>
                            <div className="flex-1 h-3 bg-jungle-deeper rounded-full overflow-hidden">
                              <div className="h-full rounded-full transition-all" style={{ width: `${Math.min(100, pct)}%`, backgroundColor: color }} />
                            </div>
                            <span className="text-[10px] font-bold w-10 text-right" style={{ color }}>
                              {pct.toFixed(0)}%
                            </span>
                          </div>
                        );
                      })}
                    <div className="border-t border-jungle-border pt-2 mt-2 flex items-center justify-between">
                      <span className="text-[10px] text-jungle-dim">Overall</span>
                      <span className="text-sm font-bold text-jungle-accent">{muscleGaps.avg_pct_of_ideal?.toFixed(0) || "—"}% of ideal</span>
                    </div>
                  </>
                ) : (
                  <p className="text-jungle-dim text-xs text-center py-4">Run diagnostics to see growth projections</p>
                )}
              </div>
            </ChartCard>
            );

            if (isVizOn("detail_metrics") && diagnostic?.advanced_measurements) bodies.detail_metrics = (
            <ChartCard
              title="Detail Metrics"
              subtitle="Lat Spread & Quad VMO"
              tooltip="Advanced measurements for lat activation and quad development."
            >
              <div className="mt-2 space-y-2">
                {diagnostic.advanced_measurements.lat_spread_delta_cm !== undefined && (
                  <div className="flex items-center justify-between bg-jungle-deeper rounded-lg px-3 py-2">
                    <div>
                      <p className="text-xs text-jungle-muted font-medium">Lat Spread Delta</p>
                      <p className="text-[9px] text-jungle-dim">Relaxed → Spread</p>
                    </div>
                    <span className="text-lg font-bold text-jungle-accent">
                      +{diagnostic.advanced_measurements.lat_spread_delta_cm} cm
                    </span>
                  </div>
                )}
                {diagnostic.advanced_measurements.back_width_cm && (
                  <div className="flex items-center justify-between bg-jungle-deeper rounded-lg px-3 py-2">
                    <p className="text-xs text-jungle-muted font-medium">Back Width</p>
                    <span className="text-lg font-bold text-jungle-accent">{diagnostic.advanced_measurements.back_width_cm} cm</span>
                  </div>
                )}
                {diagnostic.advanced_measurements.quad_vmo_ratio !== undefined && (
                  <div className="flex items-center justify-between bg-jungle-deeper rounded-lg px-3 py-2">
                    <div>
                      <p className="text-xs text-jungle-muted font-medium">VMO Ratio</p>
                      <p className="text-[9px] text-jungle-dim">Target: 0.76–0.82</p>
                    </div>
                    <span className={`text-lg font-bold ${
                      (diagnostic.advanced_measurements.quad_vmo_ratio >= 0.76 && diagnostic.advanced_measurements.quad_vmo_ratio <= 0.82)
                        ? "text-green-400" : "text-yellow-400"
                    }`}>
                      {diagnostic.advanced_measurements.quad_vmo_ratio.toFixed(3)}
                    </span>
                  </div>
                )}
              </div>
            </ChartCard>
            );

            if (isVizOn("ari")) bodies.ari = (
          <ChartCard
            title="Autonomic Fuel Gauge"
            subtitle="Recovery Status · ARI"
            tooltip="ARI (Autonomic Readiness Index) measures your daily recovery capacity from HRV, sleep quality, resting heart rate, and soreness. Green = train hard. ARI < 55 for 3+ days can trigger an automatic refeed."
          >
            {ari ? (
              <div className="mt-3">
                <div className="flex items-center justify-between mb-3">
                  <span
                    className={`px-2 py-0.5 rounded text-xs font-semibold uppercase ${
                      ari.zone === "green"
                        ? "bg-green-500/20 text-green-400"
                        : ari.zone === "yellow"
                        ? "bg-yellow-500/20 text-yellow-400"
                        : "bg-red-500/20 text-red-400"
                    }`}
                  >
                    {ari.zone} zone
                  </span>
                  <span className="text-3xl font-bold text-jungle-accent">{ari.ari_score}</span>
                </div>

                {/* Fuel gauge bar */}
                <div className="relative h-4 bg-jungle-deeper rounded-full overflow-hidden mb-2">
                  <div className="absolute inset-0 flex pointer-events-none">
                    <div className="flex-[40] border-r border-jungle-border/50" />
                    <div className="flex-[30] border-r border-jungle-border/50" />
                    <div className="flex-[30]" />
                  </div>
                  <div
                    className="h-full rounded-full transition-all"
                    style={{
                      width: `${ari.ari_score}%`,
                      backgroundColor:
                        ari.zone === "green"
                          ? "#4ade80"
                          : ari.zone === "yellow"
                          ? "#eab308"
                          : "#ef4444",
                    }}
                  />
                </div>
                <div className="flex justify-between text-[9px] text-jungle-dim mb-3">
                  <span>Red &lt;40</span>
                  <span>Yellow 40–70</span>
                  <span>Green 70+</span>
                </div>

                {ari.components && (
                  <div className="grid grid-cols-3 gap-2 text-center">
                    {Object.entries(ari.components).map(([k, v]) => (
                      <div key={k} className="bg-jungle-deeper rounded-lg p-2">
                        <p className="text-[10px] text-jungle-dim capitalize">{k}</p>
                        <p className="text-sm font-bold">{Math.round(v)}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <EmptyState label="Submit HRV data during check-in to see readiness" />
            )}
          </ChartCard>
            );

            if (isVizOn("adherence")) bodies.adherence = (
          <ChartCard
            title="Adherence Grid"
            subtitle="12-Week Compliance"
            tooltip="Daily training and nutrition compliance over the last 12 weeks. Darker green = better adherence. Adherence < 85% locks autoregulation adjustments."
          >
            {adherence.length > 0 ? (
              <div className="mt-3">
                <AdherenceHeatmap data={adherence} type="overall" />
              </div>
            ) : (
              <EmptyState label="Log adherence during check-in to see compliance grid" />
            )}
          </ChartCard>
            );

            if (isVizOn("prep_timeline")) bodies.prep_timeline = (
          <ChartCard title="Competition Countdown" subtitle="Prep Timeline">
            {weeksOut !== undefined ? (
              <div className="mt-3 space-y-3">
                {/* Weeks out */}
                <div className="flex items-end gap-2">
                  <span className="text-5xl font-bold text-jungle-accent leading-none">
                    {weeksOut}
                  </span>
                  <span className="text-jungle-muted text-sm pb-1">weeks out</span>
                </div>

                {/* Phase badge */}
                <div className="flex items-center gap-2">
                  <span className={`px-2 py-0.5 rounded text-xs font-semibold uppercase ${phaseColorClass}`}>
                    {currentPhase.replace(/_/g, " ")}
                  </span>
                  {timeline?.competition_date && (
                    <span className="text-[10px] text-jungle-dim">
                      {timeline.competition_date}
                    </span>
                  )}
                </div>

                {/* Progress bar */}
                {totalWeeks > 0 && (
                  <div>
                    <div className="flex justify-between text-[9px] text-jungle-dim mb-1">
                      <span>Now</span>
                      <span>Contest</span>
                    </div>
                    <div className="h-2 bg-jungle-deeper rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full bg-jungle-accent transition-all"
                        style={{
                          width: `${Math.max(0, Math.min(100, ((totalWeeks - (weeksOut ?? 0)) / totalWeeks) * 100))}%`,
                        }}
                      />
                    </div>
                    <div className="text-[9px] text-jungle-dim mt-0.5 text-right">
                      {totalWeeks - (weeksOut ?? 0)} / {totalWeeks} weeks elapsed
                    </div>
                  </div>
                )}

                {/* Phase description */}
                {phaseInfo?.description && (
                  <p className="text-[10px] text-jungle-muted border-t border-jungle-border pt-2">
                    {phaseInfo.description}
                  </p>
                )}

                {/* Nutrition & training cues */}
                <div className="grid grid-cols-2 gap-2">
                  {phaseInfo?.nutrition_cue && (
                    <div className="bg-jungle-deeper rounded-lg p-2">
                      <p className="text-[9px] text-jungle-dim uppercase tracking-wide mb-0.5">Nutrition</p>
                      <p className="text-[10px] text-jungle-muted">{phaseInfo.nutrition_cue}</p>
                    </div>
                  )}
                  {phaseInfo?.training_cue && (
                    <div className="bg-jungle-deeper rounded-lg p-2">
                      <p className="text-[9px] text-jungle-dim uppercase tracking-wide mb-0.5">Training</p>
                      <p className="text-[10px] text-jungle-muted">{phaseInfo.training_cue}</p>
                    </div>
                  )}
                </div>
              </div>
            ) : ppmStatus?.ppm_enabled && ppmReadiness ? (
              <div className="mt-3">
                <TierReadinessCard
                  readiness={ppmReadiness}
                  projection={ppmProjection ?? undefined}
                  currentCycleWeek={ppmStatus.current_cycle_week}
                  totalCycleWeeks={ppmStatus.current_cycle_week && ppmStatus.current_cycle_week > 14 ? 16 : 14}
                  onTransitionToComp={() => router.push("/settings")}
                />
              </div>
            ) : (
              <EmptyState label="Run diagnostics to load prep timeline" />
            )}
          </ChartCard>
            );

            // ── PPM: Improvement Cycle progress ───────────────────────────
            if (isVizOn("cycle_progress") && ppmStatus?.ppm_enabled) bodies.cycle_progress = (
              <ChartCard title="Improvement Cycle" subtitle={`Cycle #${ppmStatus.current_cycle_number}`}>
                <CycleProgressCard
                  cycleNumber={ppmStatus.current_cycle_number}
                  cycleWeek={ppmStatus.current_cycle_week}
                  totalWeeks={ppmStatus.current_cycle_week > 14 ? 16 : 14}
                  subPhase={ppmStatus.current_phase}
                  focusMuscles={ppmStatus.cycle_focus_muscles || []}
                />
              </ChartCard>
            );

            // ── PPM: Tier Readiness (card-sized summary, mirrors prep_timeline) ──
            if (isVizOn("tier_readiness") && ppmStatus?.ppm_enabled && ppmReadiness) bodies.tier_readiness = (
              <ChartCard title="Tier Readiness" subtitle={ppmReadiness.tier.replace(/_/g, " ")}>
                <TierReadinessCard
                  readiness={ppmReadiness}
                  projection={ppmProjection ?? undefined}
                  currentCycleWeek={ppmStatus.current_cycle_week}
                  totalCycleWeeks={ppmStatus.current_cycle_week > 14 ? 16 : 14}
                  onTransitionToComp={() => router.push("/settings")}
                />
              </ChartCard>
            );

            // ── PPM: Arm-Calf-Neck parity (Classic only, surfaced via tape) ──
            if (isVizOn("parity_check") && ppmStatus?.ppm_enabled) bodies.parity_check = (
              <ChartCard title="Arm-Calf-Neck Parity" subtitle="Reeves classical standard">
                <ParityCheckCard
                  arm_cm={ppmTape?.bicep ?? null}
                  calf_cm={ppmTape?.calf ?? null}
                  neck_cm={ppmTape?.neck ?? null}
                />
              </ChartCard>
            );

            // ── PPM: Chest : Waist ratio ──
            if (isVizOn("chest_waist") && ppmStatus?.ppm_enabled) bodies.chest_waist = (
              <ChartCard title="Chest : Waist" subtitle="V-taper ratio">
                <ChestWaistCard chest_cm={ppmTape?.chest ?? null} waist_cm={ppmTape?.waist ?? null} />
              </ChartCard>
            );

            // ── PPM: Carb cycle (high/medium/low days) ──
            if (isVizOn("carb_cycle") && ppmStatus?.ppm_enabled && carbCycle) bodies.carb_cycle = (
              <ChartCard title="Carb Cycle" subtitle="High / Medium / Low days">
                <CarbCycleCard
                  high_day={carbCycle.high_day}
                  medium_day={carbCycle.medium_day}
                  low_day={carbCycle.low_day}
                  days_per_week={carbCycle.days_per_week}
                />
              </ChartCard>
            );

            // ── Conditioning style — Classic only ──
            if (isVizOn("conditioning_style") && ppmStatus?.ppm_enabled) bodies.conditioning_style = (
              <ChartCard title="Conditioning Style" subtitle="Classic judging modifier">
                <ConditioningStyleCard
                  style={conditioningStyle}
                  onChange={setConditioningStyle}
                />
              </ChartCard>
            );

            // ── Natural ceiling (honesty) ──
            if (isVizOn("natural_ceiling") && ppmStatus?.ppm_enabled && ppmAttain) bodies.natural_ceiling = (
              <ChartCard title="Natural Ceiling" subtitle="Casey Butt prediction">
                <NaturalCeilingCard
                  predictedStageKg={ppmAttain.predicted_natural_max_stage_kg}
                  tierRequiredKg={ppmAttain.tier_required_stage_kg}
                  divisionCapKg={divisionCapKg}
                  attainable={ppmAttain.overall_attainable}
                  ffmiPredicted={ppmAttain.predicted_natural_ffmi}
                  ffmiRequired={ppmAttain.tier_ffmi_requirement}
                />
              </ChartCard>
            );

            if (isVizOn("strength_progression")) bodies.strength_progression = (
            <ChartCard
              title="Strength Progression"
              subtitle="e1RM of Main Lifts"
              tooltip="Estimated 1-rep max over time for the big compounds (squat, bench, deadlift, OHP). Pulled from StrengthLog entries or derived via the Epley formula from completed sets."
            >
              <StrengthProgressionChart series={strengthSeries} useLbs={useLbs} />
            </ChartCard>
            );

            if (isVizOn("body_weight_trend")) bodies.body_weight_trend = (
            <ChartCard
              title="Body Weight Trend"
              subtitle="7-day Rolling Average"
              tooltip="Daily body weight with a 7-day rolling average overlay. Background tint reflects your current training phase."
            >
              <BodyWeightTrendChart
                data={recentWeights}
                useLbs={useLbs}
                phase={phaseRec?.recommended_phase ?? null}
              />
            </ChartCard>
            );

            if (isVizOn("macro_adherence")) bodies.macro_adherence = (
            <ChartCard
              title="Macro Adherence"
              subtitle="30-Day Nutrition Hit Rate"
              tooltip="Daily nutrition adherence over the last 30 days. Each bar is the average of protein/carbs/fat hit rate for that day. The gold line is your 30-day average."
            >
              <MacroAdherenceChart data={adherence} />
            </ChartCard>
            );

            if (isVizOn("weekly_volume")) bodies.weekly_volume = (
            <ChartCard
              title="Weekly Volume"
              subtitle="Sets vs MEV/MAV/MRV"
              tooltip="Working sets per muscle for the current week, plotted against Renaissance Periodization volume landmarks. Red = under MEV, gold = in productive zone, green = high productive, orange = over MRV."
            >
              <WeeklyVolumeChart rows={weeklyVolume} />
            </ChartCard>
            );

            if (isVizOn("recovery_trend")) bodies.recovery_trend = (
            <ChartCard
              title="Recovery Trend"
              subtitle="ARI Composite · 30 Days"
              tooltip="Daily Autonomic Readiness Index (HRV + sleep + soreness) over the last 30 days. Green zone = ready to train hard, yellow = caution, red = under-recovered."
            >
              <RecoveryTrendChart data={recoveryTrend} />
            </ChartCard>
            );

            if (isVizOn("mesocycle_progress") && program) bodies.mesocycle_progress = (
              <ChartCard
                title="Mesocycle Progress"
                subtitle={`Week ${program.current_week} of ${program.mesocycle_weeks}`}
                tooltip="Where you are in the current 6-week mesocycle. Weeks 1-2 MEV, 3-4 MAV, week 5 MRV (peak overload), week 6 deload. The ring shows your progress through the block; the deload is when you pull back and resupercompensate."
              >
                {(() => {
                  const totalWeeks = program.mesocycle_weeks || 6;
                  const week = program.current_week || 1;
                  const pct = Math.min(100, (week / totalWeeks) * 100);
                  const weeksToDeload = Math.max(0, totalWeeks - week);
                  const phase = week <= 2 ? "MEV" : week <= 4 ? "MAV" : week === 5 ? "MRV" : "DELOAD";
                  const phaseColor = phase === "MEV" ? "#a3e635" : phase === "MAV" ? "#c8a84e" : phase === "MRV" ? "#f97316" : "#3b82f6";
                  return (
                    <div className="flex items-center gap-4 mt-2">
                      <div className="relative w-20 h-20 shrink-0">
                        <svg viewBox="0 0 100 100" className="w-20 h-20 -rotate-90">
                          <circle cx="50" cy="50" r="42" fill="none" stroke="#1a3328" strokeWidth="8" />
                          <circle cx="50" cy="50" r="42" fill="none" stroke={phaseColor} strokeWidth="8" strokeLinecap="round" strokeDasharray={`${(pct / 100) * 263.9} 263.9`} />
                        </svg>
                        <div className="absolute inset-0 flex flex-col items-center justify-center">
                          <span className="text-xl font-bold text-jungle-text leading-none">{week}</span>
                          <span className="text-[9px] text-jungle-dim">of {totalWeeks}</span>
                        </div>
                      </div>
                      <div className="flex-1 space-y-1.5 min-w-0">
                        <div>
                          <span className="text-[9px] text-jungle-dim uppercase tracking-wider">Phase</span>
                          <div className="flex items-center gap-2">
                            <span className="px-2 py-0.5 rounded text-xs font-bold" style={{ backgroundColor: `${phaseColor}20`, color: phaseColor }}>{phase}</span>
                          </div>
                        </div>
                        <div>
                          <span className="text-[9px] text-jungle-dim uppercase tracking-wider">Deload</span>
                          <p className="text-xs text-jungle-text">
                            {weeksToDeload === 0 ? "This week" : `in ${weeksToDeload} week${weeksToDeload === 1 ? "" : "s"}`}
                          </p>
                        </div>
                        <div>
                          <span className="text-[9px] text-jungle-dim uppercase tracking-wider">Split</span>
                          <p className="text-xs text-jungle-muted capitalize">{program.split_type.replace(/_/g, " ")}</p>
                        </div>
                      </div>
                    </div>
                  );
                })()}
              </ChartCard>
            );

            if (isVizOn("energy_availability") && todayMacros) bodies.energy_availability = (
              <ChartCard
                title="Energy Availability"
                subtitle="kcal / kg FFM / day"
                tooltip="Energy Availability = (intake − exercise kcal) / fat-free mass. The RED-S (Relative Energy Deficiency in Sport) threshold is 30 kcal/kg FFM. Below 25 is critical — hormones, bone density and immunity suffer."
              >
                {(() => {
                  const ea = (todayMacros as { energy_availability?: { ea_kcal_per_kg_ffm?: number; status?: string; message?: string } })?.energy_availability;
                  if (!ea || typeof ea.ea_kcal_per_kg_ffm !== "number") {
                    return <EmptyState label="Need body composition + active prescription to compute EA" />;
                  }
                  const value = ea.ea_kcal_per_kg_ffm;
                  const status = ea.status || "unknown";
                  const statusColor = status === "ok" ? "#22c55e" : status === "warning" ? "#f97316" : "#ef4444";
                  const pct = Math.max(0, Math.min(100, (value / 55) * 100)); // scale to 55 as "max healthy"
                  return (
                    <div className="mt-3 space-y-3">
                      <div className="text-center">
                        <p className="text-3xl font-bold leading-none" style={{ color: statusColor }}>
                          {value.toFixed(0)}
                        </p>
                        <p className="text-[9px] text-jungle-dim uppercase tracking-wider mt-1">kcal/kg FFM</p>
                      </div>
                      {/* Gauge bar with RED-S threshold markers */}
                      <div className="relative">
                        <div className="h-3 bg-jungle-deeper rounded-full overflow-hidden">
                          <div
                            className="h-full rounded-full transition-all"
                            style={{ width: `${pct}%`, backgroundColor: statusColor }}
                          />
                        </div>
                        {/* 25 and 30 threshold lines */}
                        <div className="absolute top-0 bottom-0 w-px bg-red-500/70" style={{ left: `${(25 / 55) * 100}%` }} />
                        <div className="absolute top-0 bottom-0 w-px bg-yellow-500/70" style={{ left: `${(30 / 55) * 100}%` }} />
                        <div className="flex justify-between text-[9px] text-jungle-dim mt-1">
                          <span>0</span>
                          <span className="text-red-400">25</span>
                          <span className="text-yellow-400">30</span>
                          <span>55</span>
                        </div>
                      </div>
                      <p className="text-[10px] text-jungle-muted leading-snug">
                        {ea.message || "Track your intake to get a live EA reading."}
                      </p>
                    </div>
                  );
                })()}
              </ChartCard>
            );

            if (isVizOn("training_time")) bodies.training_time = (
              <ChartCard
                title="Weekly Training Time"
                subtitle="This week's gym budget"
                tooltip="How many hours you're spending in the gym this week. Pro bodybuilders typically train 5-6 days × 60-90 min + 3-5 cardio sessions. This card helps you see the total weekly time commitment and plan around real life."
              >
                {weeklyVolume && weeklyVolume.length > 0 ? (
                  <div className="mt-3 space-y-2">
                    {(() => {
                      // Rough estimate: working sets × 2.5 min each + cardio sessions × duration
                      const totalWorkingSets = weeklyVolume.reduce((a, r) => a + (r.sets || 0), 0);
                      const liftingHours = (totalWorkingSets * 2.5) / 60;
                      const cardioHours = (cardioPrescription?.summary?.cardio_sessions || 0) *
                        (cardioPrescription?.cardio?.duration_min || 30) / 60;
                      const totalHours = liftingHours + cardioHours;
                      const liftingPct = totalHours > 0 ? (liftingHours / totalHours) * 100 : 0;
                      return (
                        <>
                          <div className="text-center">
                            <p className="text-3xl font-bold text-jungle-text leading-none">{totalHours.toFixed(1)}h</p>
                            <p className="text-[9px] text-jungle-dim uppercase tracking-wider mt-1">total this week</p>
                          </div>
                          <div className="space-y-1.5">
                            <div>
                              <div className="flex justify-between text-[10px] mb-0.5">
                                <span className="text-jungle-accent">Lifting</span>
                                <span className="text-jungle-text font-mono">{liftingHours.toFixed(1)}h · {totalWorkingSets} sets</span>
                              </div>
                              <div className="h-2 bg-jungle-deeper rounded-full overflow-hidden">
                                <div className="h-full bg-jungle-accent" style={{ width: `${liftingPct}%` }} />
                              </div>
                            </div>
                            {cardioHours > 0 && (
                              <div>
                                <div className="flex justify-between text-[10px] mb-0.5">
                                  <span className="text-blue-400">Cardio</span>
                                  <span className="text-jungle-text font-mono">{cardioHours.toFixed(1)}h · {cardioPrescription?.summary?.cardio_sessions}×/wk</span>
                                </div>
                                <div className="h-2 bg-jungle-deeper rounded-full overflow-hidden">
                                  <div className="h-full bg-blue-400" style={{ width: `${100 - liftingPct}%` }} />
                                </div>
                              </div>
                            )}
                          </div>
                          <p className="text-[10px] text-jungle-dim mt-2">
                            {totalHours < 5 ? "Low-volume week — good for recovery." :
                             totalHours < 10 ? "Standard pro bodybuilder window." :
                             totalHours < 14 ? "High-volume week — monitor recovery." :
                             "Very high — make sure sleep + food match the work."}
                          </p>
                        </>
                      );
                    })()}
                  </div>
                ) : (
                  <EmptyState label="Complete a session to populate weekly time" />
                )}
              </ChartCard>
            );

            // ─── New widgets ─────────────────────────────────────────────

            if (isVizOn("tomorrow_split")) bodies.tomorrow_split = (
              <ChartCard
                title="Tomorrow's Split"
                subtitle="What's on deck"
                tooltip="Your scheduled training split for tomorrow. A quick glance at what to expect when you walk into the gym."
              >
                {(() => {
                  const tmw = new Date();
                  tmw.setDate(tmw.getDate() + 1);
                  const weekday = tmw.toLocaleDateString(undefined, { weekday: "long" });
                  const dateLabel = tmw.toLocaleDateString(undefined, { month: "short", day: "numeric" });
                  if (tomorrowSession) {
                    return (
                      <div className="mt-3">
                        <p className="text-[10px] text-jungle-dim uppercase tracking-wider">{weekday} · {dateLabel}</p>
                        <p className="text-2xl font-bold text-jungle-accent capitalize mt-1">
                          {tomorrowSession.session_type.replace(/_/g, " ")} Day
                        </p>
                        <p className="text-[11px] text-jungle-muted mt-1">
                          {new Set(tomorrowSession.sets.filter((s) => !s.is_warmup).map((s) => s.exercise_name)).size} exercises queued
                        </p>
                      </div>
                    );
                  }
                  return (
                    <div className="mt-3">
                      <p className="text-[10px] text-jungle-dim uppercase tracking-wider">{weekday} · {dateLabel}</p>
                      <p className="text-2xl font-bold text-jungle-muted mt-1">Rest Day 💤</p>
                      <p className="text-[11px] text-jungle-dim mt-1">No session scheduled — recover hard.</p>
                    </div>
                  );
                })()}
              </ChartCard>
            );

            if (isVizOn("workout_tomorrow")) bodies.workout_tomorrow = (
              <ChartCard
                title="Tomorrow's Workout"
                subtitle="Exercise preview"
                tooltip="The exact exercises scheduled for tomorrow's session with set counts. Prep your playlist, pre-load the warmups, walk in ready."
              >
                {tomorrowSession ? (() => {
                  const exerciseSets: Record<string, number> = {};
                  for (const s of tomorrowSession.sets) {
                    if (s.is_warmup) continue;
                    exerciseSets[s.exercise_name] = (exerciseSets[s.exercise_name] || 0) + 1;
                  }
                  const entries = Object.entries(exerciseSets);
                  const estMin = tomorrowSession.workout_window?.est_minutes;
                  return (
                    <div className="mt-3">
                      <div className="space-y-1">
                        {entries.map(([name, sets]) => (
                          <div key={name} className="flex justify-between text-[11px] py-1 border-b border-jungle-border/30">
                            <span className="text-jungle-muted truncate pr-2">{name}</span>
                            <span className="text-jungle-accent whitespace-nowrap">{sets} × working</span>
                          </div>
                        ))}
                      </div>
                      {estMin && (
                        <p className="text-[10px] text-jungle-dim mt-2 text-right">~{estMin} min</p>
                      )}
                    </div>
                  );
                })() : (
                  <EmptyState label="Rest day tomorrow — recovery is a weapon" />
                )}
              </ChartCard>
            );

            if (isVizOn("sleep_quality_week")) bodies.sleep_quality_week = (
              <ChartCard
                title="Sleep Quality Week"
                subtitle="7-day recovery foundation"
                tooltip="Nightly sleep quality (1-10) and total hours for the last 7 days. Sleep is where hypertrophy actually happens — growth hormone peaks in deep sleep, and sub-6h nights blunt MPS."
              >
                {sleepWeek ? (
                  <div className="mt-3">
                    <div className="flex items-end justify-between gap-1 h-24">
                      {sleepWeek.days.map((d) => {
                        const qual = d.quality ?? 0;
                        const height = qual > 0 ? (qual / 10) * 100 : 0;
                        const color = qual >= 7 ? "#4ade80" : qual >= 5 ? "#eab308" : qual > 0 ? "#ef4444" : "transparent";
                        return (
                          <div key={d.date} className="flex-1 flex flex-col items-center">
                            <div className="w-full bg-jungle-deeper rounded-sm flex items-end h-20 overflow-hidden">
                              {qual > 0 ? (
                                <div className="w-full rounded-sm transition-all" style={{ height: `${height}%`, backgroundColor: color }} />
                              ) : (
                                <div className="w-full h-full flex items-end justify-center">
                                  <span className="text-[8px] text-jungle-dim/50 mb-1">—</span>
                                </div>
                              )}
                            </div>
                            <span className="text-[9px] text-jungle-muted mt-1">{d.weekday[0]}</span>
                            <span className="text-[9px] text-jungle-dim">{d.hours ? `${d.hours.toFixed(1)}h` : "—"}</span>
                          </div>
                        );
                      })}
                    </div>
                    {sleepWeek.logged_count > 0 ? (
                      <p className="text-[10px] text-jungle-dim mt-3 text-center">
                        7-day avg: <span className="text-jungle-accent">{sleepWeek.avg_quality ?? "—"}/10</span> · {sleepWeek.avg_hours ?? "—"}h per night
                      </p>
                    ) : (
                      <p className="text-[10px] text-jungle-dim mt-3 text-center">
                        Log sleep during check-in to build a recovery baseline
                      </p>
                    )}
                  </div>
                ) : (
                  <EmptyState label="Log sleep during check-in to see the week" />
                )}
              </ChartCard>
            );

            if (isVizOn("daily_quote")) bodies.daily_quote = (
              <ChartCard
                title="Daily Fire"
                subtitle="Mental fuel"
                tooltip="A fresh quote every day. Discipline, pain, repetition — the reminders that build a physique you're proud of."
              >
                <div className="mt-3">
                  <p className="text-[13px] text-jungle-text italic leading-relaxed">
                    &ldquo;{quote.text}&rdquo;
                  </p>
                  <p className="text-[11px] text-jungle-accent mt-3 text-right">— {quote.author}</p>
                </div>
              </ChartCard>
            );

            if (isVizOn("goal_photo")) bodies.goal_photo = (
              <ChartCard
                title="Your Goal"
                subtitle="The physique you're building"
                tooltip="Your north star. Upload a photo of the physique you're chasing and the verbal goal behind it. Every rep is aimed at this."
              >
                {editingGoal ? (
                  <div className="mt-3 space-y-2">
                    <input
                      type="text"
                      value={goalDraft}
                      onChange={(e) => setGoalDraft(e.target.value)}
                      placeholder="Build Phil Heath's back thickness"
                      className="input-field text-xs w-full"
                      maxLength={120}
                    />
                    <input
                      type="file"
                      accept="image/*"
                      onChange={handleGoalPhotoChange}
                      className="text-[10px] text-jungle-muted"
                    />
                    {goalPhotoDraft && (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={goalPhotoDraft} alt="preview" className="rounded-lg max-h-[160px] mx-auto object-contain" />
                    )}
                    <div className="flex gap-2 pt-1">
                      <button
                        onClick={saveGoal}
                        disabled={goalSaving}
                        className="btn-primary text-xs px-3 py-1 disabled:opacity-50"
                      >
                        {goalSaving ? "Saving…" : "Save"}
                      </button>
                      <button
                        onClick={() => setEditingGoal(false)}
                        className="btn-secondary text-xs px-3 py-1"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                ) : aspiration?.aspiration_photo_url ? (
                  <div className="mt-3 relative">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={aspiration.aspiration_photo_url}
                      alt="aspiration"
                      className="rounded-lg max-h-[260px] w-full object-contain bg-jungle-deeper"
                    />
                    {aspiration.goal_text && (
                      <p className="text-[12px] text-jungle-muted italic text-center mt-2">
                        &ldquo;{aspiration.goal_text}&rdquo;
                      </p>
                    )}
                    <button
                      onClick={openGoalEditor}
                      className="absolute top-2 right-2 px-2 py-1 bg-jungle-deeper/80 border border-jungle-border rounded-md text-[10px] text-jungle-dim hover:text-jungle-accent"
                    >
                      ✎ Edit
                    </button>
                  </div>
                ) : (
                  <div className="mt-3 flex flex-col items-center justify-center h-36 border-2 border-dashed border-jungle-border rounded-lg">
                    <p className="text-[11px] text-jungle-dim mb-3 text-center">No goal set yet</p>
                    <button onClick={openGoalEditor} className="btn-primary text-xs px-3 py-1">
                      Set your goal
                    </button>
                  </div>
                )}
              </ChartCard>
            );

            return cardOrder
              .filter((k) => bodies[k])
              .map((k) => (
                <SortableCard
                  key={k}
                  id={k}
                  label={LABEL_OF[k] || k}
                  editMode={editMode}
                  onHide={() => hideCard(k)}
                >
                  {bodies[k]}
                </SortableCard>
              ));
          })()}
        </div>
          </SortableContext>
        </DndContext>

        {/* Quick Log Weight — outside the sortable grid */}
        <div className="mt-4 grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 sm:gap-6">
          {/* Quick Log Weight */}
          <div className={`card transition-all duration-300 ${quickLogged ? "animate-pulse" : ""}`}>
            <h3 className="text-xs font-semibold text-jungle-muted uppercase tracking-wider mb-3">
              Quick Log Weight
            </h3>
            <div className="flex gap-2 items-end mb-3">
              <div className="flex-1">
                <label className="label-field">Weight ({unit})</label>
                <input
                  type="number"
                  step="0.1"
                  min="30"
                  max="250"
                  value={quickWeight}
                  onChange={(e) => setQuickWeight(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleQuickLog()}
                  className="input-field mt-1"
                  placeholder="e.g. 90.5"
                />
              </div>
              <button
                onClick={handleQuickLog}
                disabled={quickLogging || !quickWeight}
                className="btn-primary disabled:opacity-50 whitespace-nowrap px-4 py-2 mb-0.5"
              >
                {quickLogging ? "..." : "Log"}
              </button>
            </div>

            {quickLogged && (
              <p className="text-xs text-green-400 bg-green-500/10 rounded px-2 py-1 mb-2">
                Weight logged!
              </p>
            )}

            {/* Sparkline */}
            {sparklinePath ? (
              <div className="mt-1">
                <div className="flex items-center justify-between text-[10px] text-jungle-dim mb-1">
                  <span>Last {sparklineEntries.length} entries</span>
                  <span className="text-jungle-accent font-medium">
                    {wt(sparklineEntries[sparklineEntries.length - 1]?.weight_kg)}{unit}
                  </span>
                </div>
                <svg
                  viewBox="0 0 80 24"
                  width="100%"
                  height="28"
                  preserveAspectRatio="none"
                  className="overflow-visible"
                >
                  <path
                    d={sparklinePath}
                    fill="none"
                    stroke="#c8a84e"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                  {(() => {
                    const values = sparklineEntries.map((e) => e.weight_kg);
                    const min = Math.min(...values);
                    const max = Math.max(...values);
                    const range = max - min || 1;
                    const lastX = 80;
                    const lastY = 24 - ((values[values.length - 1] - min) / range) * 24;
                    return (
                      <circle cx={lastX} cy={lastY} r="2" fill="#c8a84e" />
                    );
                  })()}
                </svg>
              </div>
            ) : (
              <p className="text-[10px] text-jungle-dim mt-1">
                Log weights to see trend sparkline
              </p>
            )}
          </div>

          {/* Quick Actions */}
          <div className="card">
            <h3 className="text-xs font-semibold text-jungle-muted uppercase tracking-wider mb-4">
              Quick Actions
            </h3>
            <div className="space-y-2">
              <ActionButton href="/checkin" label="Daily Check-In" icon="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
              <ActionButton href="/training" label="Today's Workout" icon="M13 10V3L4 14h7v7l9-11h-7z" />
              <ActionButton href="/nutrition" label="Log Nutrition" icon="M3 3h2l.4 2M7 13h10l4-8H5.4M7 13L5.4 5M7 13l-2.293 2.293c-.63.63-.184 1.707.707 1.707H17m0 0a2 2 0 100 4 2 2 0 000-4zm-8 2a2 2 0 100 4 2 2 0 000-4z" />
              <ActionButton href="/progress" label="Progress History" icon="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              <ActionButton href="/training/exercises" label="Exercise Library" icon="M4 6h16M4 10h16M4 14h16M4 18h16" />
              <ActionButton href="/settings" label="Settings" icon="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </div>
          </div>
        </div>
      </main>

      {/* Mobile bottom nav */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 bg-jungle-deeper/95 backdrop-blur-md border-t border-jungle-border z-50">
        <div className="flex justify-around py-2">
          <MobileNavItem href="/dashboard" label="Home" active icon="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
          <MobileNavItem href="/checkin" label="Check-in" icon="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
          <MobileNavItem href="/training" label="Train" icon="M13 10V3L4 14h7v7l9-11h-7z" />
          <MobileNavItem href="/nutrition" label="Nutrition" icon="M3 3h2l.4 2M7 13h10l4-8H5.4M7 13L5.4 5M7 13l-2.293 2.293c-.63.63-.184 1.707.707 1.707H17" />
        </div>
      </nav>

      <div className="md:hidden h-16" />
    </div>
  );
}

const ChartCard = memo(function ChartCard({
  title,
  subtitle,
  tooltip,
  children,
}: {
  title: string;
  subtitle: string;
  tooltip?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="card">
      <div className="flex items-baseline justify-between mb-1">
        <h3 className="text-xs font-semibold text-jungle-muted uppercase tracking-wider flex items-center">
          {title}
          {tooltip && <InfoTooltip text={tooltip} />}
        </h3>
        <span className="text-[10px] text-jungle-dim">{subtitle}</span>
      </div>
      {children}
    </div>
  );
});

/** Convert snake_case site keys to "Title Case" labels */
function siteLabel(site: string): string {
  return site.split("_").map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(" ");
}

function EmptyState({ label, action }: { label: string; action?: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center h-36 text-jungle-dim text-xs border border-dashed border-jungle-border rounded-lg mt-3 px-4 text-center">
      <svg className="w-8 h-8 text-jungle-border mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
      </svg>
      {label}
      {action}
    </div>
  );
}

function ActionButton({ href, label, icon }: { href: string; label: string; icon: string }) {
  return (
    <a
      href={href}
      className="flex items-center gap-3 w-full py-2.5 px-3 bg-jungle-deeper border border-jungle-border hover:border-jungle-accent rounded-lg text-sm transition-colors"
    >
      <svg className="w-4 h-4 text-jungle-accent shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={icon} />
      </svg>
      <span>{label}</span>
    </a>
  );
}

function MobileNavItem({ href, label, icon, active = false }: { href: string; label: string; icon: string; active?: boolean }) {
  return (
    <a href={href} className={`flex flex-col items-center gap-0.5 px-3 py-1 ${active ? "text-jungle-accent" : "text-jungle-dim"}`}>
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={icon} />
      </svg>
      <span className="text-[10px]">{label}</span>
    </a>
  );
}
