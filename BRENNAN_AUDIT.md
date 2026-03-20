# Coronado — Brennan Kelley Athlete Audit
**Date:** 2026-03-19
**Purpose:** Validate every engine output against real-world bodybuilding coaching knowledge for Brennan's specific measurements.

---

## LLM Reviewer Prompt

You are an expert sports scientist and competitive bodybuilding coach with deep knowledge of exercise physiology, nutrition science, and IFBB/NPC competition standards. Your job is to critically audit the Coronado app's algorithmic outputs against Brennan's real measurements below.

**For each section, you must:**

1. **Verify the formula** — Is the mathematical approach correct for this use case? Are the constants (k_site factors, activity multipliers, protein targets, BF formulas) grounded in peer-reviewed research or established coaching practice?

2. **Sanity-check the output** — Given Brennan's actual measurements (6'2", 207 lbs, 22% BF, 3 years training, Men's Physique division), do the scores *feel* right? Would a real coach agree with this assessment?

3. **Identify blind spots** — What real-world factors is the algorithm not capturing? What would a top-level physique coach ask about that these numbers can't answer?

4. **Flag coaching conflicts** — Where does the algorithm's output contradict established bodybuilding best practices? Where is it technically correct but practically misleading?

**Key things to research and validate:**
- Are the LCSA k_site correction factors physiologically accurate per site (bicep vs calf vs waist muscle density differences)?
- Is the PDS weighting (aesthetic 40% / mass 30% / conditioning 20% / symmetry 10%) correct for Men's Physique judging criteria?
- Does the Casey Butt weight cap formula apply correctly to a 6'2" male with a slender wrist (17.1 cm)?
- Is 1.9 g/kg LBM protein correct for an offseason intermediate male lifter?
- Is the Navy circumference BF method appropriate for this body type (tall, relatively lean upper body, heavier midsection)?
- Is the TDEE multiplier of 1.55 correct for 5 days/week of heavy resistance training?
- Does the HQI lean-adjustment formula (`lean_circ = raw × √(1 − bf_fraction)`) correctly model how circumference changes with fat loss?
- Are the Men's Physique division ideal ratios (shoulders: 0.59, waist: 0.42, etc.) consistent with what IFBB judges actually reward?
- Is the conditioning score formula (`100 − deviation × 5`) appropriately sensitive? Does 1 BF% deviation = 5 points feel right?
- Is the asymptotic trajectory model a realistic representation of PDS progress over 52 weeks?

**Your output should:**
- Confirm what the algorithm is doing correctly
- Identify specific numbers or formulas that need adjustment with citations or reasoning
- Suggest concrete fixes (change constant X from Y to Z, because research shows...)
- Give an overall verdict: does this app coach like a real bodybuilding expert would, or are there systematic errors that would mislead a competitive athlete?

---

---

## 1. Athlete Profile

