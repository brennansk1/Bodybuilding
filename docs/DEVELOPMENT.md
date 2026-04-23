# Viltrum — Development & Testing

Local development setup, test commands, common workflows. For the
home-server deploy see [`DEPLOYMENT.md`](./DEPLOYMENT.md).

---

## 1. Prerequisites

- **Docker** + **Docker Compose v2** (`docker compose …`, not the legacy `docker-compose`)
- **Python ≥ 3.11** (only if running backend outside Docker)
- **Node ≥ 20** (only if running frontend outside Docker)
- **PostgreSQL 16** (only if not using the Compose DB)

---

## 2. Fast path — full stack via Docker

The default `docker compose up` wires:

- Postgres on `:5432` (host) ← container `bodybuilding-postgres-1`
- Backend on `:8000` (host, dev override) ← container `bodybuilding-backend-1` with `--reload` and a bind mount of `./backend`
- Frontend on `:3001` (host) ← container `bodybuilding-frontend-1`

```bash
cp .env.example .env
# Edit .env — at minimum set SECRET_KEY to `openssl rand -hex 32`

docker compose up --build      # first time: builds images
# Visit http://localhost:3001
```

`docker-compose.override.yml` (gitted) is auto-loaded. It pins the
backend to dev target (`uvicorn … --reload` + bind mount) and keeps the
frontend in production mode because Next.js JIT-compile latency on first
visit is painful. To force the frontend into dev mode locally, create a
`docker-compose.local.yml` (gitignored) with the target override and run:

```bash
docker compose -f docker-compose.yml \
               -f docker-compose.override.yml \
               -f docker-compose.local.yml up -d
```

---

## 3. Slow path — native hot reload

Useful when you're iterating only on backend or only on frontend.

### Backend (native, DB in Docker)

```bash
# Spin up just postgres from the Compose file
docker compose up -d postgres

cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Apply migrations
alembic upgrade head

# Run
DATABASE_URL="postgresql+asyncpg://cpos:cpos_dev_password@localhost:5432/cpos" \
SECRET_KEY="dev-secret" \
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend (native, backend in Docker or native)

```bash
cd frontend
npm install
# If backend is in Docker on :8000, this is the default:
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
# Dashboard at http://localhost:3000 (native dev port) — frontend container uses :3001
```

---

## 4. Environment variables

Full reference in [`DEPLOYMENT.md § 6`](./DEPLOYMENT.md). For local dev
the ones you're likeliest to touch:

| Var | Purpose |
|---|---|
| `SECRET_KEY` | JWT signing — must be set (`openssl rand -hex 32`) |
| `DATABASE_URL` | Async Postgres URL. Default works against the Compose DB. |
| `CORS_ORIGINS` | Add `http://localhost:3000` if you run native Next alongside Dockerized backend |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_BOT_USERNAME` | Optional — enables Telegram bot. Leave empty to disable. |

---

## 5. Dependencies

### Backend — `backend/pyproject.toml`

Runtime: `fastapi`, `uvicorn[standard]`, `sqlalchemy[asyncio]`,
`asyncpg`, `alembic`, `pydantic`, `pydantic-settings`, `python-jose`,
`passlib[bcrypt]`, `python-multipart`, `numpy`, `plotly`, `httpx`,
`gunicorn`.

Dev (`pip install -e ".[dev]"`): `pytest`, `pytest-asyncio`, `pytest-cov`,
`ruff`, `mypy`, `httpx` (for the async test client).

### Frontend — `frontend/package.json`

Runtime: `next@14.2.3`, `react@18`, `@dnd-kit/*`, `plotly.js` +
`react-plotly.js`, `lucide-react`, `tegaki` (display font). Dev:
`typescript`, `@types/{node,react,react-dom}`, `tailwindcss`, `postcss`,
`autoprefixer`.

---

## 6. Testing

### Backend — pytest

```bash
cd backend
pytest tests/ -q                       # full suite
pytest tests/test_sprint_v3.py -q      # one file
pytest -k "test_readiness" -q          # match-by-name
pytest tests/ --cov=app --cov-report=term-missing
```

Inside Docker:

```bash
docker compose exec backend pytest tests/ -q
```

### Test file map

Everything lives under `backend/tests/`:

