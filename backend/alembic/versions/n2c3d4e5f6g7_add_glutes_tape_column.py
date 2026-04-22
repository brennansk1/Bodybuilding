"""add glutes column to tape_measurements (v2 post-sprint UI pass)

Revision ID: n2c3d4e5f6g7
Revises: m1b2c3d4e5f6
Create Date: 2026-04-21 00:00:00.000000

V2.S3 elevated `glutes` to a first-class HQI visibility site across all 7
divisions (full weight for Bikini / Wellness / Womens Physique; 0.85 for
Open / Classic; 0.50 for Men's Physique). The matching tape measurement
column was never added — this migration fixes that. Nullable float; no
backfill required. Historical rows keep glutes NULL.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "n2c3d4e5f6g7"
down_revision: Union[str, None] = "m1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("tape_measurements") as batch:
        batch.add_column(sa.Column("glutes", sa.Float(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("tape_measurements") as batch:
        batch.drop_column("glutes")
