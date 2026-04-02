"""block0 schema additions — rest_seconds, is_fst7, load_type, program_start_date, started_at, completed_at, dup_profile

Revision ID: a1b2c3d4e5f6
Revises: d6e44051452a
Create Date: 2026-04-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'd6e44051452a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # TrainingSet: rest timer + FST-7 flag
    op.add_column('training_sets', sa.Column('rest_seconds', sa.Integer(), nullable=True))
    op.add_column('training_sets', sa.Column('is_fst7', sa.Boolean(), server_default=sa.text('false'), nullable=False))

    # Exercise: load_type for resistance progression
    op.add_column('exercises', sa.Column('load_type', sa.String(20), nullable=True))

    # UserProfile: program start date
    op.add_column('user_profiles', sa.Column('program_start_date', sa.Date(), nullable=True))

    # TrainingSession: session duration tracking + DUP profile
    op.add_column('training_sessions', sa.Column('started_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('training_sessions', sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('training_sessions', sa.Column('dup_profile', sa.String(10), nullable=True))


def downgrade() -> None:
    op.drop_column('training_sessions', 'dup_profile')
    op.drop_column('training_sessions', 'completed_at')
    op.drop_column('training_sessions', 'started_at')
    op.drop_column('user_profiles', 'program_start_date')
    op.drop_column('exercises', 'load_type')
    op.drop_column('training_sets', 'is_fst7')
    op.drop_column('training_sets', 'rest_seconds')
