"""add sleep_hours, stress/mood/energy, hr_component, stress_component to recovery tables

Revision ID: g5b6c7d8e9f0
Revises: f4a5b6c7d8e9
Create Date: 2026-04-10 00:10:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'g5b6c7d8e9f0'
down_revision: Union[str, None] = 'f4a5b6c7d8e9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # HRVLog expansion
    op.add_column("hrv_log", sa.Column("sleep_hours", sa.Float(), nullable=True))
    op.add_column("hrv_log", sa.Column("stress_score", sa.Float(), nullable=True))
    op.add_column("hrv_log", sa.Column("mood_score", sa.Float(), nullable=True))
    op.add_column("hrv_log", sa.Column("energy_score", sa.Float(), nullable=True))
    # ARILog expansion
    op.add_column("ari_log", sa.Column("hr_component", sa.Float(), nullable=True))
    op.add_column("ari_log", sa.Column("stress_component", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("ari_log", "stress_component")
    op.drop_column("ari_log", "hr_component")
    op.drop_column("hrv_log", "energy_score")
    op.drop_column("hrv_log", "mood_score")
    op.drop_column("hrv_log", "stress_score")
    op.drop_column("hrv_log", "sleep_hours")
