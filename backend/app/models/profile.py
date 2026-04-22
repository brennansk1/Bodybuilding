from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    sex: Mapped[str] = mapped_column(String(10), nullable=False)  # male / female
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height_cm: Mapped[float] = mapped_column(Float, nullable=False)
    division: Mapped[str] = mapped_column(String(30), nullable=False)
    competition_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    training_experience_years: Mapped[int] = mapped_column(Integer, default=0)
    manual_body_fat_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    wrist_circumference_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    ankle_circumference_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    preferences: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    available_equipment: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    disliked_exercises: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    injury_history: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    training_start_time: Mapped[str | None] = mapped_column(String(5), nullable=True)  # "HH:MM" format
    training_end_time: Mapped[str | None] = mapped_column(String(5), nullable=True)  # "HH:MM" format
    training_time_anchor: Mapped[str | None] = mapped_column(String(10), nullable=True, default="start")  # "start" | "end"
    training_duration_min: Mapped[int | None] = mapped_column(Integer, nullable=True)  # session length in minutes
    days_per_week: Mapped[int | None] = mapped_column(Integer, nullable=True, default=5)
    program_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    cycle_tracking_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    cycle_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Training status — "natural" or "enhanced". Affects MRV/MAV_high scaling
    # in volume_landmarks and tier-threshold year requirements in readiness.py.
    training_status: Mapped[str] = mapped_column(String(16), nullable=False, default="natural")

    # Training-age factors (v2 Sprint 4) — discount chronological years into
    # effective training years. See engine1/training_age.py. Nullable so
    # existing profiles keep working; engine applies documented priors when
    # null. Settings UI for manual tuning is a follow-up session deliverable.
    training_consistency_factor: Mapped[float | None] = mapped_column(Float, nullable=True)
    training_intensity_factor:   Mapped[float | None] = mapped_column(Float, nullable=True)
    training_programming_factor: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Perpetual Progression Mode (PPM). Mutually exclusive with competition_date
    # — validated at the /profile API layer.
    ppm_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    target_tier: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1–5 (CompetitiveTier)
    current_cycle_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    current_cycle_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    current_cycle_week: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    cycle_focus_muscles: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # Per-user Telegram bot token from BotFather. Never exposed in GET responses.
    # TODO: encrypt at rest (app-level Fernet or pgcrypto) before production.
    telegram_bot_token: Mapped[str | None] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="profile")
