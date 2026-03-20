"""
Engine 3 — Nutrition Controller: Autoregulation Module

Pure math module for adherence-gated prescription changes and refeed
scheduling.  No DB or HTTP imports.

Key principle: the system refuses to adjust macros when the athlete is
not consistently following the current prescription (adherence < 85 %).
"""

from typing import Dict, Any, List


# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------
_ADHERENCE_LOCK_THRESHOLD  = 85.0   # % — below this, lock prescription
_ADHERENCE_ADJUST_THRESHOLD = 90.0  # % — above this, eligible for tweaks

# Refeed parameters
_BASE_REFEED_INTERVAL_DAYS  = 14    # max days between refeeds when cutting
_MIN_REFEED_INTERVAL_DAYS   = 7     # more frequent at lower BF %
_LOW_BF_THRESHOLD_MALE      = 10.0  # % — "lean" for males
_LOW_BF_THRESHOLD_FEMALE    = 18.0  # % — "lean" for females

# Small caloric nudge when adherence is high but weight stalls
_STALL_ADJUSTMENT_KCAL = 100.0


def adherence_lock(
    adherence_pct: float,
    current_prescription: Dict[str, Any],
) -> Dict[str, Any]:
    """Check whether the prescription should be locked due to low adherence.

    If adherence is below 85 %, the system returns the *unchanged*
    prescription with a lock flag and a coaching message.

    Parameters
    ----------
    adherence_pct : float
        Rolling adherence percentage (0–100).
    current_prescription : dict
        The active macro prescription (protein_g, fat_g, carbs_g,
        target_calories, …).

    Returns
    -------
    dict
        ``locked`` (bool), ``message`` (str), and ``prescription`` (dict).
    """
    if adherence_pct < _ADHERENCE_LOCK_THRESHOLD:
        return {
            "locked": True,
            "message": (
                f"Adherence is {adherence_pct:.1f}% (below {_ADHERENCE_LOCK_THRESHOLD}%). "
                "Prescription is LOCKED — focus on consistently hitting current "
                "targets before any adjustments are made."
            ),
            "prescription": current_prescription,
        }

    return {
        "locked": False,
        "message": "Adherence is sufficient. Prescription may be adjusted.",
        "prescription": current_prescription,
    }


def adjust_for_adherence(
    prescription: Dict[str, float],
    adherence_pct: float,
    weight_trend: float,
) -> Dict[str, float]:
    """Make small caloric tweaks when adherence is high but weight stalls.

    Parameters
    ----------
    prescription : dict
        Current macro prescription with at least ``target_calories`` and
        ``carbs_g`` keys.
    adherence_pct : float
        Rolling adherence percentage (0–100).
    weight_trend : float
        Recent rate of weight change (kg/week).  A value near zero
        indicates a stall.

    Returns
    -------
    dict
        Updated prescription.  If no adjustment is warranted the original
        prescription is returned unchanged.
    """
    result = dict(prescription)  # shallow copy

    # Only adjust if adherence is high enough
    if adherence_pct < _ADHERENCE_ADJUST_THRESHOLD:
        return result

    # "Stall" defined as weight moving less than 0.05 kg/week either way
    if abs(weight_trend) >= 0.05:
        return result

    # Determine direction from target_calories context:
    # If the current target is a deficit prescription (weight should be
    # dropping), nudge calories *down*; otherwise nudge *up*.
    target_cal = result.get("target_calories", 0.0)

    # Heuristic: if the athlete is eating < TDEE-ish (say < 2500) assume
    # cutting; we subtract.  Otherwise assume bulking; we add.
    # A more robust approach uses phase, but this module stays phase-agnostic.
    # The caller can supply phase context if needed.
    if weight_trend >= 0:
        # Weight is stable-to-rising; if they want to lose, cut more
        adjusted_cal = target_cal - _STALL_ADJUSTMENT_KCAL
    else:
        # Weight is stable-to-dropping; if they want to gain, add more
        adjusted_cal = target_cal + _STALL_ADJUSTMENT_KCAL

    cal_diff = adjusted_cal - target_cal
    # Apply calorie change to carbs (most flexible macro)
    carb_change = cal_diff / 4.0  # 4 kcal per gram of carbs
    result["target_calories"] = round(adjusted_cal, 0)
    result["carbs_g"] = round(result.get("carbs_g", 0.0) + carb_change, 1)

    return result


