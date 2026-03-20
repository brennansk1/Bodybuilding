# Coronado (CPOS) — System Reference

> Competitive Physique Optimization System: 3 engines, 6 divisions, full algorithm documentation.

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Engine 1: Diagnostic (Physique Assessment)](#engine-1-diagnostic)
3. [Engine 2: Training (Programming & Autoregulation)](#engine-2-training)
4. [Engine 3: Nutrition (Macro Prescription & Autoregulation)](#engine-3-nutrition)
5. [Division Vectors & Constants](#division-vectors--constants)
6. [Data Flows & Orchestration](#data-flows--orchestration)
7. [Cross-Engine Feedback Loops](#cross-engine-feedback-loops)
8. [Score Reference Table](#score-reference-table)
9. [File Locations](#file-locations)

---

## System Overview

Coronado is a three-engine system for competitive bodybuilders (NPC/IFBB) that computes athlete development across **diagnostic**, **training**, and **nutrition** domains. Every major subsystem is **division-specific**, personalizing ideals, exercise priorities, volume allocation, and nutrition profiles to 6 competitive divisions.

| Engine | Purpose | Key Outputs |
|--------|---------|------------|
| Engine 1 (Diagnostic) | Quantify physique development, identify gaps, project trajectory | PDS, Muscle Gaps, LCSA, Aesthetic Similarity |
| Engine 2 (Training) | Generate periodized programs, autoregulate daily volume | ARI, Custom Split, Volume Budget |
| Engine 3 (Nutrition) | Prescribe macros, adjust calories, peak week protocol | TDEE, Kinetic Rate, Adherence Lock |

**Supported Divisions**: Men's Open, Classic Physique, Men's Physique, Women's Figure, Women's Bikini, Women's Physique

---

## Engine 1: Diagnostic

### LCSA (Lean Cross-Sectional Area)

**File**: `engines/engine1/lcsa.py`

Converts tape circumferences to estimated muscle cross-section (cm²):

```
LCSA = (circumference / (2*pi))^2 * pi * k_site * (1 - bf_fraction)
```

**K-Site Shape Factors** (account for non-circular cross-sections):

| Site | K Factor |
|------|----------|
| Neck | 0.85 |
| Shoulders | 0.70 |
| Chest | 0.75 |
| Bicep | 0.90 |
| Forearm | 0.92 |
| Waist | 0.60 |
| Hips | 0.65 |
| Thigh | 0.80 |
| Calf | 0.88 |

- Averages bilateral measurements (left/right) automatically
- **Output**: Per-site LCSA + total LCSA (sum of all sites)

---

### Muscle Gaps (replaces HQI)

**File**: `engines/engine1/muscle_gaps.py`

Shows the athlete's **raw centimetre gap** from current lean muscle size to the division-specific genetic ceiling ideal. No abstract scores — only real measurements.

#### Output per site

| Field | Description |
|-------|-------------|
| `current_lean_cm` | Circumference after fat stripping (cm) |
| `ideal_lean_cm` | Division-specific target at genetic ceiling (cm) |
| `gap_cm` | How much lean tissue to add (positive = underdeveloped) |
| `pct_of_ideal` | Current as % of ideal (100 = at target) |
| `gap_type` | Category (see below) |

#### Gap Types

| Type | Condition | Meaning |
|------|-----------|---------|
| `add_muscle` | gap > 0.5 cm | Only progressive training closes this |
| `at_ideal` | within ±0.5 cm | Maintain current development |
| `above_ideal` | > 0.5 cm over (non-girth site) | Over-developed for division; re-balance |
| `reduce_girth` | > 0.5 cm over (waist/hips) | Fat loss + vacuum training |

#### Ideal Circumference Computation

```
Muscle sites:  ideal = casey_butt_max * division_ceiling_factor
Stay-small sites (waist, hips): ideal = division_ratio * height_cm
```

#### Aggregate Metrics

```
total_gap_cm     = sum of all positive gap_cm (total lean cm to add)
avg_pct_of_ideal = visibility-weighted average of pct_of_ideal across sites
```

**Division Visibility Weights** (sites hidden by stage attire are down-weighted in avg_pct_of_ideal):

| Division | Thigh | Hips | Calf | Forearm |
|----------|-------|------|------|---------|
| Men's Physique | 0.0 | 0.15 | 0.25 | 1.0 |
| Women's Bikini | 0.5 | 1.0 | 0.2 | 0.3 |
| Women's Figure | 1.0 | 1.0 | 0.8 | 0.8 |
| All others | 1.0 | 1.0 | 1.0 | 1.0 |

---

### Lean Adjustment Methods

**File**: `engines/engine1/body_fat.py`

Two strategies for stripping fat from tape measurements:

#### 1. Lean Girth Formula (Preferred — Site-Specific)

```
C_lean = C_total - (pi * skinfold_mm / 10)
```

Uses the skinfold caliper reading at the corresponding site. Far more accurate because fat distribution is site-specific (e.g., 5mm on bicep vs 15mm on abdomen).

**Site-to-Skinfold Mapping**:
| Girth Site | Skinfold Site |
|------------|---------------|
| Chest | Chest |
| Bicep | Bicep |
| Thigh | Thigh |
| Calf | Calf |
| Waist | Abdominal |
| Hips | Suprailiac |

#### 2. Global Fallback (When No Site Skinfold Available)

```
lean_circ = raw * sqrt(1 - bf_fraction)
```

Used for sites without matching skinfold data (neck, shoulders, forearm).

---

### Chest / Back Isolation

Standard chest tape wraps the entire torso — lats, rhomboids, and erectors inflate it. The system supports optional advanced measurements:

- **chest_relaxed** — lats actively relaxed (isolates pecs + medial back)
- **chest_lat_spread** — maximal lat engagement (full torso)
- **lat_spread_delta** = spread - relaxed (quantifies lat contribution)
- **back_width** — linear breadth between posterior axillary folds

When `chest_relaxed` is available, muscle gap analysis uses it instead of the standard chest tape for more accurate pectoral sizing.

---

### Body Fat Estimation

**File**: `engines/engine1/body_fat.py`

#### Multi-Method Composite (Primary)

The system blends three methods with weighted averaging and reports a confidence interval:

```
composite_bf = 0.50 * JP7 + 0.30 * Parrillo + 0.20 * Navy
confidence_interval = (min_estimate, max_estimate)
```

| Confidence Level | Spread |
|-----------------|--------|
| High | < 2% spread across methods |
| Medium | 2–4% spread |
| Low | > 4% spread |

#### Jackson-Pollock 7-Site

```
Sum7 = chest + midaxillary + tricep + subscapular + abdominal + suprailiac + thigh

Male density   = 1.112 - 0.00043499*S + 0.00000055*S^2 - 0.00028826*age
Female density = 1.097 - 0.00046971*S + 0.00000056*S^2 - 0.00012828*age

BF% = (495 / density) - 450   [Siri equation]
```

#### Parrillo 9-Site (Bodybuilding-Specific)

```
Sum9 = chest + tricep + subscapular + abdominal + suprailiac + thigh + bicep + lower_back + calf
BF%  = (Sum9 * 27) / body_weight_lbs
```

Better for tracking regional stubborn fat (lower back, calves).

#### US Navy Circumference (Fallback)

```
Male:   BF = 86.010*log10(waist-neck) - 70.041*log10(height) + 36.76
Female: BF = 163.205*log10(waist+hips-neck) - 97.684*log10(height) - 78.387
```

**Categories** (Male): contest <5%, peak 5-8%, lean 8-12%, moderate 12-16%, average 16-20%, above 20%+

---

### PDS (Physique Development Score)

**File**: `engines/engine1/pds.py`

Composite 0-100 score with **division-specific component weights**:

```
PDS = w_aesthetic * aesthetic + w_muscle_mass * muscle_mass + w_conditioning * conditioning + w_symmetry * symmetry
```

#### Division-Specific Weights

| Division | Aesthetic | Muscle Mass | Conditioning | Symmetry |
|----------|-----------|-------------|--------------|----------|
| Men's Open | 0.30 | 0.40 | 0.15 | 0.15 |
| Classic Physique | 0.45 | 0.25 | 0.15 | 0.15 |
| Men's Physique | 0.40 | 0.20 | 0.25 | 0.15 |
| Women's Bikini | 0.30 | 0.15 | 0.35 | 0.20 |
| Women's Figure | 0.35 | 0.25 | 0.25 | 0.15 |
| Women's Physique | 0.35 | 0.35 | 0.15 | 0.15 |

#### Component Formulas

| Component | Formula | Notes |
|-----------|---------|-------|
| Aesthetic | 50% cosine similarity + 50% RMSE penalty | Cosine alone is scale-invariant; RMSE catches under-developed proportions |
| Muscle Mass | min(100, LCSA / ceiling * 100) | Ceiling: 20 cm²/cm height (male), 14 (female) |
| Conditioning | 80% BF score + 20% visual indicators | Quadratic BF penalty; visual: vascularity/hardness/striations (1-10 scale) |
| Symmetry | max(0, 100 - bilateral_deviation * 500) | Pairs: bicep, forearm, thigh, calf |

Conditioning BF score:
```
deviation = abs(body_fat_pct - phase_ideal_bf)
bf_score  = max(0, 100 - 0.5 * deviation^2)
```

**Phase Ideal BF** (male): contest 4%, peak 5%, cut 8%, offseason 12%, bulk 15%

**Tier Bands**:

| Tier | Score Range |
|------|-------------|
| Elite | 85-100 |
| Advanced | 70-84 |
| Intermediate | 50-69 |
| Novice | 0-49 |

---

### Bilateral Symmetry

**File**: `engines/engine1/pds.py`

```python
pairs = [bicep, forearm, thigh, calf]
deviation = abs(left - right) / avg
symmetry_score = max(0, 100 - avg_deviation * 500)
```

Per-pair breakdown includes: `left_cm`, `right_cm`, `diff_cm`, `deviation_pct`, `dominant_side`.
Lagging sides flagged when deviation > 2%.

---

### Aesthetic Vector

**File**: `engines/engine1/aesthetic_vector.py`

```
proportion = circumference / height       (per site)
delta      = ideal_ratio - actual_ratio   (positive = underdeveloped)
priority   = normalized delta * visibility_weight
similarity = cosine(actual_vector, ideal_vector)
```

Priority scores drive training volume allocation — high-priority (lagging) sites get more volume.

---

### Weight Cap

**File**: `engines/engine1/weight_cap.py`

Casey Butt formula for maximum natural lean body mass:

```
Male:   max_LBM_lbs = height_in^1.5 * (sqrt(wrist_in)/22.667 + sqrt(ankle_in)/17.010) * (1 + bf%/224)
Female: max_LBM_lbs = [same structure with coefficients /25.0, /19.0] * 0.85

stage_weight    = max_LBM / (1 - bf_fraction)    [at 5% BF]
offseason_weight = max_LBM / (1 - 0.12)          [male offseason]
```

Default structural anchors: wrist 17.8cm (male), ankle 23.0cm (male).

---

### Trajectory Predictor

**File**: `engines/engine1/trajectory.py`

Projects PDS over N weeks using asymptotic decay:

```
PDS(t) = ceiling - (ceiling - current) * e^(-k*t)
```

#### Growth Rate by Experience

| Experience | Base k |
|------------|--------|
| <2 years | 0.04 (fast) |
| 2-5 years | 0.025 |
| 5-10 years | 0.015 |
| 10+ years | 0.008 (slow) |

#### Individual Response Profiling

After ≥3 data points, the system compares actual PDS gain to model-predicted gain:

```
response_ratio = actual_pds_gain / predicted_pds_gain
```

| Category | Ratio Range | Adjustment |
|----------|-------------|------------|
| High Responder | > 1.2 | k × 1.2 |
| Normal Responder | 0.8–1.2 | k unchanged |
| Low Responder | < 0.8 | k × 0.8 |

Personalized trajectory scales `k` by response_ratio to reflect the athlete's actual adaptation rate.

---

### Feasibility Engine

**File**: `engines/engine1/feasibility.py`

```
max_weekly_gain = [1.0, 0.5, 0.25, 0.1]  by experience level
estimated_weeks = gap / max_weekly_gain
feasible = estimated_weeks <= available_weeks
```

---

### Prep Timeline & Annual Calendar

**File**: `engines/engine1/prep_timeline.py`

| Phase | Weeks Out | Calorie Modifier |
|-------|-----------|-----------------|
| Offseason | >20 | 1.15 |
| Lean Bulk | 13-20 | 1.10 |
| Cut | 4-12 | 0.85 |
| Peak Week | 1-3 | 0.80 |
| Contest | 0 | 1.00 |
| Restoration | 1-12 post-show | 0.85 → 1.00 ramp |

**Restoration Phase** (1-84 days post-show):
- Calorie modifier ramps from 0.85 → 1.00 over 12 weeks (+100-150 kcal/week)
- Protein tapers from 2.7 → 2.0 g/kg over 12 weeks
- Reduces metabolic adaptation and cortisol from extreme prep

**Annual Calendar** (`generate_annual_calendar(competition_date)`):
- Works backwards from show date to construct a full 52-week plan
- Returns list of phase blocks with start/end dates and descriptions
- Used by the frontend Competition Countdown card

---

## Engine 2: Training

### ARI (Autonomic Readiness Index)

**File**: `engines/engine2/ari.py`

Daily readiness score (0-100):

```
ARI = 0.35*HRV + 0.25*Sleep + 0.25*Soreness + 0.15*HR
```

| Component | Calculation |
|-----------|-------------|
| HRV | current_RMSSD / baseline_RMSSD * 100 (capped 100) |
| Sleep | (quality_1_10 - 1) / 9 * 100 |
| Soreness | (10 - soreness_1_10) / 9 * 100 |
| HR | 100 - clamp(deviation_from_baseline * 5, -25, 75) |

**Readiness Zones**:

| Zone | Score | Volume Modifier |
|------|-------|-----------------|
| Green | 70-100 | 1.0-1.1x |
| Yellow | 40-69 | 0.8-1.0x |
| Red | 0-39 | 0.6-0.8x |

Volume modifier: `mod = 0.6 + (ARI/100) * 0.5`

---

### Custom Split Designer

**File**: `engines/engine2/split_designer.py`

Builds optimal training splits from scratch using muscle gap priorities, division importance, and recovery constraints.

#### Need Score (0-10 per muscle)

```
need = 0.6 * gap_score + 0.4 * importance_score
```

Hidden muscles (importance <= 0.05) capped at 3.0.

#### Division Importance Weights

| Muscle | Men's Open | Men's Physique | Women's Bikini |
|--------|-----------|----------------|----------------|
| Chest | 1.0 | 1.0 | 0.3 |
| Side Delt | 1.0 | 1.2 | 0.5 |
| Quads | 1.0 | 0.0 | 0.6 |
| Glutes | 0.8 | 0.0 | 1.2 |
| Back | 1.0 | 1.0 | 0.5 |

#### Desired Frequency (from need score)

| Need Score | Frequency |
|------------|-----------|
| >= 7.0 | 3x/week |
| 4.5 - 7.0 | 2x/week |
| < 4.5 | 1x/week |

#### Volume Budget

```
t = need / 10.0
volume = MEV + t * (ceiling - MEV)
```

Division importance caps the ceiling:
- imp < 0.3: ceiling = MEV to MAV range
- imp 0.3-0.8: ceiling = MAV to MRV range
- imp >= 0.8: ceiling = full MRV

#### Construction: Cluster-then-Pack

1. Group muscles into synergistic clusters (Push, Pull, Legs, Shoulders, Arms)
2. Assign clusters to training days using archetypes (2-7 day templates)
3. Repeat high-need clusters on multiple days
4. Add accessories (abs, calves, forearms) to days with headroom
5. Auto-label days from muscle content

---

### Periodization

**File**: `engines/engine2/periodization.py`

#### Primary Strategy: Daily Undulating Periodization (DUP)

DUP is the default for athletes with < 5 years experience. Each week rotates through three intensity profiles within the same mesocycle:

| Day Type | Intensity | Rep Range | RIR | Sets |
|----------|-----------|-----------|-----|------|
| Heavy | 80-85% 1RM | 4-6 | 2 | 4 |
| Moderate | 70-75% 1RM | 8-12 | 2 | 3-4 |
| Light | 60-65% 1RM | 15-20 | 1 | 3 |

DUP simultaneously develops strength, hypertrophy, and muscular endurance — superior stimulus variety vs. linear progression.

#### Advanced Athletes: Block Periodization (>5 years)

```
3 weeks accumulation (moderate intensity, high volume)
→ 3 weeks intensification (high intensity, moderate volume)
→ 1 week realization (peak intensity, low volume)
```

#### ARI-Aware Deloads (replaces rigid every-4-weeks)

```
should_deload = avg_ari_last_week < 55
```

If average ARI over the last 7 days falls below 55, a deload is triggered regardless of the week count. Deload volume: 50% of base sets. This prevents forced deloads when an athlete is adapting well and prevents skipping deloads when recovery is compromised.

#### Volume Landmarks (sets/week)

| Muscle | MEV | MAV | MRV |
|--------|-----|-----|-----|
| Chest | 6 | 12 | 22 |
| Back | 8 | 16 | 25 |
| Shoulders | 6 | 16 | 22 |
| Biceps | 4 | 14 | 20 |
| Triceps | 4 | 14 | 20 |
| Quads | 6 | 12 | 20 |
| Hamstrings | 4 | 10 | 16 |
| Glutes | 4 | 10 | 18 |
| Calves | 6 | 16 | 22 |

#### Recovery Windows

| Category | Sites | Min Hours |
|----------|-------|-----------|
| Large | Back, Quads, Chest, Hamstrings, Glutes | 48 |
| Medium | Delts, Biceps, Triceps | 36 |
| Small | Calves, Forearms, Abs, Traps | 24 |

---

### Exercise Selection

**File**: `engines/engine2/biomechanical.py`

#### Stimulus-to-Fatigue Ratio (SFR)

```
SFR = efficiency / fatigue_ratio
Score = SFR * priority_score_for_muscle
```

#### Priority Cascade (`_allocate_sets`)

1. Fill division-specific priority slots (ordered exercise list per muscle)
2. Gap-adjusted cap: top-priority exercise for severely lagging muscles gets boost
3. Rotation penalty: 30% SFR reduction for exercises used in previous mesocycle
4. Fallback: biomechanical SFR sort for remaining sets
5. Unilateral preference: if >5% bilateral asymmetry, prefer dumbbell/cable

#### Movement Pattern Diversity

The system tracks 9 movement pattern categories per muscle group:

```
MOVEMENT_PATTERNS = {
    "horizontal_push", "vertical_push", "horizontal_pull", "vertical_pull",
    "squat_pattern", "hinge_pattern", "carry", "isolation_curl", "isolation_extension"
}
```

`ensure_pattern_diversity(selected_exercises, muscle_group)` checks which patterns are already covered and flags any critical missing patterns, preventing over-reliance on a single movement type (e.g., only horizontal pressing for chest).

#### Equipment & Injury Filtering

Exercises are filtered against the athlete's profile before selection:
- `available_equipment`: only exercises matchable to owned equipment are shown
- `disliked_exercises`: excluded entirely
- `injury_history`: contraindicated exercises for each injury area are excluded

#### Compound Overflow Credits

| Pattern | Secondary Muscles |
|---------|-------------------|
| Push | Triceps 0.5x, Shoulders 0.3x |
| Pull | Biceps 0.5x, Traps 0.2x |
| Squat | Glutes 0.4x, Hamstrings 0.2x |
| Hinge | Glutes 0.5x, Back 0.2x |

---

### Resistance Progression

**File**: `engines/engine2/resistance.py`

Double-progression model:

```
IF current_reps >= target_reps AND RPE <= 8.0:
    increase weight by increment, reset reps to floor
ELIF RPE >= 9.5:
    hold weight and reps (consolidation)
ELSE:
    keep weight, add 1 rep
```

Auto-1RM Estimation: when strength baselines are stale > 90 days, the system estimates 1RM from the most recent `StrengthLog` entry using the Epley formula:
```
1RM = weight * (1 + reps / 30)
```

| Load Type | Increment | Rep Range |
|-----------|-----------|-----------|
| Barbell (compound) | 5.0 kg | 5-8 |
| Barbell (isolation) | 2.5 kg | 8-12 |
| Plate-loaded machine | 10.0 kg | 8-15 |
| Machine pin / Cable | 2.5 kg | 10-15 |
| Dumbbell | 2.5 kg | 8-15 |
| Bodyweight | +2.5 kg vest at rep ceiling | Varies |

---

### Recovery Estimation

**File**: `engines/engine2/recovery.py`

```
base_hours    = min + (max - min) * intensity
volume_factor = 1.0 + max(0, sets - 4) * 0.05
ari_factor    = 1.30 - (ARI/100) * 0.45

recovery_hours = base_hours * volume_factor * ari_factor
```

#### CNS / Systemic Fatigue Model

```
systemic_fatigue = sum of per-exercise fatigue scores (0-100)
```

- `check_daily_fatigue_budget(planned_exercises)`: returns `{within_budget, fatigue_score, warnings}` before a session is accepted
- `check_consecutive_heavy_days(prev_fatigue, current_fatigue)`: prevents back-to-back high CNS-demand days

#### Phase Volume Modifier (E3→E2 Cross-Engine Signal)

| Phase | Volume Multiplier |
|-------|-------------------|
| Cut | 0.85x |
| Peak Week | 0.70x |
| Contest | 0.50x |
| Restoration | 0.75x |
| Offseason / Bulk | 1.00x |

Reduces training volume automatically when caloric deficit limits recovery capacity.

---

### Warm-Up Scheme

First exercise per muscle group:

| % of Working Weight | Reps |
|---------------------|------|
| 40% | 10 |
| 60% | 5 |
| 75% | 3 |
| 85% | 1 |

---

## Engine 3: Nutrition

### TDEE & Macro Prescription

**File**: `engines/engine3/macros.py`

#### TDEE (Mifflin-St Jeor)

```
Male BMR   = 10*W + 6.25*H - 5*A + 5
Female BMR = 10*W + 6.25*H - 5*A - 161
TDEE = BMR * activity_multiplier  (1.2-1.9 PAL)
```

#### Phase Caloric Adjustments

| Phase | Adjustment |
|-------|------------|
| Bulk | TDEE + 400 kcal |
| Maintain | TDEE + 0 |
| Cut | TDEE - 400 kcal |
| Peak | TDEE - 700 kcal |
| Restoration | TDEE - 15% → TDEE (ramp over 12 weeks) |

#### Protein Targets (g/kg total body weight)

| Phase | Protein | Rationale |
|-------|---------|-----------|
| Bulk | 2.0 g/kg | Surplus reduces protein need; carbs drive anabolism |
| Maintain | 2.0 g/kg | Standard |
| Cut | 2.4 g/kg | Blunts catabolism in deficit |
| Peak | 2.7 g/kg | Extreme deficit demands max protection |
| Restoration | 2.7 → 2.0 g/kg | Tapers over 12 weeks as metabolism normalizes |

Clamped: 1.6-2.7 g/kg TBW (ISSN/Morton et al. range)

**Fat Floor**: 1.0 g/kg TBW (required for testosterone precursor biosynthesis)

**Carbs**: Remainder after protein + fat kcals subtracted from target

#### Division-Specific Overrides

| Division | Bulk Protein | Cut Protein | Carb Cycling | Fat Floor | Meals/Day |
|----------|-------------|-------------|--------------|-----------|-----------|
| Men's Open | 1.8 | 2.4 | 25% | 0.85 | 5 |
| Men's Physique | 2.0 | 2.4 | 30% | 0.75 | 5 |
| Women's Bikini | 1.8 | 2.2 | 35% | 0.80 | 4 |
| Women's Figure | 1.9 | 2.3 | 30% | 0.80 | 5 |

#### Carb Cycling (Training vs Rest Days)

```
Training day: +20% carbs, fat adjusted down
Rest day:     -20% carbs, fat adjusted up
```

#### Peri-Workout Carb Allocation

| Window | % of Daily Carbs |
|--------|------------------|
| Pre-workout (2-3h before) | 35% |
| Intra-workout | 10% |
| Post-workout (within 1h) | 25% |
| Other meals | 30% |

---

### Kinetic Rate-of-Change

**File**: `engines/engine3/kinetic.py`

**EWMA Weight Tracking** (replaces simple linear slope):

```
EWMA(t) = alpha * weight(t) + (1 - alpha) * EWMA(t-1)     [alpha = 0.3]
rate_kg_per_week = (EWMA_latest - EWMA_oldest) / weeks
```

Also computes a 7-day rolling average for comparison with EWMA.

**Menstrual Cycle Awareness** (female athletes):
- Luteal phase (days 15-28): `water_retention_flag = True`
- When flag is active, system notes that scale weight is transiently elevated and should not trigger calorie reductions

**Target Rates** (fraction of body weight per week):

| Phase | Target Rate |
|-------|-------------|
| Bulk | +0.25 to +0.5% BW/week |
| Cut | -0.5 to -1.0% BW/week |
| Maintain | +/- 0.1% BW/week |
| Peak | -0.5 to -1.0% BW/week |

**Adjustment Logic**:
- If actual rate within 10% of target: no change
- Otherwise: 100-200 kcal adjustment scaled by deviation
- Carbs are the flexible macro

---

### Autoregulation

**File**: `engines/engine3/autoregulation.py`

#### Adherence Lock

| Adherence | Action |
|-----------|--------|
| < 85% | Prescription LOCKED |
| 85-90% | Eligible for adjustments |
| >= 90% + stall | Nudge +/- 100 kcal |

#### Refeed Scheduling (During Cuts)

```
Base interval: 14 days
Leaner athletes (<10% male, <18% female): 7 days
Interpolation between 7-14 days based on body fat

Refeed carb multiplier:
  <10% BF: 2.0x
  >=20% BF: 1.5x
```

#### ARI-Triggered Emergency Refeed (E2→E3 Cross-Engine Signal)

```
IF avg(recent_ari_scores[-3:]) < 55 AND phase in ["cut", "peak"] AND bf_pct < threshold:
    trigger emergency refeed
```

When ARI averages below 55 for 3+ consecutive days during a caloric deficit, the system triggers a 1-day refeed regardless of the scheduled interval. This addresses performance degradation from excessive energy restriction.

---

### Metabolic Adaptation

**File**: `engines/engine3/thermodynamic.py`

Long deficits suppress metabolic rate. The system models this with an adaptation factor:

```
adaptation_factor = 1.0 - 0.01 * min(weeks_in_deficit, 15)
adapted_TDEE      = TDEE * adaptation_factor
```

Maximum adaptation: -15% at 15+ weeks in deficit. This ensures calorie prescriptions account for the real suppression rather than assuming static TDEE.

---

### Peak Week Protocol

**File**: `engines/engine3/peak_week.py`

7-day carb/water/sodium manipulation (show assumed Saturday):

| Day | Phase | Carbs (g/kg LBM) | Sodium (mg) | Water (mL) |
|-----|-------|------------------|-------------|------------|
| Mon | Depletion 1 | 0.5 | 1200 | 4000 |
| Tue | Depletion 2 | 0.3 | 500 | 4000 |
| Wed | Transition | 2.0 | 1200 | 3000 |
| Thu | Load 1 | 5.0 | 500 | 2000 |
| Fri | Load 2 | 4.0 | 500 | 2000 |
| Sat | Show Day | 3.0 | 500 | 2000 |
| Sun | Recovery | 3.5 | 2300 | 4000 |

Protein constant at 2.2 g/kg LBM throughout.

---

### Thermodynamic Projection

**File**: `engines/engine3/thermodynamic.py`

```
total_surplus (kcal) = daily_balance * 7 * weeks
weight_change (kg)   = total_surplus / 7700
```

Safety floors: 1500 kcal/day (male), 1200 kcal/day (female).

---

## Division Vectors & Constants

**File**: `constants/divisions.py`

### Ideal Proportions (circumference / height ratios)

| Division | Neck | Shoulders | Chest | Bicep | Forearm | Waist | Hips | Thigh | Calf | S/W Ratio |
|----------|------|-----------|-------|-------|---------|-------|------|-------|------|-----------|
| Men's Open | 0.243 | 0.618 | 0.550 | 0.230 | 0.175 | 0.447 | 0.520 | 0.340 | 0.230 | 1.382 |
| Classic Physique | 0.238 | 0.600 | 0.540 | 0.220 | 0.170 | 0.432 | 0.510 | 0.325 | 0.225 | 1.389 |
| Men's Physique | 0.230 | 0.590 | 0.520 | 0.210 | 0.165 | 0.420 | 0.490 | 0.300 | 0.215 | 1.405 |
| Women's Figure | 0.195 | 0.530 | 0.490 | 0.170 | 0.145 | 0.395 | 0.530 | 0.320 | 0.210 | 1.342 |
| Women's Bikini | 0.190 | 0.500 | 0.470 | 0.155 | 0.138 | 0.385 | 0.540 | 0.330 | 0.205 | 1.299 |
| Women's Physique | 0.200 | 0.550 | 0.500 | 0.185 | 0.152 | 0.405 | 0.520 | 0.310 | 0.215 | 1.358 |

### Division Ceiling Factors (% of Casey Butt genetic max for ideal lean circumferences)

| Division | Neck | Shoulders | Chest | Bicep | Forearm | Thigh | Calf |
|----------|------|-----------|-------|-------|---------|-------|------|
| Men's Open | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| Classic Physique | 0.96 | 0.97 | 0.97 | 0.96 | 0.95 | 0.95 | 0.95 |
| Men's Physique | 0.88 | 0.95 | 0.90 | 0.92 | 0.88 | 0.78 | 0.80 |
| Women's Figure | 0.80 | 0.85 | 0.82 | 0.80 | 0.78 | 0.82 | 0.80 |
| Women's Bikini | 0.72 | 0.75 | 0.74 | 0.70 | 0.68 | 0.75 | 0.72 |
| Women's Physique | 0.85 | 0.90 | 0.88 | 0.87 | 0.85 | 0.87 | 0.85 |

---

## Data Flows & Orchestration

### Full Diagnostic Pipeline

```
User Input
  |-- Tape measurements (13+ sites, bilateral)
  |-- Skinfold calipers (7-10 sites)
  |-- Body weight
  |-- Profile (height, age, sex, wrist, ankle, division, competition date)

run_full_diagnostic()
  1. Extract tape dict, average bilateral sites
  2. Use chest_relaxed for muscle gap analysis (if available) to isolate pecs from lats
  3. Estimate body fat: JP7/Parrillo/Navy composite with confidence interval -> Navy fallback
  4. Apply lean-girth formula per site (C_lean = C - pi*S/10) where skinfold available
  5. Global sqrt(1-bf) fallback for remaining sites
  6. Compute LCSA (raw tape + BF-corrected)
  7. Compute weight cap + max circumferences (Casey Butt)
  8. Compute Muscle Gaps (ideal = max * ceiling_factor, raw cm gap, pct_of_ideal)
  9. Compute aesthetic proportions (cosine similarity, delta, priorities)
  10. Compute PDS (division-specific weights for aesthetic/mass/conditioning/symmetry)
  11. Compute symmetry details (per-pair bilateral breakdown)
  12. Project 52-week trajectory (asymptotic decay, personalized by response ratio)
  13. Determine prep phase (including restoration phase post-show)
  14. Build annual calendar from competition date
  15. Determine phase recommendation (cross-engine E1→E3)
  16. Build advanced measurements (lat delta, back width, thigh regionality)
  17. Persist: LCSALog, HQILog (stores muscle_gaps data), PDSLog

Output: diagnostic dict with all computed values
```

### Training Program Generation

```
generate_program_sessions()
  1. Load latest muscle gap scores -> muscle priorities
  2. Load profile -> division, training experience, available_equipment,
     disliked_exercises, injury_history
  3. Detect prep phase -> apply phase volume modifier (cut=0.85, peak=0.70, etc.)
  4. Design custom split:
     - Need scores (0.6*gap + 0.4*importance)
     - Desired frequency (3/2/1x per week)
     - Volume budget (MEV->MRV interpolation with division ceiling)
     - Cluster-then-pack algorithm
  5. Filter exercises:
     - Equipment filter (match available equipment)
     - Disliked exercise exclusion
     - Injury contraindication exclusion
     - Movement pattern diversity check
  6. Estimate 1RM: use baselines; auto-estimate from recent StrengthLog if stale >90 days
  7. Generate mesocycle:
     - DUP (<5yr experience): heavy/moderate/light day rotation
     - Block (>5yr experience): accumulation -> intensification -> realization
     - ARI-aware deloads (avg ARI < 55 triggers deload, replaces rigid 4-week schedule)
  8. For each session:
     - Aggregate per-muscle sets (with phase volume modifier applied)
     - Check recovery gates (48h/36h/24h)
     - Allocate exercises via priority cascade
     - Check daily fatigue budget
     - Generate warm-up sets (40/60/75/85%)
     - Create TrainingSet records

Output: TrainingProgram + TrainingSessions + TrainingSets
```

### Daily Training Autoregulation

```
ARI Computation
  1. HRV component: RMSSD / baseline * 100
  2. Sleep component: linear 1-10 -> 0-100
  3. Soreness component: inverted 1-10 -> 0-100
  4. HR component: deviation penalty
  5. Weighted sum -> ARI score -> zone -> volume modifier (0.6-1.1x)
  6. ARI < 55 for 3+ days during cut -> trigger emergency refeed (E2→E3)
  7. avg ARI last week < 55 -> trigger deload (E2 internal)
```

### Nutrition Adjustment Cycle

```
Weekly Check-In
  1. Compute EWMA + 7-day rolling rate of change (kg/week)
  2. Flag water retention if female in luteal phase (days 15-28)
  3. Compare to phase target rate
  4. Apply metabolic adaptation: adapted_TDEE = TDEE * (1 - 0.01 * min(weeks_in_deficit, 15))
  5. Check adherence:
     - <85%: lock prescription
     - >=90% + stall: nudge +/- 100 kcal
  6. If deviation >10%: adjust 100-200 kcal
  7. Carbs are the flexible macro (protein/fat held stable)
  8. Check ARI-triggered refeed condition
```

---

## Cross-Engine Feedback Loops

| Signal | From | To | Mechanism |
|--------|------|----|-----------|
| Phase Recommendation | E1 Diagnostic | E3 Nutrition | `_recommend_phase()` reads muscle gaps + PDS + BF → suggests bulk/cut/maintain |
| Phase Volume Modifier | E3 Phase | E2 Training | Cut/peak reduces training volume by 0.85x/0.70x |
| ARI Emergency Refeed | E2 ARI | E3 Autoregulation | avg ARI < 55 for 3 days during cut triggers refeed |
| ARI Deload | E2 ARI (internal) | E2 Volume | avg ARI < 55 triggers deload regardless of week count |
| Response Profiling | E1 PDS History | E1 Trajectory | Actual vs. predicted gain personalizes future k (growth rate) |

---

## Score Reference Table

| Score | Range | Source | Description |
|-------|-------|--------|-------------|
| PDS | 0-100 | Engine 1 | Overall physique development (composite, division-weighted) |
| Muscle Gap (per site) | cm | Engine 1 | Raw lean circumference gap from current to ideal |
| % of Ideal (per site) | 0-100% | Engine 1 | Current lean cm as % of division-specific genetic ceiling |
| avg_pct_of_ideal | 0-100% | Engine 1 | Visibility-weighted average across all sites |
| LCSA (total) | cm² | Engine 1 | Total lean cross-sectional area |
| Aesthetic Similarity | 0-1 | Engine 1 | Cosine similarity to division ideal vector |
| Conditioning | 0-100 | Engine 1 | BF deviation + visual indicator score |
| Symmetry | 0-100 | Engine 1 | Bilateral variance penalty (pairs: bicep, forearm, thigh, calf) |
| Muscle Mass | 0-100 | Engine 1 | LCSA relative to height-adjusted ceiling |
| ARI | 0-100 | Engine 2 | Autonomic readiness for training |
| Need Score | 0-10 | Engine 2 | Per-muscle training priority (gap + importance) |
| SFR | 0+ | Engine 2 | Exercise stimulus-to-fatigue ratio |

---

## File Locations

### Engine 1 (Diagnostic)

| Module | Path |
|--------|------|
| Muscle Gaps | `backend/app/engines/engine1/muscle_gaps.py` |
| LCSA | `backend/app/engines/engine1/lcsa.py` |
| PDS | `backend/app/engines/engine1/pds.py` |
| Aesthetic Vector | `backend/app/engines/engine1/aesthetic_vector.py` |
| Weight Cap | `backend/app/engines/engine1/weight_cap.py` |
| Body Fat | `backend/app/engines/engine1/body_fat.py` |
| Trajectory | `backend/app/engines/engine1/trajectory.py` |
| Feasibility | `backend/app/engines/engine1/feasibility.py` |
| Prep Timeline | `backend/app/engines/engine1/prep_timeline.py` |

### Engine 2 (Training)

| Module | Path |
|--------|------|
| ARI | `backend/app/engines/engine2/ari.py` |
| Split Designer | `backend/app/engines/engine2/split_designer.py` |
| Periodization | `backend/app/engines/engine2/periodization.py` |
| Biomechanical | `backend/app/engines/engine2/biomechanical.py` |
| Resistance | `backend/app/engines/engine2/resistance.py` |
| Recovery | `backend/app/engines/engine2/recovery.py` |

### Engine 3 (Nutrition)

| Module | Path |
|--------|------|
| Macros | `backend/app/engines/engine3/macros.py` |
| Kinetic | `backend/app/engines/engine3/kinetic.py` |
| Autoregulation | `backend/app/engines/engine3/autoregulation.py` |
| Thermodynamic | `backend/app/engines/engine3/thermodynamic.py` |
| Peak Week | `backend/app/engines/engine3/peak_week.py` |

### Constants & Services

| Module | Path |
|--------|------|
| Division Vectors | `backend/app/constants/divisions.py` |
| Diagnostic Service | `backend/app/services/diagnostic.py` |
| Training Service | `backend/app/services/training.py` |

### API Routers

| Router | Path | Key Endpoints |
|--------|------|---------------|
| Engine 1 | `backend/app/routers/engine1.py` | `/run`, `/pds`, `/muscle-gaps`, `/symmetry`, `/phase-recommendation`, `/annual-calendar`, `/aesthetic-vector`, `/weight-cap`, `/feasibility`, `/diagnostic` |
| Engine 2 | `backend/app/routers/engine2.py` | `/ari`, `/volume-allocation`, `/program/generate`, `/session/{date}` |
| Engine 3 | `backend/app/routers/engine3.py` | `/prescription/current`, `/adherence`, `/autoregulation`, `/meal-plan` |
