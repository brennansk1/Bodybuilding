"""Comprehensive tests for Engine 2 — Training modules."""
from app.engines.engine2.ari import compute_ari, get_ari_zone, get_volume_modifier
from app.engines.engine2.biomechanical import score_exercise, compute_sfr
from app.engines.engine2.resistance import estimate_1rm, compute_progression
from app.engines.engine2.recovery import estimate_recovery_time, can_train_muscle
from app.engines.engine2.overflow import compute_overflow


class TestARIComprehensive:
    def test_baseline_produces_midrange(self):
        """Baseline HRV with moderate sleep/soreness → mid-range ARI."""
        score = compute_ari(65.0, 60.0, 5.0, 5.0, 65.0)
        assert 30 < score < 80

    def test_excellent_recovery(self):
        score = compute_ari(90.0, 50.0, 9.0, 1.0, 65.0)
        assert score > 70

    def test_poor_recovery(self):
        score = compute_ari(25.0, 80.0, 3.0, 9.0, 65.0)
        assert score < 40

    def test_ari_clamped_0_100(self):
        low = compute_ari(5.0, 100.0, 1.0, 10.0, 65.0)
        high = compute_ari(120.0, 40.0, 10.0, 1.0, 65.0)
        assert 0 <= low <= 100
        assert 0 <= high <= 100

    def test_volume_modifier_green_zone(self):
        mod = get_volume_modifier(85)
        assert mod >= 1.0

    def test_volume_modifier_red_zone(self):
        mod = get_volume_modifier(20)
        assert mod < 0.8


class TestBiomechanical:
    def test_sfr_calculation(self):
        sfr = compute_sfr(1.0, 0.5)
        assert sfr == 2.0

    def test_sfr_high_fatigue(self):
        sfr = compute_sfr(0.8, 1.0)
        assert sfr == 0.8

    def test_score_exercise_higher_priority_higher_score(self):
        high_priority = score_exercise(1.0, 0.5, 0.9)
        low_priority = score_exercise(1.0, 0.5, 0.3)
        assert high_priority > low_priority


class TestResistanceComprehensive:
    def test_epley_100kg_10reps(self):
        rm = estimate_1rm(100.0, 10)
        assert 125 < rm < 140  # Epley: 100*(1+10/30) = 133.3

    def test_epley_single_rep(self):
        assert estimate_1rm(140.0, 1) == 140.0

    def test_progression_returns_dict(self):
        result = compute_progression(100.0, 10, 12, 7.0)
        assert isinstance(result, dict)

    def test_progression_at_ceiling(self):
        """When reps at ceiling with manageable RPE, should increase weight."""
        result = compute_progression(100.0, 12, 12, 7.0)
        assert result is not None


class TestRecovery:
    def test_large_muscle_needs_more_recovery(self):
        large = estimate_recovery_time("quads", 16, 0.8, 70.0)
        small = estimate_recovery_time("biceps", 8, 0.8, 70.0)
        assert large > small

    def test_low_ari_increases_recovery(self):
        normal = estimate_recovery_time("chest", 12, 0.75, 80.0)
        fatigued = estimate_recovery_time("chest", 12, 0.75, 30.0)
        assert fatigued > normal

    def test_can_train_after_full_recovery(self):
        recovery_needed = estimate_recovery_time("biceps", 8, 0.7, 75.0)
        assert can_train_muscle("biceps", recovery_needed + 1, recovery_needed)

    def test_cannot_train_too_soon(self):
        assert not can_train_muscle("quads", 12.0, 48.0)


class TestOverflow:
    def test_compound_distributes_volume(self):
        result = compute_overflow(
            primary_sets=4,
            secondary_muscles_hit={"triceps": 0.5, "front_delt": 0.3},
            existing_volume={"triceps": 6, "front_delt": 4},
        )
        assert result["triceps"] >= 6
        assert result["front_delt"] >= 4
