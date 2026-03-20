"""
Engine 3 — Nutrition Controller: Energy Balance (Thermodynamic) Module

Pure math module for tracking energy surplus/deficit and projecting
body-mass changes.  No DB or HTTP imports.
"""


# Approximate kcal equivalence of 1 kg body-mass change
_KCAL_PER_KG = 7700.0

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
) -> float:
    """Project body-mass change from a sustained weekly energy balance.

    Uses the approximation that 7 700 kcal corresponds to 1 kg of
    body-mass change.

    Parameters
    ----------
    energy_balance_weekly_avg : float
        Average *daily* energy balance (kcal) over the period.  Positive
        means surplus, negative means deficit.
    weeks : float
        Duration of the projection in weeks.

    Returns
    -------
    float
        Expected weight change in kg (positive = gain, negative = loss).
    """
    total_surplus_kcal = energy_balance_weekly_avg * 7.0 * weeks
    return total_surplus_kcal / _KCAL_PER_KG


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
