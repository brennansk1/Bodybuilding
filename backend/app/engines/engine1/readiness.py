from __future__ import annotations

"""
Perpetual Progression Mode — Readiness Engine

Evaluates the athlete's current physique against a target competitive tier
using concrete, measurable thresholds. Signals whether they are ``stage_ready``,
``approaching``, ``developing``, or ``not_ready``. Also projects the number
of 14-week improvement cycles needed to reach the tier.

Design: Perpetual Progression Mode feature doc §5.1 / §6.2.

Inputs are aggregated from the other engines:
- weight_cap_pct           → profile.body_weight_kg / weight_caps.lookup_weight_cap
- normalized_ffmi          → compute_normalized_ffmi(lbm_kg, height_cm)
- shoulder_waist_ratio     → tape shoulders / tape waist
- chest_waist_ratio        → aesthetic_vector.compute_chest_waist_ratio
- arm_calf_neck_max_diff   → aesthetic_vector.compute_arm_calf_neck_parity
- hqi_score                → engine1.hqi.compute_overall_hqi
- training_years           → profile.training_experience_years
"""

from app.constants.competitive_tiers import (
    CompetitiveTier,
    ReadinessState,
    TierThresholds,
    coerce_tier,
    get_tier_thresholds,
)
from app.constants.physio import (
    stage_bf_pct as stage_bf_pct_for_sex,
    fallback_offseason_bf_pct,
    project_lean_girth,
    HQI_FRESHNESS_DAYS,
)


# ---------------------------------------------------------------------------
# FFMI helper (Kouri normalized FFMI)
# ---------------------------------------------------------------------------
def compute_normalized_ffmi(lbm_kg: float, height_cm: float) -> float:
    """Return the Kouri normalized FFMI (scaled to 1.8 m reference height)."""
    if height_cm is None or height_cm <= 0:
        return 0.0
    height_m = float(height_cm) / 100.0
    raw = float(lbm_kg) / (height_m ** 2)
    return round(raw + 6.1 * (1.8 - height_m), 2)


# ---------------------------------------------------------------------------
# Readiness evaluation
# ---------------------------------------------------------------------------
def _parity_progress(current: float, target: float) -> float:
    """Inverted progress score — lower is better for the parity metric."""
    if target <= 0:
        return 1.0 if current == 0 else max(0.0, 1.0 - current / 2.0)
    # Within target: full progress. Beyond target: decay toward 0 over 2"
    if current <= target:
        return 1.0
    return max(0.0, 1.0 - (current - target) / 2.0)


