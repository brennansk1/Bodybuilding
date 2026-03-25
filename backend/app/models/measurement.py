from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class BodyWeightLog(Base):
    __tablename__ = "body_weight_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    weight_kg: Mapped[float] = mapped_column(Float, nullable=False)
    recorded_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="body_weight_logs")

    __table_args__ = (Index("ix_bw_user_date", "user_id", "recorded_date"),)


class TapeMeasurement(Base):
    __tablename__ = "tape_measurements"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    recorded_date: Mapped[date] = mapped_column(Date, nullable=False)
    # Standard girth sites (cm)
    neck: Mapped[float | None] = mapped_column(Float, nullable=True)
    shoulders: Mapped[float | None] = mapped_column(Float, nullable=True)
    chest: Mapped[float | None] = mapped_column(Float, nullable=True)
    left_bicep: Mapped[float | None] = mapped_column(Float, nullable=True)
    right_bicep: Mapped[float | None] = mapped_column(Float, nullable=True)
    left_forearm: Mapped[float | None] = mapped_column(Float, nullable=True)
    right_forearm: Mapped[float | None] = mapped_column(Float, nullable=True)
    waist: Mapped[float | None] = mapped_column(Float, nullable=True)
    hips: Mapped[float | None] = mapped_column(Float, nullable=True)
    left_thigh: Mapped[float | None] = mapped_column(Float, nullable=True)
    right_thigh: Mapped[float | None] = mapped_column(Float, nullable=True)
    left_calf: Mapped[float | None] = mapped_column(Float, nullable=True)
    right_calf: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Advanced / isolation sites (cm)
    chest_relaxed: Mapped[float | None] = mapped_column(Float, nullable=True)
    chest_lat_spread: Mapped[float | None] = mapped_column(Float, nullable=True)
    back_width: Mapped[float | None] = mapped_column(Float, nullable=True)
    left_proximal_thigh: Mapped[float | None] = mapped_column(Float, nullable=True)
    right_proximal_thigh: Mapped[float | None] = mapped_column(Float, nullable=True)
    left_distal_thigh: Mapped[float | None] = mapped_column(Float, nullable=True)
    right_distal_thigh: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="tape_measurements")

    __table_args__ = (Index("ix_tape_user_date", "user_id", "recorded_date"),)


class SkinfoldMeasurement(Base):
    __tablename__ = "skinfold_measurements"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    recorded_date: Mapped[date] = mapped_column(Date, nullable=False)
    # 7-site Jackson-Pollock (mm)
    chest: Mapped[float | None] = mapped_column(Float, nullable=True)
    midaxillary: Mapped[float | None] = mapped_column(Float, nullable=True)
    tricep: Mapped[float | None] = mapped_column(Float, nullable=True)
    subscapular: Mapped[float | None] = mapped_column(Float, nullable=True)
    abdominal: Mapped[float | None] = mapped_column(Float, nullable=True)
    suprailiac: Mapped[float | None] = mapped_column(Float, nullable=True)
    thigh: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Additional sites for Parrillo 9-site + site-specific lean girth
    bicep: Mapped[float | None] = mapped_column(Float, nullable=True)
    lower_back: Mapped[float | None] = mapped_column(Float, nullable=True)
    calf: Mapped[float | None] = mapped_column(Float, nullable=True)
    body_fat_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="skinfold_measurements")

    __table_args__ = (Index("ix_skinfold_user_date", "user_id", "recorded_date"),)
