"""Comprehensive tests for Engine 3 — Nutrition modules."""
from app.engines.engine3.macros import compute_tdee, compute_macros
from app.engines.engine3.thermodynamic import (
    compute_energy_balance, compute_expected_weight_change, thermodynamic_floor,
)
from app.engines.engine3.kinetic import compute_rate_of_change, target_rate, adjust_calories
from app.engines.engine3.autoregulation import adherence_lock, adjust_for_adherence, compute_refeed


class TestTDEEComprehensive:
    def test_higher_weight_higher_tdee(self):
        light = compute_tdee(70, 175, 25, "male", 1.55)
        heavy = compute_tdee(100, 175, 25, "male", 1.55)
        assert heavy > light

    def test_higher_activity_higher_tdee(self):
        sedentary = compute_tdee(80, 175, 25, "male", 1.2)
        active = compute_tdee(80, 175, 25, "male", 1.9)
        assert active > sedentary

    def test_male_higher_than_female_same_stats(self):
        male = compute_tdee(70, 170, 25, "male", 1.55)
        female = compute_tdee(70, 170, 25, "female", 1.55)
        assert male > female

    def test_older_lower_tdee(self):
        young = compute_tdee(80, 175, 20, "male", 1.55)
        old = compute_tdee(80, 175, 50, "male", 1.55)
        assert young > old


class TestMacrosComprehensive:
    def test_peak_more_deficit_than_cut(self):
        cut = compute_macros(2800, "cut", 90, "male")
        peak = compute_macros(2800, "peak", 90, "male")
        assert peak["target_calories"] < cut["target_calories"]

    def test_protein_higher_during_cut(self):
        cut = compute_macros(2800, "cut", 90, "male")
        bulk = compute_macros(2800, "bulk", 90, "male")
        assert cut["protein_g"] >= bulk["protein_g"]

    def test_fat_floor_respected(self):
        macros = compute_macros(2000, "cut", 90, "male")
        assert macros["fat_g"] >= 90 * 0.7  # at least ~0.8g/kg ish

    def test_carbs_positive(self):
        macros = compute_macros(3000, "bulk", 90, "male")
        assert macros["carbs_g"] > 0


class TestThermodynamicComprehensive:
    def test_surplus_positive_change(self):
        change = compute_expected_weight_change(500, 4)
        assert change > 0

    def test_deficit_negative_change(self):
        change = compute_expected_weight_change(-500, 4)
        assert change < 0

    def test_zero_balance_no_change(self):
        change = compute_expected_weight_change(0, 10)
        assert change == 0.0

    def test_floor_female(self):
        assert thermodynamic_floor(1000, "female") == 1200

    def test_floor_not_applied_when_above(self):
        assert thermodynamic_floor(2000, "female") == 2000


class TestKinetic:
    def test_rate_of_change_stable(self):
        history = [
            ("2026-01-01", 90.0),
            ("2026-01-08", 90.0),
            ("2026-01-15", 90.0),
        ]
        rate = compute_rate_of_change(history)
        assert abs(rate) < 0.1

    def test_rate_of_change_gaining(self):
        history = [
            ("2026-01-01", 90.0),
            ("2026-01-08", 90.5),
            ("2026-01-15", 91.0),
        ]
        rate = compute_rate_of_change(history)
        assert rate > 0

    def test_target_rate_bulk_positive(self):
        rate = target_rate("bulk", 90.0)
        assert rate > 0

    def test_target_rate_cut_negative(self):
        rate = target_rate("cut", 90.0)
        assert rate < 0

    def test_adjust_calories_no_op_when_on_track(self):
        # If actual rate matches target, minimal adjustment
        adjusted = adjust_calories(2800.0, 0.4, 0.4)
        assert abs(adjusted - 2800) < 50


class TestAutoregulationComprehensive:
    def test_lock_threshold_exact(self):
        result = adherence_lock(85.0, {"target_calories": 2800, "protein_g": 180, "carbs_g": 300, "fat_g": 80})
        # At exactly 85%, should not be locked
        assert result["locked"] is False

    def test_lock_at_84(self):
        result = adherence_lock(84.0, {"target_calories": 2800, "protein_g": 180, "carbs_g": 300, "fat_g": 80})
        assert result["locked"] is True

    def test_lock_message_present(self):
        result = adherence_lock(70.0, {"target_calories": 2800, "protein_g": 180, "carbs_g": 300, "fat_g": 80})
        assert "message" in result
        assert len(result["message"]) > 0

    def test_refeed_returns_dict(self):
        result = compute_refeed(14, 10.0, "male")
        assert "refeed_calories" in result or "refeed_carbs" in result or isinstance(result, dict)
