"""
Engine 3 — Nutrition Controller: Macro Prescription Calculator

Pure math module for computing TDEE via Mifflin-St Jeor and deriving
phase-specific macronutrient prescriptions.  No DB or HTTP imports.
"""

from typing import Dict


# ---------------------------------------------------------------------------
# Phase caloric adjustments (kcal)
# ---------------------------------------------------------------------------
_PHASE_OFFSETS = {
    "bulk":     400,    # +300-500 midpoint
    "cut":     -400,    # -(300-500) midpoint
    "maintain":  0,
    "peak":   -700,
    "restoration": 0,   # starts at maintenance; calories increase weekly
}

# Protein targets (g per kg TOTAL body weight) — aligned with ISSN position stand and
# Morton et al. (2018) meta-analysis. Research literature reports 1.6–2.2 g/kg TBW;
# applying these multipliers to LBM (as prior versions did) under-doses by 25–40%
# at typical offseason body fat levels (15–25% BF).
# Higher during deficit phases to defend against catabolism; lower in surplus where
# anabolic environment reduces the protein stimulus required.
_PROTEIN_PER_KG = {
    "bulk":     2.0,   # ~1g/lb TBW — surplus environment, carbs drive anabolism
    "maintain": 2.0,   # mid-range — adequate for tissue maintenance and MPS
    "cut":      2.4,   # above maintenance — blunts muscle catabolism in deficit
    "peak":     2.7,   # upper ceiling — extreme deficit of contest week demands maximum protection
    "restoration": 2.2, # moderate — tapering down from peak protein during reverse diet
}

# Hard bounds enforced regardless of division overrides or other overrides (g/kg TBW)
_PROTEIN_MIN_PER_KG = 1.6
_PROTEIN_MAX_PER_KG = 2.7

# Minimum fat floor (g per kg TOTAL body weight) — raised from prior 0.8 g/kg LBM.
# Research: 20–35% of total calories from fat required for optimal androgen synthesis
# (testosterone precursor biosynthesis). 1.0 g/kg TBW ≈ 22–28% of calories at typical
# training TDEEs. Do not drop below this floor in any phase.
_FAT_FLOOR_PER_KG = 1.0

# Caloric densities
_KCAL_PER_G_PROTEIN = 4.0
_KCAL_PER_G_CARB    = 4.0
_KCAL_PER_G_FAT     = 9.0


def compute_tdee(
    weight_kg: float,
    height_cm: float,
    age: int,
    sex: str,
    activity_multiplier: float,
) -> float:
    """Return Total Daily Energy Expenditure using Mifflin-St Jeor.

    Parameters
    ----------
    weight_kg : float
        Body weight in kilograms.
    height_cm : float
        Height in centimetres.
    age : int
        Age in years.
    sex : str
        ``"male"`` or ``"female"`` (case-insensitive).
    activity_multiplier : float
        Standard PAL multiplier (e.g. 1.2 sedentary … 1.9 very active).

    Returns
    -------
    float
        Estimated TDEE in kcal/day.

    Raises
    ------
    ValueError
        If *sex* is not ``"male"`` or ``"female"``.
    """
    sex_lower = sex.strip().lower()
    if sex_lower == "male":
        bmr = (10.0 * weight_kg) + (6.25 * height_cm) - (5.0 * age) + 5.0
    elif sex_lower == "female":
        bmr = (10.0 * weight_kg) + (6.25 * height_cm) - (5.0 * age) - 161.0
    else:
        raise ValueError(f"sex must be 'male' or 'female', got '{sex}'")

    return bmr * activity_multiplier


