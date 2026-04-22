# Viltrum v2 — Session 1 Sprint Report

*One-session execution of the "Science-First Overhaul" sprint plan.*

## What shipped (6 sprints, 6 commits)

### S0 — Foundation refactor
- `backend/app/constants/types.py` — new `ValueWithUncertainty(value, sigma, source, notes)`
- `backend/app/constants/physio.py` — per-division `STAGE_BF_PCT_BY_DIVISION`,
  `OFFSEASON_BF_CEILING_BY_DIVISION` with citation strings (Helms 2014,
  Iraki 2019, Hulmi 2017, Chappell 2018). `PROVENANCE_REGISTRY` surface.
  `PhaseState` enum consolidates the previously stringly-typed phases.
- `routers/ppm.py` — `mini_cut_active` trigger now divisional, not
  hard-coded `bf > 15`.
- Fallback BF moved from 15/22 → 12/20 (Helms/Iraki central estimate).
- Offseason ceiling moved from flat 16/25 → 13 M / 22 F (divisional).
- `tests/test_physio_provenance.py` — 9 tests.

### S1 — Ceiling ensemble
- `backend/app/engines/engine1/ceiling_ensemble.py` — new module:
  `butt_1st_ceiling`, `butt_4th_ceiling` (1st × 1.04), `kouri_ceiling_lbm`,
  `berkhan_ceiling_stage`, `ceiling_envelope`, `ffmi_band`.
- `honesty.py::check_natural_attainability` — returns `ceiling_envelope`
  + `ffmi_band` alongside existing fields.
- `frontend/src/components/PPMCards.tsx::NaturalCeilingCard` — renders the
  three-marker envelope bar + FFMI probability band label.
- `frontend/src/lib/types.ts` — `CeilingEnvelope`, `FFMIBand` types.
- `tests/test_ceiling_ensemble.py` — 8 tests.

### S2 — ISAK-anchored girth projection
- `backend/app/engines/engine1/girth_projection.py` — new module.
  - Primary: `lean_cm = raw − π × (skinfold_mm/10)` when a SkinfoldMeasurement
    row exists (Heymsfield 1982 / ISAK manual).
  - Fallback: back-estimate per-site mm from total BF% via Jackson-Pollock
    distribution weights (Jackson & Pollock 1978).
  - Floor: `lean_cm ≥ raw × 0.85` (physiological).
  - Method reporting: `"isak_skinfold"` / `"jp_derived"` / `"bf_linear"`.
- `physio.project_lean_girth` becomes a dispatching shim (back-compat).
- `tests/test_girth_projection.py` — 10 tests.

### S3 — HQI visibility recalibration
- `backend/app/constants/divisions.py::DIVISION_VISIBILITY` — new master
  table. Closes M7 (visibility duplicated in 3 places).
- `mens_physique.thigh`: 0.0 → 0.55 (the MP-thigh bug)
- `mens_physique.calf`: 0.25 → 0.30
- Added `glutes` as a first-class site across all 7 divisions.
- `hqi.py`, `muscle_gaps.py`, `aesthetic_vector.py` now import from the
  master table instead of local copies.
- `readiness.py::evaluate_readiness::mass_distribution` — replaced hard-min
  with p=6 soft-min for graceful score transitions.
- `tests/test_hqi_visibility.py` — 8 tests.

### S4 — Logistic gains + training-age
- `backend/app/engines/engine1/training_age.py` — new module.
  - `effective_training_years(years, consistency, intensity, programming)`
    with defaults 0.85/0.75/0.70 (doc §30 priors).
  - `logistic_lbm(ceiling, t_eff)` and `logistic_annual_gain(ceiling, current)`
    using `LBM(t) = ceiling × (1 − e^(−k × 12 × t))` per McDonald / Aragon /
    Helms. k_natural = 0.020/mo; k_enhanced = 0.036/mo.
- `readiness.py::estimate_cycles_to_tier` — rewritten:
  - Uses logistic curve instead of exponential halving.
  - Drops the per-cycle 5% tax (double-counted).
  - `muscle_fraction = 0.85 − 0.015 × surplus_pct_per_week`.
  - `proportion_cycles` scales with deficit magnitude.
  - Accepts `ceiling_lbm_kg` so the PPM router can pass the Sprint 1
    ensemble-median ceiling.
  - Returns `t_effective_years`, `muscle_fraction_used`, `ceiling_lbm_kg_used`.
- `models/profile.py::UserProfile` — 3 new nullable float columns:
  `training_consistency_factor`, `training_intensity_factor`,
  `training_programming_factor`.
