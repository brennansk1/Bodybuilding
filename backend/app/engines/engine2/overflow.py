"""
Volume Overflow Distribution

Accounts for indirect (overflow) volume that secondary muscles receive
from compound exercises.  For example, a bench press primarily targets
the chest but also delivers meaningful pec-minor, anterior-delt, and
triceps stimulus.

The overflow matrix expresses what fraction of a primary set counts
toward each secondary muscle's volume tally.  This prevents
over-prescribing isolation work for muscles that already receive
substantial indirect stimulus.
"""

import math


def compute_overflow(
    primary_sets: int,
    secondary_muscles_hit: dict[str, float],
    existing_volume: dict[str, int],
) -> dict[str, int]:
    """
    Distribute overflow volume from compound sets to secondary muscles.

    Args:
        primary_sets: Number of working sets performed for the primary
                      movement (e.g. 4 sets of bench press).
        secondary_muscles_hit: Mapping of secondary muscle names to their
                               overflow coefficients (0-1).  A coefficient
                               of 0.5 means each primary set counts as
                               0.5 sets for that muscle.
                               Example::

                                   {"triceps": 0.5, "front_delt": 0.3}

        existing_volume: Current accumulated volume (sets) per muscle
                         before this overflow is applied.  Keys are muscle
                         names, values are integer set counts.

    Returns:
        Updated volume dictionary with overflow sets added.  Only muscles
        present in *secondary_muscles_hit* or *existing_volume* appear in
        the output.  Overflow contributions are floored to whole sets so
        that fractional sets never inflate the count.
    """
    updated: dict[str, int] = dict(existing_volume)

    for muscle, coefficient in secondary_muscles_hit.items():
        clamped_coeff = max(0.0, min(1.0, coefficient))
        overflow_sets = math.floor(primary_sets * clamped_coeff)

        if overflow_sets <= 0:
            continue

        current = updated.get(muscle, 0)
        updated[muscle] = current + overflow_sets

    return updated


def compute_effective_volume(
    direct_sets: dict[str, int],
    compound_movements: list[dict],
) -> dict[str, int]:
    """
    Compute total effective volume across all muscles after overflow.

    Each entry in *compound_movements* must contain::

        {
            "primary_muscle": str,
            "sets": int,
            "overflow": {muscle_name: coefficient, ...}
        }

    Args:
        direct_sets: Baseline direct volume per muscle (sets).
        compound_movements: List of compound exercises with their overflow
                            mappings.

    Returns:
        Dictionary of total effective sets per muscle (direct + overflow).
    """
    effective: dict[str, int] = dict(direct_sets)

    for movement in compound_movements:
        overflow_map: dict[str, float] = movement.get("overflow", {})
        sets: int = movement.get("sets", 0)

        effective = compute_overflow(sets, overflow_map, effective)

    return effective


def net_remaining_volume(
    target_volume: dict[str, int],
    effective_volume: dict[str, int],
) -> dict[str, int]:
    """
    Compute how many direct sets each muscle still needs after overflow.

    Args:
        target_volume: Prescribed weekly sets per muscle.
        effective_volume: Currently accumulated effective sets per muscle
                          (direct + overflow).

    Returns:
        Non-negative remaining sets per muscle.  Muscles that have met
        or exceeded their target return 0.
    """
    remaining: dict[str, int] = {}

    for muscle, target in target_volume.items():
        current = effective_volume.get(muscle, 0)
        remaining[muscle] = max(0, target - current)

    return remaining
