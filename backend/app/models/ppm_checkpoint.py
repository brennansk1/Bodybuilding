from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PPMCheckpoint(Base):
    """Perpetual Progression Mode — 14-week improvement cycle checkpoint.

    Captures the athlete's measurable state at the end of each cycle so the
    UI can display a before/after comparison and the readiness engine can
    recompute tier progress.
    """

    __tablename__ = "ppm_checkpoints"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    cycle_number: Mapped[int] = mapped_column(Integer, nullable=False)
    checkpoint_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Readiness metrics
    body_weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    bf_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    ffmi: Mapped[float | None] = mapped_column(Float, nullable=True)
    shoulder_waist_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    chest_waist_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    arm_calf_neck_parity: Mapped[float | None] = mapped_column(Float, nullable=True)
    hqi_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    weight_cap_pct: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Classification outputs
    readiness_state: Mapped[str] = mapped_column(String(32), nullable=False)
    limiting_factor: Mapped[str | None] = mapped_column(String(64), nullable=True)
    cycle_focus: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # Full tape + skinfold snapshot for historical comparison
    measurements_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
