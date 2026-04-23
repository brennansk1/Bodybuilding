# Viltrum — Database Schema

Every SQLAlchemy model in `backend/app/models/`, grouped by domain.
Relationships flow from `User`, which owns everything via `cascade=all,
delete-orphan` on its children.

Migration management: Alembic, `backend/alembic/` (run `alembic upgrade
head` — see [`DEPLOYMENT.md § 7`](./DEPLOYMENT.md)).

---

## 1. User & auth — `models/user.py`

### `users`
Primary account record.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `email` | str(255) | unique, indexed |
| `username` | str(100) | unique, indexed |
| `hashed_password` | str(255) | bcrypt |
| `onboarding_complete` | bool | gates `/dashboard` until true |
| `is_active` | bool | |
| `created_at`, `updated_at` | tz-aware |

Relationships: `profile`, `body_weight_logs`, `tape_measurements`,
`skinfold_measurements`, `strength_baselines`, `strength_logs`,
`lcsa_logs`, `pds_logs`, `hqi_logs`, `hrv_logs`, `ari_logs`,
`training_programs`, `nutrition_prescriptions`, `weekly_checkins`.

### `healthkit_api_keys`
Long-lived per-device ingest keys for `POST /checkin/daily/healthkit`.
Stored as SHA-256 digests — never plaintext after creation.

| Column | Notes |
|---|---|
| `api_key_hash` | unique |
| `key_prefix` | first 6 chars of plaintext (for display) |
| `label` | e.g. "iPhone Shortcut" |
| `last_used_at`, `revoked_at` | lifecycle |

---

## 2. Profile — `models/profile.py`

### `user_profiles`

The settings-backing record. Every field here is exposed somewhere in the
Settings UI or consumed by an engine. 1:1 with `users`.

**Core identity:**

| Column | Type | Driven by | Used for |
|---|---|---|---|
| `sex` | str(10) | onboarding | BF formulas, stage-BF target |
| `age` | int | onboarding | Mifflin-St Jeor |
| `height_cm` | float | onboarding | division proportions, weight cap, LCSA |
| `division` | str(30) | settings | aesthetic vector, ceiling factors, visibility weights |
| `training_experience_years` | int | settings | trajectory `k`, MEV/MAV/MRV scaling |
| `training_status` | str(16) | settings | `natural` / `enhanced`. Scales volume landmarks, tier gate year reqs |

**Structural / genetic anchors:**

| Column | Notes |
|---|---|
| `wrist_circumference_cm` | Casey-Butt input |
| `ankle_circumference_cm` | Casey-Butt input |
| `manual_body_fat_pct` | Override when no skinfold data |

**Training config:**

| Column | Notes |
|---|---|
| `available_equipment` | JSONB list — filters exercise selection |
| `disliked_exercises` | JSONB list — exclusion filter |
| `injury_history` | JSONB list — contraindications filter |
| `training_start_time` / `training_end_time` / `training_time_anchor` | Window anchors; drives "tomorrow's workout" time display |
| `training_duration_min` | Cap for session construction |
| `days_per_week` | Split-designer input (2–7) |
| `program_start_date` | Anchors mesocycle week numbering |

**Training-age factors (V2 Sprint 4 — discount chronological years):**

| Column | Notes |
|---|---|
| `training_consistency_factor` | 0.5–1.0 multiplier (nullable; engine applies priors when null) |
| `training_intensity_factor` | 0.5–1.0 |
| `training_programming_factor` | 0.5–1.0 |

Used in `readiness.estimate_cycles_to_tier` to scale the effective `k` in
the logistic LBM-gain curve. See [`COMPETITIVE_TIERS.md § 6`](./COMPETITIVE_TIERS.md).

**Cycle tracking (female athletes):**

| Column | Notes |
|---|---|
| `cycle_tracking_enabled` | bool |
| `cycle_start_date` | Anchor for luteal-phase detection (water-retention flag) |

**Competition / PPM (mutually exclusive):**

| Column | Notes |
|---|---|
| `competition_date` | Set when PPM off; drives phase timeline |
| `ppm_enabled` | Perpetual Progression Mode on/off |
| `target_tier` | 1–5 (see `CompetitiveTier` enum) |
| `current_achieved_tier` | **V3** — written at each PPM checkpoint; `TierBadge` reads this |
| `current_cycle_number` | Starts at 0; incremented on `/ppm/start-cycle` |
| `current_cycle_start_date` | Anchor for week arithmetic |
| `current_cycle_week` | 1..14 (or 1..16 with mini-cut prepend) |
| `cycle_focus_muscles` | JSONB — limiting muscles selected at cycle start |

