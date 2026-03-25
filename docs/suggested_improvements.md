# Coronado — Suggested Improvements

> Grounded in the current codebase. Each item references the specific engine, router, or component it would extend. Organized by impact tier within each category.

---

## Part 1 — Coaching Algorithm Improvements

### Tier 1 — High Impact, Core to the Coaching Goal

---

**C1 — Body Fat Percentage from Skinfolds (Jackson-Pollock)**
- **Problem:** `pds.py` scores conditioning using `body_fat_pct` but the system never *computes* body fat. Skinfold measurements (7 sites) are already collected in `checkin/biological` and stored in `skinfold_measurements`.
- **Fix:** Add a `body_fat.py` engine using the Jackson-Pollock 7-site formula for males and females. Wire it into `run_full_diagnostic()` in `services/diagnostic.py`. This makes the conditioning score meaningful instead of always returning the 50.0 default.
- **Files:** New `engines/engine1/body_fat.py`, `services/diagnostic.py`

---

**C2 — Peri-Workout Carbohydrate Timing Split**
- **Problem:** `macros.py` returns a flat daily carb target. Competitive bodybuilders distribute carbs specifically: high pre-workout (2–3h before), moderate intra-workout (fast carbs during), low post-workout/rest day. This is standard contest-prep coaching.
- **Fix:** Add `compute_peri_carb_split(carbs_g, training_day, meal_count)` to `macros.py` that allocates ~40% carbs pre-workout, ~10% intra, ~30% post, and distributes the rest across other meals. Engine 3 prescription endpoint surfaces this as `meal_timing` field.
- **Files:** `engines/engine3/macros.py`, `routers/engine3.py`

---

**C3 — Nutrition Periodization: Training Day vs. Rest Day Split**
- **Problem:** Currently every day has identical macros. This misses a key tool — carb cycling, where training days get more carbs and rest days get fewer (fat fills the gap). This is almost universal in bodybuilding prep.
- **Fix:** `compute_macros()` already accepts a `phase`. Add `is_training_day: bool`. Training days: +20% carbs, -corresponding fat. Rest days: -20% carbs, +fat to maintain calories. Surface as `training_day_macros` / `rest_day_macros` in the prescription response.
- **Files:** `engines/engine3/macros.py`, `routers/engine3.py`, `frontend/src/app/nutrition/page.tsx`

---

**C4 — ARI-Triggered Early Deload (Sustained Red Zone)**
- **Problem:** `periodization.py` deloads on a fixed every-4th-week schedule regardless of actual fatigue. If a user's ARI stays in the red zone for 5+ consecutive days, they need an immediate deload — not to wait for the scheduled one.
- **Fix:** In `checkin/process`, check the last 5 days of `ari_log`. If all are in red zone, flag `early_deload_recommended = True` in the process response and optionally shift the current week's sessions to deload volume (50% of normal). Display a warning card in the training UI.
- **Files:** `routers/checkin.py`, `services/training.py`

---

**C5 — Compound-Specific Progression Increments**
- **Problem:** `resistance.py` uses a flat `2.5kg` increment for all exercises. This is too much for isolation movements (cable curls, lateral raises) and too little for big compounds (deadlift, squat). This causes stalled progression on small muscles and under-loads big ones.
- **Fix:** Add an increment lookup table to `resistance.py` keyed on movement pattern: `barbell compound → 5kg`, `dumbbell compound → 2kg`, `cable/isolation → 1kg`, `bodyweight → 0 (rep only)`. `compute_progression()` accepts an optional `weight_increment` override that the session log endpoint derives from the exercise's movement pattern and equipment.
- **Files:** `engines/engine2/resistance.py`, `routers/engine2.py`

---

**C6 — Volume Landmarks (MEV / MAV / MRV) Cap**
- **Problem:** Currently, volume just increases `+1 set/week` indefinitely until deload. The system doesn't respect Maximum Recoverable Volume — past a certain set count per muscle per week, more volume causes fatigue without adaptation.
- **Fix:** Add a `VOLUME_LANDMARKS` dict to `periodization.py` with per-muscle MEV (minimum effective volume), MAV (maximum adaptive volume), and MRV (maximum recoverable volume) ranges based on published data (Israetel). Cap weekly set progression at `MRV` for each muscle. If volume allocation would exceed MRV, reduce frequency or intensity instead.
- **Files:** `engines/engine2/periodization.py`

---