def compute_macros(
    tdee: float,
    phase: str,
    weight_kg: float,
    sex: str,
    lean_mass_kg: float | None = None,
) -> Dict[str, float]:
    """Derive a macronutrient prescription from TDEE and training phase.

    Phase adjustments
    -----------------
    * **bulk**     — +300-500 kcal (uses +400 midpoint)
    * **cut**      — -300-500 kcal (uses -400 midpoint)
    * **maintain** — no adjustment
    * **peak**     — -700 kcal (contest-week depletion)

    Protein and fat floors are calculated per kg of *lean* body mass when
    ``lean_mass_kg`` is provided, because fat tissue requires negligible
    dietary protein to maintain.  Falls back to total body weight if lean
    mass is unknown.

    Parameters
    ----------
    tdee : float
        Total daily energy expenditure (kcal).
    phase : str
        One of ``"bulk"``, ``"cut"``, ``"maintain"``, ``"peak"``.
    weight_kg : float
        Total body weight in kg (used for TDEE context, not macro targets).
    sex : str
        ``"male"`` or ``"female"`` (used for future sex-specific tuning).
    lean_mass_kg : float | None
        Lean body mass in kg.  When provided, protein and fat floor targets
        are anchored to lean mass rather than total weight.

    Returns
    -------
    dict
        Keys: ``protein_g``, ``fat_g``, ``carbs_g``, ``target_calories``.

    Raises
    ------
    ValueError
        If *phase* is not a recognised value.
    """
    phase_lower = phase.strip().lower()
    if phase_lower not in _PHASE_OFFSETS:
        raise ValueError(
            f"phase must be one of {list(_PHASE_OFFSETS)}, got '{phase}'"
        )

    target_calories = tdee + _PHASE_OFFSETS[phase_lower]

    # Protein and fat are anchored to TOTAL body weight (TBW), not lean mass.
    # Research (Morton et al. 2018, ISSN 2017) reports optimal intakes in g/kg TBW.
    # lean_mass_kg is retained as a parameter for informational use but is not the
    # reference for these targets — applying LBM multipliers causes 25–40% under-dosing.
    _ = lean_mass_kg  # available for caller context; not used in macro math

    # Protein — clamped to the 1.6–2.7 g/kg TBW evidence range
    protein_per_kg = max(_PROTEIN_MIN_PER_KG, min(_PROTEIN_MAX_PER_KG, _PROTEIN_PER_KG[phase_lower]))
    protein_g = round(protein_per_kg * weight_kg, 1)
    protein_kcal = protein_g * _KCAL_PER_G_PROTEIN

    # Fat — floor of 1.0 g/kg TBW to maintain endocrine function
    fat_g = round(_FAT_FLOOR_PER_KG * weight_kg, 1)
    fat_kcal = fat_g * _KCAL_PER_G_FAT

    # Carbs — remainder
    remaining_kcal = target_calories - protein_kcal - fat_kcal
    carbs_g = round(max(remaining_kcal / _KCAL_PER_G_CARB, 0.0), 1)

    return {
        "protein_g": protein_g,
        "fat_g": fat_g,
        "carbs_g": carbs_g,
        "target_calories": round(target_calories, 0),
    }


def compute_training_rest_day_macros(
    base_macros: dict,
    weight_kg: float,
) -> dict:
    """
    Split the flat macro prescription into training-day and rest-day targets.

    Training days: +20% carbs, fat adjusted down to keep calories similar.
    Rest days: -20% carbs, fat adjusted up to compensate.

    Args:
        base_macros: Output of :func:`compute_macros` (with ``carbs_g``,
                     ``fat_g``, ``protein_g``, ``target_calories``).
        weight_kg: Body weight in kg (used to ensure fat floor is maintained).

    Returns:
        Dict with ``training_day`` and ``rest_day`` sub-dicts, each
        containing ``protein_g``, ``carbs_g``, ``fat_g``,
        ``target_calories``.
    """
    base_carbs = base_macros["carbs_g"]
    base_fat = base_macros["fat_g"]
    base_protein = base_macros["protein_g"]
    fat_floor = round(_FAT_FLOOR_PER_KG * weight_kg, 1)

    # Training day: +20% carbs, reduce fat to compensate
    train_carbs = round(base_carbs * 1.20, 1)
    extra_kcal = (train_carbs - base_carbs) * _KCAL_PER_G_CARB
    train_fat = round(max(fat_floor, base_fat - extra_kcal / _KCAL_PER_G_FAT), 1)
    train_cals = round(base_protein * 4 + train_carbs * 4 + train_fat * 9, 0)

    # Rest day: -20% carbs, increase fat to maintain calories
    rest_carbs = round(base_carbs * 0.80, 1)
    saved_kcal = (base_carbs - rest_carbs) * _KCAL_PER_G_CARB
    rest_fat = round(base_fat + saved_kcal / _KCAL_PER_G_FAT, 1)
    rest_cals = round(base_protein * 4 + rest_carbs * 4 + rest_fat * 9, 0)

    return {
        "training_day": {
            "protein_g": base_protein,
            "carbs_g": train_carbs,
            "fat_g": train_fat,
            "target_calories": train_cals,
        },
        "rest_day": {
            "protein_g": base_protein,
            "carbs_g": rest_carbs,
            "fat_g": rest_fat,
            "target_calories": rest_cals,
        },
    }


