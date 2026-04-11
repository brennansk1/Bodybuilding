from __future__ import annotations

"""
Mesocycle Periodization + Optimal Split Selection

Generates weekly training structures for a mesocycle given a split type,
volume allocation, and duration.  Supports push/pull/legs, upper/lower,
full-body, and bro splits.

Periodization modes:
- **DUP** (Daily Undulating Periodization): default.  Each week cycles three
  intensity profiles (heavy / moderate / light) across training days so every
  muscle hits all three stimulus zones within a week.
- **Block**: for advanced athletes (>5 yr experience).  Three-week accumulation,
  three-week intensification, one-week realization/deload.
- **Linear**: legacy mode.  Volume increases linearly (+1-2 sets per muscle per
  week) capped at each muscle's MRV, with an automatic deload every 4th week at
  50 % volume.

Split Auto-Selection
--------------------
Given per-muscle HQI scores (0-100, lower = more lagging) and days available
per week, ``auto_select_split()`` chooses the split that best satisfies:

1. Training frequency: lagging muscles need more sessions per week.
2. Recovery constraints: sessions must be spaced far enough apart that the
   muscle has recovered before it's trained again (48 h for large, 36 h for
   medium, 24 h for small muscles).

The algorithm scores every candidate split against the athlete's gap profile
and returns the winner.
"""

from typing import Any
import math

from app.engines.engine2.recovery import get_recovery_window


# ---------------------------------------------------------------------------
# Split templates
# ---------------------------------------------------------------------------

_SPLIT_TEMPLATES: dict[str, list[dict[str, list[str]]]] = {
    "ppl": [
        {"day": "Push",       "muscles": ["chest", "front_delt", "side_delt", "triceps"]},
        {"day": "Pull",       "muscles": ["back", "rear_delt", "biceps"]},
        {"day": "Legs",       "muscles": ["quads", "hamstrings", "glutes", "calves"]},
    ],
    "upper_lower": [
        {"day": "Upper", "muscles": [
            "chest", "back", "front_delt", "side_delt", "rear_delt",
            "biceps", "triceps",
        ]},
        {"day": "Lower", "muscles": ["quads", "hamstrings", "glutes", "calves"]},
    ],
    "full_body": [
        {"day": "Full Body", "muscles": [
            "chest", "back", "quads", "hamstrings", "glutes",
            "front_delt", "side_delt", "rear_delt",
            "biceps", "triceps", "calves",
        ]},
    ],
    "bro_split": [
        {"day": "Chest",     "muscles": ["chest", "front_delt", "triceps"]},
        {"day": "Back",      "muscles": ["back", "rear_delt", "biceps"]},
        {"day": "Shoulders", "muscles": ["front_delt", "side_delt", "rear_delt", "traps"]},
        {"day": "Arms",      "muscles": ["biceps", "triceps", "forearms"]},
        {"day": "Legs",      "muscles": ["quads", "hamstrings", "glutes", "calves"]},
    ],
}

# Deload cadence and magnitude — now phase-aware.
_DELOAD_EVERY_N_WEEKS: int = 6
_DELOAD_VOLUME_FRACTION: float = 0.50

# Phase-specific deload cadence: cutting athletes fatigue faster and need
# more frequent deloads. Bulk phases allow longer accumulation blocks.
_PHASE_DELOAD_CADENCE: dict[str, int] = {
    "offseason": 8,       # long accumulation — CNS fresh, surplus fuels recovery
    "bulk": 8,
    "lean_bulk": 6,       # standard 6-week mesocycle
    "cut": 5,             # deficit impairs recovery — shorter blocks
    "peak_week": 0,       # no deload needed — already reduced volume
    "peak": 5,
    "restoration": 4,     # de-conditioned post-show — gentle ramp
    "maintain": 6,
}

def get_deload_cadence(phase: str = "lean_bulk") -> int:
    """Return deload frequency in weeks for the current training phase."""
    return _PHASE_DELOAD_CADENCE.get(phase, _DELOAD_EVERY_N_WEEKS)

# ---------------------------------------------------------------------------
# 6-week mesocycle phase map (bodybuilding-specific)
# ---------------------------------------------------------------------------
# Week 1-2: MEV — Minimum Effective Volume (3 working sets, 2 RIR)
# Week 3-4: MAV — Maximum Adaptive Volume (+1 set, loads increase, 1 RIR)
# Week 5:   MRV — Maximum Recoverable Volume (failure, 0 RIR)
# Week 6:   Deload & Recovery (50% volume, 60% loads, no FST-7)

