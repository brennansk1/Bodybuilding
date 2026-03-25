# Coronado v4.0 — Remaining Development Plan

> **Status:** Core architecture complete. Engines implemented as pure functions. Frontend scaffold and auth flow working. Major gaps are in data seeding, pipeline integration, and session generation.

---

## Phase 1: Critical Blockers (App Non-Functional Without These)

### 1.1 Seed Exercises into Database on Startup
- **Problem:** `SEED_EXERCISES` in `app/constants/exercises.py` (57 exercises) is never inserted into the `exercises` table
- **Impact:** Onboarding strength baselines fail (queries empty table), training program generation has no exercises to select from
- **Fix:** Add seed function in `app/main.py` lifespan that inserts exercises if table is empty
- **Files:** `app/main.py`, `app/constants/exercises.py`

### 1.2 Auto-Run Engine 1 Diagnostics on Onboarding Complete
- **Problem:** `onboarding/complete` endpoint sets `onboarding_complete=True` but never calls `run_full_diagnostic()`
- **Impact:** Dashboard shows empty charts / 404s after first login
- **Fix:** Call `run_full_diagnostic()` inside `complete_onboarding()`, return computed PDS/tier
- **Files:** `app/routers/onboarding.py`

### 1.3 Generate Training Sessions & Sets in Program Generation
- **Problem:** `/engine2/program/generate` creates a `TrainingProgram` header but no `TrainingSession` or `TrainingSet` records
- **Impact:** Training page shows "No session scheduled for today"
- **Fix:** After creating program, call periodization engine to generate mesocycle structure, then create session/set records with exercises selected by biomechanical scoring
- **Files:** `app/routers/engine2.py`, new `app/services/training.py`
- **Engine modules to wire up:** `periodization.py`, `biomechanical.py`, `overflow.py`

### 1.4 Store User Preferences
- **Problem:** `onboarding/preferences` endpoint returns success but discards all data
- **Impact:** Training days/week, preferred split, meal count never saved
- **Fix:** Add `preferences` JSONB column to `UserProfile` or create `UserPreferences` model; persist data in the endpoint
- **Files:** `app/models/profile.py`, `app/routers/onboarding.py`, `app/schemas/onboarding.py`

### 1.5 Seed Ingredient Master
- **Problem:** `ingredient_master` table is empty; `/engine3/ingredients/search` always returns nothing
- **Impact:** Nutrition ingredient search non-functional
- **Fix:** Create `app/constants/ingredients.py` with ~100-200 common foods (name, calories, protein, carbs, fat per 100g), seed on startup
- **Files:** New `app/constants/ingredients.py`, `app/main.py`

---

## Phase 2: Engine Pipeline Integration (Engines Work but Aren't Connected)

### 2.1 Full Check-in Engine Pipeline
- **Problem:** `checkin/process` only runs Engine 1. Engine 2 (ARI, volume reallocation) and Engine 3 (kinetic adjustment) are never triggered
- **Fix:** After Engine 1, also:
  - Compute ARI from latest HRV data and persist to `ari_log`
  - Compute volume modifier from ARI and update current program's volume allocation
  - Run kinetic rate-of-change from weight history
  - Adjust calorie prescription if rate deviates from target
  - Check adherence lock
- **Files:** `app/routers/checkin.py`, new `app/services/training.py`, new `app/services/nutrition.py`
- **Engine modules to wire up:** `ari.py`, `overflow.py`, `recovery.py`, `kinetic.py`, `thermodynamic.py`, `autoregulation.py`

### 2.2 ARI → Volume Modifier Pipeline
- **Problem:** ARI is computed but never applied to modify training volume
- **Fix:** After computing ARI, use `get_volume_modifier()` to scale session volume. Store ARI in `ari_log`. Update `TrainingProgram.volume_allocation` with modified values
- **Files:** `app/services/training.py`, `app/routers/engine2.py`

### 2.3 Resistance Progression (Double Progression)
- **Problem:** `/engine2/session/{id}/log` records sets but never triggers progression logic
- **Fix:** After logging all sets in a session, run `compute_progression()` on each exercise. If criteria met (hit rep ceiling at manageable RPE), increase prescribed weight for next session
- **Files:** `app/routers/engine2.py`, `app/engines/engine2/resistance.py`

