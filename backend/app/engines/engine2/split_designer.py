"""
Custom Split Designer — builds an optimal weekly training template from scratch.

Instead of choosing from preset splits (PPL, Upper/Lower, etc.), this engine
designs a custom split tailored to the athlete's specific gap profile, division
requirements, and recovery constraints.

Algorithm
---------
1. **Need Score** per muscle: blends HQI gap_cm (how much muscle to add) with
   division importance (how much judges care about that muscle). This prevents
   Men's Physique athletes from sacrificing shoulder/chest volume to chase
   leg gaps that judges don't see.

2. **Desired Frequency** per muscle: higher need → more sessions/week, but
   capped by recovery (large muscles need 48h+, small muscles 24h).

3. **Volume Budget** per muscle: need-driven (MEV→MRV interpolation).

4. **Cluster-then-Pack**: muscles are grouped into synergistic clusters
   (push, pull, legs, arms, shoulders) first, then clusters are assigned
   to days. High-frequency muscles get their cluster repeated on multiple
   days. This produces natural-sounding splits like "Push", "Pull + Arms",
   "Legs" instead of random muscle pairings.

5. **Day Labeling**: each day is labeled based on its muscle content.
"""

from __future__ import annotations

import math
from typing import Any


# ---------------------------------------------------------------------------
# Division importance weights per training muscle
# ---------------------------------------------------------------------------

_DIVISION_IMPORTANCE: dict[str, dict[str, float]] = {
    "mens_physique": {
        # MP lives and dies by WIDTH. Side delts are THE differentiator.
        # Brandon Hendrickson, Jeremy Buendia — capped delts define the division.
        "chest": 1.0, "back": 1.1,
        "front_delt": 1.0, "side_delt": 1.4, "rear_delt": 0.9,
        "biceps": 1.0, "triceps": 0.9, "forearms": 0.6,
        "traps": 0.5, "abs": 0.7,
        # Legs hidden by board shorts but still trained for base / proportionality.
        # Maintenance volume prevents atrophy without stealing recovery from upper body.
        "quads": 0.3, "hamstrings": 0.3, "glutes": 0.2, "calves": 0.15,
    },
    "classic_physique": {
        # Classic is the V-taper division. Side delts + back width create the
        # Golden Era illusion. Cbum's shoulders are what separate him.
        "chest": 1.0, "back": 1.1,
        "front_delt": 1.0, "side_delt": 1.3, "rear_delt": 1.0,
        "biceps": 1.0, "triceps": 1.0, "forearms": 0.7,
        "traps": 0.8, "abs": 0.9,
        "quads": 1.0, "hamstrings": 0.9, "glutes": 0.8, "calves": 0.9,
    },
    "mens_open": {
        "chest": 1.0, "back": 1.0,
        "front_delt": 1.0, "side_delt": 1.0, "rear_delt": 1.0,
        "biceps": 1.0, "triceps": 1.0, "forearms": 0.8,
        "traps": 0.9, "abs": 0.8,
        "quads": 1.0, "hamstrings": 1.0, "glutes": 1.0, "calves": 1.0,
    },
    "womens_bikini": {
        "chest": 0.3, "back": 0.6,
        "front_delt": 0.8, "side_delt": 1.0, "rear_delt": 0.5,
        "biceps": 0.3, "triceps": 0.3, "forearms": 0.1,
        "traps": 0.2, "abs": 0.8,
        "quads": 0.6, "hamstrings": 0.9, "glutes": 1.2, "calves": 0.2,
    },
    "womens_figure": {
        "chest": 0.5, "back": 0.9,
        "front_delt": 1.0, "side_delt": 1.2, "rear_delt": 0.8,
        "biceps": 0.5, "triceps": 0.5, "forearms": 0.3,
        "traps": 0.5, "abs": 0.7,
        "quads": 0.8, "hamstrings": 0.8, "glutes": 1.0, "calves": 0.5,
    },
    "womens_physique": {
        "chest": 0.8, "back": 1.0,
        "front_delt": 1.0, "side_delt": 1.0, "rear_delt": 0.9,
        "biceps": 0.8, "triceps": 0.8, "forearms": 0.5,
        "traps": 0.7, "abs": 0.8,
        "quads": 0.9, "hamstrings": 0.9, "glutes": 0.9, "calves": 0.7,
    },
}

