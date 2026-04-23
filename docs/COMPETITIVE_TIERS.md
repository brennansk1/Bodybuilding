# Competitive Tiers — Full Reference

Single source of truth for the 5-tier Perpetual Progression Mode (PPM) ladder, every gate that defines each tier, what each gate measures, and how the program uses the data.

Anchored to **Classic Physique** in this first PPM pass; other divisions extend the same schema (`backend/app/constants/competitive_tiers.py::TIER_THRESHOLDS`).

---

## 1 — The Tiers at a Glance

| Tier | Code | Label | What it represents | Realistic federation |
|------|------|-------|---------------------|----------------------|
| **T1** | `LOCAL_NPC` | Local NPC | First-show ready. Presentable, within rules, not expected to win. | NPC local / regional |
| **T2** | `REGIONAL_NPC` | Regional NPC | Class-win contender at regional NPC shows. | NPC regional |
| **T3** | `NATIONAL_NPC` | National NPC | Competitive at NPC nationals (USA, Universe, Nationals). | NPC national qualifiers |
| **T4** | `PRO_QUALIFIER` | IFBB Pro Qualifier | Stage-ready for nationals + realistic pro-card contention. Within 1–3 lb of weight cap. | NPC USA / North Americans / Nationals |
| **T5** | `OLYMPIA` | Olympia Contender | Pro-card holder competing at the highest level. At weight cap. | IFBB Pro League · Olympia |

---

## 2 — Gate Threshold Matrix (Classic Physique)

Every cell below is a **hard gate** the athlete must clear to be classified at that tier (10 gates total per tier — see §4 for the readiness math).

### Mass + composition

| Metric | T1 | T2 | T3 | T4 | T5 |
|---|---:|---:|---:|---:|---:|
| Weight as % of IFBB cap (min–max) | 80–87 % | 87–92 % | 92–97 % | 97–100 % | 100 % |
| Stage body-fat % (range) | 6–8 % | 5–7 % | 4–6 % | 3–5 % | 3–4 % |
| Sum-of-3 skinfolds (mm, advisory) | ≤ 35 | ≤ 25 | ≤ 18 | ≤ 12 | ≤ 8 |
| Normalized FFMI (min) | 22.0 | 24.0 | 25.5 | 27.0 | 28.5 |

### Proportions (circumferential ratios)

| Metric | T1 | T2 | T3 | T4 | T5 |
|---|---:|---:|---:|---:|---:|
| Shoulder : Waist (min) | 1.40 | 1.50 | 1.55 | 1.60 | **1.618 (φ)** |
| Chest : Waist (min) | 1.30 | 1.38 | 1.42 | 1.46 | 1.48 |
| Arm · Calf · Neck parity (max diff, in) | ≤ 1.5″ | ≤ 1.0″ | ≤ 0.5″ | ≤ 0.25″ | matched |
| Illusion (X-frame) min | 2.15 | 2.25 | 2.35 | 2.45 | **2.55** |

### Readiness composites

| Metric | T1 | T2 | T3 | T4 | T5 |
|---|---:|---:|---:|---:|---:|
| HQI (app-internal) min | 40 | 55 | 70 | 82 | 90 |
| Conditioning % min | 20 % | 50 % | 75 % | 90 % | 95 % |

### Maturity gate (soft, advisory)

| Status | T1 | T2 | T3 | T4 | T5 |
|---|---:|---:|---:|---:|---:|
| Training years (natural) | ≥ 3 | ≥ 5 | ≥ 7 | ≥ 10 | **N/A** |
| Training years (enhanced) | ≥ 3 | ≥ 4 | ≥ 6 | ≥ 7 | ≥ 10 |

> T5 OLYMPIA for natural athletes is flagged as **not naturally attainable** by the honesty gate (`engine1/honesty.check_natural_attainability`). The training-years column shows 99 to encode "never" rather than a real threshold.

---

## 3 — What Each Gate Means

Every metric below is one of the 10 gates evaluated in `engine1/readiness.py::evaluate_readiness`.

### `weight_cap_pct` — Stage-projected weight as fraction of division cap

