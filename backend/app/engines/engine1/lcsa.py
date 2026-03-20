"""
Lean Cross-Sectional Area (LCSA) Engine

Converts tape measurements → lean muscle estimates per site.
LCSA = (circumference / (2π))² × π × k_site × (1 - bf_fraction)
"""
import math

from app.constants.divisions import K_SITE_FACTORS

# Map tape column names to LCSA sites
TAPE_TO_SITE = {
    "neck": "neck",
    "shoulders": "shoulders",
    "chest": "chest",
    "left_bicep": "bicep",
    "right_bicep": "bicep",
    "left_forearm": "forearm",
    "right_forearm": "forearm",
    "waist": "waist",
    "hips": "hips",
    "left_thigh": "thigh",
    "right_thigh": "thigh",
    "left_calf": "calf",
    "right_calf": "calf",
    # back_width is a linear breadth — treated as a circumference proxy for LCSA
    "back_width": "back_width",
}


def circumference_to_csa(circumference_cm: float) -> float:
    """Convert circumference to cross-sectional area (cm²)."""
    radius = circumference_cm / (2 * math.pi)
    return math.pi * radius ** 2


def compute_lcsa_site(circumference_cm: float, k_site: float, body_fat_fraction: float) -> float:
    """Compute lean CSA for a single site."""
    csa = circumference_to_csa(circumference_cm)
    return csa * k_site * (1 - body_fat_fraction)


def compute_all_lcsa(
    tape_measurements: dict[str, float],
    body_fat_pct: float | None = None,
) -> dict[str, float]:
    """
    Compute LCSA for all available sites.

    Args:
        tape_measurements: {site_name: circumference_cm}
        body_fat_pct: body fat percentage (0-100). Defaults to 15% if not provided.

    Returns:
        {site: lcsa_value}
    """
    bf_fraction = (body_fat_pct or 15.0) / 100.0

    # Average bilateral measurements
    site_values: dict[str, list[float]] = {}
    for tape_key, site in TAPE_TO_SITE.items():
        if tape_key in tape_measurements and tape_measurements[tape_key] is not None:
            site_values.setdefault(site, []).append(tape_measurements[tape_key])

    results: dict[str, float] = {}
    for site, values in site_values.items():
        avg_circ = sum(values) / len(values)
        k = K_SITE_FACTORS.get(site, 0.80)
        results[site] = round(compute_lcsa_site(avg_circ, k, bf_fraction), 2)

    return results


def compute_total_lcsa(site_values: dict[str, float]) -> float:
    """Sum all site LCSA values."""
    return round(sum(site_values.values()), 2)
