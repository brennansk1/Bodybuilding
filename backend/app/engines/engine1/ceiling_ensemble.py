from __future__ import annotations

"""
Ceiling Ensemble — v2 Sprint 1

Reports the natural muscular ceiling as an envelope across three independent
models rather than a single point estimate. No one model is "truth":

    Butt 4th-ed (approx)  — anatomical regression on ~300 drug-free champions
                            1947–2010. The 4th-ed formulas (Butt 2018) drop
                            ankle from arm predictions and re-fit on a larger
                            sample. Here we approximate by multiplying the
                            1st-ed regression by a 1.04 "conservatism
                            correction" per Nuckols' validation, pending
                            direct transcription.

    Kouri bands           — statistical-population ceiling at FFMI 24/25/26.
                            Kouri 1995 found 74 drug-free athletes ≤ FFMI 25;
                            outliers reach 26-27 naturally (hyper-responders).

    Berkhan heuristic     — `stage_kg ≈ (height_cm − 100) + offset`. A crude
                            sanity check; documents the order of magnitude
                            any serious model should respect.

    IFBB class cap        — division-specific piecewise height-weight limit
                            (from constants/weight_caps.py). This is what
                            the athlete is actually judged against.

Report:
  {butt_1st, butt_4th, kouri_24, kouri_25, kouri_26, berkhan_stage_kg,
   ifbb_class_cap, envelope: {min, median, max},
   effective_ceiling: min(model_ceilings, ifbb_class_cap)}

Sources:
  - Butt, Your Muscular Potential, 4th ed. (2018); weightrainer.net
  - Kouri et al. 1995 (Clin J Sport Med 5(4):223-228)
  - Nuckols G. "What everyone gets wrong about FFMI" (2016)
  - Henselmans validation posts (2019, 2021)
  - Berkhan M. LeanGains (heuristic target ratios)
"""

import math
from statistics import median

from app.engines.engine1.weight_cap import compute_weight_cap
from app.constants.weight_caps import lookup_weight_cap


# ---------------------------------------------------------------------------
# Model 1 — Butt 1st-edition (baseline; existing compute_weight_cap)
# Model 2 — Butt 4th-edition approximation (1st-ed × 1.04 correction)
# ---------------------------------------------------------------------------
_BUTT_4TH_APPROX_MULTIPLIER = 1.04
_BUTT_4TH_APPROX_NOTE = (
    "Butt 4th-ed (2018) approximation: 1st-ed regression × 1.04. "
    "The 4th-ed formulas re-fit on a larger sample and drop ankle from "
    "arm predictions — pending direct transcription from the book."
)


def butt_1st_ceiling(
    height_cm: float,
    wrist_cm: float | None = None,
    ankle_cm: float | None = None,
    body_fat_pct: float = 5.0,
    sex: str = "male",
) -> dict:
    """Casey Butt 1st-edition regression (existing implementation)."""
    return compute_weight_cap(height_cm, wrist_cm, ankle_cm, body_fat_pct, sex)


def butt_4th_ceiling(
    height_cm: float,
    wrist_cm: float | None = None,
    ankle_cm: float | None = None,
    body_fat_pct: float = 5.0,
    sex: str = "male",
) -> dict:
    """Butt 4th-edition approximation — 1st-ed × 1.04 conservatism correction."""
    base = compute_weight_cap(height_cm, wrist_cm, ankle_cm, body_fat_pct, sex)
    return {
        "max_lbm_kg": round(base["max_lbm_kg"] * _BUTT_4TH_APPROX_MULTIPLIER, 1),
        "stage_weight_kg": round(base["stage_weight_kg"] * _BUTT_4TH_APPROX_MULTIPLIER, 1),
        "offseason_weight_kg": round(base["offseason_weight_kg"] * _BUTT_4TH_APPROX_MULTIPLIER, 1),
        "model_note": _BUTT_4TH_APPROX_NOTE,
    }


# ---------------------------------------------------------------------------
# Model 3 — Kouri bands
# ---------------------------------------------------------------------------
# Invert the Kouri normalized FFMI formula to produce an LBM ceiling:
#   ffmi_norm = (lbm / h²) + 6.3 × (1.8 − h)
#   lbm = (ffmi_norm − 6.3 × (1.8 − h)) × h²
# Kouri 1995 used 6.3 as the height correction; modern implementations
# (incl. readiness.compute_normalized_ffmi) use 6.1 interchangeably.
# We use 6.3 for citation fidelity to Kouri's original paper.
_KOURI_HEIGHT_CORRECTION = 6.3


def kouri_ceiling_lbm(height_cm: float, sex: str = "male", ffmi_target: float = 25.0) -> float:
    """Invert Kouri normalized FFMI to produce max LBM.

    ffmi_target bands:
      24.0 → "common elite natural"
      25.0 → "Kouri statistical ceiling" (94th percentile of drug-tested)
      26.0 → "rare natural outlier"

    Female scaling: Chappell 2018 + Schutz 2002 show female FFMI ≈ 0.82×
    male across populations.
    """
    h_m = height_cm / 100.0
    raw_ffmi = ffmi_target - _KOURI_HEIGHT_CORRECTION * (1.8 - h_m)
    lbm = raw_ffmi * (h_m ** 2)
    if str(sex).lower().startswith("f"):
        lbm *= 0.82
    return round(lbm, 1)


