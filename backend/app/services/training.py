from __future__ import annotations

"""
Training Program Generation Service

Converts a TrainingProgram header into a full set of TrainingSession
and TrainingSet records for the entire mesocycle.

Key behaviours
--------------
- Split auto-selection based on muscle gap profile and recovery windows
- DUP periodization (heavy/moderate/light days) for optimal hypertrophy
- Phase-aware volume: cut phases auto-reduce volume 10-15%
- Equipment/injury filtering: respects user's available equipment and injury history
- Movement pattern diversity: ensures varied movement patterns per muscle
- CNS fatigue budget: prevents consecutive heavy compound sessions
- Exercise rotation across mesocycles
- Symmetry-driven unilateral preference
"""

import math
from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.training import (
    Exercise, StrengthBaseline, TrainingProgram, TrainingSession, TrainingSet, ARILog,
)
from app.models.diagnostic import HQILog
from app.models.measurement import TapeMeasurement
from app.engines.engine2.periodization import (
    generate_mesocycle, auto_select_split, _WEEKLY_SCHEDULE,
)
from app.engines.engine2.split_designer import design_split
from app.engines.engine2.resistance import (
    compute_weight_from_1rm, weight_increment_for_equipment,
    rep_range_for_load_type, estimate_seed_weight,
)
from app.engines.engine2.recovery import (
    get_recovery_window, can_train_muscle,
    compute_systemic_fatigue, check_daily_fatigue_budget,
)
from app.engines.engine2.biomechanical import (
    ensure_pattern_diversity, classify_exercise_pattern,
    classify_sub_region, REQUIRED_SUB_REGIONS,
)
from app.constants.exercise_priorities import get_exercise_priorities, gap_adjusted_cap


# ---------------------------------------------------------------------------
# Compound-before-isolation sequencing
# ---------------------------------------------------------------------------

# Enforce compound-before-isolation sequencing within each muscle
# to optimize CNS freshness for heavy lifts
def _compound_sort_key(exercise_entry):
    pattern = exercise_entry.get("movement_pattern", "isolation")
    # Compounds first (push, pull, squat, hinge), then isolation
    compound_patterns = {"push", "pull", "squat", "hinge", "press", "row", "compound"}
    if pattern.lower() in compound_patterns or "compound" in pattern.lower():
        return 0
    return 1


# ---------------------------------------------------------------------------
# Muscle label mapping: periodization template → DB primary_muscle
# ---------------------------------------------------------------------------

_MUSCLE_TO_DB: dict[str, str] = {
    "chest":      "chest",
    "front_delt": "front_delt",   # DB now has proper sub-group tagging
    "side_delt":  "side_delt",
    "rear_delt":  "rear_delt",
    "triceps":    "triceps",
    "back":       "back",
    "biceps":     "biceps",
    "quads":      "quads",
    "hamstrings": "hamstrings",
    "glutes":     "glutes",
    "calves":     "calves",
    "abs":        "abs",
    "traps":      "traps",
    "forearms":   "forearms",
}

# Division-specific exercise BANS — these exercises should NEVER appear in a
# program for the given division regardless of fallback scoring.
# This prevents the SFR fallback from selecting back-thickening or
# trap-building exercises that undermine the division's aesthetic goals.
_DIVISION_EXERCISE_BANS: dict[str, set[str]] = {
    "mens_physique": {
        # Hamstrings: no deadlifts (erector thickening destroys V-taper)
        "deadlift", "romanian deadlift", "sumo deadlift", "stiff-leg deadlift",
        "stiff leg deadlift", "good morning",
        # Back: no barbell rows or T-bar rows (thickness over width)
        "barbell row", "t-bar row", "t bar row", "reverse barbell row",
        "plate row", "pull-over", "pullover", "bent-arm barbell pull-over",
        "barbell pull-over",
        # Traps: no shrugs or trap builders (thick traps compress V-taper)
        "barbell shrug", "dumbbell shrug", "shrug", "farmer",
        "cage press", "rack pull",
        # Shoulders: no barbell pressing (spinal loading + trap activation)
        "military press", "standing barbell press", "behind-the-head",
        "overhead barbell press", "behind neck", "snatch-grip",
        "barbell shoulder press", "seated barbell",
        "bradford", "push-press", "clean and press",
        # Quads: no heavy barbell squats (spinal compression, waist thickening)
        "barbell back squat", "barbell squat", "barbell full squat",
        "front squat", "barbell bulgarian",
        # General: no olympic lifts (trap/erector development)
        "clean and jerk", "snatch", "jerk balance",
    },
}

# Session training order: bigger compound muscles first
_MUSCLE_ORDER = [
    "chest", "back", "quads", "hamstrings", "glutes",
    "shoulders", "biceps", "triceps", "forearms", "calves", "abs", "traps",
]

# Name keywords for shoulder sub-role filtering
_REAR_DELT_KEYWORDS = {"rear", "face", "reverse", "bent", "fly", "flye", "pull apart"}
_SIDE_DELT_KEYWORDS = {"lateral", "side raise", "upright"}

# Compound movement overflow coefficients: movement_pattern → {secondary_muscle: fraction}
_OVERFLOW: dict[str, dict[str, float]] = {
    "push":     {"triceps": 0.5, "shoulders": 0.3},
    "pull":     {"biceps": 0.5, "traps": 0.2},
    "squat":    {"glutes": 0.4, "hamstrings": 0.2},
    "hinge":    {"glutes": 0.5, "back": 0.2},
    "carry":    {"traps": 0.4, "forearms": 0.3},
    "compound": {"biceps": 0.25, "triceps": 0.25},
}

# Default weekly volume (sets) per muscle group when no Engine 1 data
DEFAULT_VOLUME: dict[str, int] = {
    "chest":      10,
    "back":       12,
    "quads":      10,
    "hamstrings": 8,
    "glutes":     6,
    "shoulders":  10,
    "biceps":     8,
    "triceps":    8,
    "calves":     6,
    "abs":        6,
    "traps":      4,
    "forearms":   4,
}

# Warm-up scheme: percentages of working weight × reps for each step
_WARMUP_SCHEME = [
    (0.40, 10),   # 40% × 10 reps
    (0.60, 5),    # 60% × 5 reps
    (0.75, 3),    # 75% × 3 reps
    (0.85, 1),    # 85% × 1 rep
]

# Muscles where bilateral asymmetry >5% triggers unilateral preference
_BILATERAL_PAIRS: dict[str, tuple[str, str]] = {
    "biceps":    ("left_bicep", "right_bicep"),
    "triceps":   ("left_bicep", "right_bicep"),   # approximate via arm
    "quads":     ("left_thigh", "right_thigh"),
    "hamstrings":("left_thigh", "right_thigh"),
    "calves":    ("left_calf", "right_calf"),
}

_UNILATERAL_KEYWORDS = {"dumbbell", "single", "unilateral", "one-arm", "one arm", "cable"}

# Phase-aware volume modifiers (cross-engine: E3 → E2)
# During caloric deficit, recovery is impaired — reduce training volume
_PHASE_VOLUME_MODIFIER: dict[str, float] = {
    "bulk": 1.0,
    "lean_bulk": 1.0,
    "offseason": 1.0,
    "maintain": 1.0,
    "cut": 0.85,        # -15% volume during cut
    "peak_week": 0.70,  # -30% volume during peak
    "contest": 0.50,    # minimal volume
    "restoration": 0.75,  # gradual ramp-back post-show
}

