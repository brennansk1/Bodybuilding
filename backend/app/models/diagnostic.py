from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Index, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class LCSALog(Base):
    __tablename__ = "lcsa_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    recorded_date: Mapped[date] = mapped_column(Date, nullable=False)
    site_values: Mapped[dict] = mapped_column(JSONB, nullable=False)  # {site: lcsa_value}
    total_lcsa: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="lcsa_logs")

    __table_args__ = (Index("ix_lcsa_user_date", "user_id", "recorded_date"),)


class PDSLog(Base):
    __tablename__ = "pds_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    recorded_date: Mapped[date] = mapped_column(Date, nullable=False)
    pds_score: Mapped[float] = mapped_column(Float, nullable=False)
    component_scores: Mapped[dict] = mapped_column(JSONB, nullable=False)  # {component: score}
    tier: Mapped[str | None] = mapped_column(nullable=True)  # novice/intermediate/advanced/elite
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="pds_logs")

    __table_args__ = (Index("ix_pds_user_date", "user_id", "recorded_date"),)


class HQILog(Base):
    __tablename__ = "hqi_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    recorded_date: Mapped[date] = mapped_column(Date, nullable=False)
    site_scores: Mapped[dict] = mapped_column(JSONB, nullable=False)  # {site: hqi_score 0-100}
    overall_hqi: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="hqi_logs")

    __table_args__ = (Index("ix_hqi_user_date", "user_id", "recorded_date"),)
