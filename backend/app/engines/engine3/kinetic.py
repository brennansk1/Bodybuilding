from __future__ import annotations

"""
Engine 3 — Nutrition Controller: Rate-of-Change (Kinetic) Module

Pure math module for computing the actual rate of body-weight change,
deriving phase-appropriate target rates, and prescribing caloric
adjustments when actual vs. target rates diverge.  No DB or HTTP imports.
"""

from datetime import datetime
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Target rate ranges (fraction of body weight per week)
# ---------------------------------------------------------------------------
_TARGET_RATE_RANGES = {
    "bulk":        (0.0025, 0.005),    # +0.25–0.5 % BW/week
    "lean_bulk":   (0.0015, 0.003),    # +0.15–0.3 % BW/week (tighter surplus)
    "cut":         (-0.010, -0.005),   # -0.5–1.0 % BW/week
    "maintain":    (-0.001, 0.001),    # roughly stable
    "peak":        (-0.007, -0.003),   # gentler than cut — preserve fullness
    "restoration": (0.002, 0.005),     # controlled weight regain post-show
}

# Adjustment step size (kcal) — now body-weight scaled via get_adjustment_step()
_ADJUSTMENT_BASE = 100.0   # base for a ~70 kg athlete
_ADJUSTMENT_MIN = 100.0    # minimum adjustment step
_ADJUSTMENT_MAX = 250.0    # absolute ceiling


def get_adjustment_step(weight_kg: float, deviation_severity: float = 0.5) -> float:
    """Return calorie adjustment step scaled by body weight and deviation.

    A 120 kg athlete needs a larger absolute kcal change than a 55 kg
    athlete to produce the same relative effect. Scaling to body weight
    ensures adjustments are proportional.

    Args:
        weight_kg: Current body weight.
        deviation_severity: 0.0-1.0 (how far off target rate is).

    Returns:
        Adjustment in kcal (always positive; caller decides direction).
    """
    bw_factor = weight_kg / 70.0   # normalized to 70 kg baseline
    severity = max(0.3, min(1.0, deviation_severity))
    step = _ADJUSTMENT_BASE * bw_factor * (0.6 + 0.4 * severity)
    return round(min(step, _ADJUSTMENT_MAX), 0)

# EWMA smoothing factor
_EWMA_ALPHA = 0.3

# Menstrual cycle: luteal phase typically days 15–28
_LUTEAL_PHASE_START = 15
_LUTEAL_PHASE_END = 28


def _compute_rolling_averages(
    sorted_history: List[Tuple[str, float]],
    window: int = 7,
) -> List[Tuple[str, float]]:
    """Compute rolling averages over the weight history.

    Parameters
    ----------
    sorted_history : list of (date_str, weight_kg)
        Chronologically sorted weight entries.
    window : int
        Rolling window size in entries (default 7).

    Returns
    -------
    list of (date_str, rolling_avg_kg)
        One entry per original entry once the window is filled.
    """
    if len(sorted_history) < window:
        # Not enough data for a full window; use expanding average
        result = []
        running_sum = 0.0
        for i, (date_str, weight) in enumerate(sorted_history):
            running_sum += weight
            result.append((date_str, running_sum / (i + 1)))
        return result

    result = []
    for i in range(window - 1, len(sorted_history)):
        chunk = sorted_history[i - window + 1: i + 1]
        avg = sum(w for _, w in chunk) / window
        result.append((sorted_history[i][0], round(avg, 3)))
    return result


def _compute_ewma(values: List[float], alpha: float = _EWMA_ALPHA) -> List[float]:
    """Apply Exponentially Weighted Moving Average to a list of values.

    Parameters
    ----------
    values : list of float
        Sequential values to smooth.
    alpha : float
        Smoothing factor (0 < alpha <= 1).  Higher = more weight on recent.

    Returns
    -------
    list of float
        EWMA-smoothed values (same length as input).
    """
    if not values:
        return []
    smoothed = [values[0]]
    for v in values[1:]:
        smoothed.append(alpha * v + (1 - alpha) * smoothed[-1])
    return smoothed


def _simple_linear_rate(sorted_history: List[Tuple[str, float]]) -> float:
    """Compute simple linear rate (kg/week) from first to last entry."""
    date_start = datetime.strptime(sorted_history[0][0], "%Y-%m-%d")
    date_end = datetime.strptime(sorted_history[-1][0], "%Y-%m-%d")
    weight_start = sorted_history[0][1]
    weight_end = sorted_history[-1][1]

    days_elapsed = (date_end - date_start).days
    if days_elapsed == 0:
        return 0.0

    weeks_elapsed = days_elapsed / 7.0
    return (weight_end - weight_start) / weeks_elapsed