# Injury contraindication mapping: injury_area → exercise keywords to avoid
_INJURY_CONTRAINDICATIONS: dict[str, list[str]] = {
    "shoulder_impingement": ["behind neck", "upright row", "behind the neck", "overhead press"],
    "shoulder": ["behind neck", "upright row"],
    "lower_back": ["deadlift", "good morning", "barbell row", "bent over"],
    "knee": ["deep squat", "sissy squat", "leg extension"],
    "elbow": ["skull crusher", "close grip", "dip"],
    "wrist": ["barbell curl", "reverse curl"],
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _equipment_tier(equipment: str) -> int:
    """Lower = higher priority (compounds first)."""
    eq = equipment.lower()
    if "barbell" in eq:  return 0
    if "dumbbell" in eq: return 1
    if "cable" in eq:    return 2
    if "e_z" in eq:      return 3
    if "machine" in eq:  return 4
    if "body" in eq:     return 5
    return 6


def _rep_range(position: int, equipment: str, load_type: str = "", exercise_name: str = "") -> tuple[int, int]:
    """Return (rep_min, rep_max) using load_type when available, else equipment fallback."""
    if load_type:
        return rep_range_for_load_type(load_type, position, exercise_name)
    # Legacy fallback for exercises not in priority cascade
    eq = equipment.lower()
    if position == 0 and "barbell" in eq:
        return 5, 8
    if position <= 1 and ("barbell" in eq or "dumbbell" in eq):
        return 8, 12
    if "cable" in eq or "e_z" in eq:
        return 10, 15
    return 12, 15


def _filter_rear_delt(exercises: list) -> list:
    preferred = [e for e in exercises if any(w in e.name.lower() for w in _REAR_DELT_KEYWORDS)]
    rest = [e for e in exercises if e not in preferred]
    return preferred + rest


def _filter_side_delt(exercises: list) -> list:
    preferred = [e for e in exercises if any(w in e.name.lower() for w in _SIDE_DELT_KEYWORDS)]
    rest = [e for e in exercises if e not in preferred]
    return preferred + rest


def _is_unilateral(exercise) -> bool:
    eq = exercise.equipment.lower()
    name = exercise.name.lower()
    return any(kw in eq or kw in name for kw in _UNILATERAL_KEYWORDS)


def _compute_warmup_sets(working_weight: float | None) -> list[dict]:
    """Return warm-up set specs for the first exercise of a muscle group."""
    if not working_weight or working_weight <= 0:
        return []
    return [
        {
            "warmup": True,
            "weight_kg": round(working_weight * pct, 1),
            "reps": reps,
        }
        for pct, reps in _WARMUP_SCHEME
    ]


def _allocate_sets(
    exercises: list,
    total_sets: int,
    delt_role: str | None,
    priority: float = 5.0,
    prefer_unilateral: bool = False,
    prev_mesocycle_ids: set | None = None,
    division: str = "mens_open",
    muscle: str = "",
    hqi: float = 70.0,
    dup_rep_range: tuple[int, int] | None = None,
) -> list[tuple]:
    """
    Sequential Exercise Overflow Matrix — cascade total_sets through a
    division-specific priority list, filling each exercise to its max set
    cap before cascading to the next.

    Priority list is sourced from ``exercise_priorities.py`` and encodes
    each division's preferred exercise order per muscle group (e.g. Men's
    Physique chest starts at incline not flat; Women's Bikini glutes start
    at hip thrust not squat).

    Gap adjustment: for severely lagging muscles (low HQI) the top-priority
    exercise cap is raised so the most effective stimulus gets the most volume
    before cascading.

    Rotation: exercises used in the previous mesocycle are penalised 30% in
    the fallback scorer so they don't appear repeatedly across blocks.

    Unilateral preference: if tape shows >5% L/R asymmetry the fallback
    scoring promotes dumbbell/cable exercises.

    Returns list of (exercise, n_sets, rep_min, rep_max).
    """
    if not exercises or total_sets <= 0:
        return []

    prev_ids = prev_mesocycle_ids or set()

    # ----- Safety Patch: Olympic Lift Ban -------------------------------------
    _OLYMPIC_LIFTS = ("clean", "snatch", "jerk", "clean and", "power clean", "hang clean", "push press", "push jerk")
    candidates = [
        ex for ex in exercises 
        if not any(kw in ex.name.lower() for kw in _OLYMPIC_LIFTS)
    ]

    # ----- Apply delt sub-role filtering first --------------------------------
    if delt_role == "rear_delt":
        candidates = _filter_rear_delt(candidates)
    elif delt_role == "side_delt":
        candidates = _filter_side_delt(candidates)

    # ----- Build an exercise lookup by name -----------------------------------
    by_name: dict[str, object] = {ex.name.lower(): ex for ex in candidates}

    # ----- Division cascade ---------------------------------------------------
    priority_slots = get_exercise_priorities(division, muscle)
    result: list[tuple] = []
    remaining = total_sets
    used_ex_ids: set = set()

    for slot_idx, slot in enumerate(priority_slots):
        if remaining <= 0:
            break

        # Find the best matching exercise in candidates for this priority slot
        matched_ex = None
        for kw in slot["keywords"]:
            kw_lower = kw.lower()
            # Exact name match first
            if kw_lower in by_name:
                matched_ex = by_name[kw_lower]
                break
            # Substring match
            for ex in candidates:
                if ex.id not in used_ex_ids and kw_lower in ex.name.lower():
                    matched_ex = ex
                    break
            if matched_ex and matched_ex.id not in used_ex_ids:
                break
            matched_ex = None

        if matched_ex is None or matched_ex.id in used_ex_ids:
            continue

        # Apply gap-adjusted cap (top slot gets boosted for lagging muscles)
        cap = gap_adjusted_cap(slot["max_sets"], hqi, is_top_priority=(slot_idx == 0))
        n_sets = min(remaining, cap)
        if n_sets <= 0:
            continue

        pos = len(result)
        slot_load_type = slot.get("load_type", "")
        if slot_load_type:
            rep_min, rep_max = _rep_range(pos, matched_ex.equipment, slot_load_type, matched_ex.name)
        elif dup_rep_range:
            rep_min, rep_max = dup_rep_range
        else:
            rep_min, rep_max = _rep_range(pos, matched_ex.equipment)
        result.append((matched_ex, n_sets, rep_min, rep_max))
        remaining -= n_sets
        used_ex_ids.add(matched_ex.id)

    # ----- Fallback: biomechanical-SFR sort for any remaining sets -----------
    # (exercises not covered by the priority list, or when no priority list exists)
    
    # ----- Equipment Ratio Enforcement ----------------------------------------
    # For mens_open: if >40% of exercises already selected are barbell,
    # heavily penalize additional barbells in the fallback sort.
    barbell_count = sum(1 for ex, _, _, _ in result
                        if (getattr(ex, "equipment", "") or "").lower() == "barbell")
    total_ex_count = len(result)
    barbell_saturated = (
        division == "mens_open" 
        and total_ex_count > 0 
        and barbell_count / total_ex_count > 0.4
    )
    
    if remaining > 0:
        def _sort_key(e):
            eff = e.biomechanical_efficiency
            # Open Division SFR Bias Fix: Massive athletes require inherently more 
            # stabilization energy, drastically buffing the SFR of supported plates over barbells
            if division == "mens_open" and getattr(e, "equipment", "").lower() in ("machine", "cable", "plate_loaded"):
                eff = min(1.0, eff * 1.25)
                
            sfr = (eff / max(e.fatigue_ratio, 0.1)) * priority
            if e.id in prev_ids:
                sfr *= 0.70
            tier = _equipment_tier(e.equipment)
            if prefer_unilateral and _is_unilateral(e):
                tier = max(0, tier - 1)
            # If barbell ratio is already saturated, push barbells to the back
            if barbell_saturated and (getattr(e, "equipment", "") or "").lower() == "barbell":
                tier += 3
            return (tier, -sfr)

        fallback = sorted(
            [e for e in candidates if e.id not in used_ex_ids],
            key=_sort_key,
        )
        for fb_pos, ex in enumerate(fallback):
            if remaining <= 0:
                break
            n_sets = min(remaining, 4)
            pos = len(result) + fb_pos
            fb_load_type = getattr(ex, "load_type", "") or ""
            if fb_load_type:
                rep_min, rep_max = _rep_range(pos, ex.equipment, fb_load_type, ex.name)
            elif dup_rep_range:
                rep_min, rep_max = dup_rep_range
            else:
                rep_min, rep_max = _rep_range(pos, ex.equipment)
            result.append((ex, n_sets, rep_min, rep_max))
            remaining -= n_sets
            used_ex_ids.add(ex.id)

    # ----- Sub-Region Guarantee (BEFORE compound sort) --------------------------
    # Fix GEN-06: Must run before compound-before-isolation sort so that
    # sub-region swaps don't break compound ordering or overwrite the FST-7
    # exercise placed at the end of the list.
    required_regions = REQUIRED_SUB_REGIONS.get(muscle, [])
    if required_regions and len(result) >= 2:
        # Classify current selections
        covered_regions: dict[str, list[int]] = {}
        for idx, (ex_obj, _, _, _) in enumerate(result):
            region = classify_sub_region(muscle, ex_obj.name)
            if region:
                covered_regions.setdefault(region, []).append(idx)

        missing = [r for r in required_regions if r not in covered_regions]
        if missing:
            # Find duplicate regions (regions with >1 exercise) to swap from
            duplicates = [(r, idxs) for r, idxs in covered_regions.items()
                          if len(idxs) > 1]
            duplicates.sort(key=lambda x: -len(x[1]))  # most duplicates first

            for missing_region in missing:
                if not duplicates:
                    break
                # Find best candidate exercise for the missing sub-region
                region_kws = {
                    "lateral": _SIDE_DELT_KEYWORDS,
                    "rear": _REAR_DELT_KEYWORDS,
                    "front": {"press", "overhead", "military", "front raise"},
                    "upper": {"incline"},
                    "lower": {"decline", "dip"},
                    "width": {"pulldown", "pull-up", "pullup", "lat"},
                    "thickness": {"row", "t-bar"},
                }.get(missing_region, set())

                swap_candidate = None
                for ex in candidates:
                    if ex.id in used_ex_ids:
                        continue
                    if any(kw in ex.name.lower() for kw in region_kws):
                        swap_candidate = ex
                        break

                if swap_candidate and duplicates:
                    # Swap out the last exercise from the most-duplicated region
                    dup_region, dup_idxs = duplicates[0]
                    swap_idx = dup_idxs[-1]
                    old_ex, old_sets, _, _ = result[swap_idx]
                    pos = swap_idx
                    rep_min, rep_max = _rep_range(pos, swap_candidate.equipment)
                    result[swap_idx] = (swap_candidate, old_sets, rep_min, rep_max)
                    used_ex_ids.discard(old_ex.id)
                    used_ex_ids.add(swap_candidate.id)
                    dup_idxs.pop()
                    if len(dup_idxs) <= 1:
                        duplicates.pop(0)

    # ----- Sort compounds before isolations within this muscle group ----------
    result.sort(key=lambda entry: _compound_sort_key({
        "movement_pattern": getattr(entry[0], "movement_pattern", "isolation") or "isolation",
    }))

    # FST-7 is now applied at session-level by _apply_session_fst7() after
    # all muscle groups have their exercises allocated. Removed from here to
    # prevent per-muscle FST-7 from interfering with session-level selection.

    return result


def _check_bilateral_asymmetry(tape: TapeMeasurement | None, db_muscle: str) -> bool:
    """Return True if this muscle has >5% bilateral asymmetry, warranting unilateral preference."""
    if not tape:
        return False
    pair = _BILATERAL_PAIRS.get(db_muscle)
    if not pair:
        return False
    left_val = getattr(tape, pair[0], None)
    right_val = getattr(tape, pair[1], None)
    if not left_val or not right_val or left_val <= 0 or right_val <= 0:
        return False
    avg = (left_val + right_val) / 2.0
    deviation = abs(left_val - right_val) / avg
    return deviation > 0.05  # >5% asymmetry


# ---------------------------------------------------------------------------
# FST-7 Protocol — Session-Level Application
# ---------------------------------------------------------------------------

# Division-specific muscles that qualify for FST-7 finishers.
# Ordered by priority — the engine picks the first match that also has
# the lowest HQI (most lagging) among muscles trained in this session.
_FST7_TARGETS: dict[str, list[str]] = {
    "mens_open":       ["chest", "back", "side_delt", "biceps", "calves", "hamstrings", "quads"],
    "mens_physique":   ["side_delt", "rear_delt", "back", "biceps", "triceps", "chest"],
    "classic_physique":["side_delt", "rear_delt", "biceps", "calves", "chest", "back", "quads"],
    "womens_bikini":   ["glutes", "hamstrings", "side_delt", "rear_delt"],
    "womens_figure":   ["side_delt", "rear_delt", "back", "glutes"],
    "womens_physique": ["side_delt", "back", "biceps", "hamstrings", "chest"],
    "wellness":        ["glutes", "hamstrings", "quads", "side_delt"],
}

# Preferred FST-7 finisher exercise per body part (from Hany Rambod's protocols).
# These are machine/cable isolations — the best implements for short-rest pump work.
_FST7_FINISHER_PREFERENCES: dict[str, list[str]] = {
    "chest":      ["pec deck", "cable fly", "machine fly"],
    "back":       ["straight-arm", "pulldown", "machine pullover"],
    "side_delt":  ["machine lateral raise", "cable lateral raise"],
    "rear_delt":  ["reverse pec deck", "cable face pull", "machine reverse fly"],
    "front_delt": ["machine shoulder press"],
    "quads":      ["leg extension", "leg press"],
    "hamstrings": ["seated leg curl", "lying leg curl"],
    "glutes":     ["hip abduction", "cable kickback", "machine kickback"],
    "biceps":     ["cable curl", "spider curl", "machine curl"],
    "triceps":    ["cable pushdown", "rope pushdown", "overhead cable"],
    "calves":     ["standing calf raise", "seated calf raise", "leg press calf"],
}

# FST-7 intensity by mode (from mesocycle week data)
_FST7_INTENSITY: dict[str, dict] = {
    "moderate":  {"rest_seconds": 45, "rir": 2, "reps": (10, 12)},  # Weeks 1-2
    "aggressive":{"rest_seconds": 35, "rir": 1, "reps": (8, 12)},   # Weeks 3-4
    "extreme":   {"rest_seconds": 30, "rir": 0, "reps": (8, 12)},   # Week 5
    "none":      {},  # Deload — no FST-7
}


def _compute_rest_seconds(
    movement_pattern: str,
    load_type: str,
    dup_profile: str = "moderate",
    is_warmup: bool = False,
) -> int:
    """
    Rest-time lookup: movement_pattern × load_type × DUP intensity.

    Heavy compound:   180–300s
    Moderate compound: 120–180s
    Heavy isolation:   90–120s
    Moderate isolation: 60–90s
    Warmup:           60s
    """
    if is_warmup:
        return 60

    pattern = (movement_pattern or "isolation").lower()
    is_compound = pattern in ("push", "pull", "squat", "hinge", "lunge", "carry")

    if is_compound:
        if dup_profile == "heavy":
            return 240  # 4 min — heavy compounds need full ATP recovery
        if dup_profile == "light":
            return 120  # 2 min — lighter loads recover faster
        return 180  # 3 min — moderate default
    else:
        # Isolation
        if dup_profile == "heavy":
            return 105  # ~1:45
        if dup_profile == "light":
            return 60   # 1 min
        return 90  # 1:30 — moderate default


def _apply_session_fst7(
    db_session,  # AsyncSession
    session,     # TrainingSession
    session_sets: list,  # list of (TrainingSet, exercise_name, muscle, equipment)
    fst7_mode: str,
    division: str,
    hqi_scores: dict[str, float],
) -> None:
    """
    Apply FST-7 protocol at the session level.

    Picks ONE exercise from the session to become the FST-7 finisher:
    1. Filter to division-priority muscles present in this session
    2. Rank by HQI (lowest = most lagging = highest priority)
    3. Find the best machine/cable isolation for that muscle
    4. Convert it to 7 FST-7 sets with mode-appropriate rest_seconds
    5. Mark all those sets with is_fst7=True

    Skips entirely if fst7_mode is "none" (deload weeks).
    """
    if fst7_mode == "none" or not session_sets:
        return

    intensity = _FST7_INTENSITY.get(fst7_mode, _FST7_INTENSITY["moderate"])
    if not intensity:
        return

    rest_sec = intensity["rest_seconds"]
    fst7_reps = intensity["reps"]

    # 1. Get division's FST-7 target muscles
    targets = _FST7_TARGETS.get(division, _FST7_TARGETS.get("mens_open", []))

    # 2. Find which target muscles are actually in this session
    session_muscles = set()
    for ts, ex_name, muscle, eq in session_sets:
        if not ts.is_warmup:
            session_muscles.add(muscle)

    eligible_muscles = [m for m in targets if m in session_muscles]
    if not eligible_muscles:
        return

    # 3. Rank by HQI — lowest score = most lagging = best FST-7 target
    eligible_muscles.sort(key=lambda m: hqi_scores.get(m, 70.0))
    chosen_muscle = eligible_muscles[0]

    # 4. Find the best machine/cable isolation exercise for that muscle
    finisher_prefs = _FST7_FINISHER_PREFERENCES.get(chosen_muscle, [])
    chosen_set = None
    chosen_ex_name = None

    # First pass: match against finisher preferences
    for ts, ex_name, muscle, eq in reversed(session_sets):
        if muscle != chosen_muscle or ts.is_warmup:
            continue
        eq_lower = (eq or "").lower()
        name_lower = ex_name.lower()
        if eq_lower not in ("machine", "cable", "dumbbell"):
            continue
        if any(pref in name_lower for pref in finisher_prefs):
            chosen_set = ts
            chosen_ex_name = ex_name
            break

    # Second pass: any machine/cable exercise for that muscle
    if not chosen_set:
        for ts, ex_name, muscle, eq in reversed(session_sets):
            if muscle != chosen_muscle or ts.is_warmup:
                continue
            eq_lower = (eq or "").lower()
            name_lower = ex_name.lower()
            if eq_lower in ("machine", "cable", "dumbbell") and "squat" not in name_lower and "deadlift" not in name_lower:
                chosen_set = ts
                chosen_ex_name = ex_name
                break

    if not chosen_set:
        return

    # 5. Convert all sets for this exercise to FST-7 protocol
    fst7_rep_target = (fst7_reps[0] + fst7_reps[1]) // 2
    fst7_sets_applied = 0
    for ts, ex_name, muscle, eq in session_sets:
        if ts.exercise_id == chosen_set.exercise_id and not ts.is_warmup:
            ts.is_fst7 = True
            ts.rest_seconds = rest_sec
            ts.prescribed_reps = fst7_rep_target
            fst7_sets_applied += 1

    # If the exercise has fewer than 7 sets, add more to reach 7
    sets_to_add = 7 - fst7_sets_applied
    if sets_to_add > 0:
        # Find the highest set_number in the session
        max_set_num = max(ts.set_number for ts, _, _, _ in session_sets)
        for i in range(sets_to_add):
            new_set = TrainingSet(
                session_id=session.id,
                exercise_id=chosen_set.exercise_id,
                set_number=max_set_num + 1 + i,
                prescribed_reps=fst7_rep_target,
                prescribed_weight_kg=chosen_set.prescribed_weight_kg,
                is_warmup=False,
                rest_seconds=rest_sec,
                is_fst7=True,
            )
            db_session.add(new_set)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def generate_program_sessions(
    db: AsyncSession,
    user_id,
    program: TrainingProgram,
    volume_allocation: dict[str, int],
    start_date: date,
) -> int:
    """
    Generate all TrainingSession + TrainingSet records for a mesocycle.

    The split type is auto-selected based on HQI gap scores and recovery
    constraints. The selected split is stored back on the program record.

    Returns the number of sessions created.
    """
    # -----------------------------------------------------------------------
    # 1. Load HQI scores for priority weights and auto-split selection
    # -----------------------------------------------------------------------
    muscle_priority: dict[str, float] = {}
    hqi_scores: dict[str, float] = {}
    hqi_gaps: dict[str, float] = {}
    hqi_result = await db.execute(
        select(HQILog).where(HQILog.user_id == user_id)
        .order_by(desc(HQILog.recorded_date), desc(HQILog.created_at)).limit(1)
    )
    latest_hqi = hqi_result.scalar_one_or_none()
    if latest_hqi and latest_hqi.site_scores:
        for k, v in latest_hqi.site_scores.items():
            k_lower = k.lower()
            if isinstance(v, dict):
                hqi_scores[k_lower] = float(v.get("pct_of_ideal", 70.0))
                hqi_gaps[k_lower] = max(0.0, float(v.get("gap_cm", 0.0)))
            else:
                hqi_scores[k_lower] = float(v)
                hqi_gaps[k_lower] = 0.0
        for site, score in hqi_scores.items():
            muscle_priority[site] = round(10.0 * (1.0 - score / 100.0), 1)

    # -----------------------------------------------------------------------
    # 2. Load profile (used for split design, division, preferences)
    # -----------------------------------------------------------------------
    from app.models.profile import UserProfile
    prof_result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == user_id)
    )
    profile = prof_result.scalar_one_or_none()
    user_division = getattr(profile, "division", "mens_open") or "mens_open"

    # Equipment and injury constraints
    available_equipment = getattr(profile, "available_equipment", None)
    disliked_exercises = set(
        (e.lower() for e in (getattr(profile, "disliked_exercises", None) or []))
    )
    injury_history = getattr(profile, "injury_history", None) or []
    active_injuries = [
        inj for inj in injury_history
        if isinstance(inj, dict) and inj.get("active", False)
    ]

    # Phase-aware volume modifier (cross-engine: E3 → E2)
    from app.engines.engine1.prep_timeline import prep_phase_for_date
    comp_date = getattr(profile, "competition_date", None)
    current_phase = prep_phase_for_date(comp_date)
    phase_volume_mod = _PHASE_VOLUME_MODIFIER.get(current_phase, 1.0)

    # -----------------------------------------------------------------------
    # 2b. Design custom split based on gap profile, division, and recovery
    # -----------------------------------------------------------------------
    custom_split_result = design_split(hqi_gaps, user_division, program.days_per_week)
    custom_template = custom_split_result["template"]
    selected_split = "custom"
    # Persist selected split back to the program record
    program.split_type = selected_split

    # -----------------------------------------------------------------------
    # 3. Load exercises and strength baselines
    # -----------------------------------------------------------------------
    ex_result = await db.execute(select(Exercise))
    all_exercises = ex_result.scalars().all()

    # Equipment normalization map — handles legacy names and user input variants
    _EQUIP_NORMALIZE: dict[str, str] = {
        "body_only": "bodyweight", "bodyweight": "bodyweight",
        "e_z_curl_bar": "ez_bar", "ez_bar": "ez_bar", "ez bar": "ez_bar",
        "kettlebells": "dumbbell", "kettlebell": "dumbbell",
        "bands": "bodyweight", "resistance band": "bodyweight",
        "none": "bodyweight",
        "barbell": "barbell", "dumbbell": "dumbbell", "cable": "cable",
        "machine": "machine", "smith_machine": "smith_machine",
        "smith machine": "smith_machine",
    }

    # Filter exercises by available equipment
    if available_equipment:
        equip_set = set(_EQUIP_NORMALIZE.get(e.lower(), e.lower()) for e in available_equipment)
        # Always allow bodyweight exercises
        equip_set.add("bodyweight")
        all_exercises = [
            ex for ex in all_exercises
            if _EQUIP_NORMALIZE.get(ex.equipment.lower(), ex.equipment.lower()) in equip_set
        ]

    # Filter out disliked exercises
    if disliked_exercises:
        all_exercises = [
            ex for ex in all_exercises
            if ex.name.lower() not in disliked_exercises
        ]

    # Filter out exercises contraindicated by active injuries
    if active_injuries:
        contraindicated_keywords = set()
        for inj in active_injuries:
            area = inj.get("area", "").lower()
            for key, keywords in _INJURY_CONTRAINDICATIONS.items():
                if key in area:
                    contraindicated_keywords.update(kw.lower() for kw in keywords)
            # Also check exercise-level contraindications
            contra_type = inj.get("type", "").lower()
            if contra_type:
                contraindicated_keywords.add(contra_type)

        if contraindicated_keywords:
            all_exercises = [
                ex for ex in all_exercises
                if not any(kw in ex.name.lower() for kw in contraindicated_keywords)
                and not (
                    hasattr(ex, 'contraindications') and ex.contraindications
                    and any(
                        inj.get("area", "").lower() in (c.lower() for c in ex.contraindications)
                        for inj in active_injuries
                    )
                )
            ]

    # Apply division-specific exercise bans
    div_bans = _DIVISION_EXERCISE_BANS.get(user_division, set())
    if div_bans:
        all_exercises = [
            ex for ex in all_exercises
            if not any(ban in ex.name.lower() for ban in div_bans)
        ]

    by_muscle: dict[str, list] = defaultdict(list)
    for ex in all_exercises:
        by_muscle[ex.primary_muscle].append(ex)

    bl_result = await db.execute(
        select(StrengthBaseline, Exercise.name)
        .join(Exercise, StrengthBaseline.exercise_id == Exercise.id)
        .where(StrengthBaseline.user_id == user_id)
        .order_by(desc(StrengthBaseline.recorded_date), desc(StrengthBaseline.created_at))
    )
    baselines: dict[str, float] = {}
    for bl, name in bl_result.all():
        k = name.lower()
        if k not in baselines:
            baselines[k] = bl.one_rm_kg

    # Load latest body weight for seed estimation (exercises without baselines)
    from app.models.measurement import BodyWeightLog
    bw_result = await db.execute(
        select(BodyWeightLog).where(BodyWeightLog.user_id == user_id)
        .order_by(desc(BodyWeightLog.recorded_date)).limit(1)
    )
    latest_bw = bw_result.scalar_one_or_none()
    user_body_weight_kg = latest_bw.weight_kg if latest_bw else 90.0  # fallback 90kg

    # Check if strength baselines are stale (>90 days old)
    # If stale, attempt to estimate current 1RM from recent training logs
    stale_baselines = False
    if baselines:
        latest_bl_result = await db.execute(
            select(StrengthBaseline)
            .where(StrengthBaseline.user_id == user_id)
            .order_by(desc(StrengthBaseline.recorded_date), desc(StrengthBaseline.created_at))
            .limit(1)
        )
        latest_bl = latest_bl_result.scalar_one_or_none()
        if latest_bl and (date.today() - latest_bl.recorded_date).days > 90:
            stale_baselines = True
            # Auto-estimate from recent training logs (Epley formula)
            from app.engines.engine2.resistance import estimate_1rm
            from app.models.training import StrengthLog
            recent_logs = await db.execute(
                select(StrengthLog, Exercise.name)
                .join(Exercise, StrengthLog.exercise_id == Exercise.id)
                .where(StrengthLog.user_id == user_id)
                .order_by(desc(StrengthLog.recorded_date), desc(StrengthLog.created_at))
                .limit(50)
            )
            for log, ex_name in recent_logs.all():
                k = ex_name.lower()
                if k not in baselines or True:  # always update with fresher data
                    est = estimate_1rm(log.weight_kg, log.reps)
                    if est and est > 0:
                        baselines[k] = est

    # -----------------------------------------------------------------------
    # 4. Load previous mesocycle exercise IDs and HQI map
    # -----------------------------------------------------------------------
    prev_mesocycle_ids: set = set()
    if profile and profile.preferences:
        prev_ids = profile.preferences.get("prev_mesocycle_exercise_ids", [])
        prev_mesocycle_ids = set(prev_ids)

    # Per-DB-muscle HQI lookup (for gap-adjusted set caps in cascade)
    # Maps DB muscle name → HQI score (0-100)
    _MUSCLE_HQI_MAP = {
        "chest":      hqi_scores.get("chest", 70.0),
        "back":       hqi_scores.get("back", 70.0),
        "shoulders":  hqi_scores.get("shoulders", 70.0),
        "quads":      hqi_scores.get("thigh", 70.0),
        "hamstrings": hqi_scores.get("thigh", 70.0),
        "glutes":     hqi_scores.get("hips", 70.0),
        "biceps":     hqi_scores.get("bicep", 70.0),
        "triceps":    hqi_scores.get("tricep", 70.0),
        "calves":     hqi_scores.get("calf", 70.0),
        "traps":      hqi_scores.get("neck", 70.0),
        "forearms":   hqi_scores.get("forearm", 70.0),
        "abs":        70.0,
    }

    # Per-DB-muscle gap_cm lookup — drives volume allocation
    # Bigger gap = more volume needed. Default gaps for unmeasured muscles.
    _UNMEASURED_GAP_DEFAULTS = {
        "back": 4.0,       # No tape measurement; always a priority
        "abs": 0.0,        # Not size-driven
    }
    _MUSCLE_GAP_MAP: dict[str, float] = {
        "chest":      hqi_gaps.get("chest", 3.0),
        "back":       hqi_gaps.get("back", _UNMEASURED_GAP_DEFAULTS.get("back", 4.0)),
        "shoulders":  hqi_gaps.get("shoulders", 3.0),
        "quads":      hqi_gaps.get("thigh", 3.0),
        "hamstrings": hqi_gaps.get("thigh", 3.0),
        "glutes":     hqi_gaps.get("hips", 3.0),
        "biceps":     hqi_gaps.get("bicep", 2.0),
        "triceps":    hqi_gaps.get("tricep", 2.0),
        "calves":     hqi_gaps.get("calf", 3.0),
        "traps":      hqi_gaps.get("neck", 3.0),
        "forearms":   hqi_gaps.get("forearm", 2.0),
        "abs":        2.0,  # always include abs — core stability for compounds
    }

    # Map delt sub-groups into the gap map so the split designer sees them
    shoulder_gap = hqi_gaps.get("shoulders", 3.0)
    _MUSCLE_GAP_MAP["front_delt"] = shoulder_gap * 0.6   # pressing covers most
    _MUSCLE_GAP_MAP["side_delt"] = shoulder_gap * 1.2    # prioritize — most visible
    _MUSCLE_GAP_MAP["rear_delt"] = shoulder_gap * 1.0    # back double biceps

    # Use the split designer's volume budget — it includes per-delt-head
    # volumes and all fine-grained muscle names that match the custom template
    volume_allocation = {**volume_allocation, **custom_split_result["volume_budget"]}

    # Apply phase-aware volume modifier (cross-engine: E3 → E2)
    # During cuts, reduce volume to account for impaired recovery from caloric deficit
    if phase_volume_mod != 1.0:
        volume_allocation = {
            k: max(2, round(v * phase_volume_mod))
            for k, v in volume_allocation.items()
        }

    # Also ensure DB-level muscle names are present (for _MUSCLE_TO_DB mapping)
    # "shoulders" = sum of delt heads, used by exercises with primary_muscle="shoulders"
    delt_vol = sum(
        volume_allocation.get(d, 0) for d in ("front_delt", "side_delt", "rear_delt")
    )
    if "shoulders" not in volume_allocation:
        volume_allocation["shoulders"] = delt_vol

    # -----------------------------------------------------------------------
    # 5. Load latest tape measurements for symmetry assessment
    # -----------------------------------------------------------------------
    tape_result = await db.execute(
        select(TapeMeasurement).where(TapeMeasurement.user_id == user_id)
        .order_by(desc(TapeMeasurement.recorded_date), desc(TapeMeasurement.created_at)).limit(1)
    )
    latest_tape = tape_result.scalar_one_or_none()

    # -----------------------------------------------------------------------
    # 6. Generate mesocycle structure
    # -----------------------------------------------------------------------
    # Select periodization strategy based on training experience
    training_exp = getattr(profile, "training_experience_years", 3) or 3
    if training_exp > 5:
        peri_type = "block"
    else:
        peri_type = "dup"

    # Query last 7 days of ARI scores for ARI-aware deload scheduling
    seven_days_ago = date.today() - timedelta(days=7)
    ari_result = await db.execute(
        select(ARILog)
        .where(ARILog.user_id == user_id, ARILog.recorded_date >= seven_days_ago)
        .order_by(ARILog.recorded_date)
    )
    recent_ari_logs = ari_result.scalars().all()
    avg_ari_per_week: list[float] | None = None
    if recent_ari_logs:
        avg_ari = sum(log.ari_score for log in recent_ari_logs) / len(recent_ari_logs)
        avg_ari_per_week = [avg_ari]

    mesocycle = generate_mesocycle(
        days_per_week=program.days_per_week,
        split_type=selected_split,
        volume_allocation=volume_allocation,
        week_count=program.mesocycle_weeks,
        custom_template=custom_template,
        periodization_type=peri_type,
        training_experience_years=training_exp,
        avg_ari_per_week=avg_ari_per_week,
    )

    # Find next Monday on or after start_date
    days_to_monday = (7 - start_date.weekday()) % 7
    week_start = start_date + timedelta(days=days_to_monday)

    day_offsets = _WEEKLY_SCHEDULE.get(program.days_per_week, [0, 2, 4])
    sessions_created = 0
    last_trained_date: dict[str, date] = {}
    this_mesocycle_exercise_ids: list[str] = []
    
    # Track systemic spillover (e.g. 35 sets of generated shoulders splits 12/12/11 across days)
    global_spillover: dict[str, int] = {}

    for week in mesocycle:
        week_num = week["week"]
        for day_idx, day in enumerate(week["days"]):
            offset = day_offsets[day_idx % len(day_offsets)]
            session_date = week_start + timedelta(days=offset)

            session_type = day["day_label"].split(" (")[0].lower().replace(" ", "_")
            session = TrainingSession(
                program_id=program.id,
                user_id=user_id,
                session_date=session_date,
                session_type=session_type,
                week_number=week_num,
                day_number=day_idx + 1,
                completed=False,
                split_type=selected_split,
                stale_baselines=stale_baselines,
                dup_profile=day.get("dup_profile"),
            )
            db.add(session)
            await db.flush()

            # Aggregate sets by DB muscle, tracking shoulder sub-roles
            db_muscle_info: dict[str, dict] = {}
            for peri_muscle in day["muscles"]:
                db_muscle = _MUSCLE_TO_DB.get(peri_muscle, peri_muscle)
                sets = day["sets_per_muscle"].get(peri_muscle, 0)
                if sets == 0:
                    continue
                if db_muscle not in db_muscle_info:
                    db_muscle_info[db_muscle] = {"total_sets": 0, "roles": []}
                db_muscle_info[db_muscle]["total_sets"] += sets
                db_muscle_info[db_muscle]["roles"].append(peri_muscle)

            ordered = sorted(
                db_muscle_info.keys(),
                key=lambda m: _MUSCLE_ORDER.index(m) if m in _MUSCLE_ORDER else 99,
            )

            # Track overflow volume accumulated within this session
            overflow_received: dict[str, float] = {}
            # Track which muscle groups have had their first exercise (for warm-up sets)
            first_exercise_done: set[str] = set()
            # Track exercises for CNS fatigue budget validation
            session_exercise_dicts: list[dict] = []

            set_number = 1
            for db_muscle in ordered:
                info = db_muscle_info[db_muscle]
                base_sets = info["total_sets"]
                roles = info["roles"]
                candidates = by_muscle.get(db_muscle, [])
                if not candidates:
                    continue

                # Recovery gating
                if db_muscle in last_trained_date:
                    hours_since = (session_date - last_trained_date[db_muscle]).total_seconds() / 3600
                    min_recovery, _ = get_recovery_window(db_muscle)
                    if not can_train_muscle(db_muscle, hours_since, min_recovery):
                        continue

                # Reduce sets by overflow received from earlier compounds
                overflow_sets = math.floor(overflow_received.get(db_muscle, 0))
                total_sets = max(2, base_sets - overflow_sets)

                # Inject systemic spillover rolled over from previous sessions
                if db_muscle in global_spillover and global_spillover[db_muscle] > 0:
                    total_sets += global_spillover[db_muscle]
                    global_spillover[db_muscle] = 0

                # -------------------------------------------------------------------
                # Rule 1 C: Hard Session Cap & Dynamic Spillover Routing
                # If total volume for this single muscle exceeds ~12 sets in ONE day,
                # forcefully cap it to 12. Take the remainder and carry it forward.
                # -------------------------------------------------------------------
                if total_sets > 12:
                    excess = total_sets - 12
                    global_spillover[db_muscle] = global_spillover.get(db_muscle, 0) + excess
                    total_sets = 12

                # --- Fix GEN-02: Delt sub-group lookup with fallback ----------
                # When db_muscle is a delt sub-group, pass the sub-role for
                # filtering AND fall back to generic "shoulders" pool if the
                # sub-group pool is empty.
                delt_role = None
                _DELT_SUB_GROUPS = {"front_delt", "side_delt", "rear_delt"}
                if db_muscle in _DELT_SUB_GROUPS:
                    delt_role = db_muscle
                    if not candidates:
                        candidates = by_muscle.get("shoulders", [])

                # --- Fix GEN-03: Read DUP profile from mesocycle output -------
                day_dup_profile = day.get("dup_profile", "moderate")
                day_intensity_range = day.get("intensity_range", (0.65, 0.75))
                day_rep_range = day.get("rep_range", (8, 12))

                # Priority (0-10) from HQI — default 5.0 (neutral)
                priority = muscle_priority.get(db_muscle, 5.0)

                # Unilateral preference for asymmetric muscles
                prefer_unilateral = _check_bilateral_asymmetry(latest_tape, db_muscle)

                assignments = _allocate_sets(
                    candidates,
                    total_sets,
                    delt_role,
                    priority=priority,
                    prefer_unilateral=prefer_unilateral,
                    prev_mesocycle_ids=prev_mesocycle_ids,
                    division=user_division,
                    muscle=db_muscle,
                    hqi=_MUSCLE_HQI_MAP.get(db_muscle, 70.0),
                    dup_rep_range=day_rep_range,
                )
                if assignments:
                    last_trained_date[db_muscle] = session_date

                # Movement pattern diversity check: identify missing patterns
                # and attempt to swap in an exercise that covers a missing pattern
                if assignments and db_muscle not in ("abs", "calves"):
                    selected_ex_dicts = [{"name": ex.name} for ex, _, _, _ in assignments]
                    missing_patterns = ensure_pattern_diversity(selected_ex_dicts, db_muscle)
                    if missing_patterns:
                        # Try to replace the last (lowest-priority) assignment with
                        # an exercise that covers the first missing pattern
                        for candidate_ex in candidates:
                            if candidate_ex.id in {ex.id for ex, _, _, _ in assignments}:
                                continue
                            ex_pattern = classify_exercise_pattern(candidate_ex.name)
                            if ex_pattern in missing_patterns:
                                # Swap last assignment for this exercise
                                last_ex, last_sets, last_rmin, last_rmax = assignments[-1]
                                assignments[-1] = (candidate_ex, last_sets, last_rmin, last_rmax)
                                break

                # Calf exercise variety: ensure at least 2 distinct exercises
                # (standing for gastrocnemius + seated for soleus) when volume allows
                if db_muscle == "calves" and len(assignments) == 1 and total_sets >= 4:
                    used_ids = {ex.id for ex, _, _, _ in assignments}
                    for cand in candidates:
                        if cand.id not in used_ids:
                            # Split sets: give half to each exercise
                            old_ex, old_sets, old_rmin, old_rmax = assignments[0]
                            split = max(2, old_sets // 2)
                            assignments[0] = (old_ex, old_sets - split, old_rmin, old_rmax)
                            assignments.append((cand, split, old_rmin, old_rmax))
                            break

                need_warmup = db_muscle not in first_exercise_done

                for ex, n_sets, rep_min, rep_max in assignments:
                    rep_target = (rep_min + rep_max) // 2
                    prescribed_weight = None
                    if ex.name.lower() in baselines:
                        prescribed_weight = round(
                            compute_weight_from_1rm(baselines[ex.name.lower()], rep_target), 1
                        )

                    # Seed weight fallback: if no 1RM baseline, estimate from body weight
                    if prescribed_weight is None and user_body_weight_kg > 0:
                        prescribed_weight = estimate_seed_weight(
                            user_body_weight_kg,
                            getattr(ex, "equipment", "barbell"),
                            db_muscle,
                            rep_target,
                        )

                    # --- Fix GEN-04: Scale weight by DUP intensity range ----------
                    # Heavy days use the top of the intensity range (heavier weight,
                    # lower reps), light days use the bottom (lighter weight, higher reps).
                    if prescribed_weight and day_intensity_range:
                        intensity_mid = (day_intensity_range[0] + day_intensity_range[1]) / 2
                        # Default moderate intensity is ~0.70. Scale weight relative to that.
                        intensity_scale = intensity_mid / 0.70
                        prescribed_weight = round(prescribed_weight * intensity_scale, 1)

                    # Compute rest_seconds from movement_pattern × DUP profile
                    ex_pattern = getattr(ex, "movement_pattern", "isolation") or "isolation"
                    ex_load_type = getattr(ex, "load_type", "") or ""
                    working_rest = _compute_rest_seconds(ex_pattern, ex_load_type, day_dup_profile)

                    # Warm-up sets for the first exercise per muscle group
                    if need_warmup and prescribed_weight:
                        for wu in _compute_warmup_sets(prescribed_weight):
                            ts_wu = TrainingSet(
                                session_id=session.id,
                                exercise_id=ex.id,
                                set_number=set_number,
                                prescribed_reps=wu["reps"],
                                prescribed_weight_kg=wu["weight_kg"],
                                is_warmup=True,
                                rest_seconds=60,
                            )
                            db.add(ts_wu)
                            set_number += 1
                        need_warmup = False
                        first_exercise_done.add(db_muscle)

                    for _ in range(n_sets):
                        ts = TrainingSet(
                            session_id=session.id,
                            exercise_id=ex.id,
                            set_number=set_number,
                            prescribed_reps=rep_target,
                            prescribed_weight_kg=prescribed_weight,
                            is_warmup=False,
                            rest_seconds=working_rest,
                        )
                        db.add(ts)
                        set_number += 1

                    this_mesocycle_exercise_ids.append(str(ex.id))

                    # Accumulate overflow from this exercise's movement pattern
                    pattern = (ex.movement_pattern or "").lower()
                    if pattern in _OVERFLOW:
                        for sec_muscle, coeff in _OVERFLOW[pattern].items():
                            overflow_received[sec_muscle] = (
                                overflow_received.get(sec_muscle, 0) + n_sets * coeff
                            )

                    # Collect for CNS fatigue budget check
                    session_exercise_dicts.append({
                        "movement_pattern": ex.movement_pattern or "isolation",
                        "sets": n_sets,
                        "rpe": 7.5,  # Default RPE estimate for prescribed sessions
                    })

            # CNS fatigue budget validation — annotate high-load sessions
            if session_exercise_dicts:
                fatigue_check = check_daily_fatigue_budget(session_exercise_dicts)
                if not fatigue_check["within_budget"] and fatigue_check.get("warnings"):
                    session.notes = "CNS: " + "; ".join(fatigue_check["warnings"])

            # -------------------------------------------------------------------
            # FST-7 Session-Level Application
            # -------------------------------------------------------------------
            week_fst7_mode = week.get("fst7_mode", "moderate")
            if week_fst7_mode != "none":
                await db.flush()  # ensure all sets have IDs
                # Load all sets for this session to pass to FST-7
                fst7_sets_result = await db.execute(
                    select(TrainingSet, Exercise.name, Exercise.primary_muscle, Exercise.equipment)
                    .join(Exercise, TrainingSet.exercise_id == Exercise.id)
                    .where(TrainingSet.session_id == session.id)
                    .order_by(TrainingSet.set_number)
                )
                session_set_rows = fst7_sets_result.all()
                _apply_session_fst7(
                    db, session, session_set_rows,
                    fst7_mode=week_fst7_mode,
                    division=user_division,
                    hqi_scores=_MUSCLE_HQI_MAP,
                )
                await db.flush()

                # Renumber sets: non-FST-7 first, then FST-7 (finisher is last)
                renumber_result = await db.execute(
                    select(TrainingSet)
                    .where(TrainingSet.session_id == session.id)
                    .order_by(TrainingSet.is_fst7, TrainingSet.set_number)
                )
                all_session_sets = renumber_result.scalars().all()
                for new_num, ts_obj in enumerate(all_session_sets, start=1):
                    ts_obj.set_number = new_num

            # If there's spillover pending, ensure the NEXT day forces inclusion.
            # We do this by adding the keys to the next Day's `day["muscles"]` dynamically
            # if we have consecutive days left in the week.
            sessions_created += 1
            if global_spillover and day_idx + 1 < len(week["days"]):
                for pending_muscle, remaining_sets in global_spillover.items():
                    if remaining_sets > 0:
                        # Map db_muscle to peri_muscle representation if possible
                        next_day_muscles = week["days"][day_idx + 1]["muscles"]
                        if pending_muscle not in next_day_muscles:
                            next_day_muscles.append(pending_muscle)

        week_start += timedelta(weeks=1)

    # -----------------------------------------------------------------------
    # 7. Store this mesocycle's exercise IDs for next-block rotation
    # -----------------------------------------------------------------------
    if profile:
        prefs = profile.preferences or {}
        # Keep a deduplicated list of the last mesocycle's exercises
        prefs["prev_mesocycle_exercise_ids"] = list(set(this_mesocycle_exercise_ids))
        profile.preferences = prefs

    return sessions_created

async def autoregulate_session_for_soreness(
    db: AsyncSession,
    user_id,
    session: TrainingSession,
    sore_muscles: list[str],
) -> tuple[int, list[str]]:
    """
    Applies a ~25% volume reduction (minimum 1 set drop) dynamically to any exercise
    targeting a muscle flagged as highly sore in today's HRVLog.
    Returns: (number_of_sets_dropped, list_of_affected_exercises)
    """
    if not sore_muscles:
        return 0, []

    # Map the frontend muscle group names to DB primary_muscle names
    form_to_db_map = {
        "chest": "chest", "back": "back", "quads": "quads", "hamstrings": "hamstrings",
        "delts": "shoulders", "arms": ["biceps", "triceps"], "calves": "calves", 
        "abs": "abs", "glutes": "glutes", "lower back": "lower back"
    }
    
    db_sore_muscles = set()
    for m in sore_muscles:
        mapped = form_to_db_map.get(m.lower())
        if isinstance(mapped, list):
            db_sore_muscles.update(mapped)
        elif mapped:
            db_sore_muscles.add(mapped)
            
    if not db_sore_muscles:
        return 0, []

    # Get sets for this session joined with Exercise
    result = await db.execute(
        select(TrainingSet, Exercise)
        .join(Exercise, TrainingSet.exercise_id == Exercise.id)
        .where(TrainingSet.session_id == session.id)
        .order_by(TrainingSet.set_number)
    )
    
    sets = result.all()
    if not sets:
        return 0, []
        
    sets_by_exercise = defaultdict(list)
    for t_set, ex in sets:
        sets_by_exercise[ex].append(t_set)
        
    total_dropped = 0
    affected = []
    
    # 1) Calculate total scheduled working sets per sore muscle
    muscle_working_sets = defaultdict(int)
    for ex, ex_sets in sets_by_exercise.items():
        if ex.primary_muscle in db_sore_muscles:
            working_sets = [s for s in ex_sets if not s.is_warmup]
            muscle_working_sets[ex.primary_muscle] += len(working_sets)
            
    # The dynamic volume cap applied to heavily sore muscles for a single session
    _SORE_MUSCLE_SESSION_CAP = 6

    # 2) Strip sets to enforce the cap or apply a fatigue baseline 25% drop
    for ex, ex_sets in sets_by_exercise.items():
        if ex.primary_muscle in db_sore_muscles:
            working_sets = [s for s in ex_sets if not s.is_warmup]
            current_total = muscle_working_sets[ex.primary_muscle]
            
            if len(working_sets) > 1:
                drop_count = 0
                if current_total > _SORE_MUSCLE_SESSION_CAP:
                    # Strip sets to get below the session threshold (leave at least 1 set)
                    excess = current_total - _SORE_MUSCLE_SESSION_CAP
                    drop_count = min(excess, len(working_sets) - 1)
                    muscle_working_sets[ex.primary_muscle] -= drop_count
                
                # If they were already below the hard cap, still run a fatigue reduction
                if drop_count == 0:
                    drop_count = max(1, math.floor(len(working_sets) * 0.25))
                    muscle_working_sets[ex.primary_muscle] -= drop_count

                if drop_count > 0:
                    sets_to_drop = working_sets[-drop_count:]
                    for s in sets_to_drop:
                        await db.delete(s)
                    total_dropped += len(sets_to_drop)
                    affected.append(ex.name)
                
    if total_dropped > 0:
        if session.notes:
            session.notes += f"\n[Autoregulation] Dropped {total_dropped} sets due to soreness in: {', '.join(sore_muscles)}."
        else:
            session.notes = f"[Autoregulation] Dropped {total_dropped} sets due to soreness in: {', '.join(sore_muscles)}."
            
    await db.flush()
    return total_dropped, list(set(affected))