### 2.4 Recovery Gating
- **Problem:** `recovery.py` has `estimate_recovery_time()` and `can_train_muscle()` but they're never called
- **Fix:** Before generating a session's exercises, check `can_train_muscle()` for each target muscle group. Skip muscles that haven't recovered
- **Files:** `app/services/training.py`

### 2.5 Engine 3 Autoregulation with Real Data
- **Problem:** `autoregulation` endpoint uses hardcoded `soreness_1_10=5.0` and `baseline_rmssd=65.0`
- **Fix:** Compute rolling 7-day average RMSSD as baseline. Pull latest soreness from HRV/checkin data
- **Files:** `app/routers/engine3.py`

### 2.6 Nutrition Prescription Uses Profile Age
- **Problem:** `/engine3/prescription/current` computes TDEE with hardcoded `age=25`
- **Fix:** Read `profile.age` from database
- **Files:** `app/routers/engine3.py`

---

## Phase 3: Missing Endpoints & Features

### 3.1 Exercise Library Endpoint
- **Endpoint:** `GET /api/v1/engine2/exercises` — list all exercises, filterable by muscle group
- **Endpoint:** `GET /api/v1/engine2/exercises/search?q=bench` — search exercises
- **Files:** `app/routers/engine2.py`

### 3.2 Feasibility Endpoint
- **Endpoint:** `POST /api/v1/engine1/feasibility` — assess goal feasibility
- **Engine exists:** `app/engines/engine1/feasibility.py` (fully implemented, untested end-to-end)
- **Files:** `app/routers/engine1.py`

### 3.3 Meal Logging Endpoints
- **Models exist:** `UserMeal`, `MealItem` in `app/models/nutrition.py`
- **Missing endpoints:**
  - `POST /api/v1/nutrition/meals` — log a meal with items
  - `GET /api/v1/nutrition/meals/{date}` — get meals for a date
  - `GET /api/v1/nutrition/daily-totals/{date}` — computed macro totals
- **Files:** `app/routers/engine3.py` or new `app/routers/meals.py`

### 3.4 Strength Logging Endpoint
- **Model exists:** `StrengthLog` in `app/models/training.py`
- **Missing:** Dedicated endpoint to log strength tests outside of training sessions
- **Files:** `app/routers/engine2.py`

---

## Phase 4: Dashboard Visualizations (Charts Render but Need Live Data)

### 4.1 Wire Up Spider Plot (HQI)
- **Status:** Backend endpoint exists, returns Plotly JSON from DB data
- **Fix:** Frontend dashboard currently catches errors silently. Show meaningful empty state when no HQI data exists. Add "Run Diagnostics" button that calls `/engine1/run`
- **Files:** `frontend/src/app/dashboard/page.tsx`

### 4.2 Wire Up PDS Glide Path
- **Status:** Backend endpoint exists
- **Fix:** Same as 4.1 — needs data to exist first (solved by 1.2)

### 4.3 Implement Autonomic Fuel Gauge
- **Status:** Backend endpoint exists. Frontend shows "ARI fuel gauge — Phase 5" placeholder
- **Fix:** Replace placeholder with actual Plotly chart component. Fetch from `/viz/autonomic-gauge`
- **Files:** `frontend/src/app/dashboard/page.tsx`

### 4.4 Implement Adherence Grid
- **Status:** Backend endpoint exists. Frontend shows "Adherence grid — Phase 6" placeholder
- **Fix:** Replace placeholder with Plotly heatmap component. Fetch from `/viz/adherence-grid`
- **Files:** `frontend/src/app/dashboard/page.tsx`

### 4.5 Implement Hypertrophy Heatmap
- **Status:** Backend endpoint exists (returns colored body site data). Frontend shows "SVG body map — Phase 7" placeholder
- **Fix:** Create SVG body silhouette component with color-coded muscle sites based on HQI scores
- **Files:** `frontend/src/app/dashboard/page.tsx`, new `frontend/src/components/BodyHeatmap.tsx`

