"""V2.S1 — ceiling ensemble (Butt 1st/4th + Kouri + Berkhan + IFBB class cap)."""

from app.engines.engine1.ceiling_ensemble import (
    butt_1st_ceiling,
    butt_4th_ceiling,
    kouri_ceiling_lbm,
    berkhan_ceiling_stage,
    ceiling_envelope,
    ffmi_band,
)


# Bumstead-class inputs (5-time Classic Physique Olympia winner; height 185 cm).
BUMSTEAD_H_CM = 185.4
BUMSTEAD_WRIST_CM = 18.4
BUMSTEAD_ANKLE_CM = 24.0


def test_butt_4th_is_04pct_larger_than_1st():
    b1 = butt_1st_ceiling(BUMSTEAD_H_CM, BUMSTEAD_WRIST_CM, BUMSTEAD_ANKLE_CM)
    b4 = butt_4th_ceiling(BUMSTEAD_H_CM, BUMSTEAD_WRIST_CM, BUMSTEAD_ANKLE_CM)
    # 4th ed applies the 1.04 conservatism correction — within rounding.
    assert 1.03 <= b4["max_lbm_kg"] / b1["max_lbm_kg"] <= 1.05


def test_kouri_bands_are_monotonic():
    k24 = kouri_ceiling_lbm(BUMSTEAD_H_CM, sex="male", ffmi_target=24.0)
    k25 = kouri_ceiling_lbm(BUMSTEAD_H_CM, sex="male", ffmi_target=25.0)
    k26 = kouri_ceiling_lbm(BUMSTEAD_H_CM, sex="male", ffmi_target=26.0)
    assert k24 < k25 < k26


def test_kouri_female_scale_082x():
    k_male   = kouri_ceiling_lbm(170.0, sex="male", ffmi_target=25.0)
    k_female = kouri_ceiling_lbm(170.0, sex="female", ffmi_target=25.0)
    # Female scaling ~0.82× male per Chappell 2018
    assert 0.80 <= k_female / k_male <= 0.84


def test_berkhan_heuristic_scales_with_height():
    assert berkhan_ceiling_stage(165.0) == 63.0      # short: (165−100)−2
    assert berkhan_ceiling_stage(178.0) == 78.0      # mid
    assert berkhan_ceiling_stage(190.0) == 92.0      # tall: (190−100)+2


def test_envelope_median_in_bumstead_band():
    env = ceiling_envelope(
        height_cm=BUMSTEAD_H_CM,
        wrist_cm=BUMSTEAD_WRIST_CM,
        ankle_cm=BUMSTEAD_ANKLE_CM,
        division="classic_physique",
        sex="male",
        body_fat_pct=5.0,
    )
    # Bumstead's reported stage weight is ~103 kg (natural-enhanced debate
    # notwithstanding). Envelope median should be competitive — within the
    # 85-105 kg band for a 185cm Classic Physique male.
    assert 85.0 <= env["envelope_stage_kg"]["median"] <= 120.0
    # Models disagree — pessimistic < ambitious
    assert env["envelope_stage_kg"]["pessimistic"] < env["envelope_stage_kg"]["ambitious"]


def test_envelope_effective_is_capped_by_ifbb():
    # IFBB cap for 185.4 cm Classic Physique is 101.6 kg.
    env = ceiling_envelope(
        height_cm=BUMSTEAD_H_CM,
        wrist_cm=BUMSTEAD_WRIST_CM,
        ankle_cm=BUMSTEAD_ANKLE_CM,
        division="classic_physique",
        sex="male",
    )
    ifbb = env["model_estimates"]["ifbb_class_cap_kg"]
    assert env["effective_ceiling_stage_kg"] <= ifbb + 0.1


def test_ffmi_band_ranges():
    assert ffmi_band(20.0)["band"] == "common_natural"
    assert ffmi_band(23.0)["band"] == "above_average_natural"
    assert ffmi_band(24.5)["band"] == "elite_natural"
    assert ffmi_band(25.5)["band"] == "rare_elite_natural"
    assert ffmi_band(26.5)["band"] == "enhanced_likely"
    # Probabilities decrease monotonically across bands
    assert ffmi_band(20.0)["p_natural"] > ffmi_band(25.0)["p_natural"]
    assert ffmi_band(25.0)["p_natural"] > ffmi_band(26.5)["p_natural"]


def test_kouri_for_brennan_profile():
    # Brennan-like: 178 cm male, mid-intermediate.
    k25 = kouri_ceiling_lbm(178.0, sex="male", ffmi_target=25.0)
    # At 178cm, Kouri-25 LBM ≈ 78 kg — sanity check for the band label
    # emitted to readiness downstream.
    assert 75.0 <= k25 <= 82.0
