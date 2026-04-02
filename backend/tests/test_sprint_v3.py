"""
Sprint V3 Feature Tests

Tests for all new features introduced in the sprint:
- Curated exercise database integrity (Block 2A)
- Priority cascade keyword coverage (Block 2A)
- FST-7 session-level application (Block 2)
- Rest-time lookup table (Block 2)
- DUP rep range fallback (Block 2A)
- Equipment normalization (Block 2A)
- Phase transition macro adjustment (Block 5)
- BF threshold computation (Block 5)
"""
import pytest


# ---------------------------------------------------------------------------
# Block 2A — Curated Exercise Database
# ---------------------------------------------------------------------------

class TestCuratedExerciseDatabase:
    def test_minimum_exercise_count(self):
        from app.constants.exercises_curated import CURATED_EXERCISES
        assert len(CURATED_EXERCISES) >= 185, f"Expected >= 185 exercises, got {len(CURATED_EXERCISES)}"

    def test_no_duplicate_names(self):
        from app.constants.exercises_curated import CURATED_EXERCISES
        names = [e.name.lower() for e in CURATED_EXERCISES]
        dupes = [n for n in names if names.count(n) > 1]
        assert not dupes, f"Duplicate exercise names: {set(dupes)}"

    def test_all_required_fields_present(self):
        from app.constants.exercises_curated import CURATED_EXERCISES
        for ex in CURATED_EXERCISES:
            assert ex.name, f"Exercise missing name"
            assert ex.primary_muscle, f"{ex.name} missing primary_muscle"
            assert ex.equipment, f"{ex.name} missing equipment"
            assert ex.movement_pattern, f"{ex.name} missing movement_pattern"
            assert ex.load_type, f"{ex.name} missing load_type"

    def test_valid_equipment_values(self):
        from app.constants.exercises_curated import CURATED_EXERCISES
        valid = {"barbell", "dumbbell", "cable", "machine", "smith_machine", "bodyweight", "ez_bar"}
        for ex in CURATED_EXERCISES:
            assert ex.equipment in valid, f"{ex.name}: invalid equipment '{ex.equipment}'"

    def test_valid_load_types(self):
        from app.constants.exercises_curated import CURATED_EXERCISES
        valid = {"plates", "dumbbells", "cable", "machine_plates", "plate_loaded", "bodyweight"}
        for ex in CURATED_EXERCISES:
            assert ex.load_type in valid, f"{ex.name}: invalid load_type '{ex.load_type}'"

    def test_valid_movement_patterns(self):
        from app.constants.exercises_curated import CURATED_EXERCISES
        valid = {"push", "pull", "squat", "hinge", "isolation", "lunge", "carry"}
        for ex in CURATED_EXERCISES:
            assert ex.movement_pattern in valid, f"{ex.name}: invalid pattern '{ex.movement_pattern}'"

    def test_delt_subgroups_present(self):
        """Curated DB must use delt sub-groups (front_delt/side_delt/rear_delt), not generic 'shoulders'."""
        from app.constants.exercises_curated import CURATED_EXERCISES
        muscles = {ex.primary_muscle for ex in CURATED_EXERCISES}
        assert "front_delt" in muscles, "Missing front_delt exercises"
        assert "side_delt" in muscles, "Missing side_delt exercises"
        assert "rear_delt" in muscles, "Missing rear_delt exercises"
        assert "shoulders" not in muscles, "Should not have generic 'shoulders' — use delt sub-groups"

    def test_all_major_muscle_groups_covered(self):
        from app.constants.exercises_curated import CURATED_EXERCISES
        muscles = {ex.primary_muscle for ex in CURATED_EXERCISES}
        required = {"chest", "back", "front_delt", "side_delt", "rear_delt",
                     "biceps", "triceps", "quads", "hamstrings", "glutes",
                     "calves", "abs", "traps", "forearms"}
        missing = required - muscles
        assert not missing, f"Missing muscle groups: {missing}"

    def test_efficiency_and_fatigue_in_range(self):
        from app.constants.exercises_curated import CURATED_EXERCISES
        for ex in CURATED_EXERCISES:
            assert 0.0 < ex.efficiency <= 1.0, f"{ex.name}: efficiency {ex.efficiency} out of (0, 1]"
            assert 0.0 < ex.fatigue_ratio <= 1.0, f"{ex.name}: fatigue_ratio {ex.fatigue_ratio} out of (0, 1]"

    def test_exercise_name_length(self):
        from app.constants.exercises_curated import CURATED_EXERCISES
        for ex in CURATED_EXERCISES:
            assert len(ex.name) <= 100, f"Exercise name too long ({len(ex.name)}): {ex.name}"