MESO_PHASE_MAP: dict[int, dict] = {
    1: {
        "label": "MEV",
        "name": "Minimum Effective Volume",
        "description": "Base compounds, 3 working sets each. 2 RIR. Moderate FST-7 fascial stretching.",
        "volume_landmark": "mev",
        "rir": 2,
        "set_modifier": 0,   # base sets
        "fst7_mode": "moderate",
    },
    2: {
        "label": "MEV",
        "name": "Minimum Effective Volume",
        "description": "Base compounds, 3 working sets each. 2 RIR. Moderate FST-7 fascial stretching.",
        "volume_landmark": "mev",
        "rir": 2,
        "set_modifier": 0,
        "fst7_mode": "moderate",
    },
    3: {
        "label": "MAV",
        "name": "Maximum Adaptive Volume",
        "description": "+1 working set per compound. Loads increase. 1 RIR. Aggressive FST-7 stretching, 45s rest.",
        "volume_landmark": "mav",
        "rir": 1,
        "set_modifier": 1,
        "fst7_mode": "aggressive",
    },
    4: {
        "label": "MAV",
        "name": "Maximum Adaptive Volume",
        "description": "+1 working set per compound. Loads increase. 1 RIR. Aggressive FST-7 stretching, 45s rest.",
        "volume_landmark": "mav",
        "rir": 1,
        "set_modifier": 1,
        "fst7_mode": "aggressive",
    },
    5: {
        "label": "MRV",
        "name": "Maximum Recoverable Volume",
        "description": "Peak intensity. Heavy compounds at RIR 1 to protect form/joints; isolation finishers to failure (RIR 0). Forced reps and extreme intra-set stretching on FST-7 isolation work only.",
        "volume_landmark": "mrv",
        "rir": 1,
        "rir_isolation": 0,
        "set_modifier": 2,
        "fst7_mode": "extreme",
    },
    6: {
        "label": "DELOAD",
        "name": "Deload & Recovery",
        "description": "50% volume, 60% loads. No FST-7. Active recovery for cellular repair and supercompensation.",
        "volume_landmark": "deload",
        "rir": 4,
        "set_modifier": 0,
        "fst7_mode": "none",
    },
}

_DEFAULT_MESOCYCLE_WEEKS: int = 6

# Weekly set progression per muscle group.
_MIN_WEEKLY_SET_INCREASE: int = 1
_MAX_WEEKLY_SET_INCREASE: int = 2

# Training day offsets from Monday for each days-per-week config
_WEEKLY_SCHEDULE: dict[int, list[int]] = {
    2: [0, 3],             # Mon, Thu
    3: [0, 2, 4],          # Mon, Wed, Fri
    4: [0, 1, 3, 4],       # Mon, Tue, Thu, Fri
    5: [0, 1, 2, 4, 5],    # Mon, Tue, Wed, Fri, Sat
    6: [0, 1, 2, 4, 5, 6],
    7: [0, 1, 2, 3, 4, 5, 6],
}

# ---------------------------------------------------------------------------
# Volume Landmarks (sets/week) — Adaptive, RP-aligned
# MEV = minimum effective volume  (below = junk volume territory)
# MAV = maximum adaptive volume   (sweet spot center)
# MRV = maximum recoverable volume (above = excess fatigue)
#
# Base values are for an intermediate male athlete (~3-5 years training).
# Scaled dynamically by sex, training age, and prep phase via
# get_volume_landmarks().
# ---------------------------------------------------------------------------
_BASE_VOLUME_LANDMARKS: dict[str, tuple[int, int, int]] = {
    # muscle:       (MEV, MAV, MRV) — RP-aligned (Renaissance Periodization)
    "chest":        (6,  14, 22),
    "back":         (10, 18, 25),
    "quads":        (8,  14, 20),
    "hamstrings":   (6,  12, 16),
    "glutes":       (4,   8, 16),
    "shoulders":    (6,  16, 22),     # combined (backward compat)
    "biceps":       (6,  16, 22),
    "triceps":      (4,  10, 16),     # indirect from pressing accounted for
    "calves":       (8,  14, 20),
    "abs":          (6,  12, 20),    # always train abs — core stability for compounds
    "traps":        (0,  12, 20),
    "forearms":     (0,   8, 14),
    "front_delt":   (3,   8, 14),     # dedicated front delt work — incline press doesn't fully cover clavicular head (Schoenfeld 2020)
    "side_delt":    (8,  18, 24),     # tolerates high volume
    "rear_delt":    (6,  14, 22),
}

# Sex-based scaling: females generally recover faster from volume (lower
# absolute loads, less CNS demand per set) but have lower absolute MRV
# ceilings. Males with high training age can tolerate more.
_SEX_VOLUME_SCALE: dict[str, float] = {
    "male": 1.0,
    "female": 0.85,   # ~15% lower ceilings — preserves joint health, prevents overreaching
}

# Training experience scaling: novices need less stimulus, advanced athletes
# need substantially more to continue progressing.
_EXPERIENCE_VOLUME_SCALE: dict[str, float] = {
    "beginner":     0.70,   # <1 year: low MEV, respond to minimal volume
    "novice":       0.80,   # 1-2 years
    "intermediate": 1.00,   # 3-5 years (baseline)
    "advanced":     1.15,   # 5-10 years: higher MEV and MRV
    "elite":        1.25,   # 10+ years: near-genetic ceiling, needs maximum stimulus
}

# Phase-based MRV ceiling modifier: during a caloric deficit recovery
# capacity drops — MRV should be lower. During a surplus, athlete can
# tolerate more volume.
_PHASE_MRV_SCALE: dict[str, float] = {
    "offseason": 1.10,     # surplus → higher ceiling
    "bulk": 1.10,
    "lean_bulk": 1.05,
    "maintain": 1.00,
    "cut": 0.85,           # deficit → lower ceiling (recovery impaired)
    "peak_week": 0.65,     # heavily reduced
    "peak": 0.85,
    "restoration": 0.75,   # post-show: de-conditioned, gentle ramp
}