**C7 — Phase Auto-Detection from Weight Trend**
- **Problem:** Phase (bulk/cut/maintain) is set during onboarding and never changes automatically. The kinetic engine `kinetic.py` already computes `compute_rate_of_change()` — if the user's rate deviates significantly from their stated phase target for 3+ weeks, the system should flag it and suggest a phase correction.
- **Fix:** In `checkin/process`, after computing the kinetic adjustment, compare the 4-week weight trend to the expected rate for the current phase. If the athlete is in "cut" but gaining weight, surface an alert: "Your weight trend (+0.3 kg/week) doesn't match your cut phase. Consider adjusting calories." Already have the data — just needs the comparison and alert logic.
- **Files:** `routers/checkin.py`, `services/nutrition.py`

---

**C8 — Strength Baseline Staleness Warning**
- **Problem:** Program generation uses 1RM baselines to prescribe working weights. After 12+ weeks, these numbers are outdated — the athlete is likely stronger, meaning all prescribed weights are light. No mechanism currently flags stale baselines.
- **Fix:** In `generate_program_sessions()`, check the most recent `StrengthBaseline.recorded_date`. If it's older than 90 days, return a `baseline_stale: true` flag in the `program/generate` response. Frontend shows a banner: "Your strength baselines are 3+ months old — consider re-testing for accurate weight prescriptions."
- **Files:** `services/training.py`, `routers/engine2.py`, `frontend/src/app/training/page.tsx`

---

**C9 — Exercise Rotation Between Mesocycles**
- **Problem:** The same exercises appear every mesocycle because `generate_program_sessions()` always picks the top-ranked exercises. Repeating the same movements creates staleness, joint overuse, and missed stimulus from different movement vectors.
- **Fix:** Track `last_mesocycle_exercises` per user (JSONB on `UserProfile` preferences). During `generate_program_sessions()`, deprioritize exercises used in the previous mesocycle (reduce their biomechanical score by 30%) to ensure automatic variety. After program generation, store the selected exercise IDs.
- **Files:** `services/training.py`, `models/profile.py`

---

**C10 — Bro Split Support**
- **Problem:** `periodization.py` supports PPL, Upper/Lower, and Full Body. "Bro Split" (chest Monday, back Tuesday, shoulders Wednesday, arms Thursday, legs Friday) is one of the most popular splits among intermediate-advanced bodybuilders and is currently missing.
- **Fix:** Add `bro_split` to `_SPLIT_TEMPLATES` in `periodization.py`. Days: Chest, Back, Shoulders, Arms (biceps + triceps), Legs. Update the frontend settings page to offer it as a training split option.
- **Files:** `engines/engine2/periodization.py`, `frontend/src/app/settings/page.tsx`

---

**C11 — Competition Prep Timeline Engine**
- **Problem:** The system has no concept of structured prep phases — it doesn't know that 16 weeks out you should still be building, 12 weeks out you enter cut, 1 week out is peak week. A competitive bodybuilder needs the system to auto-transition phases based on competition date proximity.
- **Fix:** Add a `prep_phase_for_date(competition_date, current_date)` function to a new `engines/engine1/prep_timeline.py`. Returns: `offseason` (>16 weeks out), `lean_bulk` (12–16 weeks), `cut` (4–12 weeks), `peak_week` (≤1 week), `contest`. Wire into the `checkin/process` endpoint to auto-update `profile.phase` when the phase should transition. Notify the user when a phase change occurs.
- **Files:** New `engines/engine1/prep_timeline.py`, `routers/checkin.py`

---

**C12 — Peak Week Protocol**
- **Problem:** The current `phase = "peak"` just applies a -700 kcal offset. An actual peak week protocol is a structured 7-day protocol: carb depletion Mon/Tue, moderate Wed, carb loading Thu/Fri/Sat, maintenance Sunday (show day). Water, sodium, and potassium manipulation are also standard.
- **Fix:** Add a `compute_peak_week_protocol(body_weight_kg, show_date)` function returning a 7-day meal plan with specific carb/water/sodium targets per day. New endpoint `GET /engine3/peak-week` returns the protocol when competition date ≤ 7 days. Frontend: dedicated peak-week view replacing normal nutrition page.
- **Files:** New `engines/engine3/peak_week.py`, `routers/engine3.py`, new `frontend/src/app/nutrition/peak-week/page.tsx`

---

