# Viltrum — API Reference

Every HTTP endpoint, grouped by router. All routes are mounted under
`/api/v1`. See `backend/app/main.py` for the router registration
(`include_router(..., prefix="/api/v1")`).

Unless marked **public**, endpoints require `Authorization: Bearer <JWT>`.
See [`DEPLOYMENT.md § 5`](./DEPLOYMENT.md) for how to mint a token.

> This is a router/endpoint index, not a full parameter reference. For
> request/response schemas, open the FastAPI interactive docs at
> `/api/v1/docs` against a running backend.

---

## `auth` — `backend/app/routers/auth.py`

Registration, login, JWT refresh, API-key management.

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/auth/register` | public | Create user + return token pair |
| POST | `/auth/login` | public | Username + password → tokens |
| POST | `/auth/refresh` | public | Refresh token → new access token |
| GET | `/auth/me` | ✓ | Current user + onboarding state |
| POST | `/auth/api-keys` | ✓ | Mint a long-lived HealthKit API key (plaintext returned once) |
| GET | `/auth/api-keys` | ✓ | List this user's API keys (prefixes only) |
| DELETE | `/auth/api-keys/{key_id}` | ✓ | Revoke a key |
| POST | `/auth/share-token` | ✓ | Generate a signed share-link token |
| GET | `/auth/shared/{token}` | public | Read-only snapshot via share token |

Key symbol: `create_access_token(user_id)` (line 52).

---

## `onboarding` — `backend/app/routers/onboarding.py`

Multi-step onboarding + profile settings.

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/onboarding/profile` | ✓ | Create profile (sex, height, division, …) |
| POST | `/onboarding/measurements` | ✓ | First tape + skinfold + body-weight entry |
| POST | `/onboarding/strength-baselines` | ✓ | Starting 1RMs for key lifts |
| POST | `/onboarding/preferences` | ✓ | Equipment, disliked exercises, injuries, diet prefs |
| GET | `/onboarding/profile` | ✓ | Current profile (used by Settings) |
| PATCH | `/onboarding/profile` | ✓ | Partial profile update — **includes** `nutrition_mode_override`, `structural_priority_muscles`, training factors, PPM fields |
| POST | `/onboarding/complete` | ✓ | Mark user `onboarding_complete=True` + bootstrap first program |

---

## `checkin` — `backend/app/routers/checkin.py`

Daily and weekly check-ins, sleep/HRV/weight ingest, coaching feedback.

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/checkin/daily` | ✓ | HRV + sleep + soreness + resting HR + wellness |
| POST | `/checkin/daily/healthkit` | API key | iPhone Shortcut ingest (no JWT) |
| POST | `/checkin/weekly` | ✓ | Tape + skinfold + body-weight + adherence snapshot |
| POST | `/checkin/daily/backfill` | ✓ | Bulk backfill of historical HRV/sleep |
| GET | `/checkin/posing-recommendation` | ✓ | Next pose drill to practice |
| GET | `/checkin/timeline` | ✓ | Combined event feed |
| GET | `/checkin/weight-history` | ✓ | Body-weight log |
| GET | `/checkin/weekly/previous` | ✓ | Last weekly check-in |
| GET | `/checkin/weekly/review` | ✓ | Weekly coaching review payload |
| GET | `/checkin/gaps` | ✓ | Missing-data gap report |
| GET | `/checkin/recovery/trend` | ✓ | HRV + sleep rolling averages |
| POST | `/checkin/adherence/dedupe` | ✓ | Manual adherence cleanup |
| GET | `/checkin/coaching-feedback` | ✓ | Open feedback items |
| PATCH | `/checkin/coaching-feedback/{id}/dismiss` | ✓ | Dismiss item |
| GET | `/checkin/sleep-week` | ✓ | Last 7 days of sleep |

---

## `engine1` — `backend/app/routers/engine1.py`

Diagnostic pipeline (E1).

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/engine1/run` | ✓ | Run full diagnostic → PDS + HQI + gaps + trajectory |
| GET | `/engine1/pds` | ✓ | Latest PDS + history |
| GET | `/engine1/pds/trajectory` | ✓ | 52-week asymptotic projection |
| GET | `/engine1/lcsa` | ✓ | Lean cross-sectional area |
| GET | `/engine1/muscle-gaps` | ✓ | Per-site raw-cm gaps (tier-aware since V3) |
| GET | `/engine1/hqi` | ✓ | HQI history |
| GET | `/engine1/weight-cap` | ✓ | Casey-Butt natural max + IFBB cap |
| GET | `/engine1/class-estimate` | ✓ | Projected competition class |
| POST | `/engine1/feasibility` | ✓ | Can this PDS be reached in time? |
| GET | `/engine1/diagnostic` | ✓ | Full diagnostic payload (composite of all above) |
| GET | `/engine1/aesthetic-vector` | ✓ | S:W, V-taper, proportion deltas |
| GET | `/engine1/annual-calendar` | ✓ | 52-week phase calendar |
| GET | `/engine1/symmetry` | ✓ | Bilateral symmetry breakdown |
| GET | `/engine1/phase-recommendation` | ✓ | Cross-engine phase nudge (E1 → E3) |

