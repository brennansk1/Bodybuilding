"""Tests for the Division-Specific Exercise Priority Cascade (Phase 8)."""
import pytest
from app.constants.exercise_priorities import (
    DIVISION_EXERCISE_PRIORITIES,
    _DIVISION_ALIASES,
    get_exercise_priorities,
    gap_adjusted_cap,
)

ALL_DIVISIONS = list(DIVISION_EXERCISE_PRIORITIES.keys())
REQUIRED_MUSCLES = {
    "chest", "back", "shoulders", "quads", "hamstrings",
    "glutes", "biceps", "triceps", "calves",
}


# ---------------------------------------------------------------------------
# Structure integrity
# ---------------------------------------------------------------------------

class TestStructure:
    def test_all_six_divisions_present(self):
        expected = {
            "mens_open", "mens_physique", "classic_physique",
            "womens_bikini", "womens_figure", "womens_physique",
        }
        assert set(ALL_DIVISIONS) == expected

    def test_all_divisions_cover_required_muscles(self):
        for div in ALL_DIVISIONS:
            muscles = set(DIVISION_EXERCISE_PRIORITIES[div].keys())
            missing = REQUIRED_MUSCLES - muscles
            assert not missing, f"{div} missing muscle groups: {missing}"

    def test_each_slot_has_keywords_and_max_sets(self):
        for div, muscles in DIVISION_EXERCISE_PRIORITIES.items():
            for muscle, slots in muscles.items():
                assert len(slots) > 0, f"{div}/{muscle} has no slots"
                for i, slot in enumerate(slots):
                    assert "keywords" in slot, f"{div}/{muscle} slot {i} missing 'keywords'"
                    assert "max_sets" in slot, f"{div}/{muscle} slot {i} missing 'max_sets'"
                    assert len(slot["keywords"]) > 0, f"{div}/{muscle} slot {i} has empty keywords"

    def test_max_sets_in_valid_range(self):
        for div, muscles in DIVISION_EXERCISE_PRIORITIES.items():
            for muscle, slots in muscles.items():
                for slot in slots:
                    assert 1 <= slot["max_sets"] <= 4, (
                        f"{div}/{muscle}: max_sets={slot['max_sets']} out of [1,4] range"
                    )

    def test_each_slot_has_name_and_load_type(self):
        """New spec requires name and load_type on every slot."""
        valid_load_types = {"plates", "plate_loaded", "machine_plates", "cable", "dumbbells", "bodyweight"}
        for div, muscles in DIVISION_EXERCISE_PRIORITIES.items():
            for muscle, slots in muscles.items():
                for i, slot in enumerate(slots):
                    assert "name" in slot, f"{div}/{muscle} slot {i} missing 'name'"
                    assert "load_type" in slot, f"{div}/{muscle} slot {i} missing 'load_type'"
                    assert slot["load_type"] in valid_load_types, (
                        f"{div}/{muscle} slot {i} has invalid load_type '{slot['load_type']}'"
                    )

    def test_no_empty_keywords(self):
        for div, muscles in DIVISION_EXERCISE_PRIORITIES.items():
            for muscle, slots in muscles.items():
                for slot in slots:
                    for kw in slot["keywords"]:
                        assert kw.strip(), f"{div}/{muscle} has blank keyword"


# ---------------------------------------------------------------------------
# Compound cap rules — division-specific maximums per the canonical spec
# ---------------------------------------------------------------------------

