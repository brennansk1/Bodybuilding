"""
Progressive Overload (Resistance Progression)

Implements double progression: the athlete increases reps within a
target range first; once the rep ceiling is reached at a manageable RPE,
load is increased and reps reset to the floor of the range.

Also provides 1-RM estimation via the Epley formula for tracking
strength trends without requiring maximal singles.

Epley:  1RM = weight × (1 + reps / 30)

Load-Type Progression System
-----------------------------
Each exercise type uses specific increment rules that match real gym
equipment:

  plates        — Barbell / EZ-bar using standard Olympic plates.
                  Large compound (squat, bench, RDL, row, OHP, hip thrust):
                    5.0 kg per step (one 2.5 kg plate added per side).
                  Small isolation (curl, skull crusher, preacher):
                    2.5 kg per step (one 1.25 kg plate per side).
                  Rep range: 5-8 primary, 6-10 secondary, 8-12 isolation.

  plate_loaded  — Structural machines (Leg Press, Hack Squat).
                  10.0 kg per step (one 5 kg plate per side).
                  Rep range: 8-12 primary, 10-15 secondary.

  machine_plates— Selectorized / pin-loaded machines.
                  2.5 kg per pin step (standard stack increment).
                  Rep range: 10-15.

  cable         — Cable-pulley systems, pin-loaded stack.
                  2.5 kg per pin step.
                  Rep range: 10-15.

  dumbbells     — Standard dumbbell pairs.
                  2.5 kg per dumbbell (pairs increment by 2.5 kg in
                  standard commercial gym sets).
                  Rep range: 8-12 compound, 10-15 isolation.

  bodyweight    — Bodyweight movements.
                  Phase 1 (rep progression): increase reps until ceiling
                    (default 15 for pull-ups/dips, 20 for plank/crunch).
                  Phase 2 (weighted): add 2.5 kg via belt/vest, reset
                    reps to floor (8 for pulls, 10 for others).
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Load-type progression table
# ---------------------------------------------------------------------------

# _LARGE_COMPOUND_KEYWORDS — exercise name patterns that belong to
# the "large compound" category within a [Plates] load type.
# These get the full 5.0 kg per-step increment.
_LARGE_COMPOUND_KEYWORDS: tuple[str, ...] = (
    "squat", "deadlift", "bench press", "row", "overhead press",
    "hip thrust", "glute bridge", "good morning", "lunge",
)

# _SMALL_ISOLATION_KEYWORDS — barbell/EZ-bar isolations where smaller
# plates (1.25 kg/side = 2.5 kg total) are the practical increment.
_SMALL_ISOLATION_KEYWORDS: tuple[str, ...] = (
    "curl", "skull", "preacher",
)

# Bodyweight rep ceilings per movement pattern before switching to weighted.
_BW_REP_CEILING: dict[str, int] = {
    "pull":   15,  # pull-ups, chin-ups
    "push":   20,  # dips, push-ups
    "core":   20,  # hanging leg raise, ab wheel
    "plank":  60,  # plank (seconds)
    "default": 15,
}

# ---------------------------------------------------------------------------
# Per-load-type increment and rep-range tables
# ---------------------------------------------------------------------------

class _LTSpec:
    """Internal spec object for a load type."""
    __slots__ = ("increment", "rep_primary", "rep_secondary", "rep_isolation")

    def __init__(
        self,
        increment: float,
        rep_primary: tuple[int, int],
        rep_secondary: tuple[int, int] | None = None,
        rep_isolation: tuple[int, int] | None = None,
    ):
        self.increment = increment
        self.rep_primary = rep_primary
        self.rep_secondary = rep_secondary or rep_primary
        self.rep_isolation = rep_isolation or rep_secondary or rep_primary


_LOAD_TYPE_SPECS: dict[str, _LTSpec] = {
    # barbell/EZ-bar — see helper functions for small vs large split
    "plates": _LTSpec(
        increment=5.0,          # large compound default (2.5 kg/side)
        rep_primary=(5, 8),     # P1 heavy compound
        rep_secondary=(6, 10),  # P2 variation / secondary compound
        rep_isolation=(8, 12),  # EZ-bar curls, skull crushers
    ),
    # structural plate-loaded machines (Leg Press, Hack Squat)
    "plate_loaded": _LTSpec(
        increment=10.0,         # one 5 kg plate per side
        rep_primary=(8, 12),
        rep_secondary=(10, 15),
    ),
    # selectorized / pin-loaded machine stacks
    "machine_plates": _LTSpec(
        increment=2.5,
        rep_primary=(10, 15),
    ),
    # cable stacks
    "cable": _LTSpec(
        increment=2.5,
        rep_primary=(10, 15),
    ),
    # standard dumbbell pairs
    "dumbbells": _LTSpec(
        increment=2.5,          # gyms stock in 2.5 kg increments
        rep_primary=(8, 12),    # compound DB (press, row, lunge, thrust)
        rep_secondary=(10, 15), # isolation DB (lateral raise, curl)
    ),
    # bodyweight: rep progression first, then 2.5 kg belt/vest
    "bodyweight": _LTSpec(
        increment=2.5,
        rep_primary=(8, 15),
    ),
}

# Default when load_type is unknown
_DEFAULT_WEIGHT_INCREMENT: float = 2.5
_DEFAULT_REP_FLOOR: int = 8
_DEFAULT_REP_CEILING: int = 12

# RPE threshold: if the athlete reports RPE at or below this on the last
# working set, they are ready to increase load next session.
_RPE_PROGRESSION_THRESHOLD: float = 8.0


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def weight_increment_for_load_type(
    load_type: str,
    exercise_name: str = "",
) -> float:
    """
    Return the appropriate progression increment (kg) for a load type.

    For [plates], distinguishes large compounds (5.0 kg total, 2.5/side)
    from small barbell isolations (2.5 kg total, 1.25/side).

    Args:
        load_type: One of the canonical load type strings.
        exercise_name: Optional exercise name for compound vs isolation split.

    Returns:
        Increment in kg.
    """
    lt = load_type.lower().replace("-", "_").replace(" ", "_")
    name = exercise_name.lower()

    if lt == "plates":
        if any(k in name for k in _SMALL_ISOLATION_KEYWORDS):
            return 2.5   # 1.25 kg per side
        return 5.0       # 2.5 kg per side (large compound)

    spec = _LOAD_TYPE_SPECS.get(lt)
    return spec.increment if spec else _DEFAULT_WEIGHT_INCREMENT


def rep_range_for_load_type(
    load_type: str,
    position: int = 0,
    exercise_name: str = "",
) -> tuple[int, int]:
    """
    Return (rep_min, rep_max) for a given load type and cascade position.

    ``position`` is the 0-based index within the session exercise list:
      0  → primary compound
      1  → secondary compound / accessory
      2+ → isolation / detail work

    Args:
        load_type: Canonical load type string.
        position: 0-based exercise position in the workout.
        exercise_name: Optional exercise name for finer classification.

    Returns:
        (rep_min, rep_max) tuple.
    """
    lt = load_type.lower().replace("-", "_").replace(" ", "_")
    name = exercise_name.lower()
    spec = _LOAD_TYPE_SPECS.get(lt)

    if spec is None:
        # Legacy fallback for any unmapped load type
        return (_DEFAULT_REP_FLOOR, _DEFAULT_REP_CEILING)

    if lt == "plates":
        if any(k in name for k in _SMALL_ISOLATION_KEYWORDS):
            return spec.rep_isolation
        if position == 0:
            return spec.rep_primary    # 5-8 heavy compound
        return spec.rep_secondary      # 6-10 secondary

    if lt == "plate_loaded":
        return spec.rep_primary if position == 0 else spec.rep_secondary

    if lt == "dumbbells":
        # Compound DB movements use primary range; isolations use secondary
        is_compound = any(
            k in name for k in
            ("press", "row", "lunge", "squat", "deadlift", "thrust", "pull")
        )
        return spec.rep_primary if is_compound else spec.rep_secondary

    # cable, machine_plates, bodyweight — same range regardless of position
    return spec.rep_primary


# Backwards-compatible shim used by existing callers that pass equipment
# string from the Exercise model (e.g. "barbell", "dumbbell", "cable").
def weight_increment_for_equipment(equipment: str) -> float:
    """
    Return standard progression increment for equipment string.

    Delegates to ``weight_increment_for_load_type`` via a mapping so
    that callers not yet updated to use load_type still get correct values.
    """
    eq = equipment.strip().lower()
    if "barbell" in eq or "ez" in eq:
        return weight_increment_for_load_type("plates")
    if "dumbbell" in eq:
        return weight_increment_for_load_type("dumbbells")
    if "cable" in eq:
        return weight_increment_for_load_type("cable")
    if "machine" in eq or "selectorized" in eq:
        return weight_increment_for_load_type("machine_plates")
    if "body" in eq:
        return weight_increment_for_load_type("bodyweight")
    if "plate" in eq:
        return weight_increment_for_load_type("plate_loaded")
    return _DEFAULT_WEIGHT_INCREMENT


# ---------------------------------------------------------------------------
# 1-RM estimation
# ---------------------------------------------------------------------------

def estimate_1rm(weight: float, reps: int) -> float:
    """
    Estimate one-rep max using the Epley formula.

    Args:
        weight: Load used (any consistent unit — kg or lb).
        reps: Repetitions completed.  If reps <= 0 the weight itself is
              returned (assumed to be a true 1-RM attempt).

    Returns:
        Estimated 1-RM, rounded to one decimal.
    """
    if reps <= 0:
        return round(float(weight), 1)
    if reps == 1:
        return round(float(weight), 1)
    return round(weight * (1.0 + reps / 30.0), 1)


# ---------------------------------------------------------------------------
# Bodyweight double progression
# ---------------------------------------------------------------------------

def bodyweight_progression(
    current_reps: int,
    current_added_weight_kg: float,
    rpe: float,
    *,
    movement_pattern: str = "default",
) -> dict:
    """
    Two-phase progression for bodyweight movements.

    Phase 1 — Rep progression: add one rep per session until the rep
    ceiling for the movement pattern is reached at manageable RPE.

    Phase 2 — Weighted: once the ceiling is hit, add 2.5 kg via a
    weight belt or vest and reset reps to a lower floor.

    Args:
        current_reps: Reps completed in the last session.
        current_added_weight_kg: Current additional load (0 = pure bodyweight).
        rpe: Reported RPE on the top set.
        movement_pattern: One of "pull", "push", "core", "plank", "default".

    Returns:
        Dict with keys:
          phase (1 or 2), action ("increase_reps" | "increase_weight" | "hold"),
          next_reps, next_added_weight_kg, transition_note.
    """
    rep_ceiling = _BW_REP_CEILING.get(movement_pattern, _BW_REP_CEILING["default"])

    if rpe >= 9.5:
        return {
            "phase": 1 if current_reps < rep_ceiling else 2,
            "action": "hold",
            "next_reps": current_reps,
            "next_added_weight_kg": current_added_weight_kg,
            "transition_note": "RPE too high — consolidate this load.",
        }

    if current_reps < rep_ceiling:
        # Phase 1: advance reps
        return {
            "phase": 1,
            "action": "increase_reps",
            "next_reps": current_reps + 1,
            "next_added_weight_kg": current_added_weight_kg,
            "transition_note": f"Build to {rep_ceiling} reps before adding weight.",
        }

    # Phase 2: add weight, reset reps
    rep_floor = 8 if movement_pattern in ("pull", "push") else 10
    new_weight = round(current_added_weight_kg + 2.5, 1)
    return {
        "phase": 2,
        "action": "increase_weight",
        "next_reps": rep_floor,
        "next_added_weight_kg": new_weight,
        "transition_note": (
            f"Rep ceiling reached — add {new_weight:.1f} kg via belt/vest, "
            f"reset to {rep_floor} reps."
        ),
    }


# ---------------------------------------------------------------------------
# Double progression (all load types)
# ---------------------------------------------------------------------------

def compute_progression(
    current_weight: float,
    current_reps: int,
    target_reps: int,
    rpe: float,
    *,
    rep_floor: int = _DEFAULT_REP_FLOOR,
    weight_increment: float = _DEFAULT_WEIGHT_INCREMENT,
    load_type: str = "",
    exercise_name: str = "",
) -> dict:
    """
    Determine the next session's load and rep target via double progression.

    If ``load_type`` is provided, the weight increment is derived from the
    load-type table and overrides the ``weight_increment`` argument.

    **Logic:**

    1. If *current_reps* >= *target_reps* (the rep ceiling) **and** RPE is
       at or below the progression threshold, increase weight by the
       load-type increment and reset reps to *rep_floor*.
    2. Otherwise, keep the same weight and aim for +1 rep next session.
    3. If RPE >= 9.5, hold weight *and* reps (consolidation week).

    Args:
        current_weight: Load used in the most recent session.
        current_reps: Reps achieved on the top/last working set.
        target_reps: Rep ceiling for the current progression bracket.
        rpe: Rate of perceived exertion (1-10) on the top set.
        rep_floor: Rep floor to reset to after a weight increase.
        weight_increment: Override increment (ignored when load_type supplied).
        load_type: Canonical load type string (preferred over weight_increment).
        exercise_name: Used to choose large-compound vs isolation increment.

    Returns:
        Dictionary with keys:

        - ``next_weight`` (float): Prescribed load for next session.
        - ``next_reps`` (int): Rep target for next session.
        - ``action`` (str): ``"increase_weight"``, ``"increase_reps"``, or ``"hold"``.
        - ``estimated_1rm`` (float): Current estimated 1-RM.
        - ``load_type`` (str): Load type used for this computation.
        - ``increment_used`` (float): The actual kg step applied.
    """
    # Derive increment from load type when available
    if load_type:
        increment = weight_increment_for_load_type(load_type, exercise_name)
    else:
        increment = max(weight_increment, 1.0)

    e1rm = estimate_1rm(current_weight, current_reps)

    # Consolidation — very high RPE
    if rpe >= 9.5:
        return {
            "next_weight": current_weight,
            "next_reps": current_reps,
            "action": "hold",
            "estimated_1rm": e1rm,
            "load_type": load_type,
            "increment_used": increment,
        }

    # Rep ceiling met and RPE manageable — increase load
    if current_reps >= target_reps and rpe <= _RPE_PROGRESSION_THRESHOLD:
        return {
            "next_weight": round(current_weight + increment, 2),
            "next_reps": rep_floor,
            "action": "increase_weight",
            "estimated_1rm": e1rm,
            "load_type": load_type,
            "increment_used": increment,
        }

    # Otherwise — increase reps at same weight
    return {
        "next_weight": current_weight,
        "next_reps": current_reps + 1,
        "action": "increase_reps",
        "estimated_1rm": e1rm,
        "load_type": load_type,
        "increment_used": increment,
    }


def compute_weight_from_1rm(
    estimated_1rm: float,
    target_reps: int,
) -> float:
    """
    Back-calculate the working weight for a given rep target from 1-RM.

    Inverts the Epley formula:
        weight = 1RM / (1 + reps / 30)

    Args:
        estimated_1rm: Estimated or known one-rep max.
        target_reps: Desired rep count.

    Returns:
        Suggested working weight, rounded to one decimal.
    """
    if target_reps <= 0:
        return round(estimated_1rm, 1)
    return round(estimated_1rm / (1.0 + target_reps / 30.0), 1)
