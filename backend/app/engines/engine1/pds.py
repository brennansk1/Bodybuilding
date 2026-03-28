from __future__ import annotations

"""
Physique Development Score (PDS)

Composite score (0-100) integrating:
- Aesthetic similarity (cosine similarity to division vector)
- Muscle mass score (total LCSA relative to height-adjusted ceiling)
- Conditioning score (body fat proximity + optional visual indicators)
- Symmetry score (bilateral measurement variance) — elevated weight

Component weights are DIVISION-SPECIFIC to match judging criteria:
- Men's Open: mass-dominant (0.30 aesthetic, 0.40 mass, 0.15 conditioning, 0.15 symmetry)
- Classic Physique: aesthetics-dominant (0.45 aesthetic, 0.25 mass, 0.15 conditioning, 0.15 symmetry)
- Men's Physique: balanced aesthetics + conditioning (0.40 aesthetic, 0.20 mass, 0.25 conditioning, 0.15 symmetry)
- Women's Bikini: conditioning-dominant (0.30 aesthetic, 0.15 mass, 0.35 conditioning, 0.20 symmetry)
- Women's Figure: balanced (0.35 aesthetic, 0.25 mass, 0.25 conditioning, 0.15 symmetry)
- Women's Physique: similar to men's open (0.35 aesthetic, 0.35 mass, 0.15 conditioning, 0.15 symmetry)

Tier bands:
- Elite: 85-100
- Advanced: 70-84
- Intermediate: 50-69
- Novice: 0-49
"""


# Division-specific PDS component weights
# Each tuple: (aesthetic, muscle_mass, conditioning, symmetry)
_DIVISION_WEIGHTS: dict[str, tuple[float, float, float, float]] = {
    "mens_open":        (0.30, 0.40, 0.15, 0.15),
    "classic_physique": (0.45, 0.25, 0.15, 0.15),
    "mens_physique":    (0.40, 0.20, 0.25, 0.15),
    "womens_bikini":    (0.35, 0.10, 0.30, 0.25),  # presentation/aesthetic > conditioning
    "womens_figure":    (0.35, 0.25, 0.25, 0.15),
    "womens_physique":  (0.35, 0.35, 0.15, 0.15),
    "wellness":         (0.30, 0.15, 0.25, 0.30),  # lower body symmetry + glute mass
}
_DEFAULT_WEIGHTS = (0.40, 0.30, 0.20, 0.10)


def get_division_weights(division: str | None = None) -> dict[str, float]:
    """Return the PDS component weights for a division."""
    key = (division or "").lower().replace(" ", "_")
    w = _DIVISION_WEIGHTS.get(key, _DEFAULT_WEIGHTS)
    return {
        "aesthetic": w[0],
        "muscle_mass": w[1],
        "conditioning": w[2],
        "symmetry": w[3],
    }


def compute_muscle_mass_score(total_lcsa: float, height_cm: float, sex: str) -> float:
    """
    Score muscle mass 0-100 relative to height-based genetic ceiling.
    """
    if sex == "male":
        ceiling = 20.0 * height_cm
    else:
        ceiling = 14.0 * height_cm

    if ceiling <= 0:
        return 0.0

    ratio = total_lcsa / ceiling
    score = min(100.0, ratio * 100)
    return round(score, 1)


def compute_conditioning_score(
    body_fat_pct: float | None,
    sex: str,
    phase: str = "offseason",
    vascularity: float | None = None,
    muscle_hardness: float | None = None,
    striation_visibility: float | None = None,
) -> float:
    """
    Score conditioning 0-100.

    80% from body fat proximity to phase ideal (quadratic penalty).
    20% from optional subjective visual indicators when provided.
    """
    if body_fat_pct is None:
        return 50.0

    if sex == "male":
        ideal_bf = {"contest": 4.0, "peak_week": 5.0, "peak": 5.0, "cut": 8.0,
                    "offseason": 12.0, "bulk": 15.0, "lean_bulk": 13.0,
                    "maintain": 12.0, "restoration": 10.0}
    else:
        ideal_bf = {"contest": 10.0, "peak_week": 11.0, "peak": 11.0, "cut": 14.0,
                    "offseason": 18.0, "bulk": 22.0, "lean_bulk": 19.0,
                    "maintain": 18.0, "restoration": 16.0}

    target = ideal_bf.get(phase, ideal_bf["offseason"])
    deviation = abs(body_fat_pct - target)
    bf_score = max(0.0, 100.0 - 0.5 * deviation ** 2)

    visual_scores = []
    for val in (vascularity, muscle_hardness, striation_visibility):
        if val is not None:
            visual_scores.append(max(0.0, min(100.0, (val - 1) / 9 * 100)))

    if visual_scores:
        visual_avg = sum(visual_scores) / len(visual_scores)
        score = 0.80 * bf_score + 0.20 * visual_avg
    else:
        score = bf_score

    return round(score, 1)