**C13 — Warm-Up Set Prescription**
- **Problem:** The training session only shows working sets. Without warm-up guidance, athletes either skip warm-ups (injury risk) or waste time over-warming up. A proper warm-up protocol is essential coaching.
- **Fix:** In the session view, for the first exercise per muscle group, display a prescribed warm-up scheme based on working weight. Standard protocol: `40% × 10 → 60% × 5 → 75% × 3 → 85% × 1 → work weight`. These are display-only (not logged). Add a collapsible "Warm-Up Sets" section above the working set table.
- **Files:** `frontend/src/app/training/page.tsx`

---

**C14 — HRV Resting Heart Rate Contribution to ARI**
- **Problem:** `ari.py` collects resting HR but the comment states "Currently used as a sanity gate but not weighted into the composite." Resting HR elevation is a validated indicator of insufficient recovery — ignoring it weakens the ARI signal.
- **Fix:** Integrate resting HR into ARI as a 4th component: compare today's HR to the 14-day rolling average. HR elevated >5 bpm above baseline = -10 to -20 ARI points. Rebalance weights: HRV 35%, Sleep 25%, Soreness 25%, HR 15%.
- **Files:** `engines/engine2/ari.py`

---

### Tier 2 — Meaningful Coaching Additions

---

**C15 — Wearable Data Import (Garmin / Apple Health CSV)**
- **Problem:** Users must manually enter RMSSD and resting HR daily. This is the biggest friction point in the check-in flow — many users will skip it. Most athletes already have this data in their wearable's app.
- **Fix:** Add `POST /api/v1/checkin/import-hrv` that accepts a CSV upload (Garmin Connect export format or Apple Health XML export). Parse RMSSD and resting HR columns, bulk-insert into `hrv_log` for historical dates. Eliminates the need to ever manually enter HRV data.
- **Files:** New `routers/checkin.py` endpoint, `frontend/src/app/checkin/page.tsx`

---

**C16 — Custom Exercise Creation**
- **Problem:** The exercise database is seeded from MegaGym but users may have specialty equipment, unique variations, or home gym setups not in the database. Exercises not in the DB can't be tracked in structured sessions.
- **Fix:** Add `POST /api/v1/engine2/exercises` to create custom exercises (name, primary_muscle, equipment, movement_pattern). Custom exercises get a `user_id` FK and are included in exercise pools for that user's programs. Frontend: "Add Custom Exercise" button in the exercise library page.
- **Files:** `routers/engine2.py`, `models/training.py`, `frontend/src/app/training/exercises/page.tsx`

---

**C17 — Symmetry-Driven Unilateral Exercise Prioritization**
- **Problem:** `pds.py` computes a symmetry score from bilateral measurements but the training system doesn't *act* on asymmetries. If the left bicep is measurably smaller than the right, the program should prioritize unilateral exercises and/or prescribe more volume to the lagging side.
- **Fix:** During `generate_program_sessions()`, read bilateral tape measurements from the most recent check-in. For muscles with >5% left/right asymmetry, prefer exercises tagged as `unilateral` (dumbbell, cable single-arm) over bilateral barbell movements for that muscle.
- **Files:** `services/training.py`, `routers/engine2.py`

---

**C18 — Supplement Timing Log**
- **Problem:** Creatine loading, pre-workout caffeine timing, and intra-workout EAAs are standard bodybuilding practices that affect training output. Not tracking them means the system can't correlate supplement use with ARI/performance trends.
- **Fix:** New optional `supplements` JSONB field on `HRVLog` (or separate table). Check-in step 2 (Recovery) gets a quick supplement checklist: creatine ✓, pre-workout ✓, protein shake ✓. Log as boolean per item. No engine changes needed initially — just data collection for future correlation analysis.
- **Files:** `models/training.py` or new model, `routers/checkin.py`, `frontend/src/app/checkin/page.tsx`

---

**C19 — Fat Loss Rate Guardrail (LBM Protection)**
- **Problem:** The kinetic engine allows aggressive calorie adjustments without checking if the cut rate is risking lean mass loss. Losing faster than ~1% BW/week on a prolonged cut significantly increases muscle breakdown risk.
- **Fix:** In `adjust_calories()`, add a guardrail: if the actual rate of loss exceeds -1% BW/week for 2+ consecutive weeks, return a `lbm_risk: true` flag and cap the calorie adjustment to prevent further deficit increase. Surface a warning in the nutrition page.
- **Files:** `engines/engine3/kinetic.py`, `routers/checkin.py`

---

