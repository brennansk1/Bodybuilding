from __future__ import annotations

"""
Muscle Gaps Engine — Raw Size Gap Analysis

Replaces HQI. Shows the athlete's raw centimetre gap from current lean
muscle size to their personal weight-cap ideal for each site.

No abstract "scores" — just real measurements:
  - current_lean_cm: what you have now (fat-stripped)
  - ideal_lean_cm: your division-specific genetic ceiling target
  - gap_cm: how much lean tissue you need to add (positive = underdeveloped)
  - pct_of_ideal: what percentage of your ideal you've achieved

Gap types:
  "add_muscle"        — positive gap, only training closes this
  "at_ideal"          — within 0.5 cm of target
  "above_ideal"       — exceeds target (may indicate over-development)
  "reduce_girth"      — waist/hips over ideal; fat loss + vacuum training
"""

# Sites where waist/hips use ratio × height (stay-small targets)
_RATIO_SITES = {"waist", "hips"}


def compute_site_gap(
    lean_circ_cm: float,
    ideal_lean_cm: float,
    site: str,
) -> dict:
    """
    Compute the raw muscle gap for a single site.

    Returns:
        dict with keys:
            ideal_lean_cm     — lean circumference target (cm)
            current_lean_cm   — current lean circumference (cm)
            gap_cm            — lean cm to add (positive = underdeveloped)
            pct_of_ideal      — current as % of ideal (100 = at target)
            gap_type          — "add_muscle" | "at_ideal" | "above_ideal" | "reduce_girth"
    """
    gap_cm = ideal_lean_cm - lean_circ_cm
    pct = round((lean_circ_cm / ideal_lean_cm) * 100, 1) if ideal_lean_cm > 0 else 0.0

    if gap_cm > 0.5:
        gap_type = "add_muscle"
    elif gap_cm < -0.5 and site in _RATIO_SITES:
        gap_type = "reduce_girth"
    elif gap_cm < -0.5:
        gap_type = "above_ideal"
    else:
        gap_type = "at_ideal"

    return {
        "ideal_lean_cm": round(ideal_lean_cm, 1),
        "current_lean_cm": round(lean_circ_cm, 1),
        "gap_cm": round(gap_cm, 1),
        "pct_of_ideal": pct,
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


def compute_all_gaps(
    lean_measurements: dict[str, float],
    ideal_circumferences: dict[str, float],
) -> dict[str, dict]:
    """
    Compute muscle gaps for all available sites.

    Returns:
        {site: {ideal_lean_cm, current_lean_cm, gap_cm, pct_of_ideal, gap_type}}
    """
    results: dict[str, dict] = {}
    for site, ideal_cm in ideal_circumferences.items():
        if site in lean_measurements:
            results[site] = compute_site_gap(
                lean_circ_cm=lean_measurements[site],
                ideal_lean_cm=ideal_cm,
                site=site,
            )
    return results


def compute_total_gap(site_data: dict[str, dict]) -> float:
    """Sum of all positive gaps (total cm of muscle to add)."""
    return round(sum(
        max(0, d["gap_cm"]) for d in site_data.values()
    ), 1)


def compute_avg_pct_of_ideal(
    site_data: dict[str, dict],
    division: str | None = None,
) -> float:
    """
    Visibility-weighted average of pct_of_ideal across all sites.
    Hidden sites (e.g. thighs in Men's Physique) are down-weighted.
    """
    visibility = _DIVISION_VISIBILITY.get(
        (division or "").lower().replace(" ", "_"),
        _DEFAULT_VISIBILITY,
    )

    total_weight = 0.0
    weighted_sum = 0.0
    for site, data in site_data.items():
        # Handle both dict-of-dicts (MuscleGaps structure) and dict-of-floats (HQILog/PDSLog structure)
        if isinstance(data, dict):
            pct = data.get("pct_of_ideal", 0.0)
        else:
            pct = float(data)
            
        w = visibility.get(site, 1.0)
        weighted_sum += pct * w
        total_weight += w

    return round(weighted_sum / total_weight, 1) if total_weight > 0 else 0.0


def rank_sites_by_gap(
    site_data: dict[str, dict],
    division: str | None = None,
) -> list[dict]:
    """
    Return sites sorted by weighted_gap descending — the primary coaching output.
    weighted_gap = raw_gap_cm * division_visibility_weight.

    Only includes sites where muscle needs to be added (gap_cm > 0)
    and where visibility > 0 (judged sites).
    """
    visibility = _DIVISION_VISIBILITY.get(
        (division or "").lower().replace(" ", "_"),
        _DEFAULT_VISIBILITY,
    )

    gaps = []
    for site, data in site_data.items():
        gap_cm = data.get("gap_cm", 0)
        weight = visibility.get(site, 1.0)
        
        # Only rank if there's a positive gap and the site is actually judged/visible
        if gap_cm > 0 and weight > 0:
            weighted_gap = round(gap_cm * weight, 2)
            gaps.append({
                "site": site,
                "weighted_gap": weighted_gap,
                "visibility_weight": weight,
                **data
            })

    # Sort by weighted gap (priority) first, then raw gap as tie-breaker
    return sorted(gaps, key=lambda x: (-x["weighted_gap"], -x["gap_cm"]))


# ---------------------------------------------------------------------------
# Division visibility weights — sites hidden by stage attire are down-weighted
# ---------------------------------------------------------------------------
_DIVISION_VISIBILITY: dict[str, dict[str, float]] = {
    "mens_open": {
        # All muscle groups visible and judged equally — no hiding anything
        "neck": 1.0, "shoulders": 1.0, "chest": 1.0, "bicep": 1.0,
        "forearm": 1.0, "waist": 1.0, "hips": 0.9, "thigh": 1.0, "calf": 1.0,
        "back_width": 1.0,
    },
    "classic_physique": {
        # Same full body as open; waist judged critically (vacuum)
        "neck": 1.0, "shoulders": 1.0, "chest": 1.0, "bicep": 1.0,
        "forearm": 1.0, "waist": 1.0, "hips": 0.9, "thigh": 1.0, "calf": 1.0,
        "back_width": 1.0,
    },
    "mens_physique": {
        # Board shorts — thighs hidden, calves barely visible
        "neck": 1.0, "shoulders": 1.0, "chest": 1.0, "bicep": 1.0,
        "forearm": 1.0, "waist": 1.0,
        "hips": 0.15, "thigh": 0.0, "calf": 0.25,
        "back_width": 1.0,  # back pose is judged — V-taper is a primary criterion
    },
    "womens_bikini": {
        # Glutes primary; upper body secondary; calves rarely judged
        "neck": 1.0, "shoulders": 1.0, "chest": 1.0, "bicep": 0.6,
        "forearm": 0.3, "waist": 1.0,
        "hips": 1.0, "thigh": 0.5, "calf": 0.2,
        "back_width": 0.7,  # back pose judged but less emphasis than open
    },
    "womens_figure": {
        # Full body; shoulder-to-waist ratio is primary criterion
        "neck": 1.0, "shoulders": 1.0, "chest": 1.0, "bicep": 1.0,
        "forearm": 0.8, "waist": 1.0, "hips": 1.0, "thigh": 1.0, "calf": 0.8,
        "back_width": 1.0,
    },
    "womens_physique": {
        # Similar to figure; fuller development expected; calves judged
        "neck": 1.0, "shoulders": 1.0, "chest": 1.0, "bicep": 1.0,
        "forearm": 0.9, "waist": 1.0, "hips": 1.0, "thigh": 1.0, "calf": 1.0,
        "back_width": 1.0,
    },
}
_DEFAULT_VISIBILITY: dict[str, float] = {
    "neck": 1.0, "shoulders": 1.0, "chest": 1.0, "bicep": 1.0,
    "forearm": 1.0, "waist": 1.0, "hips": 1.0, "thigh": 1.0, "calf": 1.0,
    "back_width": 1.0,
}