def _classify_experience(training_years: int) -> str:
    """Map training years to experience tier."""
    if training_years < 1:
        return "beginner"
    elif training_years < 3:
        return "novice"
    elif training_years < 6:
        return "intermediate"
    elif training_years < 10:
        return "advanced"
    return "elite"


def get_volume_landmarks(
    muscle: str,
    sex: str = "male",
    training_years: int = 3,
    phase: str = "lean_bulk",
) -> tuple[int, int, int]:
    """Return (MEV, MAV, MRV) scaled for the athlete's profile and phase.

    A real coach adjusts volume prescriptions based on:
    - Sex: females tolerate ~15% less absolute volume
    - Training age: advanced athletes need more stimulus (higher MEV)
    - Phase: deficit phases lower MRV ceiling (recovery impaired)

    The MEV is scaled by sex and experience (you need more stimulus as
    you advance). The MRV is additionally scaled by phase (deficit =
    lower ceiling). MAV is the midpoint.
    """
    base = _BASE_VOLUME_LANDMARKS.get(muscle, (6, 12, 18))
    base_mev, base_mav, base_mrv = base

    sex_scale = _SEX_VOLUME_SCALE.get(sex.strip().lower(), 1.0)
    exp_tier = _classify_experience(training_years)
    exp_scale = _EXPERIENCE_VOLUME_SCALE.get(exp_tier, 1.0)
    phase_mrv = _PHASE_MRV_SCALE.get(phase, 1.0)

    # MEV and MAV scale with sex and experience
    mev = max(0, round(base_mev * sex_scale * exp_scale))
    # MRV additionally scales with phase (recovery capacity)
    mrv = max(mev + 2, round(base_mrv * sex_scale * exp_scale * phase_mrv))
    # MAV is the midpoint
    mav = round((mev + mrv) / 2)

    return (mev, mav, mrv)


# Keep the static dict for backward compatibility (used by split_designer etc.)
VOLUME_LANDMARKS = _BASE_VOLUME_LANDMARKS

# Minimum hours between training the same muscle (min recovery window)
_MUSCLE_MIN_RECOVERY: dict[str, float] = {
    "back": 48, "quads": 48, "glutes": 48, "hamstrings": 48, "chest": 48,
    "front_delt": 36, "side_delt": 36, "rear_delt": 36,
    "triceps": 36, "biceps": 36, "shoulders": 36,
    "calves": 24, "forearms": 24, "abs": 24, "traps": 24,
}

# HQI site name → periodization muscle name(s)
_HQI_TO_MUSCLES: dict[str, list[str]] = {
    "chest":      ["chest"],
    "shoulders":  ["front_delt", "side_delt", "rear_delt"],
    "bicep":      ["biceps"],
    "thigh":      ["quads", "hamstrings"],
    "calf":       ["calves"],
    "back":       ["back"],
    "tricep":     ["triceps"],
    "glutes":     ["glutes"],
    "forearm":    ["forearms"],
    "neck":       ["traps"],
}

# ---------------------------------------------------------------------------
# DUP (Daily Undulating Periodization) intensity profiles
# ---------------------------------------------------------------------------

DUP_PROFILES: dict[str, dict[str, Any]] = {
    "heavy": {
        "intensity_range": (0.70, 0.80),   # 70-80% 1RM
        "rep_range": (5, 8),
        "volume_modifier": 1.10,            # +10% volume from base
    },
    "moderate": {
        "intensity_range": (0.65, 0.75),   # 65-75% 1RM
        "rep_range": (8, 12),
        "volume_modifier": 1.00,            # base volume (standard hypertrophy)
    },
    "light": {
        "intensity_range": (0.55, 0.65),   # 55-65% 1RM
        "rep_range": (12, 20),
        "volume_modifier": 0.90,            # -10% volume
    },
}

# Rotation order for DUP across training days within a week
_DUP_ROTATION = ["heavy", "moderate", "light"]


# ---------------------------------------------------------------------------
# ARI-aware deload logic
# ---------------------------------------------------------------------------

def should_deload(avg_ari_last_week: float, current_week: int, mesocycle_weeks: int = 4) -> bool:
    """
    Determine whether a deload week should be scheduled.

    Uses ARI (Autonomic Readiness Index) as the primary signal, with a
    safety-net fallback at week 4.

    Args:
        avg_ari_last_week: Average ARI across the most recent full training
                           week (0-100).
        current_week: The 1-based week number within the current mesocycle.
        mesocycle_weeks: The total planned duration of this cycle.

    Returns:
        ``True`` if a deload is warranted.
    """
    # ARI-driven: athlete is systemically under-recovered
    if avg_ari_last_week < 55:
        return True
    # End-of-cycle default realization / deload
    if current_week == mesocycle_weeks:
        return True
    # Safety net: never go more than 4 consecutive weeks without a deload
    if current_week % _DELOAD_EVERY_N_WEEKS == 0 and current_week != mesocycle_weeks:
        return True
    return False


# ---------------------------------------------------------------------------
# Split auto-selection
# ---------------------------------------------------------------------------

