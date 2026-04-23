from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


POSE_TYPES = (
    "front_relaxed",
    "front_dbl_biceps",
    "side_chest_left",
    "side_chest_right",
    "back_dbl_biceps",
    "back_lat_spread",
    "abs_thigh",
    "side_triceps_left",
    "side_triceps_right",
    "most_muscular",
    "free_form",
)


class ProgressPhoto(Base):
    """Progress photo metadata. Storage URL points to external object store
    (S3/Cloudflare R2/etc.) or app-local media directory. Pose type is
    required so overlay comparison aligns like-for-like shots."""

    __tablename__ = "progress_photos"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    photo_date: Mapped[date] = mapped_column(Date, nullable=False)
    pose_type: Mapped[str] = mapped_column(String(32), nullable=False)
    storage_url: Mapped[str] = mapped_column(String(512), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