Validated at `/onboarding/profile` layer: cannot set both `competition_date` and `ppm_enabled=True`.

**V3 nutrition & specialization overrides:**

| Column | Notes |
|---|---|
| `nutrition_mode_override` | str(24) nullable — when set, Engine 3 short-circuits phase detection. Values: `bulk`, `lean_bulk`, `maintain`, `cut`, `mini_cut`, `peak_week`, `restoration`. |
| `structural_priority_muscles` | JSONB list — persistent specialization that survives PPM limiting-factor reassignment. Engine 2's split designer adds bonus volume regardless of current gap. |
| `pct_mode_active` | **DEPRECATED** — kept for schema compat. PCT mode removed in V3.1; `training_status='enhanced'` covers the programming tweaks a PCT user needs. Column accepts writes but is never read. |

**Telegram:**

| Column | Notes |
|---|---|
| `telegram_bot_token` | Per-user bot from BotFather. Never exposed in GET responses. (TODO: encrypt at rest.) |

---

## 3. Measurements — `models/measurement.py`

### `body_weight_log`
Daily body weight. Indexed `(user_id, recorded_date)`.

### `tape_measurements`
Per-date tape snapshot. Every site is nullable — partial sessions OK.

**Standard girths (cm):** `neck`, `shoulders`, `chest`, `left_bicep`,
`right_bicep`, `left_forearm`, `right_forearm`, `waist`, `hips`,
`left_thigh`, `right_thigh`, `left_calf`, `right_calf`, `glutes` (V2 —
first-class for Bikini/Wellness).

**Advanced / isolation:** `chest_relaxed` (lats off — cleaner pec number),
`chest_lat_spread`, `back_width` (axillary breadth, *linear*),
`left_proximal_thigh`, `right_proximal_thigh`, `left_distal_thigh`,
`right_distal_thigh` (regional thigh shape).

### `skinfold_measurements`
Jackson-Pollock 7-site + Parrillo 9-site + optional pre-computed `body_fat_pct`.

Sites (mm): `chest`, `midaxillary`, `tricep`, `subscapular`, `abdominal`,
`suprailiac`, `thigh` (JP7); plus `bicep`, `lower_back`, `calf` (Parrillo
extensions, also used for site-specific lean-girth projection in
`physio.project_lean_girth`).

---

## 4. Diagnostic outputs — `models/diagnostic.py`

### `lcsa_logs`
Per-date `LCSA` (Lean Cross-Sectional Area) snapshot — total + per-site.

### `pds_logs`
Per-date PDS with component breakdown (aesthetic / mass / conditioning /
symmetry). Drives the PDS trajectory chart + trajectory response-ratio
personalization.

### `hqi_logs`
Hypertrophy Quality Index — the per-site `site_scores` JSONB payload is
the authoritative HQI snapshot consumed by PPM readiness and the Muscle
Gaps widget. Stale if older than `HQI_FRESHNESS_DAYS` (90 in
`constants/physio.py`).

---

## 5. Training — `models/training.py`

### `exercises`
Global catalog + user-registered custom exercises (`user_id` nullable,
`is_custom` flag). Fields: `primary_muscle`, `secondary_muscles`,
`movement_pattern`, `movement_pattern_detail`, `equipment`, `load_type`
(for increment-math: `plates` / `dumbbells` / `cable` / `machine_plates`
/ `plate_loaded` / `bodyweight`), `biomechanical_efficiency`,
`fatigue_ratio`, `contraindications` (JSONB).

### `strength_baselines`
Seed 1RMs per lift. Used until a newer `strength_logs` entry overwrites.
Stale > 90 days triggers Epley estimation from logs.

### `strength_logs`
Per-set strength record. `estimated_1rm` computed via Epley.

### `training_programs`
The active program record. Holds `split_type`, `days_per_week`,
`mesocycle_weeks`, `current_week`, `is_active`, `volume_allocation`
(JSONB dict), `custom_template` (JSONB list of day archetypes).

### `training_sessions`
One per planned or completed session. Includes `dup_profile`
(`heavy`/`moderate`/`light`), subjective post-session feedback
(`pump_quality`, `session_difficulty`, `joint_comfort` — 1–3 scale;
drives future per-muscle volume autoregulation), `stale_baselines` flag.

### `training_sets`
Per-set rows — prescribed vs actual + RPE. V3 additions:
`set_technique` (`drop_set` / `rest_pause` / `myo_reps` / `cluster` /
`lengthened_partial`), `tempo` (string like `3-1-1-0`), `is_fst7`,
`is_warmup`, `rest_seconds`, `prescribed_rpe`, `prescribed_rir`.

