"""add PPM (Perpetual Progression Mode) + training-status profile fields

Revision ID: l0a1b2c3d4e5
Revises: k9f0a1b2c3d4
Create Date: 2026-04-21 00:00:00.000000

Perpetual Progression Mode feature + Classic Physique audit pass:
- UserProfile:
    - training_status (natural|enhanced, default 'natural')
    - ppm_enabled (bool, default FALSE)
    - target_tier (1–5, nullable)
    - current_cycle_number (default 0)
    - current_cycle_start_date (nullable)
    - current_cycle_week (default 1)
    - cycle_focus_muscles (JSONB nullable)
- NEW table `ppm_checkpoints` — per-cycle readiness snapshots.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "l0a1b2c3d4e5"
down_revision: Union[str, None] = "k9f0a1b2c3d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── UserProfile additions ──────────────────────────────────────────────
    op.add_column(
        "user_profiles",
        sa.Column(
            "training_status", sa.String(16),
            nullable=False, server_default="natural",
        ),
    )
    op.add_column(
        "user_profiles",
        sa.Column(
            "ppm_enabled", sa.Boolean(),
            nullable=False, server_default=sa.text("FALSE"),
        ),
    )
    op.add_column(
        "user_profiles",
        sa.Column("target_tier", sa.Integer(), nullable=True),
    )
    op.add_column(
        "user_profiles",
        sa.Column(
            "current_cycle_number", sa.Integer(),
            nullable=False, server_default="0",
        ),
    )
    op.add_column(
        "user_profiles",
        sa.Column("current_cycle_start_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "user_profiles",
        sa.Column(
            "current_cycle_week", sa.Integer(),
            nullable=False, server_default="1",
        ),
    )
    op.add_column(
        "user_profiles",
        sa.Column(
            "cycle_focus_muscles",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )

    # ── New table: ppm_checkpoints ─────────────────────────────────────────
    op.create_table(
        "ppm_checkpoints",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("cycle_number", sa.Integer(), nullable=False),
        sa.Column("checkpoint_date", sa.Date(), nullable=False),
        sa.Column("body_weight_kg", sa.Float(), nullable=True),
        sa.Column("bf_pct", sa.Float(), nullable=True),
        sa.Column("ffmi", sa.Float(), nullable=True),
        sa.Column("shoulder_waist_ratio", sa.Float(), nullable=True),
        sa.Column("chest_waist_ratio", sa.Float(), nullable=True),
        sa.Column("arm_calf_neck_parity", sa.Float(), nullable=True),
        sa.Column("hqi_score", sa.Float(), nullable=True),
        sa.Column("weight_cap_pct", sa.Float(), nullable=True),
        sa.Column("readiness_state", sa.String(32), nullable=False),
        sa.Column("limiting_factor", sa.String(64), nullable=True),
        sa.Column("cycle_focus", sa.String(128), nullable=True),
        sa.Column(
            "measurements_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_ppm_checkpoints_user_cycle",
        "ppm_checkpoints",
        ["user_id", "cycle_number"],
    )


def downgrade() -> None:
    op.drop_index("ix_ppm_checkpoints_user_cycle", table_name="ppm_checkpoints")
    op.drop_table("ppm_checkpoints")
    op.drop_column("user_profiles", "cycle_focus_muscles")
    op.drop_column("user_profiles", "current_cycle_week")
    op.drop_column("user_profiles", "current_cycle_start_date")
    op.drop_column("user_profiles", "current_cycle_number")
    op.drop_column("user_profiles", "target_tier")
    op.drop_column("user_profiles", "ppm_enabled")
    op.drop_column("user_profiles", "training_status")
