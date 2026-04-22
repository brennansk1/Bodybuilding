from contextlib import asynccontextmanager
import asyncio
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from app.config import settings
from app.database import engine, Base, async_session
from app.models import *  # noqa: F401, F403 — register all models with Base
from app.routers import auth, onboarding, checkin, engine1, engine2, engine3, viz, export, upload, admin, telegram, ppm

logger = logging.getLogger(__name__)


import re as _re

_IDENT_RE = _re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def _validate_identifier(name: str) -> str:
    """Validate a SQL identifier to prevent injection."""
    if not _IDENT_RE.match(name):
        raise ValueError(f"Invalid SQL identifier: {name!r}")
    return name


def _add_column_if_missing(conn, table: str, column: str, col_type: str):
    """Safely add a column to an existing table if it doesn't exist."""
    from sqlalchemy import text
    _validate_identifier(table)
    _validate_identifier(column)
    result = conn.execute(
        text("SELECT column_name FROM information_schema.columns "
             "WHERE table_name = :tbl AND column_name = :col"),
        {"tbl": table, "col": column},
    )
    if result.fetchone() is None:
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))


def _create_index_if_missing(conn, index_name: str, table: str, columns: str):
    """Create an index if it doesn't already exist."""
    from sqlalchemy import text
    _validate_identifier(index_name)
    _validate_identifier(table)
    result = conn.execute(
        text("SELECT 1 FROM pg_indexes WHERE indexname = :idx"),
        {"idx": index_name},
    )
    if result.fetchone() is None:
        conn.execute(text(f"CREATE INDEX {index_name} ON {table} ({columns})"))


