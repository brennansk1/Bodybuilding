from __future__ import annotations

"""
Volumetric Ghost Model — 3D Biomechanical Proportion Engine

Replaces the Casey Butt regression pipeline with a physics-based approach
that treats the body as a scalable 3D object. Builds a mathematically
perfect "Ghost" from division vectors, calculates its mass via an improved
Hanavan geometric model, then uses cube-root allometric scaling to fit the
Ghost to the athlete's division weight cap.

Pipeline (6 phases):
  1. Localized Lean Extraction — strip fat site-by-site using calipers
  2. Weight Cap Lookup — IFBB table → target LBM
  3. Ghost Shape — unscaled ideal proportions from division vectors
  4. Hanavan Physics — geometric segment volumes → ghost mass
  5. Allometric Scaling — cube-root scaling to match target LBM
  6. Scoring — current lean / ideal target × 100
"""

import math

from app.constants.divisions import GHOST_VECTORS, DIVISION_VECTORS
from app.constants.weight_caps import lookup_weight_cap, lookup_target_lbm


# ---------------------------------------------------------------------------
# Drillis & Contini (1966) segment length proportions
# ---------------------------------------------------------------------------
_SEGMENT_LENGTH_FRACTIONS = {
    "torso": 0.300,
    "upper_arm": 0.186,
    "forearm": 0.146,
    "thigh": 0.245,
    "calf": 0.246,
}

# Tissue density for lean muscle (kg/L)
_LEAN_DENSITY = 1.06

# Lung air volume correction (cm³) — subtracted from torso volume
_LUNG_CORRECTION_CM3 = 4000.0

# Residual mass (kg) — skeleton, organs, connective tissue not captured by segments
_RESIDUAL_MASS_KG = 4.5


# ===================================================================
# Phase 1: Localized Lean Extraction
# ===================================================================

def lean_extract_site(raw_circumference_cm: float, caliper_mm: float) -> float:
    """
    Strip subcutaneous fat from a single tape measurement using
    the site-specific skinfold caliper reading.

    Formula: Lean_Circ = Raw_Circ - π × (Caliper_mm / 10)

    The caliper measures a double fold of skin + fat. Dividing by 10
    converts mm to cm and accounts for the double-fold geometry
    (the fat layer wraps ~half the circumference on each side).
    """
    return round(raw_circumference_cm - math.pi * (caliper_mm / 10.0), 2)


def lean_extract_all(
    raw_measurements: dict[str, float],
    skinfold_data: dict[str, float],
    site_skinfold_map: dict[str, str] | None = None,
    body_fat_pct: float = 15.0,
) -> dict[str, float]:
    """
    Apply localized lean extraction to all available sites.

    For sites with a matching caliper reading, uses the site-specific
    formula. Falls back to a global BF% adjustment for unmeasured sites.

    Args:
        raw_measurements: {site: circumference_cm} — averaged bilateral
        skinfold_data: {caliper_site: mm} — from 10-site skinfold protocol
        site_skinfold_map: maps measurement site → caliper column name
        body_fat_pct: fallback global BF% for sites without caliper data

    Returns:
        {site: lean_circumference_cm}
    """
    if site_skinfold_map is None:
        site_skinfold_map = _DEFAULT_SITE_SKINFOLD_MAP

    bf_fraction = max(0.0, min(body_fat_pct / 100.0, 0.50))
    global_factor = math.sqrt(1.0 - bf_fraction)

    result: dict[str, float] = {}
    for site, circ in raw_measurements.items():
        sf_col = site_skinfold_map.get(site)
        if sf_col and sf_col in skinfold_data:
            result[site] = lean_extract_site(circ, skinfold_data[sf_col])
        else:
            result[site] = round(circ * global_factor, 2)
    return result


# Default mapping: measurement site → skinfold caliper column
_DEFAULT_SITE_SKINFOLD_MAP: dict[str, str] = {
    "chest": "chest",
    "chest_relaxed": "chest",
    "chest_expanded": "chest",
    "bicep": "bicep",
    "thigh": "thigh",
    "proximal_thigh": "thigh",
    "distal_thigh": "thigh",
    "calf": "calf",
    "waist": "abdominal",
    "hips": "suprailiac",
    "back_width": "lower_back",
}


# ===================================================================
# Phase 2: Weight Cap Lookup (delegated to constants/weight_caps.py)
# ===================================================================
# Uses lookup_weight_cap() and lookup_target_lbm() directly.


# ===================================================================
# Phase 3: Ghost Shape
# ===================================================================