**C20 — Protein Synthesis Window Logging**
- **Problem:** The research on muscle protein synthesis (MPS) shows that distributing protein across 4–5 meals of ≥30–40g each maximizes MPS response across the day. The current meal logging can't assess whether the user's protein distribution is optimally spaced.
- **Fix:** In `GET /engine3/daily-totals/{date}`, add an `mps_assessment` field. Analyze logged meals: count how many had ≥30g protein (MPS threshold), calculate average hours between protein meals, return a simple "protein distribution score" and guidance ("You had 2 MPS-threshold meals. Aim for 4.").
- **Files:** `routers/engine3.py`

---

## Part 2 — UI / UX Improvements

### Tier 1 — High Impact for Daily Use

---

**U1 — In-Session Rest Timer with Vibration**
- **Problem:** After logging a set, athletes need to time their rest period. Currently there's nothing — they use a phone timer app, breaking the flow.
- **Fix:** After clicking "Log Session" for a set (or after each set if we move to set-by-set logging), show a countdown timer at the bottom of the screen. Compound movements: 3:00 default, isolation: 1:30. Uses `setTimeout` + `navigator.vibrate()` for haptic alert on mobile. Timer is dismissable.
- **Files:** `frontend/src/app/training/page.tsx`

---

**U2 — Set-by-Set Logging with Completion Checkboxes**
- **Problem:** Currently all sets for all exercises are shown simultaneously and saved in one bulk action. This is confusing mid-workout — athletes don't know what they've already logged vs. what's next.
- **Fix:** Add a "current set" concept. Highlight the active set in gold. After entering reps/weight/RPE and tapping "Done Set," mark it complete (green checkmark, grayed background) and advance to the next set. "Log Session" button only appears after all sets are marked complete. Triggers the rest timer.
- **Files:** `frontend/src/app/training/page.tsx`

---

**U3 — Previous Session Ghost Values**
- **Problem:** Athletes need to know what they did last week to guide today's training. Currently, the session only shows prescribed values (from baselines), not the actual values from the last time this session type was performed.
- **Fix:** In `GET /engine2/session/{date}`, query the most recent completed session of the same `session_type` and return its actual logged values as `previous_reps` and `previous_weight_kg` on each set. Display in the training UI as small ghost text: "Last: 100kg × 8" next to the input.
- **Files:** `routers/engine2.py`, `frontend/src/app/training/page.tsx`

---