---

## Phase 5: Frontend Enhancements

### 5.1 Meal Logging Page
- **Missing:** No page for logging individual meals/foods
- **Needs:** Food search (from ingredient_master), portion entry, daily meal list with running totals
- **Files:** New `frontend/src/app/nutrition/meals/page.tsx`

### 5.2 Exercise Library Browser
- **Missing:** No page to browse/search the exercise database
- **Files:** New `frontend/src/app/training/exercises/page.tsx`

### 5.3 Progress History Page
- **Missing:** No dedicated page showing PDS, weight, and measurement trends over time
- **Needs:** Line charts of PDS history, weight history, LCSA by site over time
- **Files:** New `frontend/src/app/progress/page.tsx`

### 5.4 Settings / Profile Edit Page
- **Missing:** No way to update profile (division change, competition date, structural anchors)
- **Files:** New `frontend/src/app/settings/page.tsx`

### 5.5 Dashboard Empty States
- **Problem:** Dashboard fetches data and silently catches errors; user sees blank cards
- **Fix:** Show meaningful empty states with calls-to-action ("Complete your first check-in to see your PDS score")

---

## Phase 6: Data Integrity & Error Handling

### 6.1 Input Validation
- Add server-side validation for all measurement ranges (e.g., bicep 20-60cm, weight 30-250kg)
- Validate skinfold values (1-80mm range)
- Validate that tape measurements are internally consistent (shoulder > waist > neck for males)

### 6.2 Partial Measurement Handling
- Diagnostic service assumes all tape sites are present; handle partial data gracefully
- Compute HQI/LCSA only for available sites
- Skip symmetry score if no bilateral data

### 6.3 Duplicate Check-in Prevention
- Prevent multiple check-ins on the same day (or allow updates instead of inserts)
- Add unique constraint on `(user_id, recorded_date)` for measurement tables

### 6.4 Token Refresh Flow
- Frontend stores refresh token but never uses it to auto-refresh expired access tokens
- Add interceptor in `api.ts` that catches 401, refreshes token, and retries

---

## Phase 7: Production Readiness

### 7.1 Alembic Migrations
- Generate proper Alembic migration from current models (replace `create_all` + manual `ALTER TABLE`)
- Command: `alembic revision --autogenerate -m "initial_schema"`
- **Files:** `alembic/versions/`

### 7.2 Database Indexes
- Add composite indexes for frequent queries: `(user_id, recorded_date)` on all log tables
- Add index on `exercises.primary_muscle` for muscle-group filtering

### 7.3 Production Dockerfiles
- Multi-stage builds to reduce image size
- Non-root user
- Health check endpoints
- `gunicorn` with `uvicorn` workers instead of `--reload`

### 7.4 Environment Configuration
- Validate all required env vars on startup
- Separate dev/staging/prod configs
- Secure `SECRET_KEY` generation

### 7.5 Rate Limiting & Security
- Add rate limiting to auth endpoints (prevent brute force)
- Add CSRF protection
- Password complexity requirements
- Account lockout after failed attempts

### 7.6 API Documentation
- Review auto-generated OpenAPI docs at `/docs`
- Add response models to all endpoints
- Add example values to schemas

### 7.7 Testing
- Integration tests hitting real database (Docker test container)
- Frontend component tests
- End-to-end tests (onboarding → check-in → dashboard data)

---

## Completion Checklist — Suggested Improvements

All items from `suggested_improvements.md` implemented in this session:

