from __future__ import annotations

"""
Autonomic Readiness Index (ARI)

Quantifies daily training readiness on a 0-100 scale from HRV, sleep,
subjective wellness, and perceived soreness. Drives autoregulated volume
scaling so that programming adapts to the athlete's recovery state each
session.

Weighting (revised Olympia-grade coaching model):

    ARI = 0.30 * hrv_component
        + 0.20 * sleep_component       (quality 0.35 + duration 0.65)
        + 0.20 * soreness_component
        + 0.15 * hr_component
        + 0.15 * wellness_component    (stress/mood/energy composite)

The HRV baseline is a 7-day rolling mean, not 14-day — this is the HRV
research standard (Plews/Buchheit) for detecting acute autonomic drift.

Zones:
    Green  (70-100) — full or enhanced volume
    Yellow (40-69)  — moderate reduction
    Red    (0-39)   — significant deload or rest
"""


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_HRV_WEIGHT: float = 0.30
_SLEEP_WEIGHT: float = 0.20
_SORENESS_WEIGHT: float = 0.20
_HR_WEIGHT: float = 0.15
_WELLNESS_WEIGHT: float = 0.15

_SLEEP_DURATION_WEIGHT: float = 0.65
_SLEEP_QUALITY_WEIGHT: float = 0.35

_GREEN_FLOOR: float = 70.0
_YELLOW_FLOOR: float = 40.0

_VOLUME_MOD_MIN: float = 0.6
_VOLUME_MOD_MAX: float = 1.1


# ---------------------------------------------------------------------------
# Core computation
# ---------------------------------------------------------------------------

def compute_ari_breakdown(
    rmssd: float,
    resting_hr: float | None,
    sleep_quality_1_10: float | None,
    soreness_1_10: float,
    baseline_rmssd: float,
    baseline_hr: float | None = None,
    *,
    sleep_hours: float | None = None,
    stress_1_10: float | None = None,
    mood_1_10: float | None = None,
    energy_1_10: float | None = None,
) -> dict:
    """
    Compute the Autonomic Readiness Index with per-component breakdown.

    Returns a dict with:
        {"score", "zone", "hrv", "sleep", "soreness", "hr", "wellness"}
    """
    hrv_component = _hrv_score(rmssd, baseline_rmssd)
    sleep_component = _sleep_score(sleep_quality_1_10, sleep_hours)
    soreness_component = _soreness_score(soreness_1_10)

    if baseline_hr is not None and resting_hr is not None:
        hr_component = _hr_score(resting_hr, baseline_hr)
    else:
        hr_component = 50.0

    wellness_component = _wellness_score(stress_1_10, mood_1_10, energy_1_10)

    raw = (
        _HRV_WEIGHT * hrv_component
        + _SLEEP_WEIGHT * sleep_component
        + _SORENESS_WEIGHT * soreness_component
        + _HR_WEIGHT * hr_component
        + _WELLNESS_WEIGHT * wellness_component
    )
    score = round(_clamp(raw, 0.0, 100.0), 1)
    return {
        "score": score,
        "zone": get_ari_zone(score),
        "hrv": round(hrv_component, 1),
        "sleep": round(sleep_component, 1),
        "soreness": round(soreness_component, 1),
        "hr": round(hr_component, 1),
        "wellness": round(wellness_component, 1),
    }


def compute_ari(
    rmssd: float,
    resting_hr: float | None,
    sleep_quality_1_10: float | None,
    soreness_1_10: float,
    baseline_rmssd: float,
    baseline_hr: float | None = None,
    **kwargs,
) -> float:
    """
    Legacy float-returning ARI — kept for tests and engine2.py callers.
    New code should use ``compute_ari_breakdown()`` for component data.
    """
    return compute_ari_breakdown(
        rmssd,
        resting_hr,
        sleep_quality_1_10,
        soreness_1_10,
        baseline_rmssd,
        baseline_hr,
        **kwargs,
    )["score"]


