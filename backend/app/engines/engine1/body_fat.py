"""
Body Fat Estimation — Jackson-Pollock 7-Site Formula

Converts 7 skinfold measurements (mm) → body fat percentage.
Pure math, no DB or HTTP imports.
"""
import math


def categorize_body_fat(bf_pct: float, sex: str) -> str:
    """Return a descriptive category for a body fat percentage."""
    s = sex.strip().lower()
    if s == "male":
        if bf_pct < 5:   return "contest_ready"
        if bf_pct < 8:   return "peak_condition"
        if bf_pct < 12:  return "lean"
        if bf_pct < 16:  return "moderate"
        if bf_pct < 20:  return "average"
        return "above_average"
    else:
        if bf_pct < 12:  return "contest_ready"
        if bf_pct < 15:  return "peak_condition"
        if bf_pct < 20:  return "lean"
        if bf_pct < 25:  return "moderate"
        if bf_pct < 30:  return "average"
        return "above_average"


def lean_mass_kg(body_weight_kg: float, body_fat_pct: float) -> float:
    """Return lean body mass in kg."""
    return round(body_weight_kg * (1.0 - body_fat_pct / 100.0), 2)


def navy_body_fat(
    waist_cm: float,
    neck_cm: float,
    height_cm: float,
    sex: str,
    hips_cm: float | None = None,
) -> float:
    """Estimate body fat % using US Navy circumference method.

    Males use: waist, neck, height.
    Females use: waist, hips, neck, height.

    Returns
    -------
    float
        Estimated body fat percentage (clamped 4-50%).

    References
    ----------
    Hodgdon, J.A. & Beckett, M.B. (1984). Prediction of percent body fat for
    US Navy men and women from body circumferences and height.
    """
    if sex.strip().lower() == "male":
        # Navy male formula
        bf = 86.010 * math.log10(waist_cm - neck_cm) - 70.041 * math.log10(height_cm) + 36.76
    else:
        # Navy female formula — requires hips
        hips = hips_cm or waist_cm * 1.1
        bf = 163.205 * math.log10(waist_cm + hips - neck_cm) - 97.684 * math.log10(height_cm) - 78.387
    return round(max(4.0, min(bf, 50.0)), 1)


def jackson_pollock_7(
    chest: float,
    midaxillary: float,
    tricep: float,
    subscapular: float,
    abdominal: float,
    suprailiac: float,
    thigh: float,
    age: int,
    sex: str,
) -> float:
    """Estimate body fat % using Jackson-Pollock 7-site skinfold formula.

    Parameters
    ----------
    chest, midaxillary, tricep, subscapular, abdominal, suprailiac, thigh
        Skinfold thickness at each site in millimetres.
    age : int
        Age in years.
    sex : str
        "male" or "female".

    Returns
    -------
    float
        Estimated body fat percentage.

    References
    ----------
    Jackson, A.S. & Pollock, M.L. (1978). Generalized equations for predicting
    body density of men. British Journal of Nutrition, 40(3), 497-504.

    Jackson, A.S., Pollock, M.L. & Ward, A. (1980). Generalized equations for
    predicting body density of women. Medicine and Science in Sports and
    Exercise, 12(3), 175-182.

    Siri, W.E. (1961). Body composition from fluid spaces and density.
    """
    s = chest + midaxillary + tricep + subscapular + abdominal + suprailiac + thigh

    sex_lower = sex.strip().lower()
    if sex_lower == "male":
        # Jackson-Pollock male body density
        density = (
            1.112
            - 0.00043499 * s
            + 0.00000055 * s * s
            - 0.00028826 * age
        )
    else:
        # Jackson-Pollock female body density
        density = (
            1.097
            - 0.00046971 * s
            + 0.00000056 * s * s
            - 0.00012828 * age
        )

    # Siri equation: BF% = (495 / density) - 450
    bf_pct = (495.0 / density) - 450.0
    return round(max(2.0, min(bf_pct, 55.0)), 1)


def parrillo_9(
    chest: float,
    tricep: float,
    subscapular: float,
    abdominal: float,
    suprailiac: float,
    thigh: float,
    bicep: float,
    lower_back: float,
    calf: float,
    body_weight_lbs: float,
) -> float:
    """Estimate body fat % using Parrillo 9-site linear model.

    Better for tracking regional "stubborn" fat (lower back, calves)
    that Jackson-Pollock underweights.

    Parameters
    ----------
    chest, tricep, subscapular, abdominal, suprailiac, thigh, bicep,
    lower_back, calf
        Skinfold thickness at each site in millimetres.
    body_weight_lbs : float
        Body weight in pounds.

    Returns
    -------
    float
        Estimated body fat percentage (clamped 2-55%).
    """
    s9 = chest + tricep + subscapular + abdominal + suprailiac + thigh + bicep + lower_back + calf
    bf_pct = (s9 * 27.0) / body_weight_lbs
    return round(max(2.0, min(bf_pct, 55.0)), 1)