def compute_restoration_macros(
    base_tdee: float,
    weight_kg: float,
    sex: str,
    weeks_post_show: int,
) -> Dict[str, float]:
    """Compute macro prescription for the post-show restoration (reverse diet) phase.

    Restoration gradually increases calories to rebuild metabolic rate and
    hormonal function after contest prep.  The protocol:
      - Weeks 1-8:  +100 kcal/week above maintenance baseline
      - Weeks 9-12: +150 kcal/week above the week-8 level
    Protein tapers linearly from 2.7 g/kg (peak-week level) down to
    2.0 g/kg over 12 weeks to ease digestive and renal load as calories
    normalise.

    Parameters
    ----------
    base_tdee : float
        Maintenance TDEE (kcal) — the starting point for restoration.
    weight_kg : float
        Current body weight in kg.
    sex : str
        ``"male"`` or ``"female"`` (case-insensitive).
    weeks_post_show : int
        Weeks elapsed since competition (1-12+).  Values > 12 are clamped
        to week 12.

    Returns
    -------
    dict
        Keys: ``protein_g``, ``fat_g``, ``carbs_g``, ``target_calories``,
        ``week``, ``protein_per_kg``.
    """
    sex_lower = sex.strip().lower()
    if sex_lower not in ("male", "female"):
        raise ValueError(f"sex must be 'male' or 'female', got '{sex}'")

    week = max(1, min(weeks_post_show, 12))

    # Caloric ramp
    if week <= 8:
        calorie_add = 100.0 * week
    else:
        calorie_add = 100.0 * 8 + 150.0 * (week - 8)

    target_calories = base_tdee + calorie_add

    # Protein taper: 2.7 → 2.0 g/kg linearly over 12 weeks
    protein_per_kg = 2.7 - (0.7 * (week - 1) / 11.0)
    protein_per_kg = round(max(2.0, min(2.7, protein_per_kg)), 2)
    protein_g = round(protein_per_kg * weight_kg, 1)
    protein_kcal = protein_g * _KCAL_PER_G_PROTEIN

    # Fat — floor of 1.0 g/kg TBW
    fat_g = round(_FAT_FLOOR_PER_KG * weight_kg, 1)
    fat_kcal = fat_g * _KCAL_PER_G_FAT

    # Carbs — remainder
    remaining_kcal = target_calories - protein_kcal - fat_kcal
    carbs_g = round(max(remaining_kcal / _KCAL_PER_G_CARB, 0.0), 1)

    return {
        "protein_g": protein_g,
        "fat_g": fat_g,
        "carbs_g": carbs_g,
        "target_calories": round(target_calories, 0),
        "week": week,
        "protein_per_kg": protein_per_kg,
    }