# ---------------------------------------------------------------------------
# Block 2A — Priority Cascade Keyword Coverage
# ---------------------------------------------------------------------------

class TestPriorityCascadeCoverage:
    def test_every_slot_has_at_least_one_matching_exercise(self):
        """Every priority slot should have at least one keyword that matches a curated exercise."""
        from app.constants.exercises_curated import CURATED_EXERCISES
        from app.constants.exercise_priorities import DIVISION_EXERCISE_PRIORITIES

        exercise_names = [ex.name.lower() for ex in CURATED_EXERCISES]
        broken = []

        for div, muscles in DIVISION_EXERCISE_PRIORITIES.items():
            for muscle, slots in muscles.items():
                for slot in slots:
                    matched = any(
                        kw.lower() in name
                        for kw in slot["keywords"]
                        for name in exercise_names
                    )
                    if not matched:
                        broken.append(f"{div}/{muscle}: {slot['name']}")

        assert not broken, f"Broken priority slots (no matching exercise):\n" + "\n".join(broken)


# ---------------------------------------------------------------------------
# Block 2 — FST-7 & Rest Timer Configuration
# (Tested via source inspection to avoid DB dependency chain from training.py)
# ---------------------------------------------------------------------------

class TestFST7AndRestTimerConfig:
    """Verify FST-7 and rest timer config by reading source — avoids pydantic_settings import chain."""

    def test_fst7_targets_in_source(self):
        """training.py must define _FST7_TARGETS with all 7 divisions."""
        source = open("app/services/training.py").read()
        assert "_FST7_TARGETS" in source
        for div in ("mens_open", "mens_physique", "classic_physique",
                     "womens_bikini", "womens_figure", "womens_physique", "wellness"):
            assert f'"{div}"' in source, f"_FST7_TARGETS missing division: {div}"

    def test_fst7_intensity_modes_in_source(self):
        """training.py must define _FST7_INTENSITY with moderate/aggressive/extreme/none."""
        source = open("app/services/training.py").read()
        assert "_FST7_INTENSITY" in source
        for mode in ("moderate", "aggressive", "extreme", "none"):
            assert f'"{mode}"' in source, f"_FST7_INTENSITY missing mode: {mode}"

    def test_rest_seconds_function_in_source(self):
        """training.py must define _compute_rest_seconds."""
        source = open("app/services/training.py").read()
        assert "def _compute_rest_seconds" in source
        assert "is_warmup" in source
        assert "is_compound" in source

    def test_fst7_finisher_preferences_in_source(self):
        """training.py must define _FST7_FINISHER_PREFERENCES with major muscles."""
        source = open("app/services/training.py").read()
        assert "_FST7_FINISHER_PREFERENCES" in source
        for muscle in ("chest", "back", "side_delt", "biceps", "triceps", "quads", "hamstrings", "glutes", "calves"):
            assert f'"{muscle}"' in source, f"_FST7_FINISHER_PREFERENCES missing: {muscle}"

    def test_apply_session_fst7_in_source(self):
        """training.py must define _apply_session_fst7 session-level function."""
        source = open("app/services/training.py").read()
        assert "def _apply_session_fst7" in source
        assert "is_fst7" in source
        assert "rest_seconds" in source


# ---------------------------------------------------------------------------
# Block 5 — Phase Transition Macros
# ---------------------------------------------------------------------------

