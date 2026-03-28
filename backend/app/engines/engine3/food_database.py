"""
Curated bodybuilding food database.

Every food item a bodybuilding meal plan can draw from lives here.
Macros are per 100 g (raw/uncooked weight unless noted).
Phase tags control availability:  "all" = always available,
"prep" = cut/peak only, "bulk" = bulk/lean_bulk/offseason, etc.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class FoodItem:
    name: str
    category: str  # protein, carb, fat, vegetable, fruit
    protein: float  # g per 100g
    carbs: float    # g per 100g
    fat: float      # g per 100g
    calories: float  # kcal per 100g
    typical_serving_g: float = 150.0
    min_serving_g: float = 50.0
    max_serving_g: float = 400.0
    peri_workout: bool = False  # suitable for pre/post workout
    phase_tags: tuple = ("all",)  # all, prep, bulk, maintain
    exclude_tags: tuple = ()  # dietary tags that exclude this food
    # e.g. ("vegetarian",) means excluded if user is vegetarian
    meal_affinity: tuple = ("any",)  # "breakfast", "lunch_dinner", "snack", "any"


# ─── Protein Sources ─────────────────────────────────────────────────────────

PROTEINS = [
    # Lean poultry
    FoodItem("Chicken Breast", "protein", 31.0, 0.0, 3.6, 165, 170, 100, 300,
             peri_workout=True, phase_tags=("all",), exclude_tags=("vegetarian", "vegan")),
    FoodItem("Turkey Breast", "protein", 29.0, 0.0, 1.0, 135, 170, 100, 300,
             peri_workout=True, phase_tags=("all",), exclude_tags=("vegetarian", "vegan")),
    FoodItem("Ground Turkey (93/7)", "protein", 27.0, 0.0, 7.0, 170, 150, 100, 250,
             phase_tags=("all",), exclude_tags=("vegetarian", "vegan")),

    # Beef
    FoodItem("Lean Ground Beef (96/4)", "protein", 26.0, 0.0, 4.0, 152, 150, 100, 250,
             phase_tags=("all",), exclude_tags=("vegetarian", "vegan")),
    FoodItem("Lean Ground Beef (93/7)", "protein", 26.0, 0.0, 7.0, 170, 150, 100, 250,
             phase_tags=("bulk", "maintain"), exclude_tags=("vegetarian", "vegan")),
    FoodItem("Sirloin Steak", "protein", 27.0, 0.0, 8.0, 183, 170, 120, 250,
             phase_tags=("bulk", "maintain"), exclude_tags=("vegetarian", "vegan")),
    FoodItem("Flank Steak", "protein", 27.0, 0.0, 5.0, 158, 170, 120, 250,
             phase_tags=("all",), exclude_tags=("vegetarian", "vegan")),
    FoodItem("Eye of Round", "protein", 28.0, 0.0, 4.0, 150, 170, 120, 250,
             phase_tags=("all",), exclude_tags=("vegetarian", "vegan")),

    # Pork
    FoodItem("Pork Tenderloin", "protein", 26.0, 0.0, 3.5, 143, 150, 100, 250,
             phase_tags=("all",), exclude_tags=("vegetarian", "vegan", "no_pork", "halal", "kosher")),

    # Fish & Seafood
    FoodItem("Tilapia", "protein", 26.0, 0.0, 2.0, 128, 170, 100, 250,
             peri_workout=True, phase_tags=("all",), exclude_tags=("vegetarian", "vegan")),
    FoodItem("Cod", "protein", 23.0, 0.0, 1.0, 105, 170, 100, 250,
             peri_workout=True, phase_tags=("all",), exclude_tags=("vegetarian", "vegan")),
    FoodItem("Halibut", "protein", 23.0, 0.0, 1.5, 111, 170, 100, 250,
             peri_workout=True, phase_tags=("all",), exclude_tags=("vegetarian", "vegan")),
    FoodItem("Salmon", "protein", 20.0, 0.0, 13.0, 208, 170, 100, 250,
             phase_tags=("bulk", "maintain"), exclude_tags=("vegetarian", "vegan")),
    FoodItem("Canned Tuna (in water)", "protein", 26.0, 0.0, 1.0, 116, 130, 80, 200,
             phase_tags=("all",), exclude_tags=("vegetarian", "vegan")),
    FoodItem("Shrimp", "protein", 24.0, 0.0, 0.3, 99, 150, 80, 250,
             peri_workout=True, phase_tags=("all",), exclude_tags=("vegetarian", "vegan", "no_shellfish")),

    # Dairy & Eggs
    FoodItem("Whole Eggs", "protein", 13.0, 1.1, 11.0, 155, 100, 50, 200,
             phase_tags=("bulk", "maintain"), exclude_tags=("vegan", "dairy_free"),
             meal_affinity=("breakfast", "any")),
    FoodItem("Egg Whites", "protein", 11.0, 0.7, 0.2, 52, 150, 80, 300,
             peri_workout=True, phase_tags=("all",), exclude_tags=("vegan",),
             meal_affinity=("breakfast", "any")),
    FoodItem("Greek Yogurt (nonfat)", "protein", 10.0, 3.6, 0.7, 59, 200, 100, 300,
             phase_tags=("all",), exclude_tags=("vegan", "dairy_free"),
             meal_affinity=("breakfast", "snack")),
    FoodItem("Cottage Cheese (low-fat)", "protein", 11.0, 3.4, 1.0, 72, 200, 100, 300,
             phase_tags=("all",), exclude_tags=("vegan", "dairy_free"),
             meal_affinity=("breakfast", "snack")),

    # Plant-based
    FoodItem("Tofu (firm)", "protein", 17.0, 2.0, 9.0, 144, 150, 100, 250,
             phase_tags=("all",), exclude_tags=()),
    FoodItem("Tempeh", "protein", 19.0, 9.0, 11.0, 192, 130, 80, 200,
             phase_tags=("all",), exclude_tags=()),
    FoodItem("Seitan", "protein", 25.0, 4.0, 1.0, 130, 130, 80, 200,
             phase_tags=("all",), exclude_tags=("gluten_free",)),
    FoodItem("Edamame", "protein", 11.0, 9.0, 5.0, 121, 100, 60, 200,
             phase_tags=("all",), exclude_tags=()),
]

# ─── Carbohydrate Sources ────────────────────────────────────────────────────

CARBS = [
    # Complex / slow-digesting
    FoodItem("Oats (rolled)", "carb", 13.0, 68.0, 7.0, 389, 80, 40, 150,
             phase_tags=("all",), exclude_tags=(),
             meal_affinity=("breakfast", "snack")),
    FoodItem("Sweet Potato", "carb", 1.6, 20.0, 0.1, 86, 200, 100, 350,
             phase_tags=("all",), exclude_tags=(),
             meal_affinity=("lunch_dinner",)),
    FoodItem("Brown Rice (cooked)", "carb", 2.6, 23.0, 0.9, 111, 200, 100, 350,
             peri_workout=True, phase_tags=("all",), exclude_tags=(),
             meal_affinity=("lunch_dinner", "any")),
    FoodItem("Quinoa (cooked)", "carb", 4.4, 21.0, 1.9, 120, 180, 100, 300,
             phase_tags=("all",), exclude_tags=(),
             meal_affinity=("lunch_dinner",)),
    FoodItem("Cream of Rice (dry)", "carb", 7.0, 79.0, 0.5, 358, 50, 30, 100,
             peri_workout=True, phase_tags=("all",), exclude_tags=(),
             meal_affinity=("breakfast", "snack")),
    FoodItem("Ezekiel Bread", "carb", 8.0, 36.0, 1.0, 200, 60, 30, 120,
             phase_tags=("all",), exclude_tags=("gluten_free",),
             meal_affinity=("breakfast", "snack")),

    # Simple / fast-digesting (peri-workout)
    FoodItem("White Rice (cooked)", "carb", 2.7, 28.0, 0.3, 130, 200, 100, 400,
             peri_workout=True, phase_tags=("all",), exclude_tags=(),
             meal_affinity=("lunch_dinner", "any")),
    FoodItem("Jasmine Rice (cooked)", "carb", 2.7, 28.0, 0.3, 130, 200, 100, 400,
             peri_workout=True, phase_tags=("all",), exclude_tags=(),
             meal_affinity=("lunch_dinner", "any")),
    FoodItem("Rice Cakes", "carb", 8.0, 82.0, 2.8, 387, 30, 15, 60,
             peri_workout=True, phase_tags=("all",), exclude_tags=(),
             meal_affinity=("snack", "any")),
    FoodItem("Russet Potato (baked)", "carb", 2.5, 21.0, 0.1, 97, 250, 150, 400,
             peri_workout=True, phase_tags=("all",), exclude_tags=(),
             meal_affinity=("lunch_dinner",)),
    FoodItem("Red Potato (boiled)", "carb", 1.9, 20.0, 0.1, 87, 250, 150, 400,
             peri_workout=True, phase_tags=("all",), exclude_tags=(),
             meal_affinity=("lunch_dinner",)),
]

# ─── Vegetables ──────────────────────────────────────────────────────────────

VEGETABLES = [
    FoodItem("Broccoli", "vegetable", 2.8, 7.0, 0.4, 34, 150, 80, 250,
             phase_tags=("all",), exclude_tags=(), meal_affinity=("lunch_dinner",)),
    FoodItem("Asparagus", "vegetable", 2.2, 3.9, 0.1, 20, 150, 80, 250,
             phase_tags=("all",), exclude_tags=(), meal_affinity=("lunch_dinner",)),
    FoodItem("Spinach", "vegetable", 2.9, 3.6, 0.4, 23, 100, 50, 200,
             phase_tags=("all",), exclude_tags=(), meal_affinity=("lunch_dinner",)),
    FoodItem("Green Beans", "vegetable", 1.8, 7.0, 0.1, 31, 150, 80, 250,
             phase_tags=("all",), exclude_tags=(), meal_affinity=("lunch_dinner",)),
    FoodItem("Bell Peppers", "vegetable", 1.0, 6.0, 0.3, 26, 120, 60, 200,
             phase_tags=("all",), exclude_tags=(), meal_affinity=("lunch_dinner",)),
    FoodItem("Zucchini", "vegetable", 1.2, 3.1, 0.3, 17, 150, 80, 250,
             phase_tags=("all",), exclude_tags=(), meal_affinity=("lunch_dinner",)),
    FoodItem("Cucumber", "vegetable", 0.7, 3.6, 0.1, 15, 120, 60, 200,
             phase_tags=("all",), exclude_tags=(), meal_affinity=("lunch_dinner",)),
    FoodItem("Kale", "vegetable", 4.3, 9.0, 0.9, 49, 80, 40, 150,
             phase_tags=("all",), exclude_tags=(), meal_affinity=("lunch_dinner",)),
    FoodItem("Cauliflower", "vegetable", 1.9, 5.0, 0.3, 25, 150, 80, 250,
             phase_tags=("all",), exclude_tags=(), meal_affinity=("lunch_dinner",)),
]

# ─── Fruits ──────────────────────────────────────────────────────────────────

FRUITS = [
    FoodItem("Banana", "fruit", 1.1, 23.0, 0.3, 89, 120, 80, 150,
             peri_workout=True, phase_tags=("all",), exclude_tags=(),
             meal_affinity=("breakfast", "snack", "any")),
    FoodItem("Blueberries", "fruit", 0.7, 14.0, 0.3, 57, 80, 40, 150,
             phase_tags=("all",), exclude_tags=()),
    FoodItem("Strawberries", "fruit", 0.7, 8.0, 0.3, 32, 100, 50, 200,
             phase_tags=("all",), exclude_tags=()),
    FoodItem("Apple", "fruit", 0.3, 14.0, 0.2, 52, 180, 100, 200,
             phase_tags=("all",), exclude_tags=()),
    FoodItem("Pineapple", "fruit", 0.5, 13.0, 0.1, 50, 120, 60, 200,
             peri_workout=True, phase_tags=("bulk", "maintain"), exclude_tags=()),
]

# ─── Healthy Fats ────────────────────────────────────────────────────────────

FATS = [
    FoodItem("Natural Peanut Butter", "fat", 25.0, 20.0, 50.0, 588, 32, 15, 50,
             phase_tags=("all",), exclude_tags=()),
    FoodItem("Almond Butter", "fat", 21.0, 19.0, 50.0, 614, 32, 15, 50,
             phase_tags=("all",), exclude_tags=()),
    FoodItem("Almonds", "fat", 21.0, 22.0, 49.0, 579, 28, 14, 50,
             phase_tags=("all",), exclude_tags=()),
    FoodItem("Walnuts", "fat", 15.0, 14.0, 65.0, 654, 28, 14, 45,
             phase_tags=("bulk", "maintain"), exclude_tags=()),
    FoodItem("Avocado", "fat", 2.0, 9.0, 15.0, 160, 75, 50, 150,
             phase_tags=("all",), exclude_tags=()),
    FoodItem("Extra Virgin Olive Oil", "fat", 0.0, 0.0, 100.0, 884, 14, 5, 30,
             phase_tags=("all",), exclude_tags=()),
    FoodItem("Coconut Oil", "fat", 0.0, 0.0, 100.0, 862, 14, 5, 25,
             phase_tags=("bulk", "maintain"), exclude_tags=()),
    FoodItem("Chia Seeds", "fat", 17.0, 42.0, 31.0, 486, 20, 10, 40,
             phase_tags=("all",), exclude_tags=()),
    FoodItem("Flaxseeds (ground)", "fat", 18.0, 29.0, 42.0, 534, 15, 8, 30,
             phase_tags=("all",), exclude_tags=()),
]

# ─── All Foods ───────────────────────────────────────────────────────────────

ALL_FOODS = PROTEINS + CARBS + VEGETABLES + FRUITS + FATS


# ─── Filtering ───────────────────────────────────────────────────────────────

_PHASE_MAP = {
    "bulk": ("all", "bulk"),
    "lean_bulk": ("all", "bulk"),
    "cut": ("all", "prep"),
    "maintain": ("all", "maintain", "bulk"),
    "peak": ("all", "prep"),
    "restoration": ("all", "maintain", "bulk"),
}


# ─── Coach-Level Phase Blacklists ────────────────────────────────────────────
#
# These mirror what an Olympia-level coach would remove from a diet during
# specific phases. The reasoning:
#
# PEAK WEEK: Sodium control, GI predictability, water manipulation.
#   - No red meat (sodium, slow digestion, unpredictable water retention)
#   - No dairy (bloating, lactose-induced GI distress on stage day)
#   - No high-fiber complex carbs late in peak (bloating on show day)
#   - No nuts/nut butters (calorie-dense, hard to portion precisely)
#   - No cruciferous vegetables (bloating/gas)
#   - Only white fish, chicken breast, egg whites for protein
#   - Only white rice, cream of rice, rice cakes, potatoes for carbs
#   - Only olive oil (measured precisely) for fats
#
# CUT (contest prep): Gradual restriction as body fat drops.
#   - Remove calorie-dense fats (coconut oil, walnuts)
#   - Remove fatty proteins (salmon, whole eggs, sirloin)
#   - Keep food variety higher than peak but tighter than bulk
#
# These are ADDITIONAL to the phase_tags filtering already in place.

_COACH_PHASE_BLACKLISTS: dict[str, set[str]] = {
    "peak": {
        # Red meat — sodium, slow digestion, water retention unpredictability
        "Lean Ground Beef (96/4)", "Lean Ground Beef (93/7)", "Sirloin Steak",
        "Flank Steak", "Eye of Round", "Ground Turkey (93/7)",
        # Fatty fish — too much fat for peak week calorie precision
        "Salmon",
        # Dairy — bloating, lactose, GI unpredictability on stage day
        "Whole Eggs", "Greek Yogurt (nonfat)", "Cottage Cheese (low-fat)",
        # Pork — sodium content, unpredictable water
        "Pork Tenderloin",
        # Nuts and nut butters — calorie dense, hard to measure precisely
        "Natural Peanut Butter", "Almond Butter", "Almonds", "Walnuts",
        "Chia Seeds", "Flaxseeds (ground)",
        # Coconut oil — too dense, prefer olive oil for precision
        "Coconut Oil",
        # Cruciferous vegetables — bloating and gas risk on stage
        "Broccoli", "Cauliflower", "Kale",
        # High-fiber carbs — bloating risk in final days
        "Oats (rolled)", "Quinoa (cooked)", "Ezekiel Bread", "Brown Rice (cooked)",
        # Plant proteins — gas, fiber, bloating
        "Tofu (firm)", "Tempeh", "Seitan", "Edamame",
        # Fruits (most) — fructose can cause bloating + water
        "Apple", "Pineapple",
    },
    "cut": {
        # Remove calorie-dense fats that are hard to track precisely
        "Coconut Oil", "Walnuts",
        # Remove fattier proteins — every calorie counts during prep
        "Salmon", "Whole Eggs", "Sirloin Steak",
        "Lean Ground Beef (93/7)",
    },
}


# ─── Coach-Level Phase Rankings ──────────────────────────────────────────────
#
# A real Olympia coach has "go-to" proteins per phase. These rankings control
# the default order when the user has no preferences set.
# The first items in each list are chosen first by the meal planner.

_PHASE_PROTEIN_RANKINGS: dict[str, list[str]] = {
    "bulk": [
        "Chicken Breast", "Lean Ground Beef (96/4)", "Flank Steak",
        "Turkey Breast", "Whole Eggs", "Salmon", "Ground Turkey (93/7)",
        "Sirloin Steak", "Greek Yogurt (nonfat)", "Pork Tenderloin",
    ],
    "lean_bulk": [
        "Chicken Breast", "Turkey Breast", "Lean Ground Beef (96/4)",
        "Flank Steak", "Tilapia", "Egg Whites", "Greek Yogurt (nonfat)",
        "Ground Turkey (93/7)", "Cod", "Shrimp",
    ],
    "cut": [
        "Chicken Breast", "Turkey Breast", "Tilapia", "Cod",
        "Egg Whites", "Lean Ground Beef (96/4)", "Shrimp",
        "Flank Steak", "Halibut", "Canned Tuna (in water)",
    ],
    "peak": [
        "Chicken Breast", "Turkey Breast", "Tilapia", "Cod",
        "Egg Whites", "Shrimp", "Halibut",
    ],
    "maintain": [
        "Chicken Breast", "Turkey Breast", "Lean Ground Beef (96/4)",
        "Tilapia", "Flank Steak", "Egg Whites", "Cod",
        "Greek Yogurt (nonfat)", "Shrimp", "Ground Turkey (93/7)",
    ],
}

_PHASE_CARB_RANKINGS: dict[str, list[str]] = {
    "bulk": [
        "White Rice (cooked)", "Jasmine Rice (cooked)", "Sweet Potato",
        "Oats (rolled)", "Brown Rice (cooked)", "Cream of Rice (dry)",
        "Russet Potato (baked)", "Quinoa (cooked)", "Ezekiel Bread",
    ],
    "lean_bulk": [
        "White Rice (cooked)", "Jasmine Rice (cooked)", "Sweet Potato",
        "Oats (rolled)", "Brown Rice (cooked)", "Cream of Rice (dry)",
        "Quinoa (cooked)", "Russet Potato (baked)",
    ],
    "cut": [
        "White Rice (cooked)", "Jasmine Rice (cooked)", "Sweet Potato",
        "Cream of Rice (dry)", "Oats (rolled)", "Red Potato (boiled)",
        "Rice Cakes",
    ],
    "peak": [
        "White Rice (cooked)", "Jasmine Rice (cooked)", "Sweet Potato",
        "Cream of Rice (dry)", "Rice Cakes", "Red Potato (boiled)",
    ],
    "maintain": [
        "White Rice (cooked)", "Jasmine Rice (cooked)", "Sweet Potato",
        "Oats (rolled)", "Brown Rice (cooked)", "Cream of Rice (dry)",
        "Quinoa (cooked)", "Russet Potato (baked)",
    ],
}

_PHASE_FAT_RANKINGS: dict[str, list[str]] = {
    "bulk": [
        "Extra Virgin Olive Oil", "Natural Peanut Butter", "Almonds",
        "Almond Butter", "Avocado", "Walnuts", "Chia Seeds",
    ],
    "lean_bulk": [
        "Extra Virgin Olive Oil", "Avocado", "Almonds",
        "Natural Peanut Butter", "Almond Butter", "Chia Seeds",
    ],
    "cut": [
        "Extra Virgin Olive Oil", "Avocado", "Almonds",
        "Natural Peanut Butter",
    ],
    "peak": [
        "Extra Virgin Olive Oil", "Avocado",
    ],
    "maintain": [
        "Extra Virgin Olive Oil", "Avocado", "Almonds",
        "Natural Peanut Butter", "Almond Butter",
    ],
}


def _apply_phase_ranking(foods: list[FoodItem], phase: str, category: str) -> list[FoodItem]:
    """Sort foods by coach-level phase ranking. Unranked foods go to the end."""
    rankings = {
        "protein": _PHASE_PROTEIN_RANKINGS,
        "carb": _PHASE_CARB_RANKINGS,
        "fat": _PHASE_FAT_RANKINGS,
    }
    rank_map = rankings.get(category, {}).get(phase, [])
    if not rank_map:
        return foods

    rank_index = {name: i for i, name in enumerate(rank_map)}
    max_rank = len(rank_map)

    return sorted(foods, key=lambda f: rank_index.get(f.name, max_rank + hash(f.name) % 100))


def get_available_foods(
    phase: str = "maintain",
    dietary_restrictions: list[str] | None = None,
    category: str | None = None,
    peri_workout_only: bool = False,
) -> list[FoodItem]:
    """Return foods available for the given phase and dietary profile.

    Applies both phase_tags filtering AND coach-level phase blacklists
    that mirror real Olympia-level coaching practices.
    """
    allowed_phases = _PHASE_MAP.get(phase, ("all",))
    restrictions = set(dietary_restrictions or [])
    coach_blacklist = _COACH_PHASE_BLACKLISTS.get(phase, set())

    result = []
    for food in ALL_FOODS:
        # Phase filter
        if not any(tag in allowed_phases for tag in food.phase_tags):
            continue
        # Coach-level phase blacklist (e.g. no red meat during peak week)
        if food.name in coach_blacklist:
            continue
        # Dietary restriction filter
        if restrictions and any(tag in restrictions for tag in food.exclude_tags):
            continue
        # Category filter
        if category and food.category != category:
            continue
        # Peri-workout filter
        if peri_workout_only and not food.peri_workout:
            continue
        result.append(food)

    # Apply coach-level phase ranking so the "best" foods come first
    if category:
        result = _apply_phase_ranking(result, phase, category)

    return result
