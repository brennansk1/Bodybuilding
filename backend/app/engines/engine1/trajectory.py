from __future__ import annotations

"""
Trajectory Predictor

Models PDS progression over time using asymptotic decay:
PDS(t) = ceiling - (ceiling - current) × e^(-k × t)

Where k is the growth rate constant based on training experience.
"""
import math


def predict_trajectory(
    current_pds: float,
    ceiling_pds: float,
    weeks: int,
    training_experience_years: int,
) -> list[dict[str, float]]:
    """
    Project PDS over time.

    Returns:
        [{week: int, predicted_pds: float}, ...]
    """
    # Growth rate constant (higher = faster approach to ceiling)
    if training_experience_years < 2:
        k = 0.04
    elif training_experience_years < 5:
        k = 0.025
    elif training_experience_years < 10:
        k = 0.015
    else:
        k = 0.008

    trajectory: list[dict[str, float]] = []
    for w in range(weeks + 1):
        pds = ceiling_pds - (ceiling_pds - current_pds) * math.exp(-k * w)
        trajectory.append({"week": w, "predicted_pds": round(pds, 1)})

    return trajectory


def compute_goal_weeks(
    current_pds: float,
    target_pds: float,
    ceiling_pds: float,
    training_experience_years: int,
) -> int | None:
    """
    Estimate weeks to reach target PDS. Returns None if target > ceiling.
    """
    if target_pds >= ceiling_pds:
        return None
    if target_pds <= current_pds:
        return 0

    if training_experience_years < 2:
        k = 0.04
    elif training_experience_years < 5:
        k = 0.025
    elif training_experience_years < 10:
        k = 0.015
    else:
        k = 0.008

    denominator = ceiling_pds - current_pds
    if denominator <= 0:
        return None
    gap_ratio = (ceiling_pds - target_pds) / denominator
    if gap_ratio <= 0:
        return None

    weeks = -math.log(gap_ratio) / k
    return int(math.ceil(weeks))


def _k_for_experience(training_experience_years: int) -> float:
    """Return the growth rate constant k for a given experience level."""
    if training_experience_years < 2:
        return 0.04
    elif training_experience_years < 5:
        return 0.025
    elif training_experience_years < 10:
        return 0.015
    else:
        return 0.008


def compute_response_ratio(
    pds_history: list[dict],
    training_experience_years: int | None = None,
) -> dict:
    """
    Compute an individual's response ratio by comparing actual PDS
    progression to the predicted rate for their experience tier.

    Args:
        pds_history: List of ``{"date": str, "pds_score": float}`` entries,
                     sorted chronologically.  At least 3 entries required.
        training_experience_years: Actual years of serious resistance training.
            When provided, this overrides the PDS-back-calculated experience tier
            (which is unreliable for genetic outliers — a 2-year beginner with
            elite genetics could score PDS 75+ early, but shouldn't be treated
            as a 12-year veteran for rate predictions).

    Returns:
        Dict with keys:
        - ``response_ratio``: actual_rate / predicted_rate
        - ``category``: "high_responder" (>1.2), "normal_responder" (0.8-1.2),
          "low_responder" (<0.8)
        - ``actual_rate``: observed weekly PDS gain
        - ``predicted_rate``: expected weekly PDS gain based on experience tier
        - ``experience_source``: ``"provided"`` | ``"inferred"``

    Raises:
        ValueError: If fewer than 3 history entries are provided.
    """
    from datetime import datetime

    if len(pds_history) < 3:
        raise ValueError("At least 3 PDS history entries are required")

    # Parse dates and sort
    entries = sorted(
        pds_history,
        key=lambda e: e["date"],
    )

    first_date = datetime.strptime(entries[0]["date"], "%Y-%m-%d").date()
    last_date = datetime.strptime(entries[-1]["date"], "%Y-%m-%d").date()
    first_pds = entries[0]["pds_score"]
    last_pds = entries[-1]["pds_score"]

    total_days = (last_date - first_date).days
    if total_days <= 0:
        raise ValueError("PDS history must span more than 0 days")

    total_weeks = total_days / 7.0
    actual_rate = (last_pds - first_pds) / total_weeks

    if training_experience_years is not None:
        # Use the athlete's actual training history — much more reliable
        exp_years = max(0, int(training_experience_years))
        experience_source = "provided"
    else:
        # Fallback: infer from PDS level (unreliable for genetic outliers)
        # <40 → beginner (<2 yr), 40-60 → intermediate (2-5 yr),
        # 60-75 → advanced (5-10 yr), 75+ → elite (10+ yr)
        if first_pds < 40:
            exp_years = 1
        elif first_pds < 60:
            exp_years = 3
        elif first_pds < 75:
            exp_years = 7
        else:
            exp_years = 12
        experience_source = "inferred"

    k = _k_for_experience(exp_years)

    # Predicted weekly gain at the athlete's current PDS level
    # From the asymptotic model: dPDS/dt ≈ k × (ceiling - current_pds)
    # Use a generic ceiling of 100 for rate estimation
    ceiling = 100.0
    predicted_rate = k * (ceiling - first_pds)

    if predicted_rate <= 0:
        ratio = 1.0
    else:
        ratio = actual_rate / predicted_rate

    if ratio > 1.2:
        category = "high_responder"
    elif ratio < 0.8:
        category = "low_responder"
    else:
        category = "normal_responder"

    return {
        "response_ratio": round(ratio, 3),
        "category": category,
        "actual_rate": round(actual_rate, 4),
        "predicted_rate": round(predicted_rate, 4),
        "experience_years_used": exp_years,
        "experience_source": experience_source,
    }


def personalized_trajectory(
    current_pds: float,
    ceiling_pds: float,
    weeks: int,
    response_ratio: float,
    training_experience_years: int,
) -> list[dict[str, float]]:
    """
    Project PDS over time, scaled by an individual's response ratio.

    Like ``predict_trajectory`` but multiplies the growth rate k by the
    athlete's response_ratio so high responders see faster projected gains
    and low responders see slower ones.

    Args:
        current_pds: Current PDS score.
        ceiling_pds: Estimated PDS ceiling.
        weeks: Number of weeks to project.
        response_ratio: Individual response multiplier (from
                        ``compute_response_ratio``).
        training_experience_years: Years of training experience.

    Returns:
        [{week: int, predicted_pds: float}, ...]
    """
    k = _k_for_experience(training_experience_years) * response_ratio

    trajectory: list[dict[str, float]] = []
    for w in range(weeks + 1):
        pds = ceiling_pds - (ceiling_pds - current_pds) * math.exp(-k * w)
        trajectory.append({"week": w, "predicted_pds": round(pds, 1)})

    return trajectory
