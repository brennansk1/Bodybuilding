"""
Division-Specific Exercise Priority Lists

Each division defines an ordered cascade list per muscle group.
The training engine saturates exercises in priority order, filling
each slot up to its max_sets cap before cascading to the next.

Load Types (from canonical spec)
---------------------------------
  plates        — Free weights (barbells, EZ-bars) using standard plate loading.
                  Progression: 5.0 kg total (2.5/side) for large compounds;
                  2.5 kg total (1.25/side) for small isolations (curls, skulls).
  plate_loaded  — Structural machines (Leg Press, Hack Squat) using manual plates.
                  Progression: 10.0 kg total (one 5kg plate per side).
  machine_plates— Selectorized machines with pin-loaded weight stacks.
                  Progression: 2.5 kg per pin step.
  cable         — Cable-pulley systems with pin-loaded stacks.
                  Progression: 2.5 kg per pin step.
  dumbbells     — Standard dumbbell pairs.
                  Progression: 2.5 kg per dumbbell (standard pair increments).
  bodyweight    — Bodyweight movements; rep-ceiling progression first,
                  then 2.5 kg added via belt/vest when ceiling is reached.

Gap Adjustment
--------------
When a muscle's HQI is below threshold, the engine boosts the cap
of the top-priority (most effective) exercise to concentrate stimulus
where adaptation is most needed.

  HQI < 40  → top-slot max_sets ×1.5  (severe lag)
  HQI 40-65 → top-slot max_sets ×1.25 (moderate lag)
  HQI ≥ 65  → no adjustment           (maintain)

Division Philosophies
---------------------
mens_open       — Maximum overall mass. Heavy compound anchors. Thickness and
                  width back cascades merged thickness-first. All muscle groups
                  equally developed.

mens_physique   — V-taper. Width-priority back (pulldowns over rows). Flat
                  pressing capped low. Side delts P1 for shoulder width. No
                  heavy axial squats. Machines/cables preferred for legs.

classic_physique — Proportional X-frame within a height/weight cap. Balanced
                  mass. Lat pulldown leads back. Lateral raise P1 for medial
                  delt width. Compounds at reasonable caps.

womens_bikini   — Extreme glute dominance. Hip thrust P1. No heavy pressing.
                  No heavy spinal-flexion abs (stomach vacuum for waist).
                  Good Morning included at low cap P4 per spec.

womens_figure   — V-taper + glutes. Lat pulldown P1 (width). No barbell
                  overhead press (traps destroy V-taper). Shoulder girdle
                  shaped by dumbbells/cables. Cable fly leads chest.

womens_physique — Full development closest to Men's Open proportions, but
                  dumbbell/cable preferred throughout for aesthetic roundness
                  and joint health. Seated cable row P1 back (thickness +
                  width together). DB press leads chest.
"""

from typing import TypedDict


class ExercisePrioritySlot(TypedDict):
    name: str            # canonical display name for UI / logging
    keywords: list[str]  # any substring match (case-insensitive) triggers this slot
    max_sets: int        # maximum sets before cascading to next priority
    load_type: str       # "plates" | "plate_loaded" | "machine_plates" | "cable" | "dumbbells" | "bodyweight"


# ---------------------------------------------------------------------------
# Division exercise priority tables
# ---------------------------------------------------------------------------
# Format: {division: {muscle: [ExercisePrioritySlot, ...]}}
# Muscles use the DB primary_muscle naming convention.
# Cascades are ordered P1 → P2 → P3 → P4 then optional overflow slots.