_DEFAULT_IMPORTANCE: dict[str, float] = {
    "chest": 1.0, "back": 1.0,
    "front_delt": 1.0, "side_delt": 1.0, "rear_delt": 0.8,
    "biceps": 0.8, "triceps": 0.8, "forearms": 0.5,
    "traps": 0.6, "abs": 0.5,
    "quads": 0.8, "hamstrings": 0.8, "glutes": 0.7, "calves": 0.6,
}

# ---------------------------------------------------------------------------
# Synergistic muscle clusters — the building blocks of training days
# ---------------------------------------------------------------------------
# Each cluster is a natural training grouping. The designer selects and
# combines clusters to fill training days.

_CLUSTERS: dict[str, list[str]] = {
    "push":        ["chest", "front_delt", "side_delt", "triceps"],
    "pull":        ["back", "rear_delt", "biceps", "traps"],
    "legs":        ["quads", "hamstrings", "glutes", "calves"],
    "upper":       ["chest", "back", "front_delt", "side_delt", "rear_delt",
                    "biceps", "triceps"],
    "shoulders":   ["front_delt", "side_delt", "rear_delt", "traps"],
    "arms":        ["biceps", "triceps", "forearms"],
    "chest_back":  ["chest", "back"],
    # FST-7 Asymmetrical Specific
    "legs_quad_bias": ["quads", "calves"],
    "back_biceps":    ["back", "rear_delt", "biceps", "traps"],
    "chest_triceps":  ["chest", "triceps"],
    "legs_ham_glute": ["hamstrings", "glutes", "calves"],
    "delts_calves":   ["front_delt", "side_delt", "rear_delt", "calves"],
}

# Recovery hours per muscle
_RECOVERY_HOURS: dict[str, float] = {
    "chest": 48, "back": 48, "quads": 48, "hamstrings": 48, "glutes": 48,
    "front_delt": 36, "side_delt": 36, "rear_delt": 36,
    "biceps": 36, "triceps": 36,
    "calves": 24, "forearms": 24, "abs": 24, "traps": 24,
}

# Max working sets per session
_MAX_SETS_PER_SESSION = 25

# HQI site → training muscles
_HQI_TO_MUSCLES: dict[str, list[str]] = {
    "chest":     ["chest"],
    "shoulders": ["front_delt", "side_delt", "rear_delt"],
    "bicep":     ["biceps"],
    "thigh":     ["quads", "hamstrings"],
    "calf":      ["calves"],
    "back":       ["back"],
    # back_width (axillary breadth) directly measures lat spread
    "back_width": ["back"],
    "tricep":    ["triceps"],
    "hips":      ["glutes"],
    "forearm":   ["forearms"],
    "neck":      ["traps"],
}

# Volume landmarks (MEV, MAV, MRV)
_VOLUME_LANDMARKS: dict[str, tuple[int, int, int]] = {
    "chest":      (6, 12, 22),
    "back":       (8, 16, 25),
    "quads":      (6, 12, 20),
    "hamstrings": (4, 10, 16),
    "glutes":     (4, 10, 18),
    "front_delt": (4, 10, 18),
    "side_delt":  (4, 12, 20),
    "rear_delt":  (4, 12, 20),
    "biceps":     (4, 14, 20),
    "triceps":    (4, 14, 20),
    "calves":     (6, 16, 22),
    "abs":        (0, 16, 25),
    "traps":      (0, 8, 16),
    "forearms":   (0, 8, 16),
}

# Unmeasured muscle default gaps (cm)
_UNMEASURED_GAP_DEFAULTS: dict[str, float] = {
    "back": 4.0,
    "front_delt": 2.0,
    "side_delt": 2.0,
    "rear_delt": 3.0,
    "triceps": 2.0,
    "abs": 0.0,
}

ALL_MUSCLES = list(_VOLUME_LANDMARKS.keys())

# Training day offsets from Monday
# Ensures recovery days are appropriately injected.
_WEEKLY_SCHEDULE: dict[int, list[int]] = {
    3: [0, 2, 4],            # Mon, Wed, Fri
    4: [0, 1, 3, 4],         # Mon, Tue, Thu, Fri
    # 5-day: Day 1, Day 2, Rest, Day 4, Day 5, Day 6, Rest
    5: [0, 1, 3, 4, 5],      
    6: [0, 1, 2, 3, 4, 5],   # Mon-Sat
}


