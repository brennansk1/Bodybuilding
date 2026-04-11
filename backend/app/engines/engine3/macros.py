from __future__ import annotations

"""
Engine 3 — Nutrition Controller: Macro Prescription Calculator

Pure math module for computing TDEE via Katch-McArdle (when LBM is
available) or Mifflin-St Jeor (fallback) and deriving phase-specific
macronutrient prescriptions.  No DB or HTTP imports.
"""

from typing import Dict


# ---------------------------------------------------------------------------
# Phase caloric adjustments (kcal)
# ---------------------------------------------------------------------------
_PHASE_OFFSETS = {
    "bulk":     450,    # +300-600 surplus
    "lean_bulk": 250,   # +200-300 controlled surplus
    "cut":     -400,    # deficit
    "maintain":  0,
    "peak":   -700,
    "restoration": 0,
}

# Protein targets (g per kg TOTAL body weight) — aligned with ISSN position stand and
# Morton et al. (2018) meta-analysis. Research literature reports 1.6–2.2 g/kg TBW;
# applying these multipliers to LBM (as prior versions did) under-doses by 25–40%
# at typical offseason body fat levels (15–25% BF).
# Higher during deficit phases to defend against catabolism; lower in surplus where
# anabolic environment reduces the protein stimulus required.
_PROTEIN_PER_KG = {
    "bulk":      2.0,
    "lean_bulk": 2.2,   # slightly higher to prioritize LBM in surplus
    "maintain":  2.0,
    "cut":       2.4,
    "peak":      2.7,
    "restoration": 2.2,
}

# Hard bounds enforced regardless of division overrides or other overrides (g/kg TBW)
_PROTEIN_MIN_PER_KG = 1.6
_PROTEIN_MAX_PER_KG = 2.7

# Phase-decaying fat floor (g per kg TOTAL body weight)
# Offseason: 1.0 g/kg — optimal for androgen synthesis and hormonal health
# Early cut: 0.8 g/kg — slight sacrifice to spare carbs for training performance
# Late cut (men <8% BF / women <14% BF): 0.5 g/kg — aggressive fat reduction,
#   spared calories routed strictly to carbohydrates for muscle fullness
# Peak: 0.4 g/kg — maximum carb sparing for glycogen supercompensation
_FAT_FLOOR_BY_PHASE: dict[str, float] = {
    "bulk": 1.0,
    "lean_bulk": 1.0,
    "maintain": 1.0,
    "restoration": 0.9,
    "cut": 0.8,        # early cut default — overridden to 0.5 when lean (see below)
    "peak": 0.4,
}
_FAT_FLOOR_PER_KG = 1.0  # legacy fallback


def _fat_floor_for_context(
    phase: str,
    body_fat_pct: float | None = None,
    sex: str = "male",
) -> float:
    """Return the phase-appropriate fat floor in g/kg TBW.

    Coach-aligned fat floors:
    - Offseason/bulk: 1.0 g/kg (hormonal optimization, joint health)
    - Early cut: 0.8 g/kg (standard prep)
    - Late cut (<8% male, <14% female): 0.65 g/kg (not lower — protects hormones)
    - Peak week: 0.5 g/kg male, 0.6 g/kg female (7 days only, tight precision)
    - Female absolute floor: 0.6 g/kg (hormonal health is non-negotiable)

    An Olympia coach would NEVER drop a female athlete below 0.6 g/kg fat
    regardless of phase. For males, 0.5 g/kg is the absolute floor during
    peak week only — sustained cuts stay ≥0.65.
    """
    phase_key = phase.strip().lower()
    is_female = sex.strip().lower() == "female"
    floor = _FAT_FLOOR_BY_PHASE.get(phase_key, _FAT_FLOOR_PER_KG)

    # Peak week: tight but not reckless
    if phase_key == "peak":
        floor = 0.6 if is_female else 0.5

    # Late-cut override: smooth interpolation to avoid a jarring step-change.
    # Transitions from 0.8 → 0.65 g/kg over a 2% BF band.
    # A real coach would keep fat higher than the old 0.5 floor during
    # sustained prep to preserve testosterone/estrogen and avoid metabolic crash.
    elif phase_key == "cut" and body_fat_pct is not None:
        lean_threshold = 8.0 if not is_female else 14.0
        transition_band = 2.0
        late_cut_floor = 0.65 if not is_female else 0.70
        if body_fat_pct <= lean_threshold:
            floor = late_cut_floor
        elif body_fat_pct < lean_threshold + transition_band:
            fraction = (lean_threshold + transition_band - body_fat_pct) / transition_band
            floor = 0.8 - fraction * (0.8 - late_cut_floor)

    # Female absolute floor — hormonal health is non-negotiable
    if is_female:
        floor = max(floor, 0.6)

    return floor

# Caloric densities
_KCAL_PER_G_PROTEIN = 4.0
_KCAL_PER_G_CARB    = 4.0
_KCAL_PER_G_FAT     = 9.0


