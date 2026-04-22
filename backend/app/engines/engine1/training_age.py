from __future__ import annotations

"""
Training-Age Correction (v2 Sprint 4)

Chronological training years ≠ effective training years. A "10 year lifter"
who trained 3×/week with light weights and no periodization has an effective
training age of ~3-4 years. Corrects the logistic LBM gain curve so
projections reflect the athlete's real development state, not their calendar.

Formula:
  t_effective = chronological_years × consistency × intensity × programming

Factors (each 0..1):
  consistency: 1.0 = 4+ sessions/wk, 48+ wks/yr
               0.7 = 3 sessions/wk
               0.5 = 2 sessions/wk
               0.2 = sporadic
  intensity:   1.0 = regular near-failure (RIR 0-2 on most work sets)
               0.7 = moderate (RIR 3-4)
               0.4 = light (RIR 5+)
  programming: 1.0 = periodized with progressive overload tracking
               0.7 = linear progression
               0.4 = random / no structured progression

Source: v2 doc §30; validated indirectly by Roberts et al. 2018
hyper/low-responder literature. Defaults are the documented sensible
priors when the user hasn't supplied these inputs.
"""


DEFAULT_CONSISTENCY = 0.85   # 4x/wk is typical for a committed lifter
DEFAULT_INTENSITY   = 0.75   # most committed lifters are at RIR 2-3
DEFAULT_PROGRAMMING = 0.70   # most don't use formal periodization


def effective_training_years(
    chronological_years: float,
    consistency: float | None = None,
    intensity: float | None = None,
    programming: float | None = None,
) -> float:
    """Return the effective training years given discount factors.

    When any factor is None, uses the documented prior (see module
    docstring). Priors are deliberately conservative — the system should
    underpredict effective years rather than overstate readiness.
    """
    c = DEFAULT_CONSISTENCY if consistency is None else _clip01(consistency)
    i = DEFAULT_INTENSITY   if intensity   is None else _clip01(intensity)
    p = DEFAULT_PROGRAMMING if programming is None else _clip01(programming)
    t = max(0.0, float(chronological_years))
    return round(t * c * i * p, 2)


def _clip01(v: float) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return 1.0
    if f < 0.0:
        return 0.0
    if f > 1.0:
        return 1.0
    return f


# ---------------------------------------------------------------------------
# Logistic LBM gain model (v2 Sprint 4)
# ---------------------------------------------------------------------------
# Replaces the prior exponential-halving `11 × 0.5^(years-1)` curve which
# under-predicted year-1 gains by ~50% vs the McDonald/Aragon/Helms
# consensus.
#
#   LBM(t_effective) = ceiling × (1 − exp(−k × t_effective))
#
# Differentiating gives dLBM/dt = k × (ceiling − LBM_current), the
# "remaining potential" framing that matches how McDonald, Aragon, and
# Helms all describe the gain curve in words.
#
# k is the per-month rate constant. Natural default = 0.020/month produces:
#   year 1 ≈ 21% of remaining gap
#   year 2 ≈ 17% of remaining gap
#   year 3 ≈ 13% of remaining gap
# Enhanced athletes close gaps ~1.8× faster per Helms enhanced-training
# notes; default k_enhanced = 0.036/month.
K_MONTHLY_NATURAL  = 0.020
K_MONTHLY_ENHANCED = 0.036


def logistic_lbm(
    ceiling_lbm_kg: float,
    t_effective_years: float,
    training_status: str = "natural",
) -> float:
    """LBM(t_eff) = ceiling × (1 − e^(−k × t_eff_months))."""
    import math
    months = max(0.0, t_effective_years) * 12.0
    k = K_MONTHLY_ENHANCED if training_status == "enhanced" else K_MONTHLY_NATURAL
    return round(ceiling_lbm_kg * (1.0 - math.exp(-k * months)), 2)


def logistic_annual_gain(
    ceiling_lbm_kg: float,
    current_lbm_kg: float,
    training_status: str = "natural",
) -> float:
    """Return the year-1 LBM gain from current LBM toward the ceiling.

    Uses the "remaining potential" formulation:
        gain = (ceiling − current) × (1 − e^(−k × 12))
    This is the forward-looking year-1 gain irrespective of historical
    training age (accumulation is implicit in `current_lbm_kg`).
    """
    import math
    k = K_MONTHLY_ENHANCED if training_status == "enhanced" else K_MONTHLY_NATURAL
    remaining = max(0.0, ceiling_lbm_kg - current_lbm_kg)
    return round(remaining * (1.0 - math.exp(-k * 12.0)), 2)