# ---------------------------------------------------------------------------
# Zone helpers
# ---------------------------------------------------------------------------

def get_ari_zone(ari: float) -> str:
    if ari >= _GREEN_FLOOR:
        return "green"
    if ari >= _YELLOW_FLOOR:
        return "yellow"
    return "red"


def get_volume_modifier(ari: float) -> float:
    clamped = _clamp(ari, 0.0, 100.0)
    modifier = _VOLUME_MOD_MIN + (clamped / 100.0) * (_VOLUME_MOD_MAX - _VOLUME_MOD_MIN)
    return round(modifier, 2)


def get_zone_recommendation(ari: float) -> str:
    """Human-readable coaching cue for the given ARI zone."""
    zone = get_ari_zone(ari)
    if zone == "green":
        return "Ready to train hard. Hit your prescribed sets and push RPE to target."
    if zone == "yellow":
        return "Moderate recovery. Trim 10–20% working sets; stay 1 RIR further from failure than prescribed."
    return "Under-recovered. Drop to 50% volume, light compounds only, and prioritise sleep + food tonight."


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _hrv_score(rmssd: float, baseline_rmssd: float) -> float:
    if baseline_rmssd <= 0 or rmssd is None:
        return 50.0
    # Ratio to baseline, capped at 110% (supercompensated HRV).
    ratio = rmssd / baseline_rmssd
    if ratio >= 1.10:
        return 100.0
    if ratio >= 1.0:
        return 90.0 + (ratio - 1.0) * 100.0  # 90-100
    if ratio >= 0.90:
        return 60.0 + (ratio - 0.90) * 300.0  # 60-90
    if ratio >= 0.80:
        return 30.0 + (ratio - 0.80) * 300.0  # 30-60
    return max(0.0, ratio * 37.5)


def _sleep_score(sleep_quality_1_10: float | None, sleep_hours: float | None) -> float:
    """Combines quality (35%) and duration (65%)."""
    # Quality
    if sleep_quality_1_10 is None:
        q_score = 50.0
    else:
        q_score = (_clamp(sleep_quality_1_10, 1.0, 10.0) - 1.0) / 9.0 * 100.0

    # Duration: 8 h = 100, 7 h = 85, 6 h = 65, 5 h = 40, <=4 h = 15
    if sleep_hours is None:
        d_score = q_score  # fall back to quality if duration missing
    else:
        h = _clamp(sleep_hours, 0.0, 12.0)
        if h >= 8.5:
            d_score = 100.0
        elif h >= 7.5:
            d_score = 85.0 + (h - 7.5) * 15.0
        elif h >= 6.5:
            d_score = 60.0 + (h - 6.5) * 25.0
        elif h >= 5.5:
            d_score = 35.0 + (h - 5.5) * 25.0
        elif h >= 4.5:
            d_score = 15.0 + (h - 4.5) * 20.0
        else:
            d_score = max(0.0, h * 3.3)

    return _SLEEP_DURATION_WEIGHT * d_score + _SLEEP_QUALITY_WEIGHT * q_score


def _soreness_score(soreness_1_10: float | None) -> float:
    if soreness_1_10 is None:
        return 50.0
    clamped = _clamp(soreness_1_10, 1.0, 10.0)
    return (10.0 - clamped) / 9.0 * 100.0


def _hr_score(resting_hr: float, baseline_hr: float) -> float:
    """
    Symmetric scoring of resting HR deviation from 7-day baseline.

    ±10 bpm = ±50 points. 5 bpm elevated = -25, 5 bpm below = +25. Baseline
    itself returns 50 (neutral). Capped at [0, 100].
    """
    if baseline_hr is None or baseline_hr <= 0:
        return 50.0
    deviation = resting_hr - baseline_hr  # positive = elevated = worse
    score = 50.0 - (deviation * 5.0)      # symmetric
    return _clamp(score, 0.0, 100.0)


