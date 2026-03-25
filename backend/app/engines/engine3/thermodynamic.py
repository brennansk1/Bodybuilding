"""
Engine 3 — Nutrition Controller: Energy Balance (Thermodynamic) Module

Pure math module for tracking energy surplus/deficit and projecting
body-mass changes.  No DB or HTTP imports.
"""


# Phase-specific energy equivalents (kcal per kg body mass change)
# Fat tissue: ~7700 kcal/kg | Muscle tissue: ~2500 kcal/kg
# Mixed gain (bulk): ~4500 kcal/kg (muscle + glycogen + water + some fat)
# Mixed loss (cut): ~6500 kcal/kg (mostly fat with some lean tissue)
_KCAL_PER_KG_BY_PHASE = {
    "bulk": 4500.0,      # lean tissue accretion is metabolically cheaper
    "lean_bulk": 4500.0,
    "cut": 6500.0,       # mostly fat loss, some lean tissue
    "maintain": 7700.0,  # standard approximation
    "peak": 7700.0,      # extreme deficit, high fat proportion
    "restoration": 5500.0,  # rebuilding lean tissue post-show
}
_KCAL_PER_KG_DEFAULT = 7700.0

# Sex-specific caloric floors (kcal/day) — safety thresholds
_MIN_CALORIES = {
    "male":   1500.0,
    "female": 1200.0,
}


def compute_energy_balance(consumed_calories: float, tdee: float) -> float:
    """Return the daily energy balance (surplus or deficit).

    Parameters
    ----------
    consumed_calories : float
        Total calories consumed in one day.
    tdee : float
        Total daily energy expenditure.

    Returns
    -------
    float
        Positive value indicates a surplus; negative indicates a deficit.
    """
    return consumed_calories - tdee


def compute_expected_weight_change(
    energy_balance_weekly_avg: float,
    weeks: float,
    phase: str = "maintain",
) -> float:
    """Project body-mass change from a sustained weekly energy balance.

    Uses phase-specific energy equivalents:
    - Bulk: ~4500 kcal/kg (lean tissue accretion is metabolically cheaper)
    - Cut: ~6500 kcal/kg (mostly fat loss)
    - Maintain: ~7700 kcal/kg (standard approximation)

    Parameters
    ----------
    energy_balance_weekly_avg : float
        Average *daily* energy balance (kcal) over the period.
    weeks : float
        Duration of the projection in weeks.
    phase : str
        Training phase for energy equivalent selection.

    Returns
    -------
    float
        Expected weight change in kg (positive = gain, negative = loss).
    """
    kcal_per_kg = _KCAL_PER_KG_BY_PHASE.get(
        phase.strip().lower(), _KCAL_PER_KG_DEFAULT
    )
    total_surplus_kcal = energy_balance_weekly_avg * 7.0 * weeks
    return total_surplus_kcal / kcal_per_kg


def thermodynamic_floor(
    current_calories: float,
    min_calories_for_sex: str,
) -> float:
    """Clamp a caloric prescription to the sex-specific safety floor.

    Parameters
    ----------
    current_calories : float
        The proposed or current daily calorie target.
    min_calories_for_sex : str
        ``"male"`` or ``"female"`` (case-insensitive).

    Returns
    -------
    float
        ``max(current_calories, floor)`` — never drops below the safety
        minimum (1 500 kcal for males, 1 200 kcal for females).

    Raises
    ------
    ValueError
        If *min_calories_for_sex* is not ``"male"`` or ``"female"``.
    """
    sex_lower = min_calories_for_sex.strip().lower()
    if sex_lower not in _MIN_CALORIES:
        raise ValueError(
            f"min_calories_for_sex must be 'male' or 'female', got '{min_calories_for_sex}'"
        )

    floor = _MIN_CALORIES[sex_lower]
    return max(current_calories, floor)


# ---------------------------------------------------------------------------
# Metabolic Adaptation Modeling
# ---------------------------------------------------------------------------

def compute_adaptation_factor(weeks_in_deficit: float) -> float:
    """Return the metabolic adaptation factor for a prolonged deficit.

    Research shows TDEE can drop by ~1% per week of sustained deficit,
    plateauing at roughly 15% total adaptation (Trexler et al. 2014,
    Rosenbaum & Leibel 2010).

    Parameters
    ----------
    weeks_in_deficit : float
        Number of consecutive weeks spent in a caloric deficit.

    Returns
    -------
    float
        Multiplicative factor (0.85–1.0) to apply to baseline TDEE.
    """
    return 1.0 - 0.01 * min(weeks_in_deficit, 15)


def compute_adapted_tdee(tdee: float, weeks_in_deficit: float) -> float:
    """Return TDEE adjusted for metabolic adaptation during prolonged cuts.

    Applies an adaptation factor that reduces TDEE by ~1% per week of
    sustained deficit, capping at 15% total reduction.

    Parameters
    ----------
    tdee : float
        Baseline total daily energy expenditure (kcal).
    weeks_in_deficit : float
        Number of consecutive weeks spent in a caloric deficit.

    Returns
    -------
    float
        Adapted TDEE in kcal/day.
    """
    adaptation_factor = compute_adaptation_factor(weeks_in_deficit)
    adapted_tdee = tdee * adaptation_factor
    return round(adapted_tdee, 1)
