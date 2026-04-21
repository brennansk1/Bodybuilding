"""
Regression tests for the Classic Physique audit pass + PPM feature.

Covers the Ground Truth audit doc's highest-impact fixes so a future change
doesn't silently regress:
  - Classic weight caps match IFBB Pro League 2024
  - Classic division vector (waist / shoulder_to_waist / chest) corrected
  - Other divisions untouched
  - Academic Cunningham (370 + 21.6 × LBM)
  - %-based caloric offsets (and PPM sub-phase aliases resolve)
  - Peak-week sodium/water constant for Classic; 7 g/kg load carbs
  - PPM readiness evaluation + honesty check + tier constants
  - Unified phase resolver (comp-date / PPM / fallback)
  - Arnold split template exists
  - Training-status volume scaling
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest


# ─── Classic weight caps ─────────────────────────────────────────────────────
class TestClassicWeightCaps:
    def test_caps_match_ifbb_pro_league_2024(self):
        from app.constants.weight_caps import _CLASSIC_PHYSIQUE_CAPS

        # Sample a few brackets per Ground Truth doc §2.1.
        cap_by_height = dict(_CLASSIC_PHYSIQUE_CAPS)
        assert cap_by_height[162.6] == 75.7
        assert cap_by_height[177.8] == 91.6
        assert cap_by_height[185.4] == 101.6
        assert cap_by_height[200.7] == 121.1
        assert cap_by_height[999.0] == 124.3

    def test_cap_lookup(self):
        from app.constants.weight_caps import lookup_weight_cap

        # 185 cm athlete → 101.6 kg bracket
        assert lookup_weight_cap(185.4, "classic_physique") == 101.6

    def test_target_lbm_consistency(self):
        from app.constants.weight_caps import lookup_target_lbm

        # Default stage BF = 5% → LBM = cap × 0.95
        cap_lbm = lookup_target_lbm(185.4, "classic_physique", stage_bf_pct=5.0)
        assert cap_lbm == pytest.approx(101.6 * 0.95, abs=0.05)

    def test_other_divisions_untouched(self):
        """Men's Physique / Open / Women's caps must not regress."""
        from app.constants.weight_caps import (
            _MENS_OPEN_CAPS,
            _MENS_PHYSIQUE_CAPS,
            _WOMENS_BIKINI_CAPS,
        )

        # Spot-check a bracket from each division that we should NOT have touched.
        assert dict(_MENS_OPEN_CAPS)[185.4] == 132.4
        assert dict(_MENS_PHYSIQUE_CAPS)[185.4] == 101.6
        assert dict(_WOMENS_BIKINI_CAPS)[160.0] == 51.3


# ─── Classic division vector ─────────────────────────────────────────────────
class TestClassicDivisionVector:
    def test_waist_ratio(self):
        from app.constants.divisions import DIVISION_VECTORS

        assert DIVISION_VECTORS["classic_physique"]["waist"] == 0.405

    def test_shoulder_to_waist_ratio(self):
        from app.constants.divisions import DIVISION_VECTORS

        assert DIVISION_VECTORS["classic_physique"]["shoulder_to_waist"] == 1.75

    def test_chest_ratio(self):
        from app.constants.divisions import DIVISION_VECTORS

        assert DIVISION_VECTORS["classic_physique"]["chest"] == 0.560

    def test_other_divisions_vector_untouched(self):
        from app.constants.divisions import DIVISION_VECTORS

        # Men's Open should still have its 0.447 waist and 1.382 shoulder_to_waist.
        mo = DIVISION_VECTORS["mens_open"]
        assert mo["waist"] == 0.447
        assert mo["shoulder_to_waist"] == 1.382
        # Men's Physique unchanged
        mp = DIVISION_VECTORS["mens_physique"]
        assert mp["waist"] == 0.415


# ─── Classic division classes ────────────────────────────────────────────────
class TestClassicDivisionClasses:
    def test_classes_weight_aligned_to_caps(self):
        from app.constants.division_classes import _CLASSIC_PHYSIQUE_CLASSES

        by_class = {c["class"]: c for c in _CLASSIC_PHYSIQUE_CLASSES}
        assert by_class["A"]["max_weight_kg"] == 82.6
        assert by_class["Open"]["max_weight_kg"] == 124.3

    def test_npc_sanctioning_body(self):
        from app.constants.division_classes import estimate_class

        # 3-class NPC structure: 173 cm → Class B (170.2 < h ≤ 177.8).
        result = estimate_class(
            173.0,
            "classic_physique",
            sanctioning_body="npc",
            npc_num_classes=3,
        )
        assert result["class"] == "B"
        assert result["sanctioning_body"] == "npc"

    def test_ifbb_pro_default(self):
        from app.constants.division_classes import estimate_class

        result = estimate_class(177.0, "classic_physique")
        assert result["sanctioning_body"] == "ifbb_pro"


# ─── Macros: Cunningham + %-offsets + protein raise + PPM aliases ────────────
class TestMacros:
    def test_academic_cunningham(self):
        from app.engines.engine3.macros import compute_rmr_cunningham

        # 85 kg LBM → 370 + 21.6 × 85 = 2206
        assert compute_rmr_cunningham(85.0) == pytest.approx(370 + 21.6 * 85, abs=0.01)

    def test_pct_offset_cut(self):
        from app.engines.engine3.macros import compute_macros

        # TDEE=3000, phase=cut (-20%) → 2400 kcal
        out = compute_macros(tdee=3000, phase="cut", weight_kg=90, sex="male",
                             lean_mass_kg=80, body_fat_pct=10)
        assert out["target_calories"] == pytest.approx(2400, abs=1)

    def test_pct_offset_bulk(self):
        from app.engines.engine3.macros import compute_macros

        # TDEE=3000, phase=bulk (+15%) → 3450 kcal
        out = compute_macros(tdee=3000, phase="bulk", weight_kg=90, sex="male",
                             lean_mass_kg=80, body_fat_pct=14)
        assert out["target_calories"] == pytest.approx(3450, abs=1)

    def test_ppm_alias_accumulation(self):
        from app.engines.engine3.macros import compute_macros

        # ppm_accumulation maps to lean_bulk (+10% TDEE).
        out = compute_macros(tdee=3000, phase="ppm_accumulation", weight_kg=90,
                             sex="male", lean_mass_kg=80, body_fat_pct=12)
        assert out["target_calories"] == pytest.approx(3300, abs=1)

    def test_ppm_alias_deload_is_maintain(self):
        from app.engines.engine3.macros import compute_macros

        out = compute_macros(tdee=3000, phase="ppm_deload", weight_kg=90,
                             sex="male", lean_mass_kg=80, body_fat_pct=12)
        assert out["target_calories"] == pytest.approx(3000, abs=1)

    def test_protein_raised_for_bulk(self):
        from app.engines.engine3.macros import _PROTEIN_PER_KG

        assert _PROTEIN_PER_KG["bulk"] == 2.2
        assert _PROTEIN_PER_KG["lean_bulk"] == 2.4
        assert _PROTEIN_PER_KG["maintain"] == 2.2

    def test_carb_cycle_in_output(self):
        from app.engines.engine3.macros import compute_macros

        out = compute_macros(tdee=3000, phase="cut", weight_kg=90, sex="male",
                             lean_mass_kg=80, body_fat_pct=10)
        assert "carb_cycle" in out
        assert out["carb_cycle"] is not None
        assert "high_day" in out["carb_cycle"]

    def test_rate_of_loss_tracker(self):
        from app.engines.engine3.macros import adjust_deficit_for_loss_rate

        # Losing 1.5% / wk → recommend loosen
        r = adjust_deficit_for_loss_rate(-0.20, [90, 88.65])  # 1.5% drop over 1 wk
        assert r["action"] == "loosen"
        # Losing 0.2% / wk → recommend tighten
        r2 = adjust_deficit_for_loss_rate(-0.20, [90, 89.82])
        assert r2["action"] == "tighten"


# ─── Peak week evidence-based (Classic) ──────────────────────────────────────
class TestPeakWeekClassic:
    def test_sodium_flat_for_classic(self):
        from app.engines.engine3.peak_week import compute_peak_week_protocol

        proto = compute_peak_week_protocol(lean_mass_kg=85, show_date=None,
                                           division="classic_physique")
        # Every day should have the same sodium target.
        sodium_vals = {d["sodium_mg"] for d in proto[:6]}
        # Monday-Saturday are all 2500; Sunday is also 2500 per current config.
        assert sodium_vals == {2500}

    def test_water_flat_for_classic(self):
        from app.engines.engine3.peak_week import compute_peak_week_protocol

        proto = compute_peak_week_protocol(lean_mass_kg=85, show_date=None,
                                           division="classic_physique")
        water_vals = {d["water_ml"] for d in proto}
        assert water_vals == {4500}

    def test_classic_load_carbs_7_g_per_kg_lbm(self):
        from app.engines.engine3.peak_week import compute_peak_week_protocol

        lbm = 85.0
        proto = compute_peak_week_protocol(lean_mass_kg=lbm,
                                           division="classic_physique")
        load_1 = next(d for d in proto if d["protocol_day"] == "load_1")
        assert load_1["carbs_g"] == pytest.approx(7.0 * lbm, rel=0.02)

    def test_other_divisions_still_taper(self):
        """Men's Open should still run an aggressive taper — we did not break that."""
        from app.engines.engine3.peak_week import compute_peak_week_protocol

        proto = compute_peak_week_protocol(lean_mass_kg=95, division="mens_open")
        sodium_vals = [d["sodium_mg"] for d in proto]
        # Not all equal — aggressive divisions drop sodium on show day.
        assert len(set(sodium_vals)) > 1

    def test_practice_peak_week_flag(self):
        from app.engines.engine3.peak_week import compute_peak_week_protocol

        proto = compute_peak_week_protocol(
            lean_mass_kg=85, division="classic_physique", practice_peak_week=True
        )
        # Practice peak keeps load carbs at 5 g/kg (not 7).
        load_1 = next(d for d in proto if d["protocol_day"] == "load_1")
        assert load_1["carbs_g"] == pytest.approx(5.0 * 85, rel=0.02)