---

## `engine2` — `backend/app/routers/engine2.py`

Training programming, sessions, strength logging.

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/engine2/ari` | ✓ | Today's ARI score + zone |
| GET | `/engine2/volume-allocation` | ✓ | Weekly set budget per muscle |
| GET | `/engine2/exercises` | ✓ | Exercise catalog (filtered by profile) |
| GET | `/engine2/exercises/search` | ✓ | Fuzzy search |
| GET | `/engine2/optimal-split` | ✓ | Recommended split from current gaps |
| GET | `/engine2/program/current` | ✓ | Active training program |
| POST | `/engine2/program/generate` | ✓ | Create new program from diagnostic |
| GET | `/engine2/session/{date}` | ✓ | Session for given ISO date |
| POST | `/engine2/session/{id}/log` | ✓ | Log completed session |
| POST | `/engine2/session/{id}/start` | ✓ | Mark session in-progress |
| PATCH | `/engine2/session/{id}/set/{set_id}` | ✓ | Update one set (weight/reps/RPE) |
| POST | `/engine2/session/{id}/finish` | ✓ | Close session; triggers adjustments |
| POST | `/engine2/program/apply-deload` | ✓ | Force deload next week |
| POST | `/engine2/session/{id}/swap-exercise` | ✓ | Swap exercise mid-session |
| PATCH | `/engine2/session/{id}/feedback` | ✓ | Post-session feedback (too hard/easy) |
| POST | `/engine2/strength-log` | ✓ | Manual strength log entry |
| GET | `/engine2/strength-log` | ✓ | Strength history |
| POST | `/engine2/program/autoregulate-today` | ✓ | Re-run volume autoreg for today |
| GET | `/engine2/progression-status` | ✓ | Per-lift progression status |
| GET | `/engine2/sessions/history` | ✓ | Paginated session history |
| GET | `/engine2/program/schedule` | ✓ | Weekly schedule |
| POST | `/engine2/exercises` | ✓ | Register custom exercise |
| GET | `/engine2/volume-history` | ✓ | Historical volume per muscle |
| GET | `/engine2/strength-history` | ✓ | Full strength history |
| GET | `/engine2/strength/progression` | ✓ | e1RM progression per lift |
| GET | `/engine2/volume/weekly` | ✓ | Weekly volume chart data |
| GET | `/engine2/volume-landmarks` | ✓ | MEV/MAV/MRV for this athlete |

---

## `engine3` — `backend/app/routers/engine3.py`

Nutrition: macros, meal planning, peak week, carb cycle, mini-cut.

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/engine3/prescription/current` | ✓ | Current macro prescription |
| GET | `/engine3/peak-week` | ✓ | 7-day peak-week protocol |
| GET | `/engine3/adherence` | ✓ | Rolling adherence % |
| POST | `/engine3/autoregulation` | ✓ | Trigger macro-adjustment logic |
| GET | `/engine3/prescription/restoration` | ✓ | Post-show restoration ramp |
| POST | `/engine3/peak-week/adjust` | ✓ | Reactive peak-week tweaks |
| POST | `/engine3/preworkout/log` | ✓ | Log pre-workout carbs |
| GET | `/engine3/preworkout/today` | ✓ | Today's pre-workout window |
| POST | `/engine3/gi-distress` | ✓ | Log distress → routes macros |
| GET | `/engine3/cardio/prescription` | ✓ | Engine-4 cardio prescription (exposed via engine3 router) |
| POST | `/engine3/cardio/log` | ✓ | Log cardio session |
| GET | `/engine3/meal-plan/current` | ✓ | Active meal plan |
| POST | `/engine3/meal-plan/generate` | ✓ | Re-generate from preferences |
| POST | `/engine3/meal-plan/invalidate` | ✓ | Force regeneration |
| GET | `/engine3/ingredients/search` | ✓ | Ingredient search |
| POST | `/engine3/meals` | ✓ | Log meal |
| GET | `/engine3/meals/{date}` | ✓ | Day's logged meals |
| GET | `/engine3/daily-totals/{date}` | ✓ | Per-day macro totals |
| GET | `/engine3/shopping-list/weekly` | ✓ | Aisle-grouped list |
| GET | `/engine3/supplements/current` | ✓ | Evidence-tier supplements |
| GET | `/engine3/mini-cut/evaluate` | ✓ | Mini-cut eligibility |
| POST | `/engine3/phase/transition` | ✓ | Manual phase change |
| GET | `/engine3/cheat-meal/stats` | ✓ | Cheat-meal adherence |
| POST | `/engine3/cheat-meal` | ✓ | Log cheat meal |
| GET | `/engine3/carb-cycle` | ✓ | Today's training vs rest day macros |

