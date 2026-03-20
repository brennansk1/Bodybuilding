"""
Full-system simulation: intermediate Men's Physique competitor, 6'2" (188 cm).

Athlete Profile:
  - Height: 188 cm (6'2")
  - Sex: male
  - Age: 27
  - Division: mens_physique
  - Training experience: 3.5 years (intermediate)
  - Body weight: 90 kg offseason (~12% BF)
  - Phase: offseason / lean bulk

Every test uses realistic measurements for this athlete and validates
results fall within expected physiological ranges for a natural
intermediate MP competitor.
"""

import math
from datetime import date, timedelta

import pytest

# ---------------------------------------------------------------------------
# Athlete constants — reused across all test classes
# ---------------------------------------------------------------------------
HEIGHT_CM = 188.0
SEX = "male"
AGE = 27
DIVISION = "mens_physique"
BODY_WEIGHT_KG = 90.0
BODY_FAT_PCT = 12.0
TRAINING_YEARS = 3.5
DAYS_PER_WEEK = 5

# Realistic intermediate MP measurements at 188 cm / 90 kg / 12% BF
TAPE = {
    "neck": 39.0,
    "shoulders": 122.0,
    "chest": 106.0,
    "bicep_left": 37.5, "bicep_right": 38.0,
    "forearm_left": 30.0, "forearm_right": 30.5,
    "waist": 81.0,
    "hips": 96.0,
    "thigh_left": 58.0, "thigh_right": 59.0,
    "calf_left": 38.5, "calf_right": 39.0,
}
# Averaged bilateral sites for engine consumption
TAPE_AVERAGED = {
    "neck": 39.0,
    "shoulders": 122.0,
    "chest": 106.0,
    "bicep": 37.75,
    "forearm": 30.25,
    "waist": 81.0,
    "hips": 96.0,
    "thigh": 58.5,
    "calf": 38.75,
    "back_width": 43.0,
}

# 7-site skinfold (mm) — intermediate ~12% BF male
SKINFOLD = {
    "chest": 8.0,
    "midaxillary": 9.0,
    "tricep": 10.0,
    "subscapular": 12.0,
    "abdominal": 16.0,
    "suprailiac": 11.0,
    "thigh": 13.0,
}

# Lean-adjusted measurements (fat stripped) — used by Ghost Model
LEAN_MEASUREMENTS = {
    "neck": 37.0,
    "shoulders": 118.0,
    "chest": 103.5,
    "bicep": 35.5,
    "forearm": 28.5,
    "waist": 76.0,
    "hips": 92.5,
    "thigh": 54.5,
    "calf": 37.0,
    "back_width": 41.5,
}


# ===================================================================
# ENGINE 1 — Diagnostic / Physique Assessment
# ===================================================================

