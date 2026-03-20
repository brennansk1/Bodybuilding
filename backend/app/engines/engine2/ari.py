"""
Autonomic Readiness Index (ARI)

Quantifies daily training readiness on a 0-100 scale from HRV, sleep, and
perceived soreness.  Drives autoregulated volume scaling so that programming
adapts to the athlete's recovery state each session.

ARI = 0.40 * hrv_component + 0.30 * sleep_component + 0.30 * soreness_component

Zones:
    Green  (70-100) — full or enhanced volume
    Yellow (40-69)  — moderate reduction
    Red    (0-39)   — significant deload or rest
"""


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_HRV_WEIGHT: float = 0.35
_SLEEP_WEIGHT: float = 0.25
_SORENESS_WEIGHT: float = 0.25
_HR_WEIGHT: float = 0.15

_GREEN_FLOOR: float = 70.0
_YELLOW_FLOOR: float = 40.0

# Volume modifier mapping: maps ARI range to a multiplier applied to
# programmed volume.  Green can *supercompensate* up to 1.1×.
_VOLUME_MOD_MIN: float = 0.6
_VOLUME_MOD_MAX: float = 1.1


# ---------------------------------------------------------------------------
# Core computation
# ---------------------------------------------------------------------------

def compute_ari(
    rmssd: float,
    resting_hr: float,
    sleep_quality_1_10: float,
    soreness_1_10: float,
    baseline_rmssd: float,
    baseline_hr: float | None = None,
) -> float:
    """
    Compute the Autonomic Readiness Index.

    Weights: HRV 35%, Sleep 25%, Soreness 25%, Resting HR 15%.

    Args:
        rmssd: Current RMSSD (ms).
        resting_hr: Morning resting heart rate (bpm).
        sleep_quality_1_10: Subjective sleep quality (1-10).
        soreness_1_10: Subjective global soreness (1-10).
        baseline_rmssd: Rolling 14-day RMSSD baseline (ms).
        baseline_hr: Rolling 14-day resting HR baseline (bpm).
                     If None, HR component defaults to 50 (neutral).

    Returns:
        ARI score clamped to [0, 100], rounded to one decimal.
    """
    hrv_component = _hrv_score(rmssd, baseline_rmssd)
    sleep_component = _sleep_score(sleep_quality_1_10)
    soreness_component = _soreness_score(soreness_1_10)
    hr_component = _hr_score(resting_hr, baseline_hr) if baseline_hr else 50.0

    raw = (
        _HRV_WEIGHT * hrv_component
        + _SLEEP_WEIGHT * sleep_component
        + _SORENESS_WEIGHT * soreness_component
        + _HR_WEIGHT * hr_component
    )
    return round(_clamp(raw, 0.0, 100.0), 1)


# ---------------------------------------------------------------------------
# Zone helpers
# ---------------------------------------------------------------------------

def get_ari_zone(ari: float) -> str:
    """
    Classify an ARI value into a readiness zone.

    Args:
        ari: ARI score (0-100).

    Returns:
        One of ``"green"``, ``"yellow"``, or ``"red"``.
    """
    if ari >= _GREEN_FLOOR:
        return "green"
    if ari >= _YELLOW_FLOOR:
        return "yellow"
    return "red"


def get_volume_modifier(ari: float) -> float:
    """
    Map an ARI score to a volume multiplier.

    The modifier scales linearly from 0.6 (ARI = 0) to 1.1 (ARI = 100).
    Applied to programmed set counts so that a green-zone athlete may
    slightly exceed plan while a red-zone athlete is meaningfully deloaded.

    Args:
        ari: ARI score (0-100).

    Returns:
        Volume multiplier in [0.6, 1.1], rounded to two decimals.
    """
    clamped = _clamp(ari, 0.0, 100.0)
    modifier = _VOLUME_MOD_MIN + (clamped / 100.0) * (_VOLUME_MOD_MAX - _VOLUME_MOD_MIN)
    return round(modifier, 2)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _hrv_score(rmssd: float, baseline_rmssd: float) -> float:
    """HRV component: ratio of current RMSSD to baseline, capped at 100."""
    if baseline_rmssd <= 0:
        return 0.0
    return min(100.0, (rmssd / baseline_rmssd) * 100.0)


def _sleep_score(sleep_quality_1_10: float) -> float:
    """Convert 1-10 sleep quality to a 0-100 scale."""
    clamped = _clamp(sleep_quality_1_10, 1.0, 10.0)
    return (clamped - 1.0) / 9.0 * 100.0


def _soreness_score(soreness_1_10: float) -> float:
    """Invert soreness (high soreness = low readiness) to a 0-100 scale."""
    clamped = _clamp(soreness_1_10, 1.0, 10.0)
    return (10.0 - clamped) / 9.0 * 100.0


def _hr_score(resting_hr: float, baseline_hr: float) -> float:
    """
    Score resting HR relative to 14-day baseline.

    An elevated HR (>5 bpm above baseline) indicates incomplete recovery
    and reduces ARI.  HR below baseline suggests good recovery.

    Returns a 0-100 score where 100 = at or below baseline.
    """
    if baseline_hr <= 0:
        return 50.0
    deviation = resting_hr - baseline_hr  # positive = elevated HR = worse
    # Each 5 bpm above baseline → -25 ARI points on this component
    score = 100.0 - _clamp(deviation * 5.0, -25.0, 75.0)
    return _clamp(score, 0.0, 100.0)


def _clamp(value: float, lo: float, hi: float) -> float:
    """Clamp *value* to [lo, hi]."""
    return max(lo, min(hi, value))
