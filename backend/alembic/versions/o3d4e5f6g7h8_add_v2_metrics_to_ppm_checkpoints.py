"""add illusion_xframe + conditioning_pct columns to ppm_checkpoints

Revision ID: o3d4e5f6g7h8
Revises: n2c3d4e5f6g7
Create Date: 2026-04-21 00:00:00.000000

Follows the V2 audit finding: PPMCheckpoint's V2 metrics (illusion_xframe,
conditioning_pct) were being stored in the `measurements_json` blob, which
prevented the history endpoint from querying them efficiently and made
cross-cycle progression charting awkward. This migration promotes both to
first-class nullable float columns.

Historical rows get NULL; the /ppm/history endpoint already falls back to
extracting from measurements_json when the top-level columns are NULL
(see app.routers.ppm.history::_extract_v2_metrics).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "o3d4e5f6g7h8"
down_revision: Union[str, None] = "n2c3d4e5f6g7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("ppm_checkpoints") as batch:
        batch.add_column(sa.Column("illusion_xframe",  sa.Float(), nullable=True))
        batch.add_column(sa.Column("conditioning_pct", sa.Float(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("ppm_checkpoints") as batch:
        batch.drop_column("conditioning_pct")
        batch.drop_column("illusion_xframe")
