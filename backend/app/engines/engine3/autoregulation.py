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
# Floors bumped +1-2% to account for caliper-derived BF underestimation.
# Calipers read ~2-4% lower than DEXA at contest conditioning, so these
# floors trigger slightly earlier to protect the athlete.
_DIVISION_BF_FLOOR: Dict[str, float] = {
    "mens_open": 5.0,         # DEXA-verified ~3-4% at this caliper reading
    "classic_physique": 6.0,  # DEXA ~4-5%
    "mens_physique": 7.0,     # DEXA ~5-6%
    "womens_physique": 9.0,   # DEXA ~7-8%
    "womens_figure": 9.0,     # DEXA ~7-8%
    "womens_bikini": 12.0,    # DEXA ~10-11%
    "wellness": 12.0,         # similar to bikini
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
    recent_components: List[Dict[str, float]] | None = None,
    cycle_phase: str | None = None,
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

    # Loosen the trigger during late-luteal phase — HRV is biologically
    # depressed (progesterone effect) and that's not an overtraining signal.
    effective_threshold = _ARI_LOW_THRESHOLD
    if cycle_phase == "late_luteal":
        effective_threshold = _ARI_LOW_THRESHOLD - 5.0  # 50 instead of 55
    elif cycle_phase == "early_luteal":
        effective_threshold = _ARI_LOW_THRESHOLD - 2.0

    # Recount with the effective threshold
    consecutive_low = 0
    for score in reversed(recent_ari_scores):
        if score < effective_threshold:
            consecutive_low += 1
        else:
            break

    is_deficit_phase = phase_lower in ("cut", "peak")

    triggered = (
        is_deficit_phase
        and consecutive_low >= _ARI_CONSECUTIVE_DAYS_TRIGGER
        and avg_ari < effective_threshold
    )

    # -----------------------------------------------------------------
    # Root-cause analysis: if the low ARI is stress/wellness-dominant
    # rather than HRV-dominant, the right prescription is a stress
    # recovery break (off day, more sleep), not a carb refeed. The
    # body isn't starved — the nervous system is cooked.
    # -----------------------------------------------------------------
    root_cause = "hrv"
    stress_dominant = False
    if triggered and recent_components:
        recent = recent_components[-_ARI_CONSECUTIVE_DAYS_TRIGGER:]
        avg_hrv = sum(c.get("hrv", 50) for c in recent) / max(1, len(recent))
        avg_wellness = sum(c.get("wellness", 50) for c in recent) / max(1, len(recent))
        avg_sleep = sum(c.get("sleep", 50) for c in recent) / max(1, len(recent))
        if avg_wellness < avg_hrv - 10 and avg_wellness < 40:
            stress_dominant = True
            root_cause = "stress"
        elif avg_sleep < avg_hrv - 10 and avg_sleep < 40:
            root_cause = "sleep_debt"

    if triggered and stress_dominant:
        recommendation = "stress_recovery_break"
        message = (
            f"STRESS RECOVERY BREAK: avg wellness score is driving the ARI drop "
            f"more than HRV. Don't refeed — take a full rest day and prioritise "
            f"8+ hours of sleep tonight. Consider reducing life stressors for 48 h."
        )
    elif triggered and root_cause == "sleep_debt":
        recommendation = "sleep_catch_up"
        message = (
            f"SLEEP DEBT: low ARI is driven primarily by poor sleep ({consecutive_low} "
            f"nights below threshold). Prioritise 9+ hours tonight and tomorrow "
            f"before considering a carb refeed."
        )
    elif triggered:
        lean_threshold = 10.0 if sex_lower == "male" else 18.0
        recommendation = "carb_refeed"
        if current_bf_pct <= lean_threshold:
            message = (
                f"EMERGENCY REFEED: ARI has been below {effective_threshold:.0f} for "
                f"{consecutive_low} consecutive days (avg {avg_ari:.1f}). "
                f"Athlete is lean ({current_bf_pct:.1f}% BF) — schedule an "
                f"immediate 2-day refeed at maintenance calories with 2x carbs."
            )
        else:
            message = (
                f"EMERGENCY REFEED: ARI has been below {effective_threshold:.0f} for "
                f"{consecutive_low} consecutive days (avg {avg_ari:.1f}). "
                f"Schedule a 1-day refeed at maintenance calories with 1.5x carbs."
            )
    elif is_deficit_phase and consecutive_low >= 2:
        recommendation = "monitor"
        message = (
            f"ARI is trending low ({avg_ari:.1f} avg, {consecutive_low} "
            f"consecutive days below {effective_threshold:.0f}). Monitor closely — "
            f"refeed may be needed soon."
        )
    elif not is_deficit_phase and avg_ari < effective_threshold:
        recommendation = "reduce_volume"
        message = (
            f"ARI is low ({avg_ari:.1f}) but athlete is not in a deficit phase "
            f"({phase}). Consider reducing training volume instead."
        )
    else:
        recommendation = "none"
        message = f"ARI is adequate ({avg_ari:.1f}). No emergency refeed needed."

    return {
        "ari_refeed_triggered": triggered,
        "avg_ari": round(avg_ari, 1),
        "consecutive_low_days": consecutive_low,
        "effective_threshold": effective_threshold,
        "root_cause": root_cause,
        "recommendation": recommendation,
        "cycle_phase": cycle_phase,
        "message": message,
    }


# ---------------------------------------------------------------------------
# Energy Availability floor (RED-S protection)
# ---------------------------------------------------------------------------
# Energy Availability (EA) = (dietary energy intake − exercise energy expenditure) / FFM.
# IOC consensus (Mountjoy 2018): values < 30 kcal/kg FFM/day trigger RED-S cascade
# (hormonal suppression, menstrual disruption, bone loss, immune compromise).
# Elite prep coaches never let athletes sit below EA 30 without a compensating
# refeed schedule; critical below 25.

_EA_WARNING_FLOOR = 30.0   # kcal/kg FFM/day
_EA_CRITICAL_FLOOR = 25.0  # kcal/kg FFM/day


def check_energy_availability_floor(
    target_calories: float,
    exercise_kcal_per_day: float,
    ffm_kg: float,
    sex: str = "male",
) -> Dict[str, Any]:
    """Check whether the prescribed intake crosses the RED-S energy availability floor.

    Returns ``{ea_kcal_per_kg_ffm, status ("ok"|"warning"|"critical"),
    message, recommendation}``.
    """
    if ffm_kg <= 0:
        return {
            "ea_kcal_per_kg_ffm": 0.0,
            "status": "unknown",
            "message": "FFM unknown — cannot compute energy availability.",
            "recommendation": "log_body_composition",
        }

    ea = (target_calories - exercise_kcal_per_day) / ffm_kg

    if ea >= _EA_WARNING_FLOOR:
        status, recommendation = "ok", "none"
        message = f"Energy availability {ea:.1f} kcal/kg FFM/day — within safe range."
    elif ea >= _EA_CRITICAL_FLOOR:
        status, recommendation = "warning", "raise_calories"
        message = (
            f"Energy availability {ea:.1f} kcal/kg FFM/day is below the RED-S "
            f"warning floor of {_EA_WARNING_FLOOR:.0f}. Raise intake or reduce "
            f"exercise expenditure to restore EA ≥ {_EA_WARNING_FLOOR:.0f}."
        )
    else:
        status, recommendation = "critical", "halt_cut"
        message = (
            f"CRITICAL: Energy availability {ea:.1f} kcal/kg FFM/day is below the "
            f"RED-S critical floor ({_EA_CRITICAL_FLOOR:.0f}). Halt the cut "
            f"immediately — hormonal and metabolic damage is accumulating."
        )

    return {
        "ea_kcal_per_kg_ffm": round(ea, 1),
        "status": status,
        "message": message,
        "recommendation": recommendation,
        "warning_floor": _EA_WARNING_FLOOR,
        "critical_floor": _EA_CRITICAL_FLOOR,
    }


# ---------------------------------------------------------------------------
# Metabolic adaptation detector
# ---------------------------------------------------------------------------
# Detect long-term metabolic slowdown: when actual rate of weight change is
# consistently under 50% of expected for 4+ weeks despite high adherence,
# the athlete needs a full 2-week diet break (not just 1 week) to restore
# leptin, thyroid, and NEAT before resuming the cut.

def detect_metabolic_adaptation(
    weight_history: List[tuple],  # [(date, weight_kg), ...]
    expected_rate_kg_per_week: float,
    adherence_pct: float = 100.0,
    weeks_window: int = 4,
) -> Dict[str, Any]:
    """
    Scan the last ``weeks_window`` weeks of weight history. If actual rate of
    change is < 50% of expected (and adherence is high), signal metabolic
    adaptation and recommend a 2-week diet break.
    """
    if len(weight_history) < weeks_window * 4:  # need at least 4 data points per week
        return {
            "adapted": False,
            "reason": "insufficient_data",
            "message": f"Need {weeks_window * 4}+ weight entries to detect adaptation.",
        }

    # Pick first + last data points within the window
    window_start_idx = max(0, len(weight_history) - weeks_window * 7)
    start_date, start_wt = weight_history[window_start_idx]
    end_date, end_wt = weight_history[-1]

    # Compute actual rate
    try:
        days = (end_date - start_date).days if hasattr(end_date, "year") else 0
    except Exception:
        days = 0
    if days <= 0:
        return {
            "adapted": False,
            "reason": "zero_span",
            "message": "Start and end dates are the same — cannot compute rate.",
        }

    actual_rate_per_week = (end_wt - start_wt) / (days / 7.0)

    # For a cut, expected rate is negative. Actual-vs-expected ratio:
    if expected_rate_kg_per_week == 0:
        return {
            "adapted": False,
            "reason": "no_expectation",
            "message": "No expected rate set — cannot compare.",
        }

    ratio = actual_rate_per_week / expected_rate_kg_per_week
    # ratio < 0.5 means we're losing (or gaining) at less than half the expected pace
    adapted = (ratio < 0.5) and (adherence_pct >= 85.0)

    if adapted:
        return {
            "adapted": True,
            "actual_rate_kg_per_week": round(actual_rate_per_week, 3),
            "expected_rate_kg_per_week": round(expected_rate_kg_per_week, 3),
            "ratio": round(ratio, 2),
            "reason": "metabolic_slowdown",
            "prescription": {
                "diet_break_weeks": 2,
                "calorie_add": 500,
                "carb_add_g": 100,
                "duration_days": 14,
            },
            "message": (
                f"Metabolic adaptation detected: actual rate "
                f"{actual_rate_per_week:.3f} kg/wk vs expected "
                f"{expected_rate_kg_per_week:.3f} kg/wk over {weeks_window} weeks "
                f"at {adherence_pct:.0f}% adherence. Prescribe a 2-week full "
                f"diet break at maintenance + 500 kcal/day before resuming cut."
            ),
        }
    return {
        "adapted": False,
        "actual_rate_kg_per_week": round(actual_rate_per_week, 3),
        "expected_rate_kg_per_week": round(expected_rate_kg_per_week, 3),
        "ratio": round(ratio, 2),
        "reason": "on_track" if ratio >= 0.5 else "adherence_too_low",
        "message": (
            f"Rate is {ratio * 100:.0f}% of expected — "
            + ("within normal range." if ratio >= 0.5 else
               f"below 50%, but adherence ({adherence_pct:.0f}%) is the likely culprit.")
        ),
    }


# ---------------------------------------------------------------------------
# RPE-driven volume autoregulation
# ---------------------------------------------------------------------------
# Compares actual session-average RPE to prescribed target. Chronic over-RPE
# means the athlete is in the hole (reduce volume next session); chronic
# under-RPE means the weights were too conservative (bump 2.5%).

def autoregulate_volume_by_rpe(
    recent_sessions: List[Dict[str, float]],  # [{"avg_rpe": 8.5, "prescribed_rpe": 7.0}, ...]
    over_threshold: float = 1.5,
    under_threshold: float = 1.0,
    sessions_required: int = 3,
) -> Dict[str, Any]:
    """
    Inspect the last ``sessions_required`` sessions. If actual RPE is
    consistently over target by ``over_threshold`` or more, recommend a 10%
    volume cut for the next session. If it's consistently under target by
    ``under_threshold`` or more, recommend a 2.5% weight bump.
    """
    if len(recent_sessions) < sessions_required:
        return {
            "action": "none",
            "reason": "insufficient_sessions",
            "volume_multiplier": 1.0,
            "weight_multiplier": 1.0,
            "message": f"Need at least {sessions_required} sessions with RPE data.",
        }

    window = recent_sessions[-sessions_required:]
    deltas = [s["avg_rpe"] - s["prescribed_rpe"] for s in window]
    all_over = all(d >= over_threshold for d in deltas)
    all_under = all(d <= -under_threshold for d in deltas)

    if all_over:
        return {
            "action": "reduce_volume",
            "reason": "chronic_rpe_excess",
            "volume_multiplier": 0.90,
            "weight_multiplier": 1.0,
            "avg_delta": round(sum(deltas) / len(deltas), 2),
            "message": (
                f"Average RPE has been {over_threshold:.1f}+ points above target "
                f"for {sessions_required} sessions. Reduce next-session volume by 10% "
                f"so the athlete can dig out of the hole."
            ),
        }
    if all_under:
        return {
            "action": "increase_load",
            "reason": "chronic_rpe_deficit",
            "volume_multiplier": 1.0,
            "weight_multiplier": 1.025,
            "avg_delta": round(sum(deltas) / len(deltas), 2),
            "message": (
                f"Average RPE has been {under_threshold:.1f}+ points below target "
                f"for {sessions_required} sessions. Weights are too conservative — "
                f"bump prescribed loads by 2.5% next session."
            ),
        }
    return {
        "action": "hold",
        "reason": "on_target",
        "volume_multiplier": 1.0,
        "weight_multiplier": 1.0,
        "avg_delta": round(sum(deltas) / len(deltas), 2),
        "message": "RPE tracking prescribed targets within normal variance. Hold current plan.",
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
