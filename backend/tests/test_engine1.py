"""Unit tests for Engine 1 — Diagnostic pure functions."""
import pytest
from app.engines.engine1.lcsa import compute_lcsa_site, compute_all_lcsa, compute_total_lcsa
from app.engines.engine1.hqi import compute_hqi_site, compute_all_hqi, compute_overall_hqi, compute_ideal_circumferences
from app.engines.engine1.weight_cap import compute_max_circumferences
from app.engines.engine1.pds import (
    compute_pds, compute_muscle_mass_score, compute_conditioning_score,
    compute_symmetry_score, get_tier,
)
from app.engines.engine1.aesthetic_vector import (
    compute_proportion_vector, compute_delta_vector, cosine_similarity,
)
from app.engines.engine1.weight_cap import compute_weight_cap
from app.engines.engine1.trajectory import predict_trajectory, compute_goal_weeks
from app.engines.engine1.feasibility import compute_feasibility


class TestLCSA:
    def test_compute_lcsa_site(self):
        # 40cm circumference, k=0.90, 10% body fat
        result = compute_lcsa_site(40.0, 0.90, 0.10)
        assert result > 0
        assert isinstance(result, float)

    def test_compute_all_lcsa(self):
        tape = {"neck": 40, "chest": 100, "left_bicep": 38, "right_bicep": 39, "waist": 82}
        result = compute_all_lcsa(tape, 12.0)
        assert "neck" in result
        assert "chest" in result
        assert "bicep" in result  # averaged bilateral
        assert "waist" in result
        assert all(v > 0 for v in result.values())

    def test_default_body_fat(self):
        tape = {"chest": 100}
        result_default = compute_all_lcsa(tape)
        result_explicit = compute_all_lcsa(tape, 15.0)
        assert result_default == result_explicit


class TestHQI:
    def test_perfect_score(self):
        result = compute_hqi_site(lean_circ_cm=100.0, ideal_lean_cm=100.0, site="chest")
        assert result["score"] == 100.0

    def test_at_ideal(self):
        result = compute_hqi_site(lean_circ_cm=45.0, ideal_lean_cm=45.0, site="bicep")
        assert result["score"] == 100.0
        assert result["gap_cm"] == 0.0

    def test_underdeveloped(self):
        result = compute_hqi_site(lean_circ_cm=35.0, ideal_lean_cm=45.0, site="bicep")
        assert result["score"] < 60
        assert result["gap_type"] == "add_muscle"

    def test_above_ideal(self):
        result = compute_hqi_site(lean_circ_cm=50.0, ideal_lean_cm=45.0, site="bicep")
        assert result["score"] == 100.0
        assert result["gap_type"] == "at_or_above_ideal"

    def test_waist_reduce_girth(self):
        result = compute_hqi_site(lean_circ_cm=85.0, ideal_lean_cm=78.0, site="waist")
        assert result["gap_type"] == "reduce_girth"

    def test_max_circumferences(self):
        max_circs = compute_max_circumferences(180.0, 17.8, 23.0, sex="male")
        assert "bicep" in max_circs
        assert "shoulders" in max_circs
        assert max_circs["bicep"] > 40  # reasonable genetic max
        assert max_circs["shoulders"] > max_circs["chest"]

    def test_ideal_circumferences(self):
        max_circs = compute_max_circumferences(180.0, 17.8, 23.0, sex="male")
        ceiling = {"bicep": 0.92, "forearm": 0.88, "chest": 0.90,
                    "neck": 0.88, "shoulders": 0.95, "thigh": 0.78, "calf": 0.80}
        div_vector = {"waist": 0.420, "hips": 0.490}
        ideals = compute_ideal_circumferences(max_circs, ceiling, div_vector, 180.0)
        assert ideals["bicep"] < max_circs["bicep"]  # ceiling < 1.0
        assert ideals["waist"] == round(0.420 * 180.0, 1)  # ratio × height

    def test_overall_hqi(self):
        scores = {"chest": {"score": 90}, "bicep": {"score": 80}, "thigh": {"score": 70}}
        overall = compute_overall_hqi(scores)
        assert overall == 80.0


