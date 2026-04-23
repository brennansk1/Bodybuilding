# Viltrum — Deployment

Operational runbook for the home-server deployment. Everything runs in a
single Docker Compose stack on `<server-ip>`.

For local development (hot reload, etc.) see [`DEVELOPMENT.md`](./DEVELOPMENT.md).

---

## 1. Target box

- **Host:** `<deploy-user>@<server-ip>` (home-lan only; no external exposure)
- **Stack:** Docker + Docker Compose
- **Repo checkout:** `~/Bodybuilding/` (mirror of `main`)
- **Ports:** `3001` (frontend), `5432` (postgres), `8000` is container-internal only

### Containers

| Container | Image | Port | Purpose |
|---|---|---|---|
| `bodybuilding-postgres-1` | `postgres:16-alpine` | `5432` | DB. Volume: `pg_data` (persists across rebuilds) |
| `bodybuilding-backend-1` | locally built from `backend/Dockerfile` | `8000` (internal) | FastAPI app + cron worker |
| `bodybuilding-frontend-1` | locally built from `frontend/Dockerfile` | `3001 → 3000` | Next.js server |

The names are pinned by Compose's `<project>-<service>-<n>` convention
(`bodybuilding` comes from the repo directory name).

---

## 2. Standard deploy — pull, rebuild, restart

SSH in and run from the repo root:

```bash
ssh <deploy-user>@<server-ip>
cd ~/Bodybuilding

# Pull latest main
git fetch --all && git reset --hard origin/main

# Rebuild and restart (production target)
BUILD_TARGET=production docker compose up --build -d

# Tail logs until healthy
docker compose logs -f --tail=50 backend frontend
```

Compose will recreate only containers whose build context changed. To
force everything:

```bash
docker compose down
BUILD_TARGET=production docker compose up --build -d
```

**Data is safe** — only `docker compose down -v` touches the `pg_data`
volume.

---

## 3. Restart without rebuilding

```bash
docker compose restart backend   # code already in place, just bounce
docker compose restart frontend
docker compose restart           # all three
```

---

## 4. Smoke tests after deploy

Run from the server or any LAN client:

```bash
# Backend health
curl -s http://<server-ip>:3001/api/v1/health
# {"status":"healthy","timestamp":"..."}

# Frontend up
curl -sI http://<server-ip>:3001 | head -1
# HTTP/1.1 200 OK

# Login path (requires a valid account)
curl -s -X POST http://<server-ip>:3001/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"coronado_admin","password":"coronado2024!"}'
```

Inside the box you can reach the backend directly:

```bash
docker compose exec backend curl -s http://localhost:8000/api/v1/health
```

---

## 5. JWT minting recipe (manual token for scripts / debugging)

Uses `app.routers.auth.create_access_token`. Run inside the backend container:

```bash
docker compose exec backend python -c "
from app.routers.auth import create_access_token
import asyncio
from app.database import AsyncSessionLocal
from app.models.user import User
from sqlalchemy import select

async def mint(username):
    async with AsyncSessionLocal() as db:
        u = (await db.execute(select(User).where(User.username == username))).scalar_one()
        return create_access_token(str(u.id))

print(asyncio.run(mint('coronado_admin')))
"
```

The returned string is a 30-minute HS256 access token, signed with
`SECRET_KEY` from the container env. Pair with:

```bash
TOKEN='<paste-here>'
curl -s http://<server-ip>:3001/api/v1/auth/me -H "Authorization: Bearer $TOKEN"
```

For long-lived ingest (HealthKit shortcuts, Telegram bot, etc.) prefer
`POST /api/v1/auth/api-keys` — those keys never expire but are only
accepted on the whitelisted ingest routes.

---

## 6. Environment variables

Configured via `.env` at the repo root (Compose reads it automatically).
See `.env.example` for the template.

| Variable | Default | Notes |
|---|---|---|
| `POSTGRES_USER` | `cpos` | DB user; must match `DATABASE_URL` |
| `POSTGRES_PASSWORD` | `cpos_dev_password` | **change for prod** |
| `POSTGRES_DB` | `cpos` | DB name |
| `DATABASE_URL` | `postgresql+asyncpg://cpos:cpos_dev_password@postgres:5432/cpos` | Async driver is mandatory |
| `SECRET_KEY` | (insecure default) | JWT signing; `openssl rand -hex 32` |
| `ALGORITHM` | `HS256` | |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | |
| `ENVIRONMENT` | `production` | Enables prod-only middleware |
| `CORS_ORIGINS` | `http://localhost:3001` | Comma-separated; add `http://<server-ip>:3001` for LAN access |
| `DB_POOL_SIZE` | `5` | |
| `DB_MAX_OVERFLOW` | `10` | |
| `BUILD_TARGET` | `production` | `production` or `development` (hot-reload image) |
| `INTERNAL_API_URL` | `http://backend:8000` | Frontend → backend over compose network; do not change |

---

## 7. DB operations

### Migrations

```bash
docker compose exec backend alembic upgrade head    # apply pending
docker compose exec backend alembic revision --autogenerate -m "add foo"  # new migration
docker compose exec backend alembic history --verbose
```

Migrations run automatically on container start (via the Dockerfile
entrypoint). Autogenerate still requires human review before committing.

### Shell / psql

```bash
docker compose exec postgres psql -U cpos -d cpos
```

### Backup / restore

```bash
# Backup (run from host)
docker compose exec -T postgres pg_dump -U cpos cpos | gzip > ~/cpos-$(date +%F).sql.gz

# Restore (only if you really want to blow away current data)
gunzip -c ~/cpos-2026-04-22.sql.gz | docker compose exec -T postgres psql -U cpos -d cpos
```

---

## 8. Common failure modes

| Symptom | Likely cause | Fix |
|---|---|---|
| Frontend 502 on first load after deploy | Backend not healthy yet | Wait ~40s for healthcheck; `docker compose logs backend` |
| `jose.exceptions.JWTError: Signature has expired` | Expired token | Re-login or re-mint |
| Alembic "target database is not up to date" | Manual edits on DB | `docker compose exec backend alembic stamp head` after reviewing diffs |
| Migration fails: column already exists | Local DB ahead of Alembic history | Drop the orphan column, stamp head, regenerate migration |
| Frontend shows stale data | Browser SW cache | Hard-refresh (Cmd+Shift+R) or bump manifest version |
| `asyncpg.exceptions.PostgresPasswordError` | Stale `pg_data` vs new `POSTGRES_PASSWORD` | Volumes outlive env changes — either revert the password or re-init DB |

---

## 9. Admin tools

Once deployed:

- **Admin web panel:** `http://<server-ip>:3001/admin` (requires admin account) — health scan, user list, cron logs
- **CLI audit:** `docker compose exec backend python scripts/audit_direct.py <username>`
- **CLI audit tool (interactive):** `docker compose exec backend python scripts/audit_tool.py --help`

The admin router (`/api/v1/admin/fix/*`) one-click-fixes orphaned
sessions, stale programs, duplicate programs, and missing prescriptions
— see [`API_REFERENCE.md`](./API_REFERENCE.md).

---

*Last updated 2026-04-23.*
