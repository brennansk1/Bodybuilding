"""add telegram_bot_token to user_profiles

Revision ID: h6c7d8e9f0a1
Revises: g5b6c7d8e9f0
Create Date: 2026-04-11 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'h6c7d8e9f0a1'
down_revision: Union[str, None] = 'g5b6c7d8e9f0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user_profiles",
        sa.Column("telegram_bot_token", sa.String(length=256), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_profiles", "telegram_bot_token")
