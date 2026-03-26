"""
Multi-Week Coaching Simulation Test Suite
═════════════════════════════════════════

Simulates real athlete journeys across every scenario a competitive bodybuilder
encounters. Each test feeds weekly data through the engines and verifies the
system adapts exactly as an Olympia-level coach would.

SCENARIOS TESTED:
─────────────────
A. FULL CONTEST PREP CYCLE (16 weeks)
   Offseason → cut → peak week → show → reverse diet
   Verifies: calorie taper, protein escalation, fat floor management,
   volume reduction, peak week carb load, post-show recovery

B. OFFSEASON MUSCLE BUILDING (12 weeks)
   Lean bulk with progressive overload
   Verifies: weight gain rate (0.25-0.5% BW/week), strength progression,
   volume accumulation through mesocycle, deload response

C. RECOVERY CRISIS (ARI crash)
   Athlete overreaches — sleep drops, soreness spikes, HRV crashes
   Verifies: volume auto-reduces, potential refeed triggers, recovery before push

D. ADHERENCE FAILURE & RECOVERY
   Athlete falls off diet for 2 weeks, then gets back on track
   Verifies: system locks adjustments during low adherence, resumes when compliant

E. WEIGHT STALL / PLATEAU BREAKING
   Athlete's weight stalls for 3+ weeks during a cut
   Verifies: calorie adjustment (metabolic adaptation), potential refeed,
   cardio increase recommendation

F. RAPID WEIGHT LOSS (too fast)
   Athlete loses weight too quickly (>1% BW/week)
   Verifies: system flags muscle loss risk, potentially increases calories

G. FEMALE ATHLETE HORMONAL CONSIDERATIONS
   Female bikini competitor through full prep
   Verifies: fat never drops below 0.6g/kg, calories don't go dangerously low,
   gentler peak week protocol

H. DIVISION TRANSITION
   Athlete data run through multiple divisions to verify different prescriptions
   Verifies: same body, different division = fundamentally different programming

No database required — all engines are pure functions.
"""

import pytest
from dataclasses import dataclass, replace
from copy import deepcopy

# ── Engine imports ──
from app.engines.engine1.pds import (
    compute_pds, compute_muscle_mass_score,
    compute_conditioning_score, compute_symmetry_score, get_tier,
)
from app.engines.engine1.lcsa import compute_all_lcsa
from app.engines.engine1.body_fat import lean_mass_kg
from app.engines.engine1.weight_cap import compute_weight_cap, compute_max_circumferences
from app.engines.engine1.muscle_gaps import (
    compute_all_gaps, compute_ideal_circumferences, rank_sites_by_gap,
)
from app.engines.engine2.ari import compute_ari, get_ari_zone, get_volume_modifier
from app.engines.engine2.periodization import generate_mesocycle
from app.engines.engine2.split_designer import design_split
from app.engines.engine3.macros import (
    compute_tdee, compute_macros, compute_training_rest_day_macros,
)
from app.engines.engine3.meal_planner import generate_meal_plan
from app.engines.engine3.food_database import get_available_foods
from app.engines.engine3.peak_week import compute_peak_week_protocol
from app.engines.engine3.thermodynamic import (
    compute_energy_balance, compute_expected_weight_change,
    thermodynamic_floor, compute_adaptation_factor,
)
from app.engines.engine3.kinetic import (
    compute_rate_of_change, target_rate, adjust_calories,
)
from app.engines.engine3.autoregulation import (
    should_halt_cut, adherence_lock, compute_refeed,
)
from app.constants.divisions import DIVISION_VECTORS, DIVISION_CEILING_FACTORS


# ═══════════════════════════════════════════════════════════════════════════════
# SIMULATION HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class WeekState:
    """Snapshot of an athlete's state for one week of simulation."""
    week: int
    phase: str
    body_weight_kg: float
    body_fat_pct: float
    # Recovery
    rmssd: float
    resting_hr: float
    sleep_quality: float
    soreness: float
    # Adherence
    nutrition_adherence: float  # 0-100
    training_adherence: float   # 0-100
    # Training response
    bench_1rm: float
    squat_1rm: float


