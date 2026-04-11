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
from app.engines.engine3.macros import INTRA_HBCD_BY_MUSCLE


@dataclass
class MealIngredient:
    name: str
    quantity_g: float
    protein_g: float
    carbs_g: float
    fat_g: float
    calories: float
    quantity_display: str | None = None  # e.g. "800 ml" for water


@dataclass
class Meal:
    meal_number: int
    label: str
    time_str: str
    is_peri: bool
    ingredients: list[MealIngredient] = field(default_factory=list)
    is_intra: bool = False
    note: str | None = None

    @property
    def totals(self) -> dict[str, float]:
        return {
            "calories": round(sum(i.calories for i in self.ingredients), 0),
            "protein_g": round(sum(i.protein_g for i in self.ingredients), 1),
            "carbs_g": round(sum(i.carbs_g for i in self.ingredients), 1),
            "fat_g": round(sum(i.fat_g for i in self.ingredients), 1),
        }

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "meal_number": self.meal_number,
            "label": self.label,
            "time": self.time_str,
            "is_peri": self.is_peri,
            "ingredients": [],
            "totals": self.totals,
        }
        if self.is_intra:
            d["is_intra"] = True
        if self.note:
            d["note"] = self.note
        for i in self.ingredients:
            ing: dict[str, Any] = {
                "name": i.name,
                "quantity_g": round(i.quantity_g),
                "protein_g": round(i.protein_g, 1),
                "carbs_g": round(i.carbs_g, 1),
                "fat_g": round(i.fat_g, 1),
                "calories": round(i.calories),
            }
            if i.quantity_display:
                ing["quantity_display"] = i.quantity_display
            d["ingredients"].append(ing)
        return d


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


# ─── Intra-Workout Drink Builder ─────────────────────────────────────────────