def auto_select_split(
    hqi_scores: dict[str, float],
    days_per_week: int,
) -> str:
    """
    Select the optimal training split for this athlete's gap profile.

    Strategy:
    1. Convert per-muscle HQI scores into desired weekly training frequencies.
       Lower HQI (more lagging) → higher desired frequency.
    2. For each candidate split, compute the *effective* frequency each muscle
       actually receives when the template is cycled over ``days_per_week``
       training slots — accounting for recovery constraints so that consecutive
       sessions scheduled too close together are not counted.
    3. Score each split by how well it satisfies desired frequencies,
       weighted by gap severity (low HQI muscles matter more).
    4. Return the split with the highest score.

    Args:
        hqi_scores: Mapping of muscle/site name → HQI score (0-100).
        days_per_week: Number of training days the athlete has available.

    Returns:
        Split identifier string (e.g. ``"ppl"``, ``"full_body"``).
    """
    # Build per-muscle priority (0-10) and desired frequency from HQI
    muscle_priority: dict[str, float] = {}
    muscle_desired_freq: dict[str, int] = {}

    all_muscles = set()
    for muscles in _SPLIT_TEMPLATES["bro_split"][0:5]:
        for m in muscles["muscles"]:
            all_muscles.add(m)
    for template in _SPLIT_TEMPLATES.values():
        for day in template:
            for m in day["muscles"]:
                all_muscles.add(m)

    for muscle in all_muscles:
        # Find the best HQI score match for this muscle
        hqi = _get_hqi_for_muscle(muscle, hqi_scores)
        # Priority: 0-10, inversely proportional to HQI
        priority = round(10.0 * (1.0 - hqi / 100.0), 1)
        muscle_priority[muscle] = priority

        # Desired frequency based on gap severity
        if hqi < 40:
            desired = min(3, days_per_week)   # severely lagging: max frequency
        elif hqi < 65:
            desired = min(2, days_per_week)   # moderate gap: 2x/week
        else:
            desired = 1                        # ahead of ideal: maintain with 1x

        # Clamp to what's physically feasible given recovery constraints
        desired = min(desired, _max_feasible_freq(muscle, days_per_week))
        muscle_desired_freq[muscle] = desired

    # Filter splits to only those with enough template days for days_per_week
    # (bro_split needs ≥5 days to be meaningful, for example)
    candidate_splits = _get_candidate_splits(days_per_week)

    best_split = "ppl"
    best_score = float("-inf")

    for split_name in candidate_splits:
        score = _score_split(
            split_name,
            days_per_week,
            muscle_desired_freq,
            muscle_priority,
        )
        if score > best_score:
            best_score = score
            best_split = split_name

    return best_split


def _get_hqi_for_muscle(muscle: str, hqi_scores: dict) -> float:
    """
    Look up the HQI score for a periodization muscle name.
    Handles both flat {site: float} and nested {site: {score: float, ...}} formats.
    """
    def _extract_score(val) -> float:
        if isinstance(val, dict):
            return float(val.get("pct_of_ideal", 70.0))
        return float(val)

    # Direct match
    if muscle in hqi_scores:
        return _extract_score(hqi_scores[muscle])

    # Reverse map: periodization muscle → HQI site name(s)
    for site, muscles in _HQI_TO_MUSCLES.items():
        if muscle in muscles and site in hqi_scores:
            return _extract_score(hqi_scores[site])

    return 70.0  # default: assume adequate development


def _max_feasible_freq(muscle: str, days_per_week: int) -> int:
    """
    Compute the maximum frequency a muscle can be trained per week
    given its recovery constraint and the training schedule.
    """
    min_recovery_h = _MUSCLE_MIN_RECOVERY.get(muscle, 48.0)
    min_gap_days = math.ceil(min_recovery_h / 24.0)
    offsets = _WEEKLY_SCHEDULE.get(days_per_week, [0, 2, 4])

    # Greedy: count how many days can be included without back-to-back violations
    feasible = 0
    last_offset = -1000
    for offset in offsets:
        if (offset - last_offset) >= min_gap_days:
            feasible += 1
            last_offset = offset
    return max(1, feasible)


def _get_candidate_splits(days_per_week: int) -> list[str]:
    """Return split types that are sensible for this days-per-week count."""
    candidates = []
    if days_per_week >= 2:
        candidates.extend(["ppl", "upper_lower", "full_body"])
    if days_per_week >= 5:
        candidates.append("bro_split")
    return candidates if candidates else ["full_body"]


def _effective_freq(split_name: str, days_per_week: int, muscle: str) -> int:
    """
    Compute how many times a muscle is effectively trained per week
    for a given split + days_per_week combination, after applying
    recovery constraint filtering.
    """
    template = _SPLIT_TEMPLATES[split_name]
    offsets = _WEEKLY_SCHEDULE.get(days_per_week, [0, 2, 4])
    min_recovery_h = _MUSCLE_MIN_RECOVERY.get(muscle, 48.0)
    min_gap_days = math.ceil(min_recovery_h / 24.0)

    count = 0
    last_offset = -1000
    for day_idx, offset in enumerate(offsets):
        slot = template[day_idx % len(template)]
        if muscle in slot["muscles"]:
            if (offset - last_offset) >= min_gap_days or last_offset == -1000:
                count += 1
                last_offset = offset
            # else: recovery not met — session would be skipped

    # Wrap-around check: gap from last training day to first training day
    # of the next week (simulates continuous weekly schedule)
    if count >= 2 and last_offset >= 0:
        first_trained = None
        for day_idx, offset in enumerate(offsets):
            slot = template[day_idx % len(template)]
            if muscle in slot["muscles"]:
                first_trained = offset
                break
        if first_trained is not None:
            wrap_gap = (first_trained + 7) - last_offset
            if wrap_gap < min_gap_days:
                count -= 1  # last session too close to next week's first

    return count


