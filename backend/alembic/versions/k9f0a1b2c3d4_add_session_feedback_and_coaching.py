"""add subjective session feedback + coaching feedback + rep_range_style

Revision ID: k9f0a1b2c3d4
Revises: j8e9f0a1b2c3
Create Date: 2026-04-13 00:00:00.000000

Sprint v4:
- TrainingSession: pump_quality, session_difficulty, joint_comfort (1-3 int, nullable)
- UserProfile: last_meso_exercises (JSONB, nullable)  — exercise rotation
- NEW table coaching_feedback — rule-based coaching messages per check-in
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = 'k9f0a1b2c3d4'
down_revision: Union[str, None] = 'j8e9f0a1b2c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Subjective session feedback columns (1-3 scale, nullable until rated)
    op.add_column("training_sessions", sa.Column("pump_quality", sa.Integer(), nullable=True))
    op.add_column("training_sessions", sa.Column("session_difficulty", sa.Integer(), nullable=True))
    op.add_column("training_sessions", sa.Column("joint_comfort", sa.Integer(), nullable=True))

    # Exercise rotation: previous mesocycle's exercise IDs for variety scoring
    op.add_column(
        "user_profiles",
        sa.Column("last_meso_exercises", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

    # Coaching feedback — stores rule-engine output from each weekly check-in
    op.create_table(
        "coaching_feedback",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("recorded_date", sa.Date(), nullable=False),
        sa.Column(
            "feedback_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("dismissed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_coaching_user_date",
        "coaching_feedback",
        ["user_id", "recorded_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_coaching_user_date", table_name="coaching_feedback")
    op.drop_table("coaching_feedback")
    op.drop_column("user_profiles", "last_meso_exercises")
    op.drop_column("training_sessions", "joint_comfort")
    op.drop_column("training_sessions", "session_difficulty")
    op.drop_column("training_sessions", "pump_quality")