| ID | Item | Status |
|----|------|--------|
| C1 | Body fat from skinfolds (J-P 7-site) | ✅ Done — wired into diagnostic.py |
| C2 | Peri-workout carb timing split | ✅ Done — macros.py + engine3 router |
| C3 | Training day vs rest day macros | ✅ Done — prescription endpoint |
| C4 | ARI early deload detection | ✅ Done — checkin process endpoint |
| C5 | Compound-specific progression increments | ✅ Done — resistance.py + session log |
| C6 | Volume landmarks (MEV/MAV/MRV) | ✅ Done — periodization.py |
| C7 | Phase auto-detection from weight trend | ✅ Done — checkin process |
| C8 | Stale baseline warning (90 days) | ✅ Done — training service + session API |
| C9 | Exercise rotation between mesocycles | ✅ Done — training service |
| C10 | Bro split support | ✅ Done — periodization.py |
| C11 | Competition prep timeline engine | ✅ Done — prep_timeline.py |
| C12 | Peak week protocol | ✅ Done — peak_week.py + engine3 router |
| C13 | Warm-up set prescription | ✅ Done — training service (is_warmup flag) |
| C14 | Resting HR in ARI (15% weight) | ✅ Done — ari.py rebalanced weights |
| C16 | Custom exercise creation | ✅ Done — POST /engine2/exercises |
| C17 | Symmetry-driven unilateral preference | ✅ Done — training service |
| **AUTO-SPLIT** | Gap-driven split selection | ✅ Done — auto_select_split() in periodization.py |
| U1 | Rest timer | ✅ Done — training page |
| U2 | Set-by-set checkboxes | ✅ Done — training page |
| U3 | Previous session ghost values | ✅ Done — session API + training page |
| U4 | Plate calculator | ✅ Done — training page modal |
| U5 | Macro ring chart | ✅ Done — nutrition page |
| U6 | Dashboard weight quick-log | ✅ Done — dashboard |
| U7 | Session history browser | ✅ Done — /training/history |
| U8 | RPE live color feedback | ✅ Done — training page |
| U9 | Muscles trained today heatmap | ✅ Done — training page |
| U13 | Training program overview | ✅ Done — /training/program |
| U14 | Session notes field | ✅ Done — training page + API |
| U16 | Push notification toggles | ✅ Done — settings page |
| U17 | PDF export | ✅ Done — /export/report |
| U19 | Coach share link | ✅ Done — /auth/share-token |
| U20 | Onboarding quick-mode persistence | ✅ Done — /checkin/quick |
| I3 | Production Dockerfiles | ✅ Done — Dockerfile.prod (both) |
| 7.5 | Rate limiting | ✅ Done — auth router |

---

## Original Completion Checklist

| # | Item | Priority | Status |
|---|------|----------|--------|
| 1.1 | Seed exercises | CRITICAL | ✅ Done — 348 exercises (MegaGym) |
| 1.2 | Auto-run diagnostics on onboarding | CRITICAL | ✅ Done |
| 1.3 | Generate training sessions/sets | CRITICAL | ✅ Done — services/training.py |
| 1.4 | Store user preferences | CRITICAL | ✅ Done — JSONB preferences |
| 1.5 | Seed ingredients | CRITICAL | ✅ Done — 258 USDA foods |
| 2.1 | Full check-in pipeline (E1+E2+E3) | HIGH | ✅ Done |
| 2.2 | ARI → volume modifier | HIGH | ✅ Done — ARILog persisted |
| 2.3 | Resistance progression | HIGH | ✅ Done — double progression on log |
| 2.4 | Recovery gating | HIGH | ✅ Done — wired into generate_program_sessions() |
| 2.5 | Autoregulation with real data | HIGH | ✅ Done — soreness_score in HRVLog |
| 2.6 | TDEE uses profile age | HIGH | ✅ Done |
| 3.1 | Exercise library endpoint | MEDIUM | ✅ Done — GET /exercises + /search |
| 3.2 | Feasibility endpoint | MEDIUM | ✅ Done — POST /engine1/feasibility + UI in /progress |
| 3.3 | Meal logging endpoints | MEDIUM | ✅ Done — POST/GET /meals, /daily-totals |
| 3.4 | Strength logging endpoint | MEDIUM | ✅ Done — POST/GET /engine2/strength-log + UI in /training |
| 4.1-4.5 | Dashboard chart wiring | MEDIUM | ✅ Done — SpiderChart (SVG), MiniLineChart (SVG), MuscleHeatmap (SVG) |
| 5.1 | Meal logging page | MEDIUM | ✅ Done — nutrition/page.tsx with food search |
| 5.2 | Exercise library browser | MEDIUM | ✅ Done — /training/exercises with search + muscle filter |
| 5.3 | Progress history page | MEDIUM | ✅ Done — /progress with weight/PDS/LCSA tabs |
| 5.4 | Settings / profile edit | MEDIUM | ✅ Done — /settings with profile/training/account tabs |
| 5.5 | Dashboard empty states | MEDIUM | ✅ Done |
| 6.1 | Input validation | LOW | ✅ Done — tape/skinfold ranges + consistency check |
| 6.2 | Partial measurement handling | LOW | ✅ Done — diagnostic service already handles missing sites |
| 6.3 | Duplicate check-in prevention | LOW | ✅ Done — upsert (delete+insert) on biological/HRV |
| 6.4 | Token refresh flow | LOW | ✅ Done — api.ts auto-refresh interceptor |
| 7.1 | Alembic migrations | LOW | ✅ Done — autogenerate delta migration, stamped head (7850f1556da9) |
| 7.2 | DB indexes | LOW | ✅ Done — training_sessions, training_sets, exercises.primary_muscle |
| 7.3 | Production Dockerfiles | LOW | ✅ Done — Dockerfile.prod (multi-stage, non-root, health check, gunicorn) |
| 7.4 | Env config validation | LOW | ✅ Done — config.py warns/raises for default SECRET_KEY |
| 7.5 | Rate limiting | LOW | ✅ Done — in-memory sliding window (10 req/15 min) on login + register |
| 7.6 | API docs | LOW | Auto-generated at /docs |
| 7.7 | Testing | LOW | ✅ Done — 152 unit tests across all 3 engines, constants, exercise priorities cascade |

