"""
Curated Competitive Bodybuilding Exercise Database — 191 exercises

Every exercise verified against Olympia-level training programs from Hany Rambod,
John Meadows, Kim Oddo, Chris Bumstead, Phil Heath, Brandon Hendrickson, Jeremy
Buendia, Cydney Gillon, Francielle Mattos, and others.

Exercise names are designed to match the keyword cascades in exercise_priorities.py.
primary_muscle uses delt sub-groups (front_delt/side_delt/rear_delt) for proper
shoulder volume partitioning.

Equipment values are frontend-compatible: barbell, dumbbell, cable, machine,
smith_machine, bodyweight, ez_bar.

load_type drives the resistance progression system:
  plates        — barbells, EZ-bars (5 kg / 2.5 kg increments)
  plate_loaded  — Hammer Strength, leg press, hack squat (10 kg increments)
  machine_plates— pin-loaded selectorized stacks (2.5 kg increments)
  cable         — cable-pulley pin stacks (2.5 kg increments)
  dumbbells     — standard pairs (2.5 kg per DB increments)
  bodyweight    — rep-ceiling then add 2.5 kg via belt/vest
"""

from typing import NamedTuple


class CuratedExercise(NamedTuple):
    name: str               # display name (max 100 chars), keyword-compatible
    primary_muscle: str      # DB primary_muscle: delt sub-groups, standard names
    secondary_muscles: list[str]
    equipment: str           # frontend name: barbell/dumbbell/cable/machine/smith_machine/bodyweight/ez_bar
    movement_pattern: str    # push/pull/squat/hinge/isolation/lunge
    load_type: str           # plates/plate_loaded/machine_plates/cable/dumbbells/bodyweight
    efficiency: float        # biomechanical efficiency 0.0–1.0
    fatigue_ratio: float     # systemic fatigue cost 0.0–1.0