- **What:** Your projected stage weight ÷ your IFBB Classic-Physique weight cap for your height. Stage weight is computed by stripping current body fat down to the implied stage BF (5 %).
- **Why it matters:** Each tier has a min cap-percentage you need to credibly fill. T1 = 80 % of cap; T5 = 100 % of cap.
- **Your-frame example (188 cm):** weight cap is 105.2 kg. T2 floor is 87 % × 105.2 = **91.5 kg stage weight** required.
- **Source:** `constants/weight_caps.py::lookup_weight_cap` — Ground Truth audit (2024 IFBB Pro League table).

### `bf_pct` — Stage body fat %

- **What:** Predicted body fat at stage day, derived from current BF + planned cut trajectory.
- **Why:** Every tier carries a band (e.g. T2 = 5–7 %). Below the floor you're "too dry" for Classic; above the ceiling you're "soft on stage."
- **Source:** Withers 1997 4-compartment model, Rossow 2013 drug-free pro case data.

### `skinfold_sum3` — Jackson-Pollock 3-site sum

- **Status:** Advisory, not gating in the readiness metric count.
- **What:** Sum of chest + abdominal + thigh skinfolds (mm).
- **Why:** Cross-validates BF % when manual entry is suspect.

### `ffmi_normalized` — Fat-Free Mass Index, normalized

- **What:** LBM (kg) ÷ height² (m), normalized to 6'0" so it's comparable across heights. Kouri-style normalization.
- **Why:** The single best mass marker independent of weight class. Natural ceiling is ~25; T4+ implies enhancement for most frames.
- **Source:** Kouri 1995 (FFMI natural ceiling).

### `shoulder_waist_ratio` — V-taper

- **What:** Shoulder circumference ÷ waist circumference.
- **Why:** Classic's defining silhouette. Grecian ideal = 1.618 (φ). Modern Classic Olympia winners run **1.70–1.79**.
- **Reference athletes:** CBum 52″/29″ ≈ 1.79.

### `chest_waist_ratio` — Reeves-style upper-to-mid

- **What:** Chest circumference ÷ waist circumference.
- **Reeves ideal:** 1.48 (148 % of waist). Modern Classic winners exceed 1.74.

### `arm_calf_neck_parity` — Reeves equal-circumference rule

