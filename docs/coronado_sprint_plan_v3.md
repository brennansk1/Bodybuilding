# Coronado — Sprint Plan v3

**Date:** 2026-04-01  
**Scope:** Full codebase audit + exercise database replacement + generation pipeline repair  
**Estimated Total Effort:** 95–125 hours (core blocks)

---

## Execution Order

```
0 (Schema) → 2A (Exercise DB & Pipeline) → 1 (Auto-Save) → 2 (FST-7) → 8 (Bugs) → 3 (UI) → 4 (Check-Ins) → 6 (Start Date) → 7 (Meal Regen) → 5 (Mini-Cut) → 9 (Improvements)
```

Block 2A moves to the front because every downstream block depends on correct exercise data. The curated database fixes GEN-01 (movement patterns), GEN-02 (delt sub-groups), and GEN-05 (equipment names) in one stroke. The FST-7 rework (Block 2) and rest timer both depend on correct movement_pattern values that only exist after 2A ships.

---

## Block 0 — Migrations & Schema (3–4 hours)

| # | Task | Hours |
|---|------|-------|
| 0.1 | Add `rest_seconds` (nullable int) and `is_fst7` (bool, default false) to TrainingSet model + Alembic migration | 0.5 |
| 0.2 | Add `load_type` (nullable String(20)) to Exercise model + migration — stores plates/dumbbells/cable/machine_plates/plate_loaded/bodyweight | 0.5 |
| 0.3 | Add `program_start_date` (nullable Date) to UserProfile model + migration | 0.5 |
| 0.4 | Add `started_at` and `completed_at` (nullable DateTime) to TrainingSession model + migration | 0.5 |
| 0.5 | Add `recorded_date` to DailyCheckin schema for backfill support | 0.5 |
| 0.6 | Add `dup_profile` (nullable String(10)) to TrainingSession model — stores heavy/moderate/light | 0.5 |

---

## Block 2A — Curated Exercise Database & Generation Pipeline (18–22 hours)

This is the highest-priority block. It replaces the broken 2551-exercise MegaGym database with a curated 185-exercise competitive bodybuilding database and fixes the six generation pipeline failures (GEN-01 through GEN-06).

### Phase 1: Exercise Database Replacement (6–8 hours)

| # | Task | Hours |
|---|------|-------|
| 2A.1 | Create `exercises_curated.py` with ~185 exercises: correct `primary_muscle` (front_delt/side_delt/rear_delt), correct `movement_pattern` (push/pull/squat/hinge/isolation/carry), correct `equipment` (matching frontend names), and `load_type` for the resistance progression system | 3 |
| 2A.2 | Update `seed.py` to import from `exercises_curated.py` as the primary source. Remove the MAX_PER_MUSCLE=25 cap (curated list is already the right size). Populate the new `load_type` column on Exercise during seeding | 2 |
| 2A.3 | Delete `exercises_full.py` (the 2551-exercise MegaGym database with broken metadata) | 0.5 |
| 2A.4 | Write a data migration script that wipes the existing exercises table and re-seeds from curated data. Handle FK references: strength_baselines and training_sets that reference old exercise_ids need to be matched by name to new exercise_ids, or orphaned gracefully | 2 |
| 2A.5 | Validate: run the priority cascade keyword matcher against the new database — verify all 98 priority keywords from `exercise_priorities.py` have at least one matching exercise | 0.5 |

### Phase 2: Generation Pipeline Fixes (8–10 hours)

