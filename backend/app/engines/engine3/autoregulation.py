"""
Engine 3 — Nutrition Controller: Autoregulation Module

Pure math module for adherence-gated prescription changes, refeed
scheduling, and GI distress management.  No DB or HTTP imports.

Key principle: the system refuses to adjust macros when the athlete is
not consistently following the current prescription (adherence < 85 %).
"""

from __future__ import annotations

from typing import Dict, Any, List


# Division-specific body fat floor targets (%)
# Engine 3 should halt the cut phase when these floors are reached
_DIVISION_BF_FLOOR: Dict[str, float] = {
    "mens_open": 4.0,
    "classic_physique": 5.0,
    "mens_physique": 6.0,
    "womens_physique": 8.0,
    "womens_figure": 8.0,
    "womens_bikini": 11.0,
}


def should_halt_cut(body_fat_pct: float, division: str) -> dict:
    """Check if the athlete has reached their division's BF floor.

    Returns a dict with 'halt' (bool) and 'message' (str).
    """
    key = division.lower().replace(" ", "_")
    floor = _DIVISION_BF_FLOOR.get(key, 5.0)
    if body_fat_pct <= floor:
        return {
            "halt": True,
            "floor_pct": floor,
            "message": (
                f"Body fat ({body_fat_pct}%) has reached the {division.replace('_', ' ').title()} "
                f"division floor of {floor}%. Cut phase should transition to maintenance "
                "or peak week preparation."
            ),
        }
    return {
        "halt": False,
        "floor_pct": floor,
        "message": f"Body fat ({body_fat_pct}%) is above the {floor}% division floor.",
    }


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


_THERMODYNAMIC_FLOOR = {"male": 1500.0, "female": 1200.0}


