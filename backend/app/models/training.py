from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Exercise(Base):
    __tablename__ = "exercises"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    primary_muscle: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    secondary_muscles: Mapped[str | None] = mapped_column(Text, nullable=True)
    movement_pattern: Mapped[str] = mapped_column(String(30), nullable=False)  # push/pull/squat/hinge/carry
    equipment: Mapped[str] = mapped_column(String(30), nullable=False)  # barbell/dumbbell/cable/machine/bodyweight
    biomechanical_efficiency: Mapped[float] = mapped_column(Float, default=1.0)
    fatigue_ratio: Mapped[float] = mapped_column(Float, default=1.0)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    movement_pattern_detail: Mapped[str | None] = mapped_column(String(50), nullable=True)
    contraindications: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    is_custom: Mapped[bool] = mapped_column(default=False)


class StrengthBaseline(Base):
    __tablename__ = "strength_baselines"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    exercise_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("exercises.id"))
    one_rm_kg: Mapped[float] = mapped_column(Float, nullable=False)
    recorded_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="strength_baselines")
    exercise: Mapped["Exercise"] = relationship()

    __table_args__ = (Index("ix_strength_bl_user_date", "user_id", "recorded_date"),)


class StrengthLog(Base):
    __tablename__ = "strength_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    exercise_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("exercises.id"))
    weight_kg: Mapped[float] = mapped_column(Float, nullable=False)
    reps: Mapped[int] = mapped_column(Integer, nullable=False)
    rpe: Mapped[float | None] = mapped_column(Float, nullable=True)
    estimated_1rm: Mapped[float | None] = mapped_column(Float, nullable=True)
    recorded_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="strength_logs")
    exercise: Mapped["Exercise"] = relationship()

    __table_args__ = (Index("ix_strength_log_user_date", "user_id", "recorded_date"),)


class DivisionVector(Base):
    __tablename__ = "division_vectors"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    division: Mapped[str] = mapped_column(String(30), nullable=False)
    site: Mapped[str] = mapped_column(String(30), nullable=False)
    ideal_proportion: Mapped[float] = mapped_column(Float, nullable=False)

    __table_args__ = (Index("ix_div_vector", "division", "site"),)


class HRVLog(Base):
    __tablename__ = "hrv_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    rmssd: Mapped[float] = mapped_column(Float, nullable=False)
    resting_hr: Mapped[float | None] = mapped_column(Float, nullable=True)
    sleep_quality: Mapped[float | None] = mapped_column(Float, nullable=True)  # 1-10
    soreness_score: Mapped[float | None] = mapped_column(Float, nullable=True)  # 1-10
    sore_muscles: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    recorded_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="hrv_logs")

    __table_args__ = (Index("ix_hrv_user_date", "user_id", "recorded_date"),)


class ARILog(Base):
    __tablename__ = "ari_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    ari_score: Mapped[float] = mapped_column(Float, nullable=False)
    hrv_component: Mapped[float] = mapped_column(Float, nullable=False)
    sleep_component: Mapped[float] = mapped_column(Float, nullable=False)
    soreness_component: Mapped[float] = mapped_column(Float, nullable=False)
    recorded_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="ari_logs")

    __table_args__ = (Index("ix_ari_user_date", "user_id", "recorded_date"),)


class TrainingProgram(Base):
    __tablename__ = "training_programs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    split_type: Mapped[str] = mapped_column(String(30), nullable=False)  # ppl, upper_lower, full_body, bro_split
    days_per_week: Mapped[int] = mapped_column(Integer, nullable=False)
    mesocycle_weeks: Mapped[int] = mapped_column(Integer, default=6)
    current_week: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(default=True)
    volume_allocation: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    custom_template: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="training_programs")
    sessions: Mapped[list["TrainingSession"]] = relationship(back_populates="program", cascade="all, delete-orphan")


class TrainingSession(Base):
    __tablename__ = "training_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    program_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("training_programs.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    session_date: Mapped[date] = mapped_column(Date, nullable=False)
    session_type: Mapped[str] = mapped_column(String(30), nullable=False)
    week_number: Mapped[int] = mapped_column(Integer, nullable=False)
    day_number: Mapped[int] = mapped_column(Integer, nullable=False)
    completed: Mapped[bool] = mapped_column(default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    split_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    stale_baselines: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    program: Mapped["TrainingProgram"] = relationship(back_populates="sessions")
    sets: Mapped[list["TrainingSet"]] = relationship(back_populates="session", cascade="all, delete-orphan")

    __table_args__ = (Index("ix_session_user_date", "user_id", "session_date"),)


class TrainingSet(Base):
    __tablename__ = "training_sets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("training_sessions.id", ondelete="CASCADE"))
    exercise_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("exercises.id"))
    set_number: Mapped[int] = mapped_column(Integer, nullable=False)
    prescribed_reps: Mapped[int] = mapped_column(Integer, nullable=False)
    prescribed_weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    actual_reps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actual_weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    rpe: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_warmup: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session: Mapped["TrainingSession"] = relationship(back_populates="sets")
    exercise: Mapped["Exercise"] = relationship()

    __table_args__ = (Index("ix_sets_session", "session_id"),)


class VolumeAllocationLog(Base):
    __tablename__ = "volume_allocation_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    muscle_group: Mapped[str] = mapped_column(String(30), nullable=False)
    weekly_sets: Mapped[int] = mapped_column(Integer, nullable=False)
    priority_score: Mapped[float] = mapped_column(Float, nullable=False)
    recorded_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("ix_vol_alloc_user_date", "user_id", "recorded_date"),)