| # | Task | Hours |
|---|------|-------|
| 2A.6 | Fix delt sub-group lookup: add fallback in session loop — if `by_muscle.get(db_muscle)` returns empty and `db_muscle` is a delt sub-group, fall back to `by_muscle.get("shoulders", [])` + apply sub-role filter. Wire the currently-dead `delt_role` parameter (line 898, hardcoded to None) to actually pass the sub-group | 2 |
| 2A.7 | Wire DUP profile metadata through session generation: read `day["dup_profile"]`, `day["intensity_range"]`, and `day["rep_range"]` from mesocycle output. Store `dup_profile` on TrainingSession. When `_rep_range()` has no `load_type`, fall back to the DUP rep_range instead of equipment-based heuristic | 3 |
| 2A.8 | Scale prescribed weights by DUP intensity: for heavy days, compute weight from 1RM at the heavy intensity range (70–80%); for light days, use the light range (55–65%). Currently all days use the same single `compute_weight_from_1rm(baseline, rep_target)` with no intensity modifier | 2 |
| 2A.9 | Fix `_allocate_sets` operation ordering: move sub-region guarantee BEFORE compound-before-isolation sort (prevents sub-region swap from breaking compound ordering). This also prevents sub-region swap from overwriting the FST-7 exercise (GEN-06) | 1 |
| 2A.10 | Validate end-to-end: write a test that generates a full mesocycle for a Men's Physique user and verifies: (a) no deadlifts or barbell rows appear, (b) side_delt exercises are present, (c) heavy days have lower rep ranges than light days, (d) compound exercises appear before isolations within each muscle group, (e) overflow credits fire correctly (triceps volume reduced by pressing spillover) | 2 |

### Phase 3: Equipment Filter Fix (1 hour)

| # | Task | Hours |
|---|------|-------|
| 2A.11 | Fix equipment filter in `training.py`: replace the hardcoded `== "bodyweight"` fallback with a normalization map that handles `body_only→bodyweight`, `e_z_curl_bar→barbell`, `kettlebells→dumbbell`, `none→bodyweight`. Apply normalization at seed time so the Exercise table always uses frontend-compatible names | 1 |

---

## Block 1 — Workout Auto-Save (Critical Path) (10–14 hours)

| # | Task | Hours |
|---|------|-------|
| 1.1 | Backend: Create `PATCH /engine2/session/{session_id}/set/{set_id}` endpoint for per-set persistence | 3 |
| 1.2 | Frontend: Wire `markSetDone` / `markSetDoneNowPlaying` to fire PATCH on set completion | 3 |
| 1.3 | Frontend: Add debounced auto-save on input field changes (weight/reps/rpe) — 1.5s idle → PATCH | 2 |
| 1.4 | Frontend: Remove "Save Progress" button, replace with progress-only bar + "Finish Session" button | 1.5 |
| 1.5 | Frontend: Add "Finish Session" confirmation modal that triggers progression check + session complete | 1.5 |
| 1.6 | Frontend: Fix destructive state wipe on date navigation — derive completion from server response | 2 |
| 1.7 | Fix BUG-05: Add session_id to localStorage payload, validate on restore | 1 |

---

## Block 2 — FST-7 Rearchitecture & Rest Timer Protocol (14–18 hours)

**Depends on Block 2A** — requires correct movement_pattern values to distinguish compound from isolation, and correct delt sub-group tagging for division-specific FST-7 targeting.

| # | Task | Hours |
|---|------|-------|
| 2.1 | Backend: **Remove** FST-7 override from `_allocate_sets()` (delete lines 408–424 of training.py) | 0.5 |
| 2.2 | Backend: Move `_FST7_TARGETS` from dead `periodization.py::apply_fst7()` into `training.py` as the canonical division-specific target list. Extend with FST-7 finisher exercise recommendations per body part from the research report (pec deck for chest, machine lateral raise for shoulders, straight arm pulldown for back, etc.) | 1 |
| 2.3 | Backend: Create session-level `_apply_session_fst7(session_id, db_muscle_info, fst7_mode, division, hqi_scores)` that picks ONE exercise per session — prefer highest-priority lagging muscle, select a machine/cable isolation from the session's exercises, convert it to 7 FST-7 sets with `is_fst7=True` and mode-appropriate `rest_seconds` | 4 |
| 2.4 | Backend: Wire `fst7_mode` from mesocycle week data through session generation loop — skip FST-7 entirely when mode is `"none"` (deload week 6) | 1.5 |
| 2.5 | Backend: After FST-7 applied, **renumber `set_number`** on all session TrainingSets so FST-7 sets have the highest numbers (placed last in session — the finisher is always the final exercise) | 2 |
| 2.6 | Backend: Implement FST-7 intensity differentiation — moderate (45s rest, RIR 2, weeks 1–2), aggressive (35s, RIR 1, weeks 3–4), extreme (30s, RIR 0, week 5) | 1 |
| 2.7 | Backend: Build rest-time lookup table for ALL non-FST-7 sets using `movement_pattern` × `load_type` and populate `rest_seconds` during set creation. Heavy compound: 180–300s, moderate compound: 120–180s, heavy isolation: 90–120s, moderate isolation: 60–90s, warmup: 60s | 2 |
| 2.8 | Backend: Include `rest_seconds`, `is_fst7`, `movement_pattern`, `load_type`, and `fst7_note` in session GET response | 1 |
| 2.9 | Frontend: Replace hardcoded 180/90 with per-set `rest_seconds` from API | 1 |
| 2.10 | Frontend: Display protocol label on timer ("FST-7 finisher: 30s", "Heavy compound: 3:00") + visual FST-7 badge on exercise in workout UI | 1 |
| 2.11 | Frontend: Fix `isCompoundExercise` to use `movement_pattern` from backend instead of position-based check | 0.5 |
| 2.12 | Delete dead `apply_fst7()` function from `periodization.py` (targets migrated in 2.2) | 0.5 |