---

## Phase 8 — Sequential Exercise Overflow Matrix + Division-Specific Priorities

### 8.1 Division Exercise Priority Cascade  ✅ Done
- **New file:** `backend/app/constants/exercise_priorities.py`
- Per-division ordered exercise lists for every muscle group (6 divisions × 13 muscles)
- Each slot has a `max_sets` cap — cascade fills top priority up to cap, then overflows to next
- Gap adjustment: `gap_adjusted_cap()` boosts top-slot cap by ×1.5 for HQI<40, ×1.25 for HQI<65
- Rationale encodes judging priorities per division:
  - mens_open: flat bench → barbell row → back squat anchors; all muscles equal
  - mens_physique: incline-first chest; lat pulldown before rows; side delt before press; no heavy squats
  - classic_physique: Open-style compound anchors + more isolation variety
  - womens_bikini: hip thrust → glute bridge → cable pull-through; no heavy pressing
  - womens_figure: back + glutes co-dominant; moderate pressing
  - womens_physique: full development; dumbbell/cable preference for roundness

### 8.2 Cascade Algorithm in `_allocate_sets`  ✅ Done
- Rewrote function in `backend/app/services/training.py`
- Keyword matching: each priority slot matched against exercise name (substring, case-insensitive)
- Fills exercises in order until `remaining_sets == 0`
- Fallback SFR-sort handles exercises not in priority list
- `generate_program_sessions()` now loads `user_division` from profile, builds `_MUSCLE_HQI_MAP`,
  and passes both to `_allocate_sets()` for every muscle group in every session

### 8.3 Division Nutrition Priorities  ✅ Done
- `compute_division_nutrition_priorities(division, phase)` added to `backend/app/engines/engine3/macros.py`
- Returns: protein_per_kg override, carb_cycling_factor (±%), fat floor, meal frequency, MPS threshold, coaching notes
- Applied in `GET /engine3/prescription/current`: carb cycling factor is division-driven (e.g. bikini=±35%, physique=±30%, open=±25%)
- Response now includes `division_nutrition` block with coaching notes visible in the frontend
- Frontend `nutrition/page.tsx` displays Division Coaching Notes card with meal frequency, MPS threshold, and rationale bullets

### 8.4 `GET /engine1/diagnostic` endpoint  ✅ Done
- Added to `backend/app/routers/engine1.py`
- Returns cached BF% + prep timeline without re-running full Engine 1
- Used by `/progress` Condition tab for body fat category and prep phase display