# ---------------------------------------------------------------------------
# Model 4 — Berkhan heuristic
# ---------------------------------------------------------------------------
def berkhan_ceiling_stage(height_cm: float) -> float:
    """Berkhan's LeanGains heuristic stage weight (kg).

    stage_kg ≈ (height_cm − 100) + offset
      offset = −2 for short frames (<170), 0 mid, +2 tall (>185)
    """
    base = height_cm - 100.0
    if height_cm < 170:
        return round(base - 2.0, 1)
    if height_cm > 185:
        return round(base + 2.0, 1)
    return round(base, 1)


# ---------------------------------------------------------------------------
# Ensemble envelope
# ---------------------------------------------------------------------------
def ceiling_envelope(
    height_cm: float,
    wrist_cm: float | None = None,
    ankle_cm: float | None = None,
    division: str = "classic_physique",
    sex: str = "male",
    body_fat_pct: float = 5.0,
) -> dict:
    """Compute all four model ceilings + the envelope + effective ceiling.

    Returns a dict the frontend can render as a range: three stacked bars
    for pessimistic (min) / median / ambitious (max), with the FFMI band
    indicator from `ffmi_band`.
    """
    butt_1 = butt_1st_ceiling(height_cm, wrist_cm, ankle_cm, body_fat_pct, sex)
    butt_4 = butt_4th_ceiling(height_cm, wrist_cm, ankle_cm, body_fat_pct, sex)
    k24 = kouri_ceiling_lbm(height_cm, sex, 24.0)
    k25 = kouri_ceiling_lbm(height_cm, sex, 25.0)
    k26 = kouri_ceiling_lbm(height_cm, sex, 26.0)
    berkhan_stage = berkhan_ceiling_stage(height_cm)
    ifbb_cap = lookup_weight_cap(height_cm, division)

    # Model stage-weight candidates (kg), converted to a common baseline
    # (stage weight at the division's expected BF).
    stage_bf_frac = body_fat_pct / 100.0
    stage_candidates = {
        "butt_1st":  butt_1["stage_weight_kg"],
        "butt_4th":  butt_4["stage_weight_kg"],
        "kouri_24":  round(k24 / (1.0 - stage_bf_frac), 1),
        "kouri_25":  round(k25 / (1.0 - stage_bf_frac), 1),
        "kouri_26":  round(k26 / (1.0 - stage_bf_frac), 1),
        "berkhan":   berkhan_stage,
    }

    vals = list(stage_candidates.values())
    env_min = round(min(vals), 1)
    env_max = round(max(vals), 1)
    env_median = round(median(vals), 1)

    # Effective stage ceiling: cap the model minimum at the IFBB division cap
    # (you cannot compete above it in a weight-capped division).
    effective_stage_kg = round(min(env_min, ifbb_cap), 1)

    return {
        "model_estimates": {
            "butt_1st":  butt_1,
            "butt_4th":  butt_4,
            "kouri_24_lbm_kg": k24,
            "kouri_25_lbm_kg": k25,
            "kouri_26_lbm_kg": k26,
            "berkhan_stage_kg": berkhan_stage,
            "ifbb_class_cap_kg": ifbb_cap,
        },
        "envelope_stage_kg": {
            "pessimistic": env_min,
            "median":      env_median,
            "ambitious":   env_max,
        },
        "effective_ceiling_stage_kg": effective_stage_kg,
        "division": division,
        "model_note": _BUTT_4TH_APPROX_NOTE,
    }


# ---------------------------------------------------------------------------
# FFMI probability band — doc §14
# ---------------------------------------------------------------------------
# Kouri's 25 ceiling is not a wall; it's the upper bound of a 74-person
# drug-tested sample. Surface as a probability band instead of binary.
_FFMI_BANDS: list[tuple[float, str, float]] = [
    (22.0, "common_natural",        0.999),
    (24.0, "above_average_natural", 0.97),
    (25.0, "elite_natural",         0.90),
    (26.0, "rare_elite_natural",    0.40),
    (27.0, "enhanced_likely",       0.10),
    (99.0, "enhanced_very_likely",  0.02),
]


def ffmi_band(ffmi: float) -> dict:
    """Return the band label + estimated probability the athlete is natural.

    Sources: Kouri 1995, Nuckols 2016, Henselmans 2019-2021 sample reviews.
    The probability is a population estimate, not a verdict on any
    individual — hyper-responders with elite structure reach FFMI 26+
    naturally (Pope 2000 Mr. America pre-steroid era documents some).
    """
    for upper, label, p_natural in _FFMI_BANDS:
        if ffmi < upper:
            return {"band": label, "p_natural": p_natural, "ffmi": round(ffmi, 2)}
    return {"band": "enhanced_very_likely", "p_natural": 0.02, "ffmi": round(ffmi, 2)}
