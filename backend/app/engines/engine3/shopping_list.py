"""
Engine 3 — Weekly Shopping List Generator

Aggregates all ingredients from training-day and rest-day meal plans
across a full week into a consolidated, grocery-section-organized
shopping list with realistic purchase quantities.
"""
from __future__ import annotations

import math
from collections import defaultdict


# Grocery section mapping for common bodybuilding foods
_GROCERY_SECTIONS: dict[str, str] = {
    # Proteins — Meat & Seafood
    "Chicken Breast": "meat_seafood",
    "Turkey Breast": "meat_seafood",
    "Ground Turkey (93/7)": "meat_seafood",
    "Lean Ground Beef (96/4)": "meat_seafood",
    "Lean Ground Beef (93/7)": "meat_seafood",
    "Sirloin Steak": "meat_seafood",
    "Flank Steak": "meat_seafood",
    "Eye of Round": "meat_seafood",
    "Pork Tenderloin": "meat_seafood",
    "Tilapia": "meat_seafood",
    "Cod": "meat_seafood",
    "Halibut": "meat_seafood",
    "Salmon": "meat_seafood",
    "Shrimp": "meat_seafood",
    "Canned Tuna (in water)": "canned_goods",
    "Ground Bison (93/7)": "meat_seafood",
    "Mahi Mahi": "meat_seafood",
    "Scallops": "meat_seafood",
    "Turkey Bacon": "meat_seafood",
    # Dairy & Eggs
    "Whole Eggs": "dairy_eggs",
    "Egg Whites": "dairy_eggs",
    "Egg Yolks": "dairy_eggs",
    "Greek Yogurt (nonfat)": "dairy_eggs",
    "Cottage Cheese (low-fat)": "dairy_eggs",
    # Plant proteins
    "Tofu (firm)": "produce",
    "Tempeh": "produce",
    "Seitan": "produce",
    "Edamame": "frozen",
    # Supplements
    "Whey Protein Isolate": "supplements",
    "Casein Protein Powder": "supplements",
    # Grains & Carbs
    "Oats (rolled)": "grains_bread",
    "Brown Rice (cooked)": "grains_bread",
    "White Rice (cooked)": "grains_bread",
    "Jasmine Rice (cooked)": "grains_bread",
    "Basmati Rice (cooked)": "grains_bread",
    "Cream of Rice (dry)": "grains_bread",
    "Cream of Wheat": "grains_bread",
    "Quinoa (cooked)": "grains_bread",
    "Ezekiel Bread": "grains_bread",
    "Sourdough Bread": "grains_bread",
    "Plain Bagel": "grains_bread",
    "Corn Tortillas": "grains_bread",
    "Whole Wheat Pasta (cooked)": "grains_bread",
    "White Pasta (cooked)": "grains_bread",
    "Rice Cakes": "grains_bread",
    # Produce — Starches
    "Sweet Potato": "produce",
    "Russet Potato (baked)": "produce",
    "Red Potato (boiled)": "produce",
    # Produce — Vegetables
    "Broccoli": "produce",
    "Asparagus": "produce",
    "Spinach": "produce",
    "Green Beans": "produce",
    "Bell Peppers": "produce",
    "Zucchini": "produce",
    "Cucumber": "produce",
    "Kale": "produce",
    "Cauliflower": "produce",
    # Produce — Fruits
    "Banana": "produce",
    "Blueberries": "produce",
    "Strawberries": "produce",
    "Apple": "produce",
    "Pineapple": "produce",
    "Mango": "produce",
    "Grapes": "produce",
    "Watermelon": "produce",
    "Dates (Medjool)": "produce",
    "Dates (whole)": "produce",
    # Nuts, Seeds, Oils
    "Natural Peanut Butter": "nuts_seeds",
    "Almond Butter": "nuts_seeds",
    "Almonds": "nuts_seeds",
    "Walnuts": "nuts_seeds",
    "Macadamia Nuts": "nuts_seeds",
    "Cashews": "nuts_seeds",
    "Chia Seeds": "nuts_seeds",
    "Flaxseeds (ground)": "nuts_seeds",
    "Extra Virgin Olive Oil": "oils_condiments",
    "Coconut Oil": "oils_condiments",
    "MCT Oil": "oils_condiments",
    "Avocado": "produce",
}

_SECTION_ORDER = [
    "meat_seafood", "dairy_eggs", "produce", "grains_bread",
    "nuts_seeds", "oils_condiments", "canned_goods", "frozen",
    "supplements", "other",
]

_SECTION_LABELS = {
    "meat_seafood": "Meat & Seafood",
    "dairy_eggs": "Dairy & Eggs",
    "produce": "Produce",
    "grains_bread": "Grains & Bread",
    "nuts_seeds": "Nuts & Seeds",
    "oils_condiments": "Oils & Condiments",
    "canned_goods": "Canned Goods",
    "frozen": "Frozen",
    "supplements": "Supplements",
    "other": "Other",
}