# ---------------------------------------------------------------------------
# Step 1: Need scores
# ---------------------------------------------------------------------------

def _get_muscle_gap(muscle: str, hqi_gaps: dict[str, float]) -> float:
    """Get gap_cm for a training muscle from HQI site gaps."""
    if muscle in hqi_gaps:
        return hqi_gaps[muscle]
    for site, muscles in _HQI_TO_MUSCLES.items():
        if muscle in muscles and site in hqi_gaps:
            return hqi_gaps[site]
    return _UNMEASURED_GAP_DEFAULTS.get(muscle, 3.0)


def compute_need_scores(
    hqi_gaps: dict[str, float],
    division: str,
) -> dict[str, float]:
    """
    Blended need score (0-10) per muscle.

    Need = 0.6 × gap_score + 0.4 × importance_score

    Division-hidden muscles (importance ≤ 0.05) are capped at 3.0 so they
    get maintenance volume without dominating the split.
    """
    importance = _DIVISION_IMPORTANCE.get(
        division.lower().replace(" ", "_"),
        _DEFAULT_IMPORTANCE,
    )

    need_scores: dict[str, float] = {}
    for muscle in ALL_MUSCLES:
        gap_cm = _get_muscle_gap(muscle, hqi_gaps)
        gap_score = min(10.0, max(0.0, gap_cm))
        imp = importance.get(muscle, 0.5)
        imp_score = min(10.0, imp * (10.0 / 1.2))

        if imp <= 0.05:
            need_scores[muscle] = min(3.0, gap_score * 0.3)
        else:
            raw = 0.6 * gap_score + 0.4 * imp_score
            need_scores[muscle] = round(min(10.0, raw), 2)

    return need_scores


# ---------------------------------------------------------------------------
# Step 2: Frequency + volume
# ---------------------------------------------------------------------------

def compute_desired_frequency(
    need_scores: dict[str, float],
    days_per_week: int,
    volume_budget: dict[str, int] | None = None,
    hqi_gaps: dict[str, float] | None = None,
) -> dict[str, int]:
    """Map need score → desired weekly training frequency."""
    desired: dict[str, int] = {}
    offsets = _WEEKLY_SCHEDULE.get(days_per_week, [0, 2, 4])
    for muscle, need in need_scores.items():
        if need >= 7.0:
            freq = 3
        elif need >= 4.5:
            freq = 2
        elif need >= 1.5:
            freq = 1
        else:
            freq = 1
            
        # Rule 1 (Spillover Volume Caps): If the weekly volume allocation exceeds
        # the ~12-set upper boundary of productive hypertrophic stimulus for a
        # single session, forcefully scale the frequency up so the algorithm
        # is forced to spread it across multiple days instead of dumping "junk volume".
        if volume_budget:
            vol = volume_budget.get(muscle, 0)
            if vol > 12:
                freq = max(freq, math.ceil(vol / 12))
        
        # Rule 3 (Gap-to-Frequency Hard Trigger): If the raw gap in cm
        # exceeds 15cm, the muscle MUST be trained at least 2x/week to
        # maximise protein synthesis windows for growth.
        if hqi_gaps:
            gap_cm = _get_muscle_gap(muscle, hqi_gaps)
            if gap_cm > 15.0:
                freq = max(freq, 2)
                
        min_gap = math.ceil(_RECOVERY_HOURS.get(muscle, 48) / 24)
        max_freq = _max_slots(offsets, min_gap)
        desired[muscle] = min(freq, max_freq)
    return desired


