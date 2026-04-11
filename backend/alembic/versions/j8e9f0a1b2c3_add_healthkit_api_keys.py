"""add healthkit_api_keys table

Revision ID: j8e9f0a1b2c3
Revises: i7d8e9f0a1b2
Create Date: 2026-04-11 00:10:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = 'j8e9f0a1b2c3'
down_revision: Union[str, None] = 'i7d8e9f0a1b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "healthkit_api_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("api_key_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("key_prefix", sa.String(length=16), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False, server_default="iPhone Shortcut"),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_hkkey_user_id", "healthkit_api_keys", ["user_id"])
    op.create_index("ix_hkkey_api_key_hash", "healthkit_api_keys", ["api_key_hash"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_hkkey_api_key_hash", table_name="healthkit_api_keys")
    op.drop_index("ix_hkkey_user_id", table_name="healthkit_api_keys")
    op.drop_table("healthkit_api_keys")