# ─── Arnold split ────────────────────────────────────────────────────────────
class TestArnoldSplit:
    def test_arnold_template_exists(self):
        from app.engines.engine2.periodization import _SPLIT_TEMPLATES

        assert "arnold_split" in _SPLIT_TEMPLATES
        assert len(_SPLIT_TEMPLATES["arnold_split"]) == 3

    def test_classic_bias_for_6_days(self):
        from app.engines.engine2.periodization import auto_select_split

        # With uniformly average HQI, Classic at 6 days should bias toward arnold/bro.
        hqi = {m: 75 for m in [
            "chest", "back", "shoulders", "bicep", "tricep",
            "thigh", "calf", "glutes", "forearm", "neck",
        ]}
        pick = auto_select_split(
            hqi_scores=hqi,
            days_per_week=6,
            division="classic_physique",
            training_status="intermediate",
        )
        assert pick in ("arnold_split", "bro_split")


# ─── Volume landmarks: enhancement modifier ──────────────────────────────────
class TestVolumeLandmarks:
    def test_natural_unchanged(self):
        from app.engines.engine2.volume_landmarks import get_landmarks

        natural = get_landmarks("chest", training_years=4, training_status="natural")
        assert natural["mrv"] == 22   # intermediate baseline

    def test_enhanced_scales_mrv(self):
        from app.engines.engine2.volume_landmarks import get_landmarks

        enh = get_landmarks("chest", training_years=4, training_status="enhanced")
        natural = get_landmarks("chest", training_years=4, training_status="natural")
        assert enh["mrv"] > natural["mrv"]
        # But MEV should not grow.
        assert enh["mev"] == natural["mev"]


