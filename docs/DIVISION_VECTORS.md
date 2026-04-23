# Division Vectors

Ideal proportion vectors per IFBB/NPC division. Values are circumference-to-height ratios (or linear breadth-to-height for `back_width`).

> **V2 calibration (2026-04):** Classic Physique waist tightened from 0.432 → **0.405** and shoulder_to_waist lifted from 1.389 → **1.75** to match the modern Olympia-Classic envelope (CBum 52″/29″ ≈ 1.79). Chest also raised 0.540 → **0.560** to push chest:waist toward Reeves' 148 % ideal. Men's Physique chest reduced 0.520 → 0.525 (V3 fix to preserve Open > Classic > MP hierarchy).

| Division | Neck | Shoulders | Chest | Bicep | Forearm | Waist | Hips | Thigh | Calf | Back Width | Shoulder:Waist | V-Taper |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **Men's Open** | 0.243 | 0.618 | 0.550 | 0.230 | 0.175 | 0.447 | 0.520 | 0.340 | 0.230 | 0.265 | 1.382 | 1.618 |
| **Classic Physique** | 0.238 | 0.600 | **0.560** | 0.220 | 0.170 | **0.405** | 0.510 | 0.340 | 0.230 | 0.258 | **1.75** | 1.618 |
| **Men's Physique** | 0.225 | 0.590 | 0.525 | 0.220 | 0.168 | 0.415 | 0.500 | 0.310 | 0.215 | 0.260 | 1.422 | 1.618 |
| **Women's Figure** | 0.195 | 0.530 | 0.490 | 0.170 | 0.145 | 0.395 | 0.530 | 0.320 | 0.210 | 0.210 | 1.342 | 1.342 |
| **Women's Bikini** | 0.190 | 0.500 | 0.470 | 0.155 | 0.138 | 0.385 | 0.575 | 0.330 | 0.205 | 0.198 | 1.299 | 1.299 |
| **Women's Physique** | 0.200 | 0.550 | 0.500 | 0.185 | 0.152 | 0.405 | 0.520 | 0.310 | 0.215 | 0.220 | 1.358 | 1.358 |

(Wellness division also defined in code; not duplicated here — see `divisions.py`.)

## Notes

- **Back Width** — linear axillary breadth ÷ height (not a circumference). Men's Open targets the highest lat spread.
- **Shoulder : Waist** — circumferential ratio. Classic's 1.75 is the modern Olympia drift above the Grecian φ; older docs anchored to φ (1.618) which now becomes the **T5 floor** in `competitive_tiers.py`.
- **V-Taper** — the same φ ideal across all male divisions; weighted aesthetic ratio used in PDS.
- **Chest:Waist** — Reeves' classical ideal 1.48; modern Classic winners run 1.74+. Encoded indirectly via the chest + waist vectors.

## Source

Implementation in `backend/app/constants/divisions.py::DIVISION_VECTORS`. Visibility weights (`DIVISION_VISIBILITY`) and ceiling factors (`DIVISION_CEILING_FACTORS`) live in the same file. Tier-scaled gaps are in `engine1/muscle_gaps.py::TIER_IDEAL_SCALING`.

*Last updated 2026-04-23.*
