from __future__ import annotations

"""
Aesthetic Vector Engine

Computes the athlete's current proportion vector and compares it
to the division ideal. Returns a per-site delta vector showing
which sites need to grow or shrink relative to the ideal.
"""

import numpy as np


# ---------------------------------------------------------------------------
# Division-specific site visibility — v2 Sprint 3 unified to
# constants/divisions.py (closes M7 mismatch; MP.thigh 0.0→0.55 bug).
from app.constants.divisions import (
    DIVISION_VISIBILITY as _DIVISION_SITE_VISIBILITY,
    DIVISION_VISIBILITY_DEFAULT as _DEFAULT_VISIBILITY,
)


def compute_proportion_vector(
    tape_measurements: dict[str, float],
    height_cm: float,
) -> dict[str, float]:
    """
    Convert tape measurements to proportion-of-height ratios.

    Args:
        tape_measurements: {site: circumference_cm}
        height_cm: athlete height

    Returns:
        {site: ratio}
    """
    return {site: round(circ / height_cm, 4) for site, circ in tape_measurements.items()}


def compute_delta_vector(
    actual_vector: dict[str, float],
    ideal_vector: dict[str, float],
) -> dict[str, float]:
    """
    Compute signed delta: positive = need more, negative = over-developed.

    Returns:
        {site: delta_ratio}
    """
    deltas: dict[str, float] = {}
    for site in ideal_vector:
        if site in ("shoulder_to_waist", "v_taper"):
            continue
        actual = actual_vector.get(site, 0.0)
        ideal = ideal_vector[site]
        deltas[site] = round(ideal - actual, 4)
    return deltas


def compute_priority_scores(
    delta_vector: dict[str, float],
    division: str | None = None,
) -> dict[str, float]:
    """
    Convert deltas to priority scores (0-1) for volume allocation.
    Larger positive deltas = higher priority (more underdeveloped).
    Negative deltas (over-developed) get low priority.

    Division visibility weights are applied so that sites hidden by stage
    attire are not incorrectly flagged as training priorities. For example,
    thighs score 0.0 in Men's Physique (board shorts cover them entirely).

    Args:
        delta_vector: {site: ideal - actual} — positive means underdeveloped
        division: competition division string (e.g. "mens_physique")

    Returns:
        {site: priority_score} — already visibility-weighted
    """
    if not delta_vector:
        return {}

    values = list(delta_vector.values())
    max_val = max(abs(v) for v in values) if values else 1.0
    if max_val == 0:
        return {site: 0.5 for site in delta_vector}

    division_key = (division or "").lower().replace(" ", "_")
    visibility = _DIVISION_SITE_VISIBILITY.get(division_key, _DEFAULT_VISIBILITY)

    priorities: dict[str, float] = {}
    for site, delta in delta_vector.items():
        # Positive delta → high priority, negative → low priority
        normalized = (delta / max_val + 1) / 2  # Map [-1,1] → [0,1]
        site_weight = visibility.get(site, 1.0)
        priorities[site] = round(normalized * site_weight, 3)

    return priorities


# ---------------------------------------------------------------------------
# Arm-Calf-Neck Parity (Steve Reeves Classical Standard)
# ---------------------------------------------------------------------------
# Reeves' "Building the Classic Physique the Natural Way" states that flexed
# upper arm, neck, and calf should be equal in circumference. Modern Classic
# judges still reward this balance — particularly arm:calf parity. This
# metric exposes the gap and is used by Classic-only HQI bonuses (see pds.py).
_REEVES_EQUAL_THRESHOLD_CM = 1.27    # 0.5 inch tolerance