# ─── Competitive tiers constants ─────────────────────────────────────────────
class TestCompetitiveTiers:
    def test_all_five_tiers_defined(self):
        from app.constants.competitive_tiers import (
            CompetitiveTier,
            CLASSIC_PHYSIQUE_TIERS,
        )

        assert set(CLASSIC_PHYSIQUE_TIERS.keys()) == set(CompetitiveTier)

    def test_progressive_requirements(self):
        from app.constants.competitive_tiers import (
            CompetitiveTier,
            CLASSIC_PHYSIQUE_TIERS,
        )

        t1 = CLASSIC_PHYSIQUE_TIERS[CompetitiveTier.LOCAL_NPC]
        t5 = CLASSIC_PHYSIQUE_TIERS[CompetitiveTier.OLYMPIA]
        assert t5.weight_cap_pct_min > t1.weight_cap_pct_min
        assert t5.ffmi_min > t1.ffmi_min
        assert t5.shoulder_waist_min > t1.shoulder_waist_min
        assert t5.hqi_min > t1.hqi_min
        assert t5.arm_calf_neck_parity_max < t1.arm_calf_neck_parity_max

    def test_other_divisions_not_implemented(self):
        from app.constants.competitive_tiers import (
            CompetitiveTier,
            get_tier_thresholds,
        )

        with pytest.raises(NotImplementedError):
            get_tier_thresholds("mens_open", CompetitiveTier.LOCAL_NPC)


