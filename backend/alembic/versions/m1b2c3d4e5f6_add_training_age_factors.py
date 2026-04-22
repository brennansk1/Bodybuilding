"""add training-age factor columns (v2 Sprint 4)

Revision ID: m1b2c3d4e5f6
Revises: l0a1b2c3d4e5
Create Date: 2026-04-21 00:00:00.000000

Three nullable float columns on user_profiles for training-age correction:
  * training_consistency_factor — 1.0 = 4+ sessions/wk, 0.2 = sporadic
  * training_intensity_factor   — 1.0 = near-failure, 0.4 = light
  * training_programming_factor — 1.0 = periodized, 0.4 = random

When null, readiness.estimate_cycles_to_tier falls back to documented
priors (0.85 / 0.75 / 0.70) via engine1.training_age. No data backfill
required — every existing row keeps its behavior.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "m1b2c3d4e5f6"
down_revision: Union[str, None] = "l0a1b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("user_profiles") as batch:
        batch.add_column(sa.Column("training_consistency_factor", sa.Float(), nullable=True))
        batch.add_column(sa.Column("training_intensity_factor",   sa.Float(), nullable=True))
        batch.add_column(sa.Column("training_programming_factor", sa.Float(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("user_profiles") as batch:
        batch.drop_column("training_programming_factor")
        batch.drop_column("training_intensity_factor")
        batch.drop_column("training_consistency_factor")
