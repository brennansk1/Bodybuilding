from __future__ import annotations

"""
Honesty Engine — Natural Attainability Check

Uses the Casey Butt genetic-ceiling model (engine1/weight_cap.py) to compare
the athlete's predicted natural maximum against the requirements of their
target competitive tier. Returns a clear recommendation that the frontend
surfaces as a warning modal for natural athletes pursuing advanced tiers.

Honest coaching: most apps hide or soft-pedal genetic limits. PPM does not.
If the math says a tier is not naturally attainable, say so — then offer
alternatives (natural federation, Men's Physique, adjust tier).
"""

from app.constants.competitive_tiers import CompetitiveTier, coerce_tier, get_tier_thresholds
from app.constants.weight_caps import lookup_weight_cap
from app.engines.engine1.weight_cap import compute_weight_cap
from app.engines.engine1.readiness import compute_normalized_ffmi


def check_natural_attainability(
    height_cm: float,
    wrist_cm: float | None,
    ankle_cm: float | None,
    target_tier,
    division: str = "classic_physique",
    stage_bf_pct: float = 5.0,
) -> dict:
    """Compare Casey Butt predicted natural maximum against tier requirements.

    When the wrist/ankle inputs are None, ``compute_weight_cap`` falls back to
    typical frame sizes — the caller should warn that the result is a rough
    estimate and encourage recording actual measurements.

    Returns
    -------
    dict
        predicted_natural_max_stage_kg, tier_required_stage_kg, gap_kg,
        weight_attainable, predicted_natural_ffmi, tier_ffmi_requirement,
        ffmi_attainable, overall_attainable, recommendation.
    """
    tier = coerce_tier(target_tier)
    thresholds = get_tier_thresholds(division, tier)

    predicted = compute_weight_cap(
        height_cm=height_cm,
        wrist_cm=wrist_cm,
        ankle_cm=ankle_cm,
        body_fat_pct=stage_bf_pct,
    )
    predicted_stage_kg = predicted["stage_weight_kg"]
    predicted_lbm_kg = predicted["max_lbm_kg"]

    division_cap_kg = lookup_weight_cap(height_cm, division)
    tier_required_stage_kg = thresholds.weight_cap_pct_min * division_cap_kg

    gap_kg = tier_required_stage_kg - predicted_stage_kg
    weight_attainable = gap_kg <= 0

    predicted_ffmi = compute_normalized_ffmi(predicted_lbm_kg, height_cm)
    ffmi_attainable = predicted_ffmi >= thresholds.ffmi_min

    overall_attainable = weight_attainable and ffmi_attainable

    recommendation = _attainability_recommendation(
        weight_ok=weight_attainable,
        ffmi_ok=ffmi_attainable,
        gap_kg=gap_kg,
        tier=tier,
    )

    return {
        "predicted_natural_max_stage_kg": round(predicted_stage_kg, 1),
        "predicted_natural_max_lbm_kg": round(predicted_lbm_kg, 1),
        "tier_required_stage_kg": round(tier_required_stage_kg, 1),
        "gap_kg": round(gap_kg, 1),
        "weight_attainable": weight_attainable,
        "predicted_natural_ffmi": predicted_ffmi,
        "tier_ffmi_requirement": thresholds.ffmi_min,
        "ffmi_attainable": ffmi_attainable,
        "overall_attainable": overall_attainable,
        "tier": tier.name,
        "tier_value": tier.value,
        "recommendation": recommendation,
    }


def _attainability_recommendation(
    weight_ok: bool,
    ffmi_ok: bool,
    gap_kg: float,
    tier: CompetitiveTier,
) -> str:
    if weight_ok and ffmi_ok:
        return (
            f"Your frame supports reaching {_tier_label(tier)} naturally. "
            f"Proceed with confidence."
        )
    if 0 < gap_kg <= 5:
        return (
            f"Your predicted natural ceiling is {gap_kg:.1f} kg below the "
            f"{_tier_label(tier)} target. This is borderline — exceptional "
            f"genetics, training, and nutrition might close this gap. "
            f"Consider competing one tier lower first to validate."
        )
    if gap_kg > 5:
        return (
            f"Your predicted natural ceiling is {gap_kg:.1f} kg below the "
            f"{_tier_label(tier)} target. This tier is likely not naturally "
            f"attainable for your frame. Consider: (a) competing in a natural "
            f"federation at your natural maximum, (b) targeting Men's Physique "
            f"where weight caps are lower, or (c) adjusting to a lower tier."
        )
    return (
        f"FFMI analysis suggests {_tier_label(tier)} may be beyond natural reach. "
        f"Re-evaluate after a full 12-16 month improvement cycle."
    )


def _tier_label(tier: CompetitiveTier) -> str:
    labels = {
        CompetitiveTier.LOCAL_NPC: "Tier 1 (Local NPC)",
        CompetitiveTier.REGIONAL_NPC: "Tier 2 (Regional NPC)",
        CompetitiveTier.NATIONAL_NPC: "Tier 3 (National NPC)",
        CompetitiveTier.PRO_QUALIFIER: "Tier 4 (Pro Qualifier)",
        CompetitiveTier.OLYMPIA: "Tier 5 (Olympia)",
    }
    return labels.get(tier, tier.name)
