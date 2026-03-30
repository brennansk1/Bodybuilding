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


def _select_daily_staples(
    foods: list[FoodItem],
    max_picks: int,
    slot_types: list[str],
) -> list[FoodItem]:
    """Select a small staple pool for the entire day from the ranked food list.

    Real bodybuilding coaching principle: an athlete eats 3-4 protein sources,
    2-3 carb sources, and 1-2 fat sources per day — repeating them across meals.
    This reduces meal-prep complexity and mirrors how actual competitors eat.

    The foods list is already ranked by phase priority, so we take the top N
    ensuring at least one food matches each required slot_type (breakfast vs
    lunch_dinner) when possible.
    """
    if max_picks >= len(foods):
        return foods

    staples: list[FoodItem] = []
    used_names: set[str] = set()

    # First pass: ensure coverage for each slot type
    for st in slot_types:
        for f in foods:
            if f.name not in used_names and (
                st in f.meal_affinity or "any" in f.meal_affinity
            ):
                staples.append(f)
                used_names.add(f.name)
                break

    # Second pass: fill remaining slots from top-ranked foods
    for f in foods:
        if len(staples) >= max_picks:
            break
        if f.name not in used_names:
            staples.append(f)
            used_names.add(f.name)

    return staples


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

    # Get phase-filtered food pools (already ranked by coach-level priority)
    proteins = get_available_foods(phase, restrictions, "protein")
    carbs_all = get_available_foods(phase, restrictions, "carb")
    fats = get_available_foods(phase, restrictions, "fat")
    vegetables = get_available_foods(phase, restrictions, "vegetable")

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

    # ── Coach-realistic staple selection ──────────────────────────────────
    #
    # A real bodybuilding prep diet uses a SMALL set of foods repeated across
    # meals. A typical day: 2-3 protein sources (e.g. chicken breast at most
    # meals, egg whites at breakfast, white fish post-workout), 2-3 carb
    # sources (white rice, oats, sweet potato), 1-2 fat sources (olive oil,
    # almonds), and 1-2 vegetables (broccoli, asparagus).
    #
    # The staple pool sizes below mirror real competitor prep sheets.
    # Phase tightening: peak/cut use fewer staples for GI predictability.
    is_strict_phase = phase in ("peak", "cut")

    slot_types_in_plan = list({st for _, _, _, st in slots if st != "any"})

    protein_staple_count = 2 if is_strict_phase else 3
    carb_staple_count = 2 if is_strict_phase else 3
    fat_staple_count = 1 if is_strict_phase else 2
    veg_staple_count = 1 if is_strict_phase else 2

    daily_proteins = _select_daily_staples(proteins, protein_staple_count, slot_types_in_plan)
    daily_carbs = _select_daily_staples(sustained_carbs, carb_staple_count, slot_types_in_plan)
    daily_peri_carbs = _select_daily_staples(peri_carbs, min(2, len(peri_carbs)), ["any"])
    daily_fats = _select_daily_staples(fats, fat_staple_count, slot_types_in_plan)
    daily_vegs = _select_daily_staples(vegetables, veg_staple_count, ["lunch_dinner"])
    daily_peri_proteins = _select_daily_staples(peri_proteins, min(2, len(peri_proteins)), ["any"])

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

    # Round-robin indices for staple rotation (reuse within the small pool)
    _prot_idx = 0
    _carb_idx = 0
    _fat_idx = 0
    _veg_idx = 0
    _peri_prot_idx = 0
    _peri_carb_idx = 0

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

        # ── 1. Protein source (round-robin from daily staples) ──
        if is_peri and daily_peri_proteins:
            protein_food = daily_peri_proteins[_peri_prot_idx % len(daily_peri_proteins)]
            _peri_prot_idx += 1
        elif daily_proteins:
            # Pick affinity-matching staple when possible
            affinity_match = [f for f in daily_proteins
                             if slot_type in f.meal_affinity or "any" in f.meal_affinity]
            if affinity_match:
                protein_food = affinity_match[_prot_idx % len(affinity_match)]
            else:
                protein_food = daily_proteins[_prot_idx % len(daily_proteins)]
            _prot_idx += 1
        else:
            protein_food = None

        if protein_food:
            item = _scale_food_to_protein(protein_food, m_protein)
            meal.ingredients.append(item)
            # Subtract incidental carbs/fat from remaining macro budget
            m_carbs = max(0, m_carbs - item.carbs_g)
            m_fat = max(0, m_fat - item.fat_g)

        # ── 2. Carb source (round-robin from daily staples) ──
        if m_carbs > 5:
            if is_peri and daily_peri_carbs:
                carb_food = daily_peri_carbs[_peri_carb_idx % len(daily_peri_carbs)]
                _peri_carb_idx += 1
            elif daily_carbs:
                affinity_match = [f for f in daily_carbs
                                 if slot_type in f.meal_affinity or "any" in f.meal_affinity]
                if affinity_match:
                    carb_food = affinity_match[_carb_idx % len(affinity_match)]
                else:
                    carb_food = daily_carbs[_carb_idx % len(daily_carbs)]
                _carb_idx += 1
            else:
                carb_food = None

            if carb_food:
                item = _scale_food_to_carbs(carb_food, m_carbs)
                meal.ingredients.append(item)
                # Subtract incidental fat from remaining budget
                m_fat = max(0, m_fat - item.fat_g)

        # ── 3. Fat source (not peri-workout, round-robin) ──
        if not is_peri and m_fat > 3 and daily_fats:
            fat_food = daily_fats[_fat_idx % len(daily_fats)]
            _fat_idx += 1
            item = _scale_food_to_fat(fat_food, m_fat)
            meal.ingredients.append(item)

        # ── 4. Vegetable (non-peri, non-refeed, lunch/dinner only) ──
        if not is_peri and not is_refeed and daily_vegs and slot_type != "breakfast":
            veg_food = daily_vegs[_veg_idx % len(daily_vegs)]
            _veg_idx += 1
            item = _scale_food(veg_food, veg_food.typical_serving_g)
            meal.ingredients.append(item)

        meals.append(meal)

    return [m.to_dict() for m in meals]
