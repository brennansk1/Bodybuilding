"""
Weight Cap Calculator

Estimates maximum competitive stage weight based on structural anchors
(height, wrist, ankle) using adapted Casey Butt formulas.
"""
import math


def compute_weight_cap(
    height_cm: float,
    wrist_cm: float | None = None,
    ankle_cm: float | None = None,
    body_fat_pct: float = 5.0,
    sex: str = "male",
) -> dict[str, float]:
    """
    Compute maximum lean body mass and stage weight.

    Returns:
        {
            "max_lbm_kg": float,
            "stage_weight_kg": float,
            "offseason_weight_kg": float,
        }
    """
    # Default structural anchors if not provided
    if wrist_cm is None:
        wrist_cm = 17.8 if sex == "male" else 15.2
    if ankle_cm is None:
        ankle_cm = 23.0 if sex == "male" else 20.5

    height_in = height_cm / 2.54
    wrist_in = wrist_cm / 2.54
    ankle_in = ankle_cm / 2.54

    if sex == "male":
        # Adapted Casey Butt formula
        max_lbm_lbs = (
            height_in ** 1.5
            * (math.sqrt(wrist_in) / 22.6670 + math.sqrt(ankle_in) / 17.0104)
            * (1 + body_fat_pct / 224)
        )
    else:
        max_lbm_lbs = (
            height_in ** 1.5
            * (math.sqrt(wrist_in) / 25.0 + math.sqrt(ankle_in) / 19.0)
            * (1 + body_fat_pct / 224)
        ) * 0.85

    max_lbm_kg = max_lbm_lbs * 0.453592
    bf_fraction = body_fat_pct / 100
    stage_weight = max_lbm_kg / (1 - bf_fraction)
    offseason_bf = 0.12 if sex == "male" else 0.18
    offseason_weight = max_lbm_kg / (1 - offseason_bf)

    return {
        "max_lbm_kg": round(max_lbm_kg, 1),
        "stage_weight_kg": round(stage_weight, 1),
        "offseason_weight_kg": round(offseason_weight, 1),
    }


def compute_max_circumferences(
    height_cm: float,
    wrist_cm: float | None = None,
    ankle_cm: float | None = None,
    sex: str = "male",
) -> dict[str, float]:
    """
    Predict maximum muscular circumferences at genetic ceiling (~5% BF)
    using Casey Butt per-site regression formulas.

    These represent the absolute maximum lean measurements a natural athlete
    can achieve given their skeletal frame. Division ceiling factors are then
    applied to get division-specific ideals.

    Args:
        height_cm: athlete height
        wrist_cm:  wrist circumference (arm frame anchor)
        ankle_cm:  ankle circumference (leg frame anchor)
        sex:       "male" or "female"

    Returns:
        {site: max_circumference_cm} for muscle sites
        (waist/hips excluded — those are "stay small" targets, not maximums)
    """
    if wrist_cm is None:
        wrist_cm = 17.8 if sex == "male" else 15.2
    if ankle_cm is None:
        ankle_cm = 23.0 if sex == "male" else 20.5

    h = height_cm / 2.54   # inches
    w = wrist_cm / 2.54
    a = ankle_cm / 2.54

    if sex == "male":
        max_in = {
            "bicep":    1.1709 * w + 0.1350 * h,
            "forearm":  0.950 * w + 0.1041 * h,
            "chest":    1.625 * w + 1.3682 * a + 0.3562 * h,
            "neck":     1.1 * w + 0.1264 * h,
            "thigh":    1.4737 * a + 0.1918 * h,
            "calf":     0.9812 * a + 0.125 * h,
            # Back width (axillary breadth): primary driver is height (torso frame),
            # secondary is ankle (pelvis/hip structure correlates with back depth).
            # 0.265 × height gives ~47 cm at 178 cm — consistent with elite natural Open.
            "back_width": 0.265 * h,
        }
    else:
        max_in = {
            "bicep":    0.950 * w + 0.110 * h,
            "forearm":  0.780 * w + 0.085 * h,
            "chest":    1.350 * w + 1.130 * a + 0.290 * h,
            "neck":     0.900 * w + 0.103 * h,
            "thigh":    1.250 * a + 0.160 * h,
            "calf":     0.830 * a + 0.105 * h,
            "back_width": 0.215 * h,
        }

    max_cm = {site: round(val * 2.54, 1) for site, val in max_in.items()}

    # Shoulders: chest circumference + deltoid mass premium (~6.2%)
    max_cm["shoulders"] = round(max_cm["chest"] * 1.062, 1)

    return max_cm