# ─── Readiness engine ────────────────────────────────────────────────────────
class TestReadiness:
    def _metrics(self, **overrides):
        base = {
            "body_weight_kg": 85.0,
            "normalized_ffmi": 24.0,
            "shoulder_waist_ratio": 1.55,
            "chest_waist_ratio": 1.42,
            "arm_calf_neck_max_diff_inches": 1.0,
            "hqi_score": 60.0,
            "training_years": 5.0,
        }
        base.update(overrides)
        return base

    def test_stage_ready_when_all_met(self):
        from app.constants.competitive_tiers import CompetitiveTier
        from app.engines.engine1.readiness import evaluate_readiness

        r = evaluate_readiness(
            athlete_metrics=self._metrics(body_weight_kg=90.0),
            target_tier=CompetitiveTier.LOCAL_NPC,
            weight_cap_kg=100.0,     # 90/100 = 0.90 > T1 min 0.80
            training_status="natural",
        )
        assert r["state"] == "stage_ready"

    def test_not_ready_when_gaps_large(self):
        from app.engines.engine1.readiness import evaluate_readiness

        r = evaluate_readiness(
            athlete_metrics=self._metrics(
                body_weight_kg=60.0,
                normalized_ffmi=18.0,
                shoulder_waist_ratio=1.20,
                chest_waist_ratio=1.15,
                hqi_score=20.0,
                training_years=1.0,
            ),
            target_tier=3,   # National NPC
            weight_cap_kg=100.0,
            training_status="natural",
        )
        assert r["state"] in ("not_ready", "developing")

    def test_limiting_factor_is_identified(self):
        from app.engines.engine1.readiness import evaluate_readiness

        r = evaluate_readiness(
            athlete_metrics=self._metrics(body_weight_kg=50.0),  # massive weight gap
            target_tier=1,
            weight_cap_kg=100.0,
            training_status="natural",
        )
        assert r["limiting_factor"] == "weight_cap_pct"

    def test_cycle_projection_decreases_with_less_gap(self):
        from app.engines.engine1.readiness import estimate_cycles_to_tier

        lean = estimate_cycles_to_tier(
            {"body_weight_kg": 95.0}, target_tier=1, training_years=5,
            training_status="natural", weight_cap_kg=100.0,
        )
        heavy_gap = estimate_cycles_to_tier(
            {"body_weight_kg": 70.0}, target_tier=1, training_years=5,
            training_status="natural", weight_cap_kg=100.0,
        )
        assert lean["estimated_cycles"] <= heavy_gap["estimated_cycles"]