| Field | Value | Notes |
|-------|-------|-------|
| Age | 25 | Peak hypertrophy window |
| Sex | Male | |
| Height | 188.0 cm (6'2") | Tall frame — harder to look "full" onstage |
| Body Weight | 94.12 kg (207.5 lbs) | |
| Division | Men's Physique | Board shorts; judged waist-up |
| Training Experience | 3 years | Intermediate lifter |
| Wrist Circumference | 17.1 cm | Slender — below avg male (17.8 cm) |
| Ankle Circumference | 23.3 cm | Average |
| Competition Date | 2027-03-28 | 53 weeks out |
| Training Days/Week | 5 | |
| Meal Count | 4/day | |

---

## 2. Raw Measurements

### Body Composition (Navy Method — no calipers entered yet)

```
Formula (male): BF% = 86.010 × log10(waist − neck) − 70.041 × log10(height) + 36.76
Inputs: waist = 90.5 cm, neck = 42.5 cm, height = 188.0 cm, hips = 94.0 cm
Result: 22.1% body fat
LBM  = 94.12 × (1 − 0.221) = 73.32 kg (161.6 lbs)
Fat  = 94.12 − 73.32      = 20.80 kg (45.9 lbs)
```

**Coach check:** At 6'2", 207 lbs, 22% BF is entirely plausible for an intermediate offseason lifter. Visually: soft mid-section with decent muscle visible in shoulders/chest. Navy formula is ±3–4% accurate — get calipers entered to sharpen this. ✅ Realistic.

---

### Tape Measurements

| Site | cm | inches | Notes |
|------|----|--------|-------|
| Neck | 42.5 | 16.7" | Decent for height |
| Shoulders | 131.0 | 51.6" | **Wide** — a genuine asset for physique |
| Chest | 110.0 | 43.3" | Solid offseason |
| Left Bicep | 42.0 | 16.5" | Good at 22% BF — lean ~38–39 cm |
| Right Bicep | 42.0 | 16.5" | Perfect bilateral symmetry |
| Left Forearm | 30.5 | 12.0" | |
| Right Forearm | 31.0 | 12.2" | 0.5 cm asymmetry |
| Waist | 90.5 | 35.6" | High for stage; need ~76–79 cm at contest |
| Hips | 94.0 | 37.0" | |
| Left Thigh | 54.0 | 21.3" | |
| Right Thigh | 54.0 | 21.3" | Perfect bilateral symmetry |
| Left Calf | 38.0 | 15.0" | **Lagging** — 15" is below avg at any height |
| Right Calf | 38.0 | 15.0" | Perfect bilateral symmetry |

---

### Strength Baselines (Estimated 1RMs)

| Lift | kg | lbs | Coach Assessment |
|------|----|-----|-----------------|
| Bench Press | 118.0 | 260 | Solid intermediate for bodyweight |
| Barbell Back Squat | 125.0 | 276 | Slightly below bench — common push-dominant pattern |
| Barbell Deadlift | 140.0 | 309 | ~1.49× BW — expected at 3 years |
| Military Press | 64.0 | 141 | 54% of bench — good ratio (target 55–65%) ✅ |
| Barbell Bent-Over Row | 85.0 | 187 | ⚠️ Only 72% of bench — should be closer to 85–90% |

**Coach flag:** Row vs bench ratio is 72% — indicates underdeveloped posterior relative to anterior push. Back width is the #1 visual criterion in Men's Physique (shoulder-to-waist V-taper). Prioritize pulling strength and back volume.

---

## 3. Engine 1 — Diagnostic (Physique Assessment)

### 3A. LCSA — Lean Cross-Sectional Area

**What it measures:** Estimated lean muscle volume per site, derived from tape + BF%. Strips fat tissue before computing size so offseason fat doesn't inflate scores.

**Formula:**
```
CSA     = π × (circumference / 2π)²
LCSA    = CSA × k_site × (1 − bf_fraction)
bf_fraction = 0.221   (22.1% BF)
```

k_site factors are site-specific correction constants for muscle density and limb geometry.

**Results:**

| Site | Avg Circumference | LCSA (cm²) | Notes |
|------|------------------|------------|-------|
| Shoulders | 131.0 cm | 744.68 | Largest contributor — wide clavicles |
| Chest | 110.0 cm | 562.57 | Strong |
| Hips | 94.0 cm | 356.04 | Includes glutes |
| Waist | 90.5 cm | 304.63 | Will drop as BF falls |
| Thigh | 54.0 cm | 144.61 | Moderate |
| Bicep | 42.0 cm | 98.42 | Lean gain still available |
| Neck | 42.5 cm | 95.18 | |
| Calf | 38.0 cm | 78.77 | **Weakest site — structural priority** |
| Forearm | 30.75 cm | 53.93 | Small but less judged |
| **Total** | | **2,438.83** | |

**Mass score ceiling:** `20.0 × 188 cm = 3,760 cm²`  
(Elite competitive male natural ceiling, ~Casey Butt approximation)  
**Mass score:** `2,439 / 3,760 × 100 = 64.9 / 100` ✅ Realistic for 3-year intermediate

**Coach check:** LCSA formula correctly strips fat first — avoids the classic error of comparing raw tape at 22% BF to a stage athlete at 5% BF. Calf being the weakest site matches visual expectations for 15" calves on a 6'2" frame. ✅

---

### 3B. HQI — Hypertrophy Quality Index

**What it measures:** How close each site's lean size-to-height ratio is to the Men's Physique division ideal.

**Lean adjustment first:**
```
factor = √(1 − 0.221) = √0.779 = 0.883
All circumferences × 0.883 before computing ratios
```
This reflects what you'd look like at contest conditioning (without fat) while keeping actual muscle size.

**Results vs Men's Physique Ideal:**

| Site | Your Lean Ratio | Division Ideal | HQI | Status |
|------|----------------|----------------|-----|--------|
| Chest | 0.516 | 0.520 | 99.3 | Nearly perfect ✅ |
| Waist | 0.425 | 0.420 | 98.8 | Very close — improves further on cut ✅ |
| Shoulders | 0.615 | 0.590 | 95.8 | **Exceeds ideal — true structural width** ✅ |
| Bicep | 0.197 | 0.210 | 93.9 | Slightly small; grows with continued training |
| Hips | 0.441 | 0.490 | 90.1 | Below division ideal — partially fat |
| Forearm | 0.144 | 0.165 | 87.5 | Below ideal |
| Neck | 0.200 | 0.230 | 86.7 | Thin relative to height |
| Thigh | 0.254 | 0.300 | 84.5 | Expected — thighs not judged in physique |
| Calf | 0.178 | 0.215 | 83.0 | **Lowest — structural weakness confirmed** |
| **Overall HQI** | | | **91.1** | |

**Coach check:** HQI 91.1 sounds high but is correct — these ratios represent your *shape* corrected for fat, not your absolute stage readiness. Your proportional framework (especially shoulder width) is genuinely good for this division. The HQI measures "if you were at 5% BF, are your proportions correct?" — and mostly yes, except calves. ✅

**Caveat:** HQI 91.1 should be communicated as "your proportional blueprint is strong" not "you're 91% ready to compete."

---

### 3C. Aesthetic Vector & Proportion Analysis

**Proportion vector:** Site ratios (lean-adjusted circumference / height) compared to division ideal via cosine similarity + RMSE.

**Your ratios vs Men's Physique ideal:**

| Site | Your Lean Ratio | Ideal | Gap | Priority Rank |
|------|----------------|-------|-----|---------------|
| Hips | 0.441 | 0.490 | −10.0% | **#1** |
| Thigh | 0.254 | 0.300 | −15.3% | **#2** |
| Calf | 0.178 | 0.215 | −17.2% | **#3** |
| Neck | 0.200 | 0.230 | −13.0% | #4 |
| Forearm | 0.144 | 0.165 | −12.7% | #5 |
| Bicep | 0.197 | 0.210 | −6.2% | #6 |
| Chest | 0.516 | 0.520 | −0.8% | #7 |
| Waist | 0.425 | 0.420 | +1.2% | #8 (slight excess) |
| Shoulders | 0.615 | 0.590 | +4.2% | #9 (you exceed ideal) |

**Aesthetic score:** 70.0 / 100
```
cosine_similarity = ~0.999 (correct shape direction)
RMSE blend:  aesthetic = (0.5 × cosine + 0.5 × rmse_score) × 100
             rmse_score penalizes magnitude gaps even when direction is right
```

**Coach check:** Priority list of hips → thigh → calf → neck is exactly what a coach would say for a tall Men's Physique competitor. The hips ranking high at #1 is partly fat (will self-correct on cut) and partly real (glutes). Calves at #3 are the only site that won't improve from cutting — these need direct work. Shoulders exceeding the ideal is a genuine positive. ✅

---

### 3D. PDS — Physique Development Score

**Formula:**
```
PDS = (aesthetic × 0.40) + (muscle_mass × 0.30) + (conditioning × 0.20) + (symmetry × 0.10)
```

**Component breakdown:**

| Component | Score | Weight | Points | How computed |
|-----------|-------|--------|--------|-------------|
| Aesthetic | 70.0 | 40% | 28.0 | Cosine+RMSE vs division vector |
| Muscle Mass | 64.9 | 30% | 19.5 | LCSA 2,439 / ceiling 3,760 |
| Conditioning | 49.5 | 20% | 9.9 | `100 − |22.1 − 12.0| × 5 = 49.5` |
| Symmetry | 98.0 | 10% | 9.8 | Bilateral tape variance ≈ 0 |
| **PDS** | **67.2** | | | **Intermediate** |

**Conditioning score detail:**
```
Offseason ideal BF% for male = 12%
Your BF% = 22.1%
Deviation = 10.1 percentage points
Score = max(0, 100 − 10.1 × 5) = 49.5
```

**Tier:** Intermediate (50–70) — upper end at 67.2.

**Coach check:** Completely accurate for an intermediate lifter at 22% BF offseason. The conditioning score (49.5) is the biggest drag — and it should be, you are 10 points above ideal offseason BF. When you cut to 10–12% for stage, conditioning jumps to ~90+, which contributes +8 points to PDS immediately (20% weight), pushing PDS toward 75+. ✅

**Symmetry at 98.0:** All bilateral pairs are within 0.5 cm. This is legitimately excellent symmetry for a lifter. ✅

---

### 3E. Weight Cap (Casey Butt Formula)

**What it measures:** Your structural genetic ceiling for lean mass based on bone frame.

**Formula (adapted Casey Butt):**
```
max_LBM_lbs = height_in^1.5 × (√wrist_in / 22.667 + √ankle_in / 17.010) × (1 + BF% / 224)
Inputs: height = 74.0 in, wrist = 6.73 in, ankle = 9.17 in, BF% = 5%
```

**Results:**

| Metric | Value | Notes |
|--------|-------|-------|
| Max LBM | 86.4 kg (190.5 lbs) | Structural genetic ceiling |
| Stage weight @ 5% BF | 90.9 kg (200.4 lbs) | Target contest weight |
| Offseason weight @ 12% BF | 98.2 kg (216.5 lbs) | Maximum healthy offseason |

**Your current position:**
- Current LBM: 73.32 kg
- Genetic ceiling: 86.4 kg
- **Remaining headroom: 13.1 kg (~29 lbs) of natural muscle growth**
- Current offseason weight (94.12 kg) is within your cap (98.2 kg) ✅

**Coach check:** Wrist at 17.1cm is slightly below avg, which pulls your ceiling down modestly. 86.4 kg max LBM is very achievable at a natural level. You have ~29 lbs of muscle-building headroom at 3 years of training — likely 4–6 years of quality training to realize fully. The fact that you're currently under your offseason weight cap is a healthy sign. ✅

---

## 4. Engine 1 — Trajectory & Feasibility

### 4A. PDS Trajectory (52 weeks)

**Model:** Asymptotic decay — progress slows as you approach ceiling.
```
ceiling = min(95, PDS + 30) = 95.0
rate = f(experience_years)  [3 years = moderate rate]
PDS(week) = ceiling − (ceiling − start) × e^(−rate × week)
```

| Timepoint | Week | Predicted PDS | Tier |
|-----------|------|--------------|------|
| Now | 0 | 67.2 | Intermediate |
| 3 months | 13 | 75.0 | Advanced |
| 6 months | 26 | 81.1 | Advanced |
| 1 year | 52 | 88.8 | Elite |

**Coach check:** The jump from 67.2 → 75.0 in 13 weeks is plausible — a cut from 22% → 14% BF alone would spike conditioning score enough to contribute +5 PDS points. Elite at 88.8 in 52 weeks is optimistic but not impossible given competition motivation. ✅ The asymptotic model is the correct shape — gains slow at higher PDS scores.

### 4B. Feasibility — PDS 82 (Advanced) by Competition

```
Target: 82.0  |  Current: 67.2  |  Gap: 14.8 pts  |  Time: 54 weeks
Result: FEASIBLE ✅
Estimated time to reach target: 29 weeks (by October 2026)
Max weekly gain: 0.5 PDS points/week
Confidence: 63%
```

**Coach check:** 14.8 points in 54 weeks at 0.27 pts/week average is achievable. Most of the gain comes from conditioning improvement (cutting BF) rather than adding muscle. 63% confidence is appropriately uncertain for a 12-month projection. ✅

---

## 5. Engine 1 — Prep Timeline

**Competition date:** 2027-03-28 | **Weeks out:** 53 | **Current phase:** Offseason

| Parameter | Value |
|-----------|-------|
| Phase label | Offseason |
| Calorie modifier | 1.15× TDEE |
| Training cue | Maximum volume and intensity. Prioritize lagging muscle groups. |
| Nutrition cue | Permissive surplus. Prioritize performance and progressive overload. |

**Recommended competition prep timeline for this athlete:**

| Period | Duration | Phase |
|--------|----------|-------|
| Now → ~Nov 2026 | Weeks 53–20 | Offseason / lean bulk |
| Nov 2026 → Jan 2027 | Weeks 20–12 | Transition / begin cut |
| Jan 2027 → Mar 2027 | Weeks 12–1 | Full competition prep |
| Mar 21–28, 2027 | Week 1 | Peak week |

**Coach check:** At 53 weeks out, offseason classification is exactly right. Plenty of time to build before cutting. ✅

---

## 6. Engine 3 — Nutrition Controller

### 6A. TDEE

```
BMR (Mifflin-St Jeor, male):
  = (10 × 94.12) + (6.25 × 188) − (5 × 25) + 5
  = 941.2 + 1,175 − 125 + 5 = 1,996 kcal

PAL multiplier: 1.55 (5 training days/week, moderate)
TDEE = 1,996 × 1.55 = 3,094 kcal
```

**Coach check:** 3,094 kcal for a 207 lb male training 5 days/week is in the right ballpark (typical range 2,900–3,400). The 1.55 multiplier is standard but may slightly underestimate for heavy compound training. Real TDEE is likely 3,200–3,400. ⚠️ Minor underestimate — acceptable.

### 6B. Macro Prescription (Maintain Phase, anchored to LBM)

```
Protein : 1.9 g/kg LBM = 1.9 × 73.32 = 139.3g  (557 kcal)
Fat     : 0.8 g/kg LBM = 0.8 × 73.32 =  58.7g  (528 kcal)
Carbs   : (3,094 − 557 − 528) / 4   = 502.2g  (2,009 kcal)
Total   : 3,094 kcal
```

| Macro | Amount | kcal | % of total |
|-------|--------|------|-----------|
| Protein | 139.3g | 557 | 18% |
| Fat | 58.7g | 528 | 17% |
| Carbs | 502.2g | 2,009 | 65% |

**Coach check:** Protein at 139g is evidence-based (1.9 g/kg LBM is within 1.6–2.2 g/kg range). However, at 22% BF the Navy BF% estimate has ±3–4% error, meaning LBM could be 70–77 kg → protein range 133–147g. Many coaches would use 1g/lb total bodyweight (207g) as a simpler rule with built-in buffer. Worth entering caliper measurements to sharpen LBM.

Fat at 58.7g is the minimum floor — may be too low for optimal testosterone production in an offseason male. Consider raising to 80–90g in offseason (1.1 g/kg LBM).

Carbs at 502g is high but mathematically correct given the large TDEE and protein/fat minimums. Appropriate for high-volume training. ✅

### 6C. Peri-Workout Carb Distribution

| Timing | Carbs | % of daily |
|--------|-------|-----------|
| Pre-workout (2–3h before) | 175.8g | 35% |
| Intra-workout | 50.2g | 10% |
| Post-workout (within 1h) | 125.5g | 25% |
| Other meal(s) | 150.7g | 30% |

**Coach check:** The 35/10/25/30 split is evidence-informed. At 4 meals, only 1 meal is outside the peri-workout window — 150.7g in a single non-training meal is a large carb load. Would suggest splitting into 2 other meals if meal count allows. ✅ Formula logic is correct; meal count is the constraint.

### 6D. Men's Physique Division Nutrition Priorities

```
Carb cycling: ±30% training vs rest days
Fat floor:    0.75 g/kg LBM
Meal target:  5/day (configured at 4 — 1 below recommendation)
MPS threshold: 35g protein per meal (minimum to stimulate muscle protein synthesis)
```

At 4 meals and 139g protein: 139 / 4 = **34.8g per meal** — just under the 35g MPS threshold. Consider increasing to 5 meals or bumping protein slightly to ensure each meal stimulates MPS.

---

## 7. Flags & Recommendations

| # | Flag | Severity | Recommendation |
|---|------|----------|----------------|
| 1 | **Fat floor too low for offseason** | ⚠️ Medium | 0.8 g/kg LBM → 58.7g fat is near-minimum for hormonal health in a male. Raise to 1.0–1.1 g/kg LBM in offseason (~73–80g fat). |
| 2 | **Protein per meal below MPS threshold** | ⚠️ Medium | 34.8g/meal at 4 meals is ~1g under the 35g MPS stimulus threshold. Add a 5th meal or increase total protein to 150g. |
| 3 | **TDEE likely 5–10% low** | 🔵 Low | 1.55 PAL may underestimate 5-day heavy training. Real TDEE probably 3,200–3,400. Consider 1.65 PAL. |
| 4 | **Navy BF% ≈ ±3–4% accurate** | ⚠️ Medium | All LBM-anchored outputs depend on this estimate. Enter 7-site Jackson-Pollock calipers for precision. |
| 5 | **HQI 91.1 may be miscommunicated** | 🔵 Low | HQI measures proportional shape, not stage-readiness. Needs clear UI messaging. |
| 6 | **Calves are a genuine structural priority** | ✅ Confirmed | Calf LCSA (78.77) is lowest site; HQI 83.0; priority rank #3. Needs 3–4x/week direct work. |
| 7 | **Back strength lagging** | 🔵 Note | Row (187 lbs) vs bench (260 lbs) = 72% ratio. For V-taper, target 85%+ (row ≥220 lbs). |
| 8 | **Strength not used in PDS** | 🔵 Feature gap | 1RM data logged but not integrated into any score component. Strength-to-BW ratio could sharpen Mass Score. |

---

## 8. Real Coach Verdict

> **Measurements check out.** At 6'2", 207 lbs, 22% BF, 3 years training — PDS of 67.2 (Intermediate) is accurate and honest.
>
> **What the algorithm got right:**
> - Conditioning is dragging you down (correct — 22% BF is far from stage)
> - Shoulders are your best asset (correct — 131 cm at 6'2" is genuinely wide)
> - Calves are your structural weak point (correct — 15" at 6'2" is below average)
> - Back prioritization is implied by the low row-to-bench ratio
>
> **Competition path at 53 weeks out:**
> 1. Offseason lean bulk through ~November 2026 (add LBM while staying under 98.2 kg offseason cap)
> 2. Begin cut around 18–20 weeks out (November)
> 3. Target stage weight ~90–92 kg at 8–10% BF
> 4. Hit calves hard year-round — they won't respond to cut-phase training alone
> 5. Prioritize rowing movements to close the push/pull gap
>
> **The engines are coaching you correctly.**

---

*Audit generated: 2026-03-19 | Coronado v1.0*
