"""
Build ingredient_master seed data from USDA FoodData Central.

Filters to bodybuilding-relevant foods (whole foods, single ingredients)
and extracts calories, protein, carbs, fat, fiber per 100g.

Output: backend/app/constants/ingredients.py
"""
import csv
import os
import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "FoodData_Central_foundation_food_csv_2025-12-18"
OUT_FILE = Path(__file__).parent.parent / "backend/app/constants/ingredients.py"

# Bodybuilding-relevant food category IDs
RELEVANT_CATEGORIES = {
    "1",   # Dairy and Egg Products
    "4",   # Fats and Oils
    "5",   # Poultry Products
    "10",  # Pork Products
    "11",  # Vegetables and Vegetable Products
    "12",  # Nut and Seed Products
    "13",  # Beef Products
    "15",  # Finfish and Shellfish Products
    "16",  # Legumes and Legume Products
    "17",  # Lamb, Veal, and Game Products
    "20",  # Cereal Grains and Pasta
}

# Nutrient IDs we care about
NUTRIENT_IDS = {
    "2047": "calories",   # Energy (Atwater General Factors), kcal
    "1008": "calories",   # Energy (fallback), kcal
    "1003": "protein_g",  # Protein
    "1004": "fat_g",      # Total lipid (fat)
    "1005": "carbs_g",    # Carbohydrate, by difference
    "1079": "fiber_g",    # Fiber, total dietary
}

# Skip words indicating processed/mixed foods
SKIP_WORDS = [
    "soup", "sauce", "gravy", "baby food", "formula", "infant",
    "frozen meal", "dinner", "entree", "casserole", "stew",
    "mixed", "salad dressing", "marinade", "pickle", "relish",
    "candied", "glazed", "cured", "smoked sausage", "hot dog",
    "USDA commodity", "ns as to", "NFS",
]

def load_foods():
    foods = {}
    with open(DATA_DIR / "food.csv") as f:
        for row in csv.DictReader(f):
            cat = row.get("food_category_id", "")
            if cat not in RELEVANT_CATEGORIES:
                continue
            desc = row["description"].strip()
            # Skip processed/mixed items
            if any(w.lower() in desc.lower() for w in SKIP_WORDS):
                continue
            foods[row["fdc_id"]] = {
                "fdc_id": row["fdc_id"],
                "name": desc,
                "category_id": cat,
                "calories": None,
                "protein_g": None,
                "fat_g": None,
                "carbs_g": None,
                "fiber_g": None,
            }
    print(f"Loaded {len(foods)} candidate foods")
    return foods

def load_nutrients(foods):
    filled = 0
    with open(DATA_DIR / "food_nutrient.csv") as f:
        for row in csv.DictReader(f):
            fdc_id = row["fdc_id"]
            if fdc_id not in foods:
                continue
            nutrient_id = row["nutrient_id"]
            if nutrient_id not in NUTRIENT_IDS:
                continue
            field = NUTRIENT_IDS[nutrient_id]
            val = row["amount"]
            if val and val.strip():
                try:
                    amount = float(val)
                    # Only set calories once (prefer 2047 over 1008)
                    if field == "calories":
                        if foods[fdc_id]["calories"] is None or nutrient_id == "2047":
                            foods[fdc_id]["calories"] = amount
                    elif foods[fdc_id][field] is None:
                        foods[fdc_id][field] = amount
                    filled += 1
                except ValueError:
                    pass
    print(f"Filled {filled} nutrient values")
    return foods

def deduplicate_and_score(foods):
    """Keep the best entry for each food name (prefer entries with all 4 macros)."""
    by_name = {}
    for fdc_id, food in foods.items():
        # Must have at least calories and protein
        if food["calories"] is None or food["protein_g"] is None:
            continue
        # Set defaults for missing values
        food["fat_g"] = food["fat_g"] or 0.0
        food["carbs_g"] = food["carbs_g"] or 0.0
        food["fiber_g"] = food["fiber_g"] or 0.0

        name = food["name"].lower()
        # Score: prefer entries with all macros
        score = sum(1 for f in ["calories", "protein_g", "fat_g", "carbs_g", "fiber_g"]
                   if food[f] is not None and food[f] > 0)

        if name not in by_name or score > by_name[name]["score"]:
            by_name[name] = {**food, "score": score}

    return list(by_name.values())

def clean_name(name):
    """Normalize food name for display."""
    # Title case, remove trailing commas
    name = name.strip().rstrip(",")
    # Shorten very long names
    if len(name) > 80:
        name = name[:77] + "..."
    return name

def main():
    print("Loading foods...")
    foods = load_foods()
    print("Loading nutrients...")
    foods = load_nutrients(foods)
    print("Deduplicating...")
    unique = deduplicate_and_score(foods)
    print(f"Unique foods with macros: {len(unique)}")

    # Sort by category then name
    unique.sort(key=lambda x: (x["category_id"], x["name"]))

    # Build the output
    lines = [
        '"""',
        'Ingredient Master Seed Data',
        '',
        'Derived from USDA FoodData Central Foundation Foods dataset.',
        'All values are per 100g of food.',
        '',
        'Format: (name, calories_kcal, protein_g, carbs_g, fat_g, fiber_g)',
        '"""',
        '',
        'INGREDIENT_SEED: list[tuple[str, float, float, float, float, float]] = [',
    ]

    for food in unique:
        name = clean_name(food["name"])
        name_escaped = name.replace('"', '\\"').replace("'", "\\'")
        cal = round(food["calories"] or 0, 1)
        prot = round(food["protein_g"] or 0, 1)
        carb = round(food["carbs_g"] or 0, 1)
        fat = round(food["fat_g"] or 0, 1)
        fib = round(food["fiber_g"] or 0, 1)
        lines.append(f'    ("{name_escaped}", {cal}, {prot}, {carb}, {fat}, {fib}),')

    lines.append(']')
    lines.append('')
    lines.append(f'# {len(unique)} foods total')
    lines.append('')

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_FILE, "w") as f:
        f.write("\n".join(lines))

    print(f"Written to {OUT_FILE}")
    print(f"Total ingredients: {len(unique)}")

    # Show sample
    print("\nSample (first 10):")
    for food in unique[:10]:
        print(f"  {clean_name(food['name'])}: {food['calories']}kcal, {food['protein_g']}g protein")

if __name__ == "__main__":
    main()
