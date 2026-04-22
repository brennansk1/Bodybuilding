# Viltrum — Engine Calculation Reference

Every formula, constant, and threshold the engines use to reason about
body composition, stage conditioning, lean-tissue projection, readiness,
and split design — with source file, line, and verification inputs.

The goal is a single document the athlete (or a coach) can use to verify
that the readiness pct, the lean-gap callout, the tier thresholds, and
the split designer's choices all follow from numbers you can audit.

If a calculation lives in more than one place, it is wrong. This document
also names which file is **authoritative** for each constant so future
refactors don't reintroduce drift.

---

## Table of contents

1. [Physiological constants (single source of truth)](#1-physiological-constants)
2. [Stage-projected weight (readiness)](#2-stage-projected-weight-readiness)
3. [Weight cap (Casey Butt)](#3-weight-cap-casey-butt)
4. [Ideal circumferences](#4-ideal-circumferences)
5. [Lean girth projection (BF-stripping)](#5-lean-girth-projection-bf-stripping)
6. [HQI — Hypertrophy Quality Index](#6-hqi--hypertrophy-quality-index)
7. [Mass gaps & mass-distribution readiness metric](#7-mass-gaps--mass-distribution-readiness-metric)
8. [Readiness tier evaluation](#8-readiness-tier-evaluation)
9. [Cycles-to-tier projection](#9-cycles-to-tier-projection)
10. [Symmetry scoring](#10-symmetry-scoring)
11. [Asymmetry-driven unilateral bias](#11-asymmetry-driven-unilateral-bias)
12. [Volumetric Ghost model](#12-volumetric-ghost-model)
13. [Split designer (need scores, volume budget)](#13-split-designer)
14. [FFMI (Kouri normalized)](#14-ffmi-kouri-normalized)

---

## 1. Physiological constants

**Authoritative file:** `backend/app/constants/physio.py`

| Constant | Male | Female | Purpose |
|---|---|---|---|
| `STAGE_BF_PCT` | 5.0% | 10.0% | What BF an athlete is projected *to* when evaluating readiness |
| `OFFSEASON_BF_CEILING` | 16.0% | 25.0% | Above this, planner routes to mini-cut |
| `FALLBACK_OFFSEASON_BF` | 15.0% | 22.0% | Used when no BF measurement exists |
| `HQI_FRESHNESS_DAYS` | 90 | 90 | Older HQI logs don't count toward readiness |
| `ASYMMETRY_UNILATERAL_CM` | 1.5 | 1.5 | Pair spread above this triggers unilateral bias |

Per-site lean-projection coefficients (`SITE_LEAN_K`): how aggressively fat
is stripped from each tape site when projecting to stage leanness.

| Site | k | Intuition |
|---|---|---|
| neck | 0.30 | carries almost no subcutaneous fat |
| forearm | 0.35 | sparse subq |
| calf | 0.35 | sparse subq |
| bicep | 0.40 | mild |
| shoulders | 0.50 | moderate |
| thigh | 0.50 | moderate |
| chest | 0.55 | heavy |
| hips | 0.65 | heavy |
| waist | 0.75 | dominant — most BF reduction shows up here |
| back_width | 0.50 | linear, treated as torso |

Symmetry penalty multipliers (used by `pds.compute_symmetry_details`):

| Site | Multiplier | Why |
|---|---|---|
| bicep | 600 | front-double-bi judged every pose |
| forearm | 600 | visible in most poses |
| calf | 550 | stage-standing silhouette |
| thigh | 300 | quad dominance somewhat tolerated |
| (default) | 500 | used by scalar `compute_symmetry_score` |

**Verification:** any engine importing `stage_bf_pct`, `fallback_offseason_bf_pct`,
`project_lean_girth`, `HQI_FRESHNESS_DAYS`, `SYMMETRY_PENALTY_MULT`, or
`ASYMMETRY_UNILATERAL_CM` must pull from `physio.py`. As of R4.A/R4.F: `readiness.py`,
`pds.py`, `weight_cap.py`, and `split_designer.py` all do.

---

## 2. Stage-projected weight (readiness)

**File:** `backend/app/engines/engine1/readiness.py::evaluate_readiness`

The readiness question is **"if you cut to stage conditioning today, would
your weight land at the tier target?"** — not "what do you weigh right now."

```
lbm_kg              = body_weight_kg × (1 − bf_pct / 100)
projected_stage_kg  = lbm_kg / (1 − stage_bf_pct / 100)      # stage_bf from physio.py
stage_weight_pct    = projected_stage_kg / weight_cap_kg
```

If BF is missing → fall back to `fallback_offseason_bf_pct(sex)` (15% M / 22% F).

**Why this matters:** previously the engine used `body_weight_kg / weight_cap_kg`.
A 93.5 kg male at 22% BF would report 0.889 of cap (89% "met"). Correct
answer: 93.5 × 0.78 / 0.95 = 76.7 kg stage → 0.723 of cap. Big reality check.

Example verification:

| Input | Raw % | Stage-projected % |
|---|---|---|
| 93.5 kg, 22% BF, 105.2 kg cap | 0.889 | **0.729** |
| 85 kg, 8% BF, 85 kg cap | 1.000 | **0.967** |
| 82 kg, 15% BF (fallback), 100 kg cap | 0.820 | **0.734** |

---

## 3. Weight cap (Casey Butt)

**File:** `backend/app/engines/engine1/weight_cap.py::compute_weight_cap`

Max lean body mass at stage conditioning is a function of height, wrist,
ankle, and target BF. Derived from Casey Butt's regression:

```
max_lbm_lbs  = height_in^1.5
             × (sqrt(wrist_in) / 22.6670 + sqrt(ankle_in) / 17.0104)
             × (1 + body_fat_pct / 224)                       # small BF correction
# Female version multiplies by 0.85 and uses 25.0 / 19.0 divisors

max_lbm_kg       = max_lbm_lbs × 0.453592
stage_weight_kg  = max_lbm_kg / (1 − body_fat_pct / 100)
offseason_weight_kg = max_lbm_kg / (1 − offseason_bf)         # 0.12 M / 0.18 F
```

Default structural anchors (when not measured): wrist 17.8 cm / 15.2 cm,
ankle 23.0 cm / 20.5 cm. Default `body_fat_pct` now pulls from
`physio.stage_bf_pct(sex)` rather than being hard-coded 5.0.

Tier caps (`lookup_weight_cap`) come from the IFBB 2024 official table —
the Casey-Butt figure is the athlete's *personal* ceiling; the tier cap is
the *division's* allowed maximum. The readiness metric tests the athlete's
projected-stage against the tier cap, not against their personal ceiling.

---

## 4. Ideal circumferences

**Authoritative file:** `backend/app/engines/engine1/hqi.py::compute_ideal_circumferences`

(`muscle_gaps.py` re-exports from `hqi.py` — R4.A removed the duplicate.)

For every muscle site:
```
ideal_lean_cm = casey_butt_max_cm × division_ceiling_factor
```

For **waist** and **hips** (stay-small sites):
```
ideal_lean_cm = division_vector_ratio × height_cm
```

### Casey Butt per-site maxima (inches)

From `weight_cap.compute_max_circumferences` — male formulas:

| Site | Formula |
|---|---|
| bicep   | `1.1709 × wrist + 0.1350 × height` |
| forearm | `0.950 × wrist + 0.1041 × height` |
| chest   | `1.625 × wrist + 1.3682 × ankle + 0.3562 × height` |
| neck    | `1.1 × wrist + 0.1264 × height` |
| thigh   | `1.4737 × ankle + 0.1918 × height` |
| calf    | `0.9812 × ankle + 0.125 × height` |
| back_width | `0.265 × height` |
| shoulders | `chest × 1.062` (6.2% deltoid mass premium) |

Female formulas trade coefficients (see file) and back_width uses `0.215 × height`.

### Division ceiling factors (what fraction of Casey-Butt max each division targets)

**File:** `backend/app/constants/divisions.py::DIVISION_CEILING_FACTORS`

| Division | bicep | chest | thigh | calf | back_width |
|---|---|---|---|---|---|
| mens_open | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| classic_physique | 0.96 | 0.97 | 0.95 | 0.95 | 0.97 |
| mens_physique | 0.92 | 0.90 | 0.78 | 0.80 | 0.93 |
| womens_figure | 0.80 | 0.82 | 0.82 | 0.80 | 0.82 |
| womens_bikini | 0.70 | 0.74 | 0.75 | 0.72 | 0.75 |
| womens_physique | 0.87 | 0.88 | 0.87 | 0.85 | 0.87 |
| wellness | 0.72 | 0.72 | 0.90 | 0.72 | 0.75 |

**Verification example:** for a 178 cm / 17.8 cm wrist / 23 cm ankle male
Classic Physique athlete:
- Casey-Butt bicep max = 1.1709 × 7.01 + 0.1350 × 70.08 = 17.67" = 44.9 cm
- Classic ideal bicep = 44.9 × 0.96 = **43.1 cm**

---

## 5. Lean girth projection (BF-stripping)

**File:** `backend/app/constants/physio.py::project_lean_girth`

Converts a raw tape reading at current BF to what that site would measure
at stage leanness (5% M / 10% F):

```
lean_cm = raw_cm × (1 − k_site × max(0, bf_pct − 5) / 100)
```

Capped at 5% residual BF (the lean circumference can't drop below what the
athlete would measure at contest conditioning).

**Verification:** 40 cm raw bicep at 22% BF →
`40 × (1 − 0.40 × 17 / 100) = 40 × 0.932 = 37.3 cm` lean.

This is what HQI compares against `ideal_lean_cm` (44.9 × 0.96 = 43.1 cm
for Classic) — giving a **5.8 cm** raw-lean gap. The aesthetic ratio check
using raw 40 cm vs ratio target (0.220 × 178 = 39.2 cm) *would pass*,
hence the old engine silently reported "biceps fine" while HQI correctly
flagged a 5.8 cm gap.

---

## 6. HQI — Hypertrophy Quality Index

**File:** `backend/app/engines/engine1/hqi.py`

Per-site score on 0–100 using exponential decay over lean-cm gap:

```
gap_cm = ideal_lean_cm − lean_circ_cm
score  = 100 × exp(−0.055 × gap_cm)       # if gap_cm > 0
       = 100                              # if at or above ideal
```

| gap_cm | score |
|---|---|
| 0  | 100 |
| 3  |  83 |
| 5  |  74 |
| 10 |  55 |
| 15 |  41 |
| 20 |  30 |

Overall HQI: **visibility-weighted** average (hidden sites don't dilute).

### Division visibility weights

See `hqi.py::_DIVISION_VISIBILITY` and `muscle_gaps.py::_DIVISION_VISIBILITY`
(kept in sync). Notable:

| Division | thigh | calf | hips | forearm |
|---|---|---|---|---|
| mens_open | 1.0 | 1.0 | 0.9 | 1.0 |
| classic_physique | 1.0 | 1.0 | 0.9 | 1.0 |
| mens_physique | 0.0 | 0.25 | 0.15 | 1.0 |
| womens_bikini | 0.5 | 0.2 | 1.0 | 0.3 |
| wellness | 1.0 | 0.4 | 1.0 | 0.3 |

A Men's Physique athlete with a 10 cm thigh gap takes **zero** penalty
(weight 0), whereas the same gap in Open/Classic costs 55 points.

---

## 7. Mass gaps & mass-distribution readiness metric

**File:** `backend/app/engines/engine1/readiness.py` (R4.C)

HQI produces per-site gap rows. Readiness now exposes the **top three
lagging muscles by lean-cm gap** as an 8th metric called
`mass_distribution`:

```
worst_pct = min(pct_of_ideal for top-3 add_muscle sites) / 100
met       = worst_pct ≥ 0.85
```

Surfaced in TierReadinessCard as the "Lagging muscles" panel next to the
limiting-factor callout. The worst site becomes the limiting factor when
its pct_progress < the other seven metrics'.

**Verification:** an athlete whose only sub-85% HQI site is quads at 68%
will have `mass_distribution.current = 0.68, target = 0.85, met = false`
and **quads** will be visible in the lagging-muscles panel with the exact
`current cm / ideal cm / −gap cm` breakdown.

---

## 8. Readiness tier evaluation

**File:** `backend/app/engines/engine1/readiness.py::evaluate_readiness`

Eight metrics are compared against `TierThresholds` from
`constants/competitive_tiers.py::CLASSIC_PHYSIQUE_TIERS`:

| Metric | Direction | Source |
|---|---|---|
| `weight_cap_pct` | ≥ threshold | stage-projected weight ÷ cap |
| `ffmi` | ≥ threshold | Kouri normalized |
| `shoulder_waist` | ≥ threshold | tape shoulders ÷ waist |
| `chest_waist` | ≥ threshold | aesthetic_vector |
| `arm_calf_neck_parity` | ≤ threshold (inches) | max − min of arm/calf/neck |
| `hqi` | ≥ threshold | visibility-weighted HQI, zeroed if >90 days old |
| `training_years` | ≥ threshold | profile.training_experience_years |
| `mass_distribution` | ≥ 0.85 worst-site | top 3 HQI lagging-muscle pct (R4.C) |

State classification:
```
pct_met = metrics_met / metrics_total
pct_met ≥ 1.00 → stage_ready
pct_met ≥ 0.85 → approaching
pct_met ≥ 0.60 → developing
else           → not_ready
```

Limiting factor = the metric with the lowest `pct_progress`.

### Classic Physique tier table (excerpt)

| Tier | WC % min | FFMI | S:W | C:W | Parity | HQI | Years (nat) |
|---|---|---|---|---|---|---|---|
| T1 Local | 0.80 | 22.0 | 1.40 | 1.30 | 1.5" | 50 | 2 |
| T2 Regional | 0.87 | 23.5 | 1.45 | 1.33 | 1.2" | 65 | 3 |
| T3 National | 0.92 | 25.0 | 1.50 | 1.36 | 1.0" | 78 | 5 |
| T4 Pro qual | 0.96 | 26.5 | 1.55 | 1.40 | 0.75" | 85 | 7 |
| T5 Olympia | 1.00 | 28.0 | 1.60 | 1.43 | 0.50" | 92 | 9 |

---

## 9. Cycles-to-tier projection

**File:** `readiness.py::estimate_cycles_to_tier`

```
annual_lbm_natural    = max(0.5,  11.0 × 0.5^(training_years − 1))
annual_lbm_enhanced   = max(1.0,  16.0 × 0.6^(training_years − 1))
per_cycle_lbm_kg      = annual_lbm × 14/52

weight_gap            = (tier_threshold × weight_cap_kg) − body_weight_kg
lbm_gap               = max(0, weight_gap × 0.70)         # ~70% of mass gap is LBM

mass_cycles: iterate adding per_cycle_lbm with 5%/cycle diminishing returns
            until accumulated ≥ lbm_gap

proportion_cycles     = 3 if any of {shoulder_waist, chest_waist, parity} unmet

total_cycles          = max(mass_cycles, proportion_cycles)
estimated_months      = total_cycles × 3.5        # 14-week cycle length
```

---

## 10. Symmetry scoring

**File:** `backend/app/engines/engine1/pds.py`

Scalar `compute_symmetry_score(tape)`:
```
deviation = |left − right| / ((left + right) / 2)    # per pair
avg_dev   = mean(deviation for all L/R pairs)
score     = max(0, 100 − avg_dev × SYMMETRY_PENALTY_DEFAULT)   # 500
```

Per-site `compute_symmetry_details(tape)`:
```
penalty_mult = SYMMETRY_PENALTY_MULT[site]          # from physio.py
site_score   = max(0, 100 − dev × penalty_mult)
```

**Verification:** bicep L=40.5, R=40.0. avg=40.25. dev=0.01242.
- Scalar contribution: 0.01242 × 500 = 6.21
- Bicep site: 100 − 0.01242 × 600 = 92.6

Both functions now read the same multipliers (R4.F closed the M4 mismatch).

---

## 11. Asymmetry-driven unilateral bias

**File:** `backend/app/engines/engine2/split_designer.py` (R4.E)

When a bilateral pair spread exceeds `ASYMMETRY_UNILATERAL_CM` (1.5 cm):

```
lagging_side            = "right" if left > right else "left"
bonus_sets_per_session  = 2
```

Surfaced as `design_split() → unilateral_bias[muscle] = {lagging_side, spread_cm, bonus_sets_per_session}`.

Consumed by `services/training.generate_program_sessions`: when computing
`total_sets` for a db_muscle that appears in the bias map, +2 sets are
added to that session. The extra volume targets the lagging side at
exercise-selection time (preferring unilateral lifts).

Tape pair → training muscle mapping:

| Tape pair | Training muscles affected |
|---|---|
| left_bicep / right_bicep | biceps |
| left_forearm / right_forearm | forearms |
| left_thigh / right_thigh | quads + hamstrings |
| left_calf / right_calf | calves |

---

## 12. Volumetric Ghost model

**File:** `backend/app/engines/engine1/volumetric_ghost.py`

Produces a 3D Hanavan-segment body reconstruction from tape +
`GHOST_VECTORS[division]` (in `constants/divisions.py`). The output
`stage_weight_kg` and per-site lean ideals feed the muscle_gaps engine.

Ghost vectors are **distinct** from `DIVISION_VECTORS` — the latter
encode aesthetic shape for PDS scoring, the former encode actual
competitive athlete proportions at the weight cap. For Classic at 180 cm:

- Aesthetic: waist/height = 0.405, bicep/height = 0.220
- Ghost: waist/height = 0.440, bicep/height = 0.295

Allometric scaling applies a cube-root correction so the Hanavan mass
matches the division weight cap; the vectors themselves do most of the work.

---

## 13. Split designer

**File:** `backend/app/engines/engine2/split_designer.py::design_split`

Builds a custom weekly training template from:

1. **Need scores** per muscle: `gap_cm × division_importance_weight × illusion_multiplier`
2. **Volume budget** per muscle: scaled MEV→MAV→MRV placement based on need
3. **Desired frequency** per muscle: driven by need + recovery window
4. **Division archetype**: Open vs MP vs glute-priority (Bikini/Wellness)

Key safety clamps (Rule 1 series):
- **Shoulder aggregation clamp**: combined front+side+rear delt volume
  capped at `12 × shoulder_frequency` to prevent a 35-set "shoulder day"
  when the engine sums three independent sub-muscles.
- **Per-session muscle cap**: 10 sets per muscle per session; excess
  spills to the next session.
- **Per-session total cap** (`_MAX_SETS_PER_SESSION`): enforced on
  cluster-aggregated days.
- **Low-importance filter**: muscles with division importance ≤ 0.25
  appear max once per week; ≤ 0.1 removed entirely.

Output keys: `template`, `split_name` ("custom"), `need_scores`,
`volume_budget`, `desired_frequency`, `unilateral_bias`, `reasoning`.

Dead `auto_select_split()` was removed in R3.2 — there is now exactly
one split-generation path.

---

## 14. FFMI (Kouri normalized)

**File:** `readiness.py::compute_normalized_ffmi`

```
height_m = height_cm / 100
raw_ffmi = lbm_kg / height_m²
ffmi     = raw_ffmi + 6.1 × (1.8 − height_m)          # scale to 1.8m reference
```

The +6.1 correction is Kouri's adjustment so short and tall athletes can
be compared on the same scale. At 1.8 m height the correction is zero;
at 1.7 m it adds 0.61, at 1.9 m it subtracts 0.61.

**Verification:** 80 kg LBM at 178 cm →
raw = 80 / 1.78² = 25.25. normalized = 25.25 + 6.1 × (1.8 − 1.78) = 25.37.

Kouri's natural-ceiling interpretation:
- 23+ → trained natural
- 25+ → advanced natural (upper natural bound)
- 27+ → above natural limit (enhanced)

---

## Changelog

- **R4.A** — Unified `compute_ideal_circumferences` (was duplicated in
  `hqi.py` and `muscle_gaps.py`). Created `physio.py` for stage BF,
  offseason ceiling, fallback BF, HQI freshness, site-lean coefficients,
  symmetry multipliers, and asymmetry threshold.
- **R4.B** — Readiness now uses `physio.stage_bf_pct(sex)` and
  `fallback_offseason_bf_pct(sex)`; HQI staleness guard uses
  `physio.HQI_FRESHNESS_DAYS`.
- **R4.C** — Readiness added `mass_distribution` metric + `mass_gaps`
  top-level output; TierReadinessCard renders the lagging-muscles panel.
- **R4.D** — PPM `_build_cycle_plan` now passes real HQI site gaps into
  `design_split` (was empty dict → division archetype only).
- **R4.E** — `design_split` emits `unilateral_bias` from L/R tape spread
  > 1.5 cm; `generate_program_sessions` adds +2 sets per session to the
  lagging-side muscle.
- **R4.F** — `pds.py` symmetry multipliers pulled from `physio.py`;
  `weight_cap.py` default BF now sourced from `physio.stage_bf_pct`.

## Mismatch tracker

| ID | Description | Status |
|---|---|---|
| M1 | `weight_cap` default `body_fat_pct=5.0` hard-coded while readiness used `physio.stage_bf_pct` | **Fixed R4.F** |
| M2 | PPM `_build_cycle_plan` passed empty `hqi_gaps` to `design_split` | **Fixed R4.D** |
| M3 | Readiness compared raw-tape ratios, HQI compared lean cross-section → quads could silently pass at 19 cm lean gap | **Fixed R4.C** (mass_distribution metric surfaces the gap) |
| M4 | `pds.compute_symmetry_score` used scalar 500 while `compute_symmetry_details` used per-site 300–600 — same athlete got two scores | **Fixed R4.F** (both now read `physio.SYMMETRY_PENALTY_*`) |
| M5 | `compute_ideal_circumferences` duplicated in `hqi.py` and `muscle_gaps.py` with subtly different outputs | **Fixed R4.A** |
| M6 | `_SYMMETRY_PENALTY_MULT` hard-coded in `pds.py` | **Fixed R4.F** |
| M7 | HQI visibility weights duplicated in `hqi.py` and `muscle_gaps.py` — still both exist but in sync | Monitored |
| M8 | Stage BF duplicated across `readiness.py`, `weight_cap.py`, `pds.py` | **Fixed R4.A** |