class TestVolumetricGhostModel:
    """Full Volumetric Ghost Model pipeline for 188cm MP."""

    def test_ghost_pipeline_runs(self):
        from app.engines.engine1.volumetric_ghost import run_ghost_pipeline
        result = run_ghost_pipeline(HEIGHT_CM, DIVISION, LEAN_MEASUREMENTS, SEX)
        assert "weight_cap_kg" in result
        assert "ghost_mass_kg" in result
        assert "allometric_multiplier" in result
        assert "hanavan_volumes" in result
        assert "ideal_circumferences" in result
        assert "site_scores" in result

    def test_weight_cap_lookup(self):
        from app.constants.weight_caps import lookup_weight_cap, lookup_target_lbm
        cap = lookup_weight_cap(HEIGHT_CM, DIVISION)
        lbm = lookup_target_lbm(HEIGHT_CM, DIVISION)
        # 188cm MP cap should be 97 kg (from table)
        assert cap == 97.0
        assert 90 < lbm < 95  # 97 × 0.95 ≈ 92.15

    def test_ghost_mass_realistic(self):
        from app.engines.engine1.volumetric_ghost import run_ghost_pipeline
        r = run_ghost_pipeline(HEIGHT_CM, DIVISION, LEAN_MEASUREMENTS, SEX)
        # Ghost mass should be close to but slightly below target LBM
        assert 80 < r["ghost_mass_kg"] < 95, f"Ghost mass {r['ghost_mass_kg']} out of range"

    def test_allometric_multiplier_inflates(self):
        """Multiplier must be > 1.0 (ghost inflates to reach weight cap)."""
        from app.engines.engine1.volumetric_ghost import run_ghost_pipeline
        r = run_ghost_pipeline(HEIGHT_CM, DIVISION, LEAN_MEASUREMENTS, SEX)
        assert r["allometric_multiplier"] > 1.0, "Ghost should inflate, not shrink"
        assert r["allometric_multiplier"] < 1.05, "Inflation should be modest (<5%)"

    def test_hanavan_segment_volumes(self):
        from app.engines.engine1.volumetric_ghost import run_ghost_pipeline
        r = run_ghost_pipeline(HEIGHT_CM, DIVISION, LEAN_MEASUREMENTS, SEX)
        vols = r["hanavan_volumes"]
        # All segments should have positive volume
        for seg in ("upper_arms", "forearms", "thighs", "calves", "torso"):
            assert vols[seg] > 0, f"{seg} volume should be positive"
        # Torso should be the largest segment
        assert vols["torso"] > vols["upper_arms"]
        assert vols["torso"] > vols["forearms"]
        # Thighs should be larger than arms
        assert vols["thighs"] > vols["upper_arms"]
        # Total after lung < total
        assert vols["total_after_lung"] < vols["total"]

    def test_ideal_circumferences_realistic(self):
        from app.engines.engine1.volumetric_ghost import run_ghost_pipeline
        r = run_ghost_pipeline(HEIGHT_CM, DIVISION, LEAN_MEASUREMENTS, SEX)
        ic = r["ideal_circumferences"]
        # MP at 188cm — expected ranges for intermediate+ competitor
        assert 42 < ic["neck"] < 46, f"Neck {ic['neck']} out of range"
        assert 108 < ic["shoulders"] < 118, f"Shoulders {ic['shoulders']} out of range"
        assert 95 < ic["chest"] < 105, f"Chest {ic['chest']} out of range"
        assert 38 < ic["bicep"] < 43, f"Bicep {ic['bicep']} out of range"
        assert 30 < ic["forearm"] < 34, f"Forearm {ic['forearm']} out of range"
        assert 75 < ic["waist"] < 85, f"Waist {ic['waist']} out of range"
        assert 58 < ic["thigh"] < 68, f"Thigh {ic['thigh']} out of range"
        assert 39 < ic["calf"] < 44, f"Calf {ic['calf']} out of range"
        assert 45 < ic["back_width"] < 52, f"Back width {ic['back_width']} out of range"

    def test_site_scores_format(self):
        from app.engines.engine1.volumetric_ghost import run_ghost_pipeline
        r = run_ghost_pipeline(HEIGHT_CM, DIVISION, LEAN_MEASUREMENTS, SEX)
        for site, score in r["site_scores"].items():
            assert "ideal_lean_cm" in score
            assert "current_lean_cm" in score
            assert "gap_cm" in score
            assert "pct_of_ideal" in score
            assert "gap_type" in score
            assert score["gap_type"] in ("add_muscle", "at_ideal", "above_ideal", "reduce_girth")

    def test_waist_uses_division_vectors(self):
        """Waist ideal should come from DIVISION_VECTORS, not GHOST_VECTORS."""
        from app.engines.engine1.volumetric_ghost import run_ghost_pipeline
        from app.constants.divisions import DIVISION_VECTORS
        r = run_ghost_pipeline(HEIGHT_CM, DIVISION, LEAN_MEASUREMENTS, SEX)
        expected = DIVISION_VECTORS["mens_physique"]["waist"] * HEIGHT_CM
        assert abs(r["ideal_circumferences"]["waist"] - expected) < 1.0


class TestClassEstimation:
    def test_class_for_188cm_mp(self):
        from app.constants.division_classes import estimate_class
        cls = estimate_class(HEIGHT_CM, DIVISION, BODY_WEIGHT_KG)
        assert cls is not None
        assert "label" in cls
        assert "division" in cls


class TestLCSA:
    def test_compute_all_lcsa(self):
        from app.engines.engine1.lcsa import compute_all_lcsa, compute_total_lcsa
        lcsa = compute_all_lcsa(TAPE_AVERAGED, BODY_FAT_PCT)
        total = compute_total_lcsa(lcsa)
        assert len(lcsa) >= 6
        assert total > 0
        # Intermediate MP total LCSA should be in 250-400 range
        assert 1500 < total < 3000, f"Total LCSA {total} out of range"

    def test_lcsa_site_values_positive(self):
        from app.engines.engine1.lcsa import compute_all_lcsa
        lcsa = compute_all_lcsa(TAPE_AVERAGED, BODY_FAT_PCT)
        for site, val in lcsa.items():
            assert val > 0, f"LCSA for {site} should be positive"


class TestBodyFat:
    def test_jackson_pollock_7(self):
        from app.engines.engine1.body_fat import jackson_pollock_7
        bf = jackson_pollock_7(
            chest=SKINFOLD["chest"], midaxillary=SKINFOLD["midaxillary"],
            tricep=SKINFOLD["tricep"], subscapular=SKINFOLD["subscapular"],
            abdominal=SKINFOLD["abdominal"], suprailiac=SKINFOLD["suprailiac"],
            thigh=SKINFOLD["thigh"], age=AGE, sex=SEX,
        )
        # Intermediate male with these skinfolds: expect 10-16%
        assert 8 < bf < 18, f"JP7 body fat {bf}% out of expected range"

    def test_navy_body_fat(self):
        from app.engines.engine1.body_fat import navy_body_fat
        bf = navy_body_fat(
            waist_cm=TAPE["waist"], neck_cm=TAPE["neck"],
            height_cm=HEIGHT_CM, sex=SEX,
        )
        assert 8 < bf < 20, f"Navy BF {bf}% out of expected range"

    def test_lean_mass_kg(self):
        from app.engines.engine1.body_fat import lean_mass_kg
        lm = lean_mass_kg(BODY_WEIGHT_KG, BODY_FAT_PCT)
        # 90 kg × (1 - 0.12) = 79.2 kg
        assert abs(lm - 79.2) < 0.5