def compute_refeed(
    days_in_deficit: int,
    current_bf_pct: float,
    sex: str,
) -> Dict[str, float]:
    """Determine whether a refeed day is warranted and prescribe one.

    Refeeds are scheduled every 10–14 days during a cut.  Athletes at
    lower body-fat percentages receive more frequent refeeds (closer to
    every 7–10 days) to mitigate hormonal down-regulation.

    Parameters
    ----------
    days_in_deficit : int
        Consecutive days the athlete has been in a caloric deficit.
    current_bf_pct : float
        Current estimated body-fat percentage.
    sex : str
        ``"male"`` or ``"female"`` (case-insensitive).

    Returns
    -------
    dict
        ``refeed_due`` (bool) — whether a refeed is recommended now.
        ``refeed_interval_days`` (int) — computed interval between refeeds.
        ``refeed_calories`` (float) — recommended refeed-day calories
        (maintenance-level, i.e. deficit + surplus offset to ~0 balance).
        ``refeed_carbs_multiplier`` (float) — multiplier to apply to
        normal carb prescription on the refeed day (typically 1.5–2.0x).
    """
    sex_lower = sex.strip().lower()
    if sex_lower not in ("male", "female"):
        raise ValueError(f"sex must be 'male' or 'female', got '{sex}'")

    # Determine leanness threshold
    lean_threshold = (
        _LOW_BF_THRESHOLD_MALE if sex_lower == "male"
        else _LOW_BF_THRESHOLD_FEMALE
    )

    # Interpolate refeed interval between min (lean) and base (higher BF)
    if current_bf_pct <= lean_threshold:
        interval = _MIN_REFEED_INTERVAL_DAYS
    elif current_bf_pct >= lean_threshold + 10.0:
        interval = _BASE_REFEED_INTERVAL_DAYS
    else:
        # Linear interpolation
        fraction = (current_bf_pct - lean_threshold) / 10.0
        interval = round(
            _MIN_REFEED_INTERVAL_DAYS
            + fraction * (_BASE_REFEED_INTERVAL_DAYS - _MIN_REFEED_INTERVAL_DAYS)
        )

    refeed_due = days_in_deficit >= interval

    # Carb multiplier: leaner athletes get a higher carb bump
    if current_bf_pct <= lean_threshold:
        carb_multiplier = 2.0
    elif current_bf_pct >= lean_threshold + 10.0:
        carb_multiplier = 1.5
    else:
        fraction = (current_bf_pct - lean_threshold) / 10.0
        carb_multiplier = round(2.0 - fraction * 0.5, 2)

    return {
        "refeed_due": refeed_due,
        "refeed_interval_days": interval,
        "refeed_calories": 0.0,  # caller fills in from TDEE (maintenance)
        "refeed_carbs_multiplier": carb_multiplier,
    }


# ---------------------------------------------------------------------------
# ARI-Triggered Emergency Refeed (Engine 2 → Engine 3 cross-engine feedback)
# ---------------------------------------------------------------------------
_ARI_LOW_THRESHOLD = 55.0
_ARI_CONSECUTIVE_DAYS_TRIGGER = 3


def check_ari_triggered_refeed(
    recent_ari_scores: List[float],
    phase: str,
    current_bf_pct: float,
    sex: str,
) -> Dict[str, Any]:
    """Determine whether an emergency refeed is warranted based on ARI scores.

    This function implements the cross-engine feedback loop where Engine 2
    (Adaptive Readiness Index) informs Engine 3 (Nutrition Controller).
    When ARI scores are consistently low during a cut, it signals that the
    athlete's recovery capacity is dangerously compromised and an emergency
    refeed is needed to restore hormonal and metabolic function.

    Trigger criteria:
      - Phase must be ``"cut"`` or ``"peak"``
      - Average ARI < 55 for 3+ consecutive days in the recent window

    Parameters
    ----------
    recent_ari_scores : list of float
        ARI scores from the last 3–5 days (most recent last).
    phase : str
        Current training phase.
    current_bf_pct : float
        Current estimated body-fat percentage.
    sex : str
        ``"male"`` or ``"female"`` (case-insensitive).

    Returns
    -------
    dict
        ``ari_refeed_triggered`` (bool) — whether an emergency refeed is
        recommended.
        ``avg_ari`` (float) — average of the provided ARI scores.
        ``consecutive_low_days`` (int) — number of consecutive days with
        ARI below the threshold.
        ``message`` (str) — human-readable coaching rationale.
    """
    phase_lower = phase.strip().lower()
    sex_lower = sex.strip().lower()
    if sex_lower not in ("male", "female"):
        raise ValueError(f"sex must be 'male' or 'female', got '{sex}'")

    if not recent_ari_scores:
        return {
            "ari_refeed_triggered": False,
            "avg_ari": 0.0,
            "consecutive_low_days": 0,
            "message": "No ARI data provided.",
        }

    avg_ari = sum(recent_ari_scores) / len(recent_ari_scores)

    # Count consecutive low days from the most recent backwards
    consecutive_low = 0
    for score in reversed(recent_ari_scores):
        if score < _ARI_LOW_THRESHOLD:
            consecutive_low += 1
        else:
            break

    # Only trigger during deficit phases
    is_deficit_phase = phase_lower in ("cut", "peak")

    triggered = (
        is_deficit_phase
        and consecutive_low >= _ARI_CONSECUTIVE_DAYS_TRIGGER
        and avg_ari < _ARI_LOW_THRESHOLD
    )

    if triggered:
        lean_threshold = 10.0 if sex_lower == "male" else 18.0
        if current_bf_pct <= lean_threshold:
            message = (
                f"EMERGENCY REFEED: ARI has been below {_ARI_LOW_THRESHOLD} for "
                f"{consecutive_low} consecutive days (avg {avg_ari:.1f}). "
                f"Athlete is lean ({current_bf_pct:.1f}% BF) — schedule an "
                f"immediate 2-day refeed at maintenance calories with 2x carbs."
            )
        else:
            message = (
                f"EMERGENCY REFEED: ARI has been below {_ARI_LOW_THRESHOLD} for "
                f"{consecutive_low} consecutive days (avg {avg_ari:.1f}). "
                f"Schedule a 1-day refeed at maintenance calories with 1.5x carbs."
            )
    elif is_deficit_phase and consecutive_low >= 2:
        message = (
            f"ARI is trending low ({avg_ari:.1f} avg, {consecutive_low} "
            f"consecutive days below {_ARI_LOW_THRESHOLD}). Monitor closely — "
            f"refeed may be needed soon."
        )
    elif not is_deficit_phase and avg_ari < _ARI_LOW_THRESHOLD:
        message = (
            f"ARI is low ({avg_ari:.1f}) but athlete is not in a deficit phase "
            f"({phase}). Consider reducing training volume instead."
        )
    else:
        message = f"ARI is adequate ({avg_ari:.1f}). No emergency refeed needed."

    return {
        "ari_refeed_triggered": triggered,
        "avg_ari": round(avg_ari, 1),
        "consecutive_low_days": consecutive_low,
        "message": message,
    }
