"""V3 foundation — profile overrides, tier tracking, checkpoint snapshots, progress_photos

Revision ID: p4e5f6g7h8i9
Revises: o3d4e5f6g7h8
Create Date: 2026-04-22 00:00:00.000000

Consolidated migration for V3 daily-use + tier-aware overhaul:

1. UserProfile adds:
   - nutrition_mode_override (str)       — manual "bulk"/"cut"/"maintain"/"pct_recovery" or null (auto)
   - pct_mode_active (bool)              — blocks cuts; holds maintenance ±5%
   - structural_priority_muscles (JSONB) — persistent specialization tags
   - current_achieved_tier (int)         — distinct from target_tier; written by checkpoint eval

2. PPMCheckpoint adds:
   - macros_snapshot  (JSONB) — full macro prescription at checkpoint time
   - training_snapshot (JSONB) — split + volume allocation at checkpoint
   - volume_snapshot  (JSONB) — per-muscle actual vs prescribed sets

3. New table: progress_photos
   - user_id, date, pose_type, storage_url, notes, created_at
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision: str = "p4e5f6g7h8i9"
down_revision: Union[str, None] = "o3d4e5f6g7h8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Profile extensions
    with op.batch_alter_table("user_profiles") as batch:
        batch.add_column(sa.Column("nutrition_mode_override", sa.String(length=24), nullable=True))
        batch.add_column(sa.Column("pct_mode_active", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column("structural_priority_muscles", JSONB, nullable=True))
        batch.add_column(sa.Column("current_achieved_tier", sa.Integer(), nullable=True))

    # 2. Checkpoint snapshot extensions
    with op.batch_alter_table("ppm_checkpoints") as batch:
        batch.add_column(sa.Column("macros_snapshot", JSONB, nullable=True))
        batch.add_column(sa.Column("training_snapshot", JSONB, nullable=True))
        batch.add_column(sa.Column("volume_snapshot", JSONB, nullable=True))

    # 3. progress_photos table
    op.create_table(
        "progress_photos",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("photo_date", sa.Date(), nullable=False),
        sa.Column("pose_type", sa.String(length=32), nullable=False),
        sa.Column("storage_url", sa.String(length=512), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_progress_photos_user_date", "progress_photos", ["user_id", "photo_date"])


def downgrade() -> None:
    op.drop_index("ix_progress_photos_user_date", table_name="progress_photos")
    op.drop_table("progress_photos")

    with op.batch_alter_table("ppm_checkpoints") as batch:
        batch.drop_column("volume_snapshot")
        batch.drop_column("training_snapshot")
        batch.drop_column("macros_snapshot")

    with op.batch_alter_table("user_profiles") as batch:
        batch.drop_column("current_achieved_tier")
        batch.drop_column("structural_priority_muscles")
        batch.drop_column("pct_mode_active")
        batch.drop_column("nutrition_mode_override")