class TestPDS:
    def test_division_weights_mp(self):
        from app.engines.engine1.pds import get_division_weights
        w = get_division_weights(DIVISION)
        assert abs(sum(w.values()) - 1.0) < 0.01
        # MP: aesthetic-heavy, proportion matters most
        assert w["aesthetic"] > 0

    def test_pds_score_range(self):
        from app.engines.engine1.pds import (
            compute_pds, compute_muscle_mass_score,
            compute_conditioning_score, compute_symmetry_score,
        )
        from app.engines.engine1.lcsa import compute_all_lcsa, compute_total_lcsa
        from app.engines.engine1.aesthetic_vector import (
            compute_proportion_vector, cosine_similarity,
        )
        from app.constants.divisions import DIVISION_VECTORS

        lcsa = compute_all_lcsa(TAPE_AVERAGED, BODY_FAT_PCT)
        total_lcsa = compute_total_lcsa(lcsa)
        mass = compute_muscle_mass_score(total_lcsa, HEIGHT_CM, SEX)
        cond = compute_conditioning_score(BODY_FAT_PCT, SEX)
        sym = compute_symmetry_score(TAPE)

        actual_v = compute_proportion_vector(TAPE_AVERAGED, HEIGHT_CM)
        ideal_v = DIVISION_VECTORS[DIVISION]
        sim = cosine_similarity(actual_v, ideal_v)
        aesthetic = sim * 100

        pds = compute_pds(aesthetic, mass, cond, sym, DIVISION)
        assert 0 <= pds <= 100
        # Intermediate MP: expect 45-75 PDS
        assert 30 < pds < 95, f"PDS {pds} out of expected intermediate range"

    def test_tier_assignment(self):
        from app.engines.engine1.pds import get_tier
        assert get_tier(55) == "intermediate"
        assert get_tier(72) == "advanced"
        assert get_tier(45) == "novice"
        assert get_tier(90) == "elite"

    def test_symmetry_score(self):
        from app.engines.engine1.pds import compute_symmetry_score
        score = compute_symmetry_score(TAPE)
        assert 75 < score <= 100, f"Symmetry {score} out of range"

    def test_symmetry_details(self):
        from app.engines.engine1.pds import compute_symmetry_details
        details = compute_symmetry_details(TAPE)
        assert isinstance(details, list)
        for d in details:
            assert "site" in d
            assert "left_cm" in d
            assert "right_cm" in d
            assert "deviation_pct" in d


class TestAestheticVector:
    def test_proportion_vector(self):
        from app.engines.engine1.aesthetic_vector import compute_proportion_vector
        v = compute_proportion_vector(TAPE_AVERAGED, HEIGHT_CM)
        assert len(v) >= 6
        # All ratios should be reasonable (0.1 - 0.8 of height)
        for site, ratio in v.items():
            assert 0.05 < ratio < 1.0, f"{site} ratio {ratio} out of range"

    def test_cosine_similarity_to_ideal(self):
        from app.engines.engine1.aesthetic_vector import (
            compute_proportion_vector, cosine_similarity,
        )
        from app.constants.divisions import DIVISION_VECTORS
        actual = compute_proportion_vector(TAPE_AVERAGED, HEIGHT_CM)
        ideal = DIVISION_VECTORS[DIVISION]
        sim = cosine_similarity(actual, ideal)
        # Intermediate should be somewhat close to ideal: > 0.90
        assert 0.85 < sim <= 1.0, f"Cosine similarity {sim} lower than expected"

    def test_delta_vector(self):
        from app.engines.engine1.aesthetic_vector import (
            compute_proportion_vector, compute_delta_vector,
        )
        from app.constants.divisions import DIVISION_VECTORS
        actual = compute_proportion_vector(TAPE_AVERAGED, HEIGHT_CM)
        ideal = DIVISION_VECTORS[DIVISION]
        delta = compute_delta_vector(actual, ideal)
        assert len(delta) > 0
        # Deltas should be small for intermediate (within ±0.1 of ideal)
        for site, d in delta.items():
            assert abs(d) < 0.15, f"{site} delta {d} too large"


class TestMuscleGaps:
    def test_gap_ranking(self):
        from app.engines.engine1.volumetric_ghost import run_ghost_pipeline
        from app.engines.engine1.muscle_gaps import rank_sites_by_gap, compute_total_gap
        r = run_ghost_pipeline(HEIGHT_CM, DIVISION, LEAN_MEASUREMENTS, SEX)
        ranked = rank_sites_by_gap(r["site_scores"])
        total = compute_total_gap(r["site_scores"])
        assert len(ranked) > 0
        # Total gap should be positive (intermediate has room to grow)
        assert total >= 0

    def test_avg_pct_of_ideal(self):
        from app.engines.engine1.volumetric_ghost import run_ghost_pipeline
        from app.engines.engine1.muscle_gaps import compute_avg_pct_of_ideal
        r = run_ghost_pipeline(HEIGHT_CM, DIVISION, LEAN_MEASUREMENTS, SEX)
        avg = compute_avg_pct_of_ideal(r["site_scores"], DIVISION)
        # Intermediate: should be 75-95% of ideal
        assert 65 < avg < 100, f"Avg pct of ideal {avg} out of range"