def _build_intra_drink(
    body_weight_kg: float,
    session_muscles: list[str],
    training_start_time: str,
    training_duration_min: int,
    peri_carb_budget_g: float,
    is_early_workout: bool = False,
    is_late_workout: bool = False,
) -> tuple[Meal, float, float]:
    """Build an Olympia-level intra-workout supplement drink.

    The drink maximizes fascial stretching and pump during FST-7 protocols:
    - HBCD for immediate glycolytic fuel (low osmolality, fast gastric emptying)
    - EAAs for intra-session MPS signaling
    - Citrulline + Agmatine + Betaine for NO-driven vasodilation and cell volume
    - Electrolytes (sodium + potassium) for plasma volume and cramp prevention

    Returns (meal, hbcd_carbs_g, eaa_protein_g) so the caller can adjust budgets.
    """
    _clamp = lambda v, lo, hi: max(lo, min(v, hi))

    # ── EAAs ──
    eaa_g = round(body_weight_kg * 0.13, 1)
    if is_early_workout:
        eaa_g = round(eaa_g * 1.25, 1)  # fasted → more anti-catabolic
    eaa_g = _clamp(eaa_g, 8.0, 15.0)
    eaa_protein_g = round(eaa_g * 0.85, 1)  # ~85% amino acid by weight

    # ── HBCD (muscle-scaled) ──
    if session_muscles:
        hbcd_g = float(max(
            (INTRA_HBCD_BY_MUSCLE.get(m.lower(), 20) for m in session_muscles),
            default=25,
        ))
    else:
        hbcd_g = 25.0  # fallback
    if is_early_workout:
        hbcd_g = round(hbcd_g * 1.25)  # fasted → HBCD is primary fuel
    if is_late_workout:
        hbcd_g = min(hbcd_g, 30.0)  # avoid blood sugar spike before sleep
    hbcd_g = _clamp(hbcd_g, 10.0, min(60.0, peri_carb_budget_g))

    # ── Pink Himalayan Salt ──
    salt_g = round(body_weight_kg * 0.012, 2)
    if is_late_workout:
        salt_g = round(salt_g * 0.75, 2)  # reduce sodium before sleep
    salt_g = _clamp(salt_g, 0.5, 1.5)

    # ── Fixed-dose supplements ──
    potassium_mg = 200.0  # safety cap — never exceed 300mg supplemental
    betaine_g = 2.5       # clinical research dose
    agmatine_g = 1.0      # standard effective dose
    creatine_g = 5.0      # saturation dose

    # ── L-Citrulline Malate 2:1 ──
    citrulline_g = round(body_weight_kg * 0.09, 1)
    citrulline_g = _clamp(citrulline_g, 6.0, 10.0)

    # ── Water ──
    water_ml = round(_clamp(400 + body_weight_kg * 8, 400, 1200))

    # ── Build ingredient list ──
    ingredients = [
        MealIngredient("EAAs (Essential Amino Acids)", eaa_g,
                        protein_g=eaa_protein_g, carbs_g=0, fat_g=0,
                        calories=round(eaa_protein_g * 4)),
        MealIngredient("Highly Branched Cyclic Dextrin (HBCD)", hbcd_g,
                        protein_g=0, carbs_g=hbcd_g, fat_g=0,
                        calories=round(hbcd_g * 4)),
        MealIngredient("Pink Himalayan Salt", salt_g,
                        protein_g=0, carbs_g=0, fat_g=0, calories=0),
        MealIngredient("Potassium Citrate", round(potassium_mg / 1000, 1),
                        protein_g=0, carbs_g=0, fat_g=0, calories=0),
        MealIngredient("Betaine Anhydrous", betaine_g,
                        protein_g=0, carbs_g=0, fat_g=0, calories=0),
        MealIngredient("Agmatine Sulfate", agmatine_g,
                        protein_g=0, carbs_g=0, fat_g=0, calories=0),
        MealIngredient("Creatine Monohydrate", creatine_g,
                        protein_g=0, carbs_g=0, fat_g=0, calories=0),
        MealIngredient("L-Citrulline Malate 2:1", citrulline_g,
                        protein_g=0, carbs_g=0, fat_g=0, calories=0),
        MealIngredient("Water", water_ml,
                        protein_g=0, carbs_g=0, fat_g=0, calories=0,
                        quantity_display=f"{water_ml} ml"),
    ]

    # ── Compute time (midpoint of training session) ──
    try:
        h, m = map(int, training_start_time.split(":"))
        train_start_mins = h * 60 + m
    except Exception:
        train_start_mins = 10 * 60
    intra_time_mins = train_start_mins + training_duration_min // 2
    time_str = _mins_to_time(intra_time_mins)

    meal = Meal(
        meal_number=0,  # set by caller
        label="Intra-Workout Drink",
        time_str=time_str,
        is_peri=True,
        ingredients=ingredients,
        is_intra=True,
        note=(
            "Sip throughout the entire training session — do not chug. "
            "During FST-7 finisher sets (7 sets, 30-45s rest), the pump complex "
            "(citrulline + agmatine + betaine + sodium) maximizes intracellular "
            "fluid and fascia stretch. HBCD provides immediate glycolytic fuel "
            "for high-rep work without GI distress."
        ),
    )

    return meal, hbcd_g, eaa_protein_g


# ─── Meal time slot builder ──────────────────────────────────────────────────

