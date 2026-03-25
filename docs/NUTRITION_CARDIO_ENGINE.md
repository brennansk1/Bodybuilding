# Engine 3 (Nutrition Controller) & Engine 4 (Cardio & NEAT) -- Algorithmic Specification

> **CPOS v4.0 Development Reference**
> Last updated: 2026-03-23

---

## Table of Contents

1. [Engine 3 Architecture Overview](#1-engine-3-architecture-overview)
2. [TDEE Calculation](#2-tdee-calculation)
3. [Phase-Specific Macro Prescription](#3-phase-specific-macro-prescription)
4. [Dynamic Fat Floor Phasing](#4-dynamic-fat-floor-phasing)
5. [Weekly-Neutral Carb Cycling](#5-weekly-neutral-carb-cycling)
6. [Chrono-Nutrient Meal Planning](#6-chrono-nutrient-meal-planning)
7. [Session-Matched Intra-Workout HBCD Scaling](#7-session-matched-intra-workout-hbcd-scaling)
8. [Division-Specific Nutrition Profiles](#8-division-specific-nutrition-profiles)
9. [Thermodynamic Energy Balance](#9-thermodynamic-energy-balance)
10. [Metabolic Adaptation Modeling](#10-metabolic-adaptation-modeling)
11. [Autoregulation System](#11-autoregulation-system)
12. [Refeed Scheduling](#12-refeed-scheduling)
13. [ARI-Triggered Emergency Refeeds](#13-ari-triggered-emergency-refeeds)
14. [Division BF Floor (Halt-Cut Logic)](#14-division-bf-floor-halt-cut-logic)
15. [GI Distress Routing](#15-gi-distress-routing)
16. [Reactive Peak Week Controller](#16-reactive-peak-week-controller)
17. [Post-Show Restoration Protocol](#17-post-show-restoration-protocol)
18. [Engine 4: Energy Flux Model](#18-engine-4-energy-flux-model)
19. [Engine 4: NEAT Step Count Titration](#19-engine-4-neat-step-count-titration)
20. [Engine 4: Active Cardio Periodization](#20-engine-4-active-cardio-periodization)
21. [Engine 4: ARI-Aware Recovery Adjustments](#21-engine-4-ari-aware-recovery-adjustments)
22. [Cross-Engine Data Flow Diagram](#22-cross-engine-data-flow-diagram)

---

## 1. Engine 3 Architecture Overview

Engine 3 is the **Nutrition Controller** -- it translates an athlete's biometric state, training phase, and competition division into a precise daily macronutrient prescription. It operates as a pure math layer (no DB or HTTP dependencies) composed of five submodules:

| Submodule | File | Responsibility |
|-----------|------|----------------|
| **Macros** | `engine3/macros.py` | TDEE computation, macro prescription, carb cycling, chrono-nutrient meal planning, division profiles, HBCD scaling |
| **Thermodynamic** | `engine3/thermodynamic.py` | Energy balance tracking, weight-change projection, caloric floor enforcement, metabolic adaptation modeling |
| **Kinetic** | `engine3/kinetic.py` | Rate-of-change analysis (EWMA-smoothed), target rate derivation, caloric adjustment when rate deviates |
| **Autoregulation** | `engine3/autoregulation.py` | Adherence lock, diet breaks, refeed scheduling, ARI-triggered emergency refeeds, GI distress routing, BF floor halt-cut |
| **Peak Week** | `engine3/peak_week.py` | 7-day carb/water/sodium manipulation protocol, reactive condition-based adjustments |

**Design principle:** Every function is stateless and deterministic. The caller (router/service layer) is responsible for fetching athlete data from the database and passing it into these pure functions.

---

## 2. TDEE Calculation

Engine 3 uses a dual-formula approach: **Katch-McArdle** when lean body mass (LBM) is available (preferred for muscular athletes), falling back to **Mifflin-St Jeor** when LBM is unknown.

### Katch-McArdle (Primary)

```
BMR = 370 + (21.6 x LBM_kg)
TDEE = BMR x activity_multiplier
```

**Coaching rationale:** Katch-McArdle is more accurate for muscular athletes because it accounts for lean mass directly. Height/weight-based formulas systematically overestimate BMR for athletes with above-average muscle mass, and underestimate for those with very low body fat.

**Example:** A 90 kg male at 12% body fat (LBM = 79.2 kg):
```
BMR = 370 + (21.6 x 79.2) = 370 + 1710.7 = 2080.7 kcal
```

### Mifflin-St Jeor (Fallback)

```
Male:   BMR = (10.0 x weight_kg) + (6.25 x height_cm) - (5.0 x age) + 5.0
Female: BMR = (10.0 x weight_kg) + (6.25 x height_cm) - (5.0 x age) - 161.0
TDEE = BMR x activity_multiplier
```

**Example:** A 90 kg, 180 cm, 28-year-old male:
```
BMR = (10 x 90) + (6.25 x 180) - (5 x 28) + 5 = 900 + 1125 - 140 + 5 = 1890 kcal
```

### Activity Multiplier Reference

| Level | Multiplier | Description |
|-------|-----------|-------------|
| Sedentary | 1.2 | Desk job, no exercise |
| Lightly active | 1.375 | Light exercise 1-3 days/week |
| Moderately active | 1.55 | Moderate exercise 3-5 days/week |
| Very active | 1.725 | Hard exercise 6-7 days/week |
| Extremely active | 1.9 | Twice-daily training or physical labor |

**Implementation:** `macros.compute_tdee()`

---

## 3. Phase-Specific Macro Prescription

After TDEE is computed, a phase offset is applied to establish the caloric target. Protein and fat are set first (as hard requirements), then carbohydrates fill the remainder.

### Phase Caloric Offsets

| Phase | Offset (kcal) | Rationale |
|-------|--------------|-----------|
| Bulk | +400 | Midpoint of +300-500 range for controlled surplus |
| Cut | -400 | Midpoint of -(300-500) range for moderate deficit |
| Maintain | 0 | No adjustment |
| Peak | -700 | Aggressive contest-week depletion |
| Restoration | 0 | Starts at maintenance; increases weekly (see Section 17) |

### Target Calorie Formula

```
target_calories = TDEE + phase_offset
```

### Protein Targets (g/kg Total Body Weight)

Aligned with the ISSN position stand and Morton et al. (2018) meta-analysis. Anchored to **total body weight** (TBW), not lean mass -- applying LBM multipliers under-doses by 25-40% at typical offseason body fat levels (15-25% BF).

| Phase | g/kg TBW | Rationale |
|-------|---------|-----------|
| Bulk | 2.0 | ~1 g/lb TBW; surplus environment; carbs drive anabolism |
| Maintain | 2.0 | Mid-range; adequate for tissue maintenance and MPS |
| Cut | 2.4 | Elevated to blunt muscle catabolism in deficit |
| Peak | 2.7 | Upper ceiling; extreme deficit of contest week demands maximum protection |
| Restoration | 2.2 | Moderate; tapering down from peak protein during reverse diet |

**Hard bounds enforced regardless of division or phase:**
- **Protein floor:** 1.6 g/kg TBW (minimum for any athlete)
- **Protein ceiling:** 2.7 g/kg TBW (diminishing returns above this; renal/digestive cost)

### Macro Priority Order

```
1. protein_g = protein_per_kg x weight_kg           (set first -- non-negotiable)
2. fat_g     = fat_floor_per_kg x weight_kg          (set second -- see Section 4)
3. carbs_g   = (target_calories - protein_kcal - fat_kcal) / 4.0   (residual)
```

Carbohydrates are always the **residual macro** -- they absorb any caloric adjustments after protein and fat floors are satisfied.

**Caloric densities:** Protein = 4 kcal/g | Carbs = 4 kcal/g | Fat = 9 kcal/g

**Worked example:** 90 kg male in a cut (TDEE 3225):
```
target_calories = 3225 - 400 = 2825 kcal
protein_g       = 2.4 x 90  = 216 g    (864 kcal)
fat_g           = 0.8 x 90  = 72 g     (648 kcal)    [cut-phase floor]
remaining_kcal  = 2825 - 864 - 648 = 1313 kcal
carbs_g         = 1313 / 4  = 328.3 g
```

**Implementation:** `macros.compute_macros()`

---

## 4. Dynamic Fat Floor Phasing

Fat intake follows a **phase-decaying floor model** (1.0 -> 0.8 -> 0.5 -> 0.4 g/kg) that progressively reduces fat as competition approaches, routing spared calories strictly to carbohydrates for muscle fullness and training performance.

### Fat Floor Decay Model (g/kg TBW)

| Phase | Fat Floor | Rationale |
|-------|----------|-----------|
| Bulk | 1.0 | Optimal for androgen synthesis and hormonal health |
| Lean Bulk | 1.0 | Same as bulk |
| Maintain | 1.0 | Full hormonal support |
| Restoration | 0.9 | Rebuilding hormonal function post-show |
| Cut (early) | 0.8 | Slight sacrifice to spare carbs for training performance |
| Cut (late-stage) | 0.5 | Aggressive reduction when already lean (see override below) |
| Peak | 0.4 | Maximum carb sparing for glycogen supercompensation |

### Late-Stage Cut Override

When the athlete is already lean, the fat floor drops from 0.8 to 0.5 g/kg:

```python
if phase == "cut" and body_fat_pct is not None:
    lean_threshold = 8.0 if sex == "male" else 14.0
    if body_fat_pct <= lean_threshold:
        fat_floor = 0.5  # g/kg TBW (down from 0.8)
```

| Sex | Lean Threshold | Fat Floor (Early Cut) | Fat Floor (Late Cut) |
|-----|---------------|----------------------|---------------------|
| Male | <= 8% BF | 0.8 g/kg | 0.5 g/kg |
| Female | <= 14% BF | 0.8 g/kg | 0.5 g/kg |

**Coaching rationale:** At sub-8% (male) or sub-14% (female) body fat, the athlete is deep into prep. Fat is minimised to maximise carbohydrate availability, which directly drives training performance, muscle glycogen, and on-stage fullness. Hormonal disruption at this stage is accepted as a temporary trade-off that the restoration phase (Section 17) will address.

**Implementation:** `macros._fat_floor_for_context()`

---

## 5. Weekly-Neutral Carb Cycling

Carb cycling distributes the weekly carbohydrate budget unevenly between training and rest days while preserving the total weekly macro budget (caloric neutrality).

### Algebraic Solution

Given:
- `C` = base daily carbs (from `compute_macros`)
- `T` = training days per week (default 5)
- `R` = rest days per week (7 - T)
- `ratio` = 1.25 (training days get 25% more carbs than rest days)

```
Weekly carb budget preserved: W = 7 x C

Constraint 1: (T x train_carbs) + (R x rest_carbs) = W
Constraint 2: train_carbs = rest_carbs x ratio

Substituting:
  rest_carbs x (T x ratio + R) = 7 x C

Solving:
  rest_carbs  = (7 x C) / (T x ratio + R)
  train_carbs = rest_carbs x 1.25
```

**Worked example:** base_carbs = 300 g, 5 training days:
```
rest_carbs  = (7 x 300) / (5 x 1.25 + 2) = 2100 / 8.25 = 254.5 g
train_carbs = 254.5 x 1.25 = 318.2 g

Weekly verification:
(5 x 318.2) + (2 x 254.5) = 1591 + 509 = 2100 g = 7 x 300 g  [preserved]
```

### Fat Rebalancing

To keep weekly calories roughly equivalent, fat is adjusted inversely to carbs:

```python
# Training day: fat reduced to compensate for extra carb kcal (clamped to fat floor)
extra_carb_kcal = (train_carbs - base_carbs) * 4.0
train_fat = max(fat_floor, base_fat - extra_carb_kcal / 9.0)

# Rest day: fat increased with saved carb kcal
saved_carb_kcal = (base_carbs - rest_carbs) * 4.0
rest_fat = base_fat + saved_carb_kcal / 9.0
```

Protein stays constant across both day types.

**Coaching rationale:** Training days demand more glycogen for performance. Higher carbs peri-workout maximise muscle protein synthesis (MPS) and glycogen resynthesis. Rest days shift toward higher fat, which supports hormonal health and satiety when training stimulus is absent.

**Implementation:** `macros.compute_training_rest_day_macros()`

---

## 6. Chrono-Nutrient Meal Planning

Meals are anchored to the training window with peri-workout prioritisation. The system generates a time-stamped meal plan based on training start time.

### Peri-Workout Carbohydrate Allocation

| Window | % of Daily Carbs | Timing | Notes |
|--------|-----------------|--------|-------|
| Pre-Workout | 35% | 90-120 min before training | Complex carbs, high protein, strict <10g fat for rapid gastric emptying |
| Intra-Workout | 10% | During training | Fast carbs (HBCD) -- see Section 7 for session-matched scaling |
| Post-Workout | 25% | Within 60 min after training | Highest carb meal -- maximise glycogen resynthesis |
| Remaining meals | 30% (split evenly) | Spaced 3.5-4 hours apart | Last meal is casein-dominant for overnight MPS |

### Peri-Workout Macro Composition

```
Pre-Workout:
  protein = (daily_protein / meal_count) x 1.1     [10% boost]
  carbs   = min(daily_carbs x 0.25, scaled_cap)
  fat     = min(5g, daily_fat x 0.05)              [minimal for gastric emptying]

Post-Workout:
  protein = (daily_protein / meal_count) x 1.2     [20% boost]
  carbs   = daily_carbs x 0.35                     [largest carb meal]
  fat     = min(5g, daily_fat x 0.05)              [minimal]
```

### Intra-Workout Trigger

Intra-workout nutrition is only prescribed when `training_duration > 75 minutes`. Sessions shorter than this rely on pre-workout glycogen stores alone.

When prescribed:
```
15g EAA (Essential Amino Acids) + scaled HBCD (see Section 7)
0g protein, 0g fat
```

### Meal Spacing Rules

- Non-peri-workout meals start at 08:00, spaced 4 hours apart
- Meals within 2 hours of the pre- or post-workout window are skipped
- No meals scheduled after 22:00
- Final meal is labelled "Casein" with slow-digesting protein recommendation

**Implementation:** `macros.compute_chrono_meal_plan()`

---

## 7. Session-Matched Intra-Workout HBCD Scaling

Intra-workout Highly Branched Cyclic Dextrin (HBCD) prescription is scaled by the glycogen demand of the muscles being trained in that session. Large compound movements deplete 2-3x more glycogen than isolation days.

### HBCD Prescription by Muscle Group

| Muscle Group | HBCD (g) | Glycogen Demand |
|-------------|---------|----------------|
| Quads | 50 | Very high -- squats, leg press |
| Hamstrings | 50 | Very high -- RDLs, leg curls |
| Back | 45 | High -- rows, pulldowns, deadlifts |
| Glutes | 40 | High -- hip thrusts, lunges |
| Chest | 25 | Moderate -- bench press, flyes |
| Shoulders (combined) | 25 | Moderate |
| Front Delt | 20 | Moderate-low |
| Side Delt | 15 | Low |
| Rear Delt | 15 | Low |
| Traps | 10 | Low |
| Biceps | 0 | Negligible -- rely on pre-workout meal |
| Triceps | 0 | Negligible |
| Forearms | 0 | Negligible |
| Calves | 0 | Negligible |
| Abs | 0 | Negligible |

### Scaling Logic

```python
# The session's HBCD dose is the MAX demand across all trained muscle groups
intra_carbs = max(HBCD_BY_MUSCLE[m] for m in session_muscles)

# Fallback when no session data: 20g
# When max demand is 0 (arms/calves day): intra-workout omitted entirely

# Prescription format:
"15g EAA + {intra_carbs}g HBCD (scaled to session demand)"
```

**Coaching rationale:** A legs session depleting quads and hamstrings demands 50g HBCD to sustain training intensity through 20+ working sets. An arms-only session has negligible glycogen demand and does not benefit from intra-workout carbs -- the pre-workout meal is sufficient. Using the MAX (not sum) prevents over-feeding on multi-muscle sessions where glycogen pools overlap.

**Implementation:** `macros.compute_chrono_meal_plan()` with `session_muscles` parameter; lookup table `macros._INTRA_HBCD_BY_MUSCLE`

---

## 8. Division-Specific Nutrition Profiles

Each of the six competition divisions has a distinct nutrition profile that modulates the base macro prescription. These are algorithmically set (not user-configurable) based on what each division rewards on stage.

### Division Protein Targets (g/kg TBW by Phase)

| Division | Bulk | Cut | Maintain | Peak | Restoration |
|----------|------|-----|----------|------|-------------|
| Men's Open | 1.8 | 2.4 | 2.0 | 2.4 | 2.2 |
| Men's Physique | 2.0 | 2.4 | 2.2 | 2.4 | 2.2 |
| Classic Physique | 1.9 | 2.4 | 2.0 | 2.4 | 2.2 |
| Women's Bikini | 1.8 | 2.2 | 2.0 | 2.2 | 2.0 |
| Women's Figure | 1.9 | 2.3 | 2.0 | 2.3 | 2.1 |
| Women's Physique | 1.9 | 2.4 | 2.1 | 2.4 | 2.2 |

All division overrides are clamped to the global 1.6-2.7 g/kg TBW bounds.

### Division Nutrition Parameters

| Division | Carb Cycling Factor | Fat Floor (g/kg) | Meal Freq | MPS Threshold (g/meal) |
|----------|-------------------|------------------|-----------|----------------------|
| Men's Open | 0.25 (+/-25%) | 0.85 | 5 | 40 |
| Men's Physique | 0.30 (+/-30%) | 0.75 | 5 | 35 |
| Classic Physique | 0.25 (+/-25%) | 0.80 | 5 | 40 |
| Women's Bikini | 0.35 (+/-35%) | 0.80 | 4 | 30 |
| Women's Figure | 0.30 (+/-30%) | 0.80 | 5 | 35 |
| Women's Physique | 0.25 (+/-25%) | 0.80 | 5 | 35 |

### Division Coaching Rationale

**Men's Open:** Mass is the primary goal. Aggressive calorie surplus in offseason (+300-500 kcal). Heavy compound training demands glycogen. Peak week uses full carb-depletion then load cycle. Fat floor slightly elevated (0.85 g/kg) to support testosterone production.

**Men's Physique:** Year-round leanness is judged. Moderate bulk calories. Pronounced carb cycling (30%) keeps metabolism active while lean. Waist tightness is judged -- minimise sodium and fibre before stage.

**Classic Physique:** Weight cap means bulk must be controlled -- stop surplus at cap weight. Slightly less aggressive surplus than open. Fat slightly lower than open to leave more room for carbs during bulk.

**Women's Bikini:** Conservative caloric surplus to avoid excess upper-body mass. Aggressive carb cycling (35%) keeps glute fullness on training days while staying lean. Fat is critical for hormonal health -- never drop below 0.8 g/kg. Peak week is subtle -- carb taper then moderate load (no extreme depletion). Eliminate high-sodium foods and carbonated drinks 5 days out.

**Women's Figure:** More training volume than bikini demands more carbs on training days. Shoulder-to-waist ratio matters -- avoid excessive bloating near show. Moderate carb load on rest days.

**Women's Physique:** Heavy compound training demands glycogen -- carbs are non-negotiable. Protein elevated during cut to preserve hard-earned muscle mass. Peak week follows full depletion-load cycle similar to men's open.

### Division Name Aliases

The system normalises division names and supports aliases:

| Alias | Resolves To |
|-------|------------|
| `open` | `mens_open` |
| `classic` | `classic_physique` |
| `physique` | `mens_physique` |
| `bikini` | `womens_bikini` |
| `figure` | `womens_figure` |

**Implementation:** `macros.compute_division_nutrition_priorities()`

---

## 9. Thermodynamic Energy Balance

The thermodynamic module tracks energy surplus/deficit and projects body mass changes using phase-specific energy equivalents.

### Energy Balance

```
energy_balance = consumed_calories - TDEE
```

Positive = surplus (gaining), negative = deficit (losing).

### Phase-Specific Energy Equivalents (kcal/kg)

The caloric cost of gaining or losing 1 kg of body mass varies by phase because the tissue composition of gains/losses differs:

| Phase | kcal/kg | Tissue Composition |
|-------|---------|-------------------|
| Bulk | 4,500 | Mixed: muscle + glycogen + water + some fat (lean tissue accretion is metabolically cheaper) |
| Lean Bulk | 4,500 | Same as bulk |
| Cut | 6,500 | Mostly fat loss with some lean tissue |
| Maintain | 7,700 | Standard approximation (pure fat tissue) |
| Peak | 7,700 | Extreme deficit, high fat proportion |
| Restoration | 5,500 | Rebuilding lean tissue post-show |

Reference: pure fat tissue = ~7,700 kcal/kg | pure muscle tissue = ~2,500 kcal/kg

### Weight Change Projection Formula

```
total_surplus_kcal = daily_energy_balance x 7 x weeks
expected_weight_change_kg = total_surplus_kcal / kcal_per_kg_for_phase
```

**Worked example (bulk):** 500 kcal/day surplus over 4 weeks:
```
total = 500 x 7 x 4 = 14,000 kcal
expected gain = 14,000 / 4,500 = 3.11 kg
```

**Worked example (cut):** -500 kcal/day deficit over 4 weeks:
```
total = -500 x 7 x 4 = -14,000 kcal
expected loss = -14,000 / 6,500 = -2.15 kg
```

This asymmetry (gaining faster than losing on the same absolute surplus/deficit) matches real-world coaching observations.

### Sex-Specific Caloric Floors (Safety Thresholds)

| Sex | Minimum Calories (kcal/day) |
|-----|---------------------------|
| Male | 1,500 |
| Female | 1,200 |

The `thermodynamic_floor()` function clamps any caloric prescription to these minimums. The system will never prescribe below these values regardless of phase or deficit target.

**Implementation:** `thermodynamic.compute_energy_balance()`, `thermodynamic.compute_expected_weight_change()`, `thermodynamic.thermodynamic_floor()`

---

## 10. Metabolic Adaptation Modeling

Prolonged caloric deficits cause the body's TDEE to decrease beyond what weight loss alone explains (adaptive thermogenesis). This module models that decay.

### Adaptation Formula

```
adaptation_factor = 1.0 - (0.01 x min(weeks_in_deficit, 15))
adapted_TDEE = baseline_TDEE x adaptation_factor
```

| Weeks in Deficit | Adaptation Factor | TDEE Reduction |
|-----------------|-------------------|----------------|
| 0 | 1.00 | 0% |
| 4 | 0.96 | -4% |
| 8 | 0.92 | -8% |
| 12 | 0.88 | -12% |
| 15+ | 0.85 | -15% (capped) |

**Key parameters:**
- Decay rate: 1% per week of sustained deficit
- Maximum adaptation: 15% total reduction (hard cap)
- Evidence basis: Trexler et al. (2014), Rosenbaum & Leibel (2010)

**Coaching rationale:** Without this adjustment, caloric prescriptions would systematically overestimate the deficit as prep progresses, leading to unexpected weight stalls. The adaptation cap at 15% prevents the model from over-correcting. Diet breaks and refeeds (Sections 11, 12) help partially reset this adaptation.

**Worked example:** Athlete with baseline TDEE of 3000 kcal, 10 weeks into a cut:
```
adaptation_factor = 1.0 - (0.01 x 10) = 0.90
adapted_TDEE = 3000 x 0.90 = 2700 kcal
# 300 kcal/day "invisible" reduction the athlete needs to account for
```

**Implementation:** `thermodynamic.compute_adaptation_factor()`, `thermodynamic.compute_adapted_tdee()`

---

## 11. Autoregulation System

The autoregulation module gates all prescription changes behind adherence checks. The system refuses to adjust macros when the athlete is not consistently following the current prescription.

### Adherence Lock

| Condition | Threshold | Action |
|-----------|----------|--------|
| Adherence < 85% | Lock threshold | Prescription is **LOCKED** -- no changes allowed. Coaching message: "Focus on consistently hitting current targets before any adjustments are made." |
| Adherence < 85% for 2+ consecutive weeks (cut/peak) | Diet break trigger | 1-week maintenance diet break prescribed |
| Adherence >= 85% | Unlocked | Prescription may be adjusted |
| Adherence >= 90% | Adjust threshold | Eligible for stall-based tweaks |

**Coaching rationale:** There is no point adjusting a prescription the athlete is not following. Adjusting macros downward when adherence is already low creates an unachievable target spiral.

### Diet Break Protocol

When adherence has been below 85% for 2+ consecutive weeks during a cut or peak phase:

```
break_calories = current_calories + 400    (approximately maintenance)
break_carbs    = current_carbs + 100       (surplus routed to glycogen)
duration       = 1 week
```

After the break: resume the deficit.

**Coaching rationale:** Chronic low adherence during a deficit signals diet fatigue, not lack of willpower. A structured diet break at maintenance calories resets psychological and physiological stress, improving subsequent adherence. This is more effective than repeatedly locking the prescription.

### Stall Adjustments

When adherence >= 90% but weight is stalling (absolute rate < 0.05 kg/week):

```python
if weight_trend >= 0:   # weight stable or rising -- athlete wants to lose
    adjusted_cal = target_cal - 100    # nudge deficit deeper
elif weight_trend < 0:  # weight stable or dropping -- athlete wants to gain
    adjusted_cal = target_cal + 100    # nudge surplus higher

# Adjustment applied entirely to carbs (most flexible macro)
carb_change = cal_diff / 4.0
```

**Constants:**
```
ADHERENCE_LOCK_THRESHOLD  = 85.0%
ADHERENCE_ADJUST_THRESHOLD = 90.0%
STALL_ADJUSTMENT_KCAL = 100.0
```

**Implementation:** `autoregulation.adherence_lock()`, `autoregulation.adjust_for_adherence()`

---

## 12. Refeed Scheduling

Refeeds are structured high-carbohydrate days inserted during cutting phases to mitigate hormonal down-regulation (leptin, thyroid, testosterone). The interval between refeeds is interpolated based on body fat percentage -- leaner athletes receive more frequent refeeds.

### Refeed Interval Interpolation (BF%-based)

```
Lean threshold: male = 10% BF, female = 18% BF

If BF% <= lean_threshold:
    interval = 7 days (most frequent)
If BF% >= lean_threshold + 10%:
    interval = 14 days (base frequency)
Otherwise:
    fraction = (BF% - lean_threshold) / 10.0
    interval = 7 + fraction x (14 - 7)    [linear interpolation]
```

| Body Fat % (Male) | Body Fat % (Female) | Refeed Interval (days) |
|-------------------|---------------------|----------------------|
| <= 10% | <= 18% | 7 |
| 12% | 20% | 8 |
| 15% | 23% | 11 |
| >= 20% | >= 28% | 14 |

### Refeed Carb Multiplier

Leaner athletes also receive a higher carb bump on refeed days:

```
If BF% <= lean_threshold:
    carb_multiplier = 2.0x    (double carbs)
If BF% >= lean_threshold + 10%:
    carb_multiplier = 1.5x
Otherwise:
    fraction = (BF% - lean_threshold) / 10.0
    carb_multiplier = 2.0 - fraction x 0.5
```

| Body Fat % (Male) | Carb Multiplier |
|-------------------|----------------|
| <= 10% | 2.0x |
| 15% | 1.75x |
| >= 20% | 1.5x |

### Refeed Day Prescription

```
refeed_calories      = TDEE (maintenance level -- deficit fully erased)
refeed_carbs         = normal_carbs x carb_multiplier
protein              = unchanged
fat                  = reduced to accommodate extra carbs within calorie target
```

A refeed is triggered when `days_in_deficit >= computed_interval`.

**Constants:**
```
BASE_REFEED_INTERVAL_DAYS = 14
MIN_REFEED_INTERVAL_DAYS  = 7
LOW_BF_THRESHOLD_MALE     = 10.0%
LOW_BF_THRESHOLD_FEMALE   = 18.0%
```

**Implementation:** `autoregulation.compute_refeed()`

---

## 13. ARI-Triggered Emergency Refeeds

This is the **cross-engine feedback loop** where Engine 2 (Adaptive Readiness Index) informs Engine 3 (Nutrition Controller). When ARI scores indicate dangerously compromised recovery during a deficit, an emergency refeed is triggered regardless of the scheduled refeed interval.

### Trigger Criteria (all three must be met)

1. Phase must be `"cut"` or `"peak"`
2. Average ARI < 55 across the recent window (3-5 days)
3. ARI has been below 55 for **3+ consecutive days** (counted from most recent backwards)

### Emergency Refeed Prescription

| Athlete Condition | Prescription | Duration |
|-------------------|-------------|----------|
| Lean (male <= 10% BF, female <= 18% BF) | Maintenance calories, 2x carbs | 2 days |
| Not lean | Maintenance calories, 1.5x carbs | 1 day |

### Alert Escalation Ladder

| ARI State | Phase | System Response |
|-----------|-------|----------------|
| avg < 55, 3+ consecutive low days | Cut/Peak | **EMERGENCY REFEED** triggered immediately |
| avg trending low, 2 consecutive low days | Cut/Peak | Warning: "Monitor closely -- refeed may be needed soon" |
| avg < 55 | Non-deficit phase | "Consider reducing training volume instead" (not a nutrition problem) |
| avg >= 55 | Any | "ARI is adequate. No emergency refeed needed." |

**Constants:**
```
ARI_LOW_THRESHOLD            = 55.0
ARI_CONSECUTIVE_DAYS_TRIGGER = 3
```

**Coaching rationale:** Low ARI during a deficit signals that the athlete's recovery capacity is overwhelmed. Continuing the deficit risks injury, illness, and muscle loss. An emergency refeed restores glycogen, leptin signaling, and CNS recovery capacity. The 2-day protocol for lean athletes reflects the more fragile hormonal state at low body fat. This system distinguishes between a nutritional recovery issue (deficit phases) and a training volume issue (non-deficit phases).

**Implementation:** `autoregulation.check_ari_triggered_refeed()`

---

## 14. Division BF Floor (Halt-Cut Logic)

Engine 3 monitors body fat percentage and halts the cut phase when the athlete reaches the division-specific BF floor. Cutting below these floors risks health complications without meaningful competitive benefit.

### Division BF Floors

| Division | BF Floor (%) | Stage Look |
|----------|-------------|-----------|
| Men's Open | 4.0 | Striated glutes, extreme conditioning |
| Classic Physique | 5.0 | Very lean, slightly softer than open |
| Men's Physique | 6.0 | V-taper and conditioning, not striations |
| Women's Physique | 8.0 | Full development with visible separation |
| Women's Figure | 8.0 | Lean with visible muscle but not overly dry |
| Women's Bikini | 11.0 | Healthy, lean look; over-conditioning is penalised |

### Halt Behavior

When `body_fat_pct <= division_floor`:
- `halt = True`
- System message: transition to maintenance or peak week preparation
- The cut phase will not prescribe further caloric reduction

When `body_fat_pct > division_floor`:
- `halt = False`
- Cut continues normally

**Coaching rationale:** Each division has a different "ideal stage condition." Men's Open demands striated glutes (4% BF), while Women's Bikini penalises excessive leanness (judges prefer 11%+). The halt-cut mechanism prevents the system from pushing an athlete below the conditioning level their division actually rewards.

**Implementation:** `autoregulation.should_halt_cut()`

---

## 15. GI Distress Routing

Digestion is the ultimate limiting factor for high-calorie phases (Men's Open bulks at 500g+ carbs/day) and a critical factor for midsection presentation (Classic Physique vacuum poses). When GI distress is reported, the system swaps food sources to pre-digested, low-FODMAP, fast-gastric-emptying alternatives.

### Trigger

```
GI Distress Index >= 6 (on a 1-10 self-reported scale)
```

### Low-FODMAP Food Source Swap Protocol

| Macro | Standard Sources | GI-Friendly Alternatives |
|-------|-----------------|------------------------|
| **Carbs** | Oats, Brown Rice, Sweet Potato, Whole Wheat Pasta | Cream of Rice, White Rice, White Potato, HBCD |
| **Protein** | Chicken Breast, Lean Beef, Eggs, Salmon | White Fish (Tilapia, Cod), Whey Isolate, Egg Whites, Turkey Breast |
| **Fat** | Whole Eggs, Almonds, Avocado, Olive Oil | MCT Oil, Macadamia Nuts (low FODMAP), Small amount Avocado |

### Severity-Based Escalation

| GI Score | Action |
|----------|--------|
| 1-5 | No intervention: "GI distress within normal range. No food source changes needed." |
| 6-7 | Full low-FODMAP swap protocol activated. Eliminate cruciferous vegetables, dairy (except whey isolate), and high-fiber foods. Consider digestive enzymes (lipase, protease, amylase) with each meal. |
| 8-10 | **SEVERE:** Temporarily reduce total food volume by 10-15%. Replace solid carb meals with liquid HBCD shakes until symptoms resolve. |

### Division-Specific Notes

- **Men's Open & Classic Physique:** GI management is critical for midsection presentation. Consider splitting meals into 6-7 smaller feedings to reduce gastric load.
- **All divisions near show:** Ensure carb load is absorbed, not sitting in the gut.

**Implementation:** `autoregulation.check_gi_distress()`

---

## 16. Reactive Peak Week Controller

Peak week is a 7-day carbohydrate, water, sodium, and potassium manipulation protocol leading into competition. The system generates a static protocol and then applies reactive adjustments based on daily morning visual check-ins.

### Static Protocol (Show on Saturday)

| Day | Stage | Carbs (g/kg LBM) | Fat (g/kg LBM) | Protein |
|-----|-------|-------------------|----------------|---------|
| Monday | Depletion 1 | 0.5 | 0.8 | 2.2 g/kg LBM |
| Tuesday | Depletion 2 | 0.3 | 0.8 | 2.2 g/kg LBM |
| Wednesday | Transition | 2.0 | 0.6 | 2.2 g/kg LBM |
| Thursday | Load 1 | 5.0 | 0.4 | 2.2 g/kg LBM |
| Friday | Load 2 | 4.0 | 0.3 | 2.2 g/kg LBM |
| Saturday | Show Day | 3.0 | 0.3 | 2.2 g/kg LBM |
| Sunday | Recovery | 3.5 | 0.8 | 2.2 g/kg LBM |

**Worked example (80 kg LBM):**

| Day | Carbs (g) | Protein (g) | Fat (g) | Total kcal |
|-----|-----------|------------|---------|-----------|
| Mon (Depletion 1) | 40 | 176 | 64 | 1,440 |
| Tue (Depletion 2) | 24 | 176 | 64 | 1,376 |
| Wed (Transition) | 160 | 176 | 48 | 1,776 |
| Thu (Load 1) | 400 | 176 | 32 | 2,592 |
| Fri (Load 2) | 320 | 176 | 24 | 2,200 |
| Sat (Show) | 240 | 176 | 24 | 1,880 |
| Sun (Recovery) | 280 | 176 | 64 | 2,408 |

### Division-Specific Water Protocols (mL/day)

| Day | Aggressive* | Default | Gentle** |
|-----|-----------|---------|---------|
| Mon | 8,000 | 6,000 | 5,000 |
| Tue | 8,000 | 6,000 | 5,000 |
| Wed | 6,000 | 5,000 | 4,500 |
| Thu | 3,000 | 3,500 | 4,000 |
| Fri | 2,500 | 3,000 | 3,500 |
| Sat | 2,000 | 2,500 | 3,000 |
| Sun | 4,000 | 4,000 | 4,000 |

\* Men's Open, Classic Physique, Women's Physique, Women's Figure
\*\* Women's Bikini, Men's Physique

### Division-Specific Sodium Protocols (mg/day)

| Day | Aggressive* | Default | Gentle** |
|-----|-----------|---------|---------|
| Mon | 2,000 | 2,300 | 2,300 |
| Tue | 1,500 | 2,000 | 2,300 |
| Wed | 1,000 | 1,500 | 2,000 |
| Thu | 1,500 | 1,500 | 1,800 |
| Fri | 1,200 | 1,200 | 1,500 |
| Sat | 800 | 1,000 | 1,200 |
| Sun | 2,300 | 2,300 | 2,300 |

Note: Aggressive sodium **increases** on Thursday (Load Day 1) compared to Wednesday. This is intentional -- sodium supports SGLT1-mediated glucose co-transport during the carb load.

### Potassium Targets

On **load and show days**, potassium is calculated to maintain a ~4.5:1 Na:K ratio:

```
potassium_mg = sodium_mg / 4.5     (load_1, load_2, show_day)
potassium_mg = 3,500               (all other days)
```

This Na:K ratio manipulation pushes water into muscle cells (intracellular) and out of subcutaneous space.

### Reactive Condition Adjustments (FLAT / SPILLED / PEAKED)

Pro coaches do not follow a static plan -- they react to how the athlete looks each morning. The reactive controller takes a visual state check-in and adjusts that day's macros in real-time.

| Condition | Visual Cues | Carbs | Sodium | Potassium | Water |
|-----------|------------|-------|--------|-----------|-------|
| **FLAT** | Muscles lack volume, vascularity low, depleted | **+25%** | **+400mg** | unchanged | unchanged |
| **SPILLED** | Blurry, subcutaneous water, distended | **-50%** | unchanged | **+500mg** | **unchanged** (do NOT restrict) |
| **PEAKED** | Full, dry, vascular -- ideal state | **freeze** | **freeze** | **freeze** | **freeze** |

```python
# FLAT: push glycogen into depleted muscles
result["carbs_g"] = int(round(carbs_g * 1.25))
result["sodium_mg"] = sodium_mg + 400
# Rationale: Sodium facilitates SGLT1 glucose co-transport across intestinal lumen

# SPILLED: halt glycogen overflow
result["carbs_g"] = int(round(carbs_g * 0.50))
result["potassium_mg"] = potassium_mg + 500
# Rationale: Potassium pulls fluid intracellularly via Na/K-ATPase pump
# Water: NO CHANGE (further restriction risks cramping and dangerous dehydration)

# PEAKED: change nothing -- coast to stage
# No modifications whatsoever
```

Calories are recalculated after any adjustment:
```
total_calories = carbs_g * 4 + protein_g * 4 + fat_g * 9
```

**Implementation:** `peak_week.compute_peak_week_protocol()`, `peak_week.adjust_peak_day_for_condition()`, `peak_week.apply_reactive_peak_week()`

---

## 17. Post-Show Restoration Protocol

The restoration (reverse diet) phase gradually increases calories to rebuild metabolic rate and hormonal function after contest prep. This is critical for long-term athlete health.

### Caloric Ramp Schedule

| Period | Weekly Increase | Cumulative (above maintenance) |
|--------|----------------|-------------------------------|
| Week 1 | +100 kcal | +100 |
| Week 4 | +100 kcal | +400 |
| Week 8 | +100 kcal | +800 |
| Week 9 | +150 kcal | +950 |
| Week 12 | +150 kcal | +1,400 |

```python
if week <= 8:
    calorie_add = 100.0 * week
else:
    calorie_add = 100.0 * 8 + 150.0 * (week - 8)

target_calories = base_tdee + calorie_add
```

### Protein Taper (2.7 -> 2.0 g/kg over 12 weeks)

```python
protein_per_kg = 2.7 - (0.7 * (week - 1) / 11.0)
# Clamped to [2.0, 2.7]
```

| Week | Protein (g/kg TBW) |
|------|-------------------|
| 1 | 2.70 |
| 4 | 2.51 |
| 8 | 2.26 |
| 12 | 2.00 |

### Fat During Restoration

Fat is set at **0.9 g/kg TBW** throughout the restoration phase -- elevated compared to late prep to rebuild hormonal function (testosterone, estrogen, thyroid hormones).

### Carbs During Restoration

Carbs fill the remainder after protein and fat:
```
remaining_kcal = target_calories - protein_kcal - fat_kcal
carbs_g = max(remaining_kcal / 4.0, 0.0)
```

**Coaching rationale:** Post-show, the athlete's metabolic rate is suppressed by up to 15% (Section 10). Rapidly returning to pre-prep calorie levels causes excessive fat gain on a suppressed metabolism. The gradual ramp allows metabolic rate to recover alongside caloric intake. Protein tapers down because the extreme levels needed during peak week are unnecessary (and burden kidneys/digestion) when the athlete is no longer in a severe deficit.

**Implementation:** `macros.compute_restoration_macros()`

---

## 18. Engine 4: Energy Flux Model

Engine 4 is the **Cardio & NEAT Controller**. Its philosophy: an elite prep coach manipulates energy **expenditure** before dropping calories to the thermodynamic floor. Engine 4 intercepts Engine 3's caloric reduction pathway and mandates cardio/NEAT increases when the athlete is approaching minimum viable intake.

### Floor Intercept Thresholds

Engine 4 intercepts 250-300 kcal **above** Engine 3's absolute caloric floor:

| Sex | Engine 3 Floor | Engine 4 Intercept | Buffer |
|-----|---------------|-------------------|--------|
| Male | 1,500 kcal | 1,800 kcal | 300 kcal |
| Female | 1,200 kcal | 1,450 kcal | 250 kcal |

### Decision Logic

```
room_to_cut = max(0, current_calories - intercept)

CASE 1: room_to_cut >= target_deficit
  ACTION: "reduce_food"
  Reduce food by full target_deficit amount.
  No additional cardio needed.

CASE 2: room_to_cut < target_deficit
  food_cut = min(room_to_cut, target_deficit x 0.4)    [max 40% from food]
  cardio_deficit_needed = target_deficit - food_cut

  If food_cut > 0:
      ACTION: "both"  (split deficit between food and cardio)
  Else:
      ACTION: "add_cardio"  (at the floor -- cannot reduce food further)
```

### Cardio Calorie Burn Estimates (per 30-min session)

| Modality | Calories/Session |
|----------|-----------------|
| LISS Incline Walk | 200 |
| LISS Stairmaster | 250 |
| LISS Cycling | 220 |
| Zone 2 Cycling | 280 |
| HIIT Sprint | 350 |
| HIIT Rowing | 320 |
| HIIT Cycling | 300 |
| Steady State Elliptical | 230 |

### Cardio Safety Caps

| Parameter | Maximum |
|-----------|---------|
| Sessions per week | 5 |
| Total weekly minutes | 200 |

### Late-Prep Modality Selection

```python
if phase in ("peak", "cut") and weeks_in_deficit > 8:
    modality = "liss_incline_walk"     # CNS too fragile for HIIT
elif phase == "cut":
    modality = "liss_stairmaster"      # pure fatty acid oxidation
else:
    modality = "zone2_cycling"         # VO2max and insulin sensitivity
```

**Coaching rationale:** Dropping calories to the thermodynamic floor while the athlete still has room for additional energy expenditure is a coaching error. Food supports training performance, muscle retention, and psychological adherence. Cardio is a more expendable lever. The 40% cap on food reduction when near the floor ensures the athlete always retains enough intake for basic metabolic function.

**Implementation:** `cardio.compute_energy_flux_prescription()`

---

## 19. Engine 4: NEAT Step Count Titration

Non-Exercise Activity Thermogenesis (NEAT) plummets as athletes get leaner and more lethargic. This module prescribes escalating step targets and penalises missed targets by deducting carbs to balance unburned calories.

### Phase-Based Step Targets

| Phase | Step Target | Rationale |
|-------|------------|-----------|
| Bulk | 8,000 | Baseline activity for general health |
| Lean Bulk | 8,000 | Same as bulk |
| Maintain | 8,000 | Standard baseline |
| Restoration | 6,000 | Reduced during recovery period |
| Cut | 10,000 | First escalation to increase expenditure |
| Peak | 10,000 | Maintain but do not increase (CNS fragile) |

### Stall Escalation

When weight loss stalls (< 0.1 kg/week for 2+ weeks) during cut/peak:

```
step_target = 12,000    (second escalation)
```

**Rationale:** Increase NEAT before reducing calories further. NEAT is the most sustainable form of expenditure and does not compete with recovery.

### Caloric Estimate per Step

```python
weight_factor = weight_kg / 80.0          # normalize to 80kg baseline
kcal_per_1000_steps = 40.0 * weight_factor
daily_kcal = (step_target / 1000) * kcal_per_1000_steps
```

**Example (90 kg athlete, 10,000 step target):**
```
weight_factor = 90 / 80 = 1.125
kcal_per_1k = 40.0 x 1.125 = 45.0
daily_kcal = (10,000 / 1000) x 45.0 = 450 kcal
```

### Missed Step Penalty (Carb Deduction)

When the athlete fails to hit their step target:

```python
missed_steps = step_target - actual_steps
missed_kcal = (missed_steps / 1000) * kcal_per_1000_steps
carb_penalty_g = missed_kcal / 4.0       # 4 kcal per gram of carbs
```

The carb penalty is deducted from the next day's carbohydrate allocation to maintain the intended weekly energy balance.

**Example:** 90 kg athlete hits 7,000 of 10,000 target:
```
missed_steps = 3,000
missed_kcal = (3,000 / 1000) x 45.0 = 135 kcal
carb_penalty = 135 / 4 = 33.75g -> ~34g carbs deducted from tomorrow
```

**Implementation:** `cardio.compute_step_prescription()`

---

## 20. Engine 4: Active Cardio Periodization

Cardio modality and frequency are periodized based on training phase, with progressive overload during extended cut phases.

### Phase-Specific Cardio Prescriptions

| Phase | Sessions/Week | Duration (min) | Modality | Fasted | Purpose |
|-------|--------------|----------------|----------|--------|---------|
| Bulk | 2 | 20 | HIIT | No | VO2max and insulin sensitivity without competing with surplus |
| Lean Bulk | 2 | 25 | HIIT | No | Partition nutrients toward muscle, limit fat gain |
| Maintain | 3 | 25 | Mixed | No | Metabolic flexibility maintenance |
| Cut | 4 | 30 | LISS | Yes | Pure fatty acid oxidation; primary deficit driver |
| Peak | 3 | 20 | LISS | No | Maintain expenditure without glycogen depletion |
| Restoration | 2 | 20 | LISS | No | Gentle reintroduction; body needs to rebuild |

### Modality Options by Phase

| Phase | Options |
|-------|---------|
| Bulk | HIIT Sprint, HIIT Cycling, Zone 2 Cycling |
| Lean Bulk | HIIT Cycling, Zone 2 Cycling |
| Maintain | Zone 2 Cycling, LISS Incline Walk, HIIT Rowing |
| Cut | LISS Incline Walk, LISS Stairmaster, LISS Cycling |
| Peak | LISS Incline Walk, Steady State Elliptical |
| Restoration | LISS Incline Walk, Zone 2 Cycling |

### Progressive Overload During Cut Phase

```python
if weeks_in_phase >= 8 and sessions < 5:
    sessions += 1                        # add 1 session after 8 weeks
elif weeks_in_phase >= 4:
    duration = min(45, duration + 5)     # extend by 5 min after 4 weeks
```

**Principle:** Increase duration before increasing frequency.

### Weight Stall Escalation (Cut/Peak)

```python
if weight_stall and phase in ("cut", "peak"):
    sessions += 1 (if < 5)
    duration = min(45, duration + 10)
```

### Key Coaching Rules

- **HIIT is banned during cut phase** -- CNS is already taxed from deficit + heavy training
- **No HIIT under any circumstances during peak** -- glycogen must be preserved for carb load
- **Discontinue cardio 48h before show day** to maximise fullness
- **Fasted AM cardio during cut** (after coffee + EAAs for muscle protection)
- **Increase duration before increasing frequency** during cut phase
- **No HIIT for at least 4 weeks post-show** during restoration
- **Schedule cardio on non-leg days** during bulk to avoid interference with hypertrophy

**Implementation:** `cardio.compute_cardio_prescription()`

---

## 21. Engine 4: ARI-Aware Recovery Adjustments

Engine 4 integrates with Engine 2's Adaptive Readiness Index (ARI) to modulate cardio volume based on recovery capacity. This is the **E2 -> E4 cross-engine feedback loop**.

### ARI-Based Cardio Reduction

| ARI Range | Adjustment | Minimum Sessions | Rationale |
|-----------|-----------|-----------------|-----------|
| >= 55 | No change | -- | Recovery is adequate |
| 40-54 | -1 session | 1 | Recovery is compromised; protect CNS |
| < 40 | -2 sessions | 1 | Recovery is severely compromised; prioritise rest |

```python
if avg_ari < 40:
    sessions = max(1, sessions - 2)
    # "ARI CRITICAL ({ari}): Cardio reduced to {n} session(s).
    #  Recovery is severely compromised -- prioritise rest."
elif avg_ari < 55:
    sessions = max(1, sessions - 1)
    # "ARI LOW ({ari}): Reducing cardio by 1 session to protect recovery."
```

### Coordinated Recovery Response

When ARI is critically low during a deficit, **both** Engine 3 and Engine 4 activate simultaneously:

| Engine | Action | Trigger |
|--------|--------|---------|
| Engine 3 (Nutrition) | Emergency refeed (Section 13) | ARI < 55 for 3+ consecutive days during cut/peak |
| Engine 4 (Cardio) | Reduce cardio sessions | ARI < 55 (immediate, no consecutive-day requirement) |

This creates a two-pronged recovery intervention: more food (Engine 3) + less activity (Engine 4).

**Coaching rationale:** When ARI is low, the athlete's autonomic nervous system is signaling systemic fatigue. Adding or maintaining high cardio volume compounds the stress. Reducing cardio allows the body to recover without abandoning expenditure entirely. The minimum of 1 session ensures some cardiovascular activity is maintained even in worst-case scenarios.

**Implementation:** `cardio.compute_cardio_prescription()` (via `avg_ari` parameter)

---

## 22. Cross-Engine Data Flow Diagram

```
+-------------------------------------------------------------------+
|                        ATHLETE INPUT                               |
|  Biometrics, Check-ins, Adherence, GI Score, Visual Condition      |
+-------------------------------------------------------------------+
         |
         v
+-------------------+        weight, BF%, LBM, measurements
|   ENGINE 1        |---------------------------------------------+
|   Diagnostic &    |   LCSA, HQI, PDS, Aesthetic Vector,        |
|   Tracking        |   Weight Cap, Trajectory                    |
+-------------------+                                              |
         |                                                         |
         | BF%, LBM, weight, phase                                 |
         v                                                         |
+-------------------+         ARI scores (recovery index)          |
|   ENGINE 2        |------------------------------------------+   |
|   Training        |   Biomechanical alignment, periodization, |   |
|   Prescription    |   split design, resistance profiles       |   |
+-------------------+                                           |   |
         |                                                      |   |
         | session_muscles, training_days, volume               |   |
         v                                                      v   v
+-------------------+                                 +-----------------+
|   ENGINE 3        |<--- ARI (E2->E3) -------------- |  CROSS-ENGINE   |
|   Nutrition       |     Emergency refeed trigger     |  FEEDBACK       |
|   Controller      |                                  |                 |
|                   |---> weight_trend, adherence ----> |  E3 -> E4:     |
|   Submodules:     |     caloric state                |  current_cals, |
|   - Macros        |                                  |  target_deficit|
|   - Thermodynamic |                                  |                |
|   - Kinetic       |                                  |  E2 -> E4:     |
|   - Autoregulation|                                  |  ARI scores    |
|   - Peak Week     |                                  |  (cardio adj)  |
+-------------------+                                  +----------------+
         |                                                      |
         | current_calories, target_deficit                     |
         v                                                      v
+-------------------+
|   ENGINE 4        |<--- ARI (E2->E4) --- avg_ari
|   Cardio & NEAT   |
|                   |
|   Subroutines:    |
|   4.1 Energy Flux |  intercepts E3 caloric floor
|   4.2 NEAT Steps  |  step count titration + carb penalty
|   4.3 Cardio      |  periodized modality + frequency
|   4.4 Summary     |  unified expenditure plan
+-------------------+
         |
         v
+-------------------------------------------------------------------+
|                     ATHLETE PRESCRIPTION                           |
|  Daily macros, meal plan, cardio Rx, step target, coaching notes   |
+-------------------------------------------------------------------+
```

### Key Cross-Engine Data Flows

| Flow | Source | Target | Data Passed | Purpose |
|------|--------|--------|-------------|---------|
| E1 -> E3 | Diagnostic | Nutrition | BF%, LBM, weight, phase | TDEE calculation, fat floor selection, refeed scheduling, BF floor halt-cut |
| E2 -> E3 | Training | Nutrition | ARI scores (3-5 day window) | Emergency refeed trigger when ARI < 55 for 3+ consecutive days during deficit |
| E2 -> E3 | Training | Nutrition | Session muscle tags | Intra-workout HBCD scaling by glycogen demand |
| E2 -> E4 | Training | Cardio | ARI scores (7-day avg) | Cardio volume reduction when ARI < 55 or < 40 |
| E3 -> E4 | Nutrition | Cardio | Current calories, target deficit | Energy flux decision: reduce food vs. add cardio |
| E4 -> E3 | Cardio | Nutrition | Carb penalty (missed steps) | Deduct carbs from next day when NEAT target missed |
| E1 -> E2 | Diagnostic | Training | Muscle gaps, aesthetic vector | Volume allocation and exercise selection priorities |

### Unified Prescription Generation (Orchestration Order)

1. **Engine 1** runs diagnostics: LCSA correction, BF%, LBM, weight cap, phase determination
2. **Engine 2** generates training split: ARI assessment, volume allocation, exercise prescription, session muscle tags
3. **Engine 3** computes nutrition:
   - TDEE -> adapted TDEE (metabolic adaptation) -> phase macros
   - Carb cycling (training vs rest days) -> chrono-nutrient meal plan (with HBCD scaling)
   - Autoregulation checks (adherence lock, stall adjustment)
   - Refeed evaluation (scheduled + ARI emergency)
   - GI distress check
   - Peak week protocol (if applicable, with reactive adjustments)
   - Restoration macros (if post-show)
4. **Engine 4** computes expenditure:
   - Cardio prescription (ARI-aware, phase-periodized)
   - NEAT step target (with stall escalation)
   - Energy flux decision (food reduction vs. cardio addition)
   - Unified expenditure summary
5. **Final output** merges all four engines into a cohesive daily prescription with coaching notes

---

## Appendix: Source File Reference

| File | Module | Key Functions |
|------|--------|--------------|
| `backend/app/engines/engine3/macros.py` | Macros | `compute_tdee()`, `compute_macros()`, `compute_training_rest_day_macros()`, `compute_restoration_macros()`, `compute_division_nutrition_priorities()`, `compute_peri_workout_carb_split()`, `compute_chrono_meal_plan()` |
| `backend/app/engines/engine3/thermodynamic.py` | Thermodynamic | `compute_energy_balance()`, `compute_expected_weight_change()`, `thermodynamic_floor()`, `compute_adaptation_factor()`, `compute_adapted_tdee()` |
| `backend/app/engines/engine3/kinetic.py` | Kinetic | `compute_rate_of_change()`, `compute_rate_of_change_detailed()`, `target_rate()`, `adjust_calories()` |
| `backend/app/engines/engine3/autoregulation.py` | Autoregulation | `adherence_lock()`, `adjust_for_adherence()`, `compute_refeed()`, `check_ari_triggered_refeed()`, `should_halt_cut()`, `check_gi_distress()` |
| `backend/app/engines/engine3/peak_week.py` | Peak Week | `compute_peak_week_protocol()`, `adjust_peak_day_for_condition()`, `apply_reactive_peak_week()` |
| `backend/app/engines/engine4/cardio.py` | Cardio & NEAT | `compute_energy_flux_prescription()`, `compute_step_prescription()`, `compute_cardio_prescription()`, `compute_total_expenditure_plan()` |