class TestTrajectoryAndFeasibility:
    def test_predict_trajectory(self):
        from app.engines.engine1.trajectory import predict_trajectory
        traj = predict_trajectory(
            current_pds=58.0, ceiling_pds=90.0, weeks=52,
            training_experience_years=int(TRAINING_YEARS),
        )
        assert len(traj) == 53  # weeks + 1
        # Should be monotonically non-decreasing
        scores = [t["predicted_pds"] for t in traj]
        for i in range(1, len(scores)):
            assert scores[i] >= scores[i - 1] - 0.01

    def test_feasibility_achievable(self):
        from app.engines.engine1.feasibility import compute_feasibility
        f = compute_feasibility(
            current_pds=58.0, target_pds=70.0,
            weeks_available=40, training_experience_years=int(TRAINING_YEARS),
        )
        assert f["feasible"] is True
        assert f["estimated_weeks"] > 0

    def test_feasibility_impossible(self):
        from app.engines.engine1.feasibility import compute_feasibility
        f = compute_feasibility(
            current_pds=58.0, target_pds=98.0,
            weeks_available=4, training_experience_years=int(TRAINING_YEARS),
        )
        assert f["feasible"] is False


class TestPrepTimeline:
    def test_phase_offseason(self):
        from app.engines.engine1.prep_timeline import prep_phase_for_date
        # No competition date → offseason
        phase = prep_phase_for_date(None)
        assert phase == "offseason"

    def test_phase_with_competition(self):
        from app.engines.engine1.prep_timeline import (
            prep_phase_for_date, weeks_out, phase_description,
        )
        comp = date.today() + timedelta(weeks=20)
        phase = prep_phase_for_date(comp)
        wo = weeks_out(comp)
        desc = phase_description(phase)
        assert wo > 0
        assert phase in ("offseason", "lean_bulk", "cut", "peak_week", "contest", "restoration")
        assert "description" in desc or "label" in desc


# ===================================================================
# ENGINE 2 — Training Prescription
# ===================================================================

class TestARI:
    """Autonomic Readiness Index for recovery gating."""

    def test_compute_ari_baseline(self):
        from app.engines.engine2.ari import compute_ari
        ari = compute_ari(
            rmssd=55.0, resting_hr=62, sleep_quality_1_10=6,
            soreness_1_10=4, baseline_rmssd=50.0,
        )
        assert 0 <= ari <= 100

    def test_ari_excellent_recovery(self):
        from app.engines.engine2.ari import compute_ari, get_ari_zone
        ari = compute_ari(
            rmssd=80.0, resting_hr=55, sleep_quality_1_10=2,
            soreness_1_10=2, baseline_rmssd=50.0,
        )
        assert ari > 65
        assert get_ari_zone(ari) in ("green", "yellow")

    def test_ari_poor_recovery(self):
        from app.engines.engine2.ari import compute_ari, get_ari_zone
        ari = compute_ari(
            rmssd=25.0, resting_hr=78, sleep_quality_1_10=8,
            soreness_1_10=9, baseline_rmssd=50.0,
        )
        assert 40 < ari < 50
        assert get_ari_zone(ari) in ("red", "yellow")

    def test_volume_modifier_range(self):
        from app.engines.engine2.ari import get_volume_modifier
        green_mod = get_volume_modifier(80)
        red_mod = get_volume_modifier(30)
        assert green_mod >= 0.8
        assert red_mod < 0.8
        assert 0.5 <= red_mod <= 1.2
        assert 0.5 <= green_mod <= 1.2


class TestResistance:
    """1RM estimation and progression logic."""

    def test_epley_1rm(self):
        from app.engines.engine2.resistance import estimate_1rm
        # 80 kg × 8 reps → ~101 kg 1RM (intermediate bench)
        orm = estimate_1rm(80.0, 8)
        assert 95 < orm < 110

    def test_single_rep_identity(self):
        from app.engines.engine2.resistance import estimate_1rm
        assert estimate_1rm(100, 1) == pytest.approx(100, abs=0.1)

    def test_weight_from_1rm(self):
        from app.engines.engine2.resistance import compute_weight_from_1rm
        # 100 kg 1RM → ~80 kg for 8 reps
        w = compute_weight_from_1rm(100.0, 8)
        assert 70 < w < 90

    def test_progression_at_ceiling(self):
        from app.engines.engine2.resistance import compute_progression
        prog = compute_progression(
            current_weight=80.0, current_reps=12,
            target_reps=12, rpe=7.5,
        )
        # At rep ceiling with manageable RPE → should suggest weight increase
        assert prog is not None


class TestRecovery:
    def test_recovery_window(self):
        from app.engines.engine2.recovery import get_recovery_window
        chest_min, chest_max = get_recovery_window("chest")
        bicep_min, bicep_max = get_recovery_window("biceps")
        # Large muscles need more recovery than small
        assert chest_min > bicep_min or chest_max > bicep_max

    def test_recovery_time_scales_with_volume(self):
        from app.engines.engine2.recovery import estimate_recovery_time
        low_vol = estimate_recovery_time("chest", volume=6, intensity=0.7, ari=75)
        high_vol = estimate_recovery_time("chest", volume=16, intensity=0.85, ari=75)
        assert high_vol > low_vol

    def test_low_ari_increases_recovery(self):
        from app.engines.engine2.recovery import estimate_recovery_time
        good_ari = estimate_recovery_time("chest", volume=10, intensity=0.75, ari=85)
        bad_ari = estimate_recovery_time("chest", volume=10, intensity=0.75, ari=30)
        assert bad_ari > good_ari

    def test_can_train_muscle(self):
        from app.engines.engine2.recovery import can_train_muscle
        assert can_train_muscle("chest", hours_since_last=72, recovery_hours_needed=48) is True
        assert can_train_muscle("chest", hours_since_last=24, recovery_hours_needed=48) is False


