# Coronado

Competitive physique optimization system for IFBB Pro bodybuilding divisions. Three computation engines drive physique scoring, training programming, and nutrition prescription — all calibrated against Olympia-level coaching standards and peer-reviewed sports science.

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
- **LCSA (Lean Cross-Sectional Area):** Lean-girth normalized muscle area per site
- **Muscle Gaps:** Raw centimetre gap analysis with stay-small site handling (waist/hips never flagged as "needs growth")
- **Volumetric Ghost Model:** Hanavan segmental geometry with allometric cube-root scaling
- **Body Fat Estimation:** Jackson-Pollock 7-site, Navy method, Parrillo 9-site with confidence intervals
- **Aesthetic Vector:** Shoulder-to-waist ratio, V-taper, golden ratio analysis
- **Weight Cap:** Casey Butt genetic ceiling with IFBB Pro weight limits per division
- **Prep Timeline:** Phase recommendation engine with annual calendar generation

### Engine 2 — Training Programming

- **Split Designer:** Division-aware muscle importance weighting (side delts prioritized 1.4x for MP, 1.3x for Classic)
- **Periodization:** DUP mesocycles (MEV → MAV → MRV → Deload) with ARI-aware volume scaling
- **ARI (Autonomic Readiness Index):** HRV + sleep + soreness + resting HR → 0-100 readiness score
- **Autoregulation:** ARI-driven volume scaling (0.6x red zone to 1.1x green zone)
- **Volume/Strength Analytics:** Weekly volume per muscle group, estimated 1RM progression tracking
- **FST-7 Protocol:** Division-specific finisher targeting for priority muscles

### Engine 3 — Nutrition

- **TDEE:** Katch-McArdle/Cunningham BMR with phase-specific surplus/deficit
- **Macro Prescription:** Protein 2.0-2.7 g/kg, carb cycling, coach-aligned fat floors (0.65 g/kg cut, 0.6 g/kg female minimum)
- **Meal Planner:** Phase-ranked food database with coach-level blacklists (no red meat/dairy/nuts in peak week)
- **Food Preferences:** User-selected protein/carb/fat sources with per-phase prioritization
- **Peak Week:** Glycogen supercompensation protocol — carb depletion → load with water/sodium manipulation
- **Autoregulation:** Adherence lock, refeed triggers, metabolic adaptation tracking, halt-cut safety

### Admin System

- **Health Checks:** Automated detection of orphaned sessions, stale programs, duplicate programs, missing prescriptions
- **Cron Service:** Background maintenance every 6 hours with in-memory log buffer
- **Doctor Fix:** One-click resolution of all detected issues
- **User Management:** Full user overview with profile, data counts, active program, and nutrition details

## Quick Start

```bash
# Clone and configure
cp .env.example .env
# Edit .env with your credentials

# Development (with hot reload)
docker compose up --build

# Production
BUILD_TARGET=production docker compose up --build -d
```

**URL:** `http://localhost:3001`

### Accounts

| Account | Username | Password | Purpose |
|---------|----------|----------|---------|
| Admin | `coronado_admin` | `coronado2024!` | Full access + admin panel at `/admin` |
| Demo | `marcus_demo` | `admin123` | Pre-loaded Classic Physique test data (dev only) |

### Key Routes

| Route | Description |
|-------|-------------|
| `/dashboard` | Athlete home — PDS, gaps, training preview, macros |
| `/training` | Today's workout with gym-mode, Now Playing, plate calculator |
| `/training/program` | Mesocycle visualization, macro/meso/microcycle overlays |
| `/training/analytics` | Volume trends, strength progression charts |
| `/nutrition` | Daily macros, meal plan with per-ingredient breakdown |
| `/nutrition/peak-week` | 7-day peak week protocol |
| `/checkin` | Quick/Full/Fit3D check-in modes |
| `/checkin/review` | Weekly coaching review dashboard |
| `/progress` | Weight trend with 7-day rolling average, PDS history, photos |
| `/settings` | Profile, training, nutrition preferences, food selection |
| `/admin` | System health, user management, cron logs (admin only) |

## Project Structure

```
.
├── backend/
│   ├── app/
│   │   ├── engines/
│   │   │   ├── engine1/    # Physique analysis (PDS, LCSA, gaps, ghost model)
│   │   │   ├── engine2/    # Training (splits, periodization, ARI, resistance)
│   │   │   ├── engine3/    # Nutrition (macros, meal plan, peak week, autoregulation)
│   │   │   └── engine4/    # Cardio prescription
│   │   ├── constants/      # Division vectors, weight caps, exercise priorities
│   │   ├── models/         # SQLAlchemy ORM models (20 tables)
│   │   ├── routers/        # FastAPI route handlers (10 routers, 65+ endpoints)
│   │   ├── schemas/        # Pydantic request/response schemas
│   │   ├── services/       # Diagnostic orchestrator, seeds, cron maintenance
│   │   └── visualizations/ # Chart generation (Plotly)
│   └── tests/              # 481 tests — coaching alignment + multi-week simulation
├── frontend/
│   ├── src/
│   │   ├── app/            # Next.js pages (12 routes)
│   │   ├── components/     # React components (heatmap, charts, plate SVG, etc.)
│   │   ├── hooks/          # useAuth hook
│   │   └── lib/            # API client, TypeScript types
│   └── public/             # PWA manifest, pine tree icons
├── docs/                   # System reference, algorithm validation
├── docker-compose.yml      # Production deployment
├── docker-compose.override.yml  # Development overrides (auto-loaded)
└── .env.example
```

## Testing

```bash
cd backend && python -m pytest tests/ -v

# Test suite includes:
# - 200 coaching alignment tests (all 6 divisions × multiple phases)
# - 39 multi-week simulation tests (8 scenarios: full prep, recovery crisis,
#   adherence failure, weight stall, rapid loss, female prep, division transition)
# - 242 engine unit tests
```

The coaching alignment tests create realistic athlete profiles and verify every engine output matches what an Olympia-level coach would prescribe — macros, fat floors, protein escalation, volume allocation, peak week protocol, division-specific priorities.

## API

Health check: `GET /api/v1/health`

All endpoints require JWT authentication via `Authorization: Bearer <token>`.

```bash
# Login (uses username, not email)
curl -X POST http://localhost:3001/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "coronado_admin", "password": "coronado2024!"}'
```

## Admin Tools

### Web Admin Panel

Navigate to `http://localhost:3001/admin` (requires admin account).

- **System Health** — scan for data integrity issues with one-click fixes
- **Users** — view all users with expandable detail cards
- **Cron Logs** — view automated maintenance history, trigger manual runs

### CLI Tools

```bash
docker compose exec backend python scripts/audit_direct.py <username>
docker compose exec backend python scripts/audit_tool.py --help
```

## Data Persistence

PostgreSQL data is stored in a named Docker volume (`pg_data`). Container rebuilds do **not** wipe user data. Only `docker compose down -v` removes the volume.

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

## Documentation

Detailed references in `docs/`:

- `SYSTEM_REFERENCE.md` — Complete API and algorithm documentation
- `VERIFY_ALGORITHMS.md` — Peer-reviewed constant validation with citations
- `DIVISION_VECTORS.md` — Ideal circumference-to-height ratios per division
- `EXERCISE_PRIORITIES.md` — Division-specific exercise cascades
- `NUTRITION_CARDIO_ENGINE.md` — Nutrition and cardio algorithm design
- `coaching_validation_checklist.md` — Pro coaching standard checklist