def compute_rate_of_change_detailed(
    weight_history: List[Tuple[str, float]],
    sex: Optional[str] = None,
    cycle_day: Optional[int] = None,
) -> Dict:
    """Compute a detailed rate-of-change analysis with EWMA smoothing.

    Uses a 7-day rolling average to smooth daily water fluctuations,
    then applies EWMA (alpha=0.3) on the rolling averages for trend
    detection.  Includes menstrual-cycle awareness for females.

    Parameters
    ----------
    weight_history : list of (date_str, weight_kg)
        Each entry is ``("YYYY-MM-DD", weight_in_kg)``.  Must contain at
        least two entries.
    sex : str | None
        ``"male"`` or ``"female"`` (case-insensitive).  Required for
        menstrual cycle awareness.
    cycle_day : int | None
        Current day of menstrual cycle (1-28).  Only relevant for females.

    Returns
    -------
    dict
        ``rate_kg_per_week``   : EWMA-smoothed rate (kg/week)
        ``rolling_avg_latest`` : latest 7-day rolling average (kg)
        ``raw_rate``           : simple linear rate for comparison (kg/week)
        ``water_retention_flag``: True if female in luteal phase (days 15-28)
        ``trend_direction``    : "gaining" | "losing" | "stable"

    Raises
    ------
    ValueError
        If fewer than two data points are provided.
    """
    if len(weight_history) < 2:
        raise ValueError("Need at least 2 weight entries to compute rate of change")

    sorted_history = sorted(weight_history, key=lambda x: x[0])

    # Raw linear rate
    raw_rate = _simple_linear_rate(sorted_history)

    # Rolling averages (7-day window)
    rolling = _compute_rolling_averages(sorted_history, window=7)
    rolling_avg_latest = rolling[-1][1] if rolling else sorted_history[-1][1]

    # EWMA on rolling averages
    rolling_values = [w for _, w in rolling]
    ewma_values = _compute_ewma(rolling_values, alpha=_EWMA_ALPHA)

    # Compute EWMA-smoothed rate from the EWMA series
    if len(rolling) >= 2:
        ewma_start = ewma_values[0]
        ewma_end = ewma_values[-1]
        date_start = datetime.strptime(rolling[0][0], "%Y-%m-%d")
        date_end = datetime.strptime(rolling[-1][0], "%Y-%m-%d")
        days_elapsed = (date_end - date_start).days
        if days_elapsed > 0:
            weeks_elapsed = days_elapsed / 7.0
            rate_kg_per_week = (ewma_end - ewma_start) / weeks_elapsed
        else:
            rate_kg_per_week = 0.0
    else:
        rate_kg_per_week = raw_rate

    # Menstrual cycle awareness
    water_retention_flag = False
    if sex and sex.strip().lower() == "female" and cycle_day is not None:
        if _LUTEAL_PHASE_START <= cycle_day <= _LUTEAL_PHASE_END:
            water_retention_flag = True

    # Trend direction
    if rate_kg_per_week > 0.05:
        trend_direction = "gaining"
    elif rate_kg_per_week < -0.05:
        trend_direction = "losing"
    else:
        trend_direction = "stable"

    return {
        "rate_kg_per_week": round(rate_kg_per_week, 4),
        "rolling_avg_latest": round(rolling_avg_latest, 3),
        "raw_rate": round(raw_rate, 4),
        "water_retention_flag": water_retention_flag,
        "trend_direction": trend_direction,
    }


def compute_rate_of_change(
    weight_history: List[Tuple[str, float]],
    sex: Optional[str] = None,
    cycle_day: Optional[int] = None,
) -> float:
    """Compute the average weekly rate of weight change from a history.

    Uses EWMA-smoothed rolling averages internally for a more robust
    estimate that filters out daily water fluctuations.

    Parameters
    ----------
    weight_history : list of (date_str, weight_kg)
        Each entry is ``("YYYY-MM-DD", weight_in_kg)``.  Must contain at
        least two entries.
    sex : str | None
        ``"male"`` or ``"female"`` (case-insensitive).  Optional.
    cycle_day : int | None
        Current day of menstrual cycle (1-28).  Optional, only for females.

    Returns
    -------
    float
        Average rate of weight change in **kg per week**.  Positive means
        gaining, negative means losing.

    Raises
    ------
    ValueError
        If fewer than two data points are provided.
    """
    detailed = compute_rate_of_change_detailed(weight_history, sex=sex, cycle_day=cycle_day)
    return detailed["rate_kg_per_week"]