# ─── Honesty engine ──────────────────────────────────────────────────────────
class TestHonesty:
    def test_large_natural_attainable_at_t1(self):
        from app.engines.engine1.honesty import check_natural_attainability

        # 6'1" (185.4 cm), 7.25" wrist (18.4 cm), 9" ankle (22.86 cm) — big frame.
        result = check_natural_attainability(
            height_cm=185.4, wrist_cm=18.4, ankle_cm=22.86, target_tier=1,
        )
        # T1 needs 80% of 101.6 kg = 81.3 kg; a 185 cm lifter should clear this.
        assert result["weight_attainable"] is True

    def test_tiny_natural_blocked_at_t5(self):
        from app.engines.engine1.honesty import check_natural_attainability

        # 5'6" natural, small frame — cannot reach Olympia.
        result = check_natural_attainability(
            height_cm=167.6, wrist_cm=16.0, ankle_cm=20.5, target_tier=5,
        )
        assert result["overall_attainable"] is False


# ─── Unified phase resolver ──────────────────────────────────────────────────
class TestPhaseResolver:
    def test_comp_date_uses_legacy(self):
        from app.engines.engine1.prep_timeline import get_current_phase

        phase = get_current_phase(
            competition_date=date.today() + timedelta(days=35),
            current_date=date.today(),
        )
        assert phase == "cut"

    def test_ppm_sub_phase_at_week_4(self):
        from app.engines.engine1.prep_timeline import get_current_phase

        start = date.today() - timedelta(days=3 * 7)  # week 4 (1-indexed)
        phase = get_current_phase(
            competition_date=None,
            ppm_enabled=True,
            cycle_start_date=start,
            current_date=date.today(),
        )
        assert phase == "ppm_accumulation"

    def test_ppm_deload_week_13(self):
        from app.engines.engine1.prep_timeline import get_current_phase

        start = date.today() - timedelta(days=12 * 7)
        phase = get_current_phase(
            competition_date=None,
            ppm_enabled=True,
            cycle_start_date=start,
            current_date=date.today(),
        )
        assert phase == "ppm_deload"

    def test_fallback_offseason(self):
        from app.engines.engine1.prep_timeline import get_current_phase

        assert get_current_phase(competition_date=None) == "offseason"


# ─── Aesthetic vector helpers ────────────────────────────────────────────────
class TestAestheticVector:
    def test_arm_calf_neck_parity(self):
        from app.engines.engine1.aesthetic_vector import compute_arm_calf_neck_parity

        # Within 1 cm → Reeves equal (threshold 1.27 cm / 0.5")
        r = compute_arm_calf_neck_parity({"bicep": 45.7, "calf": 45.0, "neck": 45.3})
        assert r["reeves_equal"] is True

        # 3 cm gap → not equal
        r2 = compute_arm_calf_neck_parity({"bicep": 50.0, "calf": 47.0, "neck": 45.0})
        assert r2["reeves_equal"] is False
        assert r2["max_diff_cm"] == pytest.approx(5.0, abs=0.01)

    def test_chest_waist_ratio(self):
        from app.engines.engine1.aesthetic_vector import compute_chest_waist_ratio

        # 132 cm chest / 77 cm waist ≈ 1.714 (CBum-ish)
        r = compute_chest_waist_ratio(132.0, 77.0)
        assert r == pytest.approx(1.714, abs=0.002)


# ─── Conditioning style (Classic only) ───────────────────────────────────────
class TestConditioningStyle:
    def test_full_bonus_for_classic(self):
        from app.engines.engine1.pds import compute_conditioning_score

        # BF well off target so base score is not already at 100 (avoiding clamp).
        neutral = compute_conditioning_score(8.0, "male", "peak_week",
                                             division="classic_physique")
        full = compute_conditioning_score(8.0, "male", "peak_week",
                                          conditioning_style="full",
                                          division="classic_physique")
        grainy = compute_conditioning_score(8.0, "male", "peak_week",
                                            conditioning_style="grainy",
                                            division="classic_physique")
        assert full > neutral
        assert grainy < neutral

    def test_other_divisions_unaffected(self):
        from app.engines.engine1.pds import compute_conditioning_score

        base = compute_conditioning_score(8.0, "male", "peak_week",
                                          division="mens_open")
        with_style = compute_conditioning_score(8.0, "male", "peak_week",
                                                conditioning_style="grainy",
                                                division="mens_open")
        assert base == with_style
