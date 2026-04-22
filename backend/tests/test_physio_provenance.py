"""V2.S0 — every per-division physio constant carries a citation.

Forces reviewers to keep provenance in step with values: a raw float that
sneaks in without a source will fail this test.
"""
from app.constants.physio import (
    STAGE_BF_PCT_BY_DIVISION,
    OFFSEASON_BF_CEILING_BY_DIVISION,
    PROVENANCE_REGISTRY,
    PhaseState,
    stage_bf_pct_for_division,
    offseason_bf_ceiling_for_division,
)
from app.constants.types import ValueWithUncertainty


REQUIRED_DIVISIONS = {
    "mens_open", "classic_physique", "mens_physique",
    "womens_bikini", "womens_figure", "womens_physique", "wellness",
}


def test_stage_bf_all_divisions_covered():
    assert REQUIRED_DIVISIONS.issubset(STAGE_BF_PCT_BY_DIVISION.keys())


def test_stage_bf_each_has_provenance():
    for div, entry in STAGE_BF_PCT_BY_DIVISION.items():
        assert isinstance(entry, ValueWithUncertainty)
        assert entry.source, f"{div} stage BF missing citation"


def test_offseason_ceiling_each_has_provenance():
    for div, entry in OFFSEASON_BF_CEILING_BY_DIVISION.items():
        assert isinstance(entry, ValueWithUncertainty)
        assert entry.source, f"{div} offseason ceiling missing citation"


def test_offseason_ceiling_stricter_than_prior():
    # v2 doc §1: ceilings moved from 16%/25% flat → ≤13% M, ≤24% F per division
    assert offseason_bf_ceiling_for_division("classic_physique") <= 14.0
    assert offseason_bf_ceiling_for_division("womens_bikini") <= 25.0


def test_stage_bf_classic_within_helms_band():
    v = STAGE_BF_PCT_BY_DIVISION["classic_physique"]
    assert 4.0 <= v.value <= 6.0  # Helms 2014 stage band for Classic


def test_stage_bf_bikini_within_chappell_band():
    v = STAGE_BF_PCT_BY_DIVISION["womens_bikini"]
    assert 10.0 <= v.value <= 14.0


def test_stage_bf_lookup_helpers():
    # Preferred (division-aware) API
    assert stage_bf_pct_for_division("classic_physique") == 5.0
    assert stage_bf_pct_for_division("womens_bikini") == 12.0
    # Unknown division falls back to male default (5%)
    assert stage_bf_pct_for_division("unknown_div") == 5.0


def test_provenance_registry_covers_each_constant():
    required_keys = {
        "STAGE_BF_PCT_BY_DIVISION",
        "OFFSEASON_BF_CEILING_BY_DIVISION",
        "SITE_LEAN_K",
        "SYMMETRY_PENALTY_MULT",
        "ASYMMETRY_UNILATERAL_REL",
    }
    assert required_keys.issubset(PROVENANCE_REGISTRY.keys())
    for k in required_keys:
        assert PROVENANCE_REGISTRY[k], f"{k} provenance empty"


def test_phase_state_enum_values_match_legacy_strings():
    # Any module migrated to PhaseState produces the same string the
    # stringly-typed callers expected.
    assert PhaseState.CUT.value == "cut"
    assert PhaseState.PPM_ACCUMULATION.value == "ppm_accumulation"
    assert PhaseState.PEAK_WEEK.value == "peak_week"