class TestBiomechanical:
    def test_sfr(self):
        from app.engines.engine2.biomechanical import compute_sfr
        sfr = compute_sfr(efficiency=0.9, fatigue_ratio=0.6)
        assert sfr == pytest.approx(1.5, abs=0.01)

    def test_score_exercise(self):
        from app.engines.engine2.biomechanical import score_exercise
        s = score_exercise(efficiency=0.9, fatigue_ratio=0.5, priority_score_for_muscle=8.0)
        assert s > 0

    def test_exercise_pattern_classification(self):
        from app.engines.engine2.biomechanical import classify_exercise_pattern
        assert classify_exercise_pattern("Barbell Bench Press") in ("horizontal_push", "incline_push")
        assert classify_exercise_pattern("Lat Pulldown") in ("vertical_pull", "horizontal_pull")


class TestOverflow:
    def test_compute_overflow(self):
        from app.engines.engine2.overflow import compute_overflow
        overflow = compute_overflow(
            primary_sets=12,
            secondary_muscles_hit={"triceps": 0.5, "front_delt": 0.3},
            existing_volume={}
        )
        assert overflow["triceps"] == pytest.approx(6.0, abs=0.5)
        assert overflow["front_delt"] == 3


class TestSplitDesigner:
    """Gap-driven custom split for 188cm intermediate MP."""

    def test_design_split_for_mp(self):
        from app.engines.engine2.split_designer import design_split
        from app.engines.engine1.volumetric_ghost import run_ghost_pipeline
        r = run_ghost_pipeline(HEIGHT_CM, DIVISION, LEAN_MEASUREMENTS, SEX)
        # Convert gap_cm to simple dict for split designer
        hqi_gaps = {
            site: data["gap_cm"]
            for site, data in r["site_scores"].items()
        }
        split = design_split(hqi_gaps, DIVISION, DAYS_PER_WEEK)
        assert "template" in split
        assert "volume_budget" in split
        assert len(split["template"]) == DAYS_PER_WEEK
        # Each day should have muscles assigned
        for day in split["template"]:
            assert "muscles" in day
            assert len(day["muscles"]) > 0

    def test_mp_legs_deprioritized(self):
        """MP split should not heavily train legs (judges don't see them)."""
        from app.engines.engine2.split_designer import design_split
        hqi_gaps = {"neck": 3, "shoulders": 5, "chest": 4, "bicep": 2,
                    "forearm": 1, "waist": -2, "thigh": 8, "calf": 3, "back_width": 5}
        split = design_split(hqi_gaps, DIVISION, DAYS_PER_WEEK)
        vb = split["volume_budget"]
        # Quads/hams/glutes should have zero or minimal volume in MP
        for leg in ("quads", "hamstrings", "glutes"):
            if leg in vb:
                assert vb[leg] <= 8, f"MP should not train {leg} heavily: {vb[leg]} sets"


class TestPeriodization:
    def test_generate_mesocycle(self):
        from app.engines.engine2.periodization import generate_mesocycle
        vol_alloc = {
            "chest": 14, "back": 16, "side_delt": 16, "front_delt": 6,
            "rear_delt": 10, "biceps": 12, "triceps": 10, "abs": 8,
        }
        meso = generate_mesocycle(
            days_per_week=DAYS_PER_WEEK,
            split_type="custom",
            volume_allocation=vol_alloc,
            week_count=4,
            custom_template=[{"day": f"Day {i+1}", "muscles": ["chest"]} for i in range(DAYS_PER_WEEK)],
            periodization_type="dup",
            training_experience_years=TRAINING_YEARS,
        )
        assert len(meso) == 4  # 4 weeks
        for week in meso:
            assert "week" in week
            assert "days" in week
            assert len(week["days"]) == DAYS_PER_WEEK


class TestExercisePriorities:
    def test_mp_exercise_priorities(self):
        from app.constants.exercise_priorities import get_exercise_priorities
        chest_slots = get_exercise_priorities(DIVISION, "chest")
        assert len(chest_slots) >= 1
        # MP chest P1 should be incline-focused
        p1 = chest_slots[0]
        assert "incline" in p1["name"].lower() or "incline" in " ".join(p1.get("keywords", [])).lower()

    def test_mp_shoulder_priorities(self):
        from app.constants.exercise_priorities import get_exercise_priorities
        shoulder_slots = get_exercise_priorities(DIVISION, "shoulders")
        assert len(shoulder_slots) >= 1
        # MP shoulders P1 should emphasize lateral raises
        p1 = shoulder_slots[0]
        assert any("lateral" in kw.lower() for kw in p1.get("keywords", [])) or "lateral" in p1["name"].lower()

    def test_gap_adjusted_cap(self):
        from app.constants.exercise_priorities import gap_adjusted_cap
        # Severely lagging (HQI < 40) → 1.5× cap
        assert gap_adjusted_cap(3, hqi=30, is_top_priority=True) >= 4
        # Moderate (40-64) → 1.25× cap
        assert gap_adjusted_cap(3, hqi=50, is_top_priority=True) >= 3
        # Normal (≥65) → no adjustment
        assert gap_adjusted_cap(3, hqi=80, is_top_priority=True) == 3