**U4 — Plate Calculator**
- **Problem:** Prescribed weight is in kg but athletes need to know what plates to load on the bar. Mental math mid-workout is a known friction point.
- **Fix:** Tap any weight field in the session view to open a "Plate Calculator" modal. Input: target weight (pre-filled), bar weight (20kg default, configurable to 15kg women's bar). Output: plates per side in standard denominations (25, 20, 15, 10, 5, 2.5, 1.25kg). Pure frontend — no backend changes.
- **Files:** New `frontend/src/components/PlateCalculator.tsx`, `frontend/src/app/training/page.tsx`

---

**U5 — Macro Ring Chart in Nutrition Page**
- **Problem:** Nutrition data is shown as plain numbers (protein: 180g, carbs: 220g, fat: 65g). Athletes find visual ratio representations much more intuitive for understanding their macro balance at a glance.
- **Fix:** Add a donut/ring SVG chart (same approach as existing SpiderChart — pure SVG, no library) to the nutrition page showing the caloric contribution of each macro. Color: protein=blue, carbs=gold, fat=orange. Animate fill on load. Display actual vs. target as two concentric rings.
- **Files:** New `frontend/src/components/MacroRing.tsx`, `frontend/src/app/nutrition/page.tsx`

---

**U6 — Dashboard Weight Quick-Log**
- **Problem:** Logging body weight requires navigating to the full check-in flow (4 steps). Most mornings an athlete just wants to record their weight. The friction causes them to skip it, degrading the kinetic data.
- **Fix:** Add a small "Log Weight" card to the dashboard with a single number input + submit button. Calls `POST /checkin/biological` with only `body_weight_kg` filled (all other fields optional in the backend). Shows a 7-day sparkline of recent weights inline.
- **Files:** `frontend/src/app/dashboard/page.tsx`, `routers/checkin.py` (make fields optional)

---

**U7 — Session History Browser**
- **Problem:** There's no way to look back at past training sessions to compare progress, identify trends, or review what was done in a previous mesocycle.
- **Fix:** New page `/training/history` listing all completed sessions grouped by week. Clicking a session shows its full set log with actual vs. prescribed comparison. Add "View History" link to the training page quick links section.
- **Files:** New `frontend/src/app/training/history/page.tsx`, new `GET /engine2/sessions/history?limit=N&offset=N` endpoint in `routers/engine2.py`

---

**U8 — RPE Live Color Feedback**
- **Problem:** RPE inputs accept any number but give no visual signal. An athlete entering RPE 9.5 (near-max effort) looks identical to RPE 6 (moderate). Coaches use RPE color-coding consistently.
- **Fix:** On every RPE `<input>`, attach an `onChange` handler that applies a background color: ≤6 green/safe, 7–8 gold/moderate, 9 orange/high, 9.5–10 red/max. Purely CSS — no backend changes.
- **Files:** `frontend/src/app/training/page.tsx`

---

**U9 — Muscles Trained Today Visual on Training Page**
- **Problem:** The training page shows a session type label ("Push Day") but athletes can't immediately see which specific muscles they're working without reading through all the exercises.
- **Fix:** Add a small `MuscleHeatmap` component (already built) at the top of the session card, highlighted for the muscles in today's session. When the session loads, derive active muscles from the sets and pass them to the heatmap as `highlight` prop. Instant at-a-glance visual.
- **Files:** `frontend/src/app/training/page.tsx`, `frontend/src/components/MuscleHeatmap.tsx` (add `highlight` prop)

---

**U10 — Progress Photo Upload in Check-In**
- **Problem:** Tracking visual physique changes is one of the most important tools in bodybuilding. Athletes take weekly progress photos but there's nowhere to store or view them in the app.
- **Fix:** Add an optional photo upload step to the check-in flow (step 4, before the review). Photos stored server-side (local filesystem for dev, S3 path for prod). New table `progress_photos(user_id, recorded_date, photo_url)`. New `/progress/photos` gallery view showing thumbnails in chronological order with side-by-side comparison mode.
- **Files:** New `models/diagnostic.py` table, `routers/checkin.py` file upload, new `frontend/src/app/progress/photos/page.tsx`

---

**U11 — Check-In Flow Shorter Path (Quick Check-In)**
- **Problem:** The full check-in (tape measurements + skinfolds + HRV + adherence) takes 15–20 minutes. Athletes won't do this weekly long-term. Only full measurements are useful — daily HRV is the high-frequency signal.
- **Fix:** Add a "Quick Check-In" mode to the check-in page: just weight + RMSSD + resting HR + sleep quality + soreness (5 fields). This is the daily check-in. The full measurement check-in becomes a weekly/bi-weekly event, clearly labeled "Full Check-In (takes ~15 min)". Separate the two flows at the check-in landing page.
- **Files:** `frontend/src/app/checkin/page.tsx`

---

**U12 — Onboarding Measurement Guide (With Photos/Diagrams)**
- **Problem:** The onboarding measurement step requires accurate tape measurements at 13 sites. Without guidance on *where exactly* to measure (mid-bicep peak vs. flexed? natural waist vs. narrowest?), data quality will be inconsistent between check-ins, corrupting the LCSA/HQI trends.
- **Fix:** Add a collapsible measurement guide below each input group in the onboarding measurement step and the check-in step. For now, text descriptions of measurement protocol for each site. Later: SVG diagrams. Prevents measurement variance from being mistaken for actual physique change.
- **Files:** `frontend/src/app/onboarding/page.tsx`, `frontend/src/app/checkin/page.tsx`

---

**U13 — Training Program Overview Page**
- **Problem:** After generating a program, athletes can only see today's session. There's no way to view the full mesocycle structure — all sessions, weekly volume, the deload week — to understand what they've committed to.
- **Fix:** New page `/training/program` showing a calendar-style view of all sessions in the current mesocycle. Each session is a card showing date, session type, and primary muscles. Deload weeks visually distinct. Volume progression chart (week-over-week sets per muscle). Link from the training page header.
- **Files:** New `frontend/src/app/training/program/page.tsx`, new `GET /engine2/program/schedule` endpoint

---

### Tier 2 — Quality-of-Life Improvements

---

**U14 — Workout Notes Field**
- **Problem:** Athletes often have contextual notes about a session ("slept poorly, moved well anyway," "knee bothered me on squats") that explain performance variation in the data but currently have nowhere to be recorded.
- **Fix:** Add a `notes` Text field to `TrainingSession`. Show a text area at the bottom of the session view labeled "Session Notes (optional)." Include in `POST /engine2/session/{id}/log`. Also add per-exercise notes accessible by tapping an exercise card.
- **Files:** `models/training.py`, `routers/engine2.py`, `frontend/src/app/training/page.tsx`

---

**U15 — Macro Nutrient Barcode / Food Search Enhancement**
- **Problem:** The current food search uses the seeded ingredient database (258 USDA foods). This is too limited — athletes eating varied diets won't find many branded foods or less common whole foods.
- **Fix:** Add a fallback to the Open Food Facts API (`https://world.openfoodfacts.org/cgi/search.pl`) when the local ingredient search returns no results. Pure frontend fetch to their public API — no backend changes needed. Show a "Source: Open Food Facts" label on matched items.
- **Files:** `frontend/src/app/nutrition/page.tsx`

---

**U16 — Notification / Reminder System**
- **Problem:** Athletes forget to check in, forget to log meals, and miss training days without reminders. The app goes unused between sessions, reducing data quality.
- **Fix:** Browser push notifications using the Web Notifications API + `ServiceWorker`. Configurable in Settings: "Check-in reminder" (Sunday AM), "Training day reminder" (day-of, 1h before typical session time), "Log meals reminder" (8 PM if no meals logged). All client-side — no backend infrastructure needed.
- **Files:** New `frontend/src/lib/notifications.ts`, `frontend/src/app/settings/page.tsx`

---

**U17 — Downloadable Progress Report (PDF)**
- **Problem:** Athletes share progress with coaches, sponsors, or just want a formatted record. The data is all there but locked in the app.
- **Fix:** New endpoint `GET /api/v1/export/report` generates a PDF using `reportlab` (already installable): current PDS score with tier, body measurements table vs. division ideal, 12-week weight chart (rendered as PNG), current training program overview, and macro prescription. Button in Settings page: "Download Progress Report."
- **Files:** New `routers/export.py`, `frontend/src/app/settings/page.tsx`

---

**U18 — Dark Mode Gym Mode (Extreme Contrast)**
- **Problem:** The jungle dark theme is good in normal light but hard to read in a gym with harsh overhead lighting or bright screens. Athletes need maximum contrast during a session.
- **Fix:** Add a "Gym Mode" toggle in the training page header. Switches to a high-contrast theme: pure black background, pure white text, large font size (+2 steps), extra-large input fields. State saved to `localStorage`. Auto-activates on the training page if preferred.
- **Files:** `frontend/src/app/training/page.tsx`, `frontend/src/app/globals.css`

---

**U19 — Coach Share Link (Read-Only Dashboard)**
- **Problem:** Athletes working with an online coach need to share their data. Currently there's no way to give a coach view-only access to your dashboard, check-in history, and training logs.
- **Fix:** `POST /auth/share-token` generates a signed, expiring (30-day) read-only JWT. Anyone with the link can view a `GET /dashboard/shared/{token}` page — a stripped-down version of the dashboard with no ability to log or change data. Revocable from Settings.
- **Files:** `routers/auth.py`, new `frontend/src/app/dashboard/shared/[token]/page.tsx`

---

**U20 — Onboarding Progress Persistence**
- **Problem:** If the user closes the browser mid-onboarding, all entered data is lost. The backend has the 5 separate onboarding endpoints but the frontend doesn't save progress between browser sessions.
- **Fix:** After each onboarding step submission, the backend already persists that step's data. On onboarding page load, query `GET /onboarding/profile` and pre-fill all fields that already exist. If measurements were already submitted, skip to the next incomplete step. Determines step from the profile's populated fields.
- **Files:** `frontend/src/app/onboarding/page.tsx`, `routers/onboarding.py`

---

## Part 3 — Infrastructure & Data

---

**I1 — Alembic Migration Setup**
- Replace the current `create_all` + runtime `ALTER TABLE` pattern with proper versioned Alembic migrations.
- Safer for production schema changes — each change is tracked, reversible, and auditable.
- Command: `alembic revision --autogenerate -m "initial_schema"`
- **Files:** `alembic/versions/`

---

**I2 — Integration Test Suite**
- End-to-end pytest tests covering: register → onboarding → check-in → program generation → session logging → dashboard data.
- Uses `httpx.AsyncClient` with a real PostgreSQL test container (via Docker).
- Infrastructure is already wired in `pyproject.toml` (`pytest-asyncio`, `httpx`).
- **Files:** `backend/tests/`

---

**I3 — Redis-Backed Rate Limiting**
- The current in-memory rate limiter resets on restart and doesn't scale across multiple gunicorn workers.
- Replace with Redis using `redis-py` before any horizontal scaling.
- Drop-in replacement for the current `_login_attempts` dict in `routers/auth.py`.
- **Files:** `routers/auth.py`, `docker-compose.yml`

---

*Mark items as approved and they'll be implemented in priority order.*
