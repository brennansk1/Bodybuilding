"""Tests for constants — verify division vectors and exercise seed data integrity."""
from app.constants.divisions import DIVISION_VECTORS, K_SITE_FACTORS
from app.constants.exercises import SEED_EXERCISES


class TestDivisionVectors:
    def test_all_divisions_present(self):
        expected = {"mens_open", "classic_physique", "mens_physique", "womens_figure", "womens_bikini", "womens_physique", "wellness"}
        assert set(DIVISION_VECTORS.keys()) == expected

    def test_all_divisions_have_same_sites(self):
        sites = set(DIVISION_VECTORS["mens_open"].keys())
        for div in DIVISION_VECTORS.values():
            assert set(div.keys()) == sites

    def test_mens_open_shoulder_golden_ratio(self):
        """Shoulder vector should be the Golden Ratio conjugate."""
        assert DIVISION_VECTORS["mens_open"]["shoulders"] == 0.618

    def test_mens_open_vtaper_golden_ratio(self):
        assert DIVISION_VECTORS["mens_open"]["v_taper"] == 1.618

    def test_bicep_equals_calf_mens_open(self):
        """Classical symmetry rule: bicep = calf."""
        assert DIVISION_VECTORS["mens_open"]["bicep"] == DIVISION_VECTORS["mens_open"]["calf"]

    def test_classic_waist_tighter_than_open(self):
        assert DIVISION_VECTORS["classic_physique"]["waist"] < DIVISION_VECTORS["mens_open"]["waist"]

    def test_classic_higher_relative_taper(self):
        """Classic should have higher shoulder_to_waist than Open due to tighter waist."""
        assert DIVISION_VECTORS["classic_physique"]["shoulder_to_waist"] > DIVISION_VECTORS["mens_open"]["shoulder_to_waist"]

    def test_mens_physique_tightest_waist(self):
        """Men's Physique should have the tightest male waist."""
        male_divs = ["mens_open", "classic_physique", "mens_physique"]
        mp_waist = DIVISION_VECTORS["mens_physique"]["waist"]
        for div in male_divs:
            assert mp_waist <= DIVISION_VECTORS[div]["waist"]

    def test_mens_physique_smallest_thigh(self):
        """Board shorts division = smallest thigh emphasis."""
        male_divs = ["mens_open", "classic_physique", "mens_physique"]
        mp_thigh = DIVISION_VECTORS["mens_physique"]["thigh"]
        for div in male_divs:
            assert mp_thigh <= DIVISION_VECTORS[div]["thigh"]

    def test_womens_vtaper_below_male(self):
        """All women's v_taper values should be below male 1.618."""
        for div in ["womens_figure", "womens_bikini", "womens_physique"]:
            assert DIVISION_VECTORS[div]["v_taper"] < 1.618

    def test_womens_progressive_taper(self):
        """Bikini < Figure < Physique for shoulder_to_waist."""
        bikini = DIVISION_VECTORS["womens_bikini"]["shoulder_to_waist"]
        figure = DIVISION_VECTORS["womens_figure"]["shoulder_to_waist"]
        physique = DIVISION_VECTORS["womens_physique"]["shoulder_to_waist"]
        assert bikini < figure < physique

    def test_shoulder_to_waist_algebraic(self):
        """shoulder_to_waist should equal shoulders/waist (algebraically derived)."""
        for div_name, div in DIVISION_VECTORS.items():
            expected = div["shoulders"] / div["waist"]
            assert abs(div["shoulder_to_waist"] - expected) < 0.01, \
                f"{div_name}: expected {expected:.4f}, got {div['shoulder_to_waist']}"

    def test_all_ratios_positive_and_bounded(self):
        for div in DIVISION_VECTORS.values():
            for site, val in div.items():
                assert 0 < val < 2.0, f"Ratio {site}={val} out of bounds"


class TestKSiteFactors:
    def test_all_sites_present(self):
        expected = {"neck", "shoulders", "chest", "bicep", "forearm", "waist", "hips", "thigh", "calf", "back_width"}
        assert set(K_SITE_FACTORS.keys()) == expected

    def test_all_between_0_and_1(self):
        for site, k in K_SITE_FACTORS.items():
            assert 0 < k <= 1.0, f"K-factor for {site} = {k} out of range"

    def test_forearm_highest(self):
        assert K_SITE_FACTORS["forearm"] == max(K_SITE_FACTORS.values())

    def test_waist_lowest(self):
        assert K_SITE_FACTORS["waist"] == min(K_SITE_FACTORS.values())

    def test_ordering(self):
        """Limbs should have higher k-factors than trunk sites."""
        limb_avg = (K_SITE_FACTORS["bicep"] + K_SITE_FACTORS["forearm"] + K_SITE_FACTORS["calf"]) / 3
        trunk_avg = (K_SITE_FACTORS["waist"] + K_SITE_FACTORS["hips"] + K_SITE_FACTORS["chest"]) / 3
        assert limb_avg > trunk_avg


class TestExerciseDatabase:
    def test_minimum_exercise_count(self):
        assert len(SEED_EXERCISES) >= 50

    def test_exercise_tuple_format(self):
        for ex in SEED_EXERCISES:
            assert len(ex) == 7, f"Exercise {ex[0]} has {len(ex)} fields, expected 7"

    def test_efficiency_range(self):
        for ex in SEED_EXERCISES:
            assert 0.5 <= ex[5] <= 1.0, f"{ex[0]} efficiency {ex[5]} out of range"

    def test_fatigue_range(self):
        for ex in SEED_EXERCISES:
            assert 0.2 <= ex[6] <= 1.0, f"{ex[0]} fatigue ratio {ex[6]} out of range"

    def test_compound_benchmarks_at_1_0(self):
        """Core barbell compounds should be the 1.0 baseline."""
        benchmarks = {"Barbell Bench Press", "Barbell Row", "Overhead Press", "Barbell Back Squat"}
        for ex in SEED_EXERCISES:
            if ex[0] in benchmarks:
                assert ex[5] == 1.0, f"{ex[0]} efficiency should be 1.0"

    def test_unique_names(self):
        names = [ex[0] for ex in SEED_EXERCISES]
        assert len(names) == len(set(names)), "Duplicate exercise names found"

    def test_major_muscle_groups_covered(self):
        muscles = {ex[1] for ex in SEED_EXERCISES}
        required = {"chest", "back", "quads", "hamstrings", "glutes", "biceps", "triceps", "calves"}
        assert required.issubset(muscles), f"Missing muscles: {required - muscles}"