def _wellness_score(
    stress_1_10: float | None,
    mood_1_10: float | None,
    energy_1_10: float | None,
) -> float:
    """Composite subjective wellness: high stress hurts, high mood + energy help."""
    if stress_1_10 is None and mood_1_10 is None and energy_1_10 is None:
        return 50.0

    parts: list[float] = []
    if stress_1_10 is not None:
        # Invert: 1 stress = great (100), 10 stress = terrible (0)
        parts.append((10.0 - _clamp(stress_1_10, 1.0, 10.0)) / 9.0 * 100.0)
    if mood_1_10 is not None:
        parts.append((_clamp(mood_1_10, 1.0, 10.0) - 1.0) / 9.0 * 100.0)
    if energy_1_10 is not None:
        parts.append((_clamp(energy_1_10, 1.0, 10.0) - 1.0) / 9.0 * 100.0)

    return sum(parts) / len(parts)


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


# ---------------------------------------------------------------------------
# Menstrual cycle phase detection + recovery adjustment
# ---------------------------------------------------------------------------
#
# A 28-day cycle model (Sims 2016 "ROAR" protocol). Follicular phase is
# high-performance; late luteal phase (days 22–28) sees HRV drops, elevated
# resting HR, +20% recovery time, and increased carb/calorie needs. Ignoring
# this is a rookie coaching move for female athletes.

from datetime import date as _date, timedelta as _timedelta


def menstrual_phase(cycle_start_date: _date | None, today: _date | None = None) -> dict | None:
    """
    Resolve the athlete's current menstrual phase from their logged cycle start.

    Returns a dict ``{phase, day_of_cycle, recovery_multiplier, carb_bump_kcal,
    coaching_note}`` or ``None`` if tracking isn't enabled / cycle_start_date
    is missing. Phases:
        follicular (1-14)   — high HRV, normal recovery, peak performance.
        ovulation (14-16)   — mild drop in recovery; inflammation rises.
        early_luteal (15-21) — normal, slightly reduced ceiling.
        late_luteal (22-28) — elevated resting HR, reduced HRV, +20% recovery.
    """
    if cycle_start_date is None:
        return None
    today = today or _date.today()
    if today < cycle_start_date:
        return None
    day = ((today - cycle_start_date).days % 28) + 1  # 1-28

    if day <= 14:
        return {
            "phase": "follicular",
            "day_of_cycle": day,
            "recovery_multiplier": 1.0,
            "carb_bump_kcal": 0,
            "coaching_note": "Follicular phase — highest performance window. Push PRs.",
        }
    if day <= 16:
        return {
            "phase": "ovulation",
            "day_of_cycle": day,
            "recovery_multiplier": 1.05,
            "carb_bump_kcal": 50,
            "coaching_note": "Ovulation — mild recovery drag; maintain volume.",
        }
    if day <= 21:
        return {
            "phase": "early_luteal",
            "day_of_cycle": day,
            "recovery_multiplier": 1.08,
            "carb_bump_kcal": 100,
            "coaching_note": "Early luteal — slight heat + appetite rise; add ~100 kcal carbs on hard days.",
        }
    return {
        "phase": "late_luteal",
        "day_of_cycle": day,
        "recovery_multiplier": 1.20,
        "carb_bump_kcal": 150,
        "coaching_note": "Late luteal — lower insulin sensitivity, elevated RHR. Deload volume 10–15%, add ~150 kcal carbs.",
    }


def apply_cycle_modifier(ari_score: float, cycle_info: dict | None) -> float:
    """Adjust ARI for luteal-phase performance dip so green-zone prescription
    doesn't push a late-luteal athlete into overreach."""
    if not cycle_info:
        return ari_score
    phase = cycle_info.get("phase")
    if phase == "late_luteal":
        return _clamp(ari_score - 8.0, 0.0, 100.0)
    if phase == "early_luteal":
        return _clamp(ari_score - 3.0, 0.0, 100.0)
    return ari_score