DIVISION_EXERCISE_PRIORITIES: dict[str, dict[str, list[ExercisePrioritySlot]]] = {

    # =========================================================================
    # MEN'S OPEN — maximum overall mass; heavy compound anchors; all groups
    # Back cascade merges thickness (P1) and width (P2) interleaved so that
    # a single back day develops both lat sweep and rhomboid density.
    # =========================================================================
    "mens_open": {
        "chest": [
            {"name": "Barbell Bench Press",          "keywords": ["barbell bench press"],                        "max_sets": 4, "load_type": "plates"},
            {"name": "Incline Barbell Press",         "keywords": ["incline barbell", "incline barbell press"],   "max_sets": 4, "load_type": "plates"},
            {"name": "Incline Dumbbell Press",        "keywords": ["incline dumbbell", "incline dumbbell press"], "max_sets": 4, "load_type": "dumbbells"},
            {"name": "Cable Fly / Crossover",         "keywords": ["cable fly", "cable crossover"],               "max_sets": 4, "load_type": "cable"},
            {"name": "Pec Deck",                      "keywords": ["pec deck"],                                   "max_sets": 3, "load_type": "machine_plates"},
            {"name": "Dumbbell Bench Press",          "keywords": ["dumbbell bench press"],                       "max_sets": 3, "load_type": "dumbbells"},
        ],
        # Back: thickness first (mass priority), then width isolations
        "back": [
            {"name": "Barbell Row",                   "keywords": ["barbell row"],                                "max_sets": 4, "load_type": "plates"},
            {"name": "T-Bar Row",                     "keywords": ["t-bar row", "t bar row"],                    "max_sets": 4, "load_type": "plates"},
            {"name": "Lat Pulldown",                  "keywords": ["lat pulldown", "pulldown"],                  "max_sets": 4, "load_type": "cable"},
            {"name": "Seated Cable Row",              "keywords": ["seated cable row", "cable row"],             "max_sets": 4, "load_type": "cable"},
            {"name": "Dumbbell Row",                  "keywords": ["dumbbell row"],                              "max_sets": 4, "load_type": "dumbbells"},
            {"name": "Weighted Pull-Up",              "keywords": ["weighted pull-up", "pull-up", "pullup"],     "max_sets": 3, "load_type": "bodyweight"},
            {"name": "Straight Arm Pulldown",         "keywords": ["straight arm pulldown"],                     "max_sets": 3, "load_type": "cable"},
            {"name": "Single-Arm Cable Pulldown",     "keywords": ["single-arm cable pulldown", "single arm pulldown"], "max_sets": 3, "load_type": "cable"},
        ],
        "shoulders": [
            {"name": "Overhead Barbell Press",        "keywords": ["overhead press", "barbell overhead press"],  "max_sets": 4, "load_type": "plates"},
            {"name": "Dumbbell Shoulder Press",       "keywords": ["dumbbell shoulder press"],                   "max_sets": 4, "load_type": "dumbbells"},
            {"name": "Lateral Raise",                 "keywords": ["lateral raise"],                             "max_sets": 4, "load_type": "dumbbells"},
            {"name": "Rear Delt Fly",                 "keywords": ["rear delt fly", "rear delt", "face pull"],  "max_sets": 4, "load_type": "machine_plates"},
            {"name": "Cable Lateral Raise",           "keywords": ["cable lateral raise"],                       "max_sets": 3, "load_type": "cable"},
        ],
        "quads": [
            {"name": "Barbell Back Squat",            "keywords": ["barbell back squat", "barbell squat"],       "max_sets": 4, "load_type": "plates"},
            {"name": "Leg Press",                     "keywords": ["leg press"],                                 "max_sets": 4, "load_type": "plate_loaded"},
            {"name": "Hack Squat",                    "keywords": ["hack squat"],                                "max_sets": 3, "load_type": "plate_loaded"},
            {"name": "Leg Extension",                 "keywords": ["leg extension"],                             "max_sets": 3, "load_type": "machine_plates"},
            {"name": "Bulgarian Split Squat",         "keywords": ["bulgarian split", "walking lunge"],          "max_sets": 3, "load_type": "dumbbells"},
        ],
        "hamstrings": [
            {"name": "Romanian Deadlift",             "keywords": ["romanian deadlift"],                         "max_sets": 4, "load_type": "plates"},
            {"name": "Lying Leg Curl",                "keywords": ["lying leg curl"],                            "max_sets": 4, "load_type": "machine_plates"},
            {"name": "Seated Leg Curl",               "keywords": ["seated leg curl"],                           "max_sets": 3, "load_type": "machine_plates"},
            {"name": "Stiff-Leg Deadlift",            "keywords": ["stiff-leg deadlift", "stiff leg deadlift"], "max_sets": 3, "load_type": "plates"},
            {"name": "Good Morning",                  "keywords": ["good morning"],                              "max_sets": 2, "load_type": "plates"},
        ],
        "glutes": [
            {"name": "Hip Thrust",                    "keywords": ["hip thrust"],                                "max_sets": 4, "load_type": "plates"},
            {"name": "Bulgarian Split Squat",         "keywords": ["bulgarian split"],                           "max_sets": 3, "load_type": "dumbbells"},
            {"name": "Glute Bridge",                  "keywords": ["glute bridge"],                              "max_sets": 3, "load_type": "plates"},
            {"name": "Cable Pull-Through",            "keywords": ["cable pull-through", "pull-through"],        "max_sets": 3, "load_type": "cable"},
            {"name": "Romanian Deadlift",             "keywords": ["romanian deadlift"],                         "max_sets": 3, "load_type": "plates"},
        ],
        "biceps": [
            {"name": "Barbell Curl",                  "keywords": ["barbell curl"],                              "max_sets": 4, "load_type": "plates"},
            {"name": "Incline Dumbbell Curl",         "keywords": ["incline dumbbell curl", "dumbbell curl"],    "max_sets": 4, "load_type": "dumbbells"},
            {"name": "Hammer Curl",                   "keywords": ["hammer curl"],                               "max_sets": 3, "load_type": "dumbbells"},
            {"name": "Preacher Curl",                 "keywords": ["preacher curl"],                             "max_sets": 3, "load_type": "plates"},
            {"name": "Cable Curl",                    "keywords": ["cable curl"],                                "max_sets": 3, "load_type": "cable"},
        ],
        "triceps": [
            {"name": "Close-Grip Bench Press",        "keywords": ["close-grip bench press", "close grip bench"], "max_sets": 4, "load_type": "plates"},
            {"name": "Skull Crusher",                 "keywords": ["skull crusher"],                             "max_sets": 4, "load_type": "plates"},
            {"name": "Tricep Pushdown",               "keywords": ["tricep pushdown", "pushdown"],               "max_sets": 4, "load_type": "cable"},
            {"name": "Overhead Tricep Extension",     "keywords": ["overhead tricep extension", "overhead tricep ext"], "max_sets": 3, "load_type": "cable"},
            {"name": "Cable Kickback",                "keywords": ["cable kickback"],                            "max_sets": 3, "load_type": "cable"},
        ],
        "calves": [
            {"name": "Standing Calf Raise",           "keywords": ["standing calf raise"],                       "max_sets": 4, "load_type": "machine_plates"},
            {"name": "Seated Calf Raise",             "keywords": ["seated calf raise"],                         "max_sets": 4, "load_type": "plate_loaded"},
            {"name": "Leg Press Calf Raise",          "keywords": ["leg press calf raise"],                      "max_sets": 3, "load_type": "plate_loaded"},
            {"name": "Single-Leg DB Calf Raise",      "keywords": ["single-leg", "single leg"],                  "max_sets": 3, "load_type": "dumbbells"},
        ],
        "abs": [
            {"name": "Cable Crunch",                  "keywords": ["cable crunch"],                              "max_sets": 4, "load_type": "cable"},
            {"name": "Hanging Leg Raise",             "keywords": ["hanging leg raise"],                         "max_sets": 4, "load_type": "bodyweight"},
            {"name": "Ab Wheel Rollout",              "keywords": ["ab wheel"],                                  "max_sets": 3, "load_type": "bodyweight"},
            {"name": "Decline Crunch",                "keywords": ["decline crunch"],                            "max_sets": 3, "load_type": "bodyweight"},
        ],
        "traps": [
            {"name": "Barbell Shrug",                 "keywords": ["barbell shrug"],                             "max_sets": 3, "load_type": "plates"},
            {"name": "Dumbbell Shrug",                "keywords": ["dumbbell shrug"],                            "max_sets": 3, "load_type": "dumbbells"},
            {"name": "Farmer's Carry",                "keywords": ["farmer"],                                    "max_sets": 2, "load_type": "dumbbells"},
        ],
        "forearms": [
            {"name": "Wrist Curl",                    "keywords": ["wrist curl"],                                "max_sets": 3, "load_type": "plates"},
            {"name": "Reverse Wrist Curl",            "keywords": ["reverse wrist curl"],                        "max_sets": 3, "load_type": "plates"},
        ],
    },

    # =========================================================================
    # MEN'S PHYSIQUE — V-taper; side delts P1; width-first back;
    # leg extension leads quads (machines preferred, no heavy axial squat);
    # flat barbell pressing excluded; cables/DBs preferred throughout.
    # =========================================================================
    "mens_physique": {
        "chest": [
            {"name": "Incline Barbell Press",         "keywords": ["incline barbell", "incline barbell press"],   "max_sets": 4, "load_type": "plates"},
            {"name": "Incline Dumbbell Press",        "keywords": ["incline dumbbell", "incline dumbbell press"], "max_sets": 4, "load_type": "dumbbells"},
            {"name": "Cable Fly / Crossover",         "keywords": ["cable fly", "cable crossover"],               "max_sets": 4, "load_type": "cable"},
            {"name": "Pec Deck",                      "keywords": ["pec deck"],                                   "max_sets": 3, "load_type": "machine_plates"},
            # Flat barbell capped low — lower chest mass detracts from aesthetics
            {"name": "Barbell Bench Press",           "keywords": ["barbell bench press", "dumbbell bench press"], "max_sets": 2, "load_type": "plates"},
        ],
        # Width-first for V-taper lat development
        "back": [
            {"name": "Lat Pulldown",                  "keywords": ["lat pulldown", "pulldown"],                  "max_sets": 4, "load_type": "cable"},
            {"name": "Weighted Pull-Up",              "keywords": ["weighted pull-up", "pull-up", "pullup"],     "max_sets": 4, "load_type": "bodyweight"},
            {"name": "Seated Cable Row",              "keywords": ["seated cable row", "cable row"],             "max_sets": 4, "load_type": "cable"},
            {"name": "Straight Arm Pulldown",         "keywords": ["straight arm pulldown"],                     "max_sets": 3, "load_type": "cable"},
            {"name": "Dumbbell Row",                  "keywords": ["dumbbell row"],                              "max_sets": 3, "load_type": "dumbbells"},
            {"name": "T-Bar Row",                     "keywords": ["t-bar row"],                                 "max_sets": 3, "load_type": "plates"},
            # Barbell row capped low — trap recruitment compresses V-taper
            {"name": "Barbell Row",                   "keywords": ["barbell row"],                               "max_sets": 2, "load_type": "plates"},
        ],
        "shoulders": [
            {"name": "Lateral Raise",                 "keywords": ["lateral raise"],                             "max_sets": 4, "load_type": "dumbbells"},
            {"name": "Cable Lateral Raise",           "keywords": ["cable lateral raise"],                       "max_sets": 4, "load_type": "cable"},
            {"name": "Dumbbell Shoulder Press",       "keywords": ["dumbbell shoulder press"],                   "max_sets": 4, "load_type": "dumbbells"},
            {"name": "Rear Delt Fly",                 "keywords": ["rear delt fly", "rear delt", "face pull"],  "max_sets": 4, "load_type": "machine_plates"},
            # BB overhead press capped — upper trap growth narrows V-taper
            {"name": "Overhead Barbell Press",        "keywords": ["overhead press", "barbell overhead press"],  "max_sets": 2, "load_type": "plates"},
        ],
        # Machine/DB preferred; no heavy axial squat
        "quads": [
            {"name": "Leg Extension",                 "keywords": ["leg extension"],                             "max_sets": 4, "load_type": "machine_plates"},
            {"name": "Walking Lunge",                 "keywords": ["walking lunge"],                             "max_sets": 3, "load_type": "dumbbells"},
            {"name": "Leg Press",                     "keywords": ["leg press"],                                 "max_sets": 3, "load_type": "plate_loaded"},
            {"name": "Bulgarian Split Squat",         "keywords": ["bulgarian split"],                           "max_sets": 3, "load_type": "dumbbells"},
            {"name": "Hack Squat",                    "keywords": ["hack squat"],                                "max_sets": 3, "load_type": "plate_loaded"},
        ],
        "hamstrings": [
            {"name": "Lying Leg Curl",                "keywords": ["lying leg curl"],                            "max_sets": 4, "load_type": "machine_plates"},
            {"name": "Romanian Deadlift",             "keywords": ["romanian deadlift"],                         "max_sets": 3, "load_type": "plates"},
            {"name": "Seated Leg Curl",               "keywords": ["seated leg curl"],                           "max_sets": 3, "load_type": "machine_plates"},
            {"name": "Stiff-Leg Deadlift",            "keywords": ["stiff-leg deadlift"],                       "max_sets": 3, "load_type": "plates"},
        ],
        "glutes": [
            {"name": "Hip Thrust",                    "keywords": ["hip thrust"],                                "max_sets": 3, "load_type": "plates"},
            {"name": "Cable Pull-Through",            "keywords": ["cable pull-through", "pull-through"],        "max_sets": 3, "load_type": "cable"},
            {"name": "Glute Bridge",                  "keywords": ["glute bridge"],                              "max_sets": 3, "load_type": "plates"},
        ],
        "biceps": [
            {"name": "Dumbbell Curl",                 "keywords": ["dumbbell curl"],                             "max_sets": 4, "load_type": "dumbbells"},
            {"name": "Cable Curl",                    "keywords": ["cable curl"],                                "max_sets": 4, "load_type": "cable"},
            {"name": "Hammer Curl",                   "keywords": ["hammer curl"],                               "max_sets": 3, "load_type": "dumbbells"},
            {"name": "Preacher Curl",                 "keywords": ["preacher curl"],                             "max_sets": 3, "load_type": "plates"},
            {"name": "Barbell Curl",                  "keywords": ["barbell curl"],                              "max_sets": 2, "load_type": "plates"},
        ],
        "triceps": [
            {"name": "Overhead Tricep Extension",     "keywords": ["overhead tricep extension", "overhead tricep ext"], "max_sets": 4, "load_type": "cable"},
            {"name": "Tricep Pushdown",               "keywords": ["tricep pushdown", "pushdown"],               "max_sets": 4, "load_type": "cable"},
            {"name": "Skull Crusher",                 "keywords": ["skull crusher"],                             "max_sets": 3, "load_type": "plates"},
            {"name": "Cable Kickback",                "keywords": ["cable kickback"],                            "max_sets": 3, "load_type": "cable"},
            {"name": "Close-Grip Bench Press",        "keywords": ["close-grip bench press", "close grip bench"], "max_sets": 2, "load_type": "plates"},
        ],
        "calves": [
            {"name": "Standing Calf Raise",           "keywords": ["standing calf raise"],                       "max_sets": 4, "load_type": "machine_plates"},
            {"name": "Seated Calf Raise",             "keywords": ["seated calf raise"],                         "max_sets": 4, "load_type": "plate_loaded"},
            {"name": "Leg Press Calf Raise",          "keywords": ["leg press calf raise"],                      "max_sets": 3, "load_type": "plate_loaded"},
            {"name": "Single-Leg DB Calf Raise",      "keywords": ["single-leg", "single leg"],                  "max_sets": 3, "load_type": "dumbbells"},
        ],
        "abs": [
            {"name": "Cable Crunch",                  "keywords": ["cable crunch"],                              "max_sets": 4, "load_type": "cable"},
            {"name": "Hanging Leg Raise",             "keywords": ["hanging leg raise"],                         "max_sets": 4, "load_type": "bodyweight"},
            {"name": "Ab Wheel Rollout",              "keywords": ["ab wheel"],                                  "max_sets": 3, "load_type": "bodyweight"},
            {"name": "Plank",                         "keywords": ["plank"],                                     "max_sets": 3, "load_type": "bodyweight"},
        ],
        "traps": [
            # Strictly minimal — visible traps visually compress the clavicles
            {"name": "Dumbbell Shrug",                "keywords": ["dumbbell shrug"],                            "max_sets": 2, "load_type": "dumbbells"},
            {"name": "Farmer's Carry",                "keywords": ["farmer"],                                    "max_sets": 2, "load_type": "dumbbells"},
        ],
        "forearms": [
            {"name": "Wrist Curl",                    "keywords": ["wrist curl"],                                "max_sets": 2, "load_type": "plates"},
            {"name": "Reverse Wrist Curl",            "keywords": ["reverse wrist curl"],                        "max_sets": 2, "load_type": "plates"},
        ],
    },

    # =========================================================================
    # CLASSIC PHYSIQUE — X-frame proportional aesthetics within weight cap;
    # balanced upper and lower development; lat pulldown leads back cascade;
    # overhead press P1 shoulders (document spec), lateral raise P2.
    # =========================================================================
    "classic_physique": {
        "chest": [
            {"name": "Incline Barbell Press",         "keywords": ["incline barbell", "incline barbell press"],   "max_sets": 4, "load_type": "plates"},
            {"name": "Barbell Bench Press",           "keywords": ["barbell bench press"],                        "max_sets": 4, "load_type": "plates"},
            {"name": "Incline Dumbbell Press",        "keywords": ["incline dumbbell", "incline dumbbell press"], "max_sets": 4, "load_type": "dumbbells"},
            {"name": "Cable Fly / Crossover",         "keywords": ["cable fly", "cable crossover"],               "max_sets": 3, "load_type": "cable"},
            {"name": "Pec Deck",                      "keywords": ["pec deck"],                                   "max_sets": 3, "load_type": "machine_plates"},
        ],
        # Balanced: lat pulldown leads for X-frame width, rows for thickness
        "back": [
            {"name": "Lat Pulldown",                  "keywords": ["lat pulldown", "pulldown"],                  "max_sets": 4, "load_type": "cable"},
            {"name": "Barbell Row",                   "keywords": ["barbell row"],                               "max_sets": 4, "load_type": "plates"},
            {"name": "T-Bar Row",                     "keywords": ["t-bar row", "t bar row"],                   "max_sets": 4, "load_type": "plates"},
            {"name": "Seated Cable Row",              "keywords": ["seated cable row", "cable row"],             "max_sets": 4, "load_type": "cable"},
            {"name": "Dumbbell Row",                  "keywords": ["dumbbell row"],                              "max_sets": 3, "load_type": "dumbbells"},
            {"name": "Weighted Pull-Up",              "keywords": ["weighted pull-up", "pull-up", "pullup"],     "max_sets": 3, "load_type": "bodyweight"},
            {"name": "Straight Arm Pulldown",         "keywords": ["straight arm pulldown"],                     "max_sets": 3, "load_type": "cable"},
        ],
        "shoulders": [
            {"name": "Overhead Barbell Press",        "keywords": ["overhead press", "barbell overhead press"],  "max_sets": 4, "load_type": "plates"},
            {"name": "Lateral Raise",                 "keywords": ["lateral raise"],                             "max_sets": 4, "load_type": "dumbbells"},
            {"name": "Dumbbell Shoulder Press",       "keywords": ["dumbbell shoulder press"],                   "max_sets": 3, "load_type": "dumbbells"},
            {"name": "Rear Delt Fly",                 "keywords": ["rear delt fly", "rear delt", "face pull"],  "max_sets": 4, "load_type": "machine_plates"},
            {"name": "Cable Lateral Raise",           "keywords": ["cable lateral raise"],                       "max_sets": 3, "load_type": "cable"},
        ],
        "quads": [
            {"name": "Barbell Back Squat",            "keywords": ["barbell back squat", "barbell squat"],       "max_sets": 4, "load_type": "plates"},
            {"name": "Leg Press",                     "keywords": ["leg press"],                                 "max_sets": 4, "load_type": "plate_loaded"},
            {"name": "Hack Squat",                    "keywords": ["hack squat"],                                "max_sets": 3, "load_type": "plate_loaded"},
            {"name": "Leg Extension",                 "keywords": ["leg extension"],                             "max_sets": 3, "load_type": "machine_plates"},
            {"name": "Walking Lunge",                 "keywords": ["walking lunge", "bulgarian split"],          "max_sets": 3, "load_type": "dumbbells"},
        ],
        "hamstrings": [
            {"name": "Romanian Deadlift",             "keywords": ["romanian deadlift"],                         "max_sets": 4, "load_type": "plates"},
            {"name": "Lying Leg Curl",                "keywords": ["lying leg curl"],                            "max_sets": 4, "load_type": "machine_plates"},
            {"name": "Seated Leg Curl",               "keywords": ["seated leg curl"],                           "max_sets": 3, "load_type": "machine_plates"},
            {"name": "Stiff-Leg Deadlift",            "keywords": ["stiff-leg deadlift"],                       "max_sets": 3, "load_type": "plates"},
        ],
        "glutes": [
            {"name": "Hip Thrust",                    "keywords": ["hip thrust"],                                "max_sets": 3, "load_type": "plates"},
            {"name": "Bulgarian Split Squat",         "keywords": ["bulgarian split", "walking lunge"],          "max_sets": 3, "load_type": "dumbbells"},
            {"name": "Cable Pull-Through",            "keywords": ["cable pull-through", "pull-through"],        "max_sets": 3, "load_type": "cable"},
            {"name": "Glute Bridge",                  "keywords": ["glute bridge"],                              "max_sets": 3, "load_type": "plates"},
        ],
        "biceps": [
            {"name": "Barbell Curl",                  "keywords": ["barbell curl"],                              "max_sets": 4, "load_type": "plates"},
            {"name": "Dumbbell Curl",                 "keywords": ["dumbbell curl"],                             "max_sets": 3, "load_type": "dumbbells"},
            {"name": "Preacher Curl",                 "keywords": ["preacher curl"],                             "max_sets": 3, "load_type": "plates"},
            {"name": "Hammer Curl",                   "keywords": ["hammer curl"],                               "max_sets": 3, "load_type": "dumbbells"},
            {"name": "Cable Curl",                    "keywords": ["cable curl"],                                "max_sets": 3, "load_type": "cable"},
        ],
        "triceps": [
            {"name": "Close-Grip Bench Press",        "keywords": ["close-grip bench press", "close grip bench"], "max_sets": 4, "load_type": "plates"},
            {"name": "Skull Crusher",                 "keywords": ["skull crusher"],                             "max_sets": 4, "load_type": "plates"},
            {"name": "Overhead Tricep Extension",     "keywords": ["overhead tricep extension", "overhead tricep ext"], "max_sets": 3, "load_type": "cable"},
            {"name": "Tricep Pushdown",               "keywords": ["tricep pushdown", "pushdown"],               "max_sets": 3, "load_type": "cable"},
        ],
        "calves": [
            {"name": "Standing Calf Raise",           "keywords": ["standing calf raise"],                       "max_sets": 4, "load_type": "machine_plates"},
            {"name": "Seated Calf Raise",             "keywords": ["seated calf raise"],                         "max_sets": 4, "load_type": "plate_loaded"},
            {"name": "Leg Press Calf Raise",          "keywords": ["leg press calf raise"],                      "max_sets": 3, "load_type": "plate_loaded"},
            {"name": "Single-Leg DB Calf Raise",      "keywords": ["single-leg", "single leg"],                  "max_sets": 3, "load_type": "dumbbells"},
        ],
        "abs": [
            {"name": "Cable Crunch",                  "keywords": ["cable crunch"],                              "max_sets": 4, "load_type": "cable"},
            {"name": "Hanging Leg Raise",             "keywords": ["hanging leg raise"],                         "max_sets": 3, "load_type": "bodyweight"},
            {"name": "Ab Wheel Rollout",              "keywords": ["ab wheel"],                                  "max_sets": 3, "load_type": "bodyweight"},
            {"name": "Decline Crunch",                "keywords": ["decline crunch"],                            "max_sets": 3, "load_type": "bodyweight"},
        ],
        "traps": [
            {"name": "Barbell Shrug",                 "keywords": ["barbell shrug"],                             "max_sets": 3, "load_type": "plates"},
            {"name": "Dumbbell Shrug",                "keywords": ["dumbbell shrug"],                            "max_sets": 2, "load_type": "dumbbells"},
        ],
        "forearms": [
            {"name": "Wrist Curl",                    "keywords": ["wrist curl"],                                "max_sets": 3, "load_type": "plates"},
            {"name": "Reverse Wrist Curl",            "keywords": ["reverse wrist curl"],                        "max_sets": 2, "load_type": "plates"},
        ],
    },

    # =========================================================================
    # WOMEN'S BIKINI — extreme glute dominance; avoid waist-thickening;
    # hip thrust P1 glutes; no heavy pressing; stomach vacuum for abs;
    # Good Morning included at cap 2 per spec (low axial load).
    # =========================================================================
    "womens_bikini": {
        "glutes": [
            {"name": "Hip Thrust",                    "keywords": ["hip thrust"],                                "max_sets": 4, "load_type": "plates"},
            {"name": "Deficit Reverse Lunge",         "keywords": ["deficit reverse lunge", "reverse lunge"],   "max_sets": 4, "load_type": "dumbbells"},
            {"name": "Cable Pull-Through",            "keywords": ["cable pull-through", "pull-through"],        "max_sets": 4, "load_type": "cable"},
            {"name": "45-Degree Hyperextension",      "keywords": ["hyperextension", "45 degree"],              "max_sets": 3, "load_type": "bodyweight"},
            {"name": "Step-Up",                       "keywords": ["step-up", "step up"],                       "max_sets": 3, "load_type": "dumbbells"},
            {"name": "Glute Bridge",                  "keywords": ["glute bridge"],                              "max_sets": 3, "load_type": "plates"},
        ],
        "hamstrings": [
            {"name": "Romanian Deadlift",             "keywords": ["romanian deadlift"],                         "max_sets": 4, "load_type": "plates"},
            {"name": "Lying Leg Curl",                "keywords": ["lying leg curl"],                            "max_sets": 4, "load_type": "machine_plates"},
            {"name": "Seated Leg Curl",               "keywords": ["seated leg curl"],                           "max_sets": 3, "load_type": "machine_plates"},
            # Good Morning at low cap — spinal load is minimal at 2 sets
            {"name": "Good Morning",                  "keywords": ["good morning"],                              "max_sets": 2, "load_type": "plates"},
        ],
        "quads": [
            # High/wide foot placement biases glutes over quads on leg press
            {"name": "Leg Press (High Foot)",         "keywords": ["leg press"],                                 "max_sets": 4, "load_type": "plate_loaded"},
            {"name": "Walking Lunge",                 "keywords": ["walking lunge"],                             "max_sets": 3, "load_type": "dumbbells"},
            {"name": "Bulgarian Split Squat",         "keywords": ["bulgarian split"],                           "max_sets": 3, "load_type": "dumbbells"},
            {"name": "Leg Extension",                 "keywords": ["leg extension"],                             "max_sets": 3, "load_type": "machine_plates"},
        ],
        "back": [
            {"name": "Seated Cable Row",              "keywords": ["seated cable row", "cable row"],             "max_sets": 4, "load_type": "cable"},
            {"name": "Lat Pulldown",                  "keywords": ["lat pulldown", "pulldown"],                  "max_sets": 4, "load_type": "cable"},
            {"name": "Dumbbell Row",                  "keywords": ["dumbbell row"],                              "max_sets": 3, "load_type": "dumbbells"},
            {"name": "Straight Arm Pulldown",         "keywords": ["straight arm pulldown"],                     "max_sets": 3, "load_type": "cable"},
        ],
        "shoulders": [
            {"name": "Lateral Raise",                 "keywords": ["lateral raise"],                             "max_sets": 4, "load_type": "dumbbells"},
            {"name": "Cable Lateral Raise",           "keywords": ["cable lateral raise"],                       "max_sets": 4, "load_type": "cable"},
            {"name": "Rear Delt Fly",                 "keywords": ["rear delt fly", "rear delt", "face pull"],  "max_sets": 3, "load_type": "machine_plates"},
            {"name": "Dumbbell Shoulder Press",       "keywords": ["dumbbell shoulder press"],                   "max_sets": 2, "load_type": "dumbbells"},
        ],
        "chest": [
            {"name": "Cable Fly",                     "keywords": ["cable fly", "cable crossover"],              "max_sets": 3, "load_type": "cable"},
            {"name": "Pec Deck",                      "keywords": ["pec deck"],                                  "max_sets": 3, "load_type": "machine_plates"},
            {"name": "Incline Dumbbell Press",        "keywords": ["incline dumbbell"],                          "max_sets": 2, "load_type": "dumbbells"},
            {"name": "Dumbbell Bench Press",          "keywords": ["dumbbell bench press"],                      "max_sets": 2, "load_type": "dumbbells"},
        ],
        "biceps": [
            {"name": "Dumbbell Curl",                 "keywords": ["dumbbell curl"],                             "max_sets": 3, "load_type": "dumbbells"},
            {"name": "Hammer Curl",                   "keywords": ["hammer curl"],                               "max_sets": 3, "load_type": "dumbbells"},
            {"name": "Cable Curl",                    "keywords": ["cable curl"],                                "max_sets": 3, "load_type": "cable"},
            {"name": "Preacher Curl Machine",         "keywords": ["preacher curl machine", "machine preacher", "preacher curl"], "max_sets": 2, "load_type": "machine_plates"},
        ],
        "triceps": [
            {"name": "Overhead Tricep Extension",     "keywords": ["overhead tricep extension", "overhead tricep ext"], "max_sets": 3, "load_type": "cable"},
            {"name": "Tricep Pushdown",               "keywords": ["tricep pushdown", "pushdown"],               "max_sets": 3, "load_type": "cable"},
            {"name": "Cable Kickback",                "keywords": ["cable kickback"],                            "max_sets": 2, "load_type": "cable"},
            {"name": "Skull Crusher",                 "keywords": ["skull crusher"],                             "max_sets": 2, "load_type": "plates"},
        ],
        "calves": [
            {"name": "Standing Calf Raise",           "keywords": ["standing calf raise"],                       "max_sets": 4, "load_type": "machine_plates"},
            {"name": "Seated Calf Raise",             "keywords": ["seated calf raise"],                         "max_sets": 3, "load_type": "plate_loaded"},
            {"name": "Leg Press Calf Raise",          "keywords": ["leg press calf raise"],                      "max_sets": 3, "load_type": "plate_loaded"},
            {"name": "Single-Leg DB Calf Raise",      "keywords": ["single-leg", "single leg"],                  "max_sets": 2, "load_type": "dumbbells"},
        ],
        "abs": [
            # Stomach vacuum and planks protect waist tightness; NO weighted spinal flexion
            {"name": "Front Plank",                   "keywords": ["plank"],                                     "max_sets": 3, "load_type": "bodyweight"},
            {"name": "Stomach Vacuum",                "keywords": ["stomach vacuum", "vacuum"],                  "max_sets": 3, "load_type": "bodyweight"},
            {"name": "Bodyweight Leg Raise",          "keywords": ["bodyweight leg raise", "leg raise"],         "max_sets": 2, "load_type": "bodyweight"},
            {"name": "Ab Wheel Rollout",              "keywords": ["ab wheel"],                                  "max_sets": 2, "load_type": "bodyweight"},
        ],
        "traps": [
            {"name": "Dumbbell Shrug",                "keywords": ["dumbbell shrug"],                            "max_sets": 2, "load_type": "dumbbells"},
        ],
        "forearms": [
            {"name": "Wrist Curl",                    "keywords": ["wrist curl"],                                "max_sets": 2, "load_type": "plates"},
        ],
    },

    # =========================================================================
    # WOMEN'S FIGURE — V-taper + glutes; more muscle than Bikini;
    # lat pulldown P1 (width judged first); no barbell overhead press
    # (upper trap growth slopes neckline and destroys clavicular V-line);
    # cable fly leads chest (tone without upper-body mass buildup).
    # =========================================================================
    "womens_figure": {
        # Width P1 for Figure's primary judging criterion
        "back": [
            {"name": "Lat Pulldown",                  "keywords": ["lat pulldown", "pulldown"],                  "max_sets": 4, "load_type": "cable"},
            {"name": "Seated Cable Row",              "keywords": ["seated cable row", "cable row"],             "max_sets": 4, "load_type": "cable"},
            {"name": "Dumbbell Row",                  "keywords": ["dumbbell row"],                              "max_sets": 4, "load_type": "dumbbells"},
            {"name": "Straight Arm Pulldown",         "keywords": ["straight arm pulldown"],                     "max_sets": 3, "load_type": "cable"},
            {"name": "Weighted Pull-Up",              "keywords": ["weighted pull-up", "pull-up", "pullup"],     "max_sets": 3, "load_type": "bodyweight"},
            {"name": "T-Bar Row",                     "keywords": ["t-bar row"],                                 "max_sets": 3, "load_type": "plates"},
        ],
        "glutes": [
            {"name": "Hip Thrust",                    "keywords": ["hip thrust"],                                "max_sets": 4, "load_type": "plates"},
            {"name": "Romanian Deadlift",             "keywords": ["romanian deadlift"],                         "max_sets": 4, "load_type": "plates"},
            {"name": "Deficit Reverse Lunge",         "keywords": ["deficit reverse lunge", "reverse lunge"],   "max_sets": 3, "load_type": "dumbbells"},
            {"name": "Cable Pull-Through",            "keywords": ["cable pull-through", "pull-through"],        "max_sets": 3, "load_type": "cable"},
            {"name": "Bulgarian Split Squat",         "keywords": ["bulgarian split"],                           "max_sets": 3, "load_type": "dumbbells"},
        ],
        "shoulders": [
            {"name": "Lateral Raise",                 "keywords": ["lateral raise"],                             "max_sets": 4, "load_type": "dumbbells"},
            {"name": "Dumbbell Shoulder Press",       "keywords": ["dumbbell shoulder press"],                   "max_sets": 4, "load_type": "dumbbells"},
            {"name": "Cable Lateral Raise",           "keywords": ["cable lateral raise"],                       "max_sets": 3, "load_type": "cable"},
            {"name": "Rear Delt Fly",                 "keywords": ["rear delt fly", "rear delt", "face pull"],  "max_sets": 4, "load_type": "machine_plates"},
        ],
        "quads": [
            {"name": "Leg Press",                     "keywords": ["leg press"],                                 "max_sets": 4, "load_type": "plate_loaded"},
            {"name": "Hack Squat",                    "keywords": ["hack squat"],                                "max_sets": 3, "load_type": "plate_loaded"},
            {"name": "Bulgarian Split Squat",         "keywords": ["bulgarian split"],                           "max_sets": 3, "load_type": "dumbbells"},
            {"name": "Leg Extension",                 "keywords": ["leg extension"],                             "max_sets": 3, "load_type": "machine_plates"},
            {"name": "Walking Lunge",                 "keywords": ["walking lunge"],                             "max_sets": 3, "load_type": "dumbbells"},
        ],
        "hamstrings": [
            {"name": "Romanian Deadlift",             "keywords": ["romanian deadlift"],                         "max_sets": 4, "load_type": "plates"},
            {"name": "Lying Leg Curl",                "keywords": ["lying leg curl"],                            "max_sets": 4, "load_type": "machine_plates"},
            {"name": "Seated Leg Curl",               "keywords": ["seated leg curl"],                           "max_sets": 3, "load_type": "machine_plates"},
            {"name": "Glute-Ham Raise",               "keywords": ["glute-ham raise", "glute ham raise", "ghr"], "max_sets": 3, "load_type": "bodyweight"},
        ],
        # Cable fly leads — chest tone without mass buildup
        "chest": [
            {"name": "Incline Dumbbell Press",        "keywords": ["incline dumbbell"],                          "max_sets": 3, "load_type": "dumbbells"},
            {"name": "Cable Fly / Crossover",         "keywords": ["cable fly", "cable crossover"],              "max_sets": 4, "load_type": "cable"},
            {"name": "Pec Deck",                      "keywords": ["pec deck"],                                  "max_sets": 3, "load_type": "machine_plates"},
            {"name": "Dumbbell Bench Press",          "keywords": ["dumbbell bench press"],                      "max_sets": 2, "load_type": "dumbbells"},
        ],
        "biceps": [
            {"name": "Dumbbell Curl",                 "keywords": ["dumbbell curl"],                             "max_sets": 3, "load_type": "dumbbells"},
            {"name": "Hammer Curl",                   "keywords": ["hammer curl"],                               "max_sets": 3, "load_type": "dumbbells"},
            {"name": "Cable Curl",                    "keywords": ["cable curl"],                                "max_sets": 3, "load_type": "cable"},
            {"name": "Preacher Curl",                 "keywords": ["preacher curl"],                             "max_sets": 2, "load_type": "plates"},
        ],
        "triceps": [
            {"name": "Tricep Pushdown",               "keywords": ["tricep pushdown", "pushdown"],               "max_sets": 4, "load_type": "cable"},
            {"name": "Overhead Tricep Extension",     "keywords": ["overhead tricep extension", "overhead tricep ext"], "max_sets": 3, "load_type": "cable"},
            {"name": "Skull Crusher",                 "keywords": ["skull crusher"],                             "max_sets": 2, "load_type": "plates"},
            {"name": "Cable Kickback",                "keywords": ["cable kickback"],                            "max_sets": 2, "load_type": "cable"},
        ],
        "calves": [
            {"name": "Standing Calf Raise",           "keywords": ["standing calf raise"],                       "max_sets": 4, "load_type": "machine_plates"},
            {"name": "Seated Calf Raise",             "keywords": ["seated calf raise"],                         "max_sets": 3, "load_type": "plate_loaded"},
            {"name": "Leg Press Calf Raise",          "keywords": ["leg press calf raise"],                      "max_sets": 3, "load_type": "plate_loaded"},
            {"name": "Single-Leg DB Calf Raise",      "keywords": ["single-leg", "single leg"],                  "max_sets": 2, "load_type": "dumbbells"},
        ],
        "abs": [
            {"name": "Cable Crunch",                  "keywords": ["cable crunch"],                              "max_sets": 4, "load_type": "cable"},
            {"name": "Hanging Leg Raise",             "keywords": ["hanging leg raise"],                         "max_sets": 3, "load_type": "bodyweight"},
            {"name": "Ab Wheel Rollout",              "keywords": ["ab wheel"],                                  "max_sets": 2, "load_type": "bodyweight"},
            {"name": "Plank",                         "keywords": ["plank"],                                     "max_sets": 2, "load_type": "bodyweight"},
        ],
        "traps": [
            {"name": "Dumbbell Shrug",                "keywords": ["dumbbell shrug"],                            "max_sets": 2, "load_type": "dumbbells"},
        ],
        "forearms": [
            {"name": "Wrist Curl",                    "keywords": ["wrist curl"],                                "max_sets": 2, "load_type": "plates"},
        ],
    },

    # =========================================================================
    # WOMEN'S PHYSIQUE — full development closest to Men's Open proportions;
    # dumbbell/cable preferred throughout for aesthetic roundness and joint
    # health; seated cable row P1 back (thickness + width simultaneously);
    # incline DB press leads chest; dumbbell press P1 shoulders.
    # =========================================================================
    "womens_physique": {
        "chest": [
            {"name": "Incline Dumbbell Press",        "keywords": ["incline dumbbell", "incline dumbbell press"], "max_sets": 4, "load_type": "dumbbells"},
            {"name": "Dumbbell Bench Press",          "keywords": ["dumbbell bench press"],                      "max_sets": 4, "load_type": "dumbbells"},
            {"name": "Cable Fly / Crossover",         "keywords": ["cable fly", "cable crossover"],              "max_sets": 4, "load_type": "cable"},
            {"name": "Pec Deck",                      "keywords": ["pec deck"],                                  "max_sets": 3, "load_type": "machine_plates"},
            {"name": "Incline Barbell Press",         "keywords": ["incline barbell"],                           "max_sets": 3, "load_type": "plates"},
        ],
        "back": [
            {"name": "Seated Cable Row",              "keywords": ["seated cable row", "cable row"],             "max_sets": 4, "load_type": "cable"},
            {"name": "Lat Pulldown",                  "keywords": ["lat pulldown", "pulldown"],                  "max_sets": 4, "load_type": "cable"},
            {"name": "Dumbbell Row",                  "keywords": ["dumbbell row"],                              "max_sets": 4, "load_type": "dumbbells"},
            {"name": "Weighted Pull-Up",              "keywords": ["weighted pull-up", "pull-up", "pullup"],     "max_sets": 3, "load_type": "bodyweight"},
            {"name": "Barbell Row",                   "keywords": ["barbell row"],                               "max_sets": 3, "load_type": "plates"},
            {"name": "Straight Arm Pulldown",         "keywords": ["straight arm pulldown"],                     "max_sets": 3, "load_type": "cable"},
        ],
        "shoulders": [
            {"name": "Dumbbell Shoulder Press",       "keywords": ["dumbbell shoulder press"],                   "max_sets": 4, "load_type": "dumbbells"},
            {"name": "Lateral Raise",                 "keywords": ["lateral raise"],                             "max_sets": 4, "load_type": "dumbbells"},
            {"name": "Cable Lateral Raise",           "keywords": ["cable lateral raise"],                       "max_sets": 4, "load_type": "cable"},
            {"name": "Rear Delt Fly",                 "keywords": ["rear delt fly", "rear delt", "face pull"],  "max_sets": 4, "load_type": "machine_plates"},
        ],
        "quads": [
            {"name": "Leg Press",                     "keywords": ["leg press"],                                 "max_sets": 4, "load_type": "plate_loaded"},
            {"name": "Bulgarian Split Squat",         "keywords": ["bulgarian split"],                           "max_sets": 4, "load_type": "dumbbells"},
            {"name": "Hack Squat",                    "keywords": ["hack squat"],                                "max_sets": 3, "load_type": "plate_loaded"},
            {"name": "Leg Extension",                 "keywords": ["leg extension"],                             "max_sets": 3, "load_type": "machine_plates"},
            # Barbell squat demoted — waist-thickening axial load not needed
            {"name": "Barbell Back Squat",            "keywords": ["barbell back squat", "barbell squat"],       "max_sets": 2, "load_type": "plates"},
        ],
        "hamstrings": [
            {"name": "Romanian Deadlift",             "keywords": ["romanian deadlift"],                         "max_sets": 4, "load_type": "plates"},
            {"name": "Lying Leg Curl",                "keywords": ["lying leg curl"],                            "max_sets": 4, "load_type": "machine_plates"},
            {"name": "Seated Leg Curl",               "keywords": ["seated leg curl"],                           "max_sets": 3, "load_type": "machine_plates"},
            {"name": "Stiff-Leg Deadlift",            "keywords": ["stiff-leg deadlift"],                       "max_sets": 3, "load_type": "plates"},
        ],
        "glutes": [
            {"name": "Hip Thrust",                    "keywords": ["hip thrust"],                                "max_sets": 4, "load_type": "plates"},
            {"name": "Romanian Deadlift",             "keywords": ["romanian deadlift"],                         "max_sets": 3, "load_type": "plates"},
            {"name": "Cable Pull-Through",            "keywords": ["cable pull-through", "pull-through"],        "max_sets": 3, "load_type": "cable"},
            {"name": "Glute Bridge",                  "keywords": ["glute bridge"],                              "max_sets": 3, "load_type": "plates"},
        ],
        "biceps": [
            {"name": "Dumbbell Curl",                 "keywords": ["dumbbell curl"],                             "max_sets": 4, "load_type": "dumbbells"},
            {"name": "Hammer Curl",                   "keywords": ["hammer curl"],                               "max_sets": 3, "load_type": "dumbbells"},
            {"name": "Preacher Curl",                 "keywords": ["preacher curl"],                             "max_sets": 3, "load_type": "plates"},
            {"name": "Cable Curl",                    "keywords": ["cable curl"],                                "max_sets": 3, "load_type": "cable"},
        ],
        "triceps": [
            {"name": "Overhead Tricep Extension",     "keywords": ["overhead tricep extension", "overhead tricep ext"], "max_sets": 4, "load_type": "cable"},
            {"name": "Tricep Pushdown",               "keywords": ["tricep pushdown", "pushdown"],               "max_sets": 4, "load_type": "cable"},
            {"name": "Skull Crusher",                 "keywords": ["skull crusher"],                             "max_sets": 3, "load_type": "plates"},
            {"name": "Cable Kickback",                "keywords": ["cable kickback"],                            "max_sets": 3, "load_type": "cable"},
        ],
        "calves": [
            {"name": "Standing Calf Raise",           "keywords": ["standing calf raise"],                       "max_sets": 4, "load_type": "machine_plates"},
            {"name": "Seated Calf Raise",             "keywords": ["seated calf raise"],                         "max_sets": 4, "load_type": "plate_loaded"},
            {"name": "Leg Press Calf Raise",          "keywords": ["leg press calf raise"],                      "max_sets": 3, "load_type": "plate_loaded"},
            {"name": "Single-Leg DB Calf Raise",      "keywords": ["single-leg", "single leg"],                  "max_sets": 3, "load_type": "dumbbells"},
        ],
        "abs": [
            {"name": "Cable Crunch",                  "keywords": ["cable crunch"],                              "max_sets": 4, "load_type": "cable"},
            {"name": "Hanging Leg Raise",             "keywords": ["hanging leg raise"],                         "max_sets": 3, "load_type": "bodyweight"},
            {"name": "Ab Wheel Rollout",              "keywords": ["ab wheel"],                                  "max_sets": 3, "load_type": "bodyweight"},
            {"name": "Decline Crunch",                "keywords": ["decline crunch"],                            "max_sets": 3, "load_type": "bodyweight"},
        ],
        "traps": [
            {"name": "Dumbbell Shrug",                "keywords": ["dumbbell shrug"],                            "max_sets": 2, "load_type": "dumbbells"},
        ],
        "forearms": [
            {"name": "Wrist Curl",                    "keywords": ["wrist curl"],                                "max_sets": 2, "load_type": "plates"},
            {"name": "Reverse Wrist Curl",            "keywords": ["reverse wrist curl"],                        "max_sets": 2, "load_type": "plates"},
        ],
    },
}