---

## Block 3 — Workout UI Polish (6–8 hours)

| # | Task | Hours |
|---|------|-------|
| 3.1 | Increase input field sizes in overview mode (padding, font size) | 1 |
| 3.2 | Add muscle group headers / exercise group separators in accordion view | 1.5 |
| 3.3 | Collapse cardio section by default on training days (expandable) | 1 |
| 3.4 | Standardize ghost data display between Now Playing and overview modes | 1 |
| 3.5 | Fix BUG-04: Strength log display respects useLbs toggle | 0.5 |
| 3.6 | Fix BUG-03: Check if cardio already logged today on page load | 1 |
| 3.7 | Add rest timer audio/vibration alert on completion (IMP-03 + IMP-04) | 1.5 |

---

## Block 4 — Missed Check-In Handling (12–16 hours)

| # | Task | Hours |
|---|------|-------|
| 4.1 | Backend: Create `GET /checkin/gaps?since={date}` endpoint — returns missing daily + workout dates | 3 |
| 4.2 | Backend: Create `POST /checkin/daily/backfill` endpoint with date parameter + validation | 2 |
| 4.3 | Backend: Fix weekly adherence calculation to average across the full week, accounting for gaps | 3 |
| 4.4 | Backend: Fix BUG-02 — add duplicate AdherenceLog detection/deletion | 0.5 |
| 4.5 | Frontend: Build gap resolution form component (list missed days, quick-fill forms) | 4 |
| 4.6 | Frontend: Integrate gap resolution as pre-step in weekly check-in flow | 2 |
| 4.7 | Frontend: Add dashboard check-in streak indicator (IMP-06) | 2 |

---

## Block 5 — Mini-Cut Trigger Logic (8–10 hours)

| # | Task | Hours |
|---|------|-------|
| 5.1 | Backend: Add `compute_bf_threshold_from_weight_cap()` helper to `weight_cap.py` | 2 |
| 5.2 | Backend: Add mini-cut evaluation step in weekly check-in pipeline (after Engine 1) | 3 |
| 5.3 | Backend: Create `POST /engine3/phase/transition` endpoint for phase changes | 2 |
| 5.4 | Frontend: Display mini-cut recommendation in weekly check-in results with accept/dismiss CTA | 2 |
| 5.5 | Frontend: Update settings to show computed threshold when `cut_threshold_bf_pct` is empty | 1 |

---

## Block 6 — Program Start Date (3–4 hours)

| # | Task | Hours |
|---|------|-------|
| 6.1 | Backend: Add `program_start_date` to profile GET/PATCH endpoints, allowed_fields | 0.5 |
| 6.2 | Backend: Use `program_start_date` in `services/training.py` session scheduling | 1.5 |
| 6.3 | Frontend: Add date picker to onboarding profile step | 1 |
| 6.4 | Frontend: Add field to settings page | 0.5 |

---

## Block 7 — Meal Plan Auto-Regen (4–6 hours)