def _score_split(
    split_name: str,
    days_per_week: int,
    muscle_desired_freq: dict[str, int],
    muscle_priority: dict[str, float],
) -> float:
    """
    Score a split by how well it satisfies desired training frequencies,
    weighted by muscle priority (gap severity).

    Scoring:
    - Meeting desired frequency for a high-priority muscle: large bonus
    - Under-serving a high-priority muscle: large penalty (x3 of priority)
    - Over-training a low-priority muscle: small penalty
    """
    score = 0.0

    for muscle, desired in muscle_desired_freq.items():
        priority = muscle_priority.get(muscle, 5.0)
        actual = _effective_freq(split_name, days_per_week, muscle)

        if actual >= desired:
            # Meets requirement — reward proportionally to priority
            score += priority * desired
            # Small penalty for unnecessary extra frequency on low-priority muscles
            if actual > desired and priority < 4.0:
                score -= (actual - desired) * (4.0 - priority) * 0.5
        else:
            # Under-serves this muscle — penalty scales with gap severity
            deficit = desired - actual
            score -= deficit * priority * 3.0

    return score


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_mesocycle(
    days_per_week: int,
    split_type: str,
    volume_allocation: dict[str, int],
    week_count: int,
    *,
    weekly_set_increase: int = _MIN_WEEKLY_SET_INCREASE,
    custom_template: list[dict[str, list[str]]] | None = None,
    periodization_type: str = "dup",
    avg_ari_per_week: list[float] | None = None,
    training_experience_years: float = 2.0,
) -> list[dict[str, Any]]:
    """
    Build a full mesocycle plan.

    Supports three periodization modes:

    - ``"dup"`` (default): Daily Undulating Periodization.  Each training day
      within a week is assigned a rotating intensity profile (heavy / moderate /
      light).  Deloads are ARI-aware via :func:`should_deload`.
    - ``"block"``: Block periodization for advanced athletes (>5 yr experience).
      3-week accumulation (high volume MAV->MRV, moderate intensity), 3-week
      intensification (moderate volume MEV->MAV, high intensity), 1-week
      realization/deload.
    - ``"linear"``: Legacy linear progression.  Volume increases linearly each
      non-deload week and is capped at each muscle's MRV so volume never becomes
      counter-productive.  Deloads every 4th week at 50 % volume.

    Args:
        days_per_week: Training days available (e.g. 3, 4, 5, 6).
        split_type: One of ``"ppl"``, ``"upper_lower"``, ``"full_body"``,
                    ``"bro_split"``, or ``"custom"``.
        volume_allocation: Starting weekly sets per muscle group.
        week_count: Total weeks in the mesocycle (typically 4-8).
        weekly_set_increase: Sets added per muscle per non-deload week
                             (clamped to [1, 2]).  Used by linear and DUP modes.
        custom_template: When split_type is "custom", provide the day
                         templates directly (output of split_designer).
        periodization_type: ``"dup"`` (default), ``"block"``, or ``"linear"``.
        avg_ari_per_week: Optional list of average ARI values per week for
                          ARI-aware deload scheduling in DUP mode.  Index 0
                          corresponds to the ARI reading *before* week 1.
        training_experience_years: Years of serious training experience.
                                   Used to validate block periodization
                                   suitability (recommended >5 yr).

    Returns:
        List of weekly structures.

    Raises:
        ValueError: If *split_type* is not recognized and no custom_template.
    """
    if split_type == "custom" and custom_template:
        template = custom_template
    elif split_type in _SPLIT_TEMPLATES:
        template = _SPLIT_TEMPLATES[split_type]
    else:
        raise ValueError(
            f"Unknown split_type '{split_type}'. "
            f"Choose from: {', '.join(_SPLIT_TEMPLATES)}, custom"
        )

    increment = max(_MIN_WEEKLY_SET_INCREASE, min(_MAX_WEEKLY_SET_INCREASE, weekly_set_increase))

    if periodization_type == "block":
        return _generate_block_mesocycle(
            template=template,
            days_per_week=days_per_week,
            volume_allocation=volume_allocation,
            week_count=week_count,
            increment=increment,
            training_experience_years=training_experience_years,
        )
    elif periodization_type == "dup":
        return _generate_dup_mesocycle(
            template=template,
            days_per_week=days_per_week,
            volume_allocation=volume_allocation,
            week_count=week_count,
            increment=increment,
            avg_ari_per_week=avg_ari_per_week,
        )
    else:
        # Legacy linear periodization
        return _generate_linear_mesocycle(
            template=template,
            days_per_week=days_per_week,
            volume_allocation=volume_allocation,
            week_count=week_count,
            increment=increment,
        )


def get_available_splits() -> list[str]:
    """Return the list of supported split type identifiers."""
    return list(_SPLIT_TEMPLATES.keys()) + ["custom"]


