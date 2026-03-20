"""Unit tests for Engine 2 — Training pure functions."""
from app.engines.engine2.ari import compute_ari, get_ari_zone, get_volume_modifier
from app.engines.engine2.resistance import estimate_1rm, compute_progression


class TestARI:
    def test_compute_ari_range(self):
        score = compute_ari(65.0, 58.0, 7.0, 3.0, 65.0)
        assert 0 <= score <= 100

    def test_high_hrv_high_score(self):
        good = compute_ari(80.0, 55.0, 9.0, 2.0, 65.0)
        bad = compute_ari(30.0, 75.0, 4.0, 8.0, 65.0)
        assert good > bad

    def test_ari_zones(self):
        assert get_ari_zone(80) == "green"
        assert get_ari_zone(55) == "yellow"
        assert get_ari_zone(20) == "red"

    def test_volume_modifier_range(self):
        for ari in [0, 30, 50, 70, 90, 100]:
            mod = get_volume_modifier(ari)
            assert 0.5 <= mod <= 1.2


class TestResistance:
    def test_estimate_1rm_epley(self):
        # 100kg x 5 reps
        one_rm = estimate_1rm(100.0, 5)
        assert 110 < one_rm < 120  # Epley: 100 * (1 + 5/30) = 116.7

    def test_estimate_1rm_single(self):
        one_rm = estimate_1rm(100.0, 1)
        assert one_rm == 100.0

    def test_progression_add_reps(self):
        result = compute_progression(100.0, 8, 12, 7.0)
        assert result is not None
        assert "next_weight_kg" in result or "next_reps" in result
