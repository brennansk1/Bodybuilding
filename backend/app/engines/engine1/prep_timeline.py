"""
Competition Prep Timeline Engine

Determines the current prep phase based on weeks remaining until
competition day.  The phase auto-transitions drive nutrition, training
volume, and peak-week protocol activation.

Phase definitions
-----------------
offseason    — >20 weeks out: focus on building, permissive surplus
lean_bulk    — 13-20 weeks: controlled surplus, quality tissue gain
cut          — 4-12 weeks: caloric deficit, retain LBM
peak_week    — 1-3 weeks: precise manipulation (water, carbs, sodium)
contest      — show day ± 1 day
restoration  — 1-12 weeks post-show: reverse diet, metabolic recovery
"""

from __future__ import annotations

from datetime import date, timedelta


# Weeks remaining → phase boundary thresholds.
# Ground Truth doc §7.1: elite Classic preps are 16-20 weeks of deficit
# (CBum now starts 20 weeks out; naturals need ≥24). Previous bounds (cut 4-12 wk)
# were too short. Extended to 3-20 weeks cut, 20-28 weeks lean bulk, >28 offseason.
_OFFSEASON_MIN_WEEKS = 28
_LEAN_BULK_MIN_WEEKS = 20
_CUT_MIN_WEEKS = 3
_PEAK_MIN_WEEKS = 0

# Day-boundary constants (derived from week thresholds).
_CUT_MAX_DAYS = _LEAN_BULK_MIN_WEEKS * 7       # ≤ 140 days → cut window
_LEAN_BULK_MAX_DAYS = _OFFSEASON_MIN_WEEKS * 7  # ≤ 196 days → lean-bulk window


def prep_phase_for_date(
    competition_date: date | None,
    current_date: date | None = None,
) -> str:
    """
    Determine the competition prep phase for a given current date.

    Args:
        competition_date: The target show/competition date. If ``None``
                          the athlete is assumed to be in the offseason.
        current_date: Reference date (defaults to ``date.today()``).

    Returns:
        Phase string: one of ``"offseason"``, ``"lean_bulk"``, ``"cut"``,
        ``"peak_week"``, ``"contest"``.
    """
    if competition_date is None:
        return "offseason"

    ref = current_date or date.today()
    days_out = (competition_date - ref).days

    if days_out < 0:
        days_past = abs(days_out)
        if days_past <= 84:  # 1-84 days (12 weeks) post-show
            return "restoration"
        return "offseason"   # past competition — new offseason
    if days_out == 0:
        return "contest"     # show day only
    if days_out <= 7:        # ≤ 1 week out — true peak week (7 days)
        return "peak_week"
    if days_out <= _CUT_MAX_DAYS:       # ≤ 20 weeks out → cut
        return "cut"
    if days_out <= _LEAN_BULK_MAX_DAYS: # ≤ 28 weeks out → lean bulk
        return "lean_bulk"

    # For long preps (> 28 weeks out), insert mini-cut phases every 16 weeks
    # of offseason growth to resensitize insulin and prevent excessive adiposity.
    if days_out > _LEAN_BULK_MAX_DAYS:
        weeks_out_val = days_out // 7
        weeks_into_offseason = weeks_out_val - _OFFSEASON_MIN_WEEKS
        block_position = weeks_into_offseason % 20  # 16 weeks bulk + 4 weeks mini-cut
        if block_position < 4:
            return "mini_cut"

    return "offseason"


# ---------------------------------------------------------------------------
# PPM (Perpetual Progression Mode) sub-phases
# ---------------------------------------------------------------------------
# 14-week improvement cycle (optionally extended with a 15-16 week mini-cut):
#   weeks 1–2   → ppm_assessment          (maintenance kcal)
#   weeks 3–10  → ppm_accumulation        (lean_bulk kcal, MEV → MAV_high)
#   weeks 11–12 → ppm_intensification     (lean_bulk kcal, MAV_high → MRV)
#   week 13     → ppm_deload              (maintenance, 50% volume)
#   week 14     → ppm_checkpoint          (maintenance, measurements)
#   weeks 15–16 → ppm_mini_cut (optional, only if checkpoint BF > 15%)
_PPM_PHASE_BY_WEEK: dict[range | int, str] = {}  # documentation only


def ppm_phase_for_week(cycle_week: int, mini_cut_active: bool = False) -> str:
    """Return the PPM sub-phase for a given 1-indexed cycle week.

    Audit-fix: when mini-cut is active, it is a **PREPEND** (weeks 1-2) so
    the athlete brings BF under their division offseason ceiling BEFORE
    running the 14-week improvement cycle. Previously the mini-cut was
    appended at W15-16, which meant the athlete accumulated for 14 weeks
    while getting fatter, then tried to cut in 2 — backwards.

    Layout with mini-cut active (16 weeks):
        W1-2   mini-cut (prepend)
        W3-4   assessment
        W5-12  accumulation
        W13-14 intensification
        W15    deload
        W16    checkpoint

    Layout without mini-cut (14 weeks):
        W1-2   assessment
        W3-10  accumulation
        W11-12 intensification
        W13    deload
        W14    checkpoint
    """
    if cycle_week < 1:
        return "ppm_assessment"

    if mini_cut_active:
        if cycle_week <= 2:
            return "ppm_mini_cut"
        if cycle_week <= 4:
            return "ppm_assessment"
        if cycle_week <= 12:
            return "ppm_accumulation"
        if cycle_week <= 14:
            return "ppm_intensification"
        if cycle_week == 15:
            return "ppm_deload"
        if cycle_week == 16:
            return "ppm_checkpoint"
        return "ppm_assessment"

    # Standard 14-week layout (no mini-cut needed)
    if cycle_week <= 2:
        return "ppm_assessment"
    if cycle_week <= 10:
        return "ppm_accumulation"
    if cycle_week <= 12:
        return "ppm_intensification"
    if cycle_week == 13:
        return "ppm_deload"
    if cycle_week == 14:
        return "ppm_checkpoint"
    return "ppm_assessment"