def compute_volume_budget(
    hqi_gaps: dict[str, float],
    need_scores: dict[str, float],
    division: str = "",
) -> dict[str, int]:
    """
    Weekly set budget per muscle, MEV→MRV interpolated by need score.

    Division importance modulates the ceiling: low-importance muscles
    can't exceed MAV even with high gap scores. This prevents hidden
    muscles from hogging training volume.
    """
    importance = _DIVISION_IMPORTANCE.get(
        division.lower().replace(" ", "_"),
        _DEFAULT_IMPORTANCE,
    )
    volume: dict[str, int] = {}
    for muscle in ALL_MUSCLES:
        mev, mav, mrv = _VOLUME_LANDMARKS.get(muscle, (4, 12, 20))
        
        # Rule 2 (Maintenance Routing - MMV): If this specific muscle group
        # is incredibly well developed (> 95% HQI / gap < 0.5cm), hard-cap
        # its volumetric budget to a Minimum Maintenance Volume protocol (4-6 sets/wk)
        # to preserve system CNS recovery reserves for priority targets.
        gap_cm = _get_muscle_gap(muscle, hqi_gaps)
        if gap_cm < 0.5:
            volume[muscle] = min(mev, 6)
            continue
            
        need = need_scores.get(muscle, 3.0)
        imp = importance.get(muscle, 0.5)
        t = min(1.0, max(0.0, need / 10.0))

        # For low-importance muscles, cap at MAV instead of MRV
        # Gradual: imp=0 → cap at MEV, imp=0.3 → cap at MAV, imp=1.0 → cap at MRV
        if imp < 0.3:
            ceiling = mev + round((mav - mev) * (imp / 0.3))
        elif imp < 0.8:
            ceiling = mav + round((mrv - mav) * ((imp - 0.3) / 0.5))
        else:
            ceiling = mrv

        raw = round(mev + t * (ceiling - mev))
        volume[muscle] = max(mev, min(raw, ceiling))
    return volume


def _max_slots(offsets: list[int], min_gap_days: int) -> int:
    count = 0
    last = -1000
    for off in offsets:
        if (off - last) >= min_gap_days:
            count += 1
            last = off
    return max(1, count)


# ---------------------------------------------------------------------------
# Step 3: Cluster-based split design
# ---------------------------------------------------------------------------
#
# Strategy:
#   1. Pick a base split archetype based on days_per_week
#   2. Customize it: if high-need muscles need 2× frequency, duplicate
#      their cluster on a second day
#   3. Add accessory muscles (abs, forearms, calves) to days with headroom
#   4. Remove hidden muscles from training days (e.g., legs for MP)

# Split archetypes — starting points that get customized
_ARCHETYPES: dict[int, list[list[str]]] = {
    3: [["push"], ["pull"], ["legs"]],
    4: [["push"], ["pull"], ["legs"], ["shoulders", "arms"]],
    5: [["legs_quad_bias"], ["back_biceps"], ["chest_triceps"], ["legs_ham_glute"], ["delts_calves"]],
    6: [["push"], ["pull"], ["legs"], ["push"], ["pull"], ["legs"]],
}


def apply_illusion_multipliers(
    need_scores: dict[str, float],
    volume_budget: dict[str, int],
    shoulder_width_cm: float | None = None,
    height_cm: float | None = None,
    division: str = "mens_physique",
) -> tuple[dict[str, float], dict[str, int]]:
    """
    Apply illusion-based priority multipliers for narrow-framed athletes.

    If clavicle/shoulder width is narrow relative to height, apply a 2.0x
    priority multiplier to lateral and posterior deltoids to create the
    illusion of width, overriding raw geometric gaps.

    This is most impactful for V-taper divisions (MP, Classic, Figure).
    """
    if shoulder_width_cm is None or height_cm is None or height_cm <= 0:
        return need_scores, volume_budget

    # Shoulder-to-height ratio: average is ~0.26, narrow is <0.24
    ratio = shoulder_width_cm / height_cm
    v_taper_divisions = {"mens_physique", "classic_physique", "womens_figure"}
    div_key = division.lower().replace(" ", "_")

    if ratio < 0.24 and div_key in v_taper_divisions:
        multiplier = 2.0
        for muscle in ("side_delt", "rear_delt"):
            if muscle in need_scores:
                need_scores[muscle] = need_scores[muscle] * multiplier
            if muscle in volume_budget:
                volume_budget[muscle] = min(volume_budget[muscle] + 6, 24)

    return need_scores, volume_budget