def compute_division_nutrition_priorities(division: str, phase: str) -> dict:
    """
    Return division-specific nutrition guidance that modulates the macro
    prescription for a given competition category.

    This is not user-configurable — the priorities are set algorithmically
    based on what each division rewards on stage.

    Args:
        division: Competition division (e.g. "mens_open", "womens_bikini").
        phase: Training phase ("bulk", "cut", "maintain", "peak").

    Returns:
        Dict with keys:
          protein_per_kg_override  — float | None (overrides _PROTEIN_PER_KG)
          carb_cycling_factor      — float, 0-0.4 (±% carb swing train vs rest)
          fat_per_kg_floor         — float (minimum fat g/kg)
          meal_frequency_target    — int, recommended meals/day
          mps_threshold_g          — int, protein per meal for MPS stimulus
          notes                    — list[str], coaching rationale for the app UI
    """
    # ---------------------------------------------------------------------------
    # Division nutrition profiles
    # Rationale is encoded in 'notes' for transparency in the UI.
    # ---------------------------------------------------------------------------
    _PROFILES: dict[str, dict] = {
        "mens_open": {
            # Mass is the primary goal; heavy compound training demands glycogen.
            # High protein supports LBM retention during aggressive cuts.
            "protein_per_kg": {"bulk": 1.8, "cut": 2.4, "maintain": 2.0, "peak": 2.4, "restoration": 2.2},
            "carb_cycling_factor": 0.25,   # +/- 25% carbs training vs rest day
            "fat_per_kg_floor": 0.85,      # slightly elevated fat supports testosterone
            "meal_frequency_target": 5,
            "mps_threshold_g": 40,         # larger meals for mass-phase MPS
            "notes": [
                "Aggressive calorie surplus in off-season (300-500 kcal above TDEE).",
                "Protein stays ≥1.8 g/kg during bulk to prevent excess fat gain.",
                "Carbs are highest on training days to fuel heavy compound sessions.",
                "Peak week uses a full carb-depletion then load cycle.",
            ],
        },
        "mens_physique": {
            # Year-round leanness is judged; avoid excess bulk calories.
            # Higher relative protein to stay anabolic while staying lean.
            "protein_per_kg": {"bulk": 2.0, "cut": 2.4, "maintain": 2.2, "peak": 2.4, "restoration": 2.2},
            "carb_cycling_factor": 0.30,   # pronounced cycling to stay conditioned
            "fat_per_kg_floor": 0.75,
            "meal_frequency_target": 5,
            "mps_threshold_g": 35,
            "notes": [
                "Maintain visible conditioning year-round — bulk calories are moderate.",
                "Higher carb cycling factor (±30%) keeps metabolism active while lean.",
                "Avoid excessive fat in bulk phase; focus calories on carbs/protein.",
                "Waist tightness is judged — minimise sodium and fibre before stage.",
            ],
        },
        "classic_physique": {
            # Similar to open but with more attention to proportion;
            # slightly less aggressive surplus to prevent exceeding weight caps.
            "protein_per_kg": {"bulk": 1.9, "cut": 2.4, "maintain": 2.0, "peak": 2.4, "restoration": 2.2},
            "carb_cycling_factor": 0.25,
            "fat_per_kg_floor": 0.80,
            "meal_frequency_target": 5,
            "mps_threshold_g": 40,
            "notes": [
                "Weight cap means bulk must be controlled — stop surplus at cap weight.",
                "Carb timing follows a classic bodybuilding approach: most carbs around training.",
                "Fat slightly lower than open to leave more room for carbs during bulk.",
            ],
        },
        "womens_bikini": {
            # Lean physique, glute fullness, minimal upper-body mass.
            # Lower absolute protein needs; tighter calories; high carb cycling.
            "protein_per_kg": {"bulk": 1.8, "cut": 2.2, "maintain": 2.0, "peak": 2.2, "restoration": 2.0},
            "carb_cycling_factor": 0.35,   # aggressive cycling to stay lean + full glutes
            "fat_per_kg_floor": 0.80,      # adequate fat for hormonal health
            "meal_frequency_target": 4,    # lower meal count suits smaller total calories
            "mps_threshold_g": 30,
            "notes": [
                "Caloric surplus is conservative — avoid accumulating excess upper-body mass.",
                "High carb cycling factor keeps glute fullness on training days while staying lean.",
                "Fat is critical for hormonal health — never drop below 0.8 g/kg.",
                "Near show: eliminate high-sodium foods and carbonated drinks 5 days out.",
                "Peak week is subtle — carb taper then moderate load (no extreme depletion).",
            ],
        },
        "womens_figure": {
            # More developed than bikini; requires more total volume and calories.
            "protein_per_kg": {"bulk": 1.9, "cut": 2.3, "maintain": 2.0, "peak": 2.3, "restoration": 2.1},
            "carb_cycling_factor": 0.30,
            "fat_per_kg_floor": 0.80,
            "meal_frequency_target": 5,
            "mps_threshold_g": 35,
            "notes": [
                "More training volume than bikini demands more carbs on training days.",
                "Shoulder-to-waist ratio matters — avoid excessive bloating near show.",
                "Moderate carb load on rest days to maintain muscle glycogen without spilling.",
            ],
        },
        "womens_physique": {
            # Full development; similar to mens open proportionally.
            "protein_per_kg": {"bulk": 1.9, "cut": 2.4, "maintain": 2.1, "peak": 2.4, "restoration": 2.2},
            "carb_cycling_factor": 0.25,
            "fat_per_kg_floor": 0.80,
            "meal_frequency_target": 5,
            "mps_threshold_g": 35,
            "notes": [
                "Heavy compound training demands glycogen — carbs are non-negotiable.",
                "Protein is elevated during cut to preserve hard-earned muscle mass.",
                "Peak week follows a full depletion-load cycle similar to men's open.",
            ],
        },
    }

    # Normalize division name
    key = (division or "mens_open").lower().replace(" ", "_")
    _aliases = {
        "open": "mens_open",
        "classic": "classic_physique",
        "physique": "mens_physique",
        "bikini": "womens_bikini",
        "figure": "womens_figure",
    }
    key = _aliases.get(key, key)
    profile = _PROFILES.get(key, _PROFILES["mens_open"])
    phase_key = (phase or "maintain").strip().lower()

    raw_override = profile["protein_per_kg"].get(phase_key)
    # Clamp division override to the 1.6–2.7 g/kg TBW range
    clamped_override = (
        max(_PROTEIN_MIN_PER_KG, min(_PROTEIN_MAX_PER_KG, raw_override))
        if raw_override is not None else None
    )
    return {
        "protein_per_kg_override": clamped_override,
        "carb_cycling_factor": profile["carb_cycling_factor"],
        "fat_per_kg_floor": profile["fat_per_kg_floor"],
        "meal_frequency_target": profile["meal_frequency_target"],
        "mps_threshold_g": profile["mps_threshold_g"],
        "notes": profile["notes"],
    }