def adherence_lock(
    adherence_pct: float,
    current_prescription: Dict[str, Any],
    consecutive_low_weeks: int = 0,
    phase: str = "maintain",
    sex: str = "male",
) -> Dict[str, Any]:
    """Check whether the prescription should be locked due to low adherence.

    If adherence is below 85 %, the system returns the *unchanged*
    prescription with a lock flag and a coaching message.  If adherence
    has been low for 2+ consecutive weeks during a cut/peak phase, a
    1-week maintenance "diet break" is prescribed instead.

    Parameters
    ----------
    adherence_pct : float
        Rolling adherence percentage (0–100).
    current_prescription : dict
        The active macro prescription (protein_g, fat_g, carbs_g,
        target_calories, …).
    consecutive_low_weeks : int
        Number of consecutive weeks adherence has been below the lock
        threshold.
    phase : str
        Current training phase (used to determine diet break eligibility).

    Returns
    -------
    dict
        ``locked`` (bool), ``diet_break`` (bool), ``message`` (str),
        and ``prescription`` (dict).
    """
    # If adherence has been low for 2+ consecutive weeks during a cut,
    # prescribe a 1-week maintenance "diet break" instead of just locking
    floor = _THERMODYNAMIC_FLOOR.get(sex.strip().lower(), 1500.0)
    if consecutive_low_weeks >= 2 and phase.strip().lower() in ("cut", "peak"):
        # Calculate maintenance-level macros for a diet break
        break_prescription = dict(current_prescription)
        if "target_calories" in break_prescription:
            # Bump calories to approximate maintenance (+400 from cut)
            # Always validate result is above thermodynamic floor
            new_cals = round(break_prescription["target_calories"] + 400, 0)
            break_prescription["target_calories"] = max(floor, new_cals)
            # Add extra carbs with the surplus
            if "carbs_g" in break_prescription:
                break_prescription["carbs_g"] = round(
                    break_prescription["carbs_g"] + 100, 1
                )
        return {
            "locked": False,
            "diet_break": True,
            "message": (
                f"Adherence has been below {_ADHERENCE_LOCK_THRESHOLD}% for "
                f"{consecutive_low_weeks} consecutive weeks. Prescribing a 1-week "
                "maintenance 'Diet Break' to reset diet fatigue. Calories raised "
                "to approximately maintenance level. Resume the deficit next week."
            ),
            "prescription": break_prescription,
        }

    if adherence_pct < _ADHERENCE_LOCK_THRESHOLD:
        return {
            "locked": True,
            "diet_break": False,
            "message": (
                f"Adherence is {adherence_pct:.1f}% (below {_ADHERENCE_LOCK_THRESHOLD}%). "
                "Prescription is LOCKED — focus on consistently hitting current "
                "targets before any adjustments are made."
            ),
            "prescription": current_prescription,
        }

    return {
        "locked": False,
        "diet_break": False,
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


# ---------------------------------------------------------------------------
# GI Distress Routing (Upgrade 2.4)
# ---------------------------------------------------------------------------
# Digestion is the ultimate limiting factor for Men's Open bulks and a
# critical factor for Classic Physique vacuum poses.  When GI distress is
# reported, swap complex/fibrous food sources to pre-digested, low-FODMAP,
# fast-gastric-emptying alternatives.

_GI_DISTRESS_THRESHOLD = 6  # 1-10 scale; >= 6 triggers swap

# Source swap map: standard → GI-friendly alternative
_GI_FRIENDLY_SWAPS: Dict[str, Dict[str, str]] = {
    "carb_sources": {
        "standard": "Oats, Brown Rice, Sweet Potato, Whole Wheat Pasta",
        "gi_friendly": "Cream of Rice, White Rice, White Potato, HBCD (Highly Branched Cyclic Dextrin)",
    },
    "protein_sources": {
        "standard": "Chicken Breast, Lean Beef, Eggs, Salmon",
        "gi_friendly": "White Fish (Tilapia, Cod), Whey Isolate, Egg Whites, Turkey Breast",
    },
    "fat_sources": {
        "standard": "Whole Eggs, Almonds, Avocado, Olive Oil",
        "gi_friendly": "MCT Oil, Macadamia Nuts (low FODMAP), Small amount Avocado",
    },
}


def check_gi_distress(
    gi_distress_index: int,
    current_meal_plan: list[dict] | None = None,
    division: str = "mens_open",
) -> Dict[str, Any]:
    """Evaluate GI distress and recommend food source swaps if needed.

    When the athlete reports a GI Distress Index >= 6, the engine swaps
    all complex, fibrous food sources to low-FODMAP, pre-digested,
    fast-gastric-emptying alternatives.  This is critical for:
    - Men's Open: preventing bloating during high-calorie bulks (500g+ carbs)
    - Classic Physique: maintaining vacuum pose capability
    - Peak week: ensuring carb load is absorbed, not sitting in the gut

    Args:
        gi_distress_index: Self-reported score 1-10 (1=no issues, 10=severe).
        current_meal_plan: Optional list of meal dicts to annotate with swaps.
        division: Competition division for context-specific notes.

    Returns:
        Dict with:
          - ``triggered`` (bool): whether the swap protocol is active
          - ``gi_index``: the reported score
          - ``food_swaps``: recommended source swaps
          - ``coaching_notes``: list of coaching guidance strings
          - ``meal_plan_annotations``: per-meal notes if meal_plan provided
    """
    gi = max(1, min(10, gi_distress_index))
    triggered = gi >= _GI_DISTRESS_THRESHOLD
    div_key = division.lower().replace(" ", "_")

    result: Dict[str, Any] = {
        "triggered": triggered,
        "gi_index": gi,
        "food_swaps": {},
        "coaching_notes": [],
        "meal_plan_annotations": [],
    }

    if not triggered:
        result["coaching_notes"] = [
            f"GI distress ({gi}/10) is within normal range. No food source changes needed."
        ]
        return result

    # Active GI distress protocol
    result["food_swaps"] = _GI_FRIENDLY_SWAPS

    notes = [
        f"GI DISTRESS ALERT ({gi}/10): Switching all food sources to low-FODMAP protocol.",
        "CARBS: Replace oats, brown rice, and sweet potato with cream of rice, white rice, and white potato.",
        "PROTEIN: Replace beef and whole eggs with white fish (tilapia/cod) and whey isolate.",
        "FATS: Replace nuts and avocado with MCT oil in small amounts.",
        "Eliminate all cruciferous vegetables, dairy (except whey isolate), and high-fiber foods.",
        "Consider digestive enzymes (lipase, protease, amylase) with each meal.",
    ]

    if div_key in ("mens_open", "classic_physique"):
        notes.append(
            "Division note: GI management is critical for midsection presentation. "
            "Consider splitting meals into 6-7 smaller feedings to reduce gastric load."
        )

    if gi >= 8:
        notes.append(
            "SEVERE DISTRESS: Consider temporarily reducing total food volume by 10-15% "
            "and replacing solid carb meals with liquid HBCD shakes until symptoms resolve."
        )

    result["coaching_notes"] = notes

    # Annotate existing meal plan if provided
    if current_meal_plan:
        for meal in current_meal_plan:
            annotation = {
                "meal_label": meal.get("label", "Unknown"),
                "swap_carbs_to": "Cream of Rice or White Rice",
                "swap_protein_to": "White Fish or Whey Isolate",
                "swap_fat_to": "MCT Oil (minimal)",
                "note": "Low-FODMAP protocol active — fast-gastric-emptying sources only",
            }
            result["meal_plan_annotations"].append(annotation)

    return result
