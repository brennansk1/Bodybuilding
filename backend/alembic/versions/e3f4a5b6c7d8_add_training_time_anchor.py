"""add training time anchor

Revision ID: e3f4a5b6c7d8
Revises: b2c3d4e5f6a7
Create Date: 2026-04-10 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'e3f4a5b6c7d8'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user_profiles",
        sa.Column("training_end_time", sa.String(length=5), nullable=True),
    )
    op.add_column(
        "user_profiles",
        sa.Column(
            "training_time_anchor",
            sa.String(length=10),
            nullable=True,
            server_default="start",
        ),
    )
    # Backfill existing rows with the default so subsequent reads are stable.
    op.execute("UPDATE user_profiles SET training_time_anchor = 'start' WHERE training_time_anchor IS NULL")


def downgrade() -> None:
    op.drop_column("user_profiles", "training_time_anchor")
    op.drop_column("user_profiles", "training_end_time")
