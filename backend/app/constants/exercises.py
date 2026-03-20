# Seed exercise database
# Each exercise: (name, primary_muscle, secondary_muscles, movement_pattern, equipment, biomech_efficiency, fatigue_ratio)

SEED_EXERCISES = [
    # Chest
    ("Barbell Bench Press", "chest", "triceps,front_delt", "push", "barbell", 1.0, 1.0),
    ("Incline Barbell Press", "chest", "triceps,front_delt", "push", "barbell", 0.95, 0.95),
    ("Dumbbell Bench Press", "chest", "triceps,front_delt", "push", "dumbbell", 0.90, 0.85),
    ("Incline Dumbbell Press", "chest", "triceps,front_delt", "push", "dumbbell", 0.88, 0.82),
    ("Cable Fly", "chest", "", "push", "cable", 0.75, 0.50),
    ("Pec Deck", "chest", "", "push", "machine", 0.70, 0.45),
    ("Dips (Chest)", "chest", "triceps,front_delt", "push", "bodyweight", 0.85, 0.90),
    # Back
    ("Barbell Row", "back", "biceps,rear_delt", "pull", "barbell", 1.0, 1.0),
    ("Weighted Pull-Up", "back", "biceps", "pull", "bodyweight", 0.95, 0.90),
    ("Lat Pulldown", "back", "biceps", "pull", "cable", 0.85, 0.70),
    ("Seated Cable Row", "back", "biceps,rear_delt", "pull", "cable", 0.88, 0.75),
    ("Dumbbell Row", "back", "biceps,rear_delt", "pull", "dumbbell", 0.90, 0.80),
    ("T-Bar Row", "back", "biceps,rear_delt", "pull", "barbell", 0.92, 0.90),
    ("Face Pull", "rear_delt", "traps", "pull", "cable", 0.70, 0.40),
    ("Straight Arm Pulldown", "back", "", "pull", "cable", 0.72, 0.45),
    # Shoulders
    ("Overhead Press", "front_delt", "triceps,traps", "push", "barbell", 1.0, 1.0),
    ("Dumbbell Shoulder Press", "front_delt", "triceps,traps", "push", "dumbbell", 0.90, 0.85),
    ("Lateral Raise", "side_delt", "", "push", "dumbbell", 0.75, 0.40),
    ("Cable Lateral Raise", "side_delt", "", "push", "cable", 0.78, 0.38),
    ("Rear Delt Fly", "rear_delt", "", "pull", "dumbbell", 0.70, 0.35),
    ("Upright Row", "side_delt", "traps,front_delt", "pull", "barbell", 0.80, 0.75),
    # Arms
    ("Barbell Curl", "biceps", "", "pull", "barbell", 1.0, 0.60),
    ("Dumbbell Curl", "biceps", "", "pull", "dumbbell", 0.90, 0.50),
    ("Hammer Curl", "biceps", "forearms", "pull", "dumbbell", 0.85, 0.50),
    ("Preacher Curl", "biceps", "", "pull", "barbell", 0.82, 0.45),
    ("Cable Curl", "biceps", "", "pull", "cable", 0.80, 0.40),
    ("Close-Grip Bench Press", "triceps", "chest", "push", "barbell", 0.95, 0.85),
    ("Skull Crusher", "triceps", "", "push", "barbell", 0.88, 0.60),
    ("Tricep Pushdown", "triceps", "", "push", "cable", 0.82, 0.45),
    ("Overhead Tricep Extension", "triceps", "", "push", "cable", 0.80, 0.50),
    ("Dips (Triceps)", "triceps", "chest,front_delt", "push", "bodyweight", 0.90, 0.80),
    # Legs - Quads
    ("Barbell Back Squat", "quads", "glutes,hamstrings", "squat", "barbell", 1.0, 1.0),
    ("Front Squat", "quads", "glutes", "squat", "barbell", 0.92, 0.95),
    ("Leg Press", "quads", "glutes", "squat", "machine", 0.85, 0.80),
    ("Hack Squat", "quads", "glutes", "squat", "machine", 0.88, 0.85),
    ("Leg Extension", "quads", "", "squat", "machine", 0.70, 0.45),
    ("Walking Lunge", "quads", "glutes,hamstrings", "squat", "dumbbell", 0.82, 0.90),
    ("Bulgarian Split Squat", "quads", "glutes", "squat", "dumbbell", 0.85, 0.85),
    # Legs - Hamstrings
    ("Romanian Deadlift", "hamstrings", "glutes,back", "hinge", "barbell", 1.0, 1.0),
    ("Lying Leg Curl", "hamstrings", "", "hinge", "machine", 0.80, 0.50),
    ("Seated Leg Curl", "hamstrings", "", "hinge", "machine", 0.78, 0.48),
    ("Stiff-Leg Deadlift", "hamstrings", "glutes,back", "hinge", "barbell", 0.95, 0.95),
    ("Good Morning", "hamstrings", "glutes,back", "hinge", "barbell", 0.85, 0.90),
    # Legs - Glutes
    ("Step-Up", "glutes", "quads,hamstrings", "squat", "dumbbell", 1.0, 0.65),
    ("Hip Thrust", "glutes", "hamstrings", "hinge", "barbell", 1.0, 0.75),
    ("Cable Pull-Through", "glutes", "hamstrings", "hinge", "cable", 0.78, 0.50),
    ("Glute Bridge", "glutes", "hamstrings", "hinge", "barbell", 0.80, 0.55),
    # Legs - Calves
    ("Standing Calf Raise", "calves", "", "squat", "machine", 1.0, 0.40),
    ("Seated Calf Raise", "calves", "", "squat", "machine", 0.85, 0.35),
    # Compound
    ("Conventional Deadlift", "back", "hamstrings,glutes,quads,traps", "hinge", "barbell", 1.0, 1.0),
    ("Sumo Deadlift", "back", "quads,glutes,hamstrings", "hinge", "barbell", 0.95, 0.95),
    ("Power Clean", "back", "quads,glutes,traps", "hinge", "barbell", 0.80, 0.95),
    # Traps / Neck
    ("Barbell Shrug", "traps", "", "pull", "barbell", 0.90, 0.50),
    ("Dumbbell Shrug", "traps", "", "pull", "dumbbell", 0.85, 0.45),
    ("Farmer's Walk", "traps", "forearms,core", "carry", "dumbbell", 0.80, 0.85),
    # Core
    ("Cable Crunch", "abs", "", "push", "cable", 0.80, 0.40),
    ("Hanging Leg Raise", "abs", "", "pull", "bodyweight", 0.85, 0.50),
    ("Ab Wheel Rollout", "abs", "", "push", "bodyweight", 0.82, 0.55),
    ("Plank", "abs", "", "push", "bodyweight", 0.60, 0.30),
    # Forearms
    ("Wrist Curl", "forearms", "", "pull", "barbell", 0.80, 0.30),
    ("Reverse Wrist Curl", "forearms", "", "pull", "barbell", 0.75, 0.28),
]