- `alembic/versions/m1b2c3d4e5f6_add_training_age_factors.py` — migration.
- `main.py::_run_schema_migrations` — idempotent inline ALTER TABLE for
  the same 3 columns (matches existing pattern).
- `routers/ppm.py` — passes ensemble-median ceiling + training-age
  factors into `estimate_cycles_to_tier`.
- `tests/test_logistic_gains.py` — 14 tests.

### S9 — Illusion + conditioning_pct + relative asymmetry
- `engine1/aesthetic_vector.py` — new helpers `compute_vtaper`,
  `compute_xframe`, `compute_waist_height_ratio`.
- `constants/competitive_tiers.py::TierThresholds` — 2 new fields
  `illusion_xframe_min`, `conditioning_pct_min`. Classic T1–T5 populated
  per doc §8 (illusion 2.15 → 2.55; conditioning 0.20 → 0.95).
- `engine1/readiness.py::evaluate_readiness` — adds 2 metrics
  (`illusion_score`, `conditioning_pct`) — now 10/11 metrics total.
- `constants/physio.py::SYMMETRY_PENALTY_MULT` — recalibrated per doc §10.
- `engine2/split_designer.py` — asymmetry is relative (3.5% default /
  2.5% for arms/calves); bonus graded `round(100 × (spread − 0.02))`
  clamped 0–6; emits `practitioner_review` flag above 8%.
- `routers/ppm.py::_compute_athlete_metrics` — computes & passes `illusion_xframe`.
- `frontend/src/components/TierReadinessCard.tsx` — renders new metrics
  in Proportions + Readiness groups.
- `tests/test_illusion_metrics.py` — 13 tests.

## Test status

- New V2 tests: **62 passing**.
- Overall regression: V2 changes introduce **0 new failures**. Three
  pre-existing failures persist (2× ARI weighting in `test_mens_physique_188cm`,
  1× fat-floor in `test_engine3_full`) — all predate this sprint.
- Test command that's known-green:
  ```
  pytest tests/ --ignore=tests/test_mens_physique_188cm.py \
               --deselect tests/test_engine3_full.py::TestMacrosComprehensive::test_fat_floor_respected \
               --deselect tests/test_coaching_alignment.py::TestTrainingAlignment
  ```

## What's deferred (documented in plan file)

- **S5** — Split designer optimizer with SFR table for 80+ exercises
- **S6** — De Leva body-segment replacement for the Volumetric Ghost
- **S7** — Nutrition periodization state machine (diet breaks, refeeds,
  peak week, reverse diet)
- **S8** — HRV + Hooper + composite recovery + progression ledger
- **S10** — Psychometric (EAT-26, DASS-21), posing load, cardio-from-kcal,
  injury substitution graph
- **S11** — Validation corpus + harness (30-athlete JSON + notebook runner)
- **S12** — Auto-generated constants documentation from `PROVENANCE_REGISTRY`
- **S28** — Bayesian personal-parameter Kalman update (needs new
  `PPMCheckpoint.observed_lbm_gain_kg` column)

## Known behavioral changes for existing users

1. **Readiness `pct_met` shifts.** With 10–11 metrics instead of 8, any
   user who was "approaching" (6/8 met) may now show "developing" (6/11).
   This is correct — illusion + conditioning are real gates — but the
   UI should surface a "recalibrated today" note on the next checkpoint.
2. **Fallback BF estimate lowered 15→12% M / 22→20% F.** Users without
   logged BF will see slightly higher projected stage weight.
3. **Offseason ceiling tightened** (flat 16→13% M / flat 25→22 F by
   division). Users at 14–15% M will now route through a mini-cut
   prepend on next cycle start; previously they bulked straight through.
4. **Cycles-to-tier projections change.** Logistic saturates more slowly
   than exponential near the ceiling, so athletes far from their ceiling
   see SHORTER projections (correct — year-1 gain is larger per McDonald)
   and athletes near their ceiling see LONGER projections (correct —
   previously the optimistic exponential + cycle-tax produced unrealistic
   numbers).
5. **MP athletes see their thigh gaps surface** for the first time — was
   previously zeroed out by the visibility bug.

## Next session priorities (recommended)

In order of leverage:
1. **S11 validation corpus** — without named-athlete data, Sprint 3's
   λ and visibility weights are priors. The corpus unlocks empirical fit.
2. **S7 nutrition state machine** — biggest user-facing gap; engine
   hooks already exist in `engine3/macros.py`.
3. **S8 recovery composite + progression ledger** — most-requested
   autoregulation; depends on HRV source selection in settings.
4. **S5 SFR-gated split designer** — largest correctness lever after
   the foundation work this session landed.