def build_ghost_shape(height_cm: float, division: str) -> dict[str, float]:
    """
    Build the unscaled Ghost — ideal circumferences before mass scaling.

    Ghost_Circumference = Height × Division_Vector_Ratio

    Args:
        height_cm: athlete height
        division: competition division key

    Returns:
        {site: ghost_circumference_cm} for all ghost vector sites
    """
    key = division.lower().replace(" ", "_")
    vector = GHOST_VECTORS.get(key, GHOST_VECTORS.get("mens_open", {}))

    return {
        site: round(height_cm * ratio, 2)
        for site, ratio in vector.items()
    }


# ===================================================================
# Phase 4: Hanavan Physics — Improved Geometric Segmental Model
# ===================================================================

def _circumference_to_radius(circumference_cm: float) -> float:
    """Convert circumference to radius: r = C / (2π)."""
    return circumference_cm / (2.0 * math.pi)


def _cylinder_volume(circumference_cm: float, length_cm: float) -> float:
    """Volume of a cylinder: V = π × r² × L."""
    r = _circumference_to_radius(circumference_cm)
    return math.pi * r * r * length_cm


def _frustum_volume(
    circ_large_cm: float,
    circ_small_cm: float,
    length_cm: float,
) -> float:
    """
    Volume of a frustum (truncated cone):
    V = (π × L / 3) × (R₁² + R₁R₂ + R₂²)
    """
    r1 = _circumference_to_radius(circ_large_cm)
    r2 = _circumference_to_radius(circ_small_cm)
    return (math.pi * length_cm / 3.0) * (r1 * r1 + r1 * r2 + r2 * r2)


def _ramanujan_perimeter(a: float, b: float) -> float:
    """
    Ramanujan's ellipse perimeter approximation (first formula).

    C ≈ π(3(a+b) - √((3a+b)(a+3b)))

    Much more accurate than Euler for eccentric ellipses (<0.1% error for
    typical torso aspect ratios of 1.5:1 to 3:1).
    """
    return math.pi * (3.0 * (a + b) - math.sqrt((3.0 * a + b) * (a + 3.0 * b)))


def _solve_depth_from_perimeter(a: float, target_c: float) -> float | None:
    """
    Solve Ramanujan inverse: given semi-axis a and perimeter C, find b.

    Uses bisection on [0.01, a] since b ≤ a for a torso (wider than deep).
    Returns None if no solution exists (C < minimum possible perimeter).
    """
    # Minimum perimeter at b→0 is ~4a; Ramanujan gives π(3a - √(3a²)) = π×a×(3 - √3)
    min_c = math.pi * a * (3.0 - math.sqrt(3.0))
    if target_c < min_c:
        return None

    lo, hi = 0.01, a
    for _ in range(60):  # bisection converges in ~50 iterations to machine precision
        mid = (lo + hi) / 2.0
        c_mid = _ramanujan_perimeter(a, mid)
        if c_mid < target_c:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def _elliptical_cylinder_volume(
    back_width_cm: float,
    chest_relaxed_cm: float,
    length_cm: float,
) -> float:
    """
    Torso as an elliptical cylinder.

    Uses back_width as the coronal (frontal) diameter and derives the
    sagittal (front-to-back) depth from the chest circumference using
    Ramanujan's inverse (bisection solver).

    Ramanujan's formula is far more accurate than Euler for eccentric
    ellipses typical of human torsos (aspect ratio 1.5:1 to 3:1).

    If the chest circumference can't geometrically wrap around the
    back_width (C < minimum ellipse perimeter), falls back to a
    fixed-ratio model assuming width:depth = 1.5:1.

    V = π × a × b × L
    """
    a = back_width_cm / 2.0  # coronal semi-axis (half-width)

    # Try Ramanujan inverse to find sagittal semi-axis
    b = _solve_depth_from_perimeter(a, chest_relaxed_cm)

    if b is None or b < 0.5:
        # Geometry impossible — back_width wider than circumference supports.
        # Fall back: derive both axes from circumference assuming 1.5:1 ratio.
        # C = π(3(1.5b + b) - √((4.5b+b)(1.5b+3b)))
        #   = πb(7.5 - √(24.75)) ≈ πb × 2.525
        b = chest_relaxed_cm / (math.pi * 2.525)
        a = 1.5 * b

    return math.pi * a * b * length_cm