# Fallback: map any unknown division to mens_open
_DIVISION_ALIASES = {
    "open": "mens_open",
    "mens open": "mens_open",
    "classic": "classic_physique",
    "physique": "mens_physique",
    "bikini": "womens_bikini",
    "figure": "womens_figure",
    "womens physique": "womens_physique",
}


def get_exercise_priorities(
    division: str,
    muscle: str,
) -> list[ExercisePrioritySlot]:
    """
    Return the ordered exercise priority cascade for a division + muscle.

    Falls back to mens_open priorities for any unknown division/muscle.
    """
    key = division.lower().replace(" ", "_") if division else "mens_open"
    key = _DIVISION_ALIASES.get(key, key)
    division_priorities = DIVISION_EXERCISE_PRIORITIES.get(
        key, DIVISION_EXERCISE_PRIORITIES["mens_open"]
    )
    return division_priorities.get(
        muscle.lower(),
        DIVISION_EXERCISE_PRIORITIES["mens_open"].get(muscle.lower(), []),
    )


def gap_adjusted_cap(max_sets: int, hqi: float, is_top_priority: bool) -> int:
    """
    Adjust the per-exercise max set cap based on how lagging the muscle is.

    Only the top-priority (P1) exercise receives a boosted cap so the most
    effective stimulus is concentrated before cascading to secondary movements.

    Args:
        max_sets: Base cap from the priority table.
        hqi: HQI score for this muscle (0-100).
        is_top_priority: True only for the first (highest priority) slot.

    Returns:
        Adjusted integer cap (always ≥ max_sets).
    """
    if not is_top_priority:
        return max_sets
    if hqi < 40:
        return round(max_sets * 1.5)    # severe lag: concentrate stimulus
    if hqi < 65:
        return round(max_sets * 1.25)   # moderate lag: slight concentration
    return max_sets
