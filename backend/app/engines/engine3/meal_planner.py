"""
Engine 3 — Meal Planner

Generates coach-level meal plans from a curated bodybuilding food database.
Every food item is hand-picked; no random DB ingredients.

Principles:
- Phase-appropriate food selection (prep = lean, bulk = calorie-dense)
- Dietary preference filtering (vegetarian, gluten-free, etc.)
- Fat isolated from peri-workout window
- Variety across meals (no same protein 4x)
- Realistic serving sizes with macro-driven scaling
- Division-specific strategy flags
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from app.engines.engine3.food_database import (
    FoodItem,
    get_available_foods,
)


@dataclass
class MealIngredient:
    name: str
    quantity_g: float
    protein_g: float
    carbs_g: float
    fat_g: float
    calories: float


@dataclass
class Meal:
    meal_number: int
    label: str
    time_str: str
    is_peri: bool
    ingredients: list[MealIngredient] = field(default_factory=list)

    @property
    def totals(self) -> dict[str, float]:
        return {
            "calories": round(sum(i.calories for i in self.ingredients), 0),
            "protein_g": round(sum(i.protein_g for i in self.ingredients), 1),
            "carbs_g": round(sum(i.carbs_g for i in self.ingredients), 1),
            "fat_g": round(sum(i.fat_g for i in self.ingredients), 1),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "meal_number": self.meal_number,
            "label": self.label,
            "time": self.time_str,
            "is_peri": self.is_peri,
            "ingredients": [
                {
                    "name": i.name,
                    "quantity_g": round(i.quantity_g),
                    "protein_g": round(i.protein_g, 1),
                    "carbs_g": round(i.carbs_g, 1),
                    "fat_g": round(i.fat_g, 1),
                    "calories": round(i.calories),
                }
                for i in self.ingredients
            ],
            "totals": self.totals,
        }


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _scale_food(food: FoodItem, target_g: float) -> MealIngredient:
    """Create a MealIngredient from a FoodItem at a specific gram weight."""
    factor = target_g / 100.0
    return MealIngredient(
        name=food.name,
        quantity_g=round(target_g),
        protein_g=round(food.protein * factor, 1),
        carbs_g=round(food.carbs * factor, 1),
        fat_g=round(food.fat * factor, 1),
        calories=round(food.calories * factor),
    )


def _scale_food_to_protein(food: FoodItem, target_protein_g: float) -> MealIngredient:
    """Scale a food to hit a protein target."""
    if food.protein <= 0:
        return _scale_food(food, food.typical_serving_g)
    qty = (target_protein_g / food.protein) * 100
    qty = max(food.min_serving_g, min(qty, food.max_serving_g))
    return _scale_food(food, qty)


def _scale_food_to_carbs(food: FoodItem, target_carbs_g: float) -> MealIngredient:
    """Scale a food to hit a carb target."""
    if food.carbs <= 0:
        return _scale_food(food, food.typical_serving_g)
    qty = (target_carbs_g / food.carbs) * 100
    qty = max(food.min_serving_g, min(qty, food.max_serving_g))
    return _scale_food(food, qty)


def _scale_food_to_fat(food: FoodItem, target_fat_g: float) -> MealIngredient:
    """Scale a food to hit a fat target."""
    if food.fat <= 0:
        return _scale_food(food, food.typical_serving_g)
    qty = (target_fat_g / food.fat) * 100
    qty = max(food.min_serving_g, min(qty, food.max_serving_g))
    return _scale_food(food, qty)


def _pick_unique(foods: list[FoodItem], used: set[str], count: int = 1, slot_type: str = "any") -> list[FoodItem]:
    """Pick foods not yet used, filtered by meal slot type. Falls back gracefully."""
    # First try: unused foods matching the slot type
    available = [f for f in foods
                 if f.name not in used
                 and (slot_type in f.meal_affinity or "any" in f.meal_affinity)]
    if not available:
        # Fallback: any unused food (ignore affinity)
        available = [f for f in foods if f.name not in used]
    if not available:
        # Last resort: reuse foods
        available = list(foods)
    return available[:count]


# ─── Meal time slot builder ──────────────────────────────────────────────────

def _build_time_slots(
    meal_count: int,
    training_start_time: str,
    training_duration_min: int,
    is_training_day: bool,
) -> list[tuple[int, str, bool, str]]:
    """Return list of (minutes_from_midnight, label, is_peri, slot_type).

    slot_type determines which foods are appropriate:
      - "breakfast": before 10:00 AM (oats, eggs, yogurt)
      - "lunch_dinner": 10:00 AM onwards (rice, potato, meat + veg)
      - "any": peri-workout slots (macro-driven, affinity ignored)
    """
    try:
        h, m = map(int, training_start_time.split(":"))
        train_start = h * 60 + m
    except Exception:
        train_start = 10 * 60

    train_end = train_start + training_duration_min
    day_start = 6 * 60
    day_end = 22 * 60
    breakfast_cutoff = 10 * 60  # 10:00 AM

    slots: list[tuple[int, str, bool, str]] = []

    if is_training_day and meal_count >= 3:
        pre_time = max(day_start, train_start - 60)
        post_time = min(day_end, train_end + 30)

        non_peri = meal_count - 2
        before_count = max(0, non_peri // 2)
        after_count = non_peri - before_count

        before_span = pre_time - day_start
        for i in range(before_count):
            t = day_start + int(before_span * (i + 1) / (before_count + 1))
            stype = "breakfast" if t < breakfast_cutoff else "lunch_dinner"
            slots.append((t, "Meal", False, stype))

        slots.append((pre_time, "Pre-Workout", True, "any"))
        slots.append((post_time, "Post-Workout", True, "any"))

        after_span = day_end - post_time
        for i in range(after_count):
            t = post_time + int(after_span * (i + 1) / (after_count + 1))
            slots.append((t, "Meal", False, "lunch_dinner"))
    else:
        span = day_end - day_start
        for i in range(meal_count):
            t = day_start + int(span * i / max(1, meal_count - 1)) if meal_count > 1 else day_start + span // 2
            stype = "breakfast" if t < breakfast_cutoff else "lunch_dinner"
            slots.append((t, "Meal", False, stype))

    slots.sort(key=lambda x: x[0])
    return slots


def _mins_to_time(mins: int) -> str:
    """Convert minutes since midnight to 12-hour format (e.g. '7:30 AM')."""
    h = (mins // 60) % 24
    m = mins % 60
    period = "AM" if h < 12 else "PM"
    display_h = h if 1 <= h <= 12 else (h - 12 if h > 12 else 12)
    return f"{display_h}:{m:02d} {period}"


# ─── Main generator ─────────────────────────────────────────────────────────

def _prioritize_preferred(foods: list[FoodItem], preferred_names: list[str]) -> list[FoodItem]:
    """Sort foods so user-preferred items come first."""
    if not preferred_names:
        return foods
    lower_prefs = {n.lower() for n in preferred_names}
    preferred = [f for f in foods if f.name.lower() in lower_prefs]
    rest = [f for f in foods if f.name.lower() not in lower_prefs]
    random.shuffle(preferred)
    random.shuffle(rest)
    return preferred + rest


def _exclude_blacklisted(foods: list[FoodItem], blacklisted: list[str]) -> list[FoodItem]:
    """Remove blacklisted foods, but always keep at least a few options."""
    if not blacklisted:
        return foods
    lower_bl = {n.lower() for n in blacklisted}
    filtered = [f for f in foods if f.name.lower() not in lower_bl]
    return filtered if len(filtered) >= 2 else foods


def generate_meal_plan(
    phase: str,
    division: str,
    meal_count: int,
    protein_g: float,
    carbs_g: float,
    fat_g: float,
    target_calories: float,
    training_start_time: str = "10:00",
    training_duration_min: int = 75,
    is_training_day: bool = True,
    is_refeed: bool = False,
    peri_workout_carb_pct: float = 0.35,
    dietary_restrictions: list[str] | None = None,
    seed: int | None = None,
    preferred_proteins: list[str] | None = None,
    preferred_carbs: list[str] | None = None,
    preferred_fats: list[str] | None = None,
    blacklisted_foods: list[str] | None = None,
) -> list[dict]:
    """
    Generate a structured meal plan using curated bodybuilding foods.

    No DB queries — uses the hardcoded food_database module.
    Returns list of serializable meal dicts.
    """
    if seed is not None:
        random.seed(seed)

    restrictions = dietary_restrictions or []

    # Get phase-filtered food pools
    proteins = get_available_foods(phase, restrictions, "protein")
    carbs_all = get_available_foods(phase, restrictions, "carb")
    fats = get_available_foods(phase, restrictions, "fat")
    vegetables = get_available_foods(phase, restrictions, "vegetable")
    fruits = get_available_foods(phase, restrictions, "fruit")

    # Apply user blacklist and preference ordering
    bl = blacklisted_foods or []
    proteins = _prioritize_preferred(_exclude_blacklisted(proteins, bl), preferred_proteins or [])
    carbs_all = _prioritize_preferred(_exclude_blacklisted(carbs_all, bl), preferred_carbs or [])
    fats = _prioritize_preferred(_exclude_blacklisted(fats, bl), preferred_fats or [])

    # Peri-workout specific pools
    peri_proteins = [p for p in proteins if p.peri_workout] or proteins[:3]
    peri_carbs = [c for c in carbs_all if c.peri_workout] or carbs_all[:3]
    sustained_carbs = [c for c in carbs_all if not c.peri_workout] or carbs_all

    # Refeed override
    if is_refeed:
        fat_g = max(15.0, fat_g * 0.15)
        carbs_g = carbs_g * 1.6
        target_calories = protein_g * 4 + carbs_g * 4 + fat_g * 9

    # Build time slots
    slots = _build_time_slots(meal_count, training_start_time, training_duration_min, is_training_day)

    # Distribute macros across meals
    #
    # Coach principle: peri-workout window (pre + post) receives the LARGEST
    # carbohydrate allocation to fuel training and drive recovery. Fat is
    # isolated AWAY from peri-workout for gastric emptying speed. Protein
    # is distributed evenly across all meals for MPS optimization.
    peri_count = sum(1 for _, _, p, _ in slots if p)
    non_peri_count = len(slots) - peri_count

    # Peri-workout gets 40-50% of carbs (up from old 35% default)
    effective_peri_pct = max(peri_workout_carb_pct, 0.35) if is_training_day else 0
    peri_carb_total = carbs_g * effective_peri_pct if is_training_day else 0
    other_carb_total = carbs_g - peri_carb_total

    per_meal_protein = protein_g / len(slots)
    per_peri_carbs = peri_carb_total / max(1, peri_count)
    per_other_carbs = other_carb_total / max(1, non_peri_count) if non_peri_count > 0 else 0
    per_meal_fat = fat_g / max(1, non_peri_count)

    # Track used foods for variety
    used_proteins: set[str] = set()
    used_carbs: set[str] = set()
    used_fats: set[str] = set()
    used_vegs: set[str] = set()

    meals: list[Meal] = []

    for idx, (mins, label, is_peri, slot_type) in enumerate(slots):
        meal_num = idx + 1
        label_str = f"Meal {meal_num} – {label}" if label != "Meal" else f"Meal {meal_num}"
        time_str = _mins_to_time(mins)
        meal = Meal(meal_number=meal_num, label=label_str, time_str=time_str, is_peri=is_peri)

        # Per-meal targets
        m_protein = per_meal_protein
        m_carbs = per_peri_carbs if is_peri else per_other_carbs
        m_fat = 0.0 if is_peri else per_meal_fat

        # ── 1. Protein source (slot-type aware) ──
        pool = peri_proteins if is_peri else proteins
        picks = _pick_unique(pool, used_proteins, slot_type=slot_type)
        if picks:
            protein_food = picks[0]
            used_proteins.add(protein_food.name)
            item = _scale_food_to_protein(protein_food, m_protein)
            meal.ingredients.append(item)
            remaining_protein = max(0, m_protein - item.protein_g)
        else:
            remaining_protein = m_protein

        # ── 2. Carb source (slot-type aware) ──
        if m_carbs > 5:
            pool = peri_carbs if is_peri else sustained_carbs
            picks = _pick_unique(pool, used_carbs, slot_type=slot_type)
            if picks:
                carb_food = picks[0]
                used_carbs.add(carb_food.name)
                item = _scale_food_to_carbs(carb_food, m_carbs)
                meal.ingredients.append(item)

        # ── 3. Fat source (not peri-workout) ──
        if not is_peri and m_fat > 3:
            picks = _pick_unique(fats, used_fats, slot_type=slot_type)
            if picks:
                fat_food = picks[0]
                used_fats.add(fat_food.name)
                item = _scale_food_to_fat(fat_food, m_fat)
                meal.ingredients.append(item)

        # ── 4. Vegetable (non-peri, non-refeed, lunch/dinner only) ──
        if not is_peri and not is_refeed and vegetables and slot_type != "breakfast":
            picks = _pick_unique(vegetables, used_vegs, slot_type=slot_type)
            if picks:
                veg_food = picks[0]
                used_vegs.add(veg_food.name)
                item = _scale_food(veg_food, veg_food.typical_serving_g)
                meal.ingredients.append(item)

        meals.append(meal)

    return [m.to_dict() for m in meals]
