"""
Volume Landmark System — MEV / MAV / MRV per muscle group.

Source: Mike Israetel / Renaissance Periodization published landmarks.
Values are weekly working set counts for an intermediate male trainee.
Experience modifiers scale all three landmarks proportionally.

- MEV (Minimum Effective Volume): below this, no hypertrophy stimulus.
- MAV (Maximum Adaptive Volume): productive range — most progress lives here.
- MRV (Maximum Recoverable Volume): above this, recovery debt exceeds adaptation.

These are SOFT guides in the sense that individuals vary ±30%, but the
relationships (chest MEV < back MEV, side_delt MRV > front_delt MRV) are
biologically anchored and hold for most athletes.
"""

from __future__ import annotations

# Per-muscle landmarks: (MEV, MAV low, MAV high, MRV) in weekly working sets.
# MAV is expressed as a range because productive volume is a band, not a point.
LANDMARKS_INTERMEDIATE: dict[str, dict[str, int]] = {
    "chest":       {"mev": 8,  "mav_low": 12, "mav_high": 18, "mrv": 22},
    "back":        {"mev": 10, "mav_low": 14, "mav_high": 20, "mrv": 25},
    "front_delt":  {"mev": 3,  "mav_low": 6,  "mav_high": 10, "mrv": 14},
    "side_delt":   {"mev": 8,  "mav_low": 12, "mav_high": 20, "mrv": 26},
    "rear_delt":   {"mev": 6,  "mav_low": 10, "mav_high": 16, "mrv": 22},
    "biceps":      {"mev": 8,  "mav_low": 12, "mav_high": 18, "mrv": 22},
    "triceps":     {"mev": 6,  "mav_low": 10, "mav_high": 14, "mrv": 18},
    "quads":       {"mev": 8,  "mav_low": 12, "mav_high": 18, "mrv": 22},
    "hamstrings":  {"mev": 6,  "mav_low": 10, "mav_high": 14, "mrv": 18},
    "glutes":      {"mev": 4,  "mav_low": 8,  "mav_high": 12, "mrv": 16},
    "calves":      {"mev": 8,  "mav_low": 12, "mav_high": 16, "mrv": 20},
    "abs":         {"mev": 6,  "mav_low": 10, "mav_high": 14, "mrv": 20},
    "traps":       {"mev": 0,  "mav_low": 6,  "mav_high": 12, "mrv": 18},
    "forearms":    {"mev": 0,  "mav_low": 4,  "mav_high": 10, "mrv": 14},
}

# Experience-level proportional scalar.
EXPERIENCE_MODIFIERS: dict[str, float] = {
    "beginner":     0.70,   # <1 year
    "novice":       0.85,   # 1-2 years
    "intermediate": 1.00,   # 3-5 years (baseline)
    "advanced":     1.15,   # 5-10 years
    "elite":        1.25,   # 10+ years
}

# Enhanced athletes recover faster and tolerate higher weekly volume.
# Ground Truth doc §4.2 cites RP's note that landmarks are derived for
# intermediate naturals; enhanced athletes scale MRV/MAV_high +15-25%.
# MEV is NOT scaled — starting volume should still be conservative.
_ENHANCEMENT_MODIFIER_MRV = 1.20
_ENHANCEMENT_MODIFIER_MAV_HIGH = 1.20


def _classify_experience(training_years: float | None) -> str:
    if training_years is None:
        return "intermediate"
    y = float(training_years)
    if y < 1:
        return "beginner"
    if y < 3:
        return "novice"
    if y < 6:
        return "intermediate"
    if y < 10:
        return "advanced"
    return "elite"


def get_landmarks(
    muscle: str,
    training_years: float | None = 3.0,
    training_status: str = "natural",
) -> dict[str, int]:
    """Return (MEV, MAV low, MAV high, MRV) dict for one muscle, scaled by experience.

    When ``training_status == "enhanced"``, MAV_high and MRV are scaled by
    ``_ENHANCEMENT_MODIFIER_*`` (Ground Truth doc §4.2). MEV is preserved —
    starting volume should stay conservative regardless of status.
    """
    base = LANDMARKS_INTERMEDIATE.get(muscle)
    if not base:
        # Unknown muscle — return a safe default band
        return {"mev": 6, "mav_low": 10, "mav_high": 14, "mrv": 18}
    scalar = EXPERIENCE_MODIFIERS[_classify_experience(training_years)]
    enh_mrv = _ENHANCEMENT_MODIFIER_MRV if training_status == "enhanced" else 1.0
    enh_mavh = _ENHANCEMENT_MODIFIER_MAV_HIGH if training_status == "enhanced" else 1.0
    return {
        "mev": max(0, round(base["mev"] * scalar)),
        "mav_low": max(1, round(base["mav_low"] * scalar)),
        "mav_high": max(1, round(base["mav_high"] * scalar * enh_mavh)),
        "mrv": max(1, round(base["mrv"] * scalar * enh_mrv)),
    }


def get_all_landmarks(
    training_years: float | None = 3.0,
    training_status: str = "natural",
) -> dict[str, dict[str, int]]:
    """Return the full landmark table, scaled by experience + training status."""
    return {
        muscle: get_landmarks(muscle, training_years, training_status)
        for muscle in LANDMARKS_INTERMEDIATE.keys()
    }


def classify_volume(
    weekly_sets: int,
    muscle: str,
    training_years: float | None = 3.0,
    training_status: str = "natural",
) -> str:
    """
    Classify a weekly set count into a landmark zone:
      "below_mev"  | "mev_to_mav" | "mav_productive" | "mav_to_mrv" | "above_mrv"

    `mav_productive` is the sweet-spot band between mav_low and mav_high.
    """
    lm = get_landmarks(muscle, training_years, training_status)
    if weekly_sets < lm["mev"]:
        return "below_mev"
    if weekly_sets < lm["mav_low"]:
        return "mev_to_mav"
    if weekly_sets <= lm["mav_high"]:
        return "mav_productive"
    if weekly_sets <= lm["mrv"]:
        return "mav_to_mrv"
    return "above_mrv"
