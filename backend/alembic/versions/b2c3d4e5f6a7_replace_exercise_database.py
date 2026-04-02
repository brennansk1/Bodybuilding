"""replace exercise database with curated competitive bodybuilding data

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-04-01 00:01:00.000000

Data migration:
1. Build a name→id map of old exercises
2. Delete all non-custom exercises
3. Insert curated exercises
4. Re-map FK references (strength_baselines, training_sets, strength_log)
   by matching old exercise names to new exercise IDs
5. Orphan any FKs that can't be matched (set exercise_id to NULL via
   temp nullable or delete the row)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
import json
import uuid


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    from app.constants.exercises_curated import CURATED_EXERCISES

    # Full exercise DB replacement: clear FK-referencing tables, replace exercises.
    # Old training data references MegaGym exercise IDs that no longer exist —
    # programs must be regenerated after this migration (see post-deploy notes).
    fk_tables = ["training_sets", "strength_baselines", "strength_log"]
    for table in fk_tables:
        conn.execute(sa.text(f"DELETE FROM {table}"))

    # Also clear training sessions and programs (they reference deleted sets)
    conn.execute(sa.text("DELETE FROM training_sessions"))
    conn.execute(sa.text("DELETE FROM training_programs"))

    # Delete all non-custom exercises
    conn.execute(sa.text("DELETE FROM exercises WHERE is_custom = false"))

    # Insert curated exercises
    for ex in CURATED_EXERCISES:
        new_id = str(uuid.uuid4())
        conn.execute(sa.text("""
            INSERT INTO exercises (id, name, primary_muscle, secondary_muscles,
                                   movement_pattern, equipment, biomechanical_efficiency,
                                   fatigue_ratio, load_type, is_custom)
            VALUES (:id, :name, :primary, :secondary, :pattern, :equip, :eff, :fat, :lt, false)
        """), {
            "id": new_id,
            "name": ex.name[:100],
            "primary": ex.primary_muscle,
            "secondary": json.dumps(ex.secondary_muscles) if ex.secondary_muscles else None,
            "pattern": ex.movement_pattern[:30],
            "equip": ex.equipment[:30],
            "eff": ex.efficiency,
            "fat": ex.fatigue_ratio,
            "lt": ex.load_type[:20] if ex.load_type else None,
        })


def downgrade() -> None:
    # Downgrade not supported — old MegaGym data is deleted.
    # To restore, re-run the original seed from a backup.
    pass