class TestCompoundCapRule:
    """
    Compound caps follow the canonical division spec.

    Mass divisions (Men's Open, Classic Physique) allow up to 4 sets on
    heavy compounds since advanced athletes can absorb that volume.

    Aesthetic/physique divisions reduce or eliminate heavy axial loading.
    Demoted exercises must have max_sets ≤ 2.
    """

    def _find_slots_for_keyword(self, division, keyword):
        results = []
        for muscle, slots in DIVISION_EXERCISE_PRIORITIES[division].items():
            for slot in slots:
                if any(keyword in kw for kw in slot["keywords"]):
                    results.append((muscle, slot))
        return results

    def test_barbell_row_absent_or_low_in_physique(self):
        """Men's Physique barbell row must be capped ≤2 (V-taper, trap suppression)."""
        for muscle, slot in self._find_slots_for_keyword("mens_physique", "barbell row"):
            assert slot["max_sets"] <= 2, (
                f"mens_physique/{muscle}: barbell row at {slot['max_sets']}, expected ≤2"
            )

    def test_barbell_squat_absent_or_low_in_physique_and_bikini(self):
        """Heavy axial squat must be absent from Men's Physique and Women's Bikini."""
        for div in ("mens_physique", "womens_bikini"):
            quad_keywords = [kw for slot in DIVISION_EXERCISE_PRIORITIES[div]["quads"] for kw in slot["keywords"]]
            has_barbell_squat = any("barbell back squat" in kw or "barbell squat" in kw for kw in quad_keywords)
            assert not has_barbell_squat, (
                f"{div}: barbell back squat should not appear (no heavy axial loading)"
            )

    def test_good_morning_low_cap_in_bikini(self):
        """Good Morning appears at max cap 2 in Women's Bikini hamstrings per spec."""
        for muscle, slot in self._find_slots_for_keyword("womens_bikini", "good morning"):
            assert slot["max_sets"] <= 2, (
                f"womens_bikini/{muscle}: Good Morning cap {slot['max_sets']} should be ≤2"
            )

    def test_conventional_deadlift_never_appears(self):
        """Conventional Deadlift excluded from all cascades (poor SFR for hypertrophy)."""
        for div in ALL_DIVISIONS:
            for muscle, slot in self._find_slots_for_keyword(div, "conventional deadlift"):
                assert False, f"{div}/{muscle}: Conventional Deadlift must not appear"

    def test_flat_barbell_bench_low_or_absent_in_physique(self):
        """Men's Physique flat barbell bench capped ≤2 (lower chest hurts aesthetics)."""
        for muscle, slot in self._find_slots_for_keyword("mens_physique", "barbell bench press"):
            assert slot["max_sets"] <= 2, (
                f"mens_physique/{muscle}: flat bench at {slot['max_sets']}, expected ≤2"
            )


# ---------------------------------------------------------------------------
# Division-specific correctness — judging alignment
# ---------------------------------------------------------------------------

class TestMensOpen:
    def _slots(self, muscle):
        return DIVISION_EXERCISE_PRIORITIES["mens_open"][muscle]

    def test_triceps_close_grip_bench_is_p1(self):
        """Men's Open triceps P1 = Close-Grip Bench Press (maximum mass/compound loading)."""
        p1 = self._slots("triceps")[0]
        assert any("close-grip" in kw or "close grip" in kw for kw in p1["keywords"]), (
            "Men's Open triceps P1 must be Close-Grip Bench Press (mass division compound anchor)"
        )

    def test_shoulders_overhead_press_is_p1(self):
        """Men's Open shoulders P1 = Overhead Barbell Press (mass division, anterior+medial)."""
        p1 = self._slots("shoulders")[0]
        assert any("overhead press" in kw or "barbell overhead" in kw for kw in p1["keywords"]), (
            "Men's Open shoulders P1 must be Overhead Press (mass division compound anchor)"
        )

    def test_chest_barbell_bench_is_p1(self):
        """Men's Open chest P1 = Barbell Bench Press (maximum chest mass)."""
        p1 = self._slots("chest")[0]
        assert any("barbell bench press" in kw for kw in p1["keywords"]), (
            "Men's Open chest P1 must be Barbell Bench Press"
        )

    def test_conventional_deadlift_absent_from_back(self):
        back_keywords = [kw for slot in self._slots("back") for kw in slot["keywords"]]
        assert not any("conventional deadlift" in kw for kw in back_keywords), (
            "Conventional Deadlift must not appear in Men's Open back cascade (poor SFR)"
        )

    def test_upright_row_absent_from_shoulders(self):
        shoulder_keywords = [kw for slot in self._slots("shoulders") for kw in slot["keywords"]]
        assert not any("upright row" in kw for kw in shoulder_keywords), (
            "Upright Row must not appear in Men's Open shoulders (subacromial impingement)"
        )

    def test_barbell_row_leads_back(self):
        """Barbell Row is P1 for Men's Open back (thickness-first for mass)."""
        p1 = self._slots("back")[0]
        assert any("barbell row" in kw for kw in p1["keywords"]), (
            "Men's Open back P1 must be Barbell Row (thickness-first for mass)"
        )