---

## `ppm` — `backend/app/routers/ppm.py`

Perpetual Progression Mode — tier readiness, improvement cycles, checkpoints.

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/ppm/status` | ✓ | PPM on/off, current cycle + week, target tier |
| POST | `/ppm/evaluate` | ✓ | Run readiness eval against target tier |
| POST | `/ppm/attainability` | ✓ | Casey-Butt + Kouri natural-ceiling check |
| POST | `/ppm/start-cycle` | ✓ | Begin 14/16-week improvement cycle |
| GET | `/ppm/plan/{week}` | ✓ | Plan for a specific cycle week |
| POST | `/ppm/checkpoint` | ✓ | End-of-cycle snapshot → `PPMCheckpoint` |
| GET | `/ppm/history` | ✓ | Previous cycle checkpoints |
| POST | `/ppm/transition-to-comp` | ✓ | Disable PPM + set competition date |
| POST | `/ppm/disable` | ✓ | Turn PPM off |

See [`PPM.md`](./PPM.md) for full flow.

---

## `insights` — `backend/app/routers/insights.py`

V3 analytical overlays on historical data. Consumed by dashboard V3 cards
(`TierTimingCard`, `LeverSensitivityCard`, `WeightTrendCard`) and the
growth / archive pages.

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/insights/tier-projection` | ✓ | Cycles-to-tier projection across adherence profiles |
| GET | `/insights/sensitivity` | ✓ | "What moves the needle" — which input drives the biggest gate delta |
| GET | `/insights/weight-trend?days=90` | ✓ | BW + 7d rolling + kg/week rate |
| GET | `/insights/muscle-timeline/{site}` | ✓ | Per-site historical circumference + trend |
| GET | `/insights/archive/cycles` | ✓ | List of past PPM cycles (Archive page) |
| GET | `/insights/archive/cycle/{cycle_number}` | ✓ | Full reconstruction of one cycle (macros + training + volume snapshots) |

---

## `progress_photos` — `backend/app/routers/progress_photos.py`

Mounted under `/progress`. Pose-tagged photo stack.

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/progress/photos` | ✓ | Upload photo (multipart) with `photo_date` + `pose_type` |
| GET | `/progress/photos` | ✓ | List photos (optionally filtered by pose) |
| GET | `/progress/photos/{id}/file` | ✓ | Stream binary file |
| DELETE | `/progress/photos/{id}` | ✓ | Delete photo + file |
| GET | `/progress/poses` | ✓ | Static list of valid pose types (see `POSE_TYPES`) |

---

## `viz` — `backend/app/routers/viz.py`

Server-rendered Plotly payloads. Used by the admin panel and legacy
charts; the modern dashboard renders charts client-side.

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/viz/spider-plot` | ✓ | Radar chart Plotly JSON |
| GET | `/viz/pds-glide-path` | ✓ | PDS trajectory Plotly JSON |
| GET | `/viz/autonomic-gauge` | ✓ | ARI gauge Plotly JSON |
| GET | `/viz/adherence-grid` | ✓ | Heatmap Plotly JSON |
| GET | `/viz/hypertrophy-heatmap` | ✓ | Body-map Plotly JSON |

---

## `export` — `backend/app/routers/export.py`

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/export/report` | ✓ | PDF-style report of current state |

---

## `upload` — `backend/app/routers/upload.py`

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/upload` | ✓ | Generic multipart upload (goal photos, etc.) |

---

## `admin` — `backend/app/routers/admin.py`

Admin-only (checked via `dependencies.require_admin`).

| Method | Path | Description |
|---|---|---|
| GET | `/admin/health` | Scan for orphaned sessions, stale programs, duplicate programs, missing prescriptions |
| POST | `/admin/fix/orphaned-sessions` | Repair orphans |
| POST | `/admin/fix/stale-programs` | Retire stale programs |
| POST | `/admin/fix/duplicate-programs` | Deduplicate |
| POST | `/admin/fix/missing-nutrition` | Generate missing prescriptions |
| POST | `/admin/fix/all` | Run all fixes in order |
| GET | `/admin/cron/logs` | In-memory cron buffer |
| POST | `/admin/cron/run` | Trigger cron pass immediately |
| GET | `/admin/users` | List all users with counts |
| GET | `/admin/users/{user_id}/detail` | Full drill-down |

---

## `telegram` — `backend/app/routers/telegram.py`

Telegram bot integration (per-user bot token).

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/telegram/link/token` | ✓ | Register personal bot token |
| POST | `/telegram/link/generate` | ✓ | Generate linking deep-link |
| POST | `/telegram/unlink` | ✓ | Disconnect bot |
| GET | `/telegram/status` | ✓ | Link status |
| PATCH | `/telegram/notifications` | ✓ | Toggle which notifications fire |
| POST | `/telegram/webhook` | **bot signature** | Incoming Telegram update |

---

*Last indexed against backend revision `e6c31a5`, 2026-04-23.*
