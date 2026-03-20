"""
Build exercise seed data from MegaGym dataset.

Maps MegaGym body parts → our muscle group schema.
Assigns biomechanical efficiency and fatigue ratios based on
exercise type and equipment.

Output: backend/app/constants/exercises_full.py
"""
import csv
from pathlib import Path

DATA_FILE = Path(__file__).parent.parent / "megaGymDataset.csv"
OUT_FILE = Path(__file__).parent.parent / "backend/app/constants/exercises_full.py"

# Map MegaGym body parts → our primary_muscle names
BODYPART_MAP = {
    "Chest": "chest",
    "Lats": "back",
    "Middle Back": "back",
    "Lower Back": "lower_back",
    "Shoulders": "shoulders",
    "Biceps": "biceps",
    "Triceps": "triceps",
    "Forearms": "forearms",
    "Abdominals": "abs",
    "Quadriceps": "quads",
    "Hamstrings": "hamstrings",
    "Glutes": "glutes",
    "Calves": "calves",
    "Traps": "traps",
    "Abductors": "abductors",
    "Adductors": "adductors",
    "Neck": "neck",
}

# Secondary muscle heuristics based on body part + equipment
SECONDARY_MUSCLES = {
    "chest": ["triceps", "shoulders"],
    "back": ["biceps", "rear_delts"],
    "lower_back": ["glutes", "hamstrings"],
    "shoulders": ["triceps", "traps"],
    "biceps": ["forearms"],
    "triceps": ["shoulders"],
    "quads": ["glutes", "hamstrings"],
    "hamstrings": ["glutes", "lower_back"],
    "glutes": ["hamstrings", "quads"],
    "abs": ["lower_back"],
    "calves": [],
    "traps": ["back", "shoulders"],
    "forearms": [],
    "abductors": ["glutes"],
    "adductors": ["glutes"],
    "neck": [],
}

# Efficiency scores by equipment type (how well it loads the target muscle)
EQUIPMENT_EFFICIENCY = {
    "Barbell": 1.0,
    "Dumbbell": 0.92,
    "Cable": 0.88,
    "Machine": 0.80,
    "E-Z Curl Bar": 0.90,
    "Kettlebells": 0.85,
    "Body Only": 0.75,
    "Bands": 0.70,
    "Exercise Ball": 0.65,
    "Medicine Ball": 0.65,
    "Foam Roll": 0.50,
    "None": 0.60,
    "Other": 0.70,
}

# Fatigue ratios by type + equipment (systemic cost relative to stimulus)
def get_fatigue(ex_type, equipment, body_part):
    # Base fatigue from equipment (heavier = more fatigue)
    base = {
        "Barbell": 0.90,
        "Dumbbell": 0.75,
        "Cable": 0.60,
        "Machine": 0.50,
        "E-Z Curl Bar": 0.65,
        "Kettlebells": 0.70,
        "Body Only": 0.55,
        "Bands": 0.40,
        "Exercise Ball": 0.35,
        "Medicine Ball": 0.45,
        "Foam Roll": 0.20,
        "None": 0.45,
        "Other": 0.50,
    }.get(equipment, 0.60)

    # Large compound muscle groups add systemic fatigue
    if body_part in ("Quadriceps", "Hamstrings", "Glutes", "Lower Back", "Lats", "Middle Back"):
        base = min(1.0, base + 0.10)
    # Isolation / small muscles reduce systemic fatigue
    elif body_part in ("Biceps", "Triceps", "Calves", "Forearms", "Neck"):
        base = max(0.20, base - 0.15)

    return round(base, 2)

# Types to include (bodybuilding-relevant)
INCLUDE_TYPES = {"Strength", "Powerlifting", "Olympic Weightlifting"}

# Equipment to exclude (non-gym)
EXCLUDE_EQUIPMENT = {"Foam Roll", "Medicine Ball", "Exercise Ball"}

# Minimum exercises per muscle group
TARGET_PER_GROUP = 8

def main():
    exercises = []
    seen_names = set()

    with open(DATA_FILE) as f:
        for row in csv.DictReader(f):
            ex_type = row["Type"].strip()
            equipment = row["Equipment"].strip()
            body_part = row["BodyPart"].strip()
            name = row["Title"].strip()
            level = row["Level"].strip()

            # Filter
            if ex_type not in INCLUDE_TYPES:
                continue
            if equipment in EXCLUDE_EQUIPMENT:
                continue
            if body_part not in BODYPART_MAP:
                continue
            if not name:
                continue

            # Deduplicate by name (case-insensitive)
            name_lower = name.lower()
            if name_lower in seen_names:
                continue
            seen_names.add(name_lower)

            primary = BODYPART_MAP[body_part]
            secondary = SECONDARY_MUSCLES.get(primary, [])
            efficiency = EQUIPMENT_EFFICIENCY.get(equipment, 0.75)
            fatigue = get_fatigue(ex_type, equipment, body_part)

            exercises.append({
                "name": name,
                "primary_muscle": primary,
                "secondary_muscles": secondary,
                "equipment": equipment.lower().replace("-", "_").replace(" ", "_"),
                "movement_pattern": ex_type.lower().replace(" ", "_"),
                "level": level.lower() if level else "intermediate",
                "efficiency": efficiency,
                "fatigue_ratio": fatigue,
            })

    print(f"Total exercises after filtering: {len(exercises)}")

    # Count per muscle group
    from collections import Counter
    counts = Counter(e["primary_muscle"] for e in exercises)
    print("\nExercises per muscle group:")
    for muscle, count in sorted(counts.items()):
        print(f"  {muscle}: {count}")

    # Write output
    lines = [
        '"""',
        'Full Exercise Database',
        '',
        'Derived from MegaGym dataset (2918 exercises, filtered to',
        'strength/powerlifting/olympic weightlifting with gym equipment).',
        '',
        'Format: (name, primary_muscle, secondary_muscles, equipment,',
        '         movement_pattern, level, efficiency, fatigue_ratio)',
        '',
        'efficiency: 0-1.0, how well the exercise loads the target muscle',
        'fatigue_ratio: 0-1.0, systemic fatigue cost relative to stimulus',
        '"""',
        'from typing import NamedTuple',
        '',
        '',
        'class ExerciseRecord(NamedTuple):',
        '    name: str',
        '    primary_muscle: str',
        '    secondary_muscles: list[str]',
        '    equipment: str',
        '    movement_pattern: str',
        '    level: str',
        '    efficiency: float',
        '    fatigue_ratio: float',
        '',
        '',
        'EXERCISE_DATABASE: list[ExerciseRecord] = [',
    ]

    for ex in exercises:
        sec = json_list(ex["secondary_muscles"])
        lines.append(
            f'    ExerciseRecord('
            f'name={repr(ex["name"])}, '
            f'primary_muscle={repr(ex["primary_muscle"])}, '
            f'secondary_muscles={sec}, '
            f'equipment={repr(ex["equipment"])}, '
            f'movement_pattern={repr(ex["movement_pattern"])}, '
            f'level={repr(ex["level"])}, '
            f'efficiency={ex["efficiency"]}, '
            f'fatigue_ratio={ex["fatigue_ratio"]}),'
        )

    lines.append(']')
    lines.append('')
    lines.append(f'# {len(exercises)} exercises total')

    with open(OUT_FILE, "w") as f:
        f.write("\n".join(lines))

    print(f"\nWritten to {OUT_FILE}")


def json_list(lst):
    return "[" + ", ".join(repr(x) for x in lst) + "]"


if __name__ == "__main__":
    import json
    main()