class TestMensPhysique:
    def _slots(self, muscle):
        return DIVISION_EXERCISE_PRIORITIES["mens_physique"][muscle]

    def test_chest_incline_barbell_is_p1(self):
        """Men's Physique chest P1 = Incline Barbell Press (upper chest shelf priority)."""
        p1 = self._slots("chest")[0]
        assert any("incline barbell" in kw for kw in p1["keywords"]), (
            "Men's Physique chest P1 must be Incline Barbell Press (upper chest shelf)"
        )

    def test_back_lat_pulldown_before_rows(self):
        """Lat pulldown (vertical pull) should appear before horizontal rows for V-taper."""
        slots = self._slots("back")
        pulldown_idx = next(
            (i for i, s in enumerate(slots) if any("lat pulldown" in kw or "pulldown" in kw for kw in s["keywords"])),
            None,
        )
        row_idx = next(
            (i for i, s in enumerate(slots) if any("row" in kw and "cable" not in kw for kw in s["keywords"])),
            None,
        )
        if pulldown_idx is not None and row_idx is not None:
            assert pulldown_idx < row_idx, (
                "Men's Physique: Lat Pulldown should precede rows for V-taper development"
            )

    def test_shoulders_lateral_raise_is_p1(self):
        p1 = self._slots("shoulders")[0]
        assert any("lateral raise" in kw for kw in p1["keywords"]), (
            "Men's Physique shoulders P1 must be lateral raise (cap width for V-taper)"
        )


class TestClassicPhysique:
    def _slots(self, muscle):
        return DIVISION_EXERCISE_PRIORITIES["classic_physique"][muscle]

    def test_triceps_close_grip_bench_is_p1(self):
        """Classic Physique triceps P1 = Close-Grip Bench Press per spec."""
        p1 = self._slots("triceps")[0]
        assert any("close-grip" in kw or "close grip" in kw for kw in p1["keywords"]), (
            "Classic Physique triceps P1 must be Close-Grip Bench Press"
        )

    def test_shoulders_overhead_press_is_p1(self):
        """Classic Physique shoulders P1 = Overhead Barbell Press per spec."""
        p1 = self._slots("shoulders")[0]
        assert any("overhead press" in kw or "barbell overhead" in kw for kw in p1["keywords"]), (
            "Classic Physique shoulders P1 must be Overhead Barbell Press"
        )

    def test_lat_pulldown_leads_back(self):
        """Classic Physique back P1 = Lat Pulldown (X-frame width)."""
        p1 = self._slots("back")[0]
        assert any("lat pulldown" in kw or "pulldown" in kw for kw in p1["keywords"]), (
            "Classic Physique back P1 must be Lat Pulldown (X-frame lat sweep)"
        )

    def test_incline_press_leads_chest(self):
        """Classic Physique chest P1 = Incline Barbell (upper chest prioritised)."""
        p1 = self._slots("chest")[0]
        assert any("incline barbell" in kw for kw in p1["keywords"]), (
            "Classic Physique chest P1 must be Incline Barbell Press"
        )


class TestWomensBikini:
    def _slots(self, muscle):
        return DIVISION_EXERCISE_PRIORITIES["womens_bikini"][muscle]

    def test_glutes_hip_thrust_is_p1(self):
        """Women's Bikini glutes P1 = Hip Thrust per canonical spec."""
        p1 = self._slots("glutes")[0]
        assert any("hip thrust" in kw for kw in p1["keywords"]), (
            "Women's Bikini glutes P1 must be Hip Thrust (canonical spec)"
        )

    def test_glutes_reverse_lunge_is_p2(self):
        """Women's Bikini glutes P2 = Deficit Reverse Lunge per spec."""
        p2 = self._slots("glutes")[1]
        assert any("lunge" in kw or "reverse lunge" in kw for kw in p2["keywords"]), (
            "Women's Bikini glutes P2 must be a lunge variation"
        )

    def test_good_morning_present_at_low_cap(self):
        """Good Morning appears in Women's Bikini hamstrings at cap ≤2 per spec."""
        ham_slots = self._slots("hamstrings")
        gm_slots = [s for s in ham_slots if any("good morning" in kw for kw in s["keywords"])]
        assert len(gm_slots) > 0, "Good Morning must appear in Women's Bikini hamstrings per spec"
        for slot in gm_slots:
            assert slot["max_sets"] <= 2, f"Good Morning cap {slot['max_sets']} should be ≤2"

    def test_no_heavy_pressing_p1(self):
        """No heavy barbell bench press as P1 in any muscle group."""
        chest_p1 = self._slots("chest")[0]
        assert not any("barbell bench press" in kw for kw in chest_p1["keywords"]), (
            "Women's Bikini must not lead chest with barbell bench (no heavy pressing)"
        )

    def test_abs_no_weighted_spinal_flexion(self):
        """Abs must use bodyweight or cable movements protecting the waist."""
        abs_slots = self._slots("abs")
        for slot in abs_slots:
            assert "plank" in slot["name"].lower() or "vacuum" in slot["name"].lower() \
                   or "raise" in slot["name"].lower() or "wheel" in slot["name"].lower() or \
                   "crunch" in slot["name"].lower(), (
                f"Women's Bikini abs: unexpected exercise '{slot['name']}'"
            )