def compute_symmetry_score(tape_measurements: dict[str, float]) -> float:
    """
    Score bilateral symmetry 0-100. Compares left/right measurements.
    """
    pairs = [
        ("left_bicep", "right_bicep"),
        ("left_forearm", "right_forearm"),
        ("left_thigh", "right_thigh"),
        ("left_calf", "right_calf"),
    ]

    deviations: list[float] = []
    for left, right in pairs:
        if left in tape_measurements and right in tape_measurements:
            l_val = tape_measurements[left]
            r_val = tape_measurements[right]
            if l_val > 0 and r_val > 0:
                avg = (l_val + r_val) / 2
                dev = abs(l_val - r_val) / avg
                deviations.append(dev)

    if not deviations:
        return 80.0

    avg_deviation = sum(deviations) / len(deviations)
    score = max(0.0, 100.0 - avg_deviation * 500)
    return round(score, 1)


# Per-site symmetry penalty multipliers (used by compute_symmetry_details)
# Arms and calves are heavily penalized (visible from front/back at every pose)
# Thighs are lightly penalized (quad dominance is common and somewhat accepted)
_SYMMETRY_PENALTY_MULT: dict[str, float] = {
    "bicep":   600,   # heavily judged — every front double bi
    "forearm": 600,   # visible in most poses
    "calf":    550,   # extremely visible standing
    "thigh":   300,   # quad dominance tolerated by most divisions
}


def compute_symmetry_details(tape_measurements: dict[str, float]) -> list[dict]:
    """Return per-pair symmetry breakdown for display."""
    pairs = [
        ("left_bicep", "right_bicep", "bicep"),
        ("left_forearm", "right_forearm", "forearm"),
        ("left_thigh", "right_thigh", "thigh"),
        ("left_calf", "right_calf", "calf"),
    ]
    details = []
    for left, right, name in pairs:
        if left in tape_measurements and right in tape_measurements:
            l_val = tape_measurements[left]
            r_val = tape_measurements[right]
            if l_val > 0 and r_val > 0:
                avg = (l_val + r_val) / 2
                dev = abs(l_val - r_val) / avg
                # Site-specific penalty: arms/calves penalized more than legs
                penalty_mult = _SYMMETRY_PENALTY_MULT.get(name, 500)
                site_score = max(0.0, 100.0 - dev * penalty_mult)
                details.append({
                    "site": name,
                    "left_cm": round(l_val, 1),
                    "right_cm": round(r_val, 1),
                    "diff_cm": round(abs(l_val - r_val), 1),
                    "deviation_pct": round(dev * 100, 1),
                    "site_symmetry_score": round(site_score, 1),
                    "dominant_side": "left" if l_val > r_val else "right" if r_val > l_val else "even",
                })
    return details


def compute_pds(
    aesthetic_score: float,
    muscle_mass_score: float,
    conditioning_score: float,
    symmetry_score: float,
    division: str | None = None,
) -> float:
    """
    Division-weighted composite PDS.
    """
    weights = get_division_weights(division)
    pds = (
        aesthetic_score * weights["aesthetic"]
        + muscle_mass_score * weights["muscle_mass"]
        + conditioning_score * weights["conditioning"]
        + symmetry_score * weights["symmetry"]
    )
    return round(min(100.0, max(0.0, pds)), 1)


def get_tier(pds_score: float) -> str:
    if pds_score >= 85:
        return "elite"
    elif pds_score >= 70:
        return "advanced"
    elif pds_score >= 50:
        return "intermediate"
    return "novice"


TIER_BOUNDARIES = {
    "elite": 85,
    "advanced": 70,
    "intermediate": 50,
    "novice": 0,
}