| File | What it covers |
|---|---|
| `test_constants.py` | Division vectors, weight caps, visibility tables — spot-checks values against expected pro physiques |
| `test_engine1.py`, `test_engine1_full.py` | Diagnostic engine: body fat formulas, LCSA, HQI, muscle gaps, PDS, aesthetic vector, weight cap, trajectory |
| `test_engine2.py`, `test_engine2_full.py` | Training engine: split designer, periodization, ARI, resistance, recovery, biomechanical |
| `test_engine3.py`, `test_engine3_full.py` | Nutrition engine: TDEE, macros, carb cycling, autoregulation, peak week, kinetic, thermodynamic |
| `test_ceiling_ensemble.py` | Casey-Butt + Kouri natural-ceiling honesty gate |
| `test_classic_audit.py` | End-to-end Classic Physique pipeline sanity |
| `test_coaching_alignment.py` | 200+ tests: realistic athletes × phases × divisions, every output matches what a pro coach would prescribe |
| `test_exercise_priorities.py` | Per-division exercise cascades respect division judging criteria |
| `test_girth_projection.py` | `physio.project_lean_girth` BF-stripping math |
| `test_hqi_visibility.py` | Division visibility weights and HQI averaging |
| `test_illusion_metrics.py` | X-frame, S:W, chest:waist, parity |
| `test_logistic_gains.py` | `readiness.estimate_cycles_to_tier` logistic projection |
| `test_mens_physique_188cm.py` | MP division realism at tall frame |
| `test_multi_week_simulation.py` | Full multi-week prep scenarios (recovery crisis, adherence failure, weight stall, rapid loss, female prep, division transition) |
| `test_physio_provenance.py` | Every engine pulls `STAGE_BF_PCT` etc. from `physio.py` — no inline duplicates |
| `test_readiness_stage_weight.py` | Stage-projected weight math + weight-cap % gate |
| `test_sprint_v3.py` | V3 features: achieved-tier classification, nutrition override, structural priorities, V3 insights endpoints |

### Frontend — TypeScript type-check

```bash
cd frontend
npx tsc --noEmit         # type-check without emitting
npm run lint             # ESLint
npm run build            # full Next build — catches runtime compile errors
```

There is currently no frontend unit/integration test suite. Type-check +
build is the closest proxy.

---

## 7. Database workflows

### Apply migrations

```bash
docker compose exec backend alembic upgrade head
```

### New migration (autogenerate from model diff)

```bash
docker compose exec backend alembic revision --autogenerate -m "add foo column"
# Review backend/alembic/versions/*_add_foo_column.py before committing
docker compose exec backend alembic upgrade head
```

### Psql shell

```bash
docker compose exec postgres psql -U cpos -d cpos
```

### Seed test data

```bash
docker compose exec backend python scripts/seed_demo_user.py
# Creates `marcus_demo` with pre-loaded Classic Physique tape + HRV history
```

---

## 8. Common workflows

### Reset the DB entirely

```bash
docker compose down -v    # -v drops the pg_data volume
docker compose up --build
# Migrations run on startup; re-seed if needed
```

### Pull latest and re-run

```bash
git pull
docker compose up --build -d   # --build catches Dockerfile or deps changes
```

### Debug a failing engine call

Engine modules have **no DB or HTTP dependencies**. Run them directly:

```bash
docker compose exec backend python -c "
from app.engines.engine1.readiness import evaluate_readiness
from app.constants.competitive_tiers import CLASSIC_PHYSIQUE_TIERS
result = evaluate_readiness(
    metrics={'weight_cap_pct': 0.88, 'bf_pct': 8.0, 'ffmi_normalized': 24.5, ...},
    target_tier=2,
    weight_cap_kg=105.2,
    training_status='natural',
    division='classic_physique',
    sex='male',
)
print(result)
"
```

This isolates the failure to pure-math input/output with no orchestration
noise.

### Mint a JWT for curl / Postman testing

See [`DEPLOYMENT.md § 5`](./DEPLOYMENT.md) — the recipe works identically
in dev.

---

## 9. Code style

- Backend: `ruff` for lint + format (config in `pyproject.toml`). Run `ruff check .` and `ruff format .`.
- Frontend: `next lint` (ESLint default Next config). Tailwind class sort is conventional.
- No pre-commit hook enforced in CI — contributors are expected to run lint + tests before pushing.

---

## 10. Accounts for local dev

Created by the seed script when the DB is fresh:

| Account | Username | Password | Purpose |
|---|---|---|---|
| Admin | `coronado_admin` | `coronado2024!` | Full access + `/admin` panel |
| Demo | `marcus_demo` | `admin123` | Pre-loaded Classic Physique fixture |

Neither account is created automatically — run `scripts/seed_admin.py` /
`scripts/seed_demo_user.py` if they're missing.

---

*Last updated 2026-04-23.*