class TestWomensFigure:
    def _slots(self, muscle):
        return DIVISION_EXERCISE_PRIORITIES["womens_figure"][muscle]

    def test_back_lat_pulldown_is_p1(self):
        p1 = self._slots("back")[0]
        assert any("lat pulldown" in kw or "pulldown" in kw for kw in p1["keywords"]), (
            "Women's Figure back P1 must be Lat Pulldown (V-taper width over thickness)"
        )

    def test_barbell_overhead_press_absent_from_shoulders(self):
        shoulder_keywords = [kw for slot in self._slots("shoulders") for kw in slot["keywords"]]
        assert not any("barbell overhead press" in kw for kw in shoulder_keywords), (
            "Barbell Overhead Press must not appear in Women's Figure (trap growth destroys V-taper)"
        )


class TestWomensPhysique:
    def _slots(self, muscle):
        return DIVISION_EXERCISE_PRIORITIES["womens_physique"][muscle]

    def test_shoulders_db_press_is_p1(self):
        """Women's Physique shoulders P1 = Dumbbell Shoulder Press per spec."""
        p1 = self._slots("shoulders")[0]
        assert any("dumbbell shoulder press" in kw for kw in p1["keywords"]), (
            "Women's Physique shoulders P1 must be Dumbbell Shoulder Press per spec"
        )

    def test_chest_incline_db_is_p1(self):
        """Women's Physique chest P1 = Incline DB Press (dumbbell-preferred division)."""
        p1 = self._slots("chest")[0]
        assert any("incline dumbbell" in kw for kw in p1["keywords"]), (
            "Women's Physique chest P1 must be Incline Dumbbell Press"
        )

    def test_back_cable_row_is_p1(self):
        """Women's Physique back P1 = Seated Cable Row (thickness + width together)."""
        p1 = self._slots("back")[0]
        assert any("cable row" in kw or "seated cable row" in kw for kw in p1["keywords"]), (
            "Women's Physique back P1 must be Seated Cable Row"
        )

    def test_barbell_back_squat_demoted(self):
        """Back squat should not be P1 or P2 (waist thickening concern)."""
        slots = self._slots("quads")
        squat_idx = next(
            (i for i, s in enumerate(slots) if any("barbell back squat" in kw for kw in s["keywords"])),
            None,
        )
        assert squat_idx is not None, "Barbell Back Squat should still appear in quads cascade"
        assert squat_idx >= 2, (
            f"Women's Physique: Barbell Back Squat at P{squat_idx+1} — must be P3 or lower"
        )

    def test_barbell_back_squat_low_cap(self):
        """Demoted squat should have low max_sets (≤2)."""
        for slot in self._slots("quads"):
            if any("barbell back squat" in kw for kw in slot["keywords"]):
                assert slot["max_sets"] <= 2, (
                    f"Women's Physique back squat cap {slot['max_sets']} should be ≤2"
                )


# ---------------------------------------------------------------------------
# Universal rules across all divisions
# ---------------------------------------------------------------------------

