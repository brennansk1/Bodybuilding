from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class NotificationLog(Base):
    """
    Append-only log of notifications dispatched to users. Used as an
    idempotency gate so the cron-driven dispatcher doesn't re-send the
    same notification twice in a window, and as an audit trail for
    debugging why something did (or didn't) arrive.
    """
    __tablename__ = "notification_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True,
    )
    # Notification type key — one of tg.NOTIFICATION_KEYS keys.
    notification_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # Which channel fired this (currently only telegram; sms/push later).
    channel: Mapped[str] = mapped_column(String(20), default="telegram")
    status: Mapped[str] = mapped_column(String(20), default="sent")  # sent | failed
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True,
    )

    __table_args__ = (
        Index("ix_notif_user_type_sent", "user_id", "notification_type", "sent_at"),
    )