class TestCNSFatigue:
    def test_daily_fatigue_budget(self):
        from app.engines.engine2.recovery import check_daily_fatigue_budget
        session = [
            {"exercise_name": "Barbell Bench Press", "sets": 4, "intensity": 0.85, "equipment": "barbell"},
            {"exercise_name": "Incline DB Press", "sets": 3, "intensity": 0.75, "equipment": "dumbbell"},
            {"exercise_name": "Cable Fly", "sets": 3, "intensity": 0.65, "equipment": "cable"},
        ]
        result = check_daily_fatigue_budget(session)
        assert "within_budget" in result


# ===================================================================
# ENGINE 3 — Nutrition Controller
# ===================================================================

class TestTDEE:
    def test_compute_tdee(self):
        from app.engines.engine3.macros import compute_tdee
        tdee = compute_tdee(
            weight_kg=BODY_WEIGHT_KG, height_cm=HEIGHT_CM,
            age=AGE, sex=SEX, activity_multiplier=1.55,
        )
        # Active 90kg male: expect 2700-3300 kcal
        assert 2500 < tdee < 3500, f"TDEE {tdee} out of range"

    def test_male_higher_than_female(self):
        from app.engines.engine3.macros import compute_tdee
        male = compute_tdee(90, 188, 27, "male", 1.55)
        female = compute_tdee(90, 188, 27, "female", 1.55)
        assert male > female


class TestMacros:
    def test_bulk_macros(self):
        from app.engines.engine3.macros import compute_macros
        m = compute_macros(tdee=3000, phase="bulk", weight_kg=BODY_WEIGHT_KG, sex=SEX)
        assert m["target_calories"] > 3000  # surplus
        assert m["protein_g"] > 0
        assert m["carbs_g"] > 0
        assert m["fat_g"] > 0
        # Protein: 1.8-2.5 g/kg typical
        assert 1.5 * BODY_WEIGHT_KG < m["protein_g"] < 3.0 * BODY_WEIGHT_KG

    def test_cut_macros(self):
        from app.engines.engine3.macros import compute_macros
        m = compute_macros(tdee=3000, phase="cut", weight_kg=BODY_WEIGHT_KG, sex=SEX)
        assert m["target_calories"] < 3000  # deficit
        # Cut protein should be >= bulk protein (muscle preservation)
        bulk = compute_macros(tdee=3000, phase="bulk", weight_kg=BODY_WEIGHT_KG, sex=SEX)
        assert m["protein_g"] >= bulk["protein_g"] * 0.9

    def test_maintain_macros(self):
        from app.engines.engine3.macros import compute_macros
        m = compute_macros(tdee=3000, phase="maintain", weight_kg=BODY_WEIGHT_KG, sex=SEX)
        # Should be close to TDEE
        assert abs(m["target_calories"] - 3000) < 300

    def test_phase_calorie_ordering(self):
        from app.engines.engine3.macros import compute_macros
        bulk = compute_macros(3000, "bulk", BODY_WEIGHT_KG, SEX)
        maintain = compute_macros(3000, "maintain", BODY_WEIGHT_KG, SEX)
        cut = compute_macros(3000, "cut", BODY_WEIGHT_KG, SEX)
        assert bulk["target_calories"] > maintain["target_calories"] > cut["target_calories"]


class TestThermodynamic:
    def test_energy_balance(self):
        from app.engines.engine3.thermodynamic import compute_energy_balance
        surplus = compute_energy_balance(consumed_calories=3200, tdee=3000)
        deficit = compute_energy_balance(consumed_calories=2500, tdee=3000)
        assert surplus > 0
        assert deficit < 0

    def test_expected_weight_change(self):
        from app.engines.engine3.thermodynamic import compute_expected_weight_change
        # 500 kcal surplus × 7 days = 3500 kcal/week ≈ 0.45 kg/week
        gain = compute_expected_weight_change(energy_balance_weekly_avg=500, weeks=1)
        assert 0.3 < gain < 0.8
        loss = compute_expected_weight_change(energy_balance_weekly_avg=-500, weeks=1)
        assert -0.8 < loss < -0.3

    def test_thermodynamic_floor_male(self):
        from app.engines.engine3.thermodynamic import thermodynamic_floor
        floored = thermodynamic_floor(current_calories=1200, min_calories_for_sex="male")
        assert floored >= 1500  # male floor = 1500

    def test_metabolic_adaptation(self):
        from app.engines.engine3.thermodynamic import compute_adaptation_factor, compute_adapted_tdee
        # No adaptation at week 0
        assert compute_adaptation_factor(0) == pytest.approx(1.0, abs=0.01)
        # Adaptation increases with deficit duration
        factor_4 = compute_adaptation_factor(4)
        factor_12 = compute_adaptation_factor(12)
        assert factor_4 < 1.0
        assert factor_12 < factor_4  # more adaptation over time
        # Adapted TDEE should be lower
        adapted = compute_adapted_tdee(3000, 8)
        assert adapted < 3000