def _build_time_slots(
    meal_count: int,
    training_start_time: str,
    training_duration_min: int,
    is_training_day: bool,
    include_intra: bool = False,
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
        pre_time = max(day_start, train_start - 90)   # pre-WO 90min before (digestion)
        post_time = min(day_end, train_end + 30)

        peri_slots = 3 if include_intra else 2
        non_peri = meal_count - peri_slots
        before_span = pre_time - day_start

        # If there's less than 90 min before pre-WO, no room for a separate meal.
        # Athletes training at 5-6am train fasted or use pre-WO as first meal.
        if before_span < 90:
            before_count = 0
            after_count = non_peri
        else:
            # Distribute based on available time windows
            hours_before = before_span / 60
            hours_after = (day_end - post_time) / 60
            total_hours = hours_before + hours_after
            if total_hours > 0:
                before_count = max(1, round(non_peri * hours_before / total_hours))
            else:
                before_count = max(1, non_peri // 2)
            after_count = non_peri - before_count

        for i in range(before_count):
            t = day_start + int(before_span * (i + 1) / (before_count + 1))
            stype = "breakfast" if t < breakfast_cutoff else "lunch_dinner"
            slots.append((t, "Meal", False, stype))

        slots.append((pre_time, "Pre-Workout", True, "any"))
        if include_intra:
            intra_time = train_start + training_duration_min // 2
            slots.append((intra_time, "Intra-Workout", True, "any"))
        slots.append((post_time, "Post-Workout", True, "any"))

        after_span = day_end - post_time
        for i in range(after_count):
            t = post_time + int(after_span * (i + 1) / (after_count + 1))
            slots.append((t, "Meal", False, "lunch_dinner"))

        # Guarantee: the FIRST meal of the day is always breakfast-type
        # (a real athlete eats eggs at 6-7am, not chicken)
        if slots:
            slots.sort(key=lambda x: x[0])
            first = slots[0]
            if not first[2] and first[0] < 12 * 60:  # non-peri and before noon
                slots[0] = (first[0], first[1], first[2], "breakfast")
    else:
        # Rest days end earlier — last meal by 9 PM max (real coaches don't
        # schedule meals at 10 PM; digestion and sleep quality suffer)
        rest_day_end = 21 * 60  # 9:00 PM
        span = rest_day_end - day_start
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
    """Sort foods so user-preferred items come first, preserving phase-rank order.

    Uses substring matching so "White Rice" matches "White Rice (cooked)", etc.
    Deterministic: preferred foods stay in the caller's preference order; the rest
    stay in phase-rank order. This is critical for meal-plan stability — coaches
    repeat 2-3 staples across every meal, not a new random pick each regen.
    """
    if not preferred_names:
        return foods
    lower_prefs = [n.lower() for n in preferred_names]

    def _preferred_rank(f: FoodItem) -> int | None:
        fname = f.name.lower()
        for idx, pref in enumerate(lower_prefs):
            if pref in fname:
                return idx
        return None

    ranked = [(f, _preferred_rank(f)) for f in foods]
    preferred = sorted(
        [(f, r) for f, r in ranked if r is not None],
        key=lambda pair: pair[1],  # type: ignore[arg-type]
    )
    rest = [f for f, r in ranked if r is None]
    return [f for f, _ in preferred] + rest


def compute_filtered_picks(
    phase: str,
    dietary_restrictions: list[str] | None,
    preferred_proteins: list[str] | None,
    preferred_carbs: list[str] | None,
    preferred_fats: list[str] | None,
    preferred_vegetables: list[str] | None,
) -> dict[str, list[str]]:
    """Return user picks that got dropped by phase/dietary filtering.

    Used by the router so the nutrition page can show "Sirloin Steak isn't
    available during cut — pick a leaner option" instead of silently
    swapping the food. Pure function, no DB, safe to call on every request.
    """
    restrictions = dietary_restrictions or []
    proteins = get_available_foods(phase, restrictions, "protein")
    carbs = get_available_foods(phase, restrictions, "carb")
    fats = get_available_foods(phase, restrictions, "fat")
    vegs = get_available_foods(phase, restrictions, "vegetable")

    def _dropped(picks: list[str] | None, pool: list[FoodItem]) -> list[str]:
        if not picks:
            return []
        pool_names = [f.name.lower() for f in pool]
        return [p for p in picks if not any(p.lower() in name for name in pool_names)]

    return {
        "proteins": _dropped(preferred_proteins, proteins),
        "carbs": _dropped(preferred_carbs, carbs),
        "fats": _dropped(preferred_fats, fats),
        "vegetables": _dropped(preferred_vegetables, vegs),
    }


def _strict_filter(foods: list[FoodItem], preferred_names: list[str]) -> list[FoodItem]:
    """Restrict the food pool to ONLY the user's selected items.

    Uses substring matching so "White Rice" matches "White Rice (cooked)", etc.
    If no matches are found (edge case — user picked foods blocked by dietary
    restrictions in this phase), fall back to the full phase-ranked pool so the
    planner still has something to work with.

    Preserves phase-rank order within the filtered set: a user's top pick that
    also happens to be the phase-optimal choice stays at the top of the pool.
    """
    if not preferred_names:
        return foods
    lower_prefs = [n.lower() for n in preferred_names]
    filtered = [
        f for f in foods
        if any(pref in f.name.lower() for pref in lower_prefs)
    ]
    return filtered if filtered else foods


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
    preferred_vegetables: list[str] | None = None,
    intra_workout_nutrition: bool = False,
    fasted_training: bool = False,
    body_weight_kg: float = 80.0,
    session_muscles: list[str] | None = None,
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

    # Apply user preference filtering + ordering.
    #
    # When the user selects ANY staples for a macro, the planner restricts
    # that food pool to ONLY those picks — a real coach prep sheet uses
    # exactly 2-3 proteins, 2-3 carbs, 1-2 fats, 2 vegetables rotated across
    # every meal, nothing else. We clip to the coach-recommended maximum
    # (3/3/2/2) in case the UI somehow let extras through, then strict-filter.
    #
    # When the user has not yet picked staples, we fall through to the
    # phase-ranked default pool so a fresh account still gets a usable plan.
    clipped_proteins = (preferred_proteins or [])[:3]
    clipped_carbs = (preferred_carbs or [])[:3]
    clipped_fats = (preferred_fats or [])[:2]
    clipped_veggies = (preferred_vegetables or [])[:3]

    # Track which user picks were dropped by the phase filter (e.g. Sirloin
    # during cut) so the caller can surface a warning in the UI. We compute
    # this by diffing the user's clipped list against the filtered pool's
    # names, using the same substring matching _strict_filter uses.
    def _picks_in_pool(picks: list[str], pool: list[FoodItem]) -> tuple[list[str], list[str]]:
        survivors: list[str] = []
        dropped: list[str] = []
        pool_names = [f.name.lower() for f in pool]
        for pick in picks:
            lp = pick.lower()
            if any(lp in name for name in pool_names):
                survivors.append(pick)
            else:
                dropped.append(pick)
        return survivors, dropped

    _kept_proteins, _dropped_proteins = _picks_in_pool(clipped_proteins, proteins)
    _kept_carbs, _dropped_carbs = _picks_in_pool(clipped_carbs, carbs_all)
    _kept_fats, _dropped_fats = _picks_in_pool(clipped_fats, fats)
    _kept_veggies, _dropped_veggies = _picks_in_pool(clipped_veggies, vegetables)
    _filtered_picks = {
        "proteins": _dropped_proteins,
        "carbs": _dropped_carbs,
        "fats": _dropped_fats,
        "vegetables": _dropped_veggies,
    }

    proteins = _prioritize_preferred(_strict_filter(proteins, clipped_proteins), clipped_proteins)
    carbs_all = _prioritize_preferred(_strict_filter(carbs_all, clipped_carbs), clipped_carbs)
    fats = _prioritize_preferred(_strict_filter(fats, clipped_fats), clipped_fats)
    vegetables = _prioritize_preferred(_strict_filter(vegetables, clipped_veggies), clipped_veggies)

    # Peri-workout specific pools
    peri_proteins = [p for p in proteins if p.peri_workout] or proteins[:3]
    peri_carbs = [c for c in carbs_all if c.peri_workout] or carbs_all[:3]
    # Sustained carbs: exclude peri-workout carbs UNLESS they have breakfast/snack
    # affinity. Cream of Rice is peri_workout=True but also meal_affinity includes
    # "breakfast" — it must stay available for rest-day breakfast slots.
    sustained_carbs = [c for c in carbs_all
                       if not c.peri_workout
                       or "breakfast" in c.meal_affinity
                       or "snack" in c.meal_affinity] or carbs_all

    # Refeed override
    if is_refeed:
        fat_g = max(15.0, fat_g * 0.15)
        carbs_g = carbs_g * 1.6
        target_calories = protein_g * 4 + carbs_g * 4 + fat_g * 9

    # ── Detect early/late workout for intra-drink adjustments ──
    try:
        _h, _m = map(int, training_start_time.split(":"))
        _train_start_mins = _h * 60 + _m
    except Exception:
        _train_start_mins = 10 * 60
    _train_end_mins = _train_start_mins + training_duration_min
    # "Early workout" now means "before 7 AM AND the athlete explicitly
    # chose fasted training". Previously this was time-only, which forced
    # a blank pre-WO meal on anyone who trains at dawn. Olympia-grade coaches
    # usually prescribe a real pre-WO meal (coffee + oats + whey + banana)
    # even for 5-6 AM lifters — fasted-only is a deliberate preference.
    _is_early_workout = fasted_training and (_train_start_mins < 7 * 60)
    _is_late_workout = (_train_end_mins + 30) > 20 * 60  # post-WO after 8 PM

    # Build time slots (with intra slot if enabled)
    _include_intra = intra_workout_nutrition and is_training_day
    slots = _build_time_slots(
        meal_count, training_start_time, training_duration_min,
        is_training_day, include_intra=_include_intra,
    )

    # ── Build intra-workout drink and adjust macro budgets ──
    _intra_meal: Meal | None = None
    _intra_hbcd_g = 0.0
    _intra_eaa_protein_g = 0.0

    # Compute peri carb total before potentially adjusting for intra drink
    effective_peri_pct = max(peri_workout_carb_pct, 0.35) if is_training_day else 0
    peri_carb_total = carbs_g * effective_peri_pct if is_training_day else 0

    if _include_intra:
        _intra_meal, _intra_hbcd_g, _intra_eaa_protein_g = _build_intra_drink(
            body_weight_kg=body_weight_kg,
            session_muscles=session_muscles or [],
            training_start_time=training_start_time,
            training_duration_min=training_duration_min,
            peri_carb_budget_g=peri_carb_total,
            is_early_workout=_is_early_workout,
            is_late_workout=_is_late_workout,
        )
        # Subtract intra drink's carbs/calories from daily budgets
        carbs_g -= _intra_hbcd_g
        target_calories -= round(_intra_hbcd_g * 4 + _intra_eaa_protein_g * 4)
        peri_carb_total -= _intra_hbcd_g

    # ── Coach-realistic staple selection ──────────────────────────────────
    #
    # A real bodybuilding prep diet uses a SMALL set of foods repeated across
    # meals. A typical day: 2-3 protein sources, 2-3 carb sources, 1-2 fat
    # sources, and 1-2 vegetables rotated across every meal.
    #
    # When the user has explicitly picked staples in Settings, we rotate
    # exactly those (capped to what survived the phase filter). When they
    # haven't picked anything yet, we fall back to phase-based defaults
    # that mirror real competitor prep sheets — tighter for peak/cut,
    # looser for bulk/maintain.
    is_strict_phase = phase in ("peak", "cut")

    slot_types_in_plan = list({st for _, _, _, st in slots if st != "any"})

    def _staple_count(user_picks: list[str], pool: list[FoodItem], default: int) -> int:
        """Rotate all of the user's surviving picks, or fall back to default."""
        if user_picks and pool:
            return max(1, min(len(pool), len(user_picks)))
        return default

    protein_staple_count = _staple_count(_kept_proteins, proteins, 2 if is_strict_phase else 3)
    carb_staple_count = _staple_count(_kept_carbs, sustained_carbs, 2 if is_strict_phase else 3)
    fat_staple_count = _staple_count(_kept_fats, fats, 1 if is_strict_phase else 2)
    veg_staple_count = _staple_count(_kept_veggies, vegetables, 1 if is_strict_phase else 2)

    # Ensure breakfast proteins are included in the daily staple pool.
    # Training days: lean proteins ONLY (egg whites, yogurt) — Whole Eggs add
    # 11g fat per 100g which eats into the tight training-day fat budget.
    # Rest days: Whole Eggs OK — fat budget is larger and they add flavor/satiety.
    _BF_PROTEIN_NAMES = {"Egg Whites", "Whole Eggs", "Greek Yogurt (nonfat)", "Cottage Cheese (low-fat)"}
    if is_training_day:
        _BF_PROTEIN_NAMES = _BF_PROTEIN_NAMES - {"Whole Eggs"}
    has_breakfast_slot = "breakfast" in slot_types_in_plan
    if has_breakfast_slot:
        # Force at least one breakfast protein into the staple pool
        bf_prots = [p for p in proteins if p.name in _BF_PROTEIN_NAMES]
        non_bf_prots = [p for p in proteins if p.name not in _BF_PROTEIN_NAMES]
        if bf_prots:
            # Take 1 breakfast protein + rest from ranked list
            daily_proteins = bf_prots[:1] + _select_daily_staples(non_bf_prots, max(1, protein_staple_count - 1), slot_types_in_plan)
        else:
            daily_proteins = _select_daily_staples(proteins, protein_staple_count, slot_types_in_plan)
    else:
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
    # Count peri/non-peri slots (intra slot counted as peri but handled separately)
    food_peri_count = sum(1 for _, lbl, p, _ in slots if p and lbl != "Intra-Workout")
    non_peri_count = sum(1 for _, _, p, _ in slots if not p)

    # peri_carb_total and effective_peri_pct were computed above (before intra adjustment)
    if not _include_intra:
        # Standard path: recompute if intra wasn't enabled
        effective_peri_pct = max(peri_workout_carb_pct, 0.35) if is_training_day else 0
        peri_carb_total = carbs_g * effective_peri_pct if is_training_day else 0
    other_carb_total = carbs_g - peri_carb_total

    # When intra is enabled, split remaining peri carbs using pre:post ratio (25:22)
    if _include_intra and food_peri_count == 2:
        per_pre_carbs = peri_carb_total * (25.0 / 47.0)
        per_post_carbs = peri_carb_total * (22.0 / 47.0)
        # Late workout: halve post-WO carbs, redistribute to non-peri meals
        if _is_late_workout:
            saved = per_post_carbs * 0.5
            per_post_carbs *= 0.5
            other_carb_total += saved
    else:
        per_pre_carbs = peri_carb_total / max(1, food_peri_count)
        per_post_carbs = per_pre_carbs

    # Count food-meal slots (exclude intra drink and fasted pre-WO)
    _food_slot_count = len(slots)
    if _include_intra:
        _food_slot_count -= 1  # intra drink is not a food meal
    if _is_early_workout and _include_intra:
        _food_slot_count -= 1  # fasted pre-WO has no food
        # Redistribute fasted pre-WO carbs to non-peri meals
        other_carb_total += per_pre_carbs
        per_pre_carbs = 0.0

    per_meal_protein = protein_g / max(1, _food_slot_count)
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

    # Build dedicated breakfast protein pool.
    # Training day: lean only (Egg Whites, Yogurt) — no Whole Eggs (too much fat).
    # Rest day: Whole Eggs allowed — fat budget is larger.
    _BREAKFAST_PROTEIN_NAMES_SLOT = {
        "Egg Whites", "Whole Eggs", "Greek Yogurt (nonfat)",
        "Cottage Cheese (low-fat)",
    }
    if is_training_day:
        _BREAKFAST_PROTEIN_NAMES_SLOT = _BREAKFAST_PROTEIN_NAMES_SLOT - {"Whole Eggs"}
    breakfast_proteins = [p for p in proteins if p.name in _BREAKFAST_PROTEIN_NAMES_SLOT]
    if not breakfast_proteins:
        # No breakfast proteins in available pool (all blacklisted/filtered) — fall back
        breakfast_proteins = daily_proteins

    for idx, (mins, label, is_peri, slot_type) in enumerate(slots):
        meal_num = idx + 1
        label_str = f"Meal {meal_num} – {label}" if label != "Meal" else f"Meal {meal_num}"
        time_str = _mins_to_time(mins)
        is_pre = label == "Pre-Workout"
        is_post = label == "Post-Workout"

        # ── Intra-Workout slot: insert pre-built drink, skip food assembly ──
        if label == "Intra-Workout" and _intra_meal is not None:
            _intra_meal.meal_number = meal_num
            _intra_meal.label = f"Meal {meal_num} – Intra-Workout Drink"
            meals.append(_intra_meal)
            continue

        meal = Meal(meal_number=meal_num, label=label_str, time_str=time_str, is_peri=is_peri)

        # Per-meal targets (use pre/post specific carbs when intra is enabled)
        m_protein = per_meal_protein
        if is_pre:
            m_carbs = per_pre_carbs
        elif is_post:
            m_carbs = per_post_carbs
        elif is_peri:
            m_carbs = per_pre_carbs  # fallback for any other peri slot
        else:
            m_carbs = per_other_carbs
        m_fat = 0.0 if is_peri else per_meal_fat

        # ── Early workout: pre-WO meal is fasted (just a label, no food) ──
        if is_pre and _is_early_workout and _include_intra:
            meal.label = f"Meal {meal_num} – Pre-Workout (Fasted)"
            meal.note = "Training fasted — intra-workout drink provides fuel and anti-catabolic EAAs."
            # Skip food for this meal; redistribute carbs to other meals
            meals.append(meal)
            continue

        # ── Assembly: Pre-select protein → Carb → Fat (adjusted) → Veg → Protein ──
        # Pre-select the protein food first to estimate its fat contribution,
        # then reduce the dedicated fat source target accordingly. This prevents
        # high-fat proteins (Whole Eggs, Sirloin) from blowing the fat budget.
        incidental_protein = 0.0

        def _slot_match(pool: list[FoodItem], target_slot: str) -> list[FoodItem]:
            """Tiered affinity match.

            Tier 1: foods with the exact slot_type in meal_affinity.
                    e.g. "lunch_dinner" match → White Rice, Sweet Potato.
            Tier 2: foods with ONLY "any" affinity (no specific slot).
                    e.g. Chicken Breast, Sirloin Steak (no explicit slot set).
            Tier 3: foods with "any" PLUS a non-matching slot.
                    e.g. Egg Whites ("breakfast", "any") — used only if no
                    tier 1 or tier 2 food survives. A coach never plates
                    egg whites at dinner if chicken is available.
            """
            tier1 = [f for f in pool if target_slot in f.meal_affinity]
            if tier1:
                return tier1
            tier2 = [f for f in pool
                     if "any" in f.meal_affinity
                     and not any(s in f.meal_affinity for s in ("breakfast", "snack"))]
            if tier2:
                return tier2
            tier3 = [f for f in pool
                     if "any" in f.meal_affinity or target_slot in f.meal_affinity]
            return tier3 or pool

        # ── 0. Pre-select protein food (determine WHICH, don't scale yet) ──
        protein_food = None
        if is_peri and daily_peri_proteins:
            protein_food = daily_peri_proteins[_peri_prot_idx % len(daily_peri_proteins)]
            _peri_prot_idx += 1
        elif slot_type == "breakfast" and breakfast_proteins:
            protein_food = breakfast_proteins[_prot_idx % len(breakfast_proteins)]
            _prot_idx += 1
        elif daily_proteins:
            affinity_match = _slot_match(daily_proteins, slot_type)
            protein_food = affinity_match[_prot_idx % len(affinity_match)]
            _prot_idx += 1

        # Estimate protein food's fat contribution so we can budget for it
        est_prot_fat = 0.0
        if protein_food and protein_food.fat > 0.5 and protein_food.protein > 0:
            est_qty = (m_protein / protein_food.protein) * 100
            est_prot_fat = est_qty * protein_food.fat / 100

        # ── 1. Vegetable (non-peri, non-refeed, non-breakfast) ──
        # Vegetables are plated FIRST so their carbs are subtracted from the
        # meal's carb budget before the dedicated carb source is scaled.
        # Coach principle: every lunch/dinner/snack gets a veg; breakfast
        # stays clean (oats/eggs/yogurt are not typically plated with
        # broccoli). This is also where we track `incidental_veg_carbs` so
        # the carb source shrinks to make room.
        incidental_veg_carbs = 0.0
        if not is_peri and not is_refeed and daily_vegs and slot_type != "breakfast":
            veg_food = daily_vegs[_veg_idx % len(daily_vegs)]
            _veg_idx += 1
            item = _scale_food(veg_food, veg_food.typical_serving_g)
            meal.ingredients.append(item)
            incidental_protein += item.protein_g
            incidental_veg_carbs = item.carbs_g

        # ── 2. Carb source — scaled to remaining budget after veg ──
        carb_budget = max(0.0, m_carbs - incidental_veg_carbs)
        if carb_budget > 5:
            carb_food = None
            if is_peri and daily_peri_carbs:
                carb_food = daily_peri_carbs[_peri_carb_idx % len(daily_peri_carbs)]
                _peri_carb_idx += 1
            elif daily_carbs:
                affinity_match = _slot_match(daily_carbs, slot_type)
                carb_food = affinity_match[_carb_idx % len(affinity_match)]
                _carb_idx += 1

            if carb_food:
                item = _scale_food_to_carbs(carb_food, carb_budget)
                meal.ingredients.append(item)
                m_fat = max(0, m_fat - item.fat_g)
                incidental_protein += item.protein_g

        # ── 3. Fat source — subtract estimated protein fat from budget ──
        fat_budget = max(0, m_fat - est_prot_fat)
        if not is_peri and fat_budget > 3 and daily_fats:
            fat_food = daily_fats[_fat_idx % len(daily_fats)]
            _fat_idx += 1
            item = _scale_food_to_fat(fat_food, fat_budget)
            meal.ingredients.append(item)
            incidental_protein += item.protein_g

        # ── 4. Protein source — adjusted for incidental protein ──
        adjusted_protein = max(10.0, m_protein - incidental_protein)
        if protein_food:
            item = _scale_food_to_protein(protein_food, adjusted_protein)
            meal.ingredients.insert(0, item)  # display protein first

        meals.append(meal)

    # ── Macro Reconciliation Pass ──────────────────────────────────────────
    # Protein sources contribute incidental carbs/fat, and carb sources
    # contribute incidental protein/fat.  After building all meals, compute
    # the cumulative error and proportionally adjust the LAST non-peri meal
    # so daily totals land within ±5% of prescriptions.
    #
    # This is exactly what a real prep coach does when writing meal plans —
    # the last meal of the day is the "adjustment meal" that absorbs rounding.
    # Find last non-peri meal to adjust (the "flex meal")
    flex_meal = None
    for m in reversed(meals):
        if not m.is_peri and m.ingredients:
            flex_meal = m
            break

    if flex_meal and len(flex_meal.ingredients) >= 2:
        # Two-pass bidirectional reconciliation — like a real coach tweaking
        # the spreadsheet, checking totals, then adjusting again.
        for _pass in range(2):
            total_p = sum(i.protein_g for m in meals for i in m.ingredients)
            total_c = sum(i.carbs_g for m in meals for i in m.ingredients)
            total_f = sum(i.fat_g for m in meals for i in m.ingredients)

            # EAA protein from the intra drink is intentionally additive —
            # it's supplemental MPS signaling, not replacing whole-food protein.
            # Exclude it from the protein error so reconciliation doesn't shrink
            # food protein to compensate for the EAA bonus.
            p_err = (total_p - _intra_eaa_protein_g) - protein_g
            c_err = total_c - carbs_g
            f_err = total_f - fat_g

            # Adjust carb source (bidirectional, floor at 50% to prevent tiny servings)
            carb_items = [i for i in flex_meal.ingredients
                          if i.carbs_g > 10 and i.protein_g < i.carbs_g]
            if carb_items and abs(c_err) > 5:
                ci = carb_items[0]
                if ci.carbs_g > 0:
                    ratio = min(1.5, max(0.5, 1.0 - c_err / ci.carbs_g))
                    ci.quantity_g = round(ci.quantity_g * ratio)
                    ci.protein_g = round(ci.protein_g * ratio, 1)
                    ci.carbs_g = round(ci.carbs_g * ratio, 1)
                    ci.fat_g = round(ci.fat_g * ratio, 1)
                    ci.calories = round(ci.calories * ratio)

            # Adjust protein source (bidirectional, floor at 50%)
            prot_items = [i for i in flex_meal.ingredients
                          if i.protein_g > 10 and i.protein_g > i.carbs_g]
            if prot_items and abs(p_err) > 5:
                pi = prot_items[0]
                if pi.protein_g > 0:
                    ratio = min(1.5, max(0.5, 1.0 - p_err / pi.protein_g))
                    pi.quantity_g = round(pi.quantity_g * ratio)
                    pi.protein_g = round(pi.protein_g * ratio, 1)
                    pi.carbs_g = round(pi.carbs_g * ratio, 1)
                    pi.fat_g = round(pi.fat_g * ratio, 1)
                    pi.calories = round(pi.calories * ratio)

            # Adjust fat source (bidirectional, floor at 50%)
            fat_items = [i for i in flex_meal.ingredients
                         if i.fat_g > 3 and i.fat_g > i.protein_g]
            if fat_items and abs(f_err) > 3:
                fi = fat_items[0]
                if fi.fat_g > 0:
                    ratio = min(1.5, max(0.5, 1.0 - f_err / fi.fat_g))
                    fi.quantity_g = round(fi.quantity_g * ratio)
                    fi.protein_g = round(fi.protein_g * ratio, 1)
                    fi.carbs_g = round(fi.carbs_g * ratio, 1)
                    fi.fat_g = round(fi.fat_g * ratio, 1)
                    fi.calories = round(fi.calories * ratio)

    return [m.to_dict() for m in meals]
