# Viltrum — Architecture Overview

The 30,000-ft view. Read this first, then drop into
[`ENGINES.md`](./ENGINES.md) for the algorithm layer,
[`DATABASE_SCHEMA.md`](./DATABASE_SCHEMA.md) for persistence, and
[`API_REFERENCE.md`](./API_REFERENCE.md) for the HTTP surface.

---

## 1. Stack

| Layer | Tech | Notes |
|---|---|---|
| Frontend | Next.js 14 (App Router), TypeScript, Tailwind | `@dnd-kit` for dashboard drag, `plotly.js` for charts, `tegaki` for display type |
| Backend | FastAPI, Pydantic v2, SQLAlchemy 2.0 (async), Alembic | Python ≥ 3.11 |
| Database | PostgreSQL 16 | Async driver: `asyncpg`. JSONB columns for snapshots + preferences. |
| Auth | JWT (HS256) via `python-jose`, bcrypt via `passlib` | Access 30 min, refresh 7 days, plus long-lived HealthKit API keys |
| Deploy | Docker Compose, 3 containers | See [`DEPLOYMENT.md`](./DEPLOYMENT.md) |
| Pipelines | Pure-Python engine modules, no DB/HTTP imports | Enables unit testing + backtesting |

---

## 2. Repo layout

```
Bodybuilding/
├── backend/
│   ├── app/
│   │   ├── engines/
│   │   │   ├── engine1/      ← diagnostic (PDS, HQI, muscle gaps, ghost, readiness)
│   │   │   ├── engine2/      ← training (split designer, periodization, ARI, resistance)
│   │   │   ├── engine3/      ← nutrition (macros, kinetic, autoregulation, peak week)
│   │   │   └── engine4/      ← cardio & NEAT
│   │   ├── constants/        ← shared truth (physio.py, competitive_tiers.py,
│   │   │                       divisions.py, weight_caps.py, volume_landmarks.py)
│   │   ├── models/           ← SQLAlchemy ORM (see DATABASE_SCHEMA.md)
│   │   ├── routers/          ← FastAPI handlers (see API_REFERENCE.md)
│   │   ├── schemas/          ← Pydantic request/response
│   │   ├── services/         ← orchestration (diagnostic.py, training.py)
│   │   └── main.py           ← FastAPI app factory + router registration
│   ├── alembic/              ← DB migrations
│   ├── tests/                ← pytest suite
│   └── scripts/              ← audit_tool.py, seeds, maintenance
├── frontend/
│   ├── src/
│   │   ├── app/              ← Next.js pages (see FRONTEND_ROUTES.md)
│   │   ├── components/       ← Reusable React (charts, PPMCards, TierBadge, …)
│   │   ├── hooks/            ← useAuth, useDashboardContext, …
│   │   └── lib/              ← API client (lib/api.ts), TS types
│   └── public/
├── docker/                   ← postgres init.sql
├── docker-compose.yml        ← prod
├── docker-compose.override.yml ← dev overrides (auto-loaded)
├── docs/                     ← you are here
└── scripts/                  ← repo-level ops scripts
```

---

## 3. The four engines

```
           tape + skinfolds + body weight + HRV + sleep + subjective wellness
                                │
                                ▼
                    ┌────────────────────────┐
                    │ Engine 1 — Diagnostic  │─── PDS, HQI, muscle gaps, readiness, trajectory
                    └──────────┬─────────────┘
                               │ (lagging muscles, gap profile, current phase)
                               ▼
                    ┌────────────────────────┐
                    │ Engine 2 — Training    │─── split + periodized sessions (DUP/Block)
                    └──────────┬─────────────┘
                               │ (training load, phase, body-weight trend)
                               ▼
                    ┌────────────────────────┐
                    │ Engine 3 — Nutrition   │─── macros, carb cycle, refeeds, peak week
                    └──────────┬─────────────┘
                               │ (kcal-floor risk, phase)
                               ▼
                    ┌────────────────────────┐
                    │ Engine 4 — Cardio/NEAT │─── cardio + step prescription
                    └────────────────────────┘
```

