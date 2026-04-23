# Viltrum — Engine Reference

This document describes every engine module: what it's responsible for,
what problem it solves, how it talks to the other engines, and where to
tune it. It is meant to sit alongside [`CALCULATIONS.md`](./CALCULATIONS.md),
which catalogs the specific formulas, constants, and thresholds those
engines use.

Read ENGINES.md to understand **what each piece does and why it exists**.
Read CALCULATIONS.md to verify **the actual numbers**. When something
looks wrong, the usual debugging order is:

1. Trace the user-facing number back to the engine that produced it (this doc).
2. Locate the formula that computed it (CALCULATIONS.md).
3. Identify which constant or threshold drives the decision (physio.py,
   competitive_tiers.py, divisions.py, volume_landmarks.py).

---

## Table of contents

1. [Architecture overview](#1-architecture-overview)
2. [Cross-cutting constants layer](#2-cross-cutting-constants-layer)
3. [Engine 1 — Diagnostic (`engines/engine1/`)](#3-engine-1--diagnostic)
4. [Engine 2 — Training (`engines/engine2/`)](#4-engine-2--training)
5. [Engine 3 — Nutrition (`engines/engine3/`)](#5-engine-3--nutrition)
6. [Engine 4 — Cardio & NEAT (`engines/engine4/`)](#6-engine-4--cardio--neat)
7. [PPM orchestrator (spans engines 1–3)](#7-ppm-orchestrator)
8. [Cross-engine data flow](#8-cross-engine-data-flow)
9. [API surface → engine mapping](#9-api-surface--engine-mapping)
10. [Optimization surface (where to tune)](#10-optimization-surface)
11. [Known open design questions](#11-known-open-design-questions)

---

## 1. Architecture overview

Viltrum is a coaching system built around **four engines** plus a
**shared constants layer**. Each engine is a pure-Python module tree
under `backend/app/engines/engineN/` with *no database or HTTP imports*
— orchestration is handled by routers and services. This keeps the
scientific logic pure, unit-testable, and re-runnable against historical
data for backtesting.

```
backend/app/
├── constants/                     ← Cross-cutting truth (see §2)
│   ├── physio.py                  ← Stage BF, offseason ceiling, HQI freshness…
│   ├── competitive_tiers.py       ← PPM tier thresholds T1-T5
│   ├── weight_caps.py             ← IFBB 2024 division weight caps
│   └── divisions.py               ← DIVISION_VECTORS, DIVISION_CEILING_FACTORS
│
├── engines/
│   ├── engine1/   ← Diagnostic (who is this athlete right now?)
│   ├── engine2/   ← Training (what should the next workout look like?)
│   ├── engine3/   ← Nutrition (what should they eat this week?)
│   └── engine4/   ← Cardio & NEAT (what energy expenditure to mandate?)
│
├── services/
│   ├── diagnostic.py              ← E1 orchestrator — runs all E1 modules
│   └── training.py                ← generate_program_sessions (E2)
│
└── routers/
    ├── engine1.py engine2.py engine3.py  ← per-engine HTTP endpoints
    └── ppm.py                             ← 14-week improvement cycles
```

The conceptual flow is:

```
          (tape + skinfolds + body weight + HRV + sleep)
                              │
                              ▼
                    ┌────────────────────┐
                    │  Engine 1          │
                    │  Diagnostic        │─── PDS, HQI, Mass gaps, Readiness
                    └─────────┬──────────┘
                              │
                              ▼ (lagging muscles, gap profile, phase)
                    ┌────────────────────┐
                    │  Engine 2          │
                    │  Training          │─── Split design + periodized sessions
                    └─────────┬──────────┘
                              │
                              ▼ (training load, phase, body weight trend)
                    ┌────────────────────┐
                    │  Engine 3          │
                    │  Nutrition         │─── Macros, refeeds, peak week
                    └─────────┬──────────┘
                              │
                              ▼ (kcal floor risk)
                    ┌────────────────────┐
                    │  Engine 4          │
                    │  Cardio / NEAT     │─── Cardio + step prescription
                    └────────────────────┘
```

Engines do not cycle: **E1 → E2 → E3 → E4** is one-way. Feedback comes
from the *next* diagnostic, not from downstream engines mutating upstream.

---

## 2. Cross-cutting constants layer

These modules are pure data and shared by every engine. Treat them as the
single source of truth — if a number appears in two places, it is a bug.

### `constants/physio.py` (added in R4.A)

Physiological constants every engine needs:

- Stage BF targets (5% M / 10% F) via `stage_bf_pct(sex)`
- Offseason BF ceiling (16% M / 25% F) — above this the planner routes to mini-cut
- Fallback offseason BF (15% M / 22% F) when no measurement exists
- `SITE_LEAN_K` coefficients and `project_lean_girth(raw_cm, site, bf_pct)`
  helper for BF-stripping tape measurements
- `HQI_FRESHNESS_DAYS = 90` — diagnostics older than this don't count
- `SYMMETRY_PENALTY_MULT` map + `SYMMETRY_PENALTY_DEFAULT` for PDS
- `ASYMMETRY_UNILATERAL_CM = 1.5` — pair spread threshold for unilateral bias

**Why this module exists:** before R4.A, stage BF was declared in
`readiness.py`, `weight_cap.py`, `pds.py`, `volumetric_ghost.py`, and
inline in routers. The engines disagreed on the same athlete's stage
weight. Centralizing forces agreement.

### `constants/competitive_tiers.py`

`TierThresholds` dataclass + the Classic Physique T1–T5 table consumed
by `readiness.evaluate_readiness`. Each tier defines concrete minima on
weight-cap %, BF %, FFMI, shoulder:waist, chest:waist, arm/calf/neck
parity, HQI, and training years.

### `constants/weight_caps.py`

Canonical IFBB 2024 division × height weight cap table. Read by
readiness (what the athlete is aiming at) and by the Ghost Model (to
fit its scaling factor).

### `constants/divisions.py`

Four co-located tables keyed by division:

- **`DIVISION_VECTORS`** — circumference-to-height ratios for 11 sites.
  The **aesthetic** shape target, used by PDS scoring and the
  `shoulder_to_waist` / `v_taper` ideals.
- **`DIVISION_CEILING_FACTORS`** — what fraction of Casey-Butt max each
  division targets per muscle site. Men's Open aims for 1.0; MP
  intentionally under-develops thighs at 0.78.
- **`K_SITE_FACTORS`** — LCSA shape factors (non-circular cross-section
  correction).
- **`GHOST_VECTORS`** — Hanavan-segment proportions for the Volumetric
  Ghost model. **Distinct** from `DIVISION_VECTORS` — Ghost encodes actual
  competitive athlete proportions at the weight cap, not the aesthetic
  ratio ideals.

---

## 3. Engine 1 — Diagnostic

**Purpose:** quantify where the athlete is *right now* and flag what
needs to change. Every E1 module is pure math; the orchestrator
(`services/diagnostic.py::run_full_diagnostic`) composes their outputs
into a single API payload.

### `body_fat.py`
Jackson-Pollock 7-site skinfold formula for BF%. Includes
`categorize_body_fat(bf_pct, sex)` used by dashboard widgets.
**When authoritative BF is missing**, downstream engines fall back to
`physio.fallback_offseason_bf_pct(sex)`.

### `lcsa.py` (Lean Cross-Sectional Area)
```
LCSA_site = (circ / 2π)² × π × k_site × (1 − bf_fraction)
```
Converts a circumference to an estimated muscle cross-sectional area in
cm². `total_lcsa = Σ LCSA_site` is the scalar used by the PDS mass
component and by trajectory projections. Good because cross-section
scales with force production; bad because it rewards fat that happens to
sit over muscle (hence the BF correction).

### `weight_cap.py`
Casey Butt adaptation. Two callable outputs:

- `compute_weight_cap(height, wrist, ankle, body_fat_pct, sex)` —
  `max_lbm_kg`, `stage_weight_kg`, `offseason_weight_kg`. Default BF now
  pulls from `physio.stage_bf_pct(sex)` (R4.F).
- `compute_max_circumferences(height, wrist, ankle, sex)` — per-site
  genetic-ceiling circumferences. These × `DIVISION_CEILING_FACTORS`
  produce per-site ideals for HQI.

The Casey Butt regression is a **structural** (bone-anchor) model: your
wrist and ankle set your ceiling, no amount of training overrides the
geometry. Honest coaching refuses to promise otherwise — see
`honesty.py`.

### `aesthetic_vector.py`
Computes the athlete's current proportion vector (ratio of each
circumference to height) and compares to `DIVISION_VECTORS[division]`.
Returns cosine similarity (0–1) + per-site delta. Also exposes the
named ratio helpers used by readiness:

- `compute_chest_waist_ratio(chest, waist)`
- `compute_arm_calf_neck_parity(tape)` — max − min across the three in
  inches

**Visibility weights** live here (`_DIVISION_SITE_VISIBILITY`) mirroring
HQI's weights so the aesthetic score and the HQI score agree on which
sites are judged in each division.

### `hqi.py` — Hypertrophy Quality Index
Per-site score on 0–100 based on lean-cm gap from the personal division
ideal. Exponential decay (`k = 0.055`) means a 5 cm gap is 74, a 10 cm
gap is 55. Overall HQI is the **visibility-weighted** average.

Authoritative module for `compute_ideal_circumferences` since R4.A
(muscle_gaps.py now re-exports).

### `muscle_gaps.py`
Takes the per-site HQI rows and produces coaching-facing outputs:

- `compute_all_gaps(lean, ideal)` — `{site: {ideal, current, gap, pct, type}}`
- `rank_sites_by_gap(site_data, division)` — sorted by
  `weighted_gap = gap × visibility` so the front-end list matches what
  the judge actually sees
- `compute_avg_pct_of_ideal(...)` and `compute_total_gap(...)` for
  summary cards

This is what the Muscle Gaps widget on the dashboard renders.

### `volumetric_ghost.py`
Physics-based 3D body reconstruction using a **Hanavan segmental model**
(cylinders + frusta for limbs, ellipsoids for torso). Takes the
athlete's division, height, and tape → builds a mathematically perfect
"ghost" at division weight cap, then allometrically scales it to the
athlete's body. Used by `services/diagnostic.py` to produce the
per-site HQI gap that feeds both the PPM readiness pipeline (via
`HQILog.site_scores`) and the Muscle Gaps dashboard widget.

The Ghost model is the reason we have *two* division tables:
`DIVISION_VECTORS` encodes aesthetic shape for PDS, `GHOST_VECTORS`
encodes actual large-athlete proportions (waist 0.44 vs 0.405, etc.).

### `pds.py` — Physique Development Score
Composite 0–100 score integrating four components with
**division-specific weights**:

| Division | Aesthetic | Mass | Conditioning | Symmetry |
|---|---|---|---|---|
| mens_open | 0.30 | 0.40 | 0.15 | 0.15 |
| classic_physique | 0.45 | 0.25 | 0.15 | 0.15 |
| mens_physique | 0.40 | 0.20 | 0.25 | 0.15 |
| womens_bikini | 0.30 | 0.15 | 0.35 | 0.20 |
| womens_figure | 0.35 | 0.25 | 0.25 | 0.15 |
| womens_physique | 0.35 | 0.35 | 0.15 | 0.15 |

Symmetry multipliers now sourced from `physio.py` (R4.F) so
`compute_symmetry_score` (scalar) and `compute_symmetry_details`
(per-site) never disagree on the same athlete's scores.

Tier bands: Elite ≥85, Advanced 70–84, Intermediate 50–69, Novice <50.

### `trajectory.py`
Asymptotic decay model `PDS(t) = ceiling − (ceiling − current) × e^(−k×t)`
for 52-week PDS projection. Also exposes `personalized_trajectory` when
≥3 PDS history points exist — the response ratio is computed per-athlete
and overrides the generic `k`.

### `readiness.py` (PPM core)
Evaluates the athlete against a target competitive tier. Updated in R4.B
to accept `sex` and pull stage/fallback BF and HQI freshness from
`physio.py`. In R4.C it gained an 8th metric `mass_distribution` that
reads HQI site gaps and surfaces the top-3 lagging muscles — so a
quad at 68% of ideal can't silently pass the aesthetic ratio check.

Returns `state` ∈ {not_ready, developing, approaching, stage_ready},
`limiting_factor`, `per_metric` rows, and `mass_gaps` (top 3). Consumed
by TierReadinessCard and by `estimate_cycles_to_tier`.

### `honesty.py`
Natural attainability gate. Compares Casey-Butt-predicted natural max
against the tier's requirements. Blocks PPM enrollment at T3+ for
natural athletes whose structure says the tier is out of reach — with a
pointed recommendation (drop tiers, switch to MP, consider the natural
federations).

### `feasibility.py`
Simpler cousin of honesty — checks whether a target PDS is reachable
within the given timeline based on `trajectory.py` projections.

### `prep_timeline.py`
The phase resolver (single source of truth since R3):
```
get_current_phase(competition_date, ppm_enabled, cycle_start_date, current_date)
```
Returns one of: `offseason`, `lean_bulk`, `cut`, `peak_week`, `contest`,
`restoration`, OR `ppm_assessment`, `ppm_accumulation`,
`ppm_intensification`, `ppm_deload`, `ppm_checkpoint`, `ppm_mini_cut`.
Also exposes `ppm_phase_for_week(week, mini_cut_active)` used by the PPM
plan builder.

---

## 4. Engine 2 — Training

**Purpose:** turn the diagnostic into a concrete weekly program. The two
primary entry points are `split_designer.design_split()` (strategic) and
`services/training.generate_program_sessions()` (tactical).

### `split_designer.py`
The strategic designer. Builds a custom weekly template given:

- `hqi_gaps: {site: gap_cm}` from HQI diagnostic
- `division` + `days_per_week`
- `shoulder_width_cm`, `height_cm` (illusion multipliers)
- `tape_pairs` (R4.E — for asymmetry-driven unilateral bias)

Three internal computations:

1. **`compute_need_scores`** — `gap_cm × division_importance_weight`.
2. **`compute_volume_budget`** — weekly set count per muscle, scaled to
   MEV/MAV/MRV landmarks based on need.
3. **`compute_desired_frequency`** — how many sessions/week each muscle
   should appear in; driven by need and recovery windows.

Apply illusion multipliers for narrow-framed athletes (more shoulders
and back to cheat wider), cluster into archetypes (Open/Classic full-body,
MP upper-priority, Bikini/Wellness glute-priority), expand clusters to
muscles, and apply **safety clamps**:

- `MAX_SETS_PER_MUSCLE_PER_SESSION = 10` (spillover to next session)
- `_MAX_SETS_PER_SESSION` at cluster level
- Combined deltoid volume ≤ `12 × shoulder_frequency` (Rule 1C
  aggregation safety clamp — otherwise three delt sub-roles sum into a
  35-set session)
- Division low-importance filter (importance ≤0.25 → max once/week; ≤0.1
  → removed entirely)

**R4.E addition:** emits `unilateral_bias: {muscle: {lagging_side, spread_cm,
bonus_sets_per_session}}` when any bilateral pair spreads > 1.5 cm.
`reasoning` string explains every decision so the frontend can render
"Why this split?" accordions. There is no longer a second selector —
`auto_select_split` was deleted in R3.2.

### `periodization.py`
Mesocycle scheduler. Supports DUP (default), Block, and traditional
periodization. Exposes:

- `generate_mesocycle(split_name, weeks, volume_allocation)` — classic
  prep-style output
- `compute_cycle_mesocycle(week, focus_muscles, landmarks)` — PPM-aware;
  returns per-muscle sets + landmark zone + RIR + FST-7 mode for a given
  cycle week

### `volume_landmarks.py`
Mike Israetel / Renaissance Periodization published landmarks per
muscle. `MEV`, `MAV`, `MRV` tuples scaled by training years and
training status. These are **soft** individual-variable guides — the
engine treats them as suggestions bounded by the safety clamps, not
hard contracts.

### `ari.py` — Autonomic Readiness Index
Daily 0–100 readiness score from HRV, sleep, soreness, resting HR, and
subjective wellness. The HRV baseline is a 7-day rolling mean (Plews/
Buchheit standard). ARI feeds the daily volume autoregulation: ARI < 50
cuts planned volume by up to 40%, ARI > 85 permits an intensification
technique to fire.

### `recovery.py`
Per-muscle minimum recovery windows (small = 24–36h, medium = 36–48h,
large = 48–72h). Also tracks CNS / systemic fatigue — heavy compound
movements at high RPE contribute disproportionately, limiting capacity
across subsequent sessions. Blocks the scheduler from programming a
muscle before it's recovered.

### `biomechanical.py`
Exercise selector. Scores candidates with
`SFR = efficiency / fatigue_ratio` × `priority_score`. Also enforces
**movement-pattern diversity** — each muscle group must cover its full
pattern spectrum (horizontal press + vertical press + incline, etc.)
before repeating patterns.

### `resistance.py`
Progressive overload: double progression (reps first, then load with
reset to rep floor) with exercise-class-specific increment rules (barbell
compound ≠ dumbbell isolation ≠ cable). Also hosts the Epley 1RM
estimator used when strength baselines are >90 days old.

### `overflow.py`
Accounts for indirect volume: a bench press primarily hits chest but
adds meaningful pec-minor, front-delt, and triceps stimulus. The
overflow matrix expresses what fraction of a primary set counts toward
each secondary muscle's weekly tally, so we don't over-prescribe
isolation for already-saturated muscles.

### `services/training.py::generate_program_sessions`
Wires the above engines into persisted `TrainingSession` + `TrainingSet`
records. Pulls HQI → calls `design_split` → for each day calls
`periodization.compute_cycle_mesocycle` → filters exercises by equipment /
injury / division bans → applies recovery gating → emits sessions.

R4.E added: loads latest tape L/R pairs, passes `tape_pairs` to
`design_split`, and adds `+2 sets` per session for any muscle in the
returned `unilateral_bias` map.

---

## 5. Engine 3 — Nutrition

**Purpose:** prescribe macros + refeeds + peak week from an adherence-
gated, phase-aware model. All modules are pure math; the router
(`routers/engine3.py`) composes them.

### `macros.py`
`compute_tdee(weight, height, age, sex, activity_multiplier, lean_mass_kg)`
uses **Katch-McArdle** when LBM is available (Cunningham-adjusted),
falling back to Mifflin-St Jeor. `compute_macros(tdee, phase, …)`
produces protein/carbs/fat targets and a **carb cycle** block
(hi/med/lo days) appropriate to the phase. PPM sub-phases alias to
legacy phases via `_PPM_TO_LEGACY_FOR_MACROS` so nutrition engines
don't need PPM awareness.

### `kinetic.py`
Rate-of-change controller. Targets:

- bulk: +0.25 to +0.5 %BW/week
- lean_bulk: +0.15 to +0.3 %BW/week
- maintain: ±0.15 %BW/week
- cut: −0.5 to −1.0 %BW/week
- peak_week: no-growth, water/glycogen only

If the actual 2-week trend diverges from target, emits a calorie
adjustment (typically ±50–150 kcal/day).

### `autoregulation.py`
Adherence gate — **refuses to adjust macros when adherence < 85%**.
Core coaching principle: you cannot tell a "plan" is failing if the
athlete isn't executing it. Instead, it escalates coaching (refeed
suggestion, adherence intervention) until adherence returns.

Also hosts `BF_FLOOR` per division — halts cut and forces maintenance
when the athlete hits the division's contest-safe minimum. Floors are
bumped +1–2% above DEXA-contest-min because calipers under-read at
contest leanness.

### `thermodynamic.py`
Energy balance accounting. Converts kcal surplus/deficit to projected
body-mass change using phase-specific kcal/kg equivalents (bulk: 4500,
cut: 6500) since lean accretion is cheaper than fat accretion per unit
body mass change.

### `peak_week.py`
Generates a 7-day carb/water/sodium manipulation protocol anchored to
show day. Load days start 72h out, sodium drops 48h out, water taper
begins 24h out. Carb targets derived from LBM for size-scaling.

### `meal_planner.py`, `food_database.py`, `food_database_expansion.py`
Pantry-aware meal generator + static food database + optional expansion
set. Produces meal plans that hit the prescribed macros using the
athlete's available foods.

### `shopping_list.py`
Rolls a week of meal plans into a deduped shopping list grouped by aisle.

### `supplements.py`
Evidence-tier-rated supplement recommendations with dosing and phase
relevance (creatine always, beta-alanine during high-volume, electrolytes
peak-week, etc.).

---

## 6. Engine 4 — Cardio & NEAT

**Purpose:** manipulate *energy expenditure* before reducing *energy
intake*. A coaching principle — an elite prep intercepts Engine 3's
caloric reduction pathway and mandates cardio/NEAT increases when the
athlete approaches minimum viable intake.

### `cardio.py`
Three subroutines:

1. **Energy Flux Model** — keep food high, push expenditure higher
2. **NEAT Tracking** — phase-specific step-count titration (offseason
   8k, prep 12k, late prep 15k)
3. **Active Cardio Periodization** — HIIT permitted offseason, LISS-only
   in late prep (preserve lower-body recovery)

---

## 7. PPM orchestrator

PPM is not an engine — it is an **orchestrator** that spans E1 → E2 → E3.
Code lives in `routers/ppm.py`. Conceptually it answers:

> "Given the athlete's current diagnostic and their target tier, what
> should the next 14-week improvement cycle look like?"

Pipeline:

```
profile + latest_tape + latest_bw + latest_skinfold + latest_hqi
        │
        ▼
_compute_athlete_metrics  ←── E1 (body_fat, readiness.compute_normalized_ffmi,
        │                       aesthetic_vector, hqi)
        ▼
readiness.evaluate_readiness(metrics, target_tier, cap, training_status, division, sex)
        │
        ▼                                              ▲
_limiting_muscles_from_readiness → focus_muscles       │
        │                                              │
        ▼                                              │
split_designer.design_split(hqi_gaps, division, days, tape_pairs)
        │  (R4.D: real HQI gaps now flow in; was empty dict)
        ▼
periodization.compute_cycle_mesocycle  ←── E2
        │
        ▼
macros.compute_macros(phase=ppm_sub_phase, …)  ←── E3
        │
        ▼
plan = {split, reasoning, unilateral_bias, weeks[14 or 16]}
```

Endpoints:

| Endpoint | Engine path | Writes |
|---|---|---|
| `GET /ppm/status` | profile only | no |
| `POST /ppm/evaluate` | E1 readiness + projection | no |
| `POST /ppm/attainability` | E1 honesty | no |
| `POST /ppm/start-cycle` | honesty → readiness → plan | `UserProfile.ppm_*` |
| `GET /ppm/plan/{week}` | re-runs plan build | no |
| `POST /ppm/checkpoint` | readiness + delta vs last | `PPMCheckpoint` |
| `GET /ppm/history` | read PPMCheckpoint | no |
| `POST /ppm/transition-to-comp` | disable PPM + set comp date | profile |
| `POST /ppm/disable` | turn PPM off | profile |

Mini-cut logic: if `metrics.bf_pct > OFFSEASON_BF_CEILING_*` the plan is
16 weeks (2-week mini-cut prepend); otherwise 14.

---

## 8. Cross-engine data flow

Key cross-engine couplings (the places where "one engine's output is
another engine's input"):

| Source | Consumer | Channel |
|---|---|---|
| E1 `muscle_gaps` → `HQILog.site_scores` | E2 `split_designer` | Per-site gap_cm drives need scores |
| E1 `prep_timeline.get_current_phase` | E2 `services/training` | Phase → volume modifier |
| E1 `prep_timeline.get_current_phase` | E3 `macros.compute_macros` | Phase → kcal/macro targets |
| E1 `body_fat.categorize_body_fat` | E3 `autoregulation.BF_FLOOR` check | Halt cut when floor hit |
| E3 `kinetic.prescribe_adjustment` | E4 `cardio` | Before dropping kcal, bump NEAT/cardio |
| E2 `ari.daily_score` | E2 `generate_program_sessions` | Volume autoregulation |
| E2 `recovery.can_train_muscle` | E2 `generate_program_sessions` | Skip muscle if unrecovered |

The important thing: **E2 never calls back into E1, and E3 never calls
back into E2**. Feedback is delivered by the next diagnostic run, not by
mid-prescription loops. This makes each engine individually testable.

---

## 9. API surface → engine mapping

Front-end widgets and the engines they consume:

| Frontend component | Endpoint | Engine path |
|---|---|---|
| Muscle Gaps widget | `POST /engine1/run-diagnostic` | E1 `muscle_gaps` |
| PDS history / trajectory | `GET /engine1/pds-history`, `GET /engine1/trajectory` | E1 `pds`, `trajectory` |
| Volumetric Ghost card | `POST /engine1/ghost-model` | E1 `volumetric_ghost` |
| Tier Readiness card | `POST /ppm/evaluate` | PPM + E1 `readiness` |
| Natural ceiling widget | `POST /ppm/attainability` | E1 `honesty` + `weight_cap` |
| Prep timeline | `GET /engine1/annual-calendar` | E1 `prep_timeline` |
| Program page (comp) | `GET /engine2/program`, `GET /engine2/session/:id` | E2 `generate_program_sessions` |
| Program page (PPM) | `GET /ppm/plan/:week` | PPM + E2 `split_designer` + E2 `periodization` |
| Prescription card | `GET /engine3/prescription/current` | E3 `macros` |
| Carb cycle widget | returned inside prescription | E3 `macros` |
| Peak week card | `POST /engine3/peak-week` | E3 `peak_week` |
| Cardio widget | `GET /engine4/cardio-plan` | E4 `cardio` |

---

## 10. Optimization surface

The engines' tunable decisions — where "maybe we should try X instead"
has the most leverage.

### Engine 1
- **HQI decay constant** (`_DECAY_K = 0.055` in `hqi.py`) controls how
  punishing a gap is. Calibrated to the weight-cap ideal; re-tune if the
  ideal ceiling shifts.
- **Division visibility weights** (`_DIVISION_VISIBILITY` in `hqi.py` +
  `muscle_gaps.py`) — if MP thigh weight bumps from 0.0 to 0.2, legs
  re-enter the gap ranker and the split designer will cluster them.
- **Casey Butt coefficients** (`weight_cap.py::compute_max_circumferences`)
  — conservative by modern natural standards. Advanced athletes sometimes
  exceed them in forearms/calves. Adjust with care; they anchor the
  honesty gate.
- **PDS division weights** (`pds.py::_DIVISION_WEIGHTS`) — moving Classic
  from aesthetic-45 / mass-25 toward aesthetic-40 / mass-30 would favor
  larger athletes; current weights favor the 1970s-style silhouette.
- **Mass-distribution threshold** (0.85 in `readiness.py`) — the 8th
  metric considers a site "failing" at <85% of ideal. Tightening this to
  0.90 makes the limiter-finder more aggressive.

### Engine 2
- **Volume landmarks** (`volume_landmarks.py`) — experience modifiers
  scale MEV/MAV/MRV proportionally. Bumping the novice scalar recovers
  some of the under-programmed volume for new lifters.
- **Per-muscle session cap** (`MAX_SETS_PER_MUSCLE_PER_SESSION = 10`) —
  raising permits higher-frequency low-volume splits.
- **`ASYMMETRY_UNILATERAL_CM = 1.5`** — tightening to 1.0 cm fires
  unilateral bias more often; widening to 2.5 cm suppresses it.
- **Need-score weights** inside `split_designer` — the balance of
  `gap_cm`, `division_importance`, and `illusion_multiplier` defines
  whether the engine prioritizes aesthetics, absolute mass, or
  athlete-specific lagging parts.
- **ARI weighting** (HRV 0.30 / sleep 0.20 / soreness 0.20 / HR 0.15 /
  wellness 0.15) — swapping to sleep-heavy (0.35) better suits athletes
  with unreliable HRV data.

### Engine 3
- **Adherence threshold** (85% in `autoregulation.py`) — strict coaches
  raise to 90%; permissive lower to 80%.
- **Kinetic target ranges** (`kinetic._TARGET_RATE_RANGES`) — aggressive
  cut ≤ −1.5 %BW/wk is supported if the user explicitly requests it.
- **Kcal/kg per phase** (`thermodynamic._KCAL_PER_KG_BY_PHASE`) —
  adjustments here shift the mass-change projection but not the
  prescription itself.
- **Peak week load/taper** (`peak_week.py`) — timing is hand-tuned; the
  carb amount is LBM-scaled.

### Engine 4
- **NEAT targets per phase** (offseason 8k / prep 12k / late 15k) — the
  strongest knob. Every +3k steps = ~150 kcal/day off-the-books.
- **Cardio cap** before mandating food increase — currently implicit;
  candidate for an explicit constant.

### PPM orchestrator
- **`OFFSEASON_BF_CEILING_*`** — the mini-cut trigger. Lowering (from
  16% to 14% for males) routes more cycles through the mini-cut path.
- **Cycle length (14 vs 16)** — driven by mini-cut status; a longer
  base cycle (e.g. 17 weeks) would give more mesocycle real estate per
  improvement block.

---

## 11. Known open design questions

- **Ghost vs aesthetic vectors drift.** `GHOST_VECTORS` and
  `DIVISION_VECTORS` are intentionally different but have no automated
  consistency check. A validator that prints the two projected weights
  side-by-side per division would catch the next drift.
- **HQI visibility weights** live in both `hqi.py` and `muscle_gaps.py`.
  Same values today, but they could drift. Move to a shared constant.
  (Tracked as M7 in CALCULATIONS.md.)
- **ARI → macros.** ARI affects Engine 2 volume but doesn't feed Engine
  3 — chronic low-ARI weeks could justify a small caloric nudge up
  (central fatigue often responds to glycogen), but the engines don't
  wire this yet.
- **Peak-week carb loading depends on the athlete's gut tolerance and
  training history.** Currently a one-size LBM scalar. A response-ratio
  pattern similar to `trajectory.personalized_trajectory` would improve
  the second prep forward.
- **Split designer's illusion multiplier** is only applied once, at
  design time. If the athlete's shoulder width changes materially
  during a multi-cycle PPM run, the designer won't re-weight unless the
  plan is regenerated. A per-cycle regeneration step at each checkpoint
  would fix this.
- **Symmetry multipliers are division-agnostic.** Bicep 600 is correct
  for Open/Classic but probably too high for Bikini where symmetry
  matters less than overall shape. Candidate for a division × site
  matrix.

---

## See also

- [`CALCULATIONS.md`](./CALCULATIONS.md) — formulas, constants, thresholds
- [`docs/VERIFY_ALGORITHMS.md`](./docs/VERIFY_ALGORITHMS.md) — hand-verification worksheets
- [`docs/GHOST_MODEL_VERIFICATION.md`](./docs/GHOST_MODEL_VERIFICATION.md) — Hanavan math checks
- [`docs/NUTRITION_CARDIO_ENGINE.md`](./docs/NUTRITION_CARDIO_ENGINE.md) — deeper E3/E4 dive
- [`docs/SYSTEM_REFERENCE.md`](./docs/SYSTEM_REFERENCE.md) — legacy (pre-Viltrum, pre-PPM, pre-E4) — **partially stale**