class TestPDS:
    def test_compute_pds_range(self):
        score = compute_pds(80, 70, 60, 90)
        assert 0 <= score <= 100

    def test_weights_sum_to_one(self):
        # All components at 100 should give 100
        score = compute_pds(100, 100, 100, 100)
        assert score == 100.0

    def test_tier_boundaries(self):
        assert get_tier(90) == "elite"
        assert get_tier(75) == "advanced"
        assert get_tier(55) == "intermediate"
        assert get_tier(30) == "novice"

    def test_muscle_mass_score(self):
        score = compute_muscle_mass_score(40.0, 180.0, "male")
        assert 0 <= score <= 100

    def test_conditioning_score_at_target(self):
        # Male at 12% in offseason = ideal
        score = compute_conditioning_score(12.0, "male", "offseason")
        assert score == 100.0

    def test_conditioning_score_away_from_target(self):
        score = compute_conditioning_score(25.0, "male", "offseason")
        assert score < 100

    def test_symmetry_perfect(self):
        tape = {"left_bicep": 40, "right_bicep": 40, "left_thigh": 60, "right_thigh": 60}
        score = compute_symmetry_score(tape)
        assert score == 100.0

    def test_symmetry_asymmetric(self):
        tape = {"left_bicep": 40, "right_bicep": 35}
        score = compute_symmetry_score(tape)
        assert score < 100


class TestAestheticVector:
    def test_proportion_vector(self):
        tape = {"chest": 100, "waist": 80}
        vector = compute_proportion_vector(tape, 180.0)
        assert abs(vector["chest"] - 100 / 180) < 0.01

    def test_delta_vector(self):
        actual = {"chest": 0.55, "waist": 0.45}
        ideal = {"chest": 0.55, "waist": 0.44}
        delta = compute_delta_vector(actual, ideal)
        assert delta["chest"] == 0.0
        assert delta["waist"] < 0  # over-developed

    def test_cosine_similarity_identical(self):
        v = {"chest": 0.55, "bicep": 0.23}
        sim = cosine_similarity(v, v)
        assert abs(sim - 1.0) < 0.001


class TestWeightCap:
    def test_male_defaults(self):
        result = compute_weight_cap(180.0, sex="male")
        assert result["max_lbm_kg"] > 0
        assert result["stage_weight_kg"] > result["max_lbm_kg"]
        assert result["offseason_weight_kg"] > result["stage_weight_kg"]

    def test_female_lower_than_male(self):
        male = compute_weight_cap(170.0, sex="male")
        female = compute_weight_cap(170.0, sex="female")
        assert female["max_lbm_kg"] < male["max_lbm_kg"]

    def test_taller_higher_cap(self):
        short = compute_weight_cap(165.0, sex="male")
        tall = compute_weight_cap(190.0, sex="male")
        assert tall["max_lbm_kg"] > short["max_lbm_kg"]


class TestTrajectory:
    def test_trajectory_length(self):
        traj = predict_trajectory(50.0, 80.0, 12, 3)
        assert len(traj) == 13  # 0 through 12

    def test_trajectory_monotonic(self):
        traj = predict_trajectory(50.0, 80.0, 52, 3)
        scores = [t["predicted_pds"] for t in traj]
        assert all(scores[i] <= scores[i + 1] for i in range(len(scores) - 1))

    def test_goal_weeks_achievable(self):
        weeks = compute_goal_weeks(50.0, 70.0, 90.0, 3)
        assert weeks is not None
        assert weeks > 0

    def test_goal_weeks_impossible(self):
        weeks = compute_goal_weeks(50.0, 95.0, 90.0, 3)
        assert weeks is None


class TestFeasibility:
    def test_feasible_goal(self):
        result = compute_feasibility(50.0, 55.0, 20, 3)
        assert result["feasible"] is True

    def test_infeasible_goal(self):
        result = compute_feasibility(50.0, 90.0, 4, 10)
        assert result["feasible"] is False

    def test_already_achieved(self):
        result = compute_feasibility(70.0, 65.0, 10, 5)
        assert result["feasible"] is True
        assert result["estimated_weeks"] == 0
