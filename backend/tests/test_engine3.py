"""Unit tests for Engine 3 — Nutrition pure functions."""
from app.engines.engine3.macros import compute_tdee, compute_macros
from app.engines.engine3.thermodynamic import (
    compute_energy_balance, compute_expected_weight_change, thermodynamic_floor,
)
from app.engines.engine3.autoregulation import adherence_lock


class TestMacros:
    def test_compute_tdee_male(self):
        tdee = compute_tdee(90, 180, 25, "male", 1.55)
        assert 2500 < tdee < 3500

    def test_compute_tdee_female(self):
        tdee = compute_tdee(60, 165, 25, "female", 1.55)
        assert 1800 < tdee < 2600

    def test_compute_macros_maintain(self):
        macros = compute_macros(2800, "maintain", 90, "male")
        assert macros["protein_g"] > 0
        assert macros["carbs_g"] > 0
        assert macros["fat_g"] > 0
        # Calorie sum should approximately match target
        total = macros["protein_g"] * 4 + macros["carbs_g"] * 4 + macros["fat_g"] * 9
        assert abs(total - macros["target_calories"]) < 50

    def test_bulk_more_calories(self):
        maintain = compute_macros(2800, "maintain", 90, "male")
        bulk = compute_macros(2800, "bulk", 90, "male")
        assert bulk["target_calories"] > maintain["target_calories"]

    def test_cut_fewer_calories(self):
        maintain = compute_macros(2800, "maintain", 90, "male")
        cut = compute_macros(2800, "cut", 90, "male")
        assert cut["target_calories"] < maintain["target_calories"]


class TestThermodynamic:
    def test_energy_balance(self):
        assert compute_energy_balance(2500, 2800) == -300

    def test_expected_weight_change(self):
        # 500 kcal/day surplus × 7 days = 3500 kcal/week ≈ 0.45 kg
        change = compute_expected_weight_change(500, 1)
        assert 0.3 < change < 0.7

    def test_thermodynamic_floor_male(self):
        assert thermodynamic_floor(1200, "male") == 1500

    def test_thermodynamic_floor_above(self):
        assert thermodynamic_floor(2500, "male") == 2500


class TestAutoregulation:
    def test_adherence_lock_engaged(self):
        result = adherence_lock(70.0, {
            "target_calories": 2800,
            "protein_g": 180,
            "carbs_g": 300,
            "fat_g": 80,
        })
        assert result["locked"] is True

    def test_adherence_lock_not_engaged(self):
        result = adherence_lock(90.0, {
            "target_calories": 2800,
            "protein_g": 180,
            "carbs_g": 300,
            "fat_g": 80,
        })
        assert result["locked"] is False