def compute_arm_calf_neck_parity(measurements: dict) -> dict:
    """Compare arm, calf, and neck circumferences for Reeves-style parity.

    Expected keys in ``measurements`` (centimeters): ``bicep``, ``calf``,
    ``neck``. Missing keys return a non-evaluated result.

    Returns
    -------
    dict
        ``{"arm_cm", "calf_cm", "neck_cm", "max_diff_cm", "max_diff_inches",
           "reeves_equal"}``. ``reeves_equal`` is True when the three
        circumferences are within 0.5" (1.27 cm) of each other.
    """
    arm = measurements.get("bicep")
    calf = measurements.get("calf")
    neck = measurements.get("neck")

    if arm is None or calf is None or neck is None:
        return {
            "arm_cm": arm, "calf_cm": calf, "neck_cm": neck,
            "max_diff_cm": None, "max_diff_inches": None,
            "reeves_equal": False, "evaluated": False,
        }

    values = [arm, calf, neck]
    max_diff_cm = max(values) - min(values)
    return {
        "arm_cm": round(float(arm), 2),
        "calf_cm": round(float(calf), 2),
        "neck_cm": round(float(neck), 2),
        "max_diff_cm": round(max_diff_cm, 2),
        "max_diff_inches": round(max_diff_cm / 2.54, 2),
        "reeves_equal": max_diff_cm <= _REEVES_EQUAL_THRESHOLD_CM,
        "evaluated": True,
    }


def compute_chest_waist_ratio(chest_cm: float, waist_cm: float) -> float:
    """Return the circumferential chest-to-waist ratio.

    Reference values per Ground Truth doc §3.5:
    - Reeves ideal: 1.48 (148%)
    - CBum empirical: 1.79 (52"/29")
    - Ruffin empirical: 1.74

    Returns 0.0 when waist_cm is non-positive to avoid division errors.
    """
    if waist_cm is None or waist_cm <= 0:
        return 0.0
    return round(float(chest_cm) / float(waist_cm), 3)


# ---------------------------------------------------------------------------
# Illusion / V-taper metrics (v2 Sprint 9)
# ---------------------------------------------------------------------------
# Quantify the stage presentation of "smallness of waist relative to
# shoulders / hips." Independent of absolute mass, so a smaller but
# better-illusion athlete can still score well.
#
# - vtaper   = shoulders / waist          (Grecian 1.618; pro Classic ~1.50; top Open 1.55)
# - xframe   = shoulders × hips / waist²  (pro 1.85–2.25 band)
# - waist_h  = waist / height             (target 0.45 for male physique divisions)
def compute_vtaper(shoulders_cm: float, waist_cm: float) -> float:
    """Shoulder-to-waist ratio. Returns 0 when inputs are missing."""
    if not shoulders_cm or not waist_cm or waist_cm <= 0:
        return 0.0
    return round(float(shoulders_cm) / float(waist_cm), 3)


def compute_xframe(shoulders_cm: float, hips_cm: float, waist_cm: float) -> float:
    """X-frame illusion score: (shoulders × hips) / waist².

    Captures the ""hourglass"" that judges reward independent of
    shoulder:waist. Pro Classic typically 2.30–2.55 at stage.
    """
    if not shoulders_cm or not hips_cm or not waist_cm or waist_cm <= 0:
        return 0.0
    return round((float(shoulders_cm) * float(hips_cm)) / (float(waist_cm) ** 2), 3)


def compute_waist_height_ratio(waist_cm: float, height_cm: float) -> float:
    """Waist as a fraction of height. Target ~0.45 for male physique divisions."""
    if not waist_cm or not height_cm or height_cm <= 0:
        return 0.0
    return round(float(waist_cm) / float(height_cm), 3)


def cosine_similarity(
    actual_vector: dict[str, float],
    ideal_vector: dict[str, float],
) -> float:
    """
    Cosine similarity between actual and ideal proportion vectors.
    Returns value in [0, 1] where 1 = perfect match.
    """
    common_sites = [s for s in ideal_vector if s in actual_vector and s not in ("shoulder_to_waist", "v_taper")]
    if not common_sites:
        return 0.0

    a = np.array([actual_vector[s] for s in common_sites])
    b = np.array([ideal_vector[s] for s in common_sites])

    dot = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return float(round(dot / (norm_a * norm_b), 4))
