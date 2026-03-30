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


# Weeks remaining → phase boundary thresholds
_OFFSEASON_MIN_WEEKS = 20
_LEAN_BULK_MIN_WEEKS = 12
_CUT_MIN_WEEKS = 3
_PEAK_MIN_WEEKS = 0


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
    if days_out <= 84:       # ≤ 12 weeks out
        return "cut"
    if days_out <= 140:      # ≤ 20 weeks out
        return "lean_bulk"

    # For long preps (> 20 weeks out), insert mini-cut phases every 16 weeks
    # of offseason growth to resensitize insulin and prevent excessive adiposity
    if days_out > 140:
        weeks_out_val = days_out // 7
        # Calculate which 16-week block we're in (counting backward from cut start)
        weeks_into_offseason = weeks_out_val - 20  # weeks before lean_bulk starts
        block_position = weeks_into_offseason % 20  # 16 weeks bulk + 4 weeks mini-cut
        if block_position < 4:
            return "mini_cut"

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

    # Account for ~15-20% lean tissue loss during a cut (conservative estimate)
    # Total weight loss ≈ fat_to_lose / 0.82
    total_weight_to_lose = fat_to_lose_kg / 0.82
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

        # Recalculate BF% (assume 82% of loss is fat)
        fat_lost_this_week = weekly_loss * 0.82
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

        fat_lost = weekly_loss * 0.82
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

    # ── Determine how to split the available time ──

    if current_bf_pct <= target_bf + 1.0:
        # Already at or near stage condition — minimal cutting needed
        actual_cut_weeks = min(4, available_for_cut)  # light polish cut
        lean_bulk_weeks = max(0, available_for_cut - actual_cut_weeks)
        conditioning_note = "Near stage conditioning. Light deficit to dial in."
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