- **What:** Maximum absolute difference (inches) between arm, calf, and neck circumferences.
- **Why:** Reeves' classical standard says all three should match. Classic judges look for it specifically.
- **Reference:** Reeves at peak (6'1", 215 lb): 18.5″ / 18.5″ / 18.5″.

### `illusion_xframe` — X-frame ratio

- **What:** (shoulders × hips) ÷ waist². Captures the "X" silhouette that lets a lighter athlete beat a heavier one with worse proportions.
- **Why:** Tier 2 = 2.25; Olympia level ≈ 2.55.
- **Source:** v2 Sprint 9, `engine1/aesthetic_vector.compute_xframe`.

### `conditioning_pct` — Fraction of offseason → stage range closed

- **What:** `(offseason ceiling − current BF) ÷ (offseason ceiling − stage target)`.
- **Why:** Captures cut progress without pinning to absolute BF (which varies by athlete).
- **Tier read:** T1 = 20 %, T5 = 95 %. At 0 % you're at offseason ceiling; at 100 % you're at stage target.

### `hqi` — Hypertrophy Quality Index

- **What:** Visibility-weighted average of `pct_of_ideal` per site. Stay-small sites (waist/hips) penalize when over-ideal; grow sites cap at 100 %.
- **Why:** Single-number summary of how close lean muscle size is to the divisional ideal across all judged sites.
- **Source:** `engine1/muscle_gaps.compute_avg_pct_of_ideal` (V3 averaging fix landed 2026-04-22).

### `training_years` — Maturity gate (soft)

- **What:** Chronological training years.
- **Why:** Even with elite genetics + perfect adherence, mass + neural maturation take time. Soft gate — you can be flagged below it but it doesn't block tier classification on its own.

### `mass_distribution` — Mass-distribution worst-site check (gate #10)

- **What:** Worst-site `pct_of_ideal` across the seven primary sites (chest / shoulders / bicep / thigh / calf / forearm / neck) must be ≥ 85 %.
- **Why:** Catches lopsided physiques that score well on average HQI but have one severely lagging site that judges will spot immediately. Surfaced as `worst_sites` in the readiness payload.
- **Source:** R4.C — added as an explicit gate to the 10-metric count.

---

## 4 — Readiness State Math

`engine1/readiness.py::evaluate_readiness` computes a state from how many of the 10 gates the athlete clears:

| State | `pct_met` band | UI badge color |
|---|---:|---|
| `not_ready` | < 60 % | iron / limestone |
| `developing` | 60 – 84 % | adriatic blue |
| `approaching` | 85 – 99 % | aureus gold |
| `stage_ready` | 100 % | laurel green |

`current_achieved_tier` (V3) is the highest tier where `pct_met ≥ 0.90` — written back to the Profile at each PPM checkpoint.

---

## 5 — Tier-Scaled Ideals (V3)

The gap displayed in **Muscle Gaps** / **Heatmap** widgets is computed against **tier-scaled** ideals so a Tier-1 athlete isn't told their bicep is 9 cm short of an Olympia-level target they don't care about.

`muscle_gaps.TIER_IDEAL_SCALING`:

| Target tier | Scaling factor applied to grow-site ideals | Stay-small (waist/hips) |
|---|---:|---|
| T1 | 0.87 × | unchanged |
| T2 | 0.92 × | unchanged |
| T3 | 0.96 × | unchanged |
| T4 | 1.00 × | unchanged |
| T5 | 1.03 × | unchanged |

Anchored to each tier's `weight_cap_pct_min`. Waist/hips pass through at the absolute ideal — those are ceilings (a T1 athlete still wants a small waist), not targets to approach from below.

---

## 6 — Per-Cycle Projection Math

`readiness.estimate_cycles_to_tier` projects how many 14-week PPM improvement cycles separate the athlete from the target tier.

Inputs:
- LBM gap (target stage LBM − current LBM)
- Logistic gain curve `LBM(t) = ceiling × (1 − e^(−k·t))`
- `k` constant: `K_MONTHLY_NATURAL = 0.020`, `K_MONTHLY_ENHANCED = 0.030`
- **V3 fix (2026-04-22):** `k_eff = k × (consistency × intensity × programming)` floored at 0.25

Projections cross-cut by adherence in `project_tier_timing_across_adherence`:

| Profile | Consistency × Intensity × Programming | Adherence product |
|---|---|---:|
| HIGH (elite) | 0.95 × 0.90 × 0.85 | **0.727** |
| MEDIUM (typical serious lifter) | 0.80 × 0.75 × 0.70 | **0.420** |
| LOW (inconsistent) | 0.60 × 0.55 × 0.50 | **0.165** |

---

## 7 — Honesty Gate (`engine1/honesty.py`)

Before tier selection commits, the app compares Casey-Butt + Kouri natural ceilings to the tier's required stage weight + FFMI. Returns `overall_attainable: bool` plus per-component breakdown.

For natural athletes:
- T1–T2: usually attainable
- T3: borderline depending on frame
- T4+: typically not naturally attainable for most frames
- T5: not naturally attainable

For enhanced athletes the gate is much wider but still flips for very small-framed athletes targeting T4+.

---

## 8 — Anchor Athletes (Reference Data)

| Athlete | Height | Stage wt | Arms | Chest | Waist | Thighs | Calves | S:W | C:W |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Chris Bumstead | 6'1" / 185 cm | 225–230 lb | 21–22″ | 51–52″ | 29–30″ | 28–30″ | 18–20″ | 1.79 | 1.79 |
| Ramon Dino | 5'11" / 180 cm | ~227 lb | ~20″ | ~50″ | ~29″ | ~28″ | ~18″ | 1.72 | 1.72 |
| Terrence Ruffin | 5'5"–5'7" / 167 cm | 170–187 lb | ~18″ | ~47″ | ~27″ | ~25″ | ~17″ | 1.74 | 1.74 |
| Urs Kalecinski | ~5'11" / 180 cm | ~220 lb | ~20″ | ~49″ | ~29″ | ~27″ | ~17″ | 1.69 | 1.69 |
| Wesley Vissers | 6'2"–6'3" / 190 cm | 216–245 lb | ~20″ | ~50″ | ~30″ | ~28″ | ~18″ | 1.67 | 1.67 |

These define the de-facto T5 envelope. Sources: fitnessvolt.com, generationiron.com, greatestphysiques.com.

---

## 9 — IFBB Classic Physique Weight Caps (2024–2026)

The mass gate is anchored to this table (`constants/weight_caps.py`). Lookup is by height in cm.

| Height | Cap (lb) | Cap (kg) |
|---|---:|---:|
| ≤ 5'4" (162.6 cm) | 167 | 75.7 |
| ≤ 5'5" (165.1 cm) | 172 | 78.0 |
| ≤ 5'6" (167.6 cm) | 177 | 80.3 |
| ≤ 5'7" (170.2 cm) | 182 | 82.6 |
| ≤ 5'8" (172.7 cm) | 187 | 84.8 |
| ≤ 5'9" (175.3 cm) | 194 | 88.0 |
| ≤ 5'10" (177.8 cm) | 202 | 91.6 |
| ≤ 5'11" (180.3 cm) | 209 | 94.8 |
| ≤ 6'0" (182.9 cm) | 217 | 98.4 |
| ≤ 6'1" (185.4 cm) | 224 | 101.6 |
| ≤ 6'2" (188.0 cm) | 232 | **105.2** |
| ≤ 6'3" (190.5 cm) | 239 | 108.4 |
| ≤ 6'4" (193.0 cm) | 246 | 111.6 |
| ≤ 6'5" (195.6 cm) | 253 | 114.8 |
| ≤ 6'6" (198.1 cm) | 260 | 117.9 |
| ≤ 6'7" (200.7 cm) | 267 | 121.1 |
| > 6'7" | 274 | 124.3 |

---

## 10 — Sources

### Peer-reviewed
- Helms, Aragon, Fitschen 2014. JISSN 11:20. Contest prep nutrition.
- Morton et al. 2018. Br J Sports Med 52:376. Protein meta-analysis.
- Iraki et al. 2019. Sports 7:154. Offseason nutrition review.
- Roberts et al. 2020. J Hum Kinet 71:191. Physique athlete nutrition.
- Escalante et al. 2021. BMC Sports Sci Med Rehabil 13:68. Peak week evidence.
- Schoenfeld & Krieger 2017. Volume dose-response.
- Kouri et al. 1995. Clin J Sport Med 5(4):223. FFMI natural ceiling.
- Rossow et al. 2013. IJSPP 8:582. Natural BB case study.

### Federation rules
- IFBB Men's Classic Physique Rules 2024.
- NPC Classic Physique Rules.
- IFBB Pro League Weight Caps.

### Applied
- Steve Reeves, *Building the Classic Physique the Natural Way*.
- Casey Butt, *Your Muscular Potential* (weightrainer.net).
- Hany Rambod FST-7 system (evogennutrition.com).

---

## 11 — Code Pointers

| File | Role |
|---|---|
| `backend/app/constants/competitive_tiers.py` | Tier enum + threshold dataclass + `CLASSIC_PHYSIQUE_TIERS` table |
| `backend/app/constants/weight_caps.py` | IFBB weight caps by height |
| `backend/app/constants/divisions.py` | Per-division proportion vectors + visibility weights |
| `backend/app/engines/engine1/readiness.py` | `evaluate_readiness`, `compute_achieved_tier`, `estimate_cycles_to_tier`, `project_tier_timing_across_adherence` |
| `backend/app/engines/engine1/honesty.py` | `check_natural_attainability` — Casey-Butt + Kouri natural ceiling check |
| `backend/app/engines/engine1/muscle_gaps.py` | `TIER_IDEAL_SCALING`, `compute_all_gaps_tier_aware`, `compute_avg_pct_of_ideal` (V3 averaging fix) |
| `backend/app/engines/engine1/aesthetic_vector.py` | `compute_xframe`, `compute_chest_waist_ratio`, `compute_arm_calf_neck_parity` |
| `backend/app/routers/ppm.py` | `/ppm/evaluate`, `/ppm/attainability`, `/ppm/status` |
| `backend/app/routers/insights.py` | `/insights/tier-projection`, `/insights/sensitivity` |
| `frontend/src/components/TierReadinessCard.tsx` | Per-gate status card with 4-tier classification (Met / Close / Developing / Far) |

---

*Generated 2026-04-23. Aligned with backend revision `8312471`.*