# Common unit conversions for display
_UNIT_HINTS: dict[str, str] = {
    "Chicken Breast": "~{n} breasts",
    "Turkey Breast": "~{n} portions",
    "Whole Eggs": "~{n} eggs",
    "Egg Whites": "~{n} egg whites",
    "Banana": "~{n} bananas",
    "Apple": "~{n} apples",
    "Avocado": "~{n} avocados",
    "Sweet Potato": "~{n} potatoes",
    "Russet Potato (baked)": "~{n} potatoes",
    "Red Potato (boiled)": "~{n} potatoes",
}

_UNIT_SIZES: dict[str, float] = {
    "Chicken Breast": 170,
    "Turkey Breast": 170,
    "Whole Eggs": 50,
    "Egg Whites": 33,
    "Banana": 120,
    "Apple": 180,
    "Avocado": 75,
    "Sweet Potato": 200,
    "Russet Potato (baked)": 250,
    "Red Potato (boiled)": 150,
}


def _round_up_to(value: float, increment: float) -> float:
    """Round up to the nearest increment (e.g., nearest 100g)."""
    return math.ceil(value / increment) * increment


def generate_weekly_shopping_list(
    training_day_meals: list[dict],
    rest_day_meals: list[dict],
    training_days_per_week: int = 5,
) -> dict:
    """
    Aggregate ingredients from training and rest day meal plans into
    a weekly shopping list.

    Args:
        training_day_meals: List of meal dicts from meal_planner for training days.
        rest_day_meals: List of meal dicts from meal_planner for rest days.
        training_days_per_week: Number of training days (rest = 7 - training).

    Returns:
        Dict with:
          - items: list of shopping items grouped by grocery section
          - totals: weekly macro totals
          - section_order: ordered list of section keys
    """
    rest_days = 7 - training_days_per_week

    # Aggregate all ingredients across the week
    ingredient_totals: dict[str, dict] = defaultdict(lambda: {
        "quantity_g": 0.0, "protein_g": 0.0, "carbs_g": 0.0, "fat_g": 0.0, "calories": 0.0,
    })

    for meals, day_count in [(training_day_meals, training_days_per_week), (rest_day_meals, rest_days)]:
        for meal in meals:
            for ing in meal.get("ingredients", []):
                name = ing["name"]
                ingredient_totals[name]["quantity_g"] += ing["quantity_g"] * day_count
                ingredient_totals[name]["protein_g"] += ing.get("protein_g", 0) * day_count
                ingredient_totals[name]["carbs_g"] += ing.get("carbs_g", 0) * day_count
                ingredient_totals[name]["fat_g"] += ing.get("fat_g", 0) * day_count
                ingredient_totals[name]["calories"] += ing.get("calories", 0) * day_count

    # Build shopping list items with rounded quantities and section grouping
    items_by_section: dict[str, list[dict]] = defaultdict(list)
    weekly_totals = {"protein_g": 0, "carbs_g": 0, "fat_g": 0, "calories": 0}

    for name, totals in sorted(ingredient_totals.items()):
        raw_g = totals["quantity_g"]
        # Round up to nearest 50g for small items, 100g for larger
        purchase_g = _round_up_to(raw_g, 50 if raw_g < 500 else 100)

        section = _GROCERY_SECTIONS.get(name, "other")

        # Human-readable unit hint
        unit_hint = None
        if name in _UNIT_HINTS and name in _UNIT_SIZES:
            count = math.ceil(raw_g / _UNIT_SIZES[name])
            unit_hint = _UNIT_HINTS[name].format(n=count)

        item = {
            "name": name,
            "quantity_g": round(purchase_g),
            "quantity_display": f"{round(purchase_g)}g",
            "unit_hint": unit_hint,
            "weekly_protein_g": round(totals["protein_g"], 1),
            "weekly_carbs_g": round(totals["carbs_g"], 1),
            "weekly_fat_g": round(totals["fat_g"], 1),
            "weekly_calories": round(totals["calories"]),
        }
        items_by_section[section].append(item)

        weekly_totals["protein_g"] += totals["protein_g"]
        weekly_totals["carbs_g"] += totals["carbs_g"]
        weekly_totals["fat_g"] += totals["fat_g"]
        weekly_totals["calories"] += totals["calories"]

    # Build ordered output
    sections = []
    for section_key in _SECTION_ORDER:
        if section_key in items_by_section:
            sections.append({
                "section": section_key,
                "label": _SECTION_LABELS.get(section_key, section_key),
                "items": items_by_section[section_key],
            })

    return {
        "sections": sections,
        "total_items": sum(len(s["items"]) for s in sections),
        "weekly_totals": {k: round(v) for k, v in weekly_totals.items()},
        "training_days": training_days_per_week,
        "rest_days": rest_days,
    }
