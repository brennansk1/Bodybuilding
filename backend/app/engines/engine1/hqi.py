from __future__ import annotations

"""
Hypertrophy Quality Index (HQI) — Muscle Size Gap Engine

Measures the absolute lean circumference gap between each muscle site's
current development and its PERSONAL division ideal, anchored to the
athlete's Casey Butt genetic ceiling.

HQI 100 = "At my personal weight cap for my height/frame in my division,
this muscle has the ideal amount of muscle considering proportions."

Ideals are computed in two layers:
  1. Casey Butt per-site maximum circumferences (genetic ceiling given frame)
  2. Division ceiling factors (what fraction of max each division targets)

For muscle sites (neck, shoulders, chest, bicep, forearm, thigh, calf):
  ideal = casey_butt_max × division_ceiling_factor

For "stay small" sites (waist, hips):
  ideal = ratio × height  (kept from division vectors — target is to be small)

Scoring uses exponential decay on absolute cm gap:
  0 cm gap → 100   (at personal division ideal)
  3 cm     →  83   (minor gap)
  5 cm     →  74   (moderate)
  10 cm    →  55   (significant work needed)
  15 cm    →  41   (major gap)
  20 cm    →  30   (severely underdeveloped)

Gap types:
  "add_muscle"        — positive gap, only training closes this
  "at_or_above_ideal" — you meet or exceed the division ideal for this site
  "reduce_girth"      — waist/hips over ideal; fat loss + vacuum training
"""
import math

# Sites where waist/hips use ratio × height (stay-small targets)
_RATIO_SITES = {"waist", "hips"}

# Division visibility weights — v2 Sprint 3 moved to constants/divisions.py
# as the single source of truth (closes M7 mismatch).
from app.constants.divisions import (
    DIVISION_VISIBILITY as _DIVISION_VISIBILITY,
    DIVISION_VISIBILITY_DEFAULT as _DEFAULT_VISIBILITY,
)

# Exponential decay constant — calibrated for weight-cap-based gaps.
# Gaps are larger with weight-cap ideals so k is gentler than before.
# 3cm→83, 5cm→74, 10cm→55, 15cm→41, 20cm→30
_DECAY_K = 0.055


def compute_hqi_site(
    lean_circ_cm: float,
    ideal_lean_cm: float,
    site: str,
) -> dict:
    """
    Compute HQI for a single site.

    Args:
        lean_circ_cm:   BF-adjusted circumference (raw × √(1 − bf_fraction))
        ideal_lean_cm:  target lean circumference for this site
        site:           anatomical site name (e.g. "bicep", "calf")

    Returns:
        dict with keys:
            score             — 0-100 HQI score
            ideal_lean_cm     — lean circumference target (cm)
            current_lean_cm   — current lean circumference (cm)
            gap_cm            — lean cm to add (positive = underdeveloped)
            gap_type          — "add_muscle" | "at_or_above_ideal" | "reduce_girth"
    """
    gap_cm = ideal_lean_cm - lean_circ_cm

    if gap_cm > 0:
        score = 100.0 * math.exp(-_DECAY_K * gap_cm)
    else:
        score = 100.0
    score = max(0.0, min(100.0, round(score, 1)))

    if gap_cm > 0.5:
        gap_type = "add_muscle"
    elif gap_cm < -0.5 and site in _RATIO_SITES:
        gap_type = "reduce_girth"
    else:
        gap_type = "at_or_above_ideal"

    return {
        "score": round(score, 1),
        "ideal_lean_cm": round(ideal_lean_cm, 1),
        "current_lean_cm": round(lean_circ_cm, 1),
        "gap_cm": round(gap_cm, 1),
        "gap_type": gap_type,
    }


def compute_ideal_circumferences(
    max_circumferences: dict[str, float],
    ceiling_factors: dict[str, float],
    division_vector: dict[str, float],
    height_cm: float,
) -> dict[str, float]:
    """
    Compute the ideal lean circumference for every site.

    Muscle sites:  ideal = casey_butt_max × division_ceiling_factor
    Stay-small sites (waist, hips): ideal = division_ratio × height
    """
    ideals: dict[str, float] = {}

    for site in max_circumferences:
        factor = ceiling_factors.get(site, 1.0)
        ideals[site] = round(max_circumferences[site] * factor, 1)

    for site in _RATIO_SITES:
        if site in division_vector:
            ideals[site] = round(division_vector[site] * height_cm, 1)

    return ideals


def compute_all_hqi(
    lean_measurements: dict[str, float],
    ideal_circumferences: dict[str, float],
) -> dict[str, dict]:
    """
    Compute HQI for all available sites.

    Args:
        lean_measurements:      BF-adjusted averaged circumferences {site: cm}
        ideal_circumferences:   pre-computed ideal lean cm per site

    Returns:
        {site: {score, ideal_lean_cm, current_lean_cm, gap_cm, gap_type}}
    """
    results: dict[str, dict] = {}
    for site, ideal_cm in ideal_circumferences.items():
        if site in lean_measurements:
            results[site] = compute_hqi_site(
                lean_circ_cm=lean_measurements[site],
                ideal_lean_cm=ideal_cm,
                site=site,
            )
    return results


def compute_overall_hqi(
    site_data: dict[str, dict],
    division: str | None = None,
) -> float:
    """
    Visibility-weighted average of site HQI scores.

    Hidden sites (e.g. thighs in Men's Physique) are down-weighted so they
    don't dilute the overall score for judged body parts.
    """
    visibility = _DIVISION_VISIBILITY.get(
        (division or "").lower().replace(" ", "_"),
        _DEFAULT_VISIBILITY,
    )

    total_weight = 0.0
    weighted_sum = 0.0
    for site, data in site_data.items():
        score = data["score"] if isinstance(data, dict) else float(data)
        w = visibility.get(site, 1.0)
        weighted_sum += score * w
        total_weight += w

    return round(weighted_sum / total_weight, 1) if total_weight > 0 else 0.0


def rank_sites_by_gap(site_data: dict[str, dict]) -> list[dict]:
    """
    Return sites sorted by gap_cm descending — the primary coaching output.
    Only includes sites where muscle needs to be added (gap_cm > 0).
    """
    gaps = [
        {"site": site, **data}
        for site, data in site_data.items()
        if data.get("gap_cm", 0) > 0
    ]
    return sorted(gaps, key=lambda x: -x["gap_cm"])