| # | Task | Hours |
|---|------|-------|
| 7.1 | Frontend: Decouple meal plan regen from full engine pipeline in settings save | 1.5 |
| 7.2 | Frontend: Detect which fields changed and only regen meal plan for nutrition-relevant changes | 1.5 |
| 7.3 | Backend: Invalidate MealPlanTemplate cache when NutritionPrescription changes in weekly check-in | 1.5 |
| 7.4 | Frontend: Add "Regenerating meal plan..." toast feedback | 0.5 |

---

## Block 8 — Bug Fixes & Cleanup (3–4 hours)

| # | Task | Hours |
|---|------|-------|
| 8.1 | Fix BUG-01: StrengthLog substitute exercise write (look up exercise_id by name) | 1.5 |
| 8.2 | Add error handling for substitute exercise not found in DB (create custom exercise or warn) | 1 |
| 8.3 | Add session duration tracking (started_at/completed_at) — wire to Now Playing start + Finish Session | 1 |

---

## Block 9 — Greenlighted Improvements (Variable)

Pending your approval. Recommended priority order:

1. IMP-02: Swipe navigation in Now Playing (3–4h)
2. IMP-05: Exercise swap searchable dropdown (4–6h)
3. IMP-11: Deload notification banner (3–4h)
4. IMP-12: Progressive overload chart (4–6h)
5. IMP-01: Offline-first workout mode (8–12h)
6. IMP-07: Weekly summary export (6–8h)
7. IMP-09: Rate limiting on check-in endpoints (2h)
8. IMP-10: Exercise video/cue links (4–6h)

---

## Summary

| Block | Description | Hours | Priority |
|-------|-------------|-------|----------|
| 0 | Migrations & Schema | 3–4 | Must-do first |
| 2A | Curated Exercise DB & Pipeline Repair | 18–22 | **Critical — everything depends on this** |
| 1 | Workout Auto-Save | 10–14 | Critical |
| 2 | FST-7 Rearchitecture & Rest Timer | 14–18 | Critical |
| 3 | Workout UI Polish | 6–8 | High |
| 4 | Missed Check-In Handling | 12–16 | High |
| 5 | Mini-Cut Trigger Logic | 8–10 | Medium |
| 6 | Program Start Date | 3–4 | Medium |
| 7 | Meal Plan Auto-Regen | 4–6 | Medium |
| 8 | Bug Fixes & Cleanup | 3–4 | High |
| 9 | Greenlighted Improvements | Variable | Low–Medium |
| | **Core scope (Blocks 0–8 + 2A)** | **95–125h** | |
| | **With all improvements** | **130–170h** | |

---

## Post-Deployment Notes

**Program regeneration required.** After Blocks 2A and 2 ship, every existing user needs their program regenerated. Add a one-time admin endpoint or migration script that bulk-regenerates all active programs against the new exercise database. Old programs will have exercise_ids pointing to deleted exercises from the MegaGym dataset.

**Exercise DB is the single source of truth.** After this sprint, the curated database is THE exercise list. If you or users want to add exercises in the future, they go into `exercises_curated.py` with all required metadata (movement_pattern, load_type, primary_muscle with delt sub-groups, equipment matching frontend names). The seeder handles the rest.

**Division-aware exercise filtering.** The research report includes a full division exercise selection matrix (what each division prioritizes, de-emphasizes, or avoids). This data currently lives in `exercise_priorities.py` for the priority cascade, and in `_DIVISION_EXERCISE_BANS` for hard bans. After this sprint, the exercise_priorities cascade + the curated DB together ensure that a Men's Physique user never sees deadlifts and a Bikini user never gets barbell bench pressing. No additional filtering layer is needed — the priority cascade handles it by simply not having those exercises in the relevant division's keyword lists.

**Offseason → Prep exercise shifts.** The research shows athletes systematically swap free weights for machines during prep (barbell squat → hack squat, barbell row → machine row, etc.). This can be implemented as a future improvement: the phase engine already knows if the user is in offseason vs. prep, so the priority cascade could have phase-aware priority ordering. Not in this sprint's scope, but the curated DB has the machine alternatives available for when you build it.
