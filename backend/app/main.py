from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine, Base, async_session
from app.models import *  # noqa: F401, F403 — register all models with Base
from app.routers import auth, onboarding, checkin, engine1, engine2, engine3, viz, export, upload


def _add_column_if_missing(conn, table: str, column: str, col_type: str):
    """Safely add a column to an existing table if it doesn't exist."""
    from sqlalchemy import text
    result = conn.execute(text(
        f"SELECT column_name FROM information_schema.columns "
        f"WHERE table_name='{table}' AND column_name='{column}'"
    ))
    if result.fetchone() is None:
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))


def _create_index_if_missing(conn, index_name: str, table: str, columns: str):
    """Create an index if it doesn't already exist."""
    from sqlalchemy import text
    result = conn.execute(text(
        f"SELECT 1 FROM pg_indexes WHERE indexname = '{index_name}'"
    ))
    if result.fetchone() is None:
        conn.execute(text(f"CREATE INDEX {index_name} ON {table} ({columns})"))


def _run_schema_migrations(conn):
    """Add any new columns and indexes that create_all won't handle on existing tables."""
    _add_column_if_missing(conn, "user_profiles", "age", "INTEGER")
    _add_column_if_missing(conn, "user_profiles", "preferences", "JSONB")
    _add_column_if_missing(conn, "user_profiles", "manual_body_fat_pct", "DOUBLE PRECISION")
    _add_column_if_missing(conn, "hrv_log", "soreness_score", "DOUBLE PRECISION")
    # Training session/set new fields
    _add_column_if_missing(conn, "training_sessions", "split_type", "VARCHAR(30)")
    _add_column_if_missing(conn, "training_sessions", "stale_baselines", "BOOLEAN DEFAULT FALSE")
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
    # Indexes for frequently queried columns
    _create_index_if_missing(conn, "ix_session_user_date", "training_sessions", "user_id, session_date")
    _create_index_if_missing(conn, "ix_sets_session", "training_sets", "session_id")
    _create_index_if_missing(conn, "ix_exercises_muscle", "exercises", "primary_muscle")


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

    # Seed demo admin account (idempotent)
    from app.services.demo_seed import seed_demo_admin
    async with async_session() as db:
        created = await seed_demo_admin(db)
        await db.commit()

    yield
    await engine.dispose()


app = FastAPI(
    title="Coronado",
    description="Competitive Physique Optimization System — Coronado v4.0",
    version="4.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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

import os
from fastapi.staticfiles import StaticFiles

os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")


@app.get("/api/v1/health")
async def health_check():
    return {"status": "healthy", "version": "4.0.0", "system": "Coronado"}
