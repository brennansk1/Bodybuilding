"""
Regression tests for the stage-projected-weight readiness fix.

Before the fix: readiness.evaluate_readiness used raw current body weight vs
weight cap, producing a false "weight ✓" check for soft athletes who weigh
heavy but have high body fat. After: we project current LBM up to 5% BF so the
metric answers the real question — "if you cut to stage today, would you hit
the tier's weight floor?"
"""
from __future__ import annotations

import pytest

from app.constants.competitive_tiers import CompetitiveTier
from app.engines.engine1.readiness import evaluate_readiness


def _base_metrics(**overrides):
    base = {
        "body_weight_kg": 93.5,
        "bf_pct": 22.7,
        "normalized_ffmi": 20.0,
        "shoulder_waist_ratio": 1.20,
        "chest_waist_ratio": 1.22,
        "arm_calf_neck_max_diff_inches": 1.95,
        "hqi_score": 0.0,
        "hqi_age_days": 1,
        "training_years": 3.0,
    }
    base.update(overrides)
    return base


class TestStageProjectedWeight:
    def test_soft_athlete_does_not_pass_weight_cap_threshold(self):
        """22.7% BF + 93.5 kg + 105.2 kg cap → LBM 72.3 kg → stage proj 76.1 kg
        → ratio ~0.72, which is below the T1 threshold 0.80."""
        r = evaluate_readiness(
            _base_metrics(),
            target_tier=CompetitiveTier.LOCAL_NPC,
            weight_cap_kg=105.2,
            training_status="natural",
        )
        m = r["per_metric"]["weight_cap_pct"]
        assert m["met"] is False, "Soft athlete should NOT pass T1 weight threshold"
        assert 0.70 <= m["current"] <= 0.74
        assert m["projected_stage_kg"] == pytest.approx(76.1, abs=0.3)
        assert m["current_weight_kg"] == pytest.approx(93.5, abs=0.05)

    def test_stage_lean_athlete_passes_weight_cap_threshold(self):
        """Very-lean 6% BF + 82 kg on an 82 kg cap → LBM 77.1 → stage 81.1 →
        ratio ~0.989, comfortably within the T4 pro-qualifier threshold 0.97."""
        r = evaluate_readiness(
            _base_metrics(body_weight_kg=82.0, bf_pct=6.0),
            target_tier=CompetitiveTier.PRO_QUALIFIER,
            weight_cap_kg=82.0,
            training_status="natural",
        )
        m = r["per_metric"]["weight_cap_pct"]
        assert m["met"] is True, "Near-stage athlete should pass T4 weight threshold"
        assert m["current"] >= 0.97

    def test_missing_bf_falls_back_to_offseason_estimate(self):
        """When BF isn't logged, we shouldn't silently use body weight as LBM.
        v2 Sprint 0: fallback bumped from 15%→12% (Helms 2014 / Iraki 2019
        central estimate). Projected stage weight rises accordingly —
        93.5 × 0.88 / 0.95 = 86.6 kg → 0.866 of 100 kg cap.
        """
        m = _base_metrics(bf_pct=None)
        r = evaluate_readiness(
            m, CompetitiveTier.LOCAL_NPC, weight_cap_kg=100.0,
            training_status="natural",
        )
        w = r["per_metric"]["weight_cap_pct"]
        assert 0.85 <= w["current"] <= 0.88


class TestHQIStalenessGuard:
    def test_fresh_hqi_counts_toward_threshold(self):
        r = evaluate_readiness(
            _base_metrics(hqi_score=60.0, hqi_age_days=14),
            target_tier=CompetitiveTier.LOCAL_NPC,
            weight_cap_kg=105.2,
            training_status="natural",
        )
        assert r["per_metric"]["hqi"]["met"] is True
        assert r["per_metric"]["hqi"]["stale"] is False

    def test_stale_hqi_does_not_count(self):
        """A 180-day-old HQI of 82 should not silently satisfy the T1 floor
        of 40 — the athlete's body is different now."""
        r = evaluate_readiness(
            _base_metrics(hqi_score=82.0, hqi_age_days=180),
            target_tier=CompetitiveTier.LOCAL_NPC,
            weight_cap_kg=105.2,
            training_status="natural",
        )
        assert r["per_metric"]["hqi"]["met"] is False
        assert r["per_metric"]["hqi"]["stale"] is True
        assert r["per_metric"]["hqi"]["raw"] == pytest.approx(82.0)

    def test_missing_hqi_reports_unknown_staleness(self):
        r = evaluate_readiness(
            _base_metrics(hqi_score=0.0, hqi_age_days=None),
            target_tier=CompetitiveTier.LOCAL_NPC,
            weight_cap_kg=105.2,
            training_status="natural",
        )
        assert r["per_metric"]["hqi"]["met"] is False
        assert r["per_metric"]["hqi"]["stale"] is False
