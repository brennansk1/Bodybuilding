"""V2.S3 — HQI visibility recalibration.

Fixes the mens_physique.thigh = 0.0 bug: MP board shorts expose upper
quad; a 10cm thigh lean gap should produce a non-zero weighted_gap.
"""
from app.constants.divisions import DIVISION_VISIBILITY, get_division_visibility
from app.engines.engine1.muscle_gaps import rank_sites_by_gap
from app.engines.engine1.hqi import (
    _DIVISION_VISIBILITY as HQI_V,
    _DEFAULT_VISIBILITY as HQI_D,
)
from app.engines.engine1.aesthetic_vector import (
    _DIVISION_SITE_VISIBILITY as AV_V,
    _DEFAULT_VISIBILITY as AV_D,
)


def test_mens_physique_thigh_no_longer_zero():
    v = get_division_visibility("mens_physique")
    assert v["thigh"] > 0.3, "MP thigh visibility must not be 0 (was a bug)"


def test_mens_physique_calf_bumped():
    v = get_division_visibility("mens_physique")
    assert v["calf"] >= 0.30


def test_glutes_first_class_all_divisions():
    # Every division now has glutes as a judged site
    for div in ("mens_open", "classic_physique", "mens_physique",
                "womens_bikini", "womens_figure", "womens_physique", "wellness"):
        assert "glutes" in DIVISION_VISIBILITY[div], f"{div} missing glutes"


def test_visibility_is_single_source_of_truth():
    # All three legacy call sites point at the same object
    assert HQI_V is DIVISION_VISIBILITY
    assert AV_V is DIVISION_VISIBILITY
    assert HQI_D is AV_D  # same default table


def test_mp_thigh_gap_ranks_non_zero():
    """Rebuild the pre-v2 bug scenario: 10 cm lean thigh gap on MP athlete."""
    site_data = {
        "thigh": {
            "current_lean_cm": 52.0,
            "ideal_lean_cm":   62.0,
            "gap_cm":          10.0,
            "pct_of_ideal":    83.9,
            "gap_type":        "add_muscle",
        },
    }
    ranked = rank_sites_by_gap(site_data, division="mens_physique")
    assert len(ranked) == 1
    # weighted_gap = gap × visibility. v2 sets MP thigh to 0.55 → 10 × 0.55 = 5.5
    assert ranked[0]["weighted_gap"] == 5.5


def test_classic_has_stronger_thigh_weight_than_mp():
    """An identical thigh gap on Classic Physique weighs more than on MP."""
    site_data = {
        "thigh": {
            "current_lean_cm": 52.0,
            "ideal_lean_cm":   62.0,
            "gap_cm":          10.0,
            "pct_of_ideal":    83.9,
            "gap_type":        "add_muscle",
        },
    }
    classic = rank_sites_by_gap(site_data, division="classic_physique")
    mp = rank_sites_by_gap(site_data, division="mens_physique")
    assert classic[0]["weighted_gap"] > mp[0]["weighted_gap"]
    # Ratio ≈ 1.0 / 0.55 = 1.82
    assert 1.7 <= classic[0]["weighted_gap"] / mp[0]["weighted_gap"] <= 1.9


def test_bikini_hip_dominance_preserved():
    # Bikini hips are primary criterion; visibility must stay high
    v = get_division_visibility("womens_bikini")
    assert v["hips"] >= 0.95
    assert v["glutes"] >= 0.95
    # Forearms de-emphasized in bikini (not a judged site)
    assert v["forearm"] <= 0.70


def test_unknown_division_falls_back_to_default():
    v = get_division_visibility("alien_pose_round")
    # Default: all sites 1.0
    assert v["thigh"] == 1.0
    assert v["glutes"] == 1.0