def compute_hanavan_volume(ghost_shape: dict[str, float], height_cm: float) -> dict[str, float]:
    """
    Compute segmental volumes using the improved Hanavan geometric model.

    Segment models:
      - Upper arms: cylinders (×2, bilateral)
      - Forearms: cylinders (×2)
      - Thighs: frustums — truncated cones (×2)
      - Calves: cylinders (×2)
      - Torso: elliptical cylinder with lung correction

    Segment lengths from Drillis & Contini (1966) proportions.

    Returns:
        {
            "upper_arms": volume_cm3,
            "forearms": volume_cm3,
            "thighs": volume_cm3,
            "calves": volume_cm3,
            "torso": volume_cm3,
            "total": volume_cm3,
            "total_after_lung": volume_cm3,
        }
    """
    seg = {name: height_cm * frac for name, frac in _SEGMENT_LENGTH_FRACTIONS.items()}

    # Upper arms — cylinders (bilateral)
    bicep_circ = ghost_shape.get("bicep", 0.0)
    v_upper_arms = 2.0 * _cylinder_volume(bicep_circ, seg["upper_arm"])

    # Forearms — cylinders (bilateral)
    forearm_circ = ghost_shape.get("forearm", 0.0)
    v_forearms = 2.0 * _cylinder_volume(forearm_circ, seg["forearm"])

    # Thighs — frustums (bilateral)
    prox_thigh = ghost_shape.get("proximal_thigh", 0.0)
    dist_thigh = ghost_shape.get("distal_thigh", 0.0)
    if prox_thigh > 0 and dist_thigh > 0:
        v_thighs = 2.0 * _frustum_volume(prox_thigh, dist_thigh, seg["thigh"])
    else:
        # Fallback: single cylinder if no proximal/distal distinction
        thigh_circ = ghost_shape.get("thigh", prox_thigh or dist_thigh)
        v_thighs = 2.0 * _cylinder_volume(thigh_circ, seg["thigh"])

    # Calves — cylinders (bilateral)
    calf_circ = ghost_shape.get("calf", 0.0)
    v_calves = 2.0 * _cylinder_volume(calf_circ, seg["calf"])

    # Torso — elliptical cylinder
    back_width = ghost_shape.get("back_width", 0.0)
    chest_relaxed = ghost_shape.get("chest_relaxed", 0.0)
    if back_width > 0 and chest_relaxed > 0:
        v_torso = _elliptical_cylinder_volume(back_width, chest_relaxed, seg["torso"])
    else:
        # Fallback: circular cylinder from chest
        chest = ghost_shape.get("chest_expanded", chest_relaxed or 0.0)
        v_torso = _cylinder_volume(chest, seg["torso"])

    total = v_upper_arms + v_forearms + v_thighs + v_calves + v_torso
    total_after_lung = total - _LUNG_CORRECTION_CM3

    return {
        "upper_arms": round(v_upper_arms, 1),
        "forearms": round(v_forearms, 1),
        "thighs": round(v_thighs, 1),
        "calves": round(v_calves, 1),
        "torso": round(v_torso, 1),
        "total": round(total, 1),
        "total_after_lung": round(total_after_lung, 1),
    }


def compute_ghost_mass(total_volume_cm3: float) -> float:
    """
    Convert total segmental volume to estimated body mass.

    Ghost_Mass_kg = ((Total_Volume × Density) / 1000) + Residual_Mass

    Volume in cm³ → divide by 1000 for liters → multiply by density for kg.
    Add residual mass for skeleton, organs, connective tissue.
    """
    mass_kg = (total_volume_cm3 * _LEAN_DENSITY / 1000.0) + _RESIDUAL_MASS_KG
    return round(mass_kg, 2)


# ===================================================================
# Phase 5: Allometric Scaling
# ===================================================================

def compute_allometric_multiplier(target_lbm_kg: float, ghost_mass_kg: float) -> float:
    """
    Cube-root allometric scaling factor.

    Linear_Multiplier = ∛(Target_LBM / Ghost_Mass)

    This scales all linear dimensions (circumferences) uniformly so that
    the ghost's mass matches the target LBM from the weight cap table.
    """
    if ghost_mass_kg <= 0:
        return 1.0
    ratio = target_lbm_kg / ghost_mass_kg
    return round(ratio ** (1.0 / 3.0), 6)


def scale_ghost(ghost_shape: dict[str, float], multiplier: float) -> dict[str, float]:
    """
    Apply allometric multiplier to all ghost circumferences.

    Scaled_Circumference = Ghost_Circumference × Linear_Multiplier
    """
    return {
        site: round(circ * multiplier, 2)
        for site, circ in ghost_shape.items()
    }


# ===================================================================
# Phase 6: Scoring
# ===================================================================

def score_site(current_lean_cm: float, ideal_target_cm: float) -> float:
    """
    Score a single site as percentage of ideal.

    Score = (Current_Lean / Ideal_Target) × 100

    Returns percentage (e.g. 85.3 means 85.3% of ideal).
    """
    if ideal_target_cm <= 0:
        return 0.0
    return round((current_lean_cm / ideal_target_cm) * 100.0, 1)