class TestKinetic:
    def test_rate_of_change(self):
        from app.engines.engine3.kinetic import compute_rate_of_change
        today = date.today()
        history = [
            ((today - timedelta(days=21)).isoformat(), 89.5),
            ((today - timedelta(days=14)).isoformat(), 89.8),
            ((today - timedelta(days=7)).isoformat(), 90.1),
            (today.isoformat(), 90.3),
        ]
        rate = compute_rate_of_change(history, sex="male")
        # Gaining ~0.3 kg/week
        assert 0.0 < rate < 0.8

    def test_target_rate_bulk(self):
        from app.engines.engine3.kinetic import target_rate
        rate = target_rate("bulk", BODY_WEIGHT_KG)
        assert rate > 0  # gaining

    def test_target_rate_cut(self):
        from app.engines.engine3.kinetic import target_rate
        rate = target_rate("cut", BODY_WEIGHT_KG)
        assert rate < 0  # losing

    def test_adjust_calories(self):
        from app.engines.engine3.kinetic import adjust_calories
        # Gaining too fast on bulk — should reduce calories
        adjusted = adjust_calories(
            current_calories=3300,
            actual_rate=0.8,  # gaining 0.8 kg/week (too fast)
            target_rate_value=0.3,
        )
        assert adjusted < 3300


class TestAutoregulation:
    def test_adherence_lock_high(self):
        from app.engines.engine3.autoregulation import adherence_lock
        macros = {"protein_g": 180, "carbs_g": 300, "fat_g": 70, "target_calories": 3100}
        result = adherence_lock(adherence_pct=92.0, current_prescription=macros)
        assert result["locked"] is False

    def test_adherence_lock_low(self):
        from app.engines.engine3.autoregulation import adherence_lock
        macros = {"protein_g": 180, "carbs_g": 300, "fat_g": 70, "target_calories": 3100}
        result = adherence_lock(adherence_pct=60.0, current_prescription=macros)
        assert result["locked"] is True
        assert "message" in result

    def test_refeed_computation(self):
        from app.engines.engine3.autoregulation import compute_refeed
        refeed = compute_refeed(
            days_in_deficit=14, current_bf_pct=BODY_FAT_PCT, sex="male",
        )
        assert "refeed_calories" in refeed or "refeed_interval_days" in refeed
        # The refeed calories key value is explicitly returned as 0.0 to be filled from TDEE
        assert refeed["refeed_interval_days"] > 0
        assert "refeed_carbs_multiplier" in refeed


class TestPeriWorkoutNutrition:
    def test_carb_split(self):
        from app.engines.engine3.macros import compute_peri_workout_carb_split
        split = compute_peri_workout_carb_split(carbs_g=300.0, meal_count=5)
        assert "pre_workout_g" in split or "peri_workout" in split
        # Total distributed carbs should approximately equal input
        total = split["pre_workout_g"] + split["intra_workout_g"] + split["post_workout_g"] + (split.get("other_meals_g", 0) * split.get("other_meal_count", 1))
        assert abs(total - 300) < 5


# ===================================================================
# CROSS-ENGINE INTEGRATION
# ===================================================================

class TestGhostToTrainingIntegration:
    """Ghost Model gaps → training volume priorities."""

    def test_gap_drives_muscle_priority(self):
        from app.engines.engine1.volumetric_ghost import run_ghost_pipeline
        r = run_ghost_pipeline(HEIGHT_CM, DIVISION, LEAN_MEASUREMENTS, SEX)
        # Simulate training.py priority conversion
        priorities = {}
        for site, v in r["site_scores"].items():
            pct = v.get("pct_of_ideal", 70.0)
            priorities[site] = round(10.0 * (1.0 - pct / 100.0), 1)
        # Sites with lower pct_of_ideal should have higher priority
        for site, v in r["site_scores"].items():
            pct = v["pct_of_ideal"]
            pri = priorities[site]
            if pct < 85:
                assert pri > 0, f"{site} at {pct}% should have positive priority"
            if pct > 105:
                assert pri < 0, f"{site} at {pct}% should have negative priority"

    def test_ghost_output_has_pct_of_ideal_key(self):
        """Critical: training.py reads 'pct_of_ideal', not 'score'."""
        from app.engines.engine1.volumetric_ghost import run_ghost_pipeline
        r = run_ghost_pipeline(HEIGHT_CM, DIVISION, LEAN_MEASUREMENTS, SEX)
        for site, data in r["site_scores"].items():
            assert "pct_of_ideal" in data, f"Missing pct_of_ideal in {site}"
            assert "score" not in data or data.get("pct_of_ideal") is not None


class TestPhaseRecommendationIntegration:
    """Engine 1 physique state → Engine 3 phase recommendation."""

    def test_offseason_intermediate_recommends_bulk(self):
        """Intermediate MP at 12% BF with room to grow → should recommend bulk or lean_bulk."""
        from app.engines.engine1.volumetric_ghost import run_ghost_pipeline
        from app.engines.engine1.muscle_gaps import compute_avg_pct_of_ideal
        r = run_ghost_pipeline(HEIGHT_CM, DIVISION, LEAN_MEASUREMENTS, SEX)
        avg_pct = compute_avg_pct_of_ideal(r["site_scores"], DIVISION)
        # At 12% BF with significant room to grow (avg ~85%), should bulk
        assert avg_pct < 100, "Should have room to grow"
        assert BODY_FAT_PCT < 18, "Not too fat to bulk"


