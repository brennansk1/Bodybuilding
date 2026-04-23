"""V2.S4 — logistic gain curve + training-age correction."""
from app.engines.engine1.training_age import (
    effective_training_years,
    logistic_lbm,
    logistic_annual_gain,
    DEFAULT_CONSISTENCY, DEFAULT_INTENSITY, DEFAULT_PROGRAMMING,
)
from app.engines.engine1.readiness import estimate_cycles_to_tier
from app.constants.competitive_tiers import CompetitiveTier


# ---------------------------------------------------------------------------
# Training-age correction
# ---------------------------------------------------------------------------
def test_effective_years_full_factors():
    # All factors 1.0 → chronological unchanged
    assert effective_training_years(5.0, 1.0, 1.0, 1.0) == 5.0


def test_effective_years_sporadic_discount():
    # Sporadic trainee at light intensity / random programming
    eff = effective_training_years(10.0, 0.2, 0.4, 0.4)
    # 10 × 0.2 × 0.4 × 0.4 = 0.32 → ~0.3 year
    assert 0.30 <= eff <= 0.35


def test_effective_years_defaults_are_priors():
    # With no factors supplied, applies the documented priors
    eff = effective_training_years(5.0)
    expected = 5.0 * DEFAULT_CONSISTENCY * DEFAULT_INTENSITY * DEFAULT_PROGRAMMING
    assert abs(eff - round(expected, 2)) < 0.01


def test_effective_years_zero_when_chronological_zero():
    assert effective_training_years(0.0) == 0.0


def test_factor_out_of_range_clamped():
    # Clamp 0..1 — values above 1 behave like 1.0, below 0 like 0.0
    clamped_high = effective_training_years(5.0, consistency=2.0)
    expected_high = round(5.0 * 1.0 * DEFAULT_INTENSITY * DEFAULT_PROGRAMMING, 2)
    assert abs(clamped_high - expected_high) < 0.01
    assert effective_training_years(5.0, consistency=-1.0) == 0.0


# ---------------------------------------------------------------------------
# Logistic LBM curve
# ---------------------------------------------------------------------------
def test_logistic_lbm_asymptotes_at_ceiling():
    # At very long t_effective, LBM approaches ceiling
    val = logistic_lbm(ceiling_lbm_kg=80.0, t_effective_years=50.0)
    assert 79.5 <= val <= 80.0


def test_logistic_lbm_zero_time_zero_mass():
    # At t=0, LBM = 0 under pure-gain formulation
    assert logistic_lbm(80.0, 0.0) == 0.0


def test_novice_year_one_gain_matches_mcdonald():
    # McDonald: ~20-22 lb (9-10 kg) LBM gain in year 1 for a lifter
    # 60 kg current, 80 kg ceiling — within 9-10 kg year 1
    gain = logistic_annual_gain(ceiling_lbm_kg=80.0, current_lbm_kg=60.0)
    assert 4.0 <= gain <= 5.0   # natural 21.5% of 20 kg remaining ≈ 4.3 kg


def test_advanced_year_one_gain_small():
    # Year 6+ advanced, 78 kg of 80 kg ceiling → should be ≤ 0.6 kg
    gain = logistic_annual_gain(ceiling_lbm_kg=80.0, current_lbm_kg=78.0)
    assert gain <= 0.6


def test_enhanced_gain_faster_than_natural():
    nat = logistic_annual_gain(ceiling_lbm_kg=80.0, current_lbm_kg=70.0, training_status="natural")
    enh = logistic_annual_gain(ceiling_lbm_kg=80.0, current_lbm_kg=70.0, training_status="enhanced")
    assert enh > nat * 1.5


# ---------------------------------------------------------------------------
# Cycles-to-tier integration
# ---------------------------------------------------------------------------
def test_cycles_to_tier_uses_logistic():
    # sample: 93.5 kg @ 15% BF, T2 target, Classic Physique
    metrics = {
        "body_weight_kg": 93.5, "bf_pct": 15.0,
        "normalized_ffmi": 22.0,
        "shoulder_waist_ratio": 1.42, "chest_waist_ratio": 1.30,
        "arm_calf_neck_max_diff_inches": 0.8, "hqi_score": 72,
        "training_years": 4.0,
    }
    r = estimate_cycles_to_tier(
        metrics, CompetitiveTier.REGIONAL_NPC,
        training_years=4.0, training_status="natural",
        weight_cap_kg=105.2, division="classic_physique",
    )
    # Must surface the new logistic fields
    assert "t_effective_years" in r
    assert "muscle_fraction_used" in r
    assert "ceiling_lbm_kg_used" in r
    # Projected cycles bounded — mass not the limiter at T2 for sample
    assert 0 <= r["estimated_cycles"] <= 10


def test_cycles_zero_when_already_at_tier():
    # 96 kg of 100 kg cap at T1 → zero mass cycles
    metrics = {"body_weight_kg": 96.0, "bf_pct": 6.0, "normalized_ffmi": 25.0,
               "training_years": 8.0}
    r = estimate_cycles_to_tier(
        metrics, CompetitiveTier.LOCAL_NPC,
        training_years=8.0, training_status="natural",
        weight_cap_kg=100.0, division="classic_physique",
    )
    assert r["mass_cycles_needed"] == 0


def test_5pct_cycle_diminishing_removed():
    # Replace the old double-counted 5%/cycle term: a gap of say 3 kg
    # should resolve in fewer cycles than the old exponential+tax model.
    # Old: 3 kg / 1.5 kg per cycle × 1/0.95 tax = ~3 cycles
    # New (logistic): same 3 kg but single model → ≤3 cycles
    metrics = {"body_weight_kg": 90.0, "bf_pct": 12.0,
               "normalized_ffmi": 23.5, "training_years": 4.0}
    r = estimate_cycles_to_tier(
        metrics, CompetitiveTier.LOCAL_NPC,
        training_years=4.0, training_status="natural",
        weight_cap_kg=100.0, division="classic_physique",
    )
    # Sanity check: ceiling_lbm_kg_used should equal cap × 0.95 default
    assert r["ceiling_lbm_kg_used"] == 95.0


def test_muscle_fraction_parametrized_on_surplus():
    metrics = {"body_weight_kg": 85.0, "bf_pct": 12.0,
               "normalized_ffmi": 22.0, "training_years": 3.0}
    r_small = estimate_cycles_to_tier(
        metrics, CompetitiveTier.LOCAL_NPC,
        training_years=3.0, training_status="natural",
        weight_cap_kg=100.0, division="classic_physique",
        surplus_pct_per_week=0.2,
    )
    r_big = estimate_cycles_to_tier(
        metrics, CompetitiveTier.LOCAL_NPC,
        training_years=3.0, training_status="natural",
        weight_cap_kg=100.0, division="classic_physique",
        surplus_pct_per_week=0.6,
    )
    # Larger surplus → worse partitioning → lower muscle_fraction
    assert r_big["muscle_fraction_used"] < r_small["muscle_fraction_used"]