class TestUniversalRules:
    def test_overhead_extension_in_all_triceps_cascades(self):
        """Every division must include overhead extension somewhere in triceps cascade."""
        for div in ALL_DIVISIONS:
            slots = DIVISION_EXERCISE_PRIORITIES[div]["triceps"]
            all_kws = [kw for slot in slots for kw in slot["keywords"]]
            assert any("overhead" in kw for kw in all_kws), (
                f"{div}: overhead tricep extension must appear in triceps cascade (long-head SMBH)"
            )

    def test_cable_and_isolation_preferred_in_physique_divisions(self):
        """Physique/bikini/figure divisions should lead triceps with cable not barbell."""
        cable_first_divs = {"mens_physique", "womens_bikini", "womens_figure", "womens_physique"}
        for div in cable_first_divs:
            p1 = DIVISION_EXERCISE_PRIORITIES[div]["triceps"][0]
            assert p1["load_type"] == "cable", (
                f"{div}: triceps P1 should be cable movement, got '{p1['load_type']}'"
            )

    def test_no_division_has_upright_row(self):
        """Upright row is removed from all divisions due to subacromial impingement."""
        for div in ALL_DIVISIONS:
            for muscle, slots in DIVISION_EXERCISE_PRIORITIES[div].items():
                for slot in slots:
                    assert not any("upright row" in kw for kw in slot["keywords"]), (
                        f"{div}/{muscle}: Upright Row must never appear (impingement risk)"
                    )

    def test_every_division_has_glute_exercises(self):
        for div in ALL_DIVISIONS:
            assert len(DIVISION_EXERCISE_PRIORITIES[div]["glutes"]) >= 3, (
                f"{div}: glutes cascade must have ≥3 slots"
            )


# ---------------------------------------------------------------------------
# get_exercise_priorities() API
# ---------------------------------------------------------------------------

class TestGetExercisePriorities:
    def test_returns_correct_division(self):
        slots = get_exercise_priorities("mens_open", "chest")
        assert len(slots) > 0
        assert all("keywords" in s and "max_sets" in s for s in slots)

    def test_alias_resolution(self):
        """Division aliases (e.g. 'open' → 'mens_open') should resolve."""
        for alias, canonical in _DIVISION_ALIASES.items():
            slots = get_exercise_priorities(alias, "chest")
            canonical_slots = get_exercise_priorities(canonical, "chest")
            assert slots == canonical_slots, f"Alias {alias} did not resolve to {canonical}"

    def test_unknown_division_returns_open(self):
        """Unrecognised division falls back to mens_open."""
        slots = get_exercise_priorities("unknown_division", "chest")
        open_slots = get_exercise_priorities("mens_open", "chest")
        assert slots == open_slots

    def test_unknown_muscle_returns_empty(self):
        slots = get_exercise_priorities("mens_open", "nonexistent_muscle")
        assert slots == []

    def test_case_insensitive_division(self):
        slots_lower = get_exercise_priorities("mens_open", "back")
        slots_upper = get_exercise_priorities("MENS_OPEN", "back")
        assert slots_lower == slots_upper


# ---------------------------------------------------------------------------
# gap_adjusted_cap()
# ---------------------------------------------------------------------------

class TestGapAdjustedCap:
    def test_no_adjustment_when_not_top_priority(self):
        assert gap_adjusted_cap(4, 30.0, is_top_priority=False) == 4
        assert gap_adjusted_cap(4, 10.0, is_top_priority=False) == 4

    def test_severe_lag_multiplier(self):
        """HQI < 40 → ×1.5 on top-priority slot."""
        assert gap_adjusted_cap(4, 39.9, is_top_priority=True) == 6
        assert gap_adjusted_cap(3, 39.9, is_top_priority=True) == round(3 * 1.5)

    def test_moderate_lag_multiplier(self):
        """HQI 40-64 → ×1.25 on top-priority slot."""
        assert gap_adjusted_cap(4, 50.0, is_top_priority=True) == 5
        assert gap_adjusted_cap(4, 64.9, is_top_priority=True) == 5

    def test_no_lag_no_adjustment(self):
        """HQI ≥ 65 → no change."""
        assert gap_adjusted_cap(4, 65.0, is_top_priority=True) == 4
        assert gap_adjusted_cap(4, 90.0, is_top_priority=True) == 4

    def test_compound_cap_after_severe_gap(self):
        """Base-3 compound with severe gap yields 4-5 sets, not 6."""
        result = gap_adjusted_cap(3, 30.0, is_top_priority=True)
        assert result == round(3 * 1.5)  # 4 or 5, not 6
        assert result < 6

    def test_boundary_hqi_40(self):
        """HQI exactly 40 is moderate lag (≥40 but <65)."""
        assert gap_adjusted_cap(4, 40.0, is_top_priority=True) == 5

    def test_boundary_hqi_65(self):
        """HQI exactly 65 is no adjustment."""
        assert gap_adjusted_cap(4, 65.0, is_top_priority=True) == 4
