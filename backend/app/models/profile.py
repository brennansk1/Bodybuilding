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
    training_duration_min: Mapped[int | None] = mapped_column(Integer, nullable=True)  # session length in minutes
    days_per_week: Mapped[int | None] = mapped_column(Integer, nullable=True, default=5)
    program_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    cycle_tracking_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    cycle_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="profile")
