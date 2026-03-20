"""add advanced measurement columns

Revision ID: c047a75d24f4
Revises: 7850f1556da9
Create Date: 2026-03-19 21:00:24.930653

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c047a75d24f4'
down_revision: Union[str, None] = '7850f1556da9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Tape: advanced / isolation girth sites
    op.add_column('tape_measurements', sa.Column('chest_relaxed', sa.Float(), nullable=True))
    op.add_column('tape_measurements', sa.Column('chest_lat_spread', sa.Float(), nullable=True))
    op.add_column('tape_measurements', sa.Column('back_width', sa.Float(), nullable=True))
    op.add_column('tape_measurements', sa.Column('left_proximal_thigh', sa.Float(), nullable=True))
    op.add_column('tape_measurements', sa.Column('right_proximal_thigh', sa.Float(), nullable=True))
    op.add_column('tape_measurements', sa.Column('left_distal_thigh', sa.Float(), nullable=True))
    op.add_column('tape_measurements', sa.Column('right_distal_thigh', sa.Float(), nullable=True))
    # Skinfold: additional sites for Parrillo 9-site + site-specific lean girth
    op.add_column('skinfold_measurements', sa.Column('bicep', sa.Float(), nullable=True))
    op.add_column('skinfold_measurements', sa.Column('lower_back', sa.Float(), nullable=True))
    op.add_column('skinfold_measurements', sa.Column('calf', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('tape_measurements', 'right_distal_thigh')
    op.drop_column('tape_measurements', 'left_distal_thigh')
    op.drop_column('tape_measurements', 'right_proximal_thigh')
    op.drop_column('tape_measurements', 'left_proximal_thigh')
    op.drop_column('tape_measurements', 'back_width')
    op.drop_column('tape_measurements', 'chest_lat_spread')
    op.drop_column('tape_measurements', 'chest_relaxed')
    op.drop_column('skinfold_measurements', 'calf')
    op.drop_column('skinfold_measurements', 'lower_back')
    op.drop_column('skinfold_measurements', 'bicep')
