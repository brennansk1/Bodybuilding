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

    # Stay-small sites (waist, hips): being UNDER the ideal ratio is GOOD.
    # For these sites the "ideal" is a maximum — smaller is better.
    # A coach would never tell a Classic athlete to GROW their waist.
    if site in _RATIO_SITES:
        if gap_cm < -0.5:
            # Waist/hips exceed the ideal ratio — needs reduction
            gap_type = "reduce_girth"
        else:
            # Waist/hips at or below ideal — this is ideal, not a "gap"
            gap_type = "at_ideal"
    elif gap_cm > 0.5:
        gap_type = "add_muscle"
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


# Deprecated duplicate — the single source of truth is now
# `engine1.hqi.compute_ideal_circumferences`. Keep a thin re-export so any
# existing `from app.engines.engine1.muscle_gaps import compute_ideal_circumferences`
# continues to work without touching every call site.
from app.engines.engine1.hqi import compute_ideal_circumferences  # noqa: E402,F401


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
# Division visibility weights — v2 Sprint 3 moved to constants/divisions.py
# as the single source of truth (closes M7 mismatch).
# ---------------------------------------------------------------------------
from app.constants.divisions import (
    DIVISION_VISIBILITY as _DIVISION_VISIBILITY,
    DIVISION_VISIBILITY_DEFAULT as _DEFAULT_VISIBILITY,
)
