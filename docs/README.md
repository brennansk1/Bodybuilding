# Viltrum — Documentation Index

Viltrum (formerly Coronado / CPOS) is a multi-engine bodybuilding coaching
app for IFBB/NPC competitors. FastAPI + SQLAlchemy async backend, Next.js
14 frontend, PostgreSQL, Dockerized.

If you're new to the project, read in this order:

1. [`ARCHITECTURE.md`](./ARCHITECTURE.md) — the 30,000-ft view
2. [`ENGINES.md`](./ENGINES.md) — the four engines, what each does
3. [`PPM.md`](./PPM.md) — Perpetual Progression Mode (the product's headline feature)
4. [`DEVELOPMENT.md`](./DEVELOPMENT.md) — get a local stack running
5. [`DEPLOYMENT.md`](./DEPLOYMENT.md) — push to the home-server box

---

## Architecture & overview

| Doc | What it covers |
|---|---|
| [`ARCHITECTURE.md`](./ARCHITECTURE.md) | System diagram, request flow, deployment topology, tech stack |
| [`DATABASE_SCHEMA.md`](./DATABASE_SCHEMA.md) | Every SQLAlchemy model + V3 profile field reference |
| [`API_REFERENCE.md`](./API_REFERENCE.md) | Every router + its endpoints (auth, engine1–3, PPM, insights, …) |
| [`FRONTEND_ROUTES.md`](./FRONTEND_ROUTES.md) | Next.js App Router page tree |

## Engines & algorithms (authoritative)

| Doc | What it covers |
|---|---|
| [`ENGINES.md`](./ENGINES.md) | **Authoritative** engine reference — E1 diagnostic, E2 training, E3 nutrition, E4 cardio |
| [`CALCULATIONS.md`](./CALCULATIONS.md) | **Authoritative** formulas, constants, thresholds. File-anchored. |
| [`COMPETITIVE_TIERS.md`](./COMPETITIVE_TIERS.md) | T1–T5 ladder, gate thresholds, PPM readiness math |
| [`DIVISION_VECTORS.md`](./DIVISION_VECTORS.md) | Per-division proportion ratios (current V3 calibrations) |
| [`EXERCISE_PRIORITIES.md`](./EXERCISE_PRIORITIES.md) | Per-division exercise cascade + max set caps |
| [`PPM.md`](./PPM.md) | Perpetual Progression Mode — 14/16-week cycles, checkpoints, phase routing |

## Frontend & operations

| Doc | What it covers |
|---|---|
| [`DASHBOARD_WIDGETS.md`](./DASHBOARD_WIDGETS.md) | All 35 dashboard widgets — predicate, renderer, endpoint |
| [`DEVELOPMENT.md`](./DEVELOPMENT.md) | Local dev setup, tests, type-check, env vars |
| [`DEPLOYMENT.md`](./DEPLOYMENT.md) | Home-server deploy, Docker Compose, JWT minting, smoke tests |

## Specifications (deep-dives)

| Doc | What it covers |
|---|---|
| [`NUTRITION_CARDIO_ENGINE.md`](./NUTRITION_CARDIO_ENGINE.md) | Full E3 + E4 algorithmic spec (longest doc; still current) |

## Reference data & historical snapshots

| Doc | What it covers |
|---|---|
| [`Exercise Database.md`](./Exercise%20Database.md) | 185-exercise research catalog (deliberately preserved) |
| [`SYSTEM_REFERENCE.md`](./SYSTEM_REFERENCE.md) | **Legacy** — pre-PPM / pre-E4 / Coronado-era system reference. Partially stale. |
| [`GHOST_MODEL_VERIFICATION.md`](./GHOST_MODEL_VERIFICATION.md) | Snapshot (2026-03-23) — ghost-model audit trail |
| [`VERIFY_ALGORITHMS.md`](./VERIFY_ALGORITHMS.md) | Snapshot (2026-03-19) — initial constant verification |

---

## Doc-writing conventions

- **Authoritative** means "if this file disagrees with another file, this file wins." `CALCULATIONS.md` is authoritative for numbers; `ENGINES.md` for module responsibilities; `COMPETITIVE_TIERS.md` for the PPM ladder.
- **Snapshot** docs carry a date banner. They're audit artifacts — keep them for traceability but don't edit them retroactively.
- File paths in docs are always absolute from the repo root (`backend/app/…`) so they grep cleanly.

*Last indexed 2026-04-23.*