def design_split(
    hqi_gaps: dict[str, float],
    division: str,
    days_per_week: int,
    shoulder_width_cm: float | None = None,
    height_cm: float | None = None,
) -> dict[str, Any]:
    """
    Design an optimal custom weekly training split.

    Args:
        hqi_gaps: Per-site gap in cm from ideal.
        division: Competition division.
        days_per_week: Training frequency (2-7).
        shoulder_width_cm: Biacromial width for illusion multiplier.
        height_cm: Height for illusion multiplier ratio calculation.

    Returns:
        {
            "template": [{"day": str, "muscles": [str]}, ...],
            "split_name": "custom",
            "need_scores": {...},
            "volume_budget": {...},
            "desired_frequency": {...},
            "reasoning": str,
        }
    """
    # Enforce recovery guardrails (min 3, max 6 training days)
    days_per_week = max(3, min(6, days_per_week))
    division_key = division.lower().replace(" ", "_")

    need_scores = compute_need_scores(hqi_gaps, division_key)
    volume_budget = compute_volume_budget(hqi_gaps, need_scores, division_key)
    desired_freq = compute_desired_frequency(need_scores, days_per_week, volume_budget, hqi_gaps)
    importance = _DIVISION_IMPORTANCE.get(division_key, _DEFAULT_IMPORTANCE)

    # Apply illusion multipliers for narrow-framed athletes
    need_scores, volume_budget = apply_illusion_multipliers(
        need_scores, volume_budget, shoulder_width_cm, height_cm, division,
    )

    # -------------------------------------------------------------------------
    # Rule 1 C (Aggregation Safety Clamp): The shoulder muscle group is tracked
    # as 3 independent muscles (front/side/rear delt). If they individually receive
    # 12 sets, the engine merges them into a catastrophic 35-set "shoulder" block.
    # We must explicitly clamp the COMBINED deltoid volume down to the 12-set bound.
    # -------------------------------------------------------------------------
    shoulder_freq = max(
        desired_freq.get("front_delt", 1), 
        desired_freq.get("side_delt", 1), 
        desired_freq.get("rear_delt", 1)
    )
    max_combined_delt_vol = 12 * shoulder_freq
    current_combined_vol = sum(volume_budget.get(head, 0) for head in ("front_delt", "side_delt", "rear_delt"))
    
    if current_combined_vol > max_combined_delt_vol:
        scale_factor = max_combined_delt_vol / current_combined_vol
        for head in ("front_delt", "side_delt", "rear_delt"):
            if head in volume_budget:
                volume_budget[head] = math.floor(volume_budget[head] * scale_factor)

    # Start from archetype
    archetype = _ARCHETYPES.get(days_per_week, _ARCHETYPES[4])

    # Expand cluster names to muscle lists
    days: list[dict] = []
    for cluster_names in archetype:
        muscles: list[str] = []
        seen: set[str] = set()
        for cname in cluster_names:
            for m in _CLUSTERS.get(cname, [cname]):
                if m not in seen:
                    muscles.append(m)
                    seen.add(m)
        days.append({"muscles": muscles, "total_sets": 0})

    # Compute total sets per day & enforce absolute session caps
    for day in days:
        total = 0
        for m in day["muscles"]:
            freq = _count_muscle_freq(m, days)
            vol = volume_budget.get(m, 0)
            
            # Rule 1 B (Safety Clamp): If the available frequency slots cannot
            # successfully distribute the total volume without exceeding 12 sets
            # per session, mathematically FORCE the weekly budget down to match.
            # This protects against 35-set single-day marathons on heavily constrained splits.
            if vol / max(1, freq) > 12:
                vol = 12 * max(1, freq)
                volume_budget[m] = vol
                
            total += math.ceil(vol / max(1, freq))
        day["total_sets"] = total

    # Add accessory muscles to days with headroom
    _accessories = ["abs", "forearms", "calves"]
    for acc in _accessories:
        if volume_budget.get(acc, 0) <= 0:
            continue
        freq_needed = desired_freq.get(acc, 1)
        placements = 0
        # Sort days by ascending total sets (add to lightest days)
        for day in sorted(days, key=lambda d: d["total_sets"]):
            if placements >= freq_needed:
                break
            if acc in day["muscles"]:
                placements += 1
                continue
            vol_per = math.ceil(volume_budget[acc] / max(1, freq_needed))
            if day["total_sets"] + vol_per <= _MAX_SETS_PER_SESSION:
                day["muscles"].append(acc)
                day["total_sets"] += vol_per
                placements += 1

    # Division-specific filtering: remove or reduce hidden muscles
    # For Men's Physique: keep legs in the split but mark as maintenance
    # (volume budget already handles this via low need scores)
    # Only fully remove a muscle if its need score is 0 AND it would free
    # meaningful volume for visible muscles
    for day in days:
        filtered = []
        for m in day["muscles"]:
            # Only remove if importance is truly zero AND there's no gap
            if importance.get(m, 0.5) <= 0.0 and need_scores.get(m, 0) <= 0.5:
                continue
            filtered.append(m)
        day["muscles"] = filtered

    # Recalculate totals after filtering
    for day in days:
        total = 0
        for m in day["muscles"]:
            freq = _count_muscle_freq(m, days)
            vol = volume_budget.get(m, 0)
            total += math.ceil(vol / max(1, freq))
        day["total_sets"] = total

    # Build template with labels
    template = []
    for day in days:
        if not day["muscles"]:
            continue
        label = _generate_day_label(day["muscles"])
        template.append({
            "day": label,
            "muscles": list(day["muscles"]),
        })

    # Reasoning
    top_needs = sorted(need_scores.items(), key=lambda x: -x[1])[:5]
    hidden = [m for m in ALL_MUSCLES if importance.get(m, 0.5) <= 0.05]

    parts = [f"Custom {days_per_week}-day split for {division.replace('_', ' ').title()}."]
    if top_needs:
        top_str = ", ".join(f"{m} ({n:.1f})" for m, n in top_needs)
        parts.append(f"Top priorities: {top_str}.")
    if hidden:
        parts.append(
            f"Low-visibility muscles ({', '.join(hidden)}) get maintenance volume only."
        )

    return {
        "template": template,
        "split_name": "custom",
        "need_scores": need_scores,
        "volume_budget": volume_budget,
        "desired_frequency": desired_freq,
        "reasoning": " ".join(parts),
    }


