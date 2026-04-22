"""V2.S9 — illusion metrics + conditioning_pct + relative asymmetry."""
from app.engines.engine1.aesthetic_vector import (
    compute_vtaper,
    compute_xframe,
    compute_waist_height_ratio,
)
from app.engines.engine1.readiness import evaluate_readiness
from app.engines.engine2.split_designer import design_split
from app.constants.competitive_tiers import CompetitiveTier


# ---------------------------------------------------------------------------
# Illusion helpers
# ---------------------------------------------------------------------------
def test_vtaper_zero_on_missing_waist():
    assert compute_vtaper(135.0, 0.0) == 0.0
    assert compute_vtaper(135.0, None) == 0.0


def test_vtaper_bumstead_range():
    # Bumstead: shoulders ≈ 135 cm, waist ≈ 76 cm → vtaper 1.776
    v = compute_vtaper(135.0, 76.0)
    assert 1.75 <= v <= 1.80


def test_xframe_formula():
    # shoulders 132, hips 102, waist 76 → (132 × 102) / 76² = 2.332
    x = compute_xframe(132.0, 102.0, 76.0)
    assert 2.30 <= x <= 2.40


def test_xframe_passes_t4_fails_t5():
    # Bumstead proportions: 132/102/76 → xframe 2.33
    # T4 threshold 2.45 → fails T4; T3 threshold 2.35 → below T3
    x = compute_xframe(132.0, 102.0, 76.0)
    from app.constants.competitive_tiers import get_tier_thresholds
    t_pro = get_tier_thresholds("classic_physique", CompetitiveTier.PRO_QUALIFIER)
    t_oly = get_tier_thresholds("classic_physique", CompetitiveTier.OLYMPIA)
    assert x < t_pro.illusion_xframe_min
    assert x < t_oly.illusion_xframe_min


def test_waist_height_ratio_target():
    # Male physique target ~0.45
    assert compute_waist_height_ratio(82.0, 182.0) == round(82.0 / 182.0, 3)


# ---------------------------------------------------------------------------
# Readiness integration — illusion + conditioning
# ---------------------------------------------------------------------------
def _base_metrics(**over):
    base = {
        "body_weight_kg": 93.5, "bf_pct": 12.0,
        "normalized_ffmi": 23.5,
        "shoulder_waist_ratio": 1.50, "chest_waist_ratio": 1.38,
        "arm_calf_neck_max_diff_inches": 0.8,
        "hqi_score": 60, "training_years": 5.0,
        "illusion_xframe": 2.25,
    }
    base.update(over)
    return base


def test_illusion_score_metric_surfaces():
    r = evaluate_readiness(
        _base_metrics(illusion_xframe=2.40),
        target_tier=CompetitiveTier.NATIONAL_NPC,
        weight_cap_kg=105.2,
        training_status="natural",
        division="classic_physique",
    )
    assert "illusion_score" in r["per_metric"]
    # T3 threshold 2.35, athlete at 2.40 → met
    assert r["per_metric"]["illusion_score"]["met"] is True


def test_conditioning_pct_surfaces():
    # Classic offseason ceiling 13%, stage 5%, span 8%.
    # Athlete at 10% BF → (13−10)/(13−5) = 0.375 (3/8ths of the way down)
    r = evaluate_readiness(
        _base_metrics(bf_pct=10.0),
        target_tier=CompetitiveTier.LOCAL_NPC,
        weight_cap_kg=105.2,
        training_status="natural",
        division="classic_physique",
    )
    assert "conditioning_pct" in r["per_metric"]
    c = r["per_metric"]["conditioning_pct"]
    assert 0.35 <= c["current"] <= 0.40


def test_conditioning_pct_met_at_stage_bf():
    r = evaluate_readiness(
        _base_metrics(bf_pct=5.0),
        target_tier=CompetitiveTier.LOCAL_NPC,
        weight_cap_kg=105.2,
        training_status="natural",
        division="classic_physique",
    )
    c = r["per_metric"]["conditioning_pct"]
    assert c["current"] >= 0.99


# ---------------------------------------------------------------------------
# Relative asymmetry — graded bonus (v2 Sprint 9)
# ---------------------------------------------------------------------------
def test_asymmetry_below_threshold_no_bias():
    # 40 cm / 40.5 cm bicep — 1.25% spread, below 2.5% arm threshold
    r = design_split(
        {"bicep": 3.0}, "classic_physique", 5,
        tape_pairs={"bicep": (40.0, 40.5)},
    )
    assert r["unilateral_bias"] == {}


def test_asymmetry_graded_bonus_3pct_spread():
    # 40 / 41.2 cm bicep — 2.96% spread, above 2.5% arm threshold
    # bonus = round(100 × (0.0296 − 0.02)) = round(0.96) = 1
    r = design_split(
        {"bicep": 3.0}, "classic_physique", 5,
        tape_pairs={"bicep": (40.0, 41.2)},
    )
    assert "biceps" in r["unilateral_bias"]
    assert r["unilateral_bias"]["biceps"]["bonus_sets_per_session"] == 1


def test_asymmetry_graded_bonus_5pct_spread():
    # 40 / 42 cm bicep — 4.88% spread
    # bonus = round(100 × (0.0488 − 0.02)) = round(2.88) = 3
    r = design_split(
        {"bicep": 3.0}, "classic_physique", 5,
        tape_pairs={"bicep": (40.0, 42.0)},
    )
    assert "biceps" in r["unilateral_bias"]
    b = r["unilateral_bias"]["biceps"]
    assert b["lagging_side"] == "left"  # left (40) is smaller
    assert b["bonus_sets_per_session"] == 3


def test_asymmetry_clamped_at_6_with_practitioner_flag():
    # 40 / 50 cm — 22% spread, clamps at 6 + sets practitioner_review
    r = design_split(
        {"bicep": 5.0}, "classic_physique", 5,
        tape_pairs={"bicep": (40.0, 50.0)},
    )
    b = r["unilateral_bias"]["biceps"]
    assert b["bonus_sets_per_session"] == 6
    assert b["practitioner_review"] is True


def test_relative_threshold_favors_small_muscles():
    # Same 2 cm absolute spread:
    #   thigh (74/76)  → 2.67% spread < 3.5% thigh threshold → no bias
    #   forearm (28/30) → 6.9% spread > 2.5% arm threshold  → bonus 5
    r_thigh = design_split(
        {"thigh": 5.0}, "classic_physique", 5,
        tape_pairs={"thigh": (74.0, 76.0)},
    )
    r_forearm = design_split(
        {"forearm": 5.0}, "classic_physique", 5,
        tape_pairs={"forearm": (28.0, 30.0)},
    )
    assert r_thigh["unilateral_bias"] == {}
    assert "forearms" in r_forearm["unilateral_bias"]
    # bonus = round(100 × (0.069 − 0.02)) = round(4.9) = 5
    assert r_forearm["unilateral_bias"]["forearms"]["bonus_sets_per_session"] == 5