def lean_girth(total_circ_cm: float, skinfold_mm: float) -> float:
    """Compute lean (bone + muscle) girth by subtracting subcutaneous fat ring.

    The formula mathematically removes the adipose layer from the tape
    circumference using the site-specific skinfold measurement:
        C_lean = C_total - (π × S / 10)

    where S is the skinfold thickness in mm (divided by 10 → cm).

    This is far more accurate than the global √(1 − bf) adjustment because
    fat distribution is site-specific — an athlete can carry 4mm on the
    tricep but 15mm on the abdomen.

    Parameters
    ----------
    total_circ_cm : float
        Raw tape circumference at the site (cm).
    skinfold_mm : float
        Skinfold caliper reading at the corresponding site (mm).

    Returns
    -------
    float
        Lean circumference (cm).
    """
    return round(total_circ_cm - (math.pi * skinfold_mm / 10.0), 2)


def compute_bf_composite(
    skinfold_data: dict | None,
    tape_data: dict | None,
    age: int,
    sex: str,
    height_cm: float,
    body_weight_kg: float | None = None,
) -> dict:
    """
    Run all available body fat estimation methods and return a weighted
    composite with confidence scoring.

    Weights when all three methods available: JP7 = 0.5, Parrillo = 0.3,
    Navy = 0.2.

    Args:
        skinfold_data: Dict of skinfold site measurements in mm. Keys may
                       include: chest, midaxillary, tricep, subscapular,
                       abdominal, suprailiac, thigh, bicep, lower_back, calf.
        tape_data: Dict of circumference measurements in cm. Keys may
                   include: waist, neck, hips.
        age: Age in years.
        sex: "male" or "female".
        height_cm: Height in centimetres.
        body_weight_kg: Body weight in kilograms (required for Parrillo).

    Returns:
        Dict with keys:
        - ``primary_estimate``: weighted average body fat %
        - ``confidence_range``: (low, high) tuple
        - ``spread``: max - min across methods
        - ``methods_used``: list of method name strings
        - ``individual_estimates``: {method_name: bf_pct}
        - ``confidence_level``: "high" (<2% spread), "medium" (2-4%),
          "low" (>4%)
    """
    skinfold = skinfold_data or {}
    tape = tape_data or {}

    estimates: dict[str, float] = {}
    weights: dict[str, float] = {}

    # JP7 — requires all 7 sites
    jp7_sites = ["chest", "midaxillary", "tricep", "subscapular",
                 "abdominal", "suprailiac", "thigh"]
    if all(site in skinfold for site in jp7_sites):
        bf = jackson_pollock_7(
            chest=skinfold["chest"],
            midaxillary=skinfold["midaxillary"],
            tricep=skinfold["tricep"],
            subscapular=skinfold["subscapular"],
            abdominal=skinfold["abdominal"],
            suprailiac=skinfold["suprailiac"],
            thigh=skinfold["thigh"],
            age=age,
            sex=sex,
        )
        estimates["JP7"] = bf
        weights["JP7"] = 0.5

    # Navy — requires waist, neck, height
    if "waist" in tape and "neck" in tape:
        bf = navy_body_fat(
            waist_cm=tape["waist"],
            neck_cm=tape["neck"],
            height_cm=height_cm,
            sex=sex,
            hips_cm=tape.get("hips"),
        )
        estimates["Navy"] = bf
        weights["Navy"] = 0.2

    # Parrillo 9 — requires 9 skinfold sites + body weight
    parrillo_sites = ["chest", "tricep", "subscapular", "abdominal",
                      "suprailiac", "thigh", "bicep", "lower_back", "calf"]
    if all(site in skinfold for site in parrillo_sites) and body_weight_kg is not None:
        body_weight_lbs = body_weight_kg * 2.20462
        bf = parrillo_9(
            chest=skinfold["chest"],
            tricep=skinfold["tricep"],
            subscapular=skinfold["subscapular"],
            abdominal=skinfold["abdominal"],
            suprailiac=skinfold["suprailiac"],
            thigh=skinfold["thigh"],
            bicep=skinfold["bicep"],
            lower_back=skinfold["lower_back"],
            calf=skinfold["calf"],
            body_weight_lbs=body_weight_lbs,
        )
        estimates["Parrillo"] = bf
        weights["Parrillo"] = 0.3

    if not estimates:
        return {
            "primary_estimate": None,
            "confidence_range": (None, None),
            "spread": None,
            "methods_used": [],
            "individual_estimates": {},
            "confidence_level": None,
        }

    # Weighted average — re-normalise weights to the methods actually used
    total_weight = sum(weights[m] for m in estimates)
    primary = sum(estimates[m] * weights[m] / total_weight for m in estimates)

    vals = list(estimates.values())
    low = min(vals)
    high = max(vals)
    spread = high - low

    if spread < 2.0:
        confidence_level = "high"
    elif spread <= 4.0:
        confidence_level = "medium"
    else:
        confidence_level = "low"

    return {
        "primary_estimate": round(primary, 1),
        "confidence_range": (round(low, 1), round(high, 1)),
        "spread": round(spread, 1),
        "methods_used": list(estimates.keys()),
        "individual_estimates": {m: round(v, 1) for m, v in estimates.items()},
        "confidence_level": confidence_level,
    }
