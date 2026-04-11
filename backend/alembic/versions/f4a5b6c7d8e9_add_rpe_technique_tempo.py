"""add prescribed rpe, rir, set technique, tempo to training sets

Revision ID: f4a5b6c7d8e9
Revises: e3f4a5b6c7d8
Create Date: 2026-04-10 00:05:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'f4a5b6c7d8e9'
down_revision: Union[str, None] = 'e3f4a5b6c7d8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("training_sets", sa.Column("prescribed_rpe", sa.Float(), nullable=True))
    op.add_column("training_sets", sa.Column("prescribed_rir", sa.Integer(), nullable=True))
    op.add_column("training_sets", sa.Column("set_technique", sa.String(length=30), nullable=True))
    op.add_column("training_sets", sa.Column("tempo", sa.String(length=15), nullable=True))


def downgrade() -> None:
    op.drop_column("training_sets", "tempo")
    op.drop_column("training_sets", "set_technique")
    op.drop_column("training_sets", "prescribed_rir")
    op.drop_column("training_sets", "prescribed_rpe")
