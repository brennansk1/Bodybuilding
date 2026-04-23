"""V2.S2 — ISAK-anchored girth projection."""
import math

from app.engines.engine1.girth_projection import (
    project_lean,
    project_lean_bf_only,
)


# sample skinfold row (struct-style; module handles both dict and obj).
BRENNAN_SKINFOLD = {
    "chest":       10.0,
    "midaxillary": 10.0,
    "tricep":      12.0,
    "subscapular": 14.0,
    "abdominal":   18.0,
    "suprailiac":  13.0,
    "thigh":       12.0,
    "bicep":       6.0,
    "calf":        5.0,
}


def test_isak_strips_bicep_by_skinfold():
    # Bicep 40 cm with 6 mm skinfold → π × 0.6 ≈ 1.88 cm stripped
    r = project_lean(40.0, "bicep", skinfold_row=BRENNAN_SKINFOLD, bf_pct=22.0)
    assert r["method"] == "isak_skinfold"
    assert abs(r["lean_cm"] - (40.0 - math.pi * 0.6)) < 0.01
    assert r["skinfold_mm"] == 6.0


def test_isak_waist_combines_abd_and_supra():
    # Waist skinfold = mean(abdominal 18, suprailiac 13) = 15.5mm
    r = project_lean(85.0, "waist", skinfold_row=BRENNAN_SKINFOLD)
    assert r["method"] == "isak_skinfold"
    assert abs(r["skinfold_mm"] - 15.5) < 0.01
    assert abs(r["lean_cm"] - (85.0 - math.pi * 1.55)) < 0.01


def test_floor_prevents_implausible_stripping():
    # 40 cm bicep with 25 mm skinfold would strip ~7.85 cm → 32.15 cm.
    # Floor = 0.85 × 40 = 34.0 cm. Floor must hold.
    absurd_row = dict(BRENNAN_SKINFOLD)
    absurd_row["bicep"] = 25.0
    r = project_lean(40.0, "bicep", skinfold_row=absurd_row)
    assert r["lean_cm"] == 34.0


def test_jp_fallback_without_skinfold_row():
    # No skinfold row → JP-derived per-site estimate
    r = project_lean(40.0, "bicep", skinfold_row=None, bf_pct=15.0, sex="male")
    assert r["method"] == "jp_derived"
    assert 36.0 <= r["lean_cm"] <= 39.5


def test_bf_linear_last_resort_when_no_inputs():
    # No skinfold AND no BF% → returns raw, method bf_linear
    r = project_lean(40.0, "bicep", skinfold_row=None, bf_pct=None)
    assert r["method"] == "bf_linear"
    assert r["lean_cm"] == 40.0


def test_isak_converges_with_bf_linear_at_stage_condition():
    # At 5% BF — stage condition — ISAK and BF-linear should both
    # produce lean ≈ raw (no stripping). Skinfolds at stage are minimal.
    stage_row = dict(BRENNAN_SKINFOLD)
    for site in stage_row:
        stage_row[site] = max(2.0, stage_row[site] / 4)
    r_isak = project_lean(40.0, "bicep", skinfold_row=stage_row)
    bf_only = project_lean_bf_only(40.0, "bicep", 5.0)
    assert abs(r_isak["lean_cm"] - bf_only) < 3.0


def test_isak_and_bf_linear_within_1cm_at_offseason():
    # At the sample athlete's 22% BF with real skinfolds, ISAK and BF-linear should
    # agree within ~1 cm (both strip ~1.9 cm for the bicep).
    r_isak = project_lean(40.0, "bicep", skinfold_row=BRENNAN_SKINFOLD, bf_pct=22.0)
    bf_only = project_lean_bf_only(40.0, "bicep", 22.0)
    assert abs(r_isak["lean_cm"] - bf_only) < 1.5


def test_forearm_uses_tricep_with_scale():
    # Forearm has no direct skinfold — uses tricep × 0.7
    # Tricep 12mm × 0.7 = 8.4mm → strips π × 0.84 = 2.64 cm
    r = project_lean(30.0, "forearm", skinfold_row=BRENNAN_SKINFOLD)
    assert r["method"] == "isak_skinfold"
    assert abs(r["skinfold_mm"] - 8.4) < 0.01


def test_neck_uses_subscapular_with_scale():
    # Neck uses subscapular × 0.6 → 14 × 0.6 = 8.4mm
    r = project_lean(38.0, "neck", skinfold_row=BRENNAN_SKINFOLD)
    assert r["method"] == "isak_skinfold"
    assert abs(r["skinfold_mm"] - 8.4) < 0.01


def test_invalid_raw_returns_zero():
    r = project_lean(0.0, "bicep", skinfold_row=BRENNAN_SKINFOLD)
    assert r["method"] == "invalid_input"
    assert r["lean_cm"] == 0.0