### `volume_allocation_log`
Per-muscle weekly set count + priority score snapshots. Drives
`/engine2/volume/weekly` chart.

### `division_vectors`
DB-backed mirror of `constants/divisions.py::DIVISION_VECTORS`. **Not
authoritative** — the code table is canonical; this table is read-only
for reporting / admin.

### `hrv_log`
Daily HRV + sleep + subjective wellness inputs. Fields: `rmssd`,
`resting_hr`, `sleep_quality` (1–10), `sleep_hours`, `soreness_score`
(1–10), `sore_muscles` (JSONB), `stress_score`, `mood_score`,
`energy_score`, `notes`.

### `ari_log`
Computed daily Autonomic Readiness Index. Stores each weighted component
separately so historical charts can show contribution drift.

---

## 6. Nutrition — `models/nutrition.py`

### `ingredients_master`
Static food database. Per-100g macros + `glycemic_index`, `is_peri_workout`.

### `nutrition_prescriptions`
Current macro prescription. `tdee`, `target_calories`, `protein_g`,
`carbs_g`, `fat_g`, `peri_workout_carb_pct`, `phase`, `is_active`. Only
one `is_active=True` per user at a time (admin fix-all enforces).

### `user_meals` + `meal_items`
Logged meals with per-ingredient breakdowns.

### `nutrition_log`
Per-date macro totals (summed from `user_meals` or hand-logged).

### `preworkout_logs`
Pre-workout caffeine / pump / nutrition snapshot. Consumed by peri-
workout nutrition card + safety checks.

### `meal_plan_templates`
Generated meal plans keyed by `(user_id, phase, day_type)` (training vs rest).

### `adherence_log`
Daily `nutrition_adherence_pct`, `training_adherence_pct`,
`overall_adherence_pct`. Gates Engine 3 autoregulation (< 85% locks).

### `weekly_checkins`
Consolidated weekly snapshot — body weight + average HRV + adherence.

---

## 7. PPM — `models/ppm_checkpoint.py`

### `ppm_checkpoints`
End-of-cycle readiness snapshot.

**Readiness metrics (first-class columns):**
`body_weight_kg`, `bf_pct`, `ffmi`, `shoulder_waist_ratio`,
`chest_waist_ratio`, `arm_calf_neck_parity`, `hqi_score`,
`weight_cap_pct`, `illusion_xframe`, `conditioning_pct` (last two
promoted from JSONB to columns in V2.S9 for queryability).

**Classification:** `readiness_state`, `limiting_factor`, `cycle_focus`.

**Snapshots (JSONB — enables "Prep Replay" reconstruction):**

| Column | Contents |
|---|---|
| `measurements_json` | Full tape + skinfold snapshot |
| `macros_snapshot` | **V3** — prescription that was active at checkpoint |
| `training_snapshot` | **V3** — split + day archetypes + exercise picks |
| `volume_snapshot` | **V3** — per-muscle actual vs prescribed sets |

Enables cross-cycle comparison ("in cycle 3 at 10% you ate 3100 kcal and
hit chest 16× with these exercises"). Read by
`/insights/archive/cycle/{n}`.

---

## 8. Progress photos — `models/progress_photo.py`

### `progress_photos`
Pose-tagged photo metadata. `photo_date`, `pose_type` (enum — see
`POSE_TYPES` constant), `storage_url`, optional `notes`. Files currently
live on the backend container's media dir; storage_url can point at
external object store.

---

## 9. Other — `models/`

- **`posing.py` → `posing_logs`** — per-date posing drill log.
- **`sleep.py` → `sleep_logs`** — detailed sleep stages (distinct from HRV sleep quality).
- **`notification.py` → `notification_log`, `coaching_feedback`** — Telegram/email/in-app messages and the feedback queue.

---

## 10. JSONB conventions

`JSONB` columns are used for:
- **Lists of strings** — `available_equipment`, `disliked_exercises`, `injury_history`, `structural_priority_muscles`, `cycle_focus_muscles`, `sore_muscles`.
- **Tier snapshots** — `measurements_json`, `macros_snapshot`, `training_snapshot`, `volume_snapshot`, `meals_json`, `volume_allocation`, `custom_template`, `contraindications`, `site_scores` (HQILog).

No column schema is enforced inside JSONB — callers validate shape in
Pydantic schemas (`backend/app/schemas/`). Pattern: when data is *read
back many times in different shapes*, it's JSONB; when it's *queried or
charted*, it's a dedicated column (this is why V2.S9 promoted
`illusion_xframe` + `conditioning_pct` out of `measurements_json`).

---

*Last indexed against backend revision `e6c31a5`, 2026-04-23.*