def _count_muscle_freq(muscle: str, days: list[dict]) -> int:
    """Count how many days a muscle appears in."""
    return sum(1 for d in days if muscle in d["muscles"])


# ---------------------------------------------------------------------------
# Day labeling
# ---------------------------------------------------------------------------

def _generate_day_label(muscles: list[str]) -> str:
    """Generate a readable label for a training day based on its muscles."""
    muscle_set = set(muscles)

    # Check for well-known groupings
    _LABELS: list[tuple[set[str], str]] = [
        # Full combos first (most specific)
        ({"chest", "front_delt", "side_delt", "triceps"}, "Push"),
        ({"back", "rear_delt", "biceps", "traps"}, "Pull"),
        ({"back", "rear_delt", "biceps"}, "Pull"),
        ({"quads", "hamstrings", "glutes", "calves"}, "Legs"),
        ({"quads", "hamstrings", "glutes"}, "Legs"),
        ({"chest", "back", "front_delt", "side_delt", "rear_delt",
          "biceps", "triceps"}, "Upper"),
        # Partial combos
        ({"front_delt", "side_delt", "rear_delt", "traps"}, "Shoulders & Traps"),
        ({"front_delt", "side_delt", "rear_delt"}, "Shoulders"),
        ({"biceps", "triceps", "forearms"}, "Arms"),
        ({"biceps", "triceps"}, "Arms"),
        ({"chest", "back"}, "Chest & Back"),
    ]

    _MINOR_MUSCLES = {"abs", "forearms", "calves", "traps"}

    for combo, label in sorted(_LABELS, key=lambda x: -len(x[0])):
        if combo.issubset(muscle_set):
            remainder = muscle_set - combo
            significant = remainder - _MINOR_MUSCLES
            if not significant:
                if remainder:
                    extras = sorted({_display(m) for m in remainder})
                    return f"{label} + {' & '.join(extras)}"
                return label

    # Fallback
    names = sorted({_display(m) for m in muscles})
    if len(names) <= 3:
        return " & ".join(names)
    return " / ".join(names[:2]) + " + More"


def _display(muscle: str) -> str:
    """Display name for a muscle."""
    _NAMES = {
        "chest": "Chest", "back": "Back",
        "front_delt": "Shoulders", "side_delt": "Shoulders",
        "rear_delt": "Rear Delts",
        "biceps": "Biceps", "triceps": "Triceps", "forearms": "Forearms",
        "quads": "Quads", "hamstrings": "Hamstrings", "glutes": "Glutes",
        "calves": "Calves", "abs": "Abs", "traps": "Traps",
    }
    return _NAMES.get(muscle, muscle.replace("_", " ").title())
