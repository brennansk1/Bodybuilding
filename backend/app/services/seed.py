"""
Database seeding service.

Inserts exercises and ingredients on first startup if tables are empty.
Safe to call every startup — checks before inserting.
"""
import json
import logging

from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.training import Exercise
from app.models.nutrition import IngredientMaster

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Ingredient category inference
# ---------------------------------------------------------------------------

def _infer_category(name: str, protein: float, carbs: float, fat: float) -> str:
    name_l = name.lower()
    if any(w in name_l for w in ["chicken", "beef", "pork", "turkey", "lamb", "bison",
                                  "egg", "tuna", "salmon", "cod", "shrimp", "tilapia",
                                  "whey", "casein", "protein", "steak", "ground beef"]):
        return "protein"
    if any(w in name_l for w in ["rice", "oat", "bread", "pasta", "potato", "quinoa",
                                  "corn", "wheat", "barley", "cereal", "tortilla"]):
        return "carb"
    if any(w in name_l for w in ["oil", "butter", "nut", "almond", "walnut", "peanut",
                                  "avocado", "coconut", "lard", "cheese", "cream"]):
        return "fat"
    if any(w in name_l for w in ["broccoli", "spinach", "kale", "lettuce", "cabbage",
                                  "carrot", "celery", "cucumber", "pepper", "tomato",
                                  "asparagus", "mushroom", "onion", "garlic", "green bean"]):
        return "vegetable"
    if any(w in name_l for w in ["apple", "banana", "orange", "berry", "grape", "mango",
                                  "pineapple", "peach", "pear", "strawberry", "blueberry"]):
        return "fruit"
    # Macro-based fallback
    if protein >= 15:
        return "protein"
    if carbs >= 30:
        return "carb"
    if fat >= 15:
        return "fat"
    return "whole_food"


def _is_peri_workout(name: str, carbs: float) -> bool:
    """Mark simple carb sources as peri-workout friendly."""
    name_l = name.lower()
    return (
        carbs > 15
        and any(w in name_l for w in ["rice", "oat", "banana", "potato", "bread",
                                       "pasta", "cereal", "corn", "sweet potato"])
    )


# ---------------------------------------------------------------------------
# Seed ingredients
# ---------------------------------------------------------------------------

async def seed_ingredients(db: AsyncSession) -> int:
    """Insert ingredients from USDA seed data if table is empty."""
    result = await db.execute(select(func.count()).select_from(IngredientMaster))
    if result.scalar() > 0:
        return 0  # already seeded

    try:
        from app.constants.ingredients import INGREDIENT_SEED
    except ImportError:
        logger.warning("ingredients.py not found — skipping ingredient seeding")
        return 0

    inserted = 0
    for name, cal, prot, carb, fat, fib in INGREDIENT_SEED:
        if not name or cal <= 0:
            continue
        category = _infer_category(name, prot, carb, fat)
        peri = _is_peri_workout(name, carb)
        ingredient = IngredientMaster(
            name=name[:150],
            category=category,
            calories_per_100g=cal,
            protein_per_100g=prot,
            carbs_per_100g=carb,
            fat_per_100g=fat,
            fiber_per_100g=fib,
            is_peri_workout=peri,
        )
        db.add(ingredient)
        inserted += 1

    await db.flush()
    logger.info(f"Seeded {inserted} ingredients")
    return inserted


# ---------------------------------------------------------------------------
# Seed exercises
# ---------------------------------------------------------------------------

async def seed_exercises(db: AsyncSession) -> int:
    """Insert exercises from dataset if table is empty."""
    result = await db.execute(select(func.count()).select_from(Exercise))
    if result.scalar() > 0:
        return 0  # already seeded

    try:
        from app.constants.exercises_full import EXERCISE_DATABASE
    except ImportError:
        # Fall back to the original hand-curated list
        try:
            from app.constants.exercises import SEED_EXERCISES
            inserted = 0
            for name, primary, secondary, equipment, pattern, efficiency, fatigue in SEED_EXERCISES:
                ex = Exercise(
                    name=name,
                    primary_muscle=primary,
                    secondary_muscles=json.dumps(secondary) if secondary else None,
                    movement_pattern=pattern,
                    equipment=equipment,
                    biomechanical_efficiency=efficiency,
                    fatigue_ratio=fatigue,
                )
                db.add(ex)
                inserted += 1
            await db.flush()
            logger.info(f"Seeded {inserted} exercises (legacy list)")
            return inserted
        except ImportError:
            logger.warning("No exercise data found — skipping exercise seeding")
            return 0

    # Cap per muscle group to avoid bloat (keep highest-efficiency first)
    from collections import defaultdict
    MAX_PER_MUSCLE = 25

    by_muscle = defaultdict(list)
    for ex in EXERCISE_DATABASE:
        by_muscle[ex.primary_muscle].append(ex)

    inserted = 0
    seen_names = set()

    for muscle, exs in by_muscle.items():
        # Sort: barbell > dumbbell > cable > machine; then by efficiency desc
        EQUIPMENT_PRIORITY = {"barbell": 0, "dumbbell": 1, "cable": 2,
                              "e_z_curl_bar": 3, "machine": 4, "body_only": 5,
                              "kettlebells": 6, "bands": 7, "other": 8}
        exs_sorted = sorted(exs,
                            key=lambda e: (EQUIPMENT_PRIORITY.get(e.equipment, 9),
                                           -e.efficiency))
        for ex in exs_sorted[:MAX_PER_MUSCLE]:
            if ex.name.lower() in seen_names:
                continue
            seen_names.add(ex.name.lower())
            record = Exercise(
                name=ex.name[:100],
                primary_muscle=ex.primary_muscle,
                secondary_muscles=json.dumps(ex.secondary_muscles) if ex.secondary_muscles else None,
                movement_pattern=ex.movement_pattern[:30],
                equipment=ex.equipment[:30],
                biomechanical_efficiency=ex.efficiency,
                fatigue_ratio=ex.fatigue_ratio,
            )
            db.add(record)
            inserted += 1

    await db.flush()
    logger.info(f"Seeded {inserted} exercises (from MegaGym dataset)")
    return inserted


# ---------------------------------------------------------------------------
# Run all seeds
# ---------------------------------------------------------------------------

async def run_all_seeds(db: AsyncSession) -> dict:
    exercises = await seed_exercises(db)
    ingredients = await seed_ingredients(db)
    return {"exercises": exercises, "ingredients": ingredients}
