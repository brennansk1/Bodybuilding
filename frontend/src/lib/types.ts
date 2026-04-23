export interface User {
  id: string;
  email: string;
  username: string;
  display_name?: string;
  onboarding_complete: boolean;
  created_at: string;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface UserProfile {
  id: string;
  user_id: string;
  height_cm: number;
  division: Division;
  competition_date?: string;
  training_experience_years: number;
  sex: "male" | "female";
  // Perpetual Progression Mode fields
  ppm_enabled?: boolean;
  target_tier?: CompetitiveTier;
  training_status?: TrainingStatus;
  current_cycle_number?: number;
  current_cycle_start_date?: string;
  current_cycle_week?: number;
  cycle_focus_muscles?: string[];
  // V2.S4 — training-age correction factors (nullable — engine applies priors)
  training_consistency_factor?: number | null;
  training_intensity_factor?: number | null;
  training_programming_factor?: number | null;
  // V3 — manual overrides + tier tracking
  nutrition_mode_override?: "bulk" | "cut" | "maintain" | null;
  structural_priority_muscles?: string[] | null;
  current_achieved_tier?: CompetitiveTier | null;
}

// V3 — Tier timing projection across adherence scenarios
export interface TierProjection {
  target_tier: CompetitiveTier;
  target_tier_name: string;
  projections: {
    high:   { years: number; cycles: number; limiting_dimension: string; adherence_product: number };
    medium: { years: number; cycles: number; limiting_dimension: string; adherence_product: number };
    low:    { years: number; cycles: number; limiting_dimension: string; adherence_product: number };
  };
}

// V3 — Lever sensitivity card
export interface SensitivityLever {
  rank: number;
  lever: string;
  label: string;
  impact: "very_high" | "high" | "medium" | "low";
  reason: string;
  action: string;
}
export interface SensitivityResponse {
  levers: SensitivityLever[];
  coaching_summary: string;
}

// V3 — Weight trend
export interface WeightTrendResponse {
  points: { date: string; weight_kg: number }[];
  smoothed_7d: (number | null)[];
  smoothed_14d: (number | null)[];
  weekly_rate_kg: number | null;
  weekly_rate_pct: number | null;
  direction: "cutting" | "bulking" | "steady" | "unknown";
  in_target_band: boolean | null;
}

// V3 — Muscle-site timeline
export interface MuscleTimelineResponse {
  site: string;
  series: { date: string; value_cm: number }[];
  acceleration_windows: { start_date: string; end_date: string; rate_vs_baseline: number }[];
}

// V3 — Prep Replay
export interface CycleSummary {
  cycle_number: number;
  checkpoint_date: string | null;
  body_weight_kg: number | null;
  bf_pct: number | null;
  hqi_score: number | null;
  readiness_state: string;
  limiting_factor: string | null;
  cycle_focus: string | null;
}
export interface CycleDetail extends CycleSummary {
  readiness: {
    state: string;
    hqi_score: number | null;
    ffmi: number | null;
    bf_pct: number | null;
    weight_cap_pct: number | null;
    shoulder_waist_ratio: number | null;
    chest_waist_ratio: number | null;
    arm_calf_neck_parity: number | null;
    illusion_xframe: number | null;
    conditioning_pct: number | null;
  };
  measurements: Record<string, unknown> | null;
  macros_snapshot: Record<string, unknown> | null;
  training_snapshot: Record<string, unknown> | null;
  volume_snapshot: Record<string, unknown> | null;
  notes: string | null;
}

export type CompetitiveTier = 1 | 2 | 3 | 4 | 5;
export type TrainingStatus = "natural" | "enhanced";
export type ReadinessState =
  | "not_ready"
  | "developing"
  | "approaching"
  | "stage_ready";

export interface TierMetric {
  current: number;
  target: number;
  met: boolean;
  pct_progress: number;
}

export interface MassGap {
  site: string;
  current_lean_cm: number;
  ideal_lean_cm: number;
  gap_cm: number;
  pct_of_ideal: number;
}

export interface TierReadiness {
  state: ReadinessState;
  tier: string;
  tier_value: number;
  metrics_met: number;
  metrics_total: number;
  pct_met: number;
  per_metric: Record<string, TierMetric>;
  limiting_factor: string;
  limiting_detail: TierMetric;
  mass_gaps?: MassGap[];
}

export interface PPMCheckpoint {
  id: string;
  cycle_number: number;
  checkpoint_date: string;
  body_weight_kg: number | null;
  bf_pct: number | null;
  ffmi: number | null;
  shoulder_waist_ratio: number | null;
  chest_waist_ratio: number | null;
  arm_calf_neck_parity: number | null;
  hqi_score: number | null;
  weight_cap_pct: number | null;
  readiness_state: ReadinessState;
  limiting_factor: string | null;
  cycle_focus: string | null;
  // V2.S9 — populated on post-V2 checkpoints only; null for historical rows
  illusion_xframe?: number | null;
  conditioning_pct?: number | null;
}

export interface TierProjection {
  estimated_cycles: number;
  estimated_months: number;
  estimated_years: number;
  limiting_dimension: "mass" | "proportions";
  mass_cycles_needed: number;
  proportion_cycles_needed: number;
  annual_lbm_projection_kg: number;
  per_cycle_lbm_kg: number;
  // V2.S4 additions
  t_effective_years?: number;
  muscle_fraction_used?: number;
  ceiling_lbm_kg_used?: number;
}

export interface FFMIBand {
  band: string;
  p_natural: number;
  ffmi: number;
}

export interface CeilingEnvelope {
  model_estimates: Record<string, number | Record<string, number | string>>;
  envelope_stage_kg: {
    pessimistic: number;
    median: number;
    ambitious: number;
  };
  effective_ceiling_stage_kg: number;
  division: string;
  model_note: string;
}

export interface NaturalAttainability {
  predicted_natural_max_stage_kg: number;
  predicted_natural_max_lbm_kg: number;
  tier_required_stage_kg: number;
  gap_kg: number;
  weight_attainable: boolean;
  predicted_natural_ffmi: number;
  ffmi_band?: FFMIBand;
  tier_ffmi_requirement: number;
  ffmi_attainable: boolean;
  overall_attainable: boolean;
  tier: string;
  tier_value: number;
  recommendation: string;
  ceiling_envelope?: CeilingEnvelope;
}

export type Division =
  | "mens_open"
  | "classic_physique"
  | "mens_physique"
  | "womens_figure"
  | "womens_bikini"
  | "womens_physique";

export interface HealthCheck {
  status: string;
  version: string;
  system: string;
}