def compute_peri_workout_carb_split(carbs_g: float, meal_count: int = 5) -> dict:
    """
    Distribute carbohydrates across the day with peri-workout prioritisation.

    Allocation:
      - Pre-workout (2-3 h before training):  35% of daily carbs
      - Intra-workout (during training):       10% (fast carbs — dextrose/gels)
      - Post-workout (within 1 h after):       25% of daily carbs
      - Remaining meals split across the rest: 30% distributed evenly

    Args:
        carbs_g: Total daily carbohydrate target (grams).
        meal_count: Total meals per day (≥3). The non-peri meals share
                    the remaining carbs.

    Returns:
        Dict with keys ``pre_workout_g``, ``intra_workout_g``,
        ``post_workout_g``, ``other_meals_g`` (per meal),
        ``other_meal_count``.
    """
    meal_count = max(3, meal_count)
    pre_g    = round(carbs_g * 0.35, 1)
    intra_g  = round(carbs_g * 0.10, 1)
    post_g   = round(carbs_g * 0.25, 1)
    remaining = round(carbs_g - pre_g - intra_g - post_g, 1)

    other_meals = max(1, meal_count - 3)  # meals outside the peri-workout window
    per_other_g = round(remaining / other_meals, 1)

    return {
        "pre_workout_g": pre_g,
        "intra_workout_g": intra_g,
        "post_workout_g": post_g,
        "other_meals_g": per_other_g,
        "other_meal_count": other_meals,
    }
