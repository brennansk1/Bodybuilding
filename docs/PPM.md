# Perpetual Progression Mode (PPM)

Structured 14- or 16-week improvement cycles for off-season athletes.
Instead of a single comp-prep timeline, PPM drives the athlete through
repeated mesocycle-scale improvement blocks, each anchored to a target
competitive tier (T1–T5 — see [`COMPETITIVE_TIERS.md`](./COMPETITIVE_TIERS.md)).

PPM is an **orchestrator**, not an engine. It spans E1 → E2 → E3 and
lives in `backend/app/routers/ppm.py`.

---

## 1. Why PPM exists

Contest prep is a ~20-week tunnel. Off-season athletes without a booked
show need the same structure — measurable targets, periodization,
recoverable volume, adherence gating — without the contest date. PPM
re-anchors all of that to a **competitive tier target** instead. The
athlete picks a tier they want to be "credible at," and each 14-week
cycle closes some fraction of the gap.

At the end of every cycle, `/ppm/checkpoint` re-runs readiness against
the target tier and writes `current_achieved_tier` back to the profile.
The TierBadge UI component shows the progression.

---

## 2. Cycle shape

### Baseline — 14 weeks

| Weeks | Sub-phase | What happens |
|---|---|---|
| 1 | `ppm_assessment` | Fresh HQI + tape snapshot. Tier re-evaluation. |
| 2–5 | `ppm_accumulation` | MEV → MAV volume ramp. Heavy focus on limiting muscles. |
| 6–9 | `ppm_intensification` | MAV → MRV. Intensification techniques (drop sets, rest-pause, FST-7) fire. |
| 10 | `ppm_deload` | 50% volume, RPE cap 7. |
| 11–13 | `ppm_intensification` (block 2) | Second push phase with revised programming. |
| 14 | `ppm_checkpoint` | Measurements + photos + next-cycle planning. |

`ppm_phase_for_week(week, mini_cut_active)` in
`engine1/prep_timeline.py` is the authoritative mapping.

### With mini-cut prepend — 16 weeks

When the athlete starts a cycle above the offseason BF ceiling
(`physio.OFFSEASON_BF_CEILING` — 16 % male / 25 % female), the planner
**prepends** a 2-week mini-cut so they're entering the growth block at
an accumulation-friendly body fat.

| Weeks | Sub-phase |
|---|---|
| 1–2 | `ppm_mini_cut` (2-week aggressive deficit) |
| 3 | `ppm_assessment` |
| 4–7 | `ppm_accumulation` |
| 8–11 | `ppm_intensification` |
| 12 | `ppm_deload` |
| 13–15 | `ppm_intensification` (block 2) |
| 16 | `ppm_checkpoint` |

---

## 3. The start-cycle flow

`POST /api/v1/ppm/start-cycle` runs three gates before writing state:

```
1. Honesty gate        ── engines/engine1/honesty.check_natural_attainability
                           Refuses T3+ enrollment for natural athletes whose
                           Casey-Butt/Kouri ceilings don't support the tier.
2. Readiness eval      ── engines/engine1/readiness.evaluate_readiness
                           Returns the 10-gate breakdown + limiting factor.
3. Plan build          ── _build_cycle_plan (routers/ppm.py:751)
                           Pulls HQI site gaps → design_split → 14/16-week
                           macros + volume allocation.
```

On success, writes `ppm_enabled=True`, `target_tier`, `current_cycle_number += 1`,
`current_cycle_start_date = today`, `current_cycle_week = 1`,
`cycle_focus_muscles = [<top 3 limiting>]` to the profile.

---

## 4. Plan builder — what's in each weekly block

`_build_cycle_plan` (backend/app/routers/ppm.py:751) composes engine
primitives. For each of the N weeks it produces:

```python
{
  "week": 1..N,
  "ppm_sub_phase": "ppm_accumulation",     # from ppm_phase_for_week()
  "landmark_zone": "mev_to_mav",           # first muscle's zone for the header
  "rir": 2,
  "fst7_mode": "none" | "priority" | ...,
  "per_muscle_sets": {
      <muscle>: {"target_sets", "is_focus", "landmark", "rir", "fst7_mode"},
      ...
  },
  "macros": {"protein_g", "carbs_g", "fat_g", "target_calories",
             "carb_cycle": {...}},
  "day_rotation": [{"day_name", "muscles"}, ...],
}
```

`per_muscle_sets` comes from `engine2/periodization.compute_cycle_mesocycle`.

---

## 5. Manual nutrition-mode override (V3)

Profile column `nutrition_mode_override` (one of `bulk`, `lean_bulk`,
`maintain`, `cut`, `mini_cut`, `peak_week`, `restoration`) lets the user
explicitly opt out of PPM phase detection.