def compute_rmr_cunningham(lbm_kg: float) -> float:
    """Cunningham equation — gold standard for hyper-muscular athletes.

    RMR = 500 + (22 × LBM_kg)

    More accurate than Katch-McArdle for athletes with LBM > 75 kg
    (Men's Open / Classic competitors), as Katch-McArdle under-predicts
    RMR at extreme lean mass levels.

    Parameters
    ----------
    lbm_kg : float
        Lean body mass in kilograms.

    Returns
    -------
    float
        Resting metabolic rate in kcal/day.
    """
    return 500.0 + (22.0 * lbm_kg)


def compute_tdee(
    weight_kg: float,
    height_cm: float,
    age: int,
    sex: str,
    activity_multiplier: float,
    lean_mass_kg: float | None = None,
    use_cunningham: bool = False,
) -> float:
    """Return Total Daily Energy Expenditure.

    Uses Katch-McArdle when lean body mass is available (more accurate for
    muscular athletes); falls back to Mifflin-St Jeor otherwise.

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
    lean_mass_kg : float | None
        Lean body mass in kg.  When provided, the Katch-McArdle formula
        is used instead of Mifflin-St Jeor.

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

    if lean_mass_kg is not None and lean_mass_kg > 0:
        if use_cunningham or lean_mass_kg >= 75.0:
            # Cunningham — gold standard for hyper-muscular athletes (LBM ≥ 75 kg)
            bmr = compute_rmr_cunningham(lean_mass_kg)
        else:
            # Katch-McArdle — accurate for typical muscular athletes
            bmr = 370.0 + (21.6 * lean_mass_kg)
    elif sex_lower == "male":
        # Mifflin-St Jeor fallback when LBM unknown
        bmr = (10.0 * weight_kg) + (6.25 * height_cm) - (5.0 * age) + 5.0
    elif sex_lower == "female":
        bmr = (10.0 * weight_kg) + (6.25 * height_cm) - (5.0 * age) - 161.0
    else:
        raise ValueError(f"sex must be 'male' or 'female', got '{sex}'")

    return bmr * activity_multiplier


# ---------------------------------------------------------------------------
# Optimal Meal Frequency Calculator
# ---------------------------------------------------------------------------
# Based on Schoenfeld & Aragon (2018) meta-analysis and ISSN position stand:
#   - Minimum 3 meals/day for MPS optimization
#   - Each meal should deliver 0.4-0.55 g/kg protein (30-50g for most athletes)
#   - Eating more often than needed wastes prep time without MPS benefit
#   - Cutting phases benefit from more meals (satiety, blood sugar stability)
#   - Bulk phases can use fewer, larger meals (easier to eat surplus)

def compute_optimal_meal_count(
    protein_g: float,
    target_calories: float,
    weight_kg: float,
    phase: str = "cut",
) -> dict:
    """Determine the optimal number of meals per day for MPS optimization.

    The science: muscle protein synthesis (MPS) is maximally stimulated by
    ~0.4 g/kg of protein per meal (Morton et al. 2018). Eating below this
    threshold wastes a feeding opportunity; eating above it provides
    diminishing returns.

    Practical ceiling: 7 meals/day is the maximum for real-world compliance.
    Floor: 3 meals/day minimum (you can't distribute protein in fewer).

    Returns dict with optimal_meals, protein_per_meal, rationale.
    """
    # MPS-optimal protein per meal: 0.4-0.55 g/kg
    mps_threshold = weight_kg * 0.45  # midpoint of 0.4-0.55 range
    ideal_from_protein = max(3, round(protein_g / mps_threshold))

    # Phase adjustments
    if phase in ("cut", "peak"):
        # More meals during a cut: better satiety, stable blood sugar,
        # more even amino acid delivery to preserve LBM
        phase_bias = 1  # bump up by 1
    elif phase in ("bulk", "lean_bulk"):
        # Fewer meals during bulk: easier to hit surplus with larger meals
        phase_bias = -1 if ideal_from_protein > 4 else 0
    else:
        phase_bias = 0

    # Calorie-based sanity check: meals below 350 kcal feel too small,
    # meals above 900 kcal feel too large and impair digestion
    min_from_cals = max(3, round(target_calories / 900))
    max_from_cals = min(7, round(target_calories / 350))

    optimal = max(min_from_cals, min(max_from_cals, ideal_from_protein + phase_bias))
    optimal = max(3, min(7, optimal))  # hard clamp

    protein_per_meal = round(protein_g / optimal, 1)
    cals_per_meal = round(target_calories / optimal)

    rationale_parts = [
        f"{optimal} meals/day optimizes MPS ({protein_per_meal:.0f}g protein per meal).",
    ]
    if phase in ("cut", "peak"):
        rationale_parts.append("Higher frequency during cut improves satiety and amino acid delivery.")
    elif phase in ("bulk", "lean_bulk"):
        rationale_parts.append("Moderate frequency during bulk keeps meals large enough to hit surplus.")

    return {
        "optimal_meals": optimal,
        "protein_per_meal": protein_per_meal,
        "calories_per_meal": cals_per_meal,
        "mps_threshold_g": round(mps_threshold, 1),
        "rationale": " ".join(rationale_parts),
    }


def compute_macros(
    tdee: float,
    phase: str,
    weight_kg: float,
    sex: str,
    lean_mass_kg: float | None = None,
    body_fat_pct: float | None = None,
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

    # Fat — phase-decaying floor (1.0 g/kg offseason → 0.5 late cut → 0.4 peak)
    # Spared fat calories are routed strictly to carbohydrates
    fat_floor = _fat_floor_for_context(phase_lower, body_fat_pct, sex)
    fat_g = round(fat_floor * weight_kg, 1)
    fat_kcal = fat_g * _KCAL_PER_G_FAT

    # Carbs — remainder
    remaining_kcal = target_calories - protein_kcal - fat_kcal
    carbs_g = round(max(remaining_kcal / _KCAL_PER_G_CARB, 0.0), 1)

    # Coaching warnings — situational notes that surface at the right moment.
    warnings: list[str] = []
    lean_threshold_male = 10.0
    lean_threshold_female = 16.0
    lean_threshold = lean_threshold_male if sex == "male" else lean_threshold_female
    # Target BF for transition from cut → lean bulk (user-specific; defaults
    # to 12% male / 18% female which is roughly the "visible abs + muscle
    # retention window" most bodybuilders rebuild from).
    target_cut_bf_male = 12.0
    target_cut_bf_female = 18.0
    target_cut_bf = target_cut_bf_male if sex == "male" else target_cut_bf_female

    # ──────────────────────────────────────────────────────────────────────
    # CUT phase notes — drive the athlete toward the target then transition.
    # ──────────────────────────────────────────────────────────────────────
    if phase_lower == "cut" and body_fat_pct is not None:
        if body_fat_pct > target_cut_bf + 4:
            warnings.append(
                f"You're at {body_fat_pct:.1f}% BF — keep running the cut. Target: {target_cut_bf:.0f}% "
                f"({(body_fat_pct - target_cut_bf):.1f}% to go). Expect ~0.5% BF loss per week on a clean deficit."
            )
        elif body_fat_pct > target_cut_bf + 1:
            warnings.append(
                f"Closing in on your target ({body_fat_pct:.1f}% now → {target_cut_bf:.0f}% target). "
                f"Tighten adherence for the final stretch. Once you hit {target_cut_bf:.0f}%, transition to LEAN BULK: "
                f"+250-400 kcal (mostly carbs), protein stays 2.0-2.2 g/kg. Expect 0.25-0.4 kg/week gain."
            )
        else:
            warnings.append(
                f"🎯 Target reached ({body_fat_pct:.1f}%). Switch to LEAN BULK: +300 kcal/day "
                f"(mostly carbs), protein 2.0-2.2 g/kg, fat floor 0.9 g/kg. Track weekly — "
                f"if BF climbs past {target_cut_bf + 2:.0f}%, stall the surplus and reassess."
            )
        if body_fat_pct <= lean_threshold:
            warnings.append(
                "Alcohol is strictly off during final 8 weeks of prep — it dehydrates, "
                "impairs CNS recovery, and interferes with glycogen storage."
            )

    # ──────────────────────────────────────────────────────────────────────
    # BULK / LEAN BULK phase notes — warn before overshooting
    # ──────────────────────────────────────────────────────────────────────
    if phase_lower in ("bulk", "lean_bulk") and body_fat_pct is not None:
        overshoot_bf = target_cut_bf + 6  # +6% over target = time to cut
        if body_fat_pct >= overshoot_bf:
            warnings.append(
                f"⚠️ Body fat has climbed to {body_fat_pct:.1f}% — time to wind down the bulk and start a mini-cut. "
                f"Your next phase target: get back to {target_cut_bf:.0f}% BF before another surplus."
            )
        elif body_fat_pct >= target_cut_bf + 3:
            warnings.append(
                f"You're {body_fat_pct:.1f}% BF — edging toward cut territory. "
                f"Hold surplus tight; rate of gain should be < 0.3 kg/week or the cut will be long."
            )
        else:
            warnings.append(
                f"Bulk is clean ({body_fat_pct:.1f}% BF). Aim for 0.25-0.4 kg/week. "
                f"If weight stalls 2+ weeks at high adherence, add +100-150 kcal carbs."
            )
        warnings.append(
            "Peri-workout carbs matter in a surplus: eat 50-80g fast carbs within 60 min pre/post training."
        )

    # ──────────────────────────────────────────────────────────────────────
    # MAINTAIN phase — useful for reassessment windows
    # ──────────────────────────────────────────────────────────────────────
    if phase_lower == "maintain":
        warnings.append(
            "Maintenance is a reset window. Track weight daily — if it's stable ±0.5 kg for "
            "10 days, you've found your true TDEE. From here, pick your next phase: "
            "lean bulk (+300 kcal), cut (-400 kcal), or hold steady for another block."
        )

    # ──────────────────────────────────────────────────────────────────────
    # PEAK phase — contest week is different from late cut
    # ──────────────────────────────────────────────────────────────────────
    if phase_lower == "peak":
        warnings.append(
            "Peak week is precision work — DO NOT improvise. Follow the day-by-day peak "
            "protocol: depletion → load → show day. Trust the plan, avoid new foods, "
            "hydrate on schedule."
        )
        if body_fat_pct is not None and body_fat_pct <= lean_threshold:
            warnings.append(
                "Alcohol is strictly off during final 8 weeks of prep — it dehydrates, "
                "impairs CNS recovery, and interferes with glycogen storage."
            )

    # ──────────────────────────────────────────────────────────────────────
    # Female-specific hormonal health guardrail
    # ──────────────────────────────────────────────────────────────────────
    if fat_floor < 0.6 and sex == "female":
        warnings.append(
            "Female athletes should never drop below 0.6 g/kg fat — hormonal health "
            "and menstrual function are non-negotiable."
        )

    # ──────────────────────────────────────────────────────────────────────
    # Universal tracking reminder for deficit phases
    # ──────────────────────────────────────────────────────────────────────
    if phase_lower in ("cut", "peak"):
        warnings.append(
            "Track body weight + waist daily. A single bad data point is noise; "
            "trust 7-day rolling trends over single-day spikes."
        )

    return {
        "protein_g": protein_g,
        "fat_g": fat_g,
        "carbs_g": carbs_g,
        "target_calories": round(target_calories, 0),
        "coach_warnings": warnings,
    }


def compute_training_rest_day_macros(
    base_macros: dict,
    weight_kg: float,
    days_per_week: int = 5,
    phase: str = "maintain",
    body_fat_pct: float | None = None,
    sex: str = "male",
) -> dict:
    """
    Split the flat macro prescription into training-day and rest-day targets.

    Uses weekly-neutral carb cycling: the total weekly carb budget is
    preserved across training and rest days.  Training days receive ~25%
    more carbs than rest days, with fat adjusted to keep weekly calories
    roughly the same.

    Args:
        base_macros: Output of :func:`compute_macros` (with ``carbs_g``,
                     ``fat_g``, ``protein_g``, ``target_calories``).
        weight_kg: Body weight in kg (used to ensure fat floor is maintained).
        days_per_week: Number of training days per week (default 5).

    Returns:
        Dict with ``training_day`` and ``rest_day`` sub-dicts, each
        containing ``protein_g``, ``carbs_g``, ``fat_g``,
        ``target_calories``.
    """
    base_carbs = base_macros["carbs_g"]
    base_fat = base_macros["fat_g"]
    base_protein = base_macros["protein_g"]
    fat_floor = round(_fat_floor_for_context(phase, body_fat_pct, sex) * weight_kg, 1)

    rest_days = 7 - days_per_week

    # Weekly carb budget must be preserved: 7 × base_carbs
    # Solve: (days_per_week × train_carbs) + (rest_days × rest_carbs) = 7 × base_carbs
    # With constraint: train_carbs = rest_carbs × ratio
    # ratio chosen so training days get proportionally more carbs
    if rest_days > 0 and days_per_week > 0:
        # Target: training days get ~25% more carbs than rest days
        ratio = 1.25
        # rest_carbs × (days_per_week × ratio + rest_days) = 7 × base_carbs
        rest_carbs = round((7.0 * base_carbs) / (days_per_week * ratio + rest_days), 1)
        train_carbs = round(rest_carbs * ratio, 1)
    else:
        train_carbs = base_carbs
        rest_carbs = base_carbs

    # Adjust fat to keep weekly calories roughly the same
    extra_carb_kcal = (train_carbs - base_carbs) * _KCAL_PER_G_CARB
    train_fat = round(max(fat_floor, base_fat - extra_carb_kcal / _KCAL_PER_G_FAT), 1)
    train_cals = round(base_protein * 4 + train_carbs * 4 + train_fat * 9, 0)

    saved_carb_kcal = (base_carbs - rest_carbs) * _KCAL_PER_G_CARB
    rest_fat = round(base_fat + saved_carb_kcal / _KCAL_PER_G_FAT, 1)
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

    # Fat — restoration phase uses 0.9 g/kg (rebuilding hormonal function)
    fat_floor = _fat_floor_for_context("restoration")
    fat_g = round(fat_floor * weight_kg, 1)
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


def compute_division_nutrition_priorities(
    division: str,
    phase: str,
    body_fat_pct: float | None = None,
    sex: str = "male",
) -> dict:
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
        "wellness": {
            # Lower-body-dominant division. Higher glute/hamstring volume
            # demands more carbs on leg days; upper body stays moderate.
            "protein_per_kg": {"bulk": 1.8, "cut": 2.2, "maintain": 2.0, "peak": 2.2, "restoration": 2.0},
            "carb_cycling_factor": 0.30,
            "fat_per_kg_floor": 0.80,
            "meal_frequency_target": 5,
            "mps_threshold_g": 32,
            "notes": [
                "Lower-body dominant — carb cycling prioritises glute/hamstring training days.",
                "Upper body should stay soft — moderate surplus avoids over-developing shoulders/back.",
                "Hormonal health is non-negotiable — fat stays ≥0.8 g/kg even during prep.",
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

    # Dynamic carb cycling by body fat — elite late-cut prep widens the
    # swing to preserve glycogen fullness on training days while running
    # a steeper deficit on rest days.
    carb_swing = profile["carb_cycling_factor"]
    if phase_key in ("cut", "mini_cut") and body_fat_pct is not None:
        lean_threshold = 8.0 if sex == "male" else 14.0
        if body_fat_pct <= lean_threshold:
            carb_swing = min(0.40, carb_swing + 0.10)
        elif body_fat_pct <= lean_threshold + 3:
            carb_swing = min(0.37, carb_swing + 0.05)

    return {
        "protein_per_kg_override": clamped_override,
        "carb_cycling_factor": round(carb_swing, 3),
        "fat_per_kg_floor": profile["fat_per_kg_floor"],
        "meal_frequency_target": profile["meal_frequency_target"],
        "mps_threshold_g": profile["mps_threshold_g"],
        "notes": profile["notes"],
    }


def compute_energy_availability(
    consumed_calories: float,
    exercise_energy_expenditure: float,
    ffm_kg: float,
) -> dict:
    """Compute energy availability (EA) per kg fat-free mass.

    Below 30 kcal/kg FFM/day, females risk RED-S (Relative Energy
    Deficiency in Sport) — menstrual dysfunction, bone loss, impaired recovery.
    """
    if ffm_kg <= 0:
        return {"energy_availability_kcal_per_kg_ffm": 0, "status": "error", "message": "Invalid FFM"}

    ea = (consumed_calories - exercise_energy_expenditure) / ffm_kg

    if ea < 30:
        status = "danger"
        message = (
            f"Energy availability is {ea:.0f} kcal/kg FFM — below the 30 kcal/kg RED-S threshold. "
            "Risk of menstrual dysfunction, bone density loss, and impaired recovery. "
            "Increase caloric intake or reduce training volume immediately."
        )
    elif ea < 45:
        status = "caution"
        message = (
            f"Energy availability is {ea:.0f} kcal/kg FFM — in the caution zone (30-45). "
            "Monitor for signs of hormonal disruption, fatigue, and mood changes."
        )
    else:
        status = "adequate"
        message = f"Energy availability is {ea:.0f} kcal/kg FFM — adequate for health and performance."

    return {
        "energy_availability_kcal_per_kg_ffm": round(ea, 1),
        "status": status,
        "message": message,
    }


def compute_peri_workout_carb_split(carbs_g: float, meal_count: int = 5) -> dict:
    """
    Distribute carbohydrates across the day with peri-workout prioritisation.

    Allocation (research-validated — 55% total peri-workout):
      - Pre-workout (2-3 h before training):  25% of daily carbs
      - Intra-workout (during training):       8% (fast carbs — dextrose/gels)
      - Post-workout (within 1 h after):       22% of daily carbs
      - Remaining meals split across the rest: 45% distributed evenly

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
    pre_g    = round(carbs_g * 0.25, 1)
    intra_g  = round(carbs_g * 0.08, 1)
    post_g   = round(carbs_g * 0.22, 1)
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


# Intra-workout HBCD scaling by session muscle tags
# Large compound sessions (legs, back) deplete 2-3x more glycogen than isolation days
INTRA_HBCD_BY_MUSCLE: dict[str, int] = {
    "quads": 50, "hamstrings": 50, "glutes": 40, "back": 45,
    "chest": 25, "front_delt": 20, "side_delt": 15, "rear_delt": 15,
    "shoulders": 25,
    "biceps": 0, "triceps": 0, "forearms": 0, "calves": 0, "abs": 0, "traps": 10,
}


def compute_chrono_meal_plan(
    daily_macros: dict,
    training_start_time: str,
    training_duration_min: int = 90,
    meal_count: int = 5,
    session_muscles: list[str] | None = None,
) -> list[dict]:
    """
    Generate a chrono-nutrient meal plan anchored to the training window.

    Distributes daily macros across meals with peri-workout optimization:
    - Pre-workout (90-120 min before): high protein + carbs, minimal fat
    - Intra-workout (scaled by session muscle tags): EAAs + HBCD
    - Post-workout (within 60 min after): highest carb meal
    - Remaining meals spaced 3.5-4 hours apart

    Args:
        daily_macros: {protein_g, carbs_g, fat_g, target_calories}
        training_start_time: "HH:MM" format (e.g., "17:30")
        training_duration_min: training session length in minutes
        meal_count: total meals per day (3-6, default 5)
        session_muscles: list of muscle group tags for today's session
            (e.g. ["quads", "hamstrings", "glutes"]). Used to scale
            intra-workout HBCD prescription by glycogen demand.

    Returns:
        List of meal dicts with time, macro targets, and labels.
    """
    # Parse training time
    parts = training_start_time.split(":")
    train_hour = int(parts[0])
    train_min = int(parts[1]) if len(parts) > 1 else 0

    protein = daily_macros.get("protein_g", 180)
    carbs = daily_macros.get("carbs_g", 300)
    fat = daily_macros.get("fat_g", 70)

    meals = []

    # Pre-workout: 90 min before training, high carb + protein, very low fat
    pre_hour = train_hour - 2 if train_min < 30 else train_hour - 1
    pre_min = (train_min + 30) % 60 if train_min >= 30 else train_min + 30
    pre_carbs = round(carbs * 0.35, 0)
    pre_protein = round(protein / meal_count * 1.1, 0)
    pre_fat = round(min(5.0, fat * 0.05), 0)

    # Post-workout: largest carb meal (within 60 min after session ends)
    end_hour = train_hour + training_duration_min // 60
    end_min = train_min + training_duration_min % 60
    if end_min >= 60:
        end_hour += 1
        end_min -= 60
    post_hour = end_hour
    post_min = end_min + 30
    if post_min >= 60:
        post_hour += 1
        post_min -= 60
    post_carbs = round(carbs * 0.25, 0)
    post_protein = round(protein / meal_count * 1.2, 0)
    post_fat = round(min(5.0, fat * 0.05), 0)

    # Intra-workout: HBCD scaled by muscle group glycogen demand
    # Large muscle groups (quads, hamstrings, back) deplete glycogen heavily;
    # small muscles (arms, calves) rely on pre-workout meal only.
    intra = None
    if training_duration_min > 75:
        if session_muscles:
            # Take the max HBCD demand from the session's muscle tags
            intra_carbs = max(
                (INTRA_HBCD_BY_MUSCLE.get(m.lower(), 20) for m in session_muscles),
                default=20,
            )
        else:
            intra_carbs = 20  # fallback when no session info
        if intra_carbs > 0:
            intra_note = f"15g EAA + {intra_carbs}g HBCD (scaled to session demand)"
            intra = {
                "label": "Intra-Workout",
                "time": f"{train_hour:02d}:{train_min:02d}",
                "protein_g": 0,
                "eaa_g": 15,
                "carbs_g": intra_carbs,
                "fat_g": 0,
                "note": intra_note,
            }
        else:
            intra = None  # arms/calves day — rely on pre-workout meal

    # Remaining macros after peri-workout allocation
    remaining_protein = protein - pre_protein - post_protein
    remaining_carbs = carbs - pre_carbs - post_carbs - (intra["carbs_g"] if intra else 0)
    remaining_fat = fat - pre_fat - post_fat
    remaining_meals = meal_count - 2  # minus pre and post

    # Distribute remaining meals evenly, spaced 3.5-4 hours
    # Calculate available time windows (assume 8am wake, last meal 3h before sleep)
    other_meals = []
    per_meal_protein = round(max(0, remaining_protein) / max(1, remaining_meals), 0)
    per_meal_carbs = round(max(0, remaining_carbs) / max(1, remaining_meals), 0)
    per_meal_fat = round(max(0, remaining_fat) / max(1, remaining_meals), 0)

    # Simple spacing: start at 8am, space by 4 hours, skip peri-workout window
    meal_hour = 8
    meal_num = 1
    for _ in range(remaining_meals):
        # Skip if this meal overlaps with pre/post workout window
        while abs(meal_hour - pre_hour) < 2 or abs(meal_hour - post_hour) < 2:
            meal_hour += 1
        if meal_hour > 22:
            break
        other_meals.append({
            "label": f"Meal {meal_num}",
            "time": f"{meal_hour:02d}:00",
            "protein_g": int(per_meal_protein),
            "carbs_g": int(per_meal_carbs),
            "fat_g": int(per_meal_fat),
        })
        meal_num += 1
        meal_hour += 4

    # Last meal: casein-dominant (if there's room)
    if other_meals:
        other_meals[-1]["label"] = f"Meal {meal_num - 1} (Casein)"
        other_meals[-1]["note"] = "Slow-digesting protein before sleep"

    # Assemble in chronological order
    all_meals = []
    for m in other_meals:
        if int(m["time"].split(":")[0]) < pre_hour:
            all_meals.append(m)

    all_meals.append({
        "label": "Pre-Workout",
        "time": f"{pre_hour:02d}:{pre_min:02d}",
        "protein_g": int(pre_protein),
        "carbs_g": int(pre_carbs),
        "fat_g": int(pre_fat),
        "note": "High protein + complex carbs, strict <10g fat for rapid gastric emptying",
    })

    if intra:
        all_meals.append(intra)

    all_meals.append({
        "label": "Post-Workout",
        "time": f"{post_hour:02d}:{post_min:02d}",
        "protein_g": int(post_protein),
        "carbs_g": int(post_carbs),
        "fat_g": int(post_fat),
        "note": "Highest carb meal — maximize glycogen resynthesis",
    })

    for m in other_meals:
        if int(m["time"].split(":")[0]) >= post_hour + 2:
            all_meals.append(m)

    return all_meals


# ---------------------------------------------------------------------------
# Phase transition macro adjustment (Block 5)
# ---------------------------------------------------------------------------

_PHASE_CALORIE_MODIFIERS: dict[str, float] = {
    "offseason": 1.10,     # +10% surplus
    "bulk": 1.15,          # +15% surplus
    "lean_bulk": 1.05,     # +5% surplus
    "maintain": 1.00,
    "cut": 0.80,           # -20% deficit
    "mini_cut": 0.78,      # -22% deficit (aggressive 4-week)
    "peak_week": 0.70,     # -30% contest prep
    "contest": 0.90,       # carb-up
    "restoration": 1.05,   # reverse diet +5%
}


def adjust_macros_for_phase(
    current_calories: float,
    current_protein_g: float,
    current_carbs_g: float,
    current_fat_g: float,
    from_phase: str,
    to_phase: str,
) -> dict:
    """
    Adjust macros when transitioning between nutrition phases.
    Protein stays high; carbs/fat adjust proportionally to new calorie target.
    """
    from_mod = _PHASE_CALORIE_MODIFIERS.get(from_phase, 1.0)
    to_mod = _PHASE_CALORIE_MODIFIERS.get(to_phase, 1.0)

    # Estimate TDEE from current calories and phase modifier
    estimated_tdee = current_calories / from_mod if from_mod else current_calories
    new_calories = round(estimated_tdee * to_mod)

    # Protein stays the same or increases during cuts
    new_protein = current_protein_g
    if to_phase in ("cut", "mini_cut", "peak_week"):
        new_protein = round(max(current_protein_g, current_protein_g * 1.1), 1)  # +10% protein in deficit

    protein_cals = new_protein * 4
    remaining_cals = max(0, new_calories - protein_cals)

    # Fat: minimum 0.8g/kg estimate (~64g for 80kg), rest goes to carbs
    new_fat = round(max(current_fat_g * 0.8, remaining_cals * 0.25 / 9), 1)
    fat_cals = new_fat * 9
    new_carbs = round(max(0, (remaining_cals - fat_cals) / 4), 1)

    return {
        "calories": new_calories,
        "protein_g": new_protein,
        "carbs_g": new_carbs,
        "fat_g": new_fat,
    }


# ---------------------------------------------------------------------------
# Hydration prescription
# ---------------------------------------------------------------------------
#
# Olympia-level prep demands deliberate water intake. Guidelines synthesised
# from Armstrong (2007), IOC consensus (2019) and contest prep literature:
#   Offseason / maintain:  35 ml/kg BW
#   Bulk / lean_bulk:      38 ml/kg BW  (higher protein turnover, more sweat)
#   Cut / mini_cut:        42 ml/kg BW  (satiety aid, thermogenic, electrolyte turnover)
#   Peak week (load days): 50 ml/kg BW  (glycogen compartmentalization)
#   Peak week (cut days):  progressive restriction — handled in peak_week.py
#   Contest day:           sip strategy — handled in peak_week.py
#
# On top of the baseline, hot climates add +500 ml and each training session
# adds ~500 ml (replacing ~1% BW sweat loss, typical for 60-min session).

_HYDRATION_ML_PER_KG: dict[str, float] = {
    "offseason":   35.0,
    "maintain":    35.0,
    "bulk":        38.0,
    "lean_bulk":   38.0,
    "cut":         42.0,
    "mini_cut":    42.0,
    "restoration": 36.0,
    "peak_week":   50.0,
    "peak":        50.0,
    "contest":     0.0,   # handled separately by peak_week.py
}


def compute_hydration_target(
    weight_kg: float,
    phase: str,
    training_session_today: bool = True,
    hot_climate: bool = False,
) -> dict:
    """Daily hydration prescription in millilitres and ounces.

    Returns ``{baseline_ml, training_add_ml, climate_add_ml, total_ml, total_oz,
    per_hour_awake_ml, coaching_note}``. ``per_hour_awake_ml`` assumes a 16-hour
    waking day and spreads intake evenly so athletes don't gulp 2 L pre-sleep.
    """
    key = (phase or "maintain").strip().lower()
    per_kg = _HYDRATION_ML_PER_KG.get(key, 35.0)
    baseline = per_kg * max(weight_kg, 40.0)
    training_add = 500.0 if training_session_today else 0.0
    climate_add = 500.0 if hot_climate else 0.0
    total_ml = round(baseline + training_add + climate_add)
    total_oz = round(total_ml / 29.5735, 1)
    per_hour = round(total_ml / 16.0)

    coaching_note = (
        f"Sip ~{per_hour} ml every waking hour. Stop 2 h before bed to avoid "
        f"mid-night wake-ups. Add ~500 ml extra per intense training session."
    )
    if key in ("cut", "mini_cut"):
        coaching_note += " Higher intake aids satiety and thermogenesis during deficit."
    elif key in ("peak_week", "peak"):
        coaching_note += " Peak-week protocol may override — see peak-week page for day-by-day schedule."

    return {
        "baseline_ml": round(baseline),
        "training_add_ml": round(training_add),
        "climate_add_ml": round(climate_add),
        "total_ml": total_ml,
        "total_oz": total_oz,
        "per_hour_awake_ml": per_hour,
        "coaching_note": coaching_note,
    }


# ---------------------------------------------------------------------------
# Protein distribution validator
# ---------------------------------------------------------------------------
#
# Leucine-driven muscle protein synthesis plateaus at ~0.40 g protein / kg BW
# per dose (Moore et al. 2015, Schoenfeld & Aragon 2018). Elite prep aims to
# hit this threshold 4–6 times daily to maximise anabolic signaling windows.
#
# This helper validates a meal plan's distribution and returns a list of
# violations (meal-level info + what it would take to fix them).

_MPS_THRESHOLD_PER_KG = 0.40   # leucine threshold
_MPS_CEILING_PER_KG = 0.55     # above this has diminishing returns


def validate_protein_distribution(
    meals: list[dict],
    weight_kg: float,
) -> dict:
    """Check per-meal protein adequacy.

    ``meals`` is a list of dicts each containing at least ``{"label": str,
    "ingredients": [{"protein_g": float, ...}, ...]}`` — the ``Meal.to_dict``
    output is directly compatible.

    Returns ``{all_meals_pass, violations, target_per_meal_g, ceiling_per_meal_g,
    total_protein_g, recommended_meal_count}``.
    """
    target_per_meal = round(_MPS_THRESHOLD_PER_KG * weight_kg, 1)
    ceiling_per_meal = round(_MPS_CEILING_PER_KG * weight_kg, 1)

    # Only real meals (with ingredients) contribute MPS signalling — a fasted
    # placeholder slot doesn't count.
    scored = []
    total_protein = 0.0
    for m in meals:
        ingredients = m.get("ingredients") or []
        if not ingredients:
            continue
        protein = sum(float(i.get("protein_g", 0) or 0) for i in ingredients)
        total_protein += protein
        scored.append({
            "meal_number": m.get("meal_number"),
            "label": m.get("label"),
            "protein_g": round(protein, 1),
            "hits_threshold": protein >= target_per_meal,
            "over_ceiling": protein > ceiling_per_meal,
        })

    violations = [s for s in scored if not s["hits_threshold"] or s["over_ceiling"]]

    # How many full-dose meals the daily total supports.
    recommended_meal_count = 0
    if target_per_meal > 0:
        recommended_meal_count = max(3, min(6, int(total_protein / target_per_meal)))

    return {
        "all_meals_pass": len(violations) == 0 and len(scored) > 0,
        "target_per_meal_g": target_per_meal,
        "ceiling_per_meal_g": ceiling_per_meal,
        "total_protein_g": round(total_protein, 1),
        "mps_dose_count": sum(1 for s in scored if s["hits_threshold"]),
        "recommended_meal_count": recommended_meal_count,
        "per_meal": scored,
        "violations": violations,
        "explanation": (
            f"Each meal should deliver ≥{target_per_meal}g protein "
            f"({_MPS_THRESHOLD_PER_KG} g/kg BW) to trigger muscle protein "
            f"synthesis. 4–6 MPS doses daily maximises anabolic windows."
        ),
    }


def compute_energy_availability_kcal_per_kg_ffm(
    target_calories: float,
    exercise_kcal_per_day: float,
    ffm_kg: float,
) -> float:
    """EA = (intake - exercise kcal) / FFM. Values <30 kcal/kg/day trigger
    relative energy deficiency (RED-S). Elite coaches hard-refeed below 30."""
    if ffm_kg <= 0:
        return 0.0
    return round((target_calories - exercise_kcal_per_day) / ffm_kg, 1)


# ---------------------------------------------------------------------------
# Micronutrient + fiber coverage
# ---------------------------------------------------------------------------

def validate_micronutrient_coverage(
    meals: list[dict],
    sex: str = "male",
) -> dict:
    """Compute RDI coverage for key micronutrients + fiber from a meal plan.

    ``meals`` is the meal_planner.to_dict shape. Each ingredient contributes
    its quantity_g × per-100g micronutrient values from the food database
    fallback table. Returns a dict with per-nutrient ``{intake, target,
    coverage_pct, deficient}`` plus an overall ``deficiencies`` list for the
    UI.
    """
    from app.engines.engine3.food_database import PER_100G_MICROS, RDI_TARGETS

    targets = RDI_TARGETS.get((sex or "male").lower(), RDI_TARGETS["male"])
    totals: dict[str, float] = {k: 0.0 for k in targets}

    for meal in meals or []:
        for ing in meal.get("ingredients") or []:
            name = ing.get("name", "")
            qty_g = float(ing.get("quantity_g", 0) or 0)
            if qty_g <= 0:
                continue
            micros = PER_100G_MICROS.get(name) or {}
            factor = qty_g / 100.0
            for key in totals:
                if key in micros:
                    totals[key] += micros[key] * factor

    coverage = {}
    deficiencies: list[str] = []
    for key, target in targets.items():
        intake = round(totals[key], 1)
        pct = round(intake / target * 100.0, 1) if target > 0 else 0.0
        deficient = pct < 75.0
        coverage[key] = {
            "intake": intake,
            "target": target,
            "coverage_pct": pct,
            "deficient": deficient,
        }
        if deficient:
            deficiencies.append(key)

    return {
        "coverage": coverage,
        "deficiencies": deficiencies,
        "rdi_notes": _MICRONUTRIENT_COACHING_NOTES if deficiencies else [],
    }


_MICRONUTRIENT_COACHING_NOTES: list[str] = [
    "Iron: add red meat, oysters, spinach, or iron-fortified cereals.",
    "Zinc: oysters, beef, pumpkin seeds, or zinc supplementation.",
    "Magnesium: pumpkin seeds, almonds, dark leafy greens, dark chocolate.",
    "Calcium: dairy, sardines with bones, fortified plant milks.",
    "Vitamin D: fatty fish, fortified milk, or 1000-2000 IU supplement.",
    "Fiber: add vegetables, berries, oats, chia/flax, or psyllium husk.",
    "Potassium: potato, banana, coconut water, leafy greens.",
]
