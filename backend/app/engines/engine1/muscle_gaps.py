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


# V3 — Tier-scaled ideal gaps.
#
# The absolute `ideal_circumferences` returned by hqi.compute_ideal_circumferences
# are division-ceiling values — they correspond to T4/T5 pro-qualifier / Olympia
# proportions. For an athlete targeting Tier 1 (local NPC) that reference is
# discouraging and misleading: a 9 cm bicep gap vs the Olympia ideal becomes
# a ~1 cm gap vs the T1-scaled ideal.
#
# Scaling factors are anchored to each tier's weight-cap-pct gate:
#   T1 = 0.87 × ideal  (matches 80–87% cap)
#   T2 = 0.92 × ideal  (87–92%)
#   T3 = 0.96 × ideal  (92–97%)
#   T4 = 1.00 × ideal  (97–100%)
#   T5 = 1.03 × ideal  (modern Olympia drift above published cap ratios)
#
# Waist/hips stay-small sites are NOT downscaled — their tier ideal matches
# the division absolute (a T1 athlete still wants a small waist).
TIER_IDEAL_SCALING = {
    1: 0.87,
    2: 0.92,
    3: 0.96,
    4: 1.00,
    5: 1.03,
}


def scale_ideals_for_tier(
    ideal_circumferences: dict[str, float],
    target_tier: int | None,
) -> dict[str, float]:
    """Return a copy of ideal_circumferences scaled to the athlete's target tier.

    Waist/hips (stay-small sites) are passed through unchanged — the ideal
    for those sites is a ceiling, not a target to approach from below.

    If target_tier is None or out of range, the absolute (T4) ideals are returned.
    """
    if not target_tier or target_tier not in TIER_IDEAL_SCALING:
        return dict(ideal_circumferences)

    factor = TIER_IDEAL_SCALING[target_tier]
    scaled: dict[str, float] = {}
    for site, absolute_ideal in ideal_circumferences.items():
        if site in _RATIO_SITES:
            scaled[site] = absolute_ideal
        else:
            scaled[site] = round(absolute_ideal * factor, 1)
    return scaled


def compute_all_gaps_tier_aware(
    lean_measurements: dict[str, float],
    ideal_circumferences: dict[str, float],
    target_tier: int | None,
) -> dict[str, dict]:
    """Compute gaps against tier-scaled ideals. Adds `absolute_ideal_cm` and
    `tier_ideal_cm` to each site payload so the UI can toggle between views."""
    tier_ideals = scale_ideals_for_tier(ideal_circumferences, target_tier)
    results: dict[str, dict] = {}
    for site, tier_ideal in tier_ideals.items():
        if site in lean_measurements:
            site_gap = compute_site_gap(
                lean_circ_cm=lean_measurements[site],
                ideal_lean_cm=tier_ideal,
                site=site,
            )
            site_gap["absolute_ideal_cm"] = round(ideal_circumferences[site], 1)
            site_gap["tier_ideal_cm"] = round(tier_ideal, 1)
            site_gap["target_tier"] = target_tier
            results[site] = site_gap
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

    V3 fix: two asymmetries that were silently inflating the score for
    high-BF or over-muscled athletes.

    1. **Grow sites** (biceps, shoulders, chest, etc.) are capped at 100%.
       Exceeding the divisional ideal on a grow site is neutral at worst
       (and sometimes a negative for Classic judging). The old math gave
       a +X% credit for every cm over ideal, which padded the overall HQI
       for above-ideal sites and masked gaps elsewhere.

    2. **Stay-small sites** (waist, hips) *lose* score when they exceed
       100% of ideal — because "exceeding the waist ideal" means the
       waist is too large (usually high BF carried in the midsection).
       Previously a 110% waist counted as a +10% bonus; now it becomes
       a ~80% contribution. A fat-waisted athlete no longer appears
       "above ideal" on HQI. Penalty scales 2× per point over (symmetric
       with how far you'd mark any other metric's gap).
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

        if site in _RATIO_SITES:
            # Stay-small: exceeding ideal is the problem, not the goal.
            # 100% = at ceiling (good). 110% = 10 points over → penalize
            # by 2× the overshoot so a chronically-high waist doesn't
            # look like a contribution.
            if pct > 100.0:
                pct = max(0.0, 100.0 - 2.0 * (pct - 100.0))
        else:
            # Grow sites: exceeding ideal is neutral — cap at 100 so one
            # oversized site can't paper over multiple undersized ones.
            pct = min(pct, 100.0)

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