def get_current_phase(
    competition_date: date | None = None,
    current_date: date | None = None,
    *,
    ppm_enabled: bool = False,
    cycle_start_date: date | None = None,
    mini_cut_active: bool = False,
    # V3 — manual override + pre-cut enforcement
    nutrition_mode_override: str | None = None,
    current_bf_pct: float | None = None,
    sex: str = "male",
    division: str | None = None,
    # Kept for backwards compatibility only; PCT mode was removed in V3.1
    # because `training_status="enhanced"` already covers the programming
    # adjustments a PCT user needs. Any ``pct_mode_active=True`` is treated
    # as a no-op — do not propagate via Profile.pct_mode_active any more.
    pct_mode_active: bool = False,
) -> str:
    """Unified phase resolver (Ground Truth PPM doc §8.1, extended for V3).

    Resolution order:
    1. ``nutrition_mode_override`` set → return that override directly
       (``bulk`` / ``cut`` / ``maintain``).
    2. ``ppm_enabled`` + BF above divisional offseason ceiling (and the
       otherwise-resolved phase would be a surplus phase) → ``"ppm_pre_cut"``.
    3. ``competition_date`` set → delegate to ``prep_phase_for_date``.
    4. ``ppm_enabled`` + ``cycle_start_date`` → PPM sub-phase.
    5. Fallback → ``"offseason"``.
    """
    _ = pct_mode_active  # removed; accepted for backwards compat, ignored
    if nutrition_mode_override:
        return nutrition_mode_override

    # V3 extended-cut pre-phase. Fires when PPM is enabled AND BF is above
    # the divisional offseason ceiling, regardless of cycle state — a mid-
    # cycle bulker who is too fat should still be redirected to cut.
    # But only override if the otherwise-resolved phase is a SURPLUS phase
    # (bulk / lean_bulk / ppm_accumulation / ppm_intensification / offseason),
    # so we don't clobber a cut/mini-cut/peak the user is already running.
    def _needs_precut() -> bool:
        if not ppm_enabled or current_bf_pct is None:
            return False
        try:
            from app.constants.physio import offseason_bf_ceiling_for_division
            ceiling = offseason_bf_ceiling_for_division(division or "classic_physique", sex)
        except Exception:
            ceiling = 13.0 if sex == "male" else 22.0
        return current_bf_pct > ceiling + 2.0

    _SURPLUS_PHASES = {"offseason", "bulk", "lean_bulk", "ppm_accumulation",
                       "ppm_intensification", "ppm_assessment"}

    # Pre-cut gate when cycle hasn't started yet — fire immediately.
    if _needs_precut() and cycle_start_date is None:
        return "ppm_pre_cut"

    if competition_date is not None:
        return prep_phase_for_date(competition_date, current_date)

    if ppm_enabled and cycle_start_date is not None:
        ref = current_date or date.today()
        delta_days = (ref - cycle_start_date).days
        cycle_week = max(1, (delta_days // 7) + 1)
        phase = ppm_phase_for_week(cycle_week, mini_cut_active=mini_cut_active)
        # Mid-cycle override: if BF is high AND the phase would be a surplus,
        # swap to ppm_pre_cut. Leaves cut/deload/checkpoint phases alone.
        if _needs_precut() and phase in _SURPLUS_PHASES:
            return "ppm_pre_cut"
        return phase

    return "offseason"


def weeks_out(competition_date: date | None, current_date: date | None = None) -> int | None:
    """
    Return integer weeks remaining until competition, or None if no date set.
    Negative values mean the competition has passed.
    """
    if competition_date is None:
        return None
    ref = current_date or date.today()
    days = (competition_date - ref).days
    return days // 7


def phase_description(phase: str) -> dict:
    """
    Return a human-readable description and coaching cues for a phase.

    Returns:
        Dict with keys: ``label``, ``description``, ``nutrition_cue``,
        ``training_cue``, ``calorie_modifier`` (fraction applied to TDEE).
    """
    _DESCRIPTIONS = {
        "offseason": {
            "label": "Offseason",
            "description": "No competition on the horizon. Focus on building strength, size, and structural improvements.",
            "nutrition_cue": "Permissive surplus. Prioritise performance and progressive overload.",
            "training_cue": "Maximum volume and intensity. Prioritise lagging muscle groups.",
            "calorie_modifier": 1.15,
        },
        "lean_bulk": {
            "label": "Lean Bulk",
            "description": "Building phase with controlled surplus to minimise fat gain.",
            "nutrition_cue": "Modest +300-400 kcal surplus. Keep protein at 1.8-2.0 g/kg.",
            "training_cue": "Continue progressive overload. Begin tracking body composition closely.",
            "calorie_modifier": 1.10,
        },
        "mini_cut": {
            "label": "Mini-Cut",
            "description": (
                "4-week aggressive deficit to resensitize insulin response and clear metabolic "
                "fatigue from extended offseason growth. Prevents excessive adiposity during "
                "long preps and primes the body for subsequent anabolic surplus."
            ),
            "nutrition_cue": "500-700 kcal deficit. Protein at 2.4 g/kg to preserve muscle. Minimize cardio.",
            "training_cue": "Maintain intensity, reduce volume by 20%. Focus on strength retention.",
            "calorie_modifier": 0.82,
        },
        "cut": {
            "label": "Contest Prep — Cut",
            "description": "Caloric deficit to achieve contest conditioning while retaining muscle.",
            "nutrition_cue": "350-500 kcal deficit. Protein 2.2 g/kg. Carb cycle on training vs rest days.",
            "training_cue": "Maintain strength as long as possible. Reduce volume in the final weeks.",
            "calorie_modifier": 0.85,
        },
        "peak_week": {
            "label": "Peak Week",
            "description": "Final manipulation of water, carbs, and sodium to maximise stage appearance.",
            "nutrition_cue": "Follow peak-week protocol. High-carb load Thu-Sat. Watch sodium.",
            "training_cue": "Low volume, high pump work. No new heavy loading. Practise posing daily.",
            "calorie_modifier": 0.80,
        },
        "contest": {
            "label": "Contest Day",
            "description": "Show day. Stay hydrated, hit your peak carb load, and execute.",
            "nutrition_cue": "High-GI carbs 2-3 h pre-show. Small sodium-free meals.",
            "training_cue": "Light pump work 30-45 min before pre-judging. Conserve energy.",
            "calorie_modifier": 1.00,
        },
        "restoration": {
            "label": "Restoration",
            "description": "Post-show recovery phase. Reverse diet to restore metabolic rate and hormonal balance.",
            "nutrition_cue": "Reverse diet: increase calories by 100-150 kcal/week. Reintroduce foods gradually. Monitor biofeedback (sleep, energy, libido).",
            "training_cue": "Reduce intensity 20-30%. Focus on enjoyment and movement quality. No maximal loading for 2-3 weeks.",
            "calorie_modifier": 0.85,  # starting value; use restoration_calorie_modifier() for weekly ramp
        },
        # ── Perpetual Progression Mode sub-phases ──
        "ppm_assessment": {
            "label": "PPM — Assessment",
            "description": "Weeks 1-2 of a 14-week improvement cycle. Re-measure, re-photograph, re-test baselines before ramping volume.",
            "nutrition_cue": "Maintenance calories. Re-establish baseline TDEE before surplus.",
            "training_cue": "MEV volume, 2 RIR. No intensity techniques. Focus on movement quality.",
            "calorie_modifier": 1.00,
        },
        "ppm_accumulation": {
            "label": "PPM — Accumulation",
            "description": "Weeks 3-10 of the cycle. Progressive overload from MEV toward MAV-high. Primary growth phase.",
            "nutrition_cue": "+10% TDEE lean-bulk surplus. Protein 2.4 g/kg. Carb cycle on training days.",
            "training_cue": "Add 1-2 working sets per muscle weekly. Compound-led, isolation finishers.",
            "calorie_modifier": 1.10,
        },
        "ppm_intensification": {
            "label": "PPM — Intensification",
            "description": "Weeks 11-12. Push to MRV on priority muscles. Layer intensity techniques (FST-7, myo-reps, drop sets) on lagging groups.",
            "nutrition_cue": "Hold +10% surplus. Peri-workout carbs matter more than ever.",
            "training_cue": "RIR 1 on compounds, RIR 0 on isolations. Max FST-7 on cycle focus muscles.",
            "calorie_modifier": 1.10,
        },
        "ppm_deload": {
            "label": "PPM — Deload",
            "description": "Week 13. 50% volume, 60% loads. Clear accumulated fatigue before the checkpoint.",
            "nutrition_cue": "Drop back to maintenance. Keep protein elevated.",
            "training_cue": "Half the work sets, moderate loads. No intensity techniques.",
            "calorie_modifier": 1.00,
        },
        "ppm_checkpoint": {
            "label": "PPM — Checkpoint",
            "description": "Week 14. Full measurement battery + progress photos + tier readiness re-evaluation.",
            "nutrition_cue": "Maintenance. Full hydration ahead of measurements and photos.",
            "training_cue": "MEV + strength re-test. Establish next cycle's baseline.",
            "calorie_modifier": 1.00,
        },
        "ppm_mini_cut": {
            "label": "PPM — Mini-Cut",
            "description": "Optional weeks 15-16 — triggered when checkpoint BF > 15%. 2-week -20% deficit to resensitize insulin before the next cycle.",
            "nutrition_cue": "-20% TDEE deficit. Protein 2.8 g/kg to defend LBM.",
            "training_cue": "Hold intensity, reduce volume 15%. Strength retention focus.",
            "calorie_modifier": 0.80,
        },
        # V3 — extended pre-cut phase. Fires when PPM is enabled but starting
        # BF is above the divisional offseason ceiling. Sim finding: an athlete
        # at 22% BF targeting Classic should run a 6–12 month structured cut
        # BEFORE their first improvement cycle, not an accumulation block.
        "ppm_pre_cut": {
            "label": "PPM — Pre-Cut (Extended)",
            "description": (
                "Your starting body fat is above the divisional offseason ceiling. "
                "Run a 6-12 month structured cut to reach a productive bulking range "
                "before your first improvement cycle begins. Sim analysis shows this "
                "saves ~12 months vs. trying to accumulate while high-BF."
            ),
            "nutrition_cue": "-18% TDEE deficit. Protein 2.5 g/kg. 1–2 refeeds/week.",
            "training_cue": "Hold intensity, volume at MAV. Lagging-muscle specialization continues.",
            "calorie_modifier": 0.82,
        },
    }
    return _DESCRIPTIONS.get(phase, _DESCRIPTIONS["offseason"])


def restoration_calorie_modifier(weeks_post_show: int) -> float:
    """
    Compute the calorie modifier during the restoration phase.
    """
    clamped = max(0, min(weeks_post_show, 12))
    return round(0.85 + (0.15 * clamped / 12), 3)


def get_phase_config(phase: str) -> dict:
    """
    Return phase-specific configuration including recommended mesocycle length.
    """
    _CONFIGS = {
        "offseason":  {"recommended_meso_weeks": 6},
        "lean_bulk":  {"recommended_meso_weeks": 6},
        "mini_cut":   {"recommended_meso_weeks": 4},
        "cut":        {"recommended_meso_weeks": 4},
        "peak_week":  {"recommended_meso_weeks": 2},
        "contest":    {"recommended_meso_weeks": 1},
        "restoration": {"recommended_meso_weeks": 4},
        # PPM sub-phases map to their own recommended cycle-week duration.
        "ppm_assessment":      {"recommended_meso_weeks": 2},
        "ppm_accumulation":    {"recommended_meso_weeks": 8},
        "ppm_intensification": {"recommended_meso_weeks": 2},
        "ppm_deload":          {"recommended_meso_weeks": 1},
        "ppm_checkpoint":      {"recommended_meso_weeks": 1},
        "ppm_mini_cut":        {"recommended_meso_weeks": 2},
        "ppm_pre_cut":         {"recommended_meso_weeks": 6},
    }
    return _CONFIGS.get(phase, {"recommended_meso_weeks": 4})


# ─── Division Stage Body Fat Targets ─────────────────────────────────────────
# What a competitor needs to hit on stage day. These are realistic targets
# based on IFBB/NPC judging expectations — not the impossible 3% claims.

_STAGE_BF_TARGETS: dict[str, dict[str, float]] = {
    "male": {
        "mens_open": 4.5,
        "classic_physique": 5.0,
        "mens_physique": 6.0,
    },
    "female": {
        "womens_physique": 8.0,
        "womens_figure": 10.0,
        "womens_bikini": 12.0,
        "wellness": 12.0,
    },
}

_DEFAULT_STAGE_BF = {"male": 5.5, "female": 11.0}


def get_stage_bf_target(division: str, sex: str) -> float:
    """Return the target body fat % an athlete should hit on stage for their division."""
    sex_key = sex.strip().lower()
    targets = _STAGE_BF_TARGETS.get(sex_key, {})
    return targets.get(division, _DEFAULT_STAGE_BF.get(sex_key, 6.0))


# ─── Prep Duration Calculator ────────────────────────────────────────────────

def estimate_cut_duration(
    current_bf_pct: float,
    target_bf_pct: float,
    current_weight_kg: float,
    sex: str = "male",
) -> dict:
    """Estimate how many weeks of cutting are needed to reach target body fat.

    Uses a physiologically realistic model:
    - Fat loss rate: 0.5-1.0% of body weight per week (ISSN guidelines)
    - Leaner athletes lose slower (rate decreases as BF% drops)
    - Accounts for metabolic adaptation (5% slowdown per 4-week block)
    - Assumes ~80% of weight loss is fat, ~20% lean tissue (Heymsfield 2014)
    - Adds 2-week buffer for water retention fluctuations and stalls

    Returns dict with:
      weeks_needed, fat_kg_to_lose, projected_stage_weight,
      avg_loss_rate_kg_week, warnings[]
    """
    if current_bf_pct <= target_bf_pct:
        return {
            "weeks_needed": 0,
            "fat_kg_to_lose": 0.0,
            "projected_stage_weight": current_weight_kg,
            "avg_loss_rate_kg_week": 0.0,
            "warnings": [],
        }

    fat_mass = current_weight_kg * (current_bf_pct / 100.0)
    lean_mass = current_weight_kg - fat_mass
    target_fat_mass = lean_mass / (1.0 - target_bf_pct / 100.0) * (target_bf_pct / 100.0)
    fat_to_lose_kg = fat_mass - target_fat_mass

    # Lean tissue loss during a coached cut with adequate protein (≥2.0 g/kg)
    # and resistance training is ~10-12% of total weight loss (Helms et al. 2014).
    # Suboptimal protein produces ~18% lean loss. Default to the coached ratio
    # since this system prescribes adequate protein for all athletes.
    _FAT_LOSS_RATIO = 0.88  # 88% of weight lost is fat, 12% lean
    total_weight_to_lose = fat_to_lose_kg / _FAT_LOSS_RATIO
    projected_stage_weight = current_weight_kg - total_weight_to_lose

    # Simulate week-by-week loss with adaptation
    weeks = 0
    sim_weight = current_weight_kg
    sim_bf = current_bf_pct
    total_lost = 0.0

    while sim_bf > target_bf_pct and weeks < 52:
        weeks += 1

        # Rate scales with current BF% — leaner = slower loss
        # Above 15% BF: can lose 0.8-1.0% BW/week safely
        # 10-15% BF: 0.5-0.7% BW/week
        # Below 10% BF: 0.3-0.5% BW/week (muscle preservation critical)
        if sim_bf > 15:
            rate_pct = 0.85
        elif sim_bf > 10:
            rate_pct = 0.60
        elif sim_bf > 7:
            rate_pct = 0.45
        else:
            rate_pct = 0.35

        # Metabolic adaptation: every 4 weeks, effective rate drops 5%
        adaptation_blocks = min(4, weeks // 4)
        adaptation = 1.0 - 0.05 * adaptation_blocks

        weekly_loss = sim_weight * (rate_pct / 100.0) * adaptation
        sim_weight -= weekly_loss
        total_lost += weekly_loss

        # Recalculate BF% (88% of loss is fat with coached protein/training)
        fat_lost_this_week = weekly_loss * _FAT_LOSS_RATIO
        sim_fat = sim_weight * (sim_bf / 100.0) - fat_lost_this_week
        sim_bf = max(target_bf_pct, (sim_fat / sim_weight) * 100.0) if sim_weight > 0 else target_bf_pct

    # Add 2-week buffer for water fluctuations, stalls, and diet breaks
    buffer_weeks = 2
    total_weeks = weeks + buffer_weeks
    avg_rate = total_lost / max(1, weeks)

    warnings = []
    if total_weeks > 24:
        warnings.append(
            f"Extended prep ({total_weeks} weeks). Consider a bulk/mini-cut cycle "
            f"before starting contest prep to avoid metabolic damage."
        )
    if current_bf_pct > 20 and sex == "male":
        warnings.append(
            "Starting above 20% BF. A 4-6 week mini-cut before committing "
            "to full prep will improve insulin sensitivity and make the cut more effective."
        )
    if current_bf_pct > 28 and sex == "female":
        warnings.append(
            "Starting above 28% BF. Consider a gradual cut phase before full contest prep."
        )

    return {
        "weeks_needed": total_weeks,
        "cut_weeks": weeks,
        "buffer_weeks": buffer_weeks,
        "fat_kg_to_lose": round(fat_to_lose_kg, 1),
        "total_weight_to_lose_kg": round(total_weight_to_lose, 1),
        "projected_stage_weight": round(projected_stage_weight, 1),
        "avg_loss_rate_kg_week": round(avg_rate, 2),
        "warnings": warnings,
    }


def _simulate_cut_to_deadline(
    current_bf_pct: float,
    target_bf_pct: float,
    current_weight_kg: float,
    available_weeks: int,
) -> dict:
    """Simulate a cut over a fixed number of weeks and report where BF% lands.

    Used when the ideal cut duration exceeds the available time — the show
    date is fixed so we cut as hard as is safe and report the projected
    stage condition.
    """
    sim_weight = current_weight_kg
    sim_bf = current_bf_pct
    total_lost = 0.0

    for week in range(1, available_weeks + 1):
        if sim_bf <= target_bf_pct:
            break
        # Same rate model as estimate_cut_duration
        if sim_bf > 15:
            rate_pct = 0.85
        elif sim_bf > 10:
            rate_pct = 0.60
        elif sim_bf > 7:
            rate_pct = 0.45
        else:
            rate_pct = 0.35

        adaptation_blocks = min(4, week // 4)
        adaptation = 1.0 - 0.05 * adaptation_blocks
        weekly_loss = sim_weight * (rate_pct / 100.0) * adaptation
        sim_weight -= weekly_loss
        total_lost += weekly_loss

        fat_lost = weekly_loss * 0.88
        sim_fat = sim_weight * (sim_bf / 100.0) - fat_lost
        sim_bf = max(target_bf_pct, (sim_fat / sim_weight) * 100.0) if sim_weight > 0 else target_bf_pct

    return {
        "projected_bf_pct": round(sim_bf, 1),
        "projected_weight_kg": round(sim_weight, 1),
        "total_lost_kg": round(total_lost, 1),
        "reached_target": sim_bf <= target_bf_pct + 0.5,
    }


def compute_smart_phase_plan(
    competition_date: date,
    current_bf_pct: float,
    current_weight_kg: float,
    sex: str = "male",
    division: str = "classic_physique",
    muscle_adequacy_pct: float = 75.0,
    current_date: date | None = None,
) -> dict:
    """Generate an optimized phase plan for a FIXED competition date.

    The show date never moves. The plan adapts to the available time:
    - If there's enough time: lean bulk → cut → peak → show
    - If time is tight: cut starts immediately, shorter than ideal
    - If time is very short: aggressive cut, may not hit ideal BF%
    - Always includes peak week (7 days) and restoration (12 weeks post)

    The coach's job is to get the athlete as close to stage-ready as
    possible within the available timeline, not to delay the show.
    """
    ref = current_date or date.today()
    total_days = (competition_date - ref).days
    total_weeks = max(0, total_days // 7)

    target_bf = get_stage_bf_target(division, sex)
    ideal_cut = estimate_cut_duration(current_bf_pct, target_bf, current_weight_kg, sex)
    ideal_cut_weeks = ideal_cut["weeks_needed"]

    # Fixed durations
    peak_weeks = 1  # 7 days

    # Available cutting weeks (total minus peak week)
    available_for_cut = max(0, total_weeks - peak_weeks)

    warnings: list[str] = []

    # ── Body fat threshold for bulking ──
    # No Olympia-level coach would bulk an athlete above ~16% BF (male) or
    # ~25% BF (female).  Nutrient partitioning is poor at higher body fat —
    # surplus calories go disproportionately to fat rather than muscle.
    # The athlete must diet down first to improve insulin sensitivity and
    # growth partitioning before any surplus phase.
    _BULK_BF_CEILING = {"male": 16.0, "female": 25.0}
    bf_too_high_for_bulk = current_bf_pct > _BULK_BF_CEILING.get(sex, 16.0)

    # ── Determine how to split the available time ──

    if current_bf_pct <= target_bf + 1.0:
        # Already at or near stage condition — minimal cutting needed
        actual_cut_weeks = min(4, available_for_cut)  # light polish cut
        lean_bulk_weeks = max(0, available_for_cut - actual_cut_weeks)
        conditioning_note = "Near stage conditioning. Light deficit to dial in."
    elif bf_too_high_for_bulk:
        # Body fat too high for productive bulking — cut immediately.
        # The extra time allows a gentler, more sustainable deficit with
        # diet breaks, which better preserves muscle and metabolic rate.
        actual_cut_weeks = available_for_cut
        lean_bulk_weeks = 0
        conditioning_note = (
            f"Body fat ({current_bf_pct:.1f}%) is above the "
            f"{_BULK_BF_CEILING.get(sex, 16.0):.0f}% threshold for productive "
            f"bulking. Cutting immediately — the extended timeline allows a "
            f"gentler deficit with diet breaks for better muscle preservation."
        )
        warnings.append(
            f"Skipping lean bulk phase: {current_bf_pct:.1f}% BF exceeds the "
            f"{_BULK_BF_CEILING.get(sex, 16.0):.0f}% ceiling for nutrient "
            f"partitioning. Starting deficit immediately."
        )
    elif ideal_cut_weeks <= available_for_cut:
        # Ideal case: enough time for full cut + some lean bulk
        actual_cut_weeks = ideal_cut_weeks
        lean_bulk_weeks = available_for_cut - actual_cut_weeks
        conditioning_note = "Full prep timeline. On track for ideal conditioning."
    else:
        # Tight timeline: allocate all available time to cutting
        actual_cut_weeks = available_for_cut
        lean_bulk_weeks = 0

        # Simulate what BF% we'll actually reach
        sim = _simulate_cut_to_deadline(
            current_bf_pct, target_bf, current_weight_kg, actual_cut_weeks,
        )
        if sim["reached_target"]:
            conditioning_note = "Tight but achievable. Aggressive cut required."
        else:
            gap = sim["projected_bf_pct"] - target_bf
            conditioning_note = (
                f"Won't reach ideal {target_bf:.1f}% BF — projected stage condition "
                f"~{sim['projected_bf_pct']:.1f}% BF. Maximizing conditioning within "
                f"{actual_cut_weeks} weeks."
            )
            warnings.append(
                f"Ideal prep needs ~{ideal_cut_weeks} weeks but only {total_weeks} available. "
                f"Projected stage BF: ~{sim['projected_bf_pct']:.1f}% vs target {target_bf:.1f}%. "
                f"Will look {gap:.0f}% points softer than ideal — still competitive, "
                f"focus on posing and presentation to compensate."
            )

    # ── Build phase blocks ──
    phases: list[dict] = []

    # Contest day (fixed, non-negotiable)
    phases.append({
        "phase": "contest",
        "start_date": competition_date.isoformat(),
        "end_date": competition_date.isoformat(),
        "weeks": 0, "days": 1,
    })

    # Peak week (fixed 7 days before show)
    peak_end = competition_date - timedelta(days=1)
    peak_start = competition_date - timedelta(days=7)
    if total_weeks >= 1:
        phases.append({
            "phase": "peak_week",
            "start_date": max(ref, peak_start).isoformat(),
            "end_date": peak_end.isoformat(),
            "weeks": 1, "days": 7,
        })

    # Restoration (12 weeks post-show)
    rest_start = competition_date + timedelta(days=1)
    rest_end = competition_date + timedelta(weeks=12)
    phases.append({
        "phase": "restoration",
        "start_date": rest_start.isoformat(),
        "end_date": rest_end.isoformat(),
        "weeks": 12, "days": 84,
    })

    # Cut phase (working backward from peak week)
    if actual_cut_weeks > 0:
        cut_end = peak_start - timedelta(days=1)
        cut_start = cut_end - timedelta(weeks=actual_cut_weeks) + timedelta(days=1)
        phases.append({
            "phase": "cut",
            "start_date": max(ref, cut_start).isoformat(),
            "end_date": cut_end.isoformat(),
            "weeks": actual_cut_weeks,
            "days": actual_cut_weeks * 7,
        })

        # Lean bulk — fill remaining time before cut
        if lean_bulk_weeks >= 3:
            lb_start = ref
            lb_end = max(ref, cut_start) - timedelta(days=1)

            if lean_bulk_weeks > 20 and muscle_adequacy_pct < 70:
                # Long offseason: alternate 16w bulk + 4w mini-cut blocks
                block_start = lb_start
                while (lb_end - block_start).days >= 21:
                    bulk_end = min(block_start + timedelta(weeks=16) - timedelta(days=1), lb_end)
                    if (bulk_end - block_start).days >= 14:
                        phases.append({
                            "phase": "lean_bulk",
                            "start_date": block_start.isoformat(),
                            "end_date": bulk_end.isoformat(),
                            "weeks": (bulk_end - block_start).days // 7,
                            "days": (bulk_end - block_start).days,
                        })
                    mc_start = bulk_end + timedelta(days=1)
                    mc_end = min(mc_start + timedelta(weeks=4) - timedelta(days=1), lb_end)
                    if (mc_end - mc_start).days >= 14 and mc_start < lb_end:
                        phases.append({
                            "phase": "mini_cut",
                            "start_date": mc_start.isoformat(),
                            "end_date": mc_end.isoformat(),
                            "weeks": (mc_end - mc_start).days // 7,
                            "days": (mc_end - mc_start).days,
                        })
                        block_start = mc_end + timedelta(days=1)
                    else:
                        break
            else:
                if lb_end > lb_start:
                    phases.append({
                        "phase": "lean_bulk",
                        "start_date": lb_start.isoformat(),
                        "end_date": lb_end.isoformat(),
                        "weeks": lean_bulk_weeks,
                        "days": (lb_end - lb_start).days,
                    })

    # Sort chronologically
    phases.sort(key=lambda p: p["start_date"])

    phase_summary = " → ".join(
        f"{p['phase']}({p['weeks']}w)" for p in phases if p["phase"] != "restoration"
    )

    # Determine if we'll reach ideal conditioning
    ideal_conditioning = ideal_cut_weeks <= available_for_cut

    return {
        "ideal_conditioning": ideal_conditioning,
        "total_weeks_available": total_weeks,
        "ideal_cut_weeks": ideal_cut_weeks,
        "cut_weeks_allocated": actual_cut_weeks,
        "lean_bulk_weeks": lean_bulk_weeks if lean_bulk_weeks >= 3 else 0,
        "target_stage_bf_pct": target_bf,
        "current_bf_pct": current_bf_pct,
        "projected_stage_weight_kg": ideal_cut["projected_stage_weight"],
        "fat_to_lose_kg": ideal_cut["fat_kg_to_lose"],
        "conditioning_note": conditioning_note,
        "phase_plan": phases,
        "phase_summary": phase_summary,
        "warnings": warnings,
    }


def generate_annual_calendar(
    competition_date: date,
    current_date: date | None = None,
    current_bf_pct: float | None = None,
    current_weight_kg: float | None = None,
    sex: str = "male",
    division: str = "classic_physique",
    muscle_adequacy_pct: float = 75.0,
) -> list[dict]:
    """
    Generate a full annual phase calendar anchored to 52 weeks before
    the competition and forward into restoration.

    When *current_bf_pct* and *current_weight_kg* are provided, uses the
    smart phase planner to compute how long the cut actually needs to be
    based on the athlete's body composition. Otherwise falls back to the
    fixed threshold calendar (12w cut, 8w lean bulk).
    """
    # ── Smart calendar: use body composition data when available ──
    if current_bf_pct is not None and current_weight_kg is not None:
        plan = compute_smart_phase_plan(
            competition_date=competition_date,
            current_bf_pct=current_bf_pct,
            current_weight_kg=current_weight_kg,
            sex=sex,
            division=division,
            muscle_adequacy_pct=muscle_adequacy_pct,
            current_date=current_date,
        )
        # Convert the smart plan phases into the calendar format
        calendar = []
        for p in plan["phase_plan"]:
            desc_map = {
                "lean_bulk": "Controlled surplus to build quality tissue. Cut starts in {w} weeks.",
                "mini_cut": "4-week insulin resensitization. Maintain intensity, reduce volume 20%.",
                "cut": "Contest prep deficit: {fl}kg fat to lose over {w} weeks to reach {bf:.1f}% BF.",
                "peak_week": "Final 7-day manipulation of water, carbs, and sodium.",
                "contest": "Show day. Execute peak carb load and perform.",
                "restoration": "Reverse diet and metabolic recovery phase (12 weeks).",
            }
            desc = desc_map.get(p["phase"], "").format(
                w=p["weeks"],
                fl=plan.get("fat_to_lose_kg", 0),
                bf=plan.get("target_stage_bf_pct", 5.0),
            )
            calendar.append({
                "phase": p["phase"],
                "start_date": p["start_date"],
                "end_date": p["end_date"],
                "weeks": p["weeks"],
                "recommended_meso_weeks": get_phase_config(p["phase"])["recommended_meso_weeks"],
                "description": desc,
            })
        return calendar

    # ── Fallback: fixed threshold calendar (no body composition data) ──
    ref = current_date or date.today()
    comp = competition_date

    # Anchor the start to 52 weeks out (or today if comp is further than 1 year)
    start_anchor = min(ref, comp - timedelta(weeks=52))

    calendar: list[dict] = []

    # 1. Off-season with mini-cuts: from start_anchor to 20w out
    #    Insert 4-week mini-cut phases every 16 weeks of growth
    offseason_end = comp - timedelta(weeks=20) - timedelta(days=1)
    if start_anchor < offseason_end:
        offseason_weeks = (offseason_end - start_anchor).days // 7
        if offseason_weeks > 20:
            # Long offseason: break into 16-week bulk + 4-week mini-cut blocks
            block_start = start_anchor
            while block_start < offseason_end:
                bulk_end = min(block_start + timedelta(weeks=16) - timedelta(days=1), offseason_end)
                if block_start < bulk_end:
                    calendar.append({
                        "phase": "offseason",
                        "start_date": block_start.isoformat(),
                        "end_date": bulk_end.isoformat(),
                        "weeks": (bulk_end - block_start).days // 7,
                        "recommended_meso_weeks": 6,
                        "description": "Building phase. Focus on strength, size, and structural improvements.",
                    })
                mini_cut_start = bulk_end + timedelta(days=1)
                mini_cut_end = min(mini_cut_start + timedelta(weeks=4) - timedelta(days=1), offseason_end)
                if mini_cut_start < offseason_end and mini_cut_start < mini_cut_end:
                    calendar.append({
                        "phase": "mini_cut",
                        "start_date": mini_cut_start.isoformat(),
                        "end_date": mini_cut_end.isoformat(),
                        "weeks": (mini_cut_end - mini_cut_start).days // 7,
                        "recommended_meso_weeks": 4,
                        "description": (
                            "4-week mini-cut to resensitize insulin response "
                            "and manage body fat before next growth block."
                        ),
                    })
                block_start = mini_cut_end + timedelta(days=1)
        else:
            calendar.append({
                "phase": "offseason",
                "start_date": start_anchor.isoformat(),
                "end_date": offseason_end.isoformat(),
                "weeks": offseason_weeks,
                "recommended_meso_weeks": 6,
                "description": "Building phase. Focus on strength, size, and structural improvements.",
            })

    # 2. Lean bulk: start at max(ref, 20w out), end at 12w out
    lb_start = max(ref, comp - timedelta(weeks=20))
    lb_end = comp - timedelta(weeks=12) - timedelta(days=1)
    if lb_start < lb_end:
        calendar.append({
            "phase": "lean_bulk",
            "start_date": lb_start.isoformat(),
            "end_date": lb_end.isoformat(),
            "weeks": (lb_end - lb_start).days // 7,
            "recommended_meso_weeks": 6,
            "description": "Controlled surplus to build quality tissue while minimising fat gain.",
        })

    # 3. Cut: start at max(ref, 12w out), end at 1w out (day before peak week)
    cut_start = max(ref, comp - timedelta(weeks=12))
    cut_end = comp - timedelta(weeks=1) - timedelta(days=1)
    if cut_start < cut_end:
        calendar.append({
            "phase": "cut",
            "start_date": cut_start.isoformat(),
            "end_date": cut_end.isoformat(),
            "weeks": (cut_end - cut_start).days // 7,
            "recommended_meso_weeks": 4,
            "description": "Caloric deficit to achieve contest conditioning while retaining muscle.",
        })

    # 4. Peak week: final 7 days before show (Mon–Fri/Sat before stage)
    peak_start = max(ref, comp - timedelta(weeks=1))
    peak_end = comp - timedelta(days=1)
    if peak_start <= peak_end:
        calendar.append({
            "phase": "peak_week",
            "start_date": peak_start.isoformat(),
            "end_date": peak_end.isoformat(),
            "weeks": 1,
            "recommended_meso_weeks": 1,
            "description": "Final 7-day manipulation of water, carbs, and sodium for stage appearance.",
        })

    # 5. Contest day
    if ref <= comp:
        calendar.append({
            "phase": "contest",
            "start_date": comp.isoformat(),
            "end_date": comp.isoformat(),
            "weeks": 0,
            "recommended_meso_weeks": 1,
            "description": "Show day. Execute peak carb load and perform.",
        })

    # 6. Restoration: comp+1d to 12 weeks post
    rest_start = comp + timedelta(days=1)
    rest_end = comp + timedelta(weeks=12)
    if start_anchor < rest_end:
        # If we are already in restoration, we still show the block from its start
        calendar.append({
            "phase": "restoration",
            "start_date": rest_start.isoformat(),
            "end_date": rest_end.isoformat(),
            "weeks": 12,
            "recommended_meso_weeks": 4,
            "description": "Reverse diet and metabolic recovery phase.",
        })

    return calendar
