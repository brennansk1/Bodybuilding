# Coronado

Competitive physique optimization system for IFBB Pro bodybuilding divisions. Three computation engines drive physique scoring, training programming, and nutrition prescription — all calibrated against pro coaching standards and peer-reviewed sports science.

## Supported Divisions

- Men's Open Bodybuilding
- Classic Physique
- Men's Physique
- Women's Figure
- Women's Bikini
- Women's Physique

## Architecture

```
backend/     FastAPI + SQLAlchemy (async) + PostgreSQL
frontend/    Next.js 14 + TypeScript + Tailwind CSS
```

### Engine 1 — Physique Analysis

- **PDS (Physique Development Score):** Division-weighted composite of muscle mass, conditioning, symmetry, and aesthetics (0-100 scale)
- **HQI (Hypertrophy Quality Index):** Per-site scoring against division-specific ideal proportions via cosine similarity
- **LCSA (Lean Cross-Sectional Area):** Lean-girth normalized muscle area per site
- **Volumetric Ghost Model:** Hanavan segmental geometry with allometric cube-root scaling — generates 3D ideal circumference targets
- **Body Fat Estimation:** Jackson-Pollock 7-site, Navy method, or manual entry
- **Aesthetic Vector:** Shoulder-to-waist ratio, V-taper, golden ratio analysis
- **Weight Cap:** IFBB Pro official weight limits per height bracket and division
- **Prep Timeline:** Phase recommendation engine (bulk/cut/maintain/recomp) based on competition proximity, muscle adequacy, and body fat

### Engine 2 — Training Programming

- **Split Designer:** Division-aware muscle importance weighting with auto/PPL/UL/bro split generation
- **Periodization:** DUP mesocycles (MEV → MAV → MRV → Deload) with progressive overload
- **ARI (Autonomic Readiness Index):** HRV + sleep + soreness + resting HR → 0-100 readiness score
- **Autoregulation:** ARI-driven volume scaling (0.6x red zone to 1.1x green zone)
- **Resistance Progression:** Epley 1RM estimation, SFR-ranked exercise selection, biomechanical efficiency scoring
- **FST-7 Protocol:** Division-specific finisher targeting for priority muscles

### Engine 3 — Nutrition

- **TDEE:** Katch-McArdle BMR with PAL multipliers and phase-specific surplus/deficit
- **Macro Prescription:** Protein (2.0-2.7 g/kg LBM), carb cycling (training/rest), fat floors
- **Peak Week:** Water/sodium/carb manipulation protocol for competition week
- **Thermodynamic Model:** Adaptive metabolic rate tracking

## Quick Start

```bash
# Clone and configure
cp .env.example .env
# Edit .env with your credentials

# Development (with hot reload)
docker compose up --build

# Production
docker compose -f docker-compose.yml up --build
```

**Development:** `http://localhost:3001` (frontend) / `http://localhost:8000` (API)

### Accounts

| Account | Email | Password | Purpose |
|---------|-------|----------|---------|
| Admin | `coronado@admin.dev` | `coronado2024!` | Dashboard access, admin tasks |
| Demo | `admin@coronado.dev` | `admin123` | Pre-loaded Men's Open test data (dev only) |

## Project Structure

```
.
├── backend/
│   ├── app/
│   │   ├── engines/
│   │   │   ├── engine1/    # Physique analysis (PDS, HQI, LCSA, ghost model)
│   │   │   ├── engine2/    # Training (splits, periodization, ARI, resistance)
│   │   │   ├── engine3/    # Nutrition (macros, peak week, thermodynamic)
│   │   │   └── engine4/    # Cardio (WIP)
│   │   ├── constants/      # Division vectors, weight caps, k-factors
│   │   ├── models/         # SQLAlchemy ORM models
│   │   ├── routers/        # FastAPI route handlers
│   │   ├── schemas/        # Pydantic request/response schemas
│   │   ├── services/       # Business logic, diagnostic orchestrator, seeds
│   │   └── visualizations/ # Chart generation
│   ├── scripts/            # Admin utilities (audit, user management)
│   └── tests/              # Pytest suite
├── frontend/
│   ├── src/
│   │   ├── app/            # Next.js pages (dashboard, training, nutrition, etc.)
│   │   └── components/     # React components (heatmap, spider chart, etc.)
│   └── public/
├── docs/                   # System reference, algorithm validation, division specs
├── scripts/                # Data build scripts (exercises, ingredients)
├── docker-compose.yml      # Production deployment
├── docker-compose.override.yml  # Development overrides (auto-loaded)
└── .env.example
```

## API

Health check: `GET /api/v1/health`

All endpoints require JWT authentication via `Authorization: Bearer <token>`.

```bash
# Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "coronado@admin.dev", "password": "coronado2024!"}'

# Run full diagnostic
curl http://localhost:8000/api/v1/engine1/diagnostic \
  -H "Authorization: Bearer <token>"
```

## Admin Tools

```bash
# List all users
docker compose exec backend python scripts/list_users.py

# Full engine audit for a user
docker compose exec backend python scripts/audit_direct.py <username>

# CLI audit tool (18+ commands)
docker compose exec backend python scripts/audit_tool.py --help
```

## Testing

```bash
cd backend && pytest
```

## Documentation

Detailed references are in the `docs/` directory:

- `SYSTEM_REFERENCE.md` — Complete API and algorithm documentation
- `VERIFY_ALGORITHMS.md` — Peer-reviewed constant validation with citations
- `DIVISION_VECTORS.md` — Ideal circumference-to-height ratios per division
- `EXERCISE_PRIORITIES.md` — Division-specific exercise cascades
- `GHOST_MODEL_VERIFICATION.md` — Volumetric ghost model validation
- `NUTRITION_CARDIO_ENGINE.md` — Nutrition and cardio algorithm design
- `coaching_validation_checklist.md` — Pro coaching standard checklist

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://...` | Async PostgreSQL connection string |
| `SECRET_KEY` | (insecure default) | JWT signing key — **must change for production** |
| `ENVIRONMENT` | `development` | `development` or `production` |
| `CORS_ORIGINS` | `http://localhost:3001` | Comma-separated allowed origins |
| `DB_POOL_SIZE` | `5` | SQLAlchemy connection pool size |
| `DB_MAX_OVERFLOW` | `10` | Max overflow connections |
| `BUILD_TARGET` | `production` | Docker build stage (`production` or `development`) |
