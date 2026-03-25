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
    if days_out <= 1:
        return "contest"
    if days_out <= 21:       # ≤ 3 weeks out
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


def generate_annual_calendar(
    competition_date: date,
    current_date: date | None = None,
) -> list[dict]:
    """
    Generate a full annual phase calendar anchored to 52 weeks before
    the competition and forward into restoration.
    """
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

    # 3. Cut: start at max(ref, 12w out), end at 3w out
    cut_start = max(ref, comp - timedelta(weeks=12))
    cut_end = comp - timedelta(weeks=3) - timedelta(days=1)
    if cut_start < cut_end:
        calendar.append({
            "phase": "cut",
            "start_date": cut_start.isoformat(),
            "end_date": cut_end.isoformat(),
            "weeks": (cut_end - cut_start).days // 7,
            "recommended_meso_weeks": 4,
            "description": "Caloric deficit to achieve contest conditioning while retaining muscle.",
        })

    # 4. Peak week: start at max(ref, 3w out), end at comp-1d
    peak_start = max(ref, comp - timedelta(weeks=3))
    peak_end = comp - timedelta(days=1)
    if peak_start <= peak_end:
        calendar.append({
            "phase": "peak_week",
            "start_date": peak_start.isoformat(),
            "end_date": peak_end.isoformat(),
            "weeks": (peak_end - peak_start).days // 7 + 1,
            "recommended_meso_weeks": 2,
            "description": "Final manipulation of water, carbs, and sodium for stage appearance.",
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
