"""
Feasibility Engine

Determines if the athlete's goals are achievable within their
timeline, considering natural limits and current development.
"""


def compute_feasibility(
    current_pds: float,
    target_pds: float,
    weeks_available: int,
    training_experience_years: int,
) -> dict:
    """
    Assess whether the target PDS is achievable.

    Returns:
        {
            "feasible": bool,
            "expected_pds_gain": float,
            "max_weekly_gain": float,
            "estimated_weeks": int,
            "confidence": float,
        }
    """
    # Diminishing returns: experienced athletes gain PDS slower
    if training_experience_years < 2:
        max_weekly_gain = 1.0
    elif training_experience_years < 5:
        max_weekly_gain = 0.5
    elif training_experience_years < 10:
        max_weekly_gain = 0.25
    else:
        max_weekly_gain = 0.1

    gap = target_pds - current_pds
    if gap <= 0:
        return {
            "feasible": True,
            "expected_pds_gain": 0,
            "max_weekly_gain": max_weekly_gain,
            "estimated_weeks": 0,
            "confidence": 1.0,
        }

    estimated_weeks = int(gap / max_weekly_gain)
    feasible = estimated_weeks <= weeks_available

    # Confidence decreases as we approach genetic ceiling
    ceiling_penalty = max(0.0, 1.0 - (target_pds / 100) ** 2)
    confidence = round(min(1.0, ceiling_penalty + 0.3), 2)

    return {
        "feasible": feasible,
        "expected_pds_gain": round(min(gap, weeks_available * max_weekly_gain), 1),
        "max_weekly_gain": max_weekly_gain,
        "estimated_weeks": estimated_weeks,
        "confidence": confidence,
    }
