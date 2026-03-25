from __future__ import annotations

"""
Biomechanical Exercise Selection

Scores and selects exercises for a target muscle group using the
Stimulus-to-Fatigue Ratio (SFR) weighted by priority.

SFR_exercise = efficiency / fatigue_ratio
Score        = SFR x priority_score

Higher scores indicate exercises that deliver more hypertrophic stimulus
per unit of systemic / local fatigue, adjusted for the athlete's current
muscle-priority ranking.

Movement Pattern Diversity
--------------------------
Ensures that each muscle group's exercise selection covers the full range
of relevant movement patterns before allowing duplicate patterns.  This
prevents over-reliance on a single movement angle and maximizes overall
stimulus distribution.
"""

from typing import Any


# ---------------------------------------------------------------------------
# Movement pattern taxonomy
# ---------------------------------------------------------------------------

MOVEMENT_PATTERNS: dict[str, list[str]] = {
    "horizontal_push": ["bench press", "push up", "chest press", "dumbbell press flat", "pec deck"],
    "incline_push": ["incline press", "incline fly", "incline dumbbell"],
    "vertical_push": ["overhead press", "military press", "arnold press", "lateral raise"],
    "horizontal_pull": ["barbell row", "cable row", "seated row", "dumbbell row"],
    "vertical_pull": ["lat pulldown", "pull up", "chin up"],
    "hip_hinge": ["deadlift", "romanian deadlift", "good morning", "hip thrust"],
    "knee_dominant": ["squat", "leg press", "leg extension", "lunge", "hack squat"],
    "isolation_curl": ["curl", "preacher", "concentration"],
    "isolation_extension": ["tricep", "pushdown", "skull crusher", "overhead extension"],
}

# ---------------------------------------------------------------------------
# Anatomical sub-region classification
# ---------------------------------------------------------------------------
# Enables the engine to guarantee full coverage of all functional heads
# within a composite muscle group (e.g. all 3 delt heads for shoulders).

SUB_REGION_KEYWORDS: dict[str, dict[str, list[str]]] = {
    "shoulders": {
        "front":   ["overhead press", "military press", "arnold press", "front raise",
                    "shoulder press", "barbell press", "dumbbell press"],
        "lateral": ["lateral raise", "side raise", "upright row", "cable lateral",
                    "side delt", "lateral delt"],
        "rear":    ["rear delt", "face pull", "reverse fly", "reverse pec",
                    "bent over fly", "bent-over fly", "rear fly"],
    },
    "chest": {
        "upper":  ["incline", "low-to-high", "low to high"],
        "mid":    ["bench press", "flat press", "flat bench", "pec deck",
                   "chest press", "dumbbell press"],
        "lower":  ["decline", "dip", "high-to-low", "high to low"],
    },
    "back": {
        "width":     ["pulldown", "pull-up", "pullup", "chin up", "chin-up",
                      "straight arm pulldown"],
        "thickness": ["row", "t-bar", "barbell row", "cable row", "dumbbell row",
                      "seated row"],
        "erectors":  ["deadlift", "good morning", "hyperextension", "back extension"],
    },
}

# Required sub-regions: if a muscle has a significant gap, the engine MUST
# include at least one exercise from each of these sub-regions per week.
REQUIRED_SUB_REGIONS: dict[str, list[str]] = {
    "shoulders": ["front", "lateral", "rear"],
    "chest":     ["upper", "mid"],
    "back":      ["width", "thickness"],
}


def classify_sub_region(muscle_group: str, exercise_name: str) -> str | None:
    """
    Classify an exercise into its anatomical sub-region.

    Args:
        muscle_group: The parent muscle group (e.g. ``"shoulders"``).
        exercise_name: The exercise name to classify.

    Returns:
        Sub-region string (e.g. ``"lateral"``) or ``None`` if unclassifiable.
    """
    regions = SUB_REGION_KEYWORDS.get(muscle_group.lower(), {})
    name_lower = exercise_name.lower()
    for region, keywords in regions.items():
        if any(kw in name_lower for kw in keywords):
            return region
    return None


# Map muscle groups to relevant movement pattern categories.
_MUSCLE_RELEVANT_PATTERNS: dict[str, list[str]] = {
    "chest":      ["horizontal_push", "incline_push"],
    "back":       ["horizontal_pull", "vertical_pull"],
    "front_delt": ["vertical_push", "incline_push"],
    "side_delt":  ["vertical_push"],
    "rear_delt":  ["horizontal_pull"],
    "quads":      ["knee_dominant"],
    "hamstrings": ["hip_hinge", "knee_dominant"],
    "glutes":     ["hip_hinge", "knee_dominant"],
    "biceps":     ["isolation_curl", "vertical_pull"],
    "triceps":    ["isolation_extension", "horizontal_push", "vertical_push"],
    "calves":     [],
    "forearms":   ["isolation_curl"],
    "abs":        [],
    "traps":      ["vertical_pull"],
}