CURATED_EXERCISES: list[CuratedExercise] = [

    # =========================================================================
    # CHEST (22 exercises)
    # =========================================================================
    CuratedExercise("Barbell Bench Press",              "chest", ["front_delt", "triceps"],  "barbell",       "push", "plates",        0.95, 0.80),
    CuratedExercise("Incline Barbell Press",            "chest", ["front_delt", "triceps"],  "barbell",       "push", "plates",        0.92, 0.75),
    CuratedExercise("Incline Dumbbell Press",           "chest", ["front_delt", "triceps"],  "dumbbell",      "push", "dumbbells",     0.90, 0.70),
    CuratedExercise("Dumbbell Bench Press",             "chest", ["front_delt", "triceps"],  "dumbbell",      "push", "dumbbells",     0.88, 0.68),
    CuratedExercise("Decline Barbell Press",            "chest", ["front_delt", "triceps"],  "barbell",       "push", "plates",        0.90, 0.75),
    CuratedExercise("Hammer Strength Incline Press",    "chest", ["front_delt", "triceps"],  "machine",       "push", "plate_loaded",  0.85, 0.50),
    CuratedExercise("Hammer Strength Flat Press",       "chest", ["front_delt", "triceps"],  "machine",       "push", "plate_loaded",  0.83, 0.48),
    CuratedExercise("Seated Machine Chest Press",       "chest", ["front_delt", "triceps"],  "machine",       "push", "machine_plates", 0.80, 0.42),
    CuratedExercise("Smith Machine Incline Press",      "chest", ["front_delt", "triceps"],  "smith_machine", "push", "plate_loaded",  0.82, 0.55),
    CuratedExercise("Smith Machine Bench Press",        "chest", ["front_delt", "triceps"],  "smith_machine", "push", "plate_loaded",  0.80, 0.55),
    CuratedExercise("Decline Smith Machine Press",      "chest", ["triceps", "front_delt"],  "smith_machine", "push", "plate_loaded",  0.78, 0.50),
    CuratedExercise("Close-Grip Bench Press",           "chest", ["triceps", "front_delt"],  "barbell",       "push", "plates",        0.85, 0.70),
    CuratedExercise("Parallel Bar Dips",                "chest", ["triceps", "front_delt"],  "bodyweight",    "push", "bodyweight",    0.85, 0.60),
    CuratedExercise("Machine Dip",                      "chest", ["triceps"],                "machine",       "push", "machine_plates", 0.78, 0.40),
    CuratedExercise("Pec Deck Machine Fly",             "chest", ["front_delt"],             "machine",       "isolation", "machine_plates", 0.75, 0.28),
    CuratedExercise("Cable Fly (Crossover)",            "chest", ["front_delt"],             "cable",         "isolation", "cable",     0.72, 0.28),
    CuratedExercise("Incline Dumbbell Fly",             "chest", ["front_delt"],             "dumbbell",      "isolation", "dumbbells", 0.70, 0.30),
    CuratedExercise("High-to-Low Cable Fly",            "chest", ["front_delt"],             "cable",         "isolation", "cable",     0.70, 0.28),
    CuratedExercise("Incline Machine Fly",              "chest", ["front_delt"],             "machine",       "isolation", "machine_plates", 0.72, 0.25),
    CuratedExercise("Hex Press",                        "chest", ["triceps", "front_delt"],  "dumbbell",      "push", "dumbbells",     0.72, 0.45),
    CuratedExercise("Svend Press",                      "chest", ["front_delt"],             "bodyweight",    "isolation", "bodyweight", 0.55, 0.15),
    CuratedExercise("Gironda Dip",                      "chest", ["front_delt"],             "bodyweight",    "push", "bodyweight",    0.78, 0.55),

    # =========================================================================
    # BACK (26 exercises)
    # =========================================================================
    CuratedExercise("Wide-Grip Lat Pulldown",           "back", ["biceps", "rear_delt"],           "cable",    "pull", "cable",         0.85, 0.40),
    CuratedExercise("Close-Grip Lat Pulldown",          "back", ["biceps"],                        "cable",    "pull", "cable",         0.83, 0.38),
    CuratedExercise("Underhand Lat Pulldown",           "back", ["biceps"],                        "cable",    "pull", "cable",         0.82, 0.38),
    CuratedExercise("Single-Arm Lat Pulldown",          "back", ["biceps"],                        "cable",    "pull", "cable",         0.78, 0.32),
    CuratedExercise("Wide-Grip Pull-Up",                "back", ["biceps", "rear_delt"],           "bodyweight","pull", "bodyweight",   0.90, 0.55),
    CuratedExercise("Weighted Chin-Up",                 "back", ["biceps", "forearms"],            "bodyweight","pull", "bodyweight",   0.92, 0.60),
    CuratedExercise("Bent-Over Barbell Row",            "back", ["biceps", "rear_delt"],           "barbell",  "pull", "plates",        0.95, 0.80),
    CuratedExercise("Underhand Barbell Row",            "back", ["biceps"],                        "barbell",  "pull", "plates",        0.92, 0.78),
    CuratedExercise("Meadows Row",                      "back", ["rear_delt", "biceps"],           "barbell",  "pull", "plates",        0.88, 0.65),
    CuratedExercise("One-Arm Dumbbell Row",             "back", ["biceps", "rear_delt"],           "dumbbell", "pull", "dumbbells",     0.88, 0.60),
    CuratedExercise("T-Bar Row",                        "back", ["biceps", "rear_delt"],           "barbell",  "pull", "plates",        0.92, 0.75),
    CuratedExercise("Chest-Supported T-Bar Row",        "back", ["biceps", "rear_delt"],           "machine",  "pull", "plate_loaded",  0.85, 0.50),
    CuratedExercise("Chest-Supported Dumbbell Row",     "back", ["biceps"],                        "dumbbell", "pull", "dumbbells",     0.82, 0.45),
    CuratedExercise("Seated Cable Row",                 "back", ["biceps", "rear_delt"],           "cable",    "pull", "cable",         0.85, 0.40),
    CuratedExercise("Single-Arm Cable Row",             "back", ["biceps"],                        "cable",    "pull", "cable",         0.80, 0.35),
    CuratedExercise("Wide-Grip Cable Row",              "back", ["rear_delt", "biceps"],           "cable",    "pull", "cable",         0.82, 0.38),
    CuratedExercise("Hammer Strength Machine Row",      "back", ["biceps"],                        "machine",  "pull", "plate_loaded",  0.83, 0.45),
    CuratedExercise("Seated Machine Row",               "back", ["biceps", "rear_delt"],           "machine",  "pull", "machine_plates", 0.80, 0.38),
    CuratedExercise("Machine Low Row",                  "back", ["biceps"],                        "machine",  "pull", "machine_plates", 0.78, 0.35),
    CuratedExercise("Rack Pull",                        "back", ["traps", "glutes"],               "barbell",  "hinge", "plates",       0.88, 0.85),
    CuratedExercise("Conventional Deadlift",            "back", ["quads", "glutes", "hamstrings"], "barbell",  "hinge", "plates",       0.95, 0.95),
    CuratedExercise("Machine Pullover",                 "back", ["chest"],                         "machine",  "isolation", "machine_plates", 0.75, 0.28),
    CuratedExercise("Straight-Arm Cable Pulldown",      "back", [],                                "cable",    "isolation", "cable",    0.72, 0.25),
    CuratedExercise("Dumbbell Pullover",                "back", ["chest"],                         "dumbbell", "isolation", "dumbbells", 0.70, 0.32),
    CuratedExercise("Hyperextension",                   "back", ["glutes", "hamstrings"],          "bodyweight","hinge", "bodyweight",  0.70, 0.30),
    CuratedExercise("Reverse Hyperextension",           "back", ["glutes", "hamstrings"],          "machine",  "hinge", "machine_plates", 0.68, 0.25),

    # =========================================================================
    # SHOULDERS — FRONT DELT (8 exercises)
    # =========================================================================
    CuratedExercise("Seated Dumbbell Shoulder Press",   "front_delt", ["side_delt", "triceps"],  "dumbbell",      "push", "dumbbells",     0.90, 0.65),
    CuratedExercise("Standing Barbell Overhead Press",  "front_delt", ["side_delt", "triceps"],  "barbell",       "push", "plates",        0.92, 0.75),
    CuratedExercise("Machine Shoulder Press",           "front_delt", ["side_delt", "triceps"],  "machine",       "push", "machine_plates", 0.82, 0.45),
    CuratedExercise("Smith Machine Overhead Press",     "front_delt", ["side_delt", "triceps"],  "smith_machine", "push", "plate_loaded",  0.80, 0.55),
    CuratedExercise("Standing Arnold Press",            "front_delt", ["side_delt", "triceps"],  "dumbbell",      "push", "dumbbells",     0.85, 0.60),
    CuratedExercise("Dumbbell Front Raise",             "front_delt", ["chest"],                 "dumbbell",      "isolation", "dumbbells", 0.65, 0.25),
    CuratedExercise("Front Plate Raise",                "front_delt", ["chest"],                 "bodyweight",    "isolation", "bodyweight", 0.58, 0.20),
    CuratedExercise("Front Barbell Raise",              "front_delt", ["chest"],                 "barbell",       "isolation", "plates",    0.62, 0.25),

    # =========================================================================
    # SHOULDERS — SIDE DELT (7 exercises)
    # =========================================================================
    CuratedExercise("Standing Dumbbell Lateral Raise",  "side_delt", ["traps"],                  "dumbbell", "isolation", "dumbbells",     0.78, 0.25),
    CuratedExercise("Seated Dumbbell Lateral Raise",    "side_delt", ["traps"],                  "dumbbell", "isolation", "dumbbells",     0.80, 0.22),
    CuratedExercise("Cable Lateral Raise",              "side_delt", ["traps"],                  "cable",    "isolation", "cable",         0.78, 0.22),
    CuratedExercise("Machine Lateral Raise",            "side_delt", ["traps"],                  "machine",  "isolation", "machine_plates", 0.75, 0.20),
    CuratedExercise("Leaning Single-Arm Lateral Raise", "side_delt", ["traps"],                  "dumbbell", "isolation", "dumbbells",     0.76, 0.22),
    CuratedExercise("Incline Y-Raise",                  "side_delt", ["rear_delt", "traps"],     "dumbbell", "isolation", "dumbbells",     0.68, 0.20),
    CuratedExercise("Upright Row",                      "side_delt", ["traps", "front_delt"],    "ez_bar",   "pull",      "plates",        0.75, 0.45),

    # =========================================================================
    # SHOULDERS — REAR DELT (5 exercises)
    # =========================================================================
    CuratedExercise("Reverse Pec Deck",                 "rear_delt", ["back"],                   "machine",  "pull", "machine_plates", 0.80, 0.22),
    CuratedExercise("Bent-Over Dumbbell Rear Delt Fly", "rear_delt", ["back"],                   "dumbbell", "pull", "dumbbells",      0.75, 0.25),
    CuratedExercise("Cable Face Pull",                  "rear_delt", ["back", "traps"],          "cable",    "pull", "cable",          0.78, 0.22),
    CuratedExercise("Heavy Rear Delt Swings",           "rear_delt", ["back"],                   "dumbbell", "pull", "dumbbells",      0.68, 0.28),
    CuratedExercise("Seated Y-Cable Raise",             "rear_delt", ["side_delt", "traps"],     "cable",    "pull", "cable",          0.70, 0.20),

    # =========================================================================
    # BICEPS (14 exercises)
    # =========================================================================
    CuratedExercise("Standing Barbell Curl",            "biceps", ["forearms"],             "barbell",  "pull", "plates",        0.85, 0.40),
    CuratedExercise("Seated Alternating Dumbbell Curl", "biceps", ["forearms"],             "dumbbell", "pull", "dumbbells",     0.82, 0.35),
    CuratedExercise("Incline Dumbbell Curl",            "biceps", [],                       "dumbbell", "pull", "dumbbells",     0.80, 0.30),
    CuratedExercise("Dumbbell Hammer Curl",             "biceps", ["forearms"],             "dumbbell", "pull", "dumbbells",     0.78, 0.32),
    CuratedExercise("Preacher Curl",                    "biceps", [],                       "ez_bar",   "pull", "plates",        0.80, 0.30),
    CuratedExercise("Machine Preacher Curl",            "biceps", [],                       "machine",  "pull", "machine_plates", 0.75, 0.22),
    CuratedExercise("Concentration Curl",               "biceps", [],                       "dumbbell", "pull", "dumbbells",     0.72, 0.18),
    CuratedExercise("Straight Bar Cable Curl",          "biceps", ["forearms"],             "cable",    "pull", "cable",         0.75, 0.22),
    CuratedExercise("High Cable Curl",                  "biceps", [],                       "cable",    "pull", "cable",         0.70, 0.20),
    CuratedExercise("Spider Curl",                      "biceps", [],                       "ez_bar",   "pull", "plates",        0.78, 0.25),
    CuratedExercise("Low Pulley Cable Curl",            "biceps", ["forearms"],             "cable",    "pull", "cable",         0.72, 0.20),
    CuratedExercise("Rope Hammer Curl",                 "biceps", ["forearms"],             "cable",    "pull", "cable",         0.75, 0.22),
    CuratedExercise("Wide Incline Dumbbell Curl",       "biceps", [],                       "dumbbell", "pull", "dumbbells",     0.76, 0.28),
    CuratedExercise("EZ Bar Reverse Curl",              "forearms", ["biceps"],             "ez_bar",   "pull", "plates",        0.72, 0.28),

    # =========================================================================
    # TRICEPS (13 exercises)
    # =========================================================================
    CuratedExercise("Rope Cable Pushdown",              "triceps", [],                      "cable",    "push", "cable",         0.78, 0.22),
    CuratedExercise("Straight Bar Cable Pushdown",      "triceps", [],                      "cable",    "push", "cable",         0.78, 0.22),
    CuratedExercise("V-Bar Cable Pushdown",             "triceps", [],                      "cable",    "push", "cable",         0.76, 0.22),
    CuratedExercise("Single-Arm Reverse Grip Pushdown", "triceps", [],                      "cable",    "push", "cable",         0.72, 0.20),
    CuratedExercise("Overhead Cable Tricep Extension",  "triceps", [],                      "cable",    "push", "cable",         0.78, 0.25),
    CuratedExercise("Decline Cable Skull Crusher",      "triceps", [],                      "cable",    "push", "cable",         0.75, 0.25),
    CuratedExercise("EZ Bar Skull Crusher",             "triceps", [],                      "ez_bar",   "push", "plates",        0.82, 0.40),
    CuratedExercise("Dumbbell Skull Crusher",           "triceps", [],                      "dumbbell", "push", "dumbbells",     0.78, 0.35),
    CuratedExercise("Dumbbell Overhead Tricep Extension","triceps", [],                     "dumbbell", "push", "dumbbells",     0.75, 0.30),
    CuratedExercise("Dip Machine (Tricep)",             "triceps", ["chest"],               "machine",  "push", "machine_plates", 0.80, 0.38),
    CuratedExercise("JM Press",                         "triceps", ["chest"],               "barbell",  "push", "plates",        0.82, 0.50),
    CuratedExercise("Dumbbell Kickback",                "triceps", [],                      "dumbbell", "isolation", "dumbbells", 0.62, 0.18),
    CuratedExercise("Single-Arm Forward Cable Extension","triceps", [],                     "cable",    "push", "cable",         0.70, 0.20),

    # =========================================================================
    # QUADRICEPS (16 exercises)
    # =========================================================================
    CuratedExercise("Barbell Back Squat",               "quads", ["glutes", "hamstrings"],  "barbell",       "squat", "plates",        0.95, 0.90),
    CuratedExercise("Front Squat",                      "quads", ["glutes", "abs"],         "barbell",       "squat", "plates",        0.90, 0.82),
    CuratedExercise("Belt Squat",                       "quads", ["glutes"],                "machine",       "squat", "plate_loaded",  0.88, 0.55),
    CuratedExercise("Hack Squat",                       "quads", ["glutes"],                "machine",       "squat", "plate_loaded",  0.88, 0.55),
    CuratedExercise("Leg Press",                        "quads", ["glutes", "hamstrings"],  "machine",       "squat", "plate_loaded",  0.85, 0.50),
    CuratedExercise("Pendulum Squat",                   "quads", ["glutes"],                "machine",       "squat", "plate_loaded",  0.85, 0.50),
    CuratedExercise("V-Squat Machine",                  "quads", ["glutes", "hamstrings"],  "machine",       "squat", "plate_loaded",  0.83, 0.48),
    CuratedExercise("Smith Machine Squat",              "quads", ["glutes", "hamstrings"],  "smith_machine", "squat", "plate_loaded",  0.82, 0.55),
    CuratedExercise("Leg Extension",                    "quads", [],                        "machine",       "isolation", "machine_plates", 0.75, 0.22),
    CuratedExercise("Sissy Squat",                      "quads", [],                        "bodyweight",    "squat", "bodyweight",    0.70, 0.30),
    CuratedExercise("Walking Lunge",                    "quads", ["glutes", "hamstrings"],  "dumbbell",      "lunge", "dumbbells",     0.82, 0.60),
    CuratedExercise("Bulgarian Split Squat",            "quads", ["glutes", "hamstrings"],  "dumbbell",      "lunge", "dumbbells",     0.85, 0.60),
    CuratedExercise("Smith Machine Split Squat",        "quads", ["glutes", "hamstrings"],  "smith_machine", "lunge", "plate_loaded",  0.78, 0.50),
    CuratedExercise("Spider Bar Squat",                 "quads", ["glutes", "hamstrings"],  "barbell",       "squat", "plates",        0.88, 0.82),
    CuratedExercise("Single-Leg Leg Press",             "quads", ["glutes"],                "machine",       "squat", "plate_loaded",  0.78, 0.40),
    CuratedExercise("Sled Push",                        "quads", ["glutes", "calves"],      "machine",       "push",  "plate_loaded",  0.70, 0.55),

    # =========================================================================
    # HAMSTRINGS (8 exercises)
    # =========================================================================
    CuratedExercise("Romanian Deadlift",                "hamstrings", ["glutes", "back"],    "barbell",  "hinge", "plates",        0.92, 0.78),
    CuratedExercise("Stiff-Leg Deadlift",               "hamstrings", ["glutes", "back"],    "barbell",  "hinge", "plates",        0.90, 0.75),
    CuratedExercise("Banded B-Stance RDL",              "hamstrings", ["glutes"],            "barbell",  "hinge", "plates",        0.80, 0.55),
    CuratedExercise("Lying Leg Curl",                   "hamstrings", ["calves"],            "machine",  "isolation", "machine_plates", 0.78, 0.22),
    CuratedExercise("Seated Leg Curl",                  "hamstrings", ["calves"],            "machine",  "isolation", "machine_plates", 0.78, 0.22),
    CuratedExercise("Standing Single-Leg Curl",         "hamstrings", [],                    "machine",  "isolation", "machine_plates", 0.72, 0.20),
    CuratedExercise("Nordic Hamstring Curl",            "hamstrings", ["calves"],            "bodyweight","isolation", "bodyweight",    0.82, 0.40),
    CuratedExercise("Good Morning",                     "hamstrings", ["glutes", "back"],    "barbell",  "hinge", "plates",        0.78, 0.65),

    # =========================================================================
    # GLUTES (13 exercises)
    # =========================================================================
    CuratedExercise("Barbell Hip Thrust",               "glutes", ["hamstrings"],            "barbell",       "hinge", "plates",        0.92, 0.60),
    CuratedExercise("Plate-Loaded Hip Thrust Machine",  "glutes", ["hamstrings"],            "machine",       "hinge", "plate_loaded",  0.88, 0.45),
    CuratedExercise("Smith Machine Hip Thrust",         "glutes", ["hamstrings"],            "smith_machine", "hinge", "plate_loaded",  0.85, 0.48),
    CuratedExercise("Hip Abduction Machine",            "glutes", [],                        "machine",       "isolation", "machine_plates", 0.72, 0.18),
    CuratedExercise("Hip Adduction Machine",            "glutes", [],                        "machine",       "isolation", "machine_plates", 0.65, 0.18),
    CuratedExercise("Cable Kickback",                   "glutes", ["hamstrings"],            "cable",         "isolation", "cable",      0.68, 0.20),
    CuratedExercise("Machine Donkey Kickback",          "glutes", ["hamstrings"],            "machine",       "isolation", "machine_plates", 0.68, 0.18),
    CuratedExercise("Glute Bridge",                     "glutes", ["hamstrings"],            "barbell",       "hinge", "plates",        0.80, 0.40),
    CuratedExercise("Smith Machine Curtsy Lunge",       "glutes", ["quads"],                 "smith_machine", "lunge", "plate_loaded",  0.75, 0.45),
    CuratedExercise("Step-Up",                          "glutes", ["quads", "hamstrings"],   "dumbbell",      "lunge", "dumbbells",     0.75, 0.40),
    CuratedExercise("Banded Lateral Walk",              "glutes", [],                        "bodyweight",    "isolation", "bodyweight", 0.55, 0.12),
    CuratedExercise("Banded External Rotation",         "glutes", [],                        "bodyweight",    "isolation", "bodyweight", 0.50, 0.10),
    CuratedExercise("Cable Pull-Through",               "glutes", ["hamstrings"],            "cable",         "hinge", "cable",         0.75, 0.30),

    # =========================================================================
    # CALVES (4 exercises)
    # =========================================================================
    CuratedExercise("Standing Calf Raise",              "calves", [],                        "machine",  "isolation", "machine_plates", 0.80, 0.22),
    CuratedExercise("Seated Calf Raise",                "calves", [],                        "machine",  "isolation", "plate_loaded",   0.78, 0.20),
    CuratedExercise("Leg Press Calf Raise",             "calves", [],                        "machine",  "isolation", "plate_loaded",   0.75, 0.20),
    CuratedExercise("Hack Squat Machine Calf Raise",    "calves", [],                        "machine",  "isolation", "plate_loaded",   0.72, 0.20),

    # =========================================================================
    # ABS & CORE (10 exercises)
    # =========================================================================
    CuratedExercise("Hanging Leg Raise",                "abs", [],                           "bodyweight", "isolation", "bodyweight",  0.78, 0.25),
    CuratedExercise("Kneeling Cable Crunch",            "abs", [],                           "cable",      "isolation", "cable",       0.75, 0.22),
    CuratedExercise("Decline Crunch",                    "abs", [],                           "bodyweight", "isolation", "bodyweight",  0.72, 0.22),
    CuratedExercise("Exercise Ball Crunch",             "abs", [],                           "bodyweight", "isolation", "bodyweight",  0.62, 0.15),
    CuratedExercise("Bosu Ball Crunch",                 "abs", [],                           "bodyweight", "isolation", "bodyweight",  0.60, 0.15),
    CuratedExercise("Reverse Crunch",                   "abs", [],                           "bodyweight", "isolation", "bodyweight",  0.68, 0.18),
    CuratedExercise("Plank",                            "abs", [],                           "bodyweight", "isolation", "bodyweight",  0.65, 0.12),
    CuratedExercise("Stomach Vacuum",                   "abs", [],                           "bodyweight", "isolation", "bodyweight",  0.60, 0.05),
    CuratedExercise("Seated Machine Abdominal Crunch",  "abs", [],                           "machine",    "isolation", "machine_plates", 0.70, 0.18),
    CuratedExercise("Lying Leg Raise",                  "abs", [],                           "bodyweight", "isolation", "bodyweight",  0.68, 0.18),

    # =========================================================================
    # TRAPS (4 exercises)
    # =========================================================================
    CuratedExercise("Dumbbell Shrug",                   "traps", [],                         "dumbbell", "pull", "dumbbells",     0.75, 0.30),
    CuratedExercise("Behind-the-Back Barbell Shrug",    "traps", [],                         "barbell",  "pull", "plates",        0.78, 0.35),
    CuratedExercise("Cage Press",                       "traps", ["front_delt", "triceps"],  "barbell",  "push", "plates",        0.72, 0.45),
    CuratedExercise("Rack Pull (Above Knee)",           "traps", ["back"],                   "barbell",  "hinge", "plates",       0.85, 0.75),

    # =========================================================================
    # FOREARMS (3 exercises)
    # =========================================================================
    CuratedExercise("Barbell Wrist Curl",               "forearms", [],                      "barbell",  "isolation", "plates",    0.72, 0.18),
    CuratedExercise("Barbell Reverse Wrist Curl",       "forearms", [],                      "barbell",  "isolation", "plates",    0.68, 0.18),
    CuratedExercise("Forearm Pronation/Supination",     "forearms", [],                      "dumbbell", "isolation", "dumbbells", 0.60, 0.12),

    # =========================================================================
    # ADDITIONAL DIVISION-SPECIFIC & METHODOLOGY EXERCISES (33 exercises)
    # =========================================================================

    # Lower body specialty
    CuratedExercise("Sumo Deadlift",                    "quads", ["glutes", "hamstrings", "back"], "barbell", "hinge", "plates",   0.90, 0.85),
    CuratedExercise("Sumo Front Squat",                 "glutes", ["quads"],                "barbell",       "squat", "plates",        0.82, 0.70),
    CuratedExercise("Cable Goblet Squat",               "glutes", ["quads"],                "cable",         "squat", "cable",         0.70, 0.35),
    CuratedExercise("Elevated Smith Machine Lunge",     "glutes", ["quads", "hamstrings"],  "smith_machine", "lunge", "plate_loaded",  0.75, 0.45),
    CuratedExercise("Jump Squat",                       "quads", ["glutes", "calves"],      "bodyweight",    "squat", "bodyweight",    0.72, 0.50),
    CuratedExercise("Box Squat",                        "quads", ["glutes", "hamstrings"],  "barbell",       "squat", "plates",        0.88, 0.80),
    CuratedExercise("Inverted Leg Press",               "quads", ["glutes"],                "machine",       "squat", "plate_loaded",  0.82, 0.48),
    CuratedExercise("Stiff-Leg Barbell Deadlift",       "hamstrings", ["glutes"],           "barbell",       "hinge", "plates",        0.88, 0.72),

    # Chest specialty
    CuratedExercise("Hammer Strength Single-Arm Chest Press", "chest", ["front_delt", "triceps"], "machine", "push", "plate_loaded", 0.80, 0.42),
    CuratedExercise("Seated Cable Fly",                 "chest", ["front_delt"],            "cable",    "isolation", "cable",     0.68, 0.22),
    CuratedExercise("Cable Fly into Cable Press",       "chest", ["triceps"],               "cable",    "push",      "cable",     0.70, 0.28),
    CuratedExercise("Push-Up",                          "chest", ["triceps", "front_delt"], "bodyweight","push",     "bodyweight", 0.72, 0.30),
    CuratedExercise("Bench Dip",                        "triceps", ["front_delt", "chest"], "bodyweight","push",     "bodyweight", 0.65, 0.25),
    CuratedExercise("Banded Incline Dumbbell Press",    "chest", ["front_delt", "triceps"], "dumbbell", "push",      "dumbbells",  0.85, 0.65),
    CuratedExercise("Pronated Cable Chest Fly",         "chest", ["front_delt"],            "cable",    "isolation", "cable",      0.68, 0.22),
    CuratedExercise("GVT Machine Chest Press",          "chest", ["front_delt", "triceps"], "machine",  "push",      "machine_plates", 0.78, 0.40),

    # Back specialty
    CuratedExercise("Machine Reverse Fly",              "rear_delt", ["back"],              "machine",  "pull", "machine_plates", 0.75, 0.20),
    CuratedExercise("One-Arm Dead-Stop Barbell Row",    "back", ["biceps", "traps"],        "barbell",  "pull", "plates",         0.85, 0.65),
    CuratedExercise("Facing-Away Lat Pulldown",         "back", ["biceps"],                 "cable",    "pull", "cable",          0.78, 0.32),
    CuratedExercise("Rope Straight-Arm Pulldown",       "back", ["rear_delt"],              "cable",    "isolation", "cable",     0.70, 0.22),
    CuratedExercise("Standing Overhand Cable Row",      "back", ["rear_delt", "biceps"],    "cable",    "pull", "cable",          0.78, 0.35),
    CuratedExercise("Rack Chin-Up",                     "back", ["biceps"],                 "bodyweight","pull","bodyweight",      0.80, 0.45),
    CuratedExercise("GVT Chest-Supported DB Row",       "back", ["biceps"],                 "dumbbell", "pull", "dumbbells",      0.80, 0.42),
    CuratedExercise("Seated Straight-Arm Cable Pulldown","back", [],                        "cable",    "isolation", "cable",     0.70, 0.22),

    # Arm specialty
    CuratedExercise("Standing Double Biceps Cable Curl","biceps", [],                       "cable",    "pull", "cable",          0.68, 0.20),
    CuratedExercise("Dual Rope Tricep Extension",       "triceps", [],                      "cable",    "push", "cable",          0.75, 0.22),
    CuratedExercise("Fat Gripz Machine Preacher Curl",  "biceps", ["forearms"],             "machine",  "pull", "machine_plates", 0.72, 0.22),
    CuratedExercise("Machine Incline Curl",             "biceps", [],                       "machine",  "pull", "machine_plates", 0.72, 0.20),
    CuratedExercise("Leg Press Calf Raise (Single-Leg)","calves", [],                       "machine",  "isolation", "plate_loaded", 0.72, 0.18),

    # Shoulder specialty
    CuratedExercise("Incline Bench Alternating Front Raise","front_delt", ["chest"],        "dumbbell", "isolation", "dumbbells",  0.62, 0.22),
    CuratedExercise("Single-Arm Cable Lateral Raise",   "side_delt", ["traps"],             "cable",    "isolation", "cable",      0.76, 0.20),
    CuratedExercise("Cable Rope Face Pull",             "rear_delt", ["back", "traps"],     "cable",    "pull", "cable",          0.76, 0.22),
    CuratedExercise("Dumbbell Upright Row",             "side_delt", ["traps", "front_delt"],"dumbbell","pull",      "dumbbells",  0.72, 0.35),

    # Abs specialty
    CuratedExercise("Ab Wheel Rollout",                 "abs", [],                          "bodyweight","isolation", "bodyweight", 0.75, 0.30),

    # Additional exercises required by priority cascade
    CuratedExercise("Deficit Reverse Lunge",            "glutes", ["quads", "hamstrings"],  "dumbbell",  "lunge", "dumbbells",    0.80, 0.50),
    CuratedExercise("Glute-Ham Raise",                  "hamstrings", ["glutes", "calves"], "bodyweight","isolation","bodyweight", 0.82, 0.38),
    CuratedExercise("Farmer's Walk",                    "traps", ["forearms", "abs"],       "dumbbell",  "carry",   "dumbbells",  0.75, 0.50),
]

# Quick count: verify at module load
assert len(CURATED_EXERCISES) >= 185, f"Expected ≥185 exercises, got {len(CURATED_EXERCISES)}"
# Verify no duplicate names
_names = [e.name.lower() for e in CURATED_EXERCISES]
_dupes = [n for n in _names if _names.count(n) > 1]
assert not _dupes, f"Duplicate exercise names: {set(_dupes)}"
