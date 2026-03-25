from __future__ import annotations

"""
Aesthetic Vector Engine

Computes the athlete's current proportion vector and compares it
to the division ideal. Returns a per-site delta vector showing
which sites need to grow or shrink relative to the ideal.
"""

import numpy as np


# ---------------------------------------------------------------------------
# Division-specific site visibility weights
# ---------------------------------------------------------------------------
# Each value is a multiplier (0.0–1.0) applied to the raw priority score.
# Sites hidden by stage attire are not judged — rerouting training volume to
# those sites is a coaching error. 0.0 = not judged, 1.0 = fully judged.
_DIVISION_SITE_VISIBILITY: dict[str, dict[str, float]] = {
    "mens_open": {
        # Full physique judged front and back — back_width fully scored
        "neck": 1.0, "shoulders": 1.0, "chest": 1.0, "bicep": 1.0,
        "forearm": 1.0, "waist": 1.0, "hips": 1.0, "thigh": 1.0, "calf": 1.0,
        "back_width": 1.0,
    },
    "classic_physique": {
        # Full physique judged — legs and back included
        "neck": 1.0, "shoulders": 1.0, "chest": 1.0, "bicep": 1.0,
        "forearm": 1.0, "waist": 1.0, "hips": 1.0, "thigh": 1.0, "calf": 1.0,
        "back_width": 1.0,
    },
    "mens_physique": {
        # Board shorts cover waist to mid-thigh; thighs fully hidden.
        # Back pose IS judged — V-taper / back width is a primary criterion.
        "neck": 1.0, "shoulders": 1.0, "chest": 1.0, "bicep": 1.0,
        "forearm": 1.0, "waist": 1.0,
        "hips": 0.15,      # creates waist contrast; not judged for size
        "thigh": 0.0,      # completely hidden — do not route volume here
        "calf": 0.25,      # potentially visible below shorts; not judged
        "back_width": 1.0, # back pose fully judged — V-taper is the signature look
    },
    "womens_bikini": {
        # Bikini bottoms expose glutes/hips heavily — primary judging criterion.
        # Thighs partially visible; back pose judged but less emphasis.
        "neck": 1.0, "shoulders": 1.0, "chest": 1.0, "bicep": 0.6,
        "forearm": 0.3, "waist": 1.0,
        "hips": 1.0,       # glute development is a primary bikini criterion
        "thigh": 0.5,      # visible and contributes to overall leg shape
        "calf": 0.2,
        "back_width": 0.7, # back pose judged; less emphasis than open
    },
    "womens_figure": {
        # Full physique judged — legs and back included
        "neck": 1.0, "shoulders": 1.0, "chest": 1.0, "bicep": 1.0,
        "forearm": 0.8, "waist": 1.0, "hips": 1.0, "thigh": 1.0, "calf": 0.8,
        "back_width": 1.0,
    },
    "womens_physique": {
        # Full physique — similar to men's open weighting
        "neck": 1.0, "shoulders": 1.0, "chest": 1.0, "bicep": 1.0,
        "forearm": 1.0, "waist": 1.0, "hips": 1.0, "thigh": 1.0, "calf": 1.0,
        "back_width": 1.0,
    },
}

# Default fallback — all sites weighted equally
_DEFAULT_VISIBILITY: dict[str, float] = {
    "neck": 1.0, "shoulders": 1.0, "chest": 1.0, "bicep": 1.0,
    "forearm": 1.0, "waist": 1.0, "hips": 1.0, "thigh": 1.0, "calf": 1.0,
    "back_width": 1.0,
}


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