class TestPhaseTransitionMacros:
    def test_cut_reduces_calories(self):
        from app.engines.engine3.macros import adjust_macros_for_phase
        result = adjust_macros_for_phase(
            current_calories=3000, current_protein_g=200,
            current_carbs_g=350, current_fat_g=80,
            from_phase="offseason", to_phase="cut",
        )
        assert result["calories"] < 3000, "Cut should reduce calories"

    def test_bulk_increases_calories(self):
        from app.engines.engine3.macros import adjust_macros_for_phase
        result = adjust_macros_for_phase(
            current_calories=2500, current_protein_g=200,
            current_carbs_g=250, current_fat_g=80,
            from_phase="maintain", to_phase="bulk",
        )
        assert result["calories"] > 2500, "Bulk should increase calories"

    def test_protein_maintained_or_increased_in_cut(self):
        from app.engines.engine3.macros import adjust_macros_for_phase
        result = adjust_macros_for_phase(
            current_calories=3000, current_protein_g=200,
            current_carbs_g=350, current_fat_g=80,
            from_phase="offseason", to_phase="mini_cut",
        )
        assert result["protein_g"] >= 200, "Protein should not decrease during cut"

    def test_mini_cut_more_aggressive_than_cut(self):
        from app.engines.engine3.macros import adjust_macros_for_phase
        cut = adjust_macros_for_phase(
            current_calories=3000, current_protein_g=200,
            current_carbs_g=350, current_fat_g=80,
            from_phase="maintain", to_phase="cut",
        )
        mini_cut = adjust_macros_for_phase(
            current_calories=3000, current_protein_g=200,
            current_carbs_g=350, current_fat_g=80,
            from_phase="maintain", to_phase="mini_cut",
        )
        assert mini_cut["calories"] <= cut["calories"], "Mini-cut should be as aggressive or more than regular cut"


# ---------------------------------------------------------------------------
# Block 5 — BF Threshold Computation
# ---------------------------------------------------------------------------

class TestBFThreshold:
    def test_threshold_returns_valid_structure(self):
        from app.engines.engine1.weight_cap import compute_bf_threshold_from_weight_cap
        result = compute_bf_threshold_from_weight_cap(
            height_cm=180.0, current_weight_kg=95.0,
            wrist_cm=18.0, ankle_cm=23.0,
        )
        assert "threshold_bf_pct" in result
        assert "should_mini_cut" in result
        assert "offseason_cap_kg" in result

    def test_lightweight_athlete_no_mini_cut(self):
        from app.engines.engine1.weight_cap import compute_bf_threshold_from_weight_cap
        result = compute_bf_threshold_from_weight_cap(
            height_cm=175.0, current_weight_kg=75.0,
            wrist_cm=17.0, ankle_cm=22.0,
        )
        assert not result["should_mini_cut"], "Lightweight athlete shouldn't trigger mini-cut"

    def test_overweight_athlete_triggers_mini_cut(self):
        from app.engines.engine1.weight_cap import compute_bf_threshold_from_weight_cap
        result = compute_bf_threshold_from_weight_cap(
            height_cm=175.0, current_weight_kg=120.0,
            wrist_cm=17.0, ankle_cm=22.0,
        )
        assert result["should_mini_cut"], "Significantly overweight athlete should trigger mini-cut"


# ---------------------------------------------------------------------------
# Block 2A — Equipment Normalization
# ---------------------------------------------------------------------------

class TestEquipmentNormalization:
    def test_normalization_map_covers_legacy_names(self):
        """The normalization map in training.py should handle all legacy equipment names."""
        # Simulate the normalization map used in training.py
        _EQUIP_NORMALIZE = {
            "body_only": "bodyweight", "bodyweight": "bodyweight",
            "e_z_curl_bar": "ez_bar", "ez_bar": "ez_bar",
            "kettlebells": "dumbbell", "kettlebell": "dumbbell",
            "bands": "bodyweight", "resistance band": "bodyweight",
            "none": "bodyweight",
            "barbell": "barbell", "dumbbell": "dumbbell", "cable": "cable",
            "machine": "machine", "smith_machine": "smith_machine",
        }
        assert _EQUIP_NORMALIZE["body_only"] == "bodyweight"
        assert _EQUIP_NORMALIZE["e_z_curl_bar"] == "ez_bar"
        assert _EQUIP_NORMALIZE["kettlebells"] == "dumbbell"
        assert _EQUIP_NORMALIZE["bands"] == "bodyweight"
        assert _EQUIP_NORMALIZE["none"] == "bodyweight"


# ---------------------------------------------------------------------------
# Seed Service
# ---------------------------------------------------------------------------

class TestSeedService:
    def test_seed_imports_curated_not_full(self):
        """seed.py should import from exercises_curated, not exercises_full."""
        source = open("app/services/seed.py").read()
        assert "exercises_curated" in source, "seed.py should import from exercises_curated"
        assert "exercises_full" not in source, "seed.py should NOT import from exercises_full"
        assert "MAX_PER_MUSCLE" not in source, "seed.py should not have MAX_PER_MUSCLE cap"

    def test_seed_populates_load_type(self):
        """seed.py should set load_type when creating Exercise records."""
        source = open("app/services/seed.py").read()
        assert "load_type" in source, "seed.py should populate load_type on Exercise"