# ---------------------------------------------------------------------------
# DUP mesocycle builder
# ---------------------------------------------------------------------------

def _generate_dup_mesocycle(
    template: list[dict[str, list[str]]],
    days_per_week: int,
    volume_allocation: dict[str, int],
    week_count: int,
    increment: int,
    avg_ari_per_week: list[float] | None = None,
) -> list[dict[str, Any]]:
    """Build a mesocycle using Daily Undulating Periodization."""
    mesocycle: list[dict[str, Any]] = []

    for week_num in range(1, week_count + 1):
        # Determine deload via ARI or safety-net fallback
        if avg_ari_per_week and week_num - 1 < len(avg_ari_per_week):
            prev_ari = avg_ari_per_week[week_num - 1]
        else:
            prev_ari = 70.0  # assume adequate if no ARI data provided

        is_deload = should_deload(prev_ari, week_num, week_count)

        if is_deload:
            # Deload week: 50% volume, all sets at "light" profile
            week_volume = _week_volume(
                base_volume=volume_allocation,
                week_num=1,  # use base volume for deload calculation
                increment=0,
                is_deload=True,
            )
            days = _build_dup_days(
                template, days_per_week, week_volume, deload=True,
                week_num=week_num,
            )
        else:
            # Progressive non-deload week with DUP rotation
            week_volume = _week_volume(
                base_volume=volume_allocation,
                week_num=week_num,
                increment=increment,
                is_deload=False,
            )
            days = _build_dup_days(
                template, days_per_week, week_volume, deload=False,
                week_num=week_num,
            )

        # Attach mesocycle phase metadata
        phase_info = MESO_PHASE_MAP.get(week_num, MESO_PHASE_MAP.get(6, {}))
        mesocycle.append({
            "week": week_num,
            "is_deload": is_deload,
            "periodization_type": "dup",
            "meso_phase": phase_info.get("label", "MEV"),
            "meso_phase_name": phase_info.get("name", ""),
            "meso_phase_description": phase_info.get("description", ""),
            "rir": phase_info.get("rir", 2),
            "rir_isolation": phase_info.get("rir_isolation", phase_info.get("rir", 2)),
            "fst7_mode": phase_info.get("fst7_mode", "moderate"),
            "volume": week_volume,
            "days": days,
        })

    return mesocycle


def _build_dup_days(
    template: list[dict[str, list[str]]],
    days_per_week: int,
    week_volume: dict[str, int],
    deload: bool,
    week_num: int = 1,
) -> list[dict[str, Any]]:
    """
    Build training days with DUP intensity profiles rotating across days.

    Each training day receives one of heavy / moderate / light, cycling so
    that every muscle hits all three zones across the week.  During deload
    weeks, all days use the "light" profile.
    """
    days: list[dict[str, Any]] = []

    for i in range(days_per_week):
        slot = template[i % len(template)]
        day_label = slot["day"]
        if days_per_week > len(template):
            day_label = f"{slot['day']} ({i // len(template) + 1})"

        if deload:
            profile_name = "light"
        else:
            profile_name = _DUP_ROTATION[(i + week_num - 1) % len(_DUP_ROTATION)]

        profile = DUP_PROFILES[profile_name]

        # Adjust volume for this day's profile modifier
        volume_modifier = profile["volume_modifier"]
        if deload:
            volume_modifier = 1.0  # deload volume already halved

        days.append({
            "day_label": day_label,
            "muscles": list(slot["muscles"]),
            "sets_per_muscle": {},
            "dup_profile": profile_name,
            "intensity_range": profile["intensity_range"],
            "rep_range": profile["rep_range"],
            "volume_modifier": volume_modifier,
        })

    # Count how many days each muscle appears in.
    muscle_day_count: dict[str, int] = {}
    for day in days:
        for m in day["muscles"]:
            muscle_day_count[m] = muscle_day_count.get(m, 0) + 1

    # Distribute weekly volume evenly across training days, adjusted by
    # each day's DUP volume modifier.
    muscle_assigned: dict[str, int] = {}
    for day in days:
        modifier = day["volume_modifier"]
        for m in day["muscles"]:
            total = week_volume.get(m, 0)
            count = muscle_day_count.get(m, 1)
            already = muscle_assigned.get(m, 0)
            # Base per-day share, then apply DUP modifier
            per_day = math.ceil((total / count) * modifier)
            assigned = min(per_day, total - already)
            assigned = max(0, assigned)

            # Enforce MEV floor per session
            mev, _, _ = VOLUME_LANDMARKS.get(m, (0, 0, 100))
            min_per_session = math.ceil(mev / count) if count > 0 else 0
            assigned = max(assigned, min(min_per_session, total - already))

            day["sets_per_muscle"][m] = max(0, assigned)
            muscle_assigned[m] = already + assigned

    return days


# ---------------------------------------------------------------------------
# Block periodization mesocycle builder
# ---------------------------------------------------------------------------