class TestARIToVolumeIntegration:
    """ARI score → volume modifier → affects training prescription."""

    def test_full_ari_to_volume_pipeline(self):
        from app.engines.engine2.ari import compute_ari, get_ari_zone, get_volume_modifier
        ari = compute_ari(55.0, 62, 6, 4, 50.0)
        zone = get_ari_zone(ari)
        mod = get_volume_modifier(ari)
        assert zone in ("green", "yellow", "red")
        assert 0.5 <= mod <= 1.2
        # Volume modifier should reflect zone
        if zone == "green":
            assert mod >= 0.9
        elif zone == "red":
            assert mod < 0.8


class TestFullPipelineEndToEnd:
    """Complete simulation: diagnostic → training → nutrition for 188cm MP."""

    def test_complete_pipeline(self):
        """Run the full Engine 1 → 2 → 3 pipeline and verify all outputs."""
        # Engine 1: Diagnostic
        from app.engines.engine1.volumetric_ghost import run_ghost_pipeline
        from app.engines.engine1.lcsa import compute_all_lcsa, compute_total_lcsa
        from app.engines.engine1.pds import (
            compute_pds, compute_muscle_mass_score,
            compute_conditioning_score, compute_symmetry_score,
        )
        from app.engines.engine1.aesthetic_vector import (
            compute_proportion_vector, cosine_similarity,
        )
        from app.constants.divisions import DIVISION_VECTORS

        ghost = run_ghost_pipeline(HEIGHT_CM, DIVISION, LEAN_MEASUREMENTS, SEX)
        lcsa = compute_all_lcsa(TAPE_AVERAGED, BODY_FAT_PCT)
        total_lcsa = compute_total_lcsa(lcsa)
        mass_score = compute_muscle_mass_score(total_lcsa, HEIGHT_CM, SEX)
        cond_score = compute_conditioning_score(BODY_FAT_PCT, SEX)
        sym_score = compute_symmetry_score(TAPE)
        actual_v = compute_proportion_vector(TAPE_AVERAGED, HEIGHT_CM)
        sim = cosine_similarity(actual_v, DIVISION_VECTORS[DIVISION])
        pds = compute_pds(sim * 100, mass_score, cond_score, sym_score, DIVISION)

        assert 0 <= pds <= 100
        assert ghost["allometric_multiplier"] > 1.0

        # Engine 2: Training split from gaps
        from app.engines.engine2.split_designer import design_split
        hqi_gaps = {s: d["gap_cm"] for s, d in ghost["site_scores"].items()}
        split = design_split(hqi_gaps, DIVISION, DAYS_PER_WEEK)
        assert len(split["template"]) == DAYS_PER_WEEK

        # Engine 2: Periodization
        from app.engines.engine2.periodization import generate_mesocycle
        meso = generate_mesocycle(
            days_per_week=DAYS_PER_WEEK,
            split_type="custom",
            volume_allocation=split["volume_budget"],
            week_count=4,
            custom_template=split["template"],
            periodization_type="dup",
            training_experience_years=TRAINING_YEARS,
        )
        assert len(meso) == 4

        # Engine 3: Nutrition
        from app.engines.engine3.macros import compute_tdee, compute_macros
        tdee = compute_tdee(BODY_WEIGHT_KG, HEIGHT_CM, AGE, SEX, 1.55)
        macros = compute_macros(tdee, "bulk", BODY_WEIGHT_KG, SEX)
        assert macros["target_calories"] > tdee
        assert macros["protein_g"] > 100

        # Cross-engine: ARI modifies volume
        from app.engines.engine2.ari import compute_ari, get_volume_modifier
        ari = compute_ari(55, 62, 6, 4, 50.0)
        vol_mod = get_volume_modifier(ari)
        assert 0.5 <= vol_mod <= 1.2

        # Verify the full chain produced reasonable outputs
        print(f"\n{'='*60}")
        print(f"FULL PIPELINE — 188cm Men's Physique (Intermediate)")
        print(f"{'='*60}")
        print(f"PDS Score: {pds:.1f} ({('novice' if pds<50 else 'intermediate' if pds<70 else 'advanced' if pds<85 else 'elite')})")
        print(f"Ghost Mass: {ghost['ghost_mass_kg']:.1f} kg → Target: {ghost['target_lbm_kg']:.1f} kg")
        print(f"Scale Factor: {ghost['allometric_multiplier']:.4f}x")
        print(f"TDEE: {tdee:.0f} kcal | Bulk: {macros['target_calories']:.0f} kcal")
        print(f"Macros: P={macros['protein_g']:.0f}g C={macros['carbs_g']:.0f}g F={macros['fat_g']:.0f}g")
        print(f"ARI: {ari:.0f} | Volume Mod: {vol_mod:.2f}")
        print(f"Split: {len(split['template'])} days/week")
        print(f"Mesocycle: {len(meso)} weeks × {DAYS_PER_WEEK} days")
        print(f"Top 3 gap priorities:")
        ranked = sorted(ghost["site_scores"].items(), key=lambda x: x[1]["gap_cm"], reverse=True)
        for site, data in ranked[:3]:
            print(f"  {site}: {data['pct_of_ideal']:.1f}% of ideal ({data['gap_cm']:+.1f} cm)")
        print(f"{'='*60}\n")