def classify_exercise_pattern(exercise_name: str) -> str | None:
    """
    Return the movement pattern category for a given exercise name.

    Performs a case-insensitive substring match against the exercises listed
    in :data:`MOVEMENT_PATTERNS`.

    Args:
        exercise_name: The exercise name to classify (e.g. ``"incline
                       dumbbell press"``).

    Returns:
        The pattern category string (e.g. ``"incline_push"``), or ``None``
        if no match is found.
    """
    name_lower = exercise_name.lower().strip()

    for pattern, exercises in MOVEMENT_PATTERNS.items():
        for ex in exercises:
            if ex in name_lower or name_lower in ex:
                return pattern

    return None


def ensure_pattern_diversity(
    selected_exercises: list[dict[str, Any]],
    muscle_group: str,
) -> list[str]:
    """
    Identify movement pattern categories that are missing from the current
    exercise selection for a muscle group.

    For each muscle group, at least one exercise from each relevant pattern
    category should be included before allowing duplicate patterns.

    Args:
        selected_exercises: List of exercise dicts already chosen.  Each
                            must have a ``"name"`` key.
        muscle_group: The target muscle group (e.g. ``"chest"``, ``"back"``).

    Returns:
        List of missing movement pattern names that should still be covered.
        Empty list if all relevant patterns are represented.
    """
    relevant_patterns = _MUSCLE_RELEVANT_PATTERNS.get(
        muscle_group.lower(), [],
    )

    if not relevant_patterns:
        return []

    # Determine which patterns are already covered by the selected exercises.
    covered: set[str] = set()
    for ex in selected_exercises:
        name = ex.get("name", "")
        pattern = classify_exercise_pattern(name)
        if pattern and pattern in relevant_patterns:
            covered.add(pattern)

    missing = [p for p in relevant_patterns if p not in covered]
    return missing


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------

def score_exercise(
    efficiency: float,
    fatigue_ratio: float,
    priority_score_for_muscle: float,
) -> float:
    """
    Compute a composite selection score for a single exercise.

    Args:
        efficiency: How effectively the exercise stimulates the target
                    muscle (0-10 scale, higher = better).
        fatigue_ratio: Systemic/local fatigue cost of the exercise
                       (> 0; 1.0 = neutral, higher = more fatiguing).
        priority_score_for_muscle: Current priority weight for the target
                                   muscle (e.g. 0-10).  Derived from PDS
                                   deficits or coach overrides.

    Returns:
        Composite score (higher is better), rounded to two decimals.

    Raises:
        ValueError: If fatigue_ratio is non-positive.
    """
    if fatigue_ratio <= 0:
        raise ValueError("fatigue_ratio must be > 0")

    sfr = efficiency / fatigue_ratio
    return round(sfr * priority_score_for_muscle, 2)


def compute_sfr(efficiency: float, fatigue_ratio: float) -> float:
    """
    Compute the raw Stimulus-to-Fatigue Ratio.

    Args:
        efficiency: Exercise efficiency for the target muscle (0-10).
        fatigue_ratio: Fatigue cost (> 0).

    Returns:
        SFR value, rounded to two decimals.

    Raises:
        ValueError: If fatigue_ratio is non-positive.
    """
    if fatigue_ratio <= 0:
        raise ValueError("fatigue_ratio must be > 0")
    return round(efficiency / fatigue_ratio, 2)


def select_exercises(
    available_exercises: list[dict[str, Any]],
    muscle_group: str,
    n_exercises: int,
    priority: float,
) -> list[dict[str, Any]]:
    """
    Select the top *n_exercises* for a given muscle group.

    Each dict in *available_exercises* must contain at least::

        {
            "name": str,
            "muscle_group": str,
            "efficiency": float,      # 0-10
            "fatigue_ratio": float,    # > 0
        }

    Args:
        available_exercises: Pool of candidate exercises.
        muscle_group: Target muscle (must match exercise ``muscle_group``).
        n_exercises: How many exercises to return.
        priority: Priority weight for the target muscle, passed through to
                  :func:`score_exercise`.

    Returns:
        Up to *n_exercises* dicts from the input list, each augmented with
        ``"score"`` and ``"sfr"`` keys, sorted descending by score.
    """
    candidates: list[dict[str, Any]] = []

    for ex in available_exercises:
        if ex.get("muscle_group", "").lower() != muscle_group.lower():
            continue

        efficiency: float = ex.get("efficiency", 0.0)
        fatigue_ratio: float = ex.get("fatigue_ratio", 1.0)

        if fatigue_ratio <= 0:
            continue

        sfr = compute_sfr(efficiency, fatigue_ratio)
        sc = score_exercise(efficiency, fatigue_ratio, priority)

        result = {**ex, "sfr": sfr, "score": sc}
        candidates.append(result)

    candidates.sort(key=lambda c: c["score"], reverse=True)
    return candidates[:n_exercises]