def _generate_block_mesocycle(
    template: list[dict[str, list[str]]],
    days_per_week: int,
    volume_allocation: dict[str, int],
    week_count: int,
    increment: int,
    training_experience_years: float,
) -> list[dict[str, Any]]:
    """
    Build a mesocycle using block periodization.

    Structure per 7-week block:
    - Weeks 1-3: Accumulation — high volume (MAV->MRV), moderate intensity.
    - Weeks 4-6: Intensification — moderate volume (MEV->MAV), high intensity.
    - Week 7: Realization / deload — low volume, test-level intensity.

    Recommended for advanced athletes (>5 yr experience).
    """
    mesocycle: list[dict[str, Any]] = []
    block_length = 7  # 3 accum + 3 intens + 1 deload

    for week_num in range(1, week_count + 1):
        position_in_block = ((week_num - 1) % block_length) + 1

        if position_in_block <= 3:
            phase = "accumulation"
            phase_week = position_in_block  # 1, 2, or 3
        elif position_in_block <= 6:
            phase = "intensification"
            phase_week = position_in_block - 3  # 1, 2, or 3
        else:
            phase = "realization"
            phase_week = 1

        week_volume, intensity_profile = _block_week_params(
            volume_allocation, phase, phase_week,
        )

        days = _build_block_days(
            template, days_per_week, week_volume, intensity_profile,
        )

        mesocycle.append({
            "week": week_num,
            "is_deload": phase == "realization",
            "periodization_type": "block",
            "block_phase": phase,
            "block_phase_week": phase_week,
            "volume": week_volume,
            "days": days,
        })

    return mesocycle


def _block_week_params(
    base_volume: dict[str, int],
    phase: str,
    phase_week: int,
) -> tuple[dict[str, int], dict[str, Any]]:
    """
    Compute volume and intensity parameters for a block periodization week.

    Returns:
        (week_volume, intensity_profile) tuple.
    """
    volume: dict[str, int] = {}

    if phase == "accumulation":
        # High volume: ramp from MAV toward MRV over 3 weeks
        for muscle, base_sets in base_volume.items():
            mev, mav, mrv = VOLUME_LANDMARKS.get(muscle, (0, base_sets, base_sets + 10))
            target = mav + round((mrv - mav) * (phase_week / 3.0))
            volume[muscle] = min(target, mrv)
        intensity_profile = {
            "intensity_range": (0.65, 0.75),
            "rep_range": (8, 12),
            "label": "accumulation",
        }

    elif phase == "intensification":
        # Moderate volume: ramp from MEV toward MAV over 3 weeks
        for muscle, base_sets in base_volume.items():
            mev, mav, mrv = VOLUME_LANDMARKS.get(muscle, (0, base_sets, base_sets + 10))
            target = mev + round((mav - mev) * (phase_week / 3.0))
            volume[muscle] = min(target, mrv)
        intensity_profile = {
            "intensity_range": (0.75, 0.85),
            "rep_range": (4, 8),
            "label": "intensification",
        }

    else:  # realization / deload
        for muscle, base_sets in base_volume.items():
            mev, _, _ = VOLUME_LANDMARKS.get(muscle, (0, base_sets, base_sets + 10))
            volume[muscle] = max(1, math.floor(mev * 0.75))
        intensity_profile = {
            "intensity_range": (0.80, 0.95),
            "rep_range": (1, 5),
            "label": "realization",
        }

    return volume, intensity_profile


def _build_block_days(
    template: list[dict[str, list[str]]],
    days_per_week: int,
    week_volume: dict[str, int],
    intensity_profile: dict[str, Any],
) -> list[dict[str, Any]]:
    """Build training days for a block periodization week."""
    days: list[dict[str, Any]] = []

    for i in range(days_per_week):
        slot = template[i % len(template)]
        day_label = slot["day"]
        if days_per_week > len(template):
            day_label = f"{slot['day']} ({i // len(template) + 1})"

        days.append({
            "day_label": day_label,
            "muscles": list(slot["muscles"]),
            "sets_per_muscle": {},
            "block_phase": intensity_profile["label"],
            "intensity_range": intensity_profile["intensity_range"],
            "rep_range": intensity_profile["rep_range"],
        })

    # Distribute volume (same logic as linear)
    muscle_day_count: dict[str, int] = {}
    for day in days:
        for m in day["muscles"]:
            muscle_day_count[m] = muscle_day_count.get(m, 0) + 1

    muscle_assigned: dict[str, int] = {}
    for day in days:
        for m in day["muscles"]:
            total = week_volume.get(m, 0)
            count = muscle_day_count.get(m, 1)
            already = muscle_assigned.get(m, 0)
            per_day = math.ceil(total / count)
            assigned = min(per_day, total - already)
            assigned = max(0, assigned)

            mev, _, _ = VOLUME_LANDMARKS.get(m, (0, 0, 100))
            min_per_session = math.ceil(mev / count) if count > 0 else 0
            assigned = max(assigned, min(min_per_session, total - already))

            day["sets_per_muscle"][m] = max(0, assigned)
            muscle_assigned[m] = already + assigned

    return days


# ---------------------------------------------------------------------------
# Linear (legacy) mesocycle builder
# ---------------------------------------------------------------------------