def evaluate_readiness(
    athlete_metrics: dict,
    target_tier,
    weight_cap_kg: float,
    training_status: str = "natural",
    division: str = "classic_physique",
    sex: str = "male",
) -> dict:
    """Compare athlete metrics to tier thresholds and classify readiness.

    Parameters
    ----------
    athlete_metrics : dict
        Keys expected:
          - ``body_weight_kg`` (float)
          - ``normalized_ffmi`` (float, optional — 0 = unknown)
          - ``shoulder_waist_ratio`` (float)
          - ``chest_waist_ratio`` (float)
          - ``arm_calf_neck_max_diff_inches`` (float — max - min across arm/calf/neck)
          - ``hqi_score`` (float)
          - ``training_years`` (float)
    target_tier : CompetitiveTier | int | str
        The tier the athlete is training toward.
    weight_cap_kg : float
        Division weight cap at the athlete's height.
    training_status : "natural" | "enhanced"
    division : str

    Returns
    -------
    dict
        state (ReadinessState), metrics_met, metrics_total, pct_met, per_metric,
        limiting_factor, limiting_detail.
    """
    tier = coerce_tier(target_tier)
    thresholds: TierThresholds = get_tier_thresholds(division, tier)

    results: dict[str, dict] = {}
    met_count = 0

    def _record(name: str, current: float, target: float, met: bool, pct_progress: float, **extra):
        nonlocal met_count
        entry = {
            "current": round(float(current), 3),
            "target": round(float(target), 3),
            "met": bool(met),
            "pct_progress": round(max(0.0, min(1.0, float(pct_progress))), 3),
        }
        entry.update(extra)
        results[name] = entry
        if met:
            met_count += 1

    # ── Weight % of cap — STAGE-projected, not raw ──
    # The readiness question is "if you cut to stage conditioning today, would
    # your weight land at the tier target?". That's driven by your current
    # lean mass, not your current total weight. Projecting LBM up to 5% BF
    # avoids the false-positive where someone heavy-and-soft reports 0.89 of
    # cap but is actually nowhere near contest weight.
    body_weight_kg = float(athlete_metrics.get("body_weight_kg", 0.0))
    _raw_bf = athlete_metrics.get("bf_pct")
    bf_pct: float | None = float(_raw_bf) if _raw_bf not in (None, 0, 0.0) else None
    # Pull stage and fallback BF from the centralized physio module so every
    # engine sees the same numbers.
    stage_bf = stage_bf_pct_for_sex(sex)
    bf_for_proj = bf_pct if bf_pct is not None and bf_pct > 0 else fallback_offseason_bf_pct(sex)
    lbm_kg = body_weight_kg * (1.0 - bf_for_proj / 100.0)
    projected_stage_kg = lbm_kg / (1.0 - stage_bf / 100.0) if lbm_kg > 0 else 0.0
    stage_weight_pct = projected_stage_kg / weight_cap_kg if weight_cap_kg > 0 else 0.0

    _record(
        "weight_cap_pct",
        current=stage_weight_pct,
        target=thresholds.weight_cap_pct_min,
        met=stage_weight_pct >= thresholds.weight_cap_pct_min,
        pct_progress=(stage_weight_pct / thresholds.weight_cap_pct_min) if thresholds.weight_cap_pct_min > 0 else 1.0,
        current_weight_kg=round(body_weight_kg, 1),
        projected_stage_kg=round(projected_stage_kg, 1),
        weight_cap_kg=round(weight_cap_kg, 1),
        bf_pct=round(bf_pct, 1) if bf_pct is not None else None,
    )

    # ── FFMI ──
    ffmi = float(athlete_metrics.get("normalized_ffmi", 0.0))
    _record(
        "ffmi",
        current=ffmi,
        target=thresholds.ffmi_min,
        met=ffmi >= thresholds.ffmi_min,
        pct_progress=(ffmi / thresholds.ffmi_min) if thresholds.ffmi_min > 0 else 1.0,
    )

    # ── Shoulder : waist ──
    sw = float(athlete_metrics.get("shoulder_waist_ratio", 0.0))
    _record(
        "shoulder_waist",
        current=sw,
        target=thresholds.shoulder_waist_min,
        met=sw >= thresholds.shoulder_waist_min,
        pct_progress=(sw / thresholds.shoulder_waist_min) if thresholds.shoulder_waist_min > 0 else 1.0,
    )

    # ── Chest : waist ──
    cw = float(athlete_metrics.get("chest_waist_ratio", 0.0))
    _record(
        "chest_waist",
        current=cw,
        target=thresholds.chest_waist_min,
        met=cw >= thresholds.chest_waist_min,
        pct_progress=(cw / thresholds.chest_waist_min) if thresholds.chest_waist_min > 0 else 1.0,
    )

    # ── Arm-calf-neck parity (inverted: lower is better) ──
    parity = float(athlete_metrics.get("arm_calf_neck_max_diff_inches", 99.0))
    _record(
        "arm_calf_neck_parity",
        current=parity,
        target=thresholds.arm_calf_neck_parity_max,
        met=parity <= thresholds.arm_calf_neck_parity_max,
        pct_progress=_parity_progress(parity, thresholds.arm_calf_neck_parity_max),
    )

    # ── HQI — with a staleness guard so an old diagnostic doesn't silently
    #          satisfy the threshold. See physio.HQI_FRESHNESS_DAYS. ──
    hqi = float(athlete_metrics.get("hqi_score", 0.0))
    hqi_age_days = athlete_metrics.get("hqi_age_days")
    hqi_stale = hqi_age_days is not None and hqi_age_days > HQI_FRESHNESS_DAYS
    hqi_effective = 0.0 if hqi_stale else hqi
    _record(
        "hqi",
        current=hqi_effective,
        target=thresholds.hqi_min,
        met=hqi_effective >= thresholds.hqi_min,
        pct_progress=(hqi_effective / thresholds.hqi_min) if thresholds.hqi_min > 0 else 1.0,
        raw=hqi,
        stale=bool(hqi_stale),
        age_days=hqi_age_days,
    )

    # ── Training years (soft gate) ──
    years = float(athlete_metrics.get("training_years", 0.0))
    yr_req = (
        thresholds.training_years_natural if training_status == "natural"
        else thresholds.training_years_enhanced
    )
    _record(
        "training_years",
        current=years,
        target=yr_req,
        met=years >= yr_req,
        pct_progress=(years / yr_req) if yr_req > 0 else 1.0,
    )

    # ── Mass distribution — the top 3 lagging muscles by HQI lean gap.
    #
    # The seven threshold metrics above evaluate *shape* (proportions,
    # weight cap %) but don't surface a per-muscle verdict. A user at 22%
    # BF whose raw thigh measures 63 cm might pass the ratio check even
    # though their lean thigh is 13 cm short of Classic ideal. This extra
    # block reads HQI's per-site gap map (if present) and computes a
    # "lean-projection gap" against the Casey-Butt × ceiling ideal, so
    # the worst three lagging muscles surface at the tier-readiness level
    # instead of being buried in the Muscle Gaps widget.
    hqi_site_gaps: dict[str, dict] = athlete_metrics.get("hqi_site_gaps") or {}
    mass_gaps: list[dict] = []
    for site, row in hqi_site_gaps.items():
        if not isinstance(row, dict):
            continue
        ideal = row.get("ideal_lean_cm")
        current = row.get("current_lean_cm")
        gap = row.get("gap_cm")
        # Only interested in "add_muscle" sites — ignore waist/hips where
        # gap_cm negative means fat to lose, not muscle to add.
        gap_type = row.get("gap_type", "")
        if gap_type != "add_muscle":
            continue
        if gap is None or ideal is None:
            continue
        mass_gaps.append({
            "site": site,
            "current_lean_cm": round(float(current or 0), 1),
            "ideal_lean_cm": round(float(ideal), 1),
            "gap_cm": round(float(gap), 1),
            "pct_of_ideal": round((float(current or 0) / float(ideal)) * 100, 1) if ideal else 0,
        })
    mass_gaps.sort(key=lambda r: r["gap_cm"], reverse=True)
    top_mass_gaps = mass_gaps[:3]
    # Headline "mass distribution" verdict: fail if any top-3 site is <85%
    # of ideal. Acts as the 8th readiness metric.
    worst_pct = min((m["pct_of_ideal"] for m in top_mass_gaps), default=100.0) / 100.0
    if top_mass_gaps:
        _record(
            "mass_distribution",
            current=round(worst_pct, 3),
            target=0.85,
            met=worst_pct >= 0.85,
            pct_progress=worst_pct / 0.85 if worst_pct < 0.85 else 1.0,
            worst_sites=top_mass_gaps,
        )

    total_count = len(results)
    pct_met = met_count / total_count if total_count else 0.0

    if pct_met >= 1.0:
        state = ReadinessState.STAGE_READY
    elif pct_met >= 0.85:
        state = ReadinessState.APPROACHING
    elif pct_met >= 0.60:
        state = ReadinessState.DEVELOPING
    else:
        state = ReadinessState.NOT_READY

    limiting_name, limiting_detail = min(results.items(), key=lambda x: x[1]["pct_progress"])

    return {
        "state": state.value,
        "tier": tier.name,
        "tier_value": tier.value,
        "metrics_met": met_count,
        "metrics_total": total_count,
        "pct_met": round(pct_met, 3),
        "per_metric": results,
        "limiting_factor": limiting_name,
        "limiting_detail": limiting_detail,
        "mass_gaps": top_mass_gaps,   # convenience top-level copy for UI
    }


