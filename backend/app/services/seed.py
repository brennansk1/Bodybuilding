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
    """Insert exercises from the curated competitive bodybuilding database if table is empty."""
    result = await db.execute(select(func.count()).select_from(Exercise))
    if result.scalar() > 0:
        return 0  # already seeded

    from app.constants.exercises_curated import CURATED_EXERCISES

    inserted = 0
    for ex in CURATED_EXERCISES:
        record = Exercise(
            name=ex.name[:100],
            primary_muscle=ex.primary_muscle,
            secondary_muscles=json.dumps(ex.secondary_muscles) if ex.secondary_muscles else None,
            movement_pattern=ex.movement_pattern[:30],
            equipment=ex.equipment[:30],
            biomechanical_efficiency=ex.efficiency,
            fatigue_ratio=ex.fatigue_ratio,
            load_type=ex.load_type[:20] if ex.load_type else None,
        )
        db.add(record)
        inserted += 1

    await db.flush()
    logger.info(f"Seeded {inserted} exercises (curated competitive bodybuilding DB)")
    return inserted


# ---------------------------------------------------------------------------
# Run all seeds
# ---------------------------------------------------------------------------

async def run_all_seeds(db: AsyncSession) -> dict:
    exercises = await seed_exercises(db)
    ingredients = await seed_ingredients(db)
    return {"exercises": exercises, "ingredients": ingredients}