def score_all_sites(
    lean_measurements: dict[str, float],
    ideal_targets: dict[str, float],
) -> dict[str, dict]:
    """
    Score all available sites, returning the same format as muscle_gaps
    for backward compatibility.

    Returns:
        {site: {ideal_lean_cm, current_lean_cm, gap_cm, pct_of_ideal, gap_type}}
    """
    results: dict[str, dict] = {}
    ratio_sites = {"waist", "hips"}

    for site, ideal_cm in ideal_targets.items():
        if site not in lean_measurements:
            continue
        current = lean_measurements[site]
        gap = round(ideal_cm - current, 1)
        pct = round((current / ideal_cm) * 100.0, 1) if ideal_cm > 0 else 0.0

        if gap > 0.5:
            gap_type = "add_muscle"
        elif gap < -0.5 and site in ratio_sites:
            gap_type = "reduce_girth"
        elif gap < -0.5:
            gap_type = "above_ideal"
        else:
            gap_type = "at_ideal"

        results[site] = {
            "ideal_lean_cm": round(ideal_cm, 1),
            "current_lean_cm": round(current, 1),
            "gap_cm": gap,
            "pct_of_ideal": pct,
            "gap_type": gap_type,
        }

    return results


# ===================================================================
# Full Pipeline
# ===================================================================

def _map_ghost_to_standard_sites(scaled_ghost: dict[str, float]) -> dict[str, float]:
    """
    Map extended ghost vector sites to standard muscle_gaps sites.

    Ghost → Standard mapping:
      chest_expanded  → chest    (competition measurement)
      proximal_thigh  → thigh    (standard tape site = fullest part)
      All others      → pass through (neck, shoulders, bicep, etc.)

    chest_relaxed, distal_thigh are kept for advanced analysis
    but are NOT included in the standard gap comparison.
    """
    standard: dict[str, float] = {}
    # waist/hips excluded — they use DIVISION_VECTORS stay-small targets
    skip = {"chest_relaxed", "chest_expanded", "proximal_thigh", "distal_thigh", "waist", "hips"}

    for site, value in scaled_ghost.items():
        if site not in skip:
            standard[site] = value

    # Map expanded sites to standard names
    if "chest_expanded" in scaled_ghost:
        standard["chest"] = scaled_ghost["chest_expanded"]
    if "proximal_thigh" in scaled_ghost:
        standard["thigh"] = scaled_ghost["proximal_thigh"]

    return standard


def run_ghost_pipeline(
    height_cm: float,
    division: str,
    lean_measurements: dict[str, float],
    sex: str = "male",
    stage_bf_pct: float = 5.0,
) -> dict:
    """
    Execute the full 6-phase Volumetric Ghost Model pipeline.

    Args:
        height_cm: athlete height
        division: competition division key
        lean_measurements: {site: lean_circumference_cm} — already fat-stripped
        sex: "male" or "female"
        stage_bf_pct: assumed stage body fat % (default 5%)

    Returns:
        {
            "weight_cap_kg": float,
            "target_lbm_kg": float,
            "ghost_shape": {site: unscaled_cm},
            "hanavan_volumes": {segment: cm3},
            "ghost_mass_kg": float,
            "allometric_multiplier": float,
            "scaled_ghost": {site: scaled_cm},
            "ideal_circumferences": {standard_site: cm},
            "site_scores": {site: {ideal, current, gap, pct, type}},
        }
    """
    # Phase 2: Weight cap
    weight_cap = lookup_weight_cap(height_cm, division)
    target_lbm = lookup_target_lbm(height_cm, division, stage_bf_pct)

    # Phase 3: Ghost shape
    ghost_shape = build_ghost_shape(height_cm, division)

    # Phase 4: Hanavan physics
    volumes = compute_hanavan_volume(ghost_shape, height_cm)
    ghost_mass = compute_ghost_mass(volumes["total_after_lung"])

    # Phase 5: Allometric scaling
    multiplier = compute_allometric_multiplier(target_lbm, ghost_mass)
    scaled_ghost = scale_ghost(ghost_shape, multiplier)

    # Map to standard sites for gap comparison
    ideal_circs = _map_ghost_to_standard_sites(scaled_ghost)

    # Add waist and hips from division vectors × height (stay-small targets)
    div_key = division.lower().replace(" ", "_")
    div_vector = DIVISION_VECTORS.get(div_key, DIVISION_VECTORS.get("mens_open", {}))
    for ratio_site in ("waist", "hips"):
        if ratio_site in div_vector and ratio_site not in ideal_circs:
            ideal_circs[ratio_site] = round(div_vector[ratio_site] * height_cm, 2)

    # Phase 6: Scoring
    site_scores = score_all_sites(lean_measurements, ideal_circs)

    return {
        "weight_cap_kg": weight_cap,
        "target_lbm_kg": target_lbm,
        "ghost_shape": ghost_shape,
        "hanavan_volumes": volumes,
        "ghost_mass_kg": ghost_mass,
        "allometric_multiplier": round(multiplier, 4),
        "scaled_ghost": scaled_ghost,
        "ideal_circumferences": ideal_circs,
        "site_scores": site_scores,
    }