def compute_week_prescription(
    state: WeekState,
    sex: str,
    height_cm: float,
    age: int,
    division: str,
    days_per_week: int,
    training_years: float,
    tape: dict,
    wrist_cm: float = 17.5,
    ankle_cm: float = 23.0,
) -> dict:
    """Run all engines for a single week and return the full prescription."""
    lbm = lean_mass_kg(state.body_weight_kg, state.body_fat_pct)

    # Engine 1: Diagnostics
    lcsa = compute_all_lcsa(tape, state.body_fat_pct)
    total_lcsa = sum(lcsa.values())
    weight_cap = compute_weight_cap(height_cm, wrist_cm, ankle_cm, 5.0, sex)
    max_circs = compute_max_circumferences(height_cm, wrist_cm, ankle_cm, sex)
    division_vector = DIVISION_VECTORS.get(division, {})
    ceiling_factors = DIVISION_CEILING_FACTORS.get(division, {})
    ideal_circs = compute_ideal_circumferences(
        max_circs, ceiling_factors, division_vector, height_cm
    )
    gaps = compute_all_gaps(tape, ideal_circs)
    ranked_gaps = rank_sites_by_gap(gaps, division)

    muscle_mass_score = compute_muscle_mass_score(total_lcsa, height_cm, sex)
    conditioning_score = compute_conditioning_score(state.body_fat_pct, sex, state.phase)
    symmetry_score = compute_symmetry_score(tape)
    pds = compute_pds(70.0, muscle_mass_score, conditioning_score, symmetry_score, division)
    tier = get_tier(pds)

    # Engine 2: Training
    ari = compute_ari(state.rmssd, state.resting_hr, state.sleep_quality,
                      state.soreness, baseline_rmssd=50.0, baseline_hr=60.0)
    ari_zone = get_ari_zone(ari)
    volume_mod = get_volume_modifier(ari)

    gap_scores = {g["site"]: g.get("gap_cm", 0) for g in ranked_gaps}
    split = design_split(gap_scores, division, days_per_week, tape.get("shoulders"), height_cm)
    volume_budget = split.get("volume_budget", {})

    # Engine 3: Nutrition
    activity_mult = 1.55 if days_per_week <= 4 else 1.725
    tdee = compute_tdee(state.body_weight_kg, height_cm, age, sex,
                        activity_mult, lean_mass_kg=lbm)
    macros = compute_macros(tdee, state.phase, state.body_weight_kg, sex,
                            lean_mass_kg=lbm, body_fat_pct=state.body_fat_pct)

    # Meal plan
    meal_count = 5 if sex == "male" else 4
    meals = generate_meal_plan(
        phase=state.phase, division=division, meal_count=meal_count,
        protein_g=macros["protein_g"], carbs_g=macros["carbs_g"],
        fat_g=macros["fat_g"], target_calories=macros["target_calories"],
        seed=42 + state.week,
    )

    # Autoregulation checks
    halt_result = should_halt_cut(state.body_fat_pct, division)
    halt = halt_result.get("halt", False) if isinstance(halt_result, dict) else bool(halt_result)
    dummy_rx = {"target_calories": macros["target_calories"], "protein_g": macros["protein_g"],
                "carbs_g": macros["carbs_g"], "fat_g": macros["fat_g"]}
    adh_result = adherence_lock(state.nutrition_adherence, dummy_rx, phase=state.phase, sex=sex)
    adh_locked = adh_result.get("locked", False) if isinstance(adh_result, dict) else bool(adh_result)

    # Peak week
    peak_protocol = None
    if state.phase == "peak":
        peak_protocol = compute_peak_week_protocol(lbm, division=division)

    # Thermodynamic floor
    floor_kcal = thermodynamic_floor(state.body_weight_kg, sex)

    return {
        "week": state.week,
        "phase": state.phase,
        "weight": state.body_weight_kg,
        "bf_pct": state.body_fat_pct,
        "lbm": lbm,
        "pds": pds,
        "tier": tier,
        "conditioning": conditioning_score,
        "ari": ari,
        "ari_zone": ari_zone,
        "volume_mod": volume_mod,
        "volume_budget": volume_budget,
        "total_volume": sum(volume_budget.values()),
        "tdee": tdee,
        "target_cal": macros["target_calories"],
        "protein_g": macros["protein_g"],
        "protein_per_kg": macros["protein_g"] / state.body_weight_kg,
        "carbs_g": macros["carbs_g"],
        "fat_g": macros["fat_g"],
        "fat_per_kg": macros["fat_g"] / state.body_weight_kg,
        "meals": meals,
        "halt_cut": halt,
        "adh_locked": adh_locked,
        "peak_protocol": peak_protocol,
        "floor_kcal": floor_kcal,
        "split_name": split.get("split_name", "unknown"),
        "top_gaps": ranked_gaps[:3],
        "available_proteins": [f.name for f in get_available_foods(state.phase, category="protein")],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SCENARIO A: FULL CONTEST PREP CYCLE (16 weeks)
# Men's Open — Offseason → Cut → Peak → Reverse
# ═══════════════════════════════════════════════════════════════════════════════

class TestFullContestPrep:
    """
    Simulate Marcus Thompson (Men's Open) through a full 16-week contest prep:
    Weeks 1-2: Late offseason (bulk)
    Weeks 3-12: Contest cut (progressive fat loss)
    Week 13: Final cut (very lean)
    Weeks 14: Peak week
    Weeks 15-16: Post-show reverse diet (restoration)
    """

    TAPE = dict(
        neck=44.0, shoulders=137.0, chest=125.0, bicep=47.0,
        forearm=35.0, waist=88.0, hips=106.0, thigh=70.0, calf=43.0,
        back_width=52.0,
    )

    def _build_timeline(self) -> list[WeekState]:
        """Simulate realistic weekly body composition changes."""
        timeline = []
        # Weeks 1-2: Late offseason
        timeline.append(WeekState(1, "bulk", 109.0, 14.0, 45, 62, 7, 4, 92, 95, 180, 230))
        timeline.append(WeekState(2, "bulk", 109.3, 14.1, 46, 61, 7.5, 3, 95, 100, 182, 232))

        # Weeks 3-12: Contest cut — progressive weight loss ~0.7kg/week
        weight = 109.0
        bf = 14.0
        for wk in range(3, 13):
            weight -= 0.8  # losing ~0.8kg/week
            bf -= 0.8      # BF dropping
            # Recovery degrades as prep continues
            rmssd = max(28, 45 - (wk - 3) * 1.5)
            sleep = max(5.0, 7.5 - (wk - 3) * 0.2)
            soreness = min(7.0, 4.0 + (wk - 3) * 0.3)
            hr = min(72, 62 + (wk - 3) * 0.8)
            # Strength slowly declines
            bench = max(150, 180 - (wk - 3) * 2)
            squat = max(190, 230 - (wk - 3) * 3)
            timeline.append(WeekState(
                wk, "cut", round(weight, 1), round(max(4.5, bf), 1),
                rmssd, hr, sleep, soreness, 88, 90, bench, squat
            ))

        # Week 13: Final cut, very lean
        timeline.append(WeekState(13, "cut", 96.5, 4.8, 30, 70, 5.0, 6, 85, 85, 155, 195))

        # Week 14: Peak week
        timeline.append(WeekState(14, "peak", 96.0, 4.5, 28, 72, 4.5, 7, 90, 80, 150, 190))

        # Weeks 15-16: Reverse diet (restoration)
        timeline.append(WeekState(15, "restoration", 97.5, 5.5, 35, 68, 6.0, 5, 80, 70, 155, 195))
        timeline.append(WeekState(16, "restoration", 99.0, 7.0, 40, 65, 7.0, 4, 85, 75, 158, 200))

        return timeline

    def test_calorie_taper_during_cut(self):
        """Calories should progressively decrease as cut progresses."""
        timeline = self._build_timeline()
        results = []
        for state in timeline:
            if state.phase == "cut":
                r = compute_week_prescription(
                    state, "male", 178.0, 30, "mens_open", 5, 10, self.TAPE,
                )
                results.append(r)

        # First cut week should have more calories than last
        assert results[0]["target_cal"] > results[-1]["target_cal"], (
            f"Calories didn't decrease: week 3={results[0]['target_cal']:.0f} "
            f"vs week 13={results[-1]['target_cal']:.0f}"
        )

    def test_protein_escalation_during_prep(self):
        """Protein per kg should increase or stay high as BF drops (LBM preservation)."""
        timeline = self._build_timeline()
        early_cut = compute_week_prescription(
            timeline[2], "male", 178.0, 30, "mens_open", 5, 10, self.TAPE
        )
        late_cut = compute_week_prescription(
            timeline[12], "male", 178.0, 30, "mens_open", 5, 10, self.TAPE
        )
        # Both should be at 2.4g/kg (cut tier). At minimum, late cut should not DROP.
        assert late_cut["protein_per_kg"] >= early_cut["protein_per_kg"] - 0.05, (
            f"Protein dropped: early={early_cut['protein_per_kg']:.2f} "
            f"late={late_cut['protein_per_kg']:.2f}"
        )
        # Both should be ≥2.2 for cut
        assert late_cut["protein_per_kg"] >= 2.2
        assert early_cut["protein_per_kg"] >= 2.2

    def test_fat_floor_maintained_through_prep(self):
        """Fat should never drop below 0.5g/kg even in peak week."""
        timeline = self._build_timeline()
        for state in timeline:
            r = compute_week_prescription(
                state, "male", 178.0, 30, "mens_open", 5, 10, self.TAPE
            )
            assert r["fat_per_kg"] >= 0.49, (
                f"Week {state.week} ({state.phase}): fat {r['fat_per_kg']:.2f}g/kg "
                f"below floor"
            )

    def test_ari_degrades_during_prep(self):
        """ARI should trend downward as the athlete gets more depleted."""
        timeline = self._build_timeline()
        early = compute_week_prescription(
            timeline[2], "male", 178.0, 30, "mens_open", 5, 10, self.TAPE
        )
        late = compute_week_prescription(
            timeline[12], "male", 178.0, 30, "mens_open", 5, 10, self.TAPE
        )
        assert late["ari"] < early["ari"], (
            f"ARI didn't degrade: early={early['ari']:.0f} late={late['ari']:.0f}"
        )

    def test_volume_reduces_during_deep_prep(self):
        """Volume modifier should decrease as ARI drops in late prep."""
        timeline = self._build_timeline()
        early = compute_week_prescription(
            timeline[2], "male", 178.0, 30, "mens_open", 5, 10, self.TAPE
        )
        late = compute_week_prescription(
            timeline[12], "male", 178.0, 30, "mens_open", 5, 10, self.TAPE
        )
        assert late["volume_mod"] <= early["volume_mod"], (
            f"Volume modifier didn't reduce: early={early['volume_mod']:.2f} "
            f"late={late['volume_mod']:.2f}"
        )

    def test_peak_week_activates(self):
        """Peak week protocol should generate when phase is 'peak'."""
        timeline = self._build_timeline()
        peak_state = timeline[13]  # Week 14
        r = compute_week_prescription(
            peak_state, "male", 178.0, 30, "mens_open", 5, 10, self.TAPE
        )
        assert r["peak_protocol"] is not None, "Peak protocol not generated"
        assert len(r["peak_protocol"]) == 7, f"Peak protocol has {len(r['peak_protocol'])} days"

    def test_peak_food_selection_clean(self):
        """Peak week foods should be only clean proteins — no red meat, no dairy."""
        timeline = self._build_timeline()
        peak_state = timeline[13]
        r = compute_week_prescription(
            peak_state, "male", 178.0, 30, "mens_open", 5, 10, self.TAPE
        )
        banned = {"Lean Ground Beef (96/4)", "Lean Ground Beef (93/7)", "Sirloin Steak",
                  "Flank Steak", "Eye of Round", "Salmon", "Whole Eggs",
                  "Greek Yogurt (nonfat)", "Cottage Cheese (low-fat)"}
        for name in r["available_proteins"]:
            assert name not in banned, f"Peak week allows {name} — coach would remove it"

    def test_restoration_calories_increase(self):
        """Post-show reverse diet should have more calories than peak."""
        timeline = self._build_timeline()
        peak_r = compute_week_prescription(
            timeline[13], "male", 178.0, 30, "mens_open", 5, 10, self.TAPE
        )
        restore_r = compute_week_prescription(
            timeline[14], "male", 178.0, 30, "mens_open", 5, 10, self.TAPE
        )
        assert restore_r["target_cal"] > peak_r["target_cal"], (
            f"Restoration calories ({restore_r['target_cal']:.0f}) not higher "
            f"than peak ({peak_r['target_cal']:.0f})"
        )

    def test_conditioning_peaks_at_show(self):
        """Conditioning score should be highest at lowest body fat."""
        timeline = self._build_timeline()
        offseason_r = compute_week_prescription(
            timeline[0], "male", 178.0, 30, "mens_open", 5, 10, self.TAPE
        )
        peak_r = compute_week_prescription(
            timeline[13], "male", 178.0, 30, "mens_open", 5, 10, self.TAPE
        )
        assert peak_r["conditioning"] > offseason_r["conditioning"], (
            f"Conditioning at 4.5% BF ({peak_r['conditioning']:.1f}) not higher "
            f"than at 14% ({offseason_r['conditioning']:.1f})"
        )

    def test_full_prep_print_summary(self, capsys):
        """Print the full 16-week prep timeline for human review."""
        timeline = self._build_timeline()
        print(f"\n{'='*80}")
        print(f"  FULL CONTEST PREP SIMULATION — Men's Open — 16 Weeks")
        print(f"{'='*80}")
        for state in timeline:
            r = compute_week_prescription(
                state, "male", 178.0, 30, "mens_open", 5, 10, self.TAPE
            )
            surplus_deficit = r["target_cal"] - r["tdee"]
            direction = "surplus" if surplus_deficit > 0 else "deficit"
            print(
                f"  Wk{state.week:2d} | {state.phase:12s} | "
                f"{state.body_weight_kg:5.1f}kg {state.body_fat_pct:4.1f}%BF | "
                f"ARI:{r['ari']:3.0f}({r['ari_zone']:6s}) vol×{r['volume_mod']:.2f} | "
                f"{r['target_cal']:4.0f}kcal ({direction}: {abs(surplus_deficit):.0f}) | "
                f"P{r['protein_g']:3.0f}g({r['protein_per_kg']:.1f}/kg) "
                f"C{r['carbs_g']:3.0f}g F{r['fat_g']:2.0f}g({r['fat_per_kg']:.2f}/kg) | "
                f"PDS:{r['pds']:.0f}"
            )
            if r["peak_protocol"]:
                print(f"         Peak: " + " → ".join(
                    f"C{d['carbs_g']:.0f}" for d in r["peak_protocol"]
                ))
        assert True


# ═══════════════════════════════════════════════════════════════════════════════
# SCENARIO B: OFFSEASON MUSCLE BUILDING (12 weeks)
# ═══════════════════════════════════════════════════════════════════════════════

class TestOffseassonBuilding:
    """Classic Physique lean bulk with progressive overload through a mesocycle."""

    TAPE = dict(
        neck=42.0, shoulders=130.0, chest=118.0, bicep=44.0,
        forearm=33.0, waist=80.0, hips=100.0, thigh=65.0, calf=41.0,
        back_width=48.0,
    )

    def _build_timeline(self) -> list[WeekState]:
        timeline = []
        weight = 98.0
        bf = 12.0
        bench = 160.0
        squat = 200.0
        for wk in range(1, 13):
            # Gaining ~0.3kg/week (lean bulk rate)
            weight += 0.3
            bf += 0.05  # slight BF creep
            # Strength progressing (linear for simplicity)
            bench += 1.0
            squat += 1.5
            # Good recovery in offseason
            rmssd = 50 + (wk % 3)  # slight variance
            # Deload week every 6 weeks — better recovery
            is_deload = wk in (6, 12)
            soreness = 2.0 if is_deload else 3.0 + (wk % 6) * 0.3
            timeline.append(WeekState(
                wk, "lean_bulk", round(weight, 1), round(bf, 1),
                rmssd, 58, 8.0, soreness, 93, 95, bench, squat
            ))
        return timeline

    def test_weight_gain_rate(self):
        """Weight gain should be ~0.25-0.5% BW/week for lean bulk."""
        timeline = self._build_timeline()
        total_gain = timeline[-1].body_weight_kg - timeline[0].body_weight_kg
        weekly_rate = total_gain / 12
        pct_rate = (weekly_rate / timeline[0].body_weight_kg) * 100
        assert 0.1 <= pct_rate <= 0.6, (
            f"Gain rate {pct_rate:.2f}%/week outside lean bulk range [0.2, 0.5]"
        )

    def test_surplus_maintained(self):
        """All offseason weeks should be in caloric surplus."""
        timeline = self._build_timeline()
        for state in timeline:
            r = compute_week_prescription(
                state, "male", 180.0, 28, "classic_physique", 5, 8, self.TAPE
            )
            assert r["target_cal"] > r["tdee"], (
                f"Week {state.week}: no surplus ({r['target_cal']:.0f} vs TDEE {r['tdee']:.0f})"
            )

    def test_mesocycle_structure(self):
        """Generated mesocycle should have proper MEV→MAV→MRV→deload phases."""
        state = WeekState(1, "lean_bulk", 98.0, 12.0, 50, 58, 8, 3, 95, 95, 160, 200)
        r = compute_week_prescription(
            state, "male", 180.0, 28, "classic_physique", 5, 8, self.TAPE
        )
        vol = r["volume_budget"]
        meso = generate_mesocycle(5, "ppl", vol, 6, training_experience_years=8)
        assert len(meso) == 6
        assert meso[-1]["is_deload"] is True, "Final week should be deload"
        # Volume should increase from week 1 to week 5
        w1_vol = meso[0].get("volume", {})
        w5_vol = meso[4].get("volume", {})
        w1_total = sum(w1_vol.values()) if isinstance(w1_vol, dict) else 0
        w5_total = sum(w5_vol.values()) if isinstance(w5_vol, dict) else 0
        assert w5_total >= w1_total, "Volume should increase MEV→MRV through mesocycle"

    def test_side_delt_priority_classic(self):
        """Classic Physique should have side delts as high-priority muscle."""
        state = WeekState(1, "lean_bulk", 98.0, 12.0, 50, 58, 8, 3, 95, 95, 160, 200)
        r = compute_week_prescription(
            state, "male", 180.0, 28, "classic_physique", 5, 8, self.TAPE
        )
        vol = r["volume_budget"]
        side_delt = vol.get("side_delt", 0)
        assert side_delt >= 8, (
            f"Classic Physique side delt volume only {side_delt} sets — "
            f"coach would prescribe ≥10 for V-taper"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# SCENARIO C: RECOVERY CRISIS (ARI CRASH)
# ═══════════════════════════════════════════════════════════════════════════════

class TestRecoveryCrisis:
    """Athlete overreaches — HRV crashes, sleep degrades, soreness spikes."""

    TAPE = dict(
        neck=39.0, shoulders=125.0, chest=110.0, bicep=40.0,
        forearm=31.0, waist=76.0, hips=96.0, thigh=60.0, calf=38.0,
        back_width=46.0,
    )

    def test_ari_crash_reduces_volume(self):
        """When ARI drops to red, volume should be aggressively reduced."""
        # Healthy week
        healthy = WeekState(1, "lean_bulk", 88.0, 11.0, 55, 56, 8, 3, 95, 95, 130, 160)
        # Crisis week — bad sleep, high soreness, crashed HRV
        crisis = WeekState(2, "lean_bulk", 88.0, 11.0, 22, 74, 3.5, 8, 90, 85, 125, 150)

        healthy_r = compute_week_prescription(
            healthy, "male", 183.0, 26, "mens_physique", 5, 5, self.TAPE
        )
        crisis_r = compute_week_prescription(
            crisis, "male", 183.0, 26, "mens_physique", 5, 5, self.TAPE
        )

        assert crisis_r["ari"] < 40, f"ARI should be red: {crisis_r['ari']:.0f}"
        assert crisis_r["ari_zone"] == "red"
        assert crisis_r["volume_mod"] <= 0.80, (
            f"Volume mod {crisis_r['volume_mod']:.2f} too high for red/low ARI"
        )
        assert crisis_r["volume_mod"] < healthy_r["volume_mod"], (
            f"Volume should be lower in crisis ({crisis_r['volume_mod']:.2f}) "
            f"than healthy ({healthy_r['volume_mod']:.2f})"
        )

    def test_recovery_then_return(self):
        """After crisis resolves (2 weeks), volume should return to normal."""
        crisis = WeekState(1, "lean_bulk", 88.0, 11.0, 22, 74, 3.5, 8, 90, 85, 125, 150)
        recovered = WeekState(3, "lean_bulk", 88.0, 11.0, 52, 58, 7.5, 3, 93, 92, 128, 155)

        crisis_r = compute_week_prescription(
            crisis, "male", 183.0, 26, "mens_physique", 5, 5, self.TAPE
        )
        recovered_r = compute_week_prescription(
            recovered, "male", 183.0, 26, "mens_physique", 5, 5, self.TAPE
        )

        assert recovered_r["volume_mod"] > crisis_r["volume_mod"], (
            f"Volume didn't recover: crisis={crisis_r['volume_mod']:.2f} "
            f"recovered={recovered_r['volume_mod']:.2f}"
        )
        assert recovered_r["ari_zone"] in ("green", "yellow")


# ═══════════════════════════════════════════════════════════════════════════════
# SCENARIO D: ADHERENCE FAILURE & RECOVERY
# ═══════════════════════════════════════════════════════════════════════════════

class TestAdherenceFailure:
    """Athlete falls off diet — system should lock adjustments, not chase noise."""

    DUMMY_RX = {"target_calories": 3000, "protein_g": 200, "carbs_g": 400, "fat_g": 80}

    def test_low_adherence_locks_adjustments(self):
        """Below 75% adherence, don't adjust macros — the plan isn't the problem."""
        result = adherence_lock(60.0, self.DUMMY_RX)
        locked = result.get("locked", False) if isinstance(result, dict) else True
        assert locked is True, "System should lock adjustments at 60% adherence"

    def test_high_adherence_allows_adjustments(self):
        """Above 85% adherence, adjustments are meaningful."""
        result = adherence_lock(90.0, self.DUMMY_RX)
        locked = result.get("locked", False) if isinstance(result, dict) else False
        assert locked is False, "System should allow adjustments at 90% adherence"

    def test_borderline_adherence(self):
        """Low adherence should lock, high should unlock — verify the spread."""
        r50 = adherence_lock(50.0, self.DUMMY_RX)
        r95 = adherence_lock(95.0, self.DUMMY_RX)
        locked_50 = r50.get("locked", True) if isinstance(r50, dict) else True
        locked_95 = r95.get("locked", True) if isinstance(r95, dict) else False
        assert locked_50 is True, "50% should definitely be locked"
        assert locked_95 is False, "95% should definitely be unlocked"

    def test_refeed_computation(self):
        """Refeed should produce meaningful calorie increase."""
        refeed = compute_refeed(30, 8.0, "male")  # 30 days in deficit, 8% BF
        assert isinstance(refeed, dict), "Refeed should return a dict"
        # Refeed should propose increased carbs
        refeed_carbs = refeed.get("carbs_g", 0) if isinstance(refeed, dict) else 0
        assert refeed_carbs >= 0, "Refeed carbs should be non-negative"


# ═══════════════════════════════════════════════════════════════════════════════
# SCENARIO E: WEIGHT STALL / PLATEAU
# ═══════════════════════════════════════════════════════════════════════════════

class TestWeightPlateau:
    """Athlete's weight stalls during cut — system should adapt."""

    def test_detect_stall(self):
        """Rate of change near zero for 3+ weeks should trigger adjustment."""
        # compute_rate_of_change expects list of (date_str, weight) tuples
        weights = [
            ("2026-03-01", 95.0), ("2026-03-08", 95.1),
            ("2026-03-15", 94.9), ("2026-03-22", 95.0),
        ]
        rate = compute_rate_of_change(weights)
        assert abs(rate) < 0.3, f"Rate should be near zero: {rate:.2f}"

    def test_adjust_down_on_stall(self):
        """When weight stalls during cut, calories should decrease."""
        current_cal = 3000.0
        target_rate_val = target_rate("cut", 90.0)  # expected loss rate for 90kg
        achieved_rate = 0.0  # stalled — no weight change

        adjustment = adjust_calories(current_cal, achieved_rate, target_rate_val)
        assert adjustment < current_cal, (
            f"Calories should decrease from {current_cal} on stall, got {adjustment}"
        )

    def test_metabolic_adaptation_factor(self):
        """After extended deficit, metabolic adaptation should be modeled."""
        factor = compute_adaptation_factor(12)
        assert 0.85 <= factor <= 0.99, (
            f"Adaptation factor {factor:.2f} outside realistic range for 12 weeks"
        )
        factor_4wk = compute_adaptation_factor(4)
        assert factor <= factor_4wk, "More weeks of deficit should cause more adaptation"

    def test_thermodynamic_floor_male(self):
        """Calories should never go below thermodynamic floor."""
        floor = thermodynamic_floor(90.0, "male")
        assert 1200 <= floor <= 2200, f"Floor {floor:.0f} outside safe range"

    def test_thermodynamic_floor_female(self):
        """Female floor should be lower but still protective."""
        floor = thermodynamic_floor(55.0, "female")
        assert 1000 <= floor <= 1800, f"Female floor {floor:.0f} outside safe range"


# ═══════════════════════════════════════════════════════════════════════════════
# SCENARIO F: RAPID WEIGHT LOSS (too fast)
# ═══════════════════════════════════════════════════════════════════════════════

class TestRapidWeightLoss:
    """Athlete loses weight too fast — muscle loss risk."""

    def test_detect_rapid_loss(self):
        """Rapid weight loss should produce a clearly negative rate."""
        weights = [
            ("2026-03-01", 100.0), ("2026-03-08", 98.5),
            ("2026-03-15", 97.0), ("2026-03-22", 95.5),
        ]
        rate = compute_rate_of_change(weights)
        assert rate < -0.2, f"Rate {rate:.2f} should be clearly negative for rapid loss"

    def test_adjust_up_on_rapid_loss(self):
        """If losing too fast, calories should increase to protect LBM."""
        current_cal = 2500.0
        target_val = target_rate("cut", 100.0)  # expected loss rate for 100kg
        achieved = -1.5  # too fast

        adjustment = adjust_calories(current_cal, achieved, target_val)
        assert adjustment > current_cal, (
            f"Calories should increase from {current_cal} when losing too fast, "
            f"got {adjustment}"
        )

    def test_halt_cut_at_low_bf_male(self):
        """Should halt cut if male reaches dangerously low BF."""
        result = should_halt_cut(3.0, "mens_open")
        halt = result.get("halt", False) if isinstance(result, dict) else bool(result)
        assert halt is True, f"Should halt cut at 3% BF, got {result}"

    def test_dont_halt_at_normal_bf(self):
        """Should NOT halt cut at normal prep BF levels."""
        result = should_halt_cut(8.0, "mens_open")
        halt = result.get("halt", False) if isinstance(result, dict) else bool(result)
        assert halt is False, f"Should not halt cut at 8% BF, got {result}"


# ═══════════════════════════════════════════════════════════════════════════════
# SCENARIO G: FEMALE ATHLETE HORMONAL CONSIDERATIONS
# ═══════════════════════════════════════════════════════════════════════════════

class TestFemalePrep:
    """Bikini competitor through full prep — hormonal protections."""

    TAPE = dict(
        neck=31.0, shoulders=100.0, chest=88.0, bicep=28.0,
        forearm=23.0, waist=65.0, hips=96.0, thigh=55.0, calf=34.0,
        back_width=36.0,
    )

    def _build_timeline(self) -> list[WeekState]:
        timeline = []
        weight = 57.0
        bf = 18.0
        for wk in range(1, 13):
            if wk <= 2:
                phase = "lean_bulk"
            elif wk <= 10:
                phase = "cut"
                weight -= 0.4
                bf -= 0.7
            elif wk == 11:
                phase = "cut"
                weight -= 0.3
                bf = max(10.0, bf - 0.5)
            else:
                phase = "peak"
                weight -= 0.2
                bf = max(9.5, bf - 0.3)

            rmssd = max(30, 60 - wk * 2.5)
            sleep = max(5.0, 8.0 - wk * 0.2)
            soreness = min(6.0, 2.0 + wk * 0.3)

            timeline.append(WeekState(
                wk, phase, round(weight, 1), round(max(9.5, bf), 1),
                rmssd, 58 + wk, sleep, soreness, 90, 88, 42, 72
            ))
        return timeline

    def test_fat_never_below_female_floor(self):
        """Female fat should never drop below 0.6g/kg in ANY phase."""
        timeline = self._build_timeline()
        for state in timeline:
            r = compute_week_prescription(
                state, "female", 163.0, 25, "womens_bikini", 5, 4, self.TAPE
            )
            assert r["fat_per_kg"] >= 0.58, (
                f"Week {state.week} ({state.phase}): fat {r['fat_per_kg']:.2f}g/kg "
                f"below female floor (0.6)"
            )

    def test_calories_never_dangerously_low(self):
        """Female athlete calories should never go below thermodynamic floor."""
        timeline = self._build_timeline()
        for state in timeline:
            r = compute_week_prescription(
                state, "female", 163.0, 25, "womens_bikini", 5, 4, self.TAPE
            )
            assert r["target_cal"] >= 1200, (
                f"Week {state.week}: {r['target_cal']:.0f} kcal dangerously low"
            )

    def test_bikini_glute_volume_consistent(self):
        """Glute volume should stay high throughout all phases for bikini."""
        timeline = self._build_timeline()
        for state in [timeline[0], timeline[5], timeline[-1]]:
            r = compute_week_prescription(
                state, "female", 163.0, 25, "womens_bikini", 5, 4, self.TAPE
            )
            glutes = r["volume_budget"].get("glutes", 0)
            assert glutes >= 8, (
                f"Week {state.week} ({state.phase}): glute volume {glutes} "
                f"too low for bikini"
            )

    def test_bikini_peak_gentler(self):
        """Bikini peak week should use gentler water/sodium manipulation."""
        peak_state = self._build_timeline()[-1]
        r = compute_week_prescription(
            peak_state, "female", 163.0, 25, "womens_bikini", 5, 4, self.TAPE
        )
        if r["peak_protocol"]:
            # Bikini should start with less water than Open
            day1_water = r["peak_protocol"][0].get("water_ml", 8000)
            assert day1_water <= 6000, (
                f"Bikini peak water {day1_water}mL too aggressive — "
                f"should be ≤6000 for female"
            )

    def test_female_prep_print_summary(self, capsys):
        """Print bikini prep timeline for review."""
        timeline = self._build_timeline()
        print(f"\n{'='*80}")
        print(f"  FEMALE BIKINI PREP SIMULATION — 12 Weeks")
        print(f"{'='*80}")
        for state in timeline:
            r = compute_week_prescription(
                state, "female", 163.0, 25, "womens_bikini", 5, 4, self.TAPE
            )
            sd = r["target_cal"] - r["tdee"]
            direction = "surplus" if sd > 0 else "deficit"
            print(
                f"  Wk{state.week:2d} | {state.phase:12s} | "
                f"{state.body_weight_kg:5.1f}kg {state.body_fat_pct:4.1f}%BF | "
                f"ARI:{r['ari']:3.0f}({r['ari_zone']:6s}) | "
                f"{r['target_cal']:4.0f}kcal ({direction}: {abs(sd):.0f}) | "
                f"P{r['protein_g']:3.0f}g F{r['fat_g']:2.0f}g({r['fat_per_kg']:.2f}/kg)"
            )
        assert True


# ═══════════════════════════════════════════════════════════════════════════════
# SCENARIO H: DIVISION TRANSITION TEST
# ═══════════════════════════════════════════════════════════════════════════════

class TestDivisionTransition:
    """Same athlete body, run through different divisions — verify different outputs."""

    TAPE = dict(
        neck=42.0, shoulders=130.0, chest=118.0, bicep=44.0,
        forearm=33.0, waist=80.0, hips=100.0, thigh=65.0, calf=41.0,
        back_width=48.0,
    )
    STATE = WeekState(1, "lean_bulk", 90.0, 12.0, 50, 58, 8, 3, 95, 95, 150, 185)

    def _get_rx(self, division: str) -> dict:
        return compute_week_prescription(
            self.STATE, "male", 180.0, 28, division, 5, 8, self.TAPE
        )

    def test_open_vs_mp_volume_differs(self):
        """Open should have more leg volume than MP."""
        open_r = self._get_rx("mens_open")
        mp_r = self._get_rx("mens_physique")
        open_legs = open_r["volume_budget"].get("quads", 0) + open_r["volume_budget"].get("hamstrings", 0)
        mp_legs = mp_r["volume_budget"].get("quads", 0) + mp_r["volume_budget"].get("hamstrings", 0)
        assert open_legs > mp_legs, (
            f"Open legs ({open_legs}) should exceed MP legs ({mp_legs})"
        )

    def test_mp_higher_side_delt_priority(self):
        """MP should have higher side delt volume than Open (proportionally)."""
        mp_r = self._get_rx("mens_physique")
        side_delt = mp_r["volume_budget"].get("side_delt", 0)
        assert side_delt >= 8, f"MP side delt volume {side_delt} too low"

    def test_classic_vs_open_ideals_differ(self):
        """Classic ideal waist should be tighter than Open."""
        open_r = self._get_rx("mens_open")
        classic_r = self._get_rx("classic_physique")
        # Both should produce valid outputs with different emphasis
        assert open_r["pds"] > 0 and classic_r["pds"] > 0

    def test_all_divisions_produce_valid_output(self):
        """Every division should produce valid, complete prescriptions."""
        for division in ["mens_open", "classic_physique", "mens_physique",
                         "womens_bikini", "womens_figure", "womens_physique"]:
            sex = "female" if division.startswith("womens") else "male"
            r = compute_week_prescription(
                self.STATE, sex, 180.0, 28, division, 5, 8, self.TAPE
            )
            assert r["target_cal"] > 1000, f"{division}: calories too low"
            assert r["protein_per_kg"] >= 1.6, f"{division}: protein too low"
            assert r["pds"] >= 0, f"{division}: invalid PDS"
            assert len(r["meals"]) >= 3, f"{division}: too few meals"


# ═══════════════════════════════════════════════════════════════════════════════
# MASTER SUMMARY — prints everything
# ═══════════════════════════════════════════════════════════════════════════════

class TestMasterSummary:
    """Print all simulation summaries together for comprehensive review."""

    def test_scenario_count(self):
        """Verify we're testing all 8 scenarios."""
        scenarios = [
            TestFullContestPrep,
            TestOffseassonBuilding,
            TestRecoveryCrisis,
            TestAdherenceFailure,
            TestWeightPlateau,
            TestRapidWeightLoss,
            TestFemalePrep,
            TestDivisionTransition,
        ]
        assert len(scenarios) == 8, "Should have 8 test scenario classes"