**Scope of override:** macros only. Training rhythm still follows the
`ppm_*` sub-phase arc because mechanical stimulus should not re-sync on
user whim.

Implementation in `_build_cycle_plan`:

```python
macro_phase = prof.nutrition_mode_override or sub_phase
macros = compute_macros(tdee, phase=macro_phase, …)
```

---

## 6. Structural priority muscles (V3)

Profile column `structural_priority_muscles` (JSONB list) adds
**persistent** specialization that PPM's limiting-factor reassignment
won't erase. Engine 2's `split_designer` boosts need scores for these
muscles regardless of current gap size.

Practical effect: an athlete chasing T4 Classic who wants eternal
emphasis on calves + rear delts lists them here; each cycle's
auto-rotated `cycle_focus_muscles` will still grant them bonus sets on
top of whatever the limiting-muscle analysis selects.

---

## 7. Achieved-tier classification (V3)

Written by `/ppm/checkpoint`:

```python
current_achieved_tier = max(tier for tier in CompetitiveTier
                            if readiness.pct_met_for(tier) >= 0.90)
```

Surfaced in the TierBadge component as `T{achieved} → T{target}`. Read
from `GET /ppm/status`.

---

## 8. Projection math

Used by `/insights/tier-projection` (V3 Tier Timing widget).

Inputs:
- LBM gap (target stage LBM − current LBM)
- Logistic gain curve: `LBM(t) = ceiling × (1 − e^(−k·t))`
- Monthly `k` constants from `engines/engine1/readiness.py`:
  - `K_MONTHLY_NATURAL = 0.020`
  - `K_MONTHLY_ENHANCED = 0.030`
- V3 effective-`k` scaling: `k_eff = k × (consistency × intensity × programming)`, floored at 0.25.

`project_tier_timing_across_adherence` returns timing under three profiles:

| Profile | Consistency × Intensity × Programming | Adherence product |
|---|---|---:|
| HIGH | 0.95 × 0.90 × 0.85 | 0.727 |
| MEDIUM | 0.80 × 0.75 × 0.70 | 0.420 |
| LOW | 0.60 × 0.55 × 0.50 | 0.165 |

This is what the "What if I dialed adherence up?" column on the tier
timing widget reflects.

---

## 9. Endpoints

| Endpoint | Purpose |
|---|---|
| `GET /ppm/status` | Current cycle + week + target + achieved tier |
| `POST /ppm/evaluate` | Run readiness against target tier without writing |
| `POST /ppm/attainability` | Natural-ceiling gate (honesty check) |
| `POST /ppm/start-cycle` | Honesty → readiness → plan → write profile |
| `GET /ppm/plan/{week}` | Rebuild and return one week's plan |
| `POST /ppm/checkpoint` | End-of-cycle snapshot → `PPMCheckpoint` |
| `GET /ppm/history` | All prior checkpoints |
| `POST /ppm/transition-to-comp` | Disable PPM + set `competition_date` |
| `POST /ppm/disable` | Turn PPM off, wipe cycle state |

Full endpoint index: [`API_REFERENCE.md`](./API_REFERENCE.md).

---

## 10. Frontend touch points

| Component | Purpose |
|---|---|
| `TierReadinessCard.tsx` | 10-gate breakdown with 4-tier status (Met / Close / Developing / Far) |
| `CycleProgressCard` (PPMCards.tsx) | Current cycle progress bar + focus muscles |
| `TierBadge.tsx` | Achieved → target chip, surfaced across widgets |
| `TierTimingCard` (V3InsightCards.tsx) | Projection-across-adherence table |

See [`DASHBOARD_WIDGETS.md`](./DASHBOARD_WIDGETS.md) for the full widget
catalog and their endpoints.

---

## 11. Data model

### `ppm_checkpoints` table

One row per cycle checkpoint. First-class columns for
every readiness metric (queryable for cross-cycle charting) + three
JSONB snapshots that enable full **Prep Replay** reconstruction:
`macros_snapshot`, `training_snapshot`, `volume_snapshot`. See
[`DATABASE_SCHEMA.md § 7`](./DATABASE_SCHEMA.md) for the full column list.

### Profile columns involved

`ppm_enabled`, `target_tier`, `current_achieved_tier`,
`current_cycle_number`, `current_cycle_start_date`, `current_cycle_week`,
`cycle_focus_muscles`, `nutrition_mode_override`,
`structural_priority_muscles`, and the training-age factor trio
(`training_consistency_factor`, `training_intensity_factor`,
`training_programming_factor`). See
[`DATABASE_SCHEMA.md § 2`](./DATABASE_SCHEMA.md).

---

*Last updated 2026-04-23.*
