from __future__ import annotations

"""
Competitive Tier Thresholds — Perpetual Progression Mode (PPM)

Five measurable competitive tiers ranging from first-show-ready (T1) to
Olympia contender (T5). Each tier defines concrete thresholds on 7 metrics:
weight-cap %, body fat %, FFMI, shoulder:waist, chest:waist, arm/calf/neck
parity, HQI, and a soft training-years gate.

These thresholds are Classic Physique-specific in this first pass.
Division-specific threshold tables for other divisions can be added by
extending ``TIER_THRESHOLDS`` with a nested division key.
"""

from dataclasses import dataclass
from enum import Enum


class CompetitiveTier(Enum):
    LOCAL_NPC      = 1
    REGIONAL_NPC   = 2
    NATIONAL_NPC   = 3
    PRO_QUALIFIER  = 4
    OLYMPIA        = 5


class ReadinessState(Enum):
    NOT_READY     = "not_ready"
    DEVELOPING    = "developing"
    APPROACHING   = "approaching"
    STAGE_READY   = "stage_ready"


@dataclass
class TierThresholds:
    """Concrete thresholds for a single competitive tier."""
    weight_cap_pct_min: float          # athlete weight / division weight cap
    weight_cap_pct_max: float
    bf_pct_max: float                  # stage body fat %
    bf_pct_min: float
    skinfold_sum3_max: float           # mm — advisory only
    ffmi_min: float                    # normalized (height²) lean-mass index
    shoulder_waist_min: float          # circumferential ratio
    chest_waist_min: float             # circumferential ratio (decimal: 1.30 = 130%)
    arm_calf_neck_parity_max: float    # max diff between the three, in inches
    hqi_min: float                     # app-internal composite score
    training_years_natural: float      # soft gate
    training_years_enhanced: float


# ---------------------------------------------------------------------------
# Classic Physique tier table (Ground Truth PPM doc §2.2)
# ---------------------------------------------------------------------------
CLASSIC_PHYSIQUE_TIERS: dict[CompetitiveTier, TierThresholds] = {
    CompetitiveTier.LOCAL_NPC: TierThresholds(
        weight_cap_pct_min=0.80, weight_cap_pct_max=0.87,
        bf_pct_max=8.0, bf_pct_min=6.0,
        skinfold_sum3_max=35.0, ffmi_min=22.0,
        shoulder_waist_min=1.40, chest_waist_min=1.30,
        arm_calf_neck_parity_max=1.5, hqi_min=40.0,
        training_years_natural=3.0, training_years_enhanced=3.0,
    ),
    CompetitiveTier.REGIONAL_NPC: TierThresholds(
        weight_cap_pct_min=0.87, weight_cap_pct_max=0.92,
        bf_pct_max=7.0, bf_pct_min=5.0,
        skinfold_sum3_max=25.0, ffmi_min=24.0,
        shoulder_waist_min=1.50, chest_waist_min=1.38,
        arm_calf_neck_parity_max=1.0, hqi_min=55.0,
        training_years_natural=5.0, training_years_enhanced=4.0,
    ),
    CompetitiveTier.NATIONAL_NPC: TierThresholds(
        weight_cap_pct_min=0.92, weight_cap_pct_max=0.97,
        bf_pct_max=6.0, bf_pct_min=4.0,
        skinfold_sum3_max=18.0, ffmi_min=25.5,
        shoulder_waist_min=1.55, chest_waist_min=1.42,
        arm_calf_neck_parity_max=0.5, hqi_min=70.0,
        training_years_natural=7.0, training_years_enhanced=6.0,
    ),
    CompetitiveTier.PRO_QUALIFIER: TierThresholds(
        weight_cap_pct_min=0.97, weight_cap_pct_max=1.00,
        bf_pct_max=5.0, bf_pct_min=3.0,
        skinfold_sum3_max=12.0, ffmi_min=27.0,
        shoulder_waist_min=1.60, chest_waist_min=1.46,
        arm_calf_neck_parity_max=0.25, hqi_min=82.0,
        training_years_natural=10.0, training_years_enhanced=7.0,
    ),
    CompetitiveTier.OLYMPIA: TierThresholds(
        weight_cap_pct_min=1.00, weight_cap_pct_max=1.00,
        bf_pct_max=4.0, bf_pct_min=3.0,
        skinfold_sum3_max=8.0, ffmi_min=28.5,
        shoulder_waist_min=1.618, chest_waist_min=1.48,
        arm_calf_neck_parity_max=0.0, hqi_min=90.0,
        training_years_natural=99.0,   # not naturally attainable
        training_years_enhanced=10.0,
    ),
}


TIER_THRESHOLDS: dict[str, dict[CompetitiveTier, TierThresholds]] = {
    "classic_physique": CLASSIC_PHYSIQUE_TIERS,
}


def get_tier_thresholds(division: str, tier: CompetitiveTier) -> TierThresholds:
    """Return the TierThresholds for a given division + tier.

    Raises NotImplementedError if the division is not yet covered (only
    Classic Physique in this first PPM pass).
    """
    key = (division or "").lower().replace(" ", "_")
    if key not in TIER_THRESHOLDS:
        raise NotImplementedError(
            f"PPM tier thresholds are currently defined only for 'classic_physique'. "
            f"Division '{division}' is not supported in this release."
        )
    return TIER_THRESHOLDS[key][tier]


def coerce_tier(value) -> CompetitiveTier:
    """Accept an int (1–5), a string enum name, or a CompetitiveTier."""
    if isinstance(value, CompetitiveTier):
        return value
    if isinstance(value, int):
        return CompetitiveTier(value)
    if isinstance(value, str):
        value = value.strip().upper()
        if value.isdigit():
            return CompetitiveTier(int(value))
        return CompetitiveTier[value]
    raise ValueError(f"Cannot coerce {value!r} to CompetitiveTier")