# ---------------------------------------------------------------------------
# Cycle projection — estimated 14-week improvement cycles to reach tier
# ---------------------------------------------------------------------------
def _annual_lbm_gain_kg(training_years: float, training_status: str) -> float:
    """Lyle McDonald / Aragon natural gain model (kg/yr), with enhancement bump."""
    if training_status == "enhanced":
        rate = 16.0 * (0.6 ** max(0.0, training_years - 1))
        return max(1.0, rate)
    rate = 11.0 * (0.5 ** max(0.0, training_years - 1))
    return max(0.5, rate)


def estimate_cycles_to_tier(
    current_metrics: dict,
    target_tier,
    training_years: float,
    training_status: str,
    weight_cap_kg: float,
    division: str = "classic_physique",
) -> dict:
    """Project how many 14-week improvement cycles are needed to hit tier.

    Mass gap is modeled with compounding diminishing returns (5% decay/cycle).
    Proportion metrics are correctable in 2–4 cycles of specialization.
    """
    tier = coerce_tier(target_tier)
    thresholds = get_tier_thresholds(division, tier)

    annual_lbm = _annual_lbm_gain_kg(training_years, training_status)
    per_cycle_lbm = annual_lbm * (14.0 / 52.0)

    target_weight = thresholds.weight_cap_pct_min * weight_cap_kg
    weight_gap = target_weight - float(current_metrics.get("body_weight_kg", 0.0))
    lbm_gap = max(0.0, weight_gap * 0.7)  # assume 70% of needed weight is LBM

    mass_cycles = 0
    if lbm_gap > 0:
        cycles = 0
        accumulated = 0.0
        rate = per_cycle_lbm
        while accumulated < lbm_gap and cycles < 50:
            accumulated += rate
            rate *= 0.95
            cycles += 1
        mass_cycles = cycles

    # Proportion metrics — 2-4 cycles of specialization.
    proportion_cycles = 0
    for metric_name in ("shoulder_waist", "chest_waist", "arm_calf_neck_parity"):
        if current_metrics.get(f"{metric_name}_met", True) is False:
            proportion_cycles = max(proportion_cycles, 3)

    total_cycles = max(mass_cycles, proportion_cycles)

    return {
        "estimated_cycles": total_cycles,
        "estimated_months": round(total_cycles * 3.5, 1),
        "estimated_years": round(total_cycles * 3.5 / 12.0, 1),
        "limiting_dimension": "mass" if mass_cycles >= proportion_cycles else "proportions",
        "mass_cycles_needed": mass_cycles,
        "proportion_cycles_needed": proportion_cycles,
        "annual_lbm_projection_kg": round(annual_lbm, 2),
        "per_cycle_lbm_kg": round(per_cycle_lbm, 2),
    }