def _generate_linear_mesocycle(
    template: list[dict[str, list[str]]],
    days_per_week: int,
    volume_allocation: dict[str, int],
    week_count: int,
    increment: int,
) -> list[dict[str, Any]]:
    """Build a mesocycle using legacy linear volume progression."""
    mesocycle: list[dict[str, Any]] = []

    for week_num in range(1, week_count + 1):
        is_deload = should_deload(70.0, week_num, week_count)

        week_volume = _week_volume(
            base_volume=volume_allocation,
            week_num=week_num,
            increment=increment,
            is_deload=is_deload,
        )

        days = _build_days(template, days_per_week, week_volume)

        mesocycle.append({
            "week": week_num,
            "is_deload": is_deload,
            "periodization_type": "linear",
            "volume": week_volume,
            "days": days,
        })

    return mesocycle


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _week_volume(
    base_volume: dict[str, int],
    week_num: int,
    increment: int,
    is_deload: bool,
) -> dict[str, int]:
    """
    Compute the volume map for a given week using gradual progressive overload.

    Starts from ``base_volume`` (the division-adjusted per-muscle budget from
    the split designer — e.g. chest at 14 sets for Men's Physique priority)
    and adds 1-2 sets per week through the accumulation phase, ramping
    toward MRV by week 5, then deloading to ~50% of the peak week.

    This replaces the old step-function (MEV weeks 1-2 flat, then jump to MAV
    in week 3) which produced volume CLIFFS — biceps going from 2 sets to
    11 sets overnight — rather than the gradual ramps a real coach prescribes.
    """
    phase_info = MESO_PHASE_MAP.get(week_num, MESO_PHASE_MAP.get(6, {}))
    base_modifier = phase_info.get("set_modifier", 0)

    # Accumulation multiplier: scales the week's target above base_volume.
    # Week 1 = base_volume (division-adjusted MEV from the split designer).
    # Each subsequent week adds the increment until MRV is reached.
    #
    # Muscles that the split designer capped at MEV (low division importance —
    # e.g. quads for Men's Physique) don't progress: judges don't reward the
    # volume, so pushing them toward MRV just steals recovery from priority
    # muscles. These stay flat at base_volume the whole accumulation phase
    # except for the deload.
    result: dict[str, int] = {}
    for muscle, base in base_volume.items():
        mev, mav, mrv = VOLUME_LANDMARKS.get(muscle, (6, 12, 18))
        base_start = max(mev, base) if base > 0 else mev

        # A muscle is "maintenance-capped" if the split designer gave it a
        # budget within 1 set of the global MEV. For MP that's typically
        # quads/glutes/hamstrings; for Bikini it's chest/biceps/triceps.
        is_maintenance = base_start <= mev + 1

        if is_deload:
            # Deload = 50% of the peak week's volume. For maintenance muscles
            # this is 50% of base; for priority muscles it's 50% of what the
            # ramp would have reached at week 5 (or MRV, whichever is lower).
            if is_maintenance:
                peak = base_start
            else:
                peak = min(mrv, base_start + increment * 4)
            target = max(1, math.floor(peak * _DELOAD_VOLUME_FRACTION))
        elif is_maintenance:
            # Hold at base. No progressive overload on maintenance muscles —
            # the stimulus is already at MEV, that's the whole point.
            target = base_start
        else:
            # Priority muscle: gradual ramp from base toward MRV.
            # Base in week 1, +increment every week after, plus the
            # phase-specific set_modifier for MAV/MRV blocks.
            weeks_of_ramp = max(0, week_num - 1)
            target = base_start + (weeks_of_ramp * increment) + base_modifier
            target = min(target, mrv)

        result[muscle] = max(1, target)

    return result


def _build_days(
    template: list[dict[str, list[str]]],
    days_per_week: int,
    week_volume: dict[str, int],
) -> list[dict[str, Any]]:
    """
    Map the split template onto *days_per_week* training slots and
    distribute each muscle's weekly sets evenly across its training days.
    """
    days: list[dict[str, Any]] = []
    for i in range(days_per_week):
        slot = template[i % len(template)]
        day_label = slot["day"]
        if days_per_week > len(template):
            day_label = f"{slot['day']} ({i // len(template) + 1})"

        days.append({
            "day_label": day_label,
            "muscles": list(slot["muscles"]),
            "sets_per_muscle": {},
        })

    # Count how many days each muscle appears in.
    muscle_day_count: dict[str, int] = {}
    for day in days:
        for m in day["muscles"]:
            muscle_day_count[m] = muscle_day_count.get(m, 0) + 1

    # Distribute weekly volume evenly across training days for each muscle.
    muscle_assigned: dict[str, int] = {}
    for day in days:
        for m in day["muscles"]:
            total = week_volume.get(m, 0)
            count = muscle_day_count.get(m, 1)
            already = muscle_assigned.get(m, 0)
            per_day = math.ceil(total / count)
            assigned = min(per_day, total - already)
            assigned = max(0, assigned)

            # Enforce MEV floor per session — at least MEV/frequency sets
            mev, _, _ = VOLUME_LANDMARKS.get(m, (0, 0, 100))
            min_per_session = math.ceil(mev / count) if count > 0 else 0
            assigned = max(assigned, min(min_per_session, total - already))

            day["sets_per_muscle"][m] = max(0, assigned)
            muscle_assigned[m] = already + assigned

    return days


# FST-7 protocol has been migrated to services/training.py::_apply_session_fst7()
# which applies FST-7 at the session level after all muscle groups are allocated.
# _FST7_TARGETS and intensity config now live in training.py.