def _run_schema_migrations(conn):
    """Add any new columns and indexes that create_all won't handle on existing tables."""
    _add_column_if_missing(conn, "user_profiles", "age", "INTEGER")
    _add_column_if_missing(conn, "user_profiles", "preferences", "JSONB")
    _add_column_if_missing(conn, "user_profiles", "manual_body_fat_pct", "DOUBLE PRECISION")
    _add_column_if_missing(conn, "hrv_log", "soreness_score", "DOUBLE PRECISION")
    _add_column_if_missing(conn, "hrv_log", "notes", "TEXT")
    # Training session/set new fields
    _add_column_if_missing(conn, "training_sessions", "split_type", "VARCHAR(30)")
    _add_column_if_missing(conn, "training_sessions", "stale_baselines", "BOOLEAN DEFAULT FALSE")
    _add_column_if_missing(conn, "training_programs", "custom_template", "JSONB")
    _add_column_if_missing(conn, "training_sets", "is_warmup", "BOOLEAN DEFAULT FALSE")
    # Exercise custom user support
    _add_column_if_missing(conn, "exercises", "user_id", "UUID")
    _add_column_if_missing(conn, "exercises", "is_custom", "BOOLEAN DEFAULT FALSE")
    _add_column_if_missing(conn, "exercises", "movement_pattern_detail", "VARCHAR(50)")
    _add_column_if_missing(conn, "exercises", "contraindications", "JSONB")
    # Weekly checkin photo fields
    _add_column_if_missing(conn, "weekly_checkins", "side_left_photo_url", "VARCHAR(255)")
    _add_column_if_missing(conn, "weekly_checkins", "side_right_photo_url", "VARCHAR(255)")
    _add_column_if_missing(conn, "weekly_checkins", "front_pose_photo_url", "VARCHAR(255)")
    _add_column_if_missing(conn, "weekly_checkins", "back_pose_photo_url", "VARCHAR(255)")
    # PPM (Perpetual Progression Mode) + training-status fields on profile
    _add_column_if_missing(conn, "user_profiles", "training_status", "VARCHAR(16) NOT NULL DEFAULT 'natural'")
    _add_column_if_missing(conn, "user_profiles", "ppm_enabled", "BOOLEAN NOT NULL DEFAULT FALSE")
    _add_column_if_missing(conn, "user_profiles", "target_tier", "INTEGER")
    _add_column_if_missing(conn, "user_profiles", "current_cycle_number", "INTEGER NOT NULL DEFAULT 0")
    _add_column_if_missing(conn, "user_profiles", "current_cycle_start_date", "DATE")
    _add_column_if_missing(conn, "user_profiles", "current_cycle_week", "INTEGER NOT NULL DEFAULT 1")
    _add_column_if_missing(conn, "user_profiles", "cycle_focus_muscles", "JSONB")
    # v2 Sprint 4 — training-age correction factors
    _add_column_if_missing(conn, "user_profiles", "training_consistency_factor", "DOUBLE PRECISION")
    _add_column_if_missing(conn, "user_profiles", "training_intensity_factor",   "DOUBLE PRECISION")
    _add_column_if_missing(conn, "user_profiles", "training_programming_factor", "DOUBLE PRECISION")
    # Indexes for frequently queried columns
    _create_index_if_missing(conn, "ix_session_user_date", "training_sessions", "user_id, session_date")
    _create_index_if_missing(conn, "ix_sets_session", "training_sets", "session_id")
    _create_index_if_missing(conn, "ix_exercises_muscle", "exercises", "primary_muscle")
    _create_index_if_missing(conn, "ix_ppm_checkpoints_user_cycle", "ppm_checkpoints", "user_id, cycle_number")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create all tables and run column migrations
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_run_schema_migrations)

    # Seed reference data on first startup
    from app.services.seed import run_all_seeds
    async with async_session() as db:
        seeded = await run_all_seeds(db)
        await db.commit()
        if seeded["exercises"] or seeded["ingredients"]:
            import logging
            logging.getLogger(__name__).info(
                f"Seeded: {seeded['exercises']} exercises, {seeded['ingredients']} ingredients"
            )

    # Seed admin account (always, idempotent)
    from app.services.admin_seed import seed_admin_account
    async with async_session() as db:
        await seed_admin_account(db)
        await db.commit()

    # Seed demo test account (idempotent, dev/staging only)
    if settings.ENVIRONMENT != "production":
        from app.services.demo_seed import seed_demo_admin
        async with async_session() as db:
            created = await seed_demo_admin(db)
            await db.commit()

    # Start background cron maintenance (every 6 hours)
    from app.services.cron import cron_loop
    cron_task = asyncio.create_task(cron_loop(interval_seconds=21600))
    logger.info("Background cron started (6h interval)")

    # Start telegram notification dispatcher (every 15 min) — separate loop
    # so time-windowed notifications (7 AM, 9 PM, etc.) have sub-hour resolution.
    from app.services.notification_dispatcher import notification_loop
    notif_task = asyncio.create_task(notification_loop(interval_seconds=900))
    logger.info("Notification dispatcher started (15m interval)")

    yield

    cron_task.cancel()
    notif_task.cancel()
    await engine.dispose()


app = FastAPI(
    title="Coronado",
    description="Competitive Physique Optimization System — Coronado v4.0",
    version="4.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"error": "Validation error", "detail": str(exc.errors()), "code": 422},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    detail = str(exc) if settings.ENVIRONMENT != "production" else "An unexpected error occurred"
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": detail, "code": 500},
    )

# Routers
app.include_router(auth.router, prefix="/api/v1")
app.include_router(onboarding.router, prefix="/api/v1")
app.include_router(checkin.router, prefix="/api/v1")
app.include_router(engine1.router, prefix="/api/v1")
app.include_router(engine2.router, prefix="/api/v1")
app.include_router(engine3.router, prefix="/api/v1")
app.include_router(viz.router, prefix="/api/v1")
app.include_router(export.router, prefix="/api/v1")
app.include_router(upload.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(telegram.router, prefix="/api/v1")
app.include_router(ppm.router, prefix="/api/v1")

import os
from pathlib import Path as _Path
from fastapi.staticfiles import StaticFiles

_UPLOAD_DIR = (_Path(__file__).resolve().parent.parent / "uploads").resolve()
_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(_UPLOAD_DIR)), name="uploads")


@app.get("/api/v1/health")
async def health_check():
    from sqlalchemy import text
    db_status = "unknown"
    try:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        logger.error("Health check DB error: %s", e)
        db_status = "error"
    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "version": "4.0.0",
        "system": "Coronado",
        "environment": settings.ENVIRONMENT,
        "db": db_status,
    }