Flow is **one-way** (E1 → E2 → E3 → E4). Feedback is delivered by the
*next* diagnostic, not by downstream engines mutating upstream state. This
keeps each engine individually testable.

See [`ENGINES.md`](./ENGINES.md) for module-level detail.

### PPM orchestrator

PPM (Perpetual Progression Mode) spans E1 → E2 → E3 but is **not** an
engine — it's an orchestrator that lives in `backend/app/routers/ppm.py`
and answers: "given the athlete's current diagnostic + target tier, what
should the next 14-week improvement cycle look like?" See
[`PPM.md`](./PPM.md).

---

## 4. Request flow — `GET /api/v1/ppm/evaluate`

Representative path through the system:

```
browser  ──► Next.js server (:3001)  ──► FastAPI (:8000)
                                          │
                                          ├─► dependencies.get_current_user  (JWT decode)
                                          ├─► routers.ppm.evaluate
                                          │     ├─► _latest_measurements()          ← DB
                                          │     ├─► _compute_athlete_metrics()      ← E1 pure funcs
                                          │     │     (body_fat · readiness · aesthetic_vector · hqi)
                                          │     ├─► readiness.evaluate_readiness()  ← E1
                                          │     └─► returns {state, per_metric, mass_gaps}
                                          └─► JSON  ──► browser  ──► TierReadinessCard
```

All engine calls are **pure functions** (no DB, no HTTP). The router
composes them with persisted data.

---

## 5. Deployment topology

```
┌──────────────────────────────────────┐
│ Home server (<server-ip>)           │
│                                      │
│  docker compose:                     │
│    bodybuilding-postgres-1  :5432    │
│    bodybuilding-backend-1   :8000    │
│    bodybuilding-frontend-1  :3001    │
│                                      │
│  pg_data volume (persisted across    │
│  rebuilds — `docker compose down -v` │
│  is the only way to wipe it)         │
└──────────────────────────────────────┘
             ▲
             │
             │ LAN
             │
       ┌─────┴─────┐
       │ iPhone /  │  ← Next.js PWA at http://<server-ip>:3001
       │ Desktop   │
       └───────────┘
```

See [`DEPLOYMENT.md`](./DEPLOYMENT.md) for the pull/build/restart recipe
and JWT-minting workflow.

---

## 6. Cross-cutting constants

Shared truth — if a number appears in two files, one of them is a bug.

| File | Contents |
|---|---|
| `backend/app/constants/physio.py` | Stage BF, offseason ceilings, HQI freshness, site-lean coefficients, asymmetry threshold |
| `backend/app/constants/competitive_tiers.py` | T1–T5 tier thresholds (Classic table is canonical) |
| `backend/app/constants/weight_caps.py` | IFBB 2024 weight caps by height |
| `backend/app/constants/divisions.py` | `DIVISION_VECTORS`, `DIVISION_CEILING_FACTORS`, `K_SITE_FACTORS`, `GHOST_VECTORS`, visibility weights |
| `backend/app/constants/volume_landmarks.py` | MEV/MAV/MRV per muscle with experience scaling |

See [`CALCULATIONS.md`](./CALCULATIONS.md) for the full list + verification inputs.

---

## 7. Directory-level design rules

- **`engines/` never imports from `models/`, `routers/`, or `services/`.** Pure math.
- **`services/` is orchestration.** Pulls data from DB, calls engines, returns a payload.
- **`routers/` is the HTTP layer.** Handles auth, request/response shape, error mapping. May call services OR engines directly for simple reads.
- **`constants/` is read-only.** No engine mutates these.
- **`schemas/` is Pydantic-only.** No business logic.

Breaking these rules is a red flag in code review.

---

## 8. What's NOT here (yet)

- Real-time / websocket. All interactions are request-response.
- Multi-tenant or shared-user data. Every query filters by `user_id`.
- External object storage. Progress photos are currently served from an on-disk media dir inside the backend container (see `progress_photos.py::_save_file`).
- Observability/metrics stack. Health check is `GET /api/v1/health`; cron logs in-memory in the backend container.

These are the known expansion surfaces — not a complete roadmap.

---

*Last updated 2026-04-23.*