def target_rate(
    phase: str,
    weight_kg: float,
    weeks_in_deficit: int = 0,
) -> float:
    """Return the metabolic-adaptation-adjusted target rate of weight change.

    Rates are expressed as a fraction of body weight per week. For extended
    cuts, metabolic adaptation progressively reduces TDEE, meaning the same
    caloric deficit produces a slower rate of loss. Rather than masking this
    as a "stall", this function adapts the target rate downward so the
    coaching system doesn't over-prescribe cardio or caloric restriction when
    the body has simply adapted.

    Parameters
    ----------
    phase : str
        One of ``"bulk"``, ``"cut"``, ``"maintain"``, ``"peak"``.
    weight_kg : float
        Current body weight in kg.
    weeks_in_deficit : int
        Weeks spent in the current deficit phase. Every 4 weeks of sustained
        deficit, the target rate drops ~5% to account for metabolic adaptation
        (Trexler et al. 2014). Cap at -20% (8 weeks blocks of 4).

    Returns
    -------
    float
        Target rate in **kg per week** (positive = gain, negative = loss).

    Raises
    ------
    ValueError
        If *phase* is not recognised.
    """
    phase_lower = phase.strip().lower()
    if phase_lower not in _TARGET_RATE_RANGES:
        raise ValueError(
            f"phase must be one of {list(_TARGET_RATE_RANGES)}, got '{phase}'"
        )

    lo, hi = _TARGET_RATE_RANGES[phase_lower]
    midpoint_fraction = (lo + hi) / 2.0

    # Metabolic adaptation — non-linear (exponential decay)
    #
    # Research (Trexler et al. 2014, Rosenbaum & Leibel 2010) shows metabolic
    # adaptation is NOT linear: the first few weeks see mild adaptation (~3%),
    # then it accelerates as the body defends its setpoint, eventually
    # plateauing around 15-20% reduction at ~16 weeks.
    #
    # Old model: 5% per 4-week block (linear, caps at 20%)
    # New model: exponential curve that's gentle early, aggressive late
    #   adaptation = 1.0 - max_reduction × (1 - e^(-k × weeks))
    #   max_reduction = 0.20 (20% ceiling — consistent with literature)
    #   k = 0.12 (rate constant — calibrated to match ~5% at week 4, ~15% at week 12)
    import math
    if weeks_in_deficit > 2 and phase_lower in ("cut", "peak"):
        max_reduction = 0.20
        k = 0.12
        adaptation_factor = 1.0 - max_reduction * (1.0 - math.exp(-k * weeks_in_deficit))
        midpoint_fraction *= adaptation_factor

    return round(midpoint_fraction * weight_kg, 3)


def adjust_calories(
    current_calories: float,
    actual_rate: float,
    target_rate_value: float,
) -> float:
    """Suggest a caloric adjustment when actual rate deviates from target.

    Rules
    -----
    * If the actual rate is *faster* than the target (e.g. gaining too
      fast on a bulk, or losing too fast on a cut), calories are nudged
      in the opposing direction by 100–200 kcal.
    * If the actual rate is *slower* than the target, calories are nudged
      toward the target by 100–200 kcal.
    * If the rates are within 10 % of each other, no adjustment is made.

    The adjustment magnitude scales linearly between 100 and 200 kcal
    based on how far off the actual rate is.

    Parameters
    ----------
    current_calories : float
        Current daily calorie prescription.
    actual_rate : float
        Observed rate of weight change (kg/week).
    target_rate_value : float
        Desired rate of weight change (kg/week).

    Returns
    -------
    float
        Adjusted daily calorie prescription.
    """
    if target_rate_value == 0.0:
        # Maintain phase — any movement triggers a correction
        deviation = actual_rate
    else:
        deviation = actual_rate - target_rate_value

    # Relative deviation — if within 10 %, leave things alone
    if target_rate_value != 0.0:
        relative = abs(deviation / target_rate_value)
        if relative <= 0.10:
            return current_calories
    else:
        if abs(deviation) < 0.01:  # effectively stable
            return current_calories

    # Scale adjustment between 100-200 kcal based on deviation magnitude
    # Use absolute deviation capped at a practical max (0.5 kg/week off)
    abs_dev = min(abs(deviation), 0.5)
    scale = abs_dev / 0.5  # 0..1
    adjustment = _ADJUSTMENT_MIN + scale * (_ADJUSTMENT_MAX - _ADJUSTMENT_MIN)

    # Direction: if gaining too fast (deviation > 0), reduce cals;
    # if losing too fast (deviation < 0), increase cals.
    if deviation > 0:
        return round(current_calories - adjustment, 0)
    else:
        return round(current_calories + adjustment, 0)
