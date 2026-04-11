"""add notification_log table

Revision ID: i7d8e9f0a1b2
Revises: h6c7d8e9f0a1
Create Date: 2026-04-11 00:05:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = 'i7d8e9f0a1b2'
down_revision: Union[str, None] = 'h6c7d8e9f0a1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notification_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("notification_type", sa.String(length=50), nullable=False),
        sa.Column("channel", sa.String(length=20), nullable=False, server_default="telegram"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="sent"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_notif_user_id", "notification_log", ["user_id"])
    op.create_index("ix_notif_user_type_sent", "notification_log", ["user_id", "notification_type", "sent_at"])
    op.create_index("ix_notif_sent_at", "notification_log", ["sent_at"])


def downgrade() -> None:
    op.drop_index("ix_notif_sent_at", table_name="notification_log")
    op.drop_index("ix_notif_user_type_sent", table_name="notification_log")
    op.drop_index("ix_notif_user_id", table_name="notification_log")
    op.drop_table("notification_log")
