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

    # ── Illusion (X-frame) — v2 Sprint 9
    # Quantifies the stage "hourglass" that judges reward independently of
    # raw shoulder:waist. xframe = (shoulders × hips) / waist². Tiered
    # thresholds: T1 2.15 → T5 2.55 (Classic Physique).
    xframe = float(athlete_metrics.get("illusion_xframe", 0.0))
    if thresholds.illusion_xframe_min > 0:
        _record(
            "illusion_score",
            current=xframe,
            target=thresholds.illusion_xframe_min,
            met=xframe >= thresholds.illusion_xframe_min,
            pct_progress=(xframe / thresholds.illusion_xframe_min) if thresholds.illusion_xframe_min > 0 else 1.0,
        )

    # ── Conditioning pct — v2 Sprint 9
    # "How close to stage conditioning" independently of mass. Zero = at
    # division offseason ceiling; one = at division stage target.
    # conditioning_pct = (offseason_BF − current_BF) / (offseason_BF − stage_BF)
    from app.constants.physio import (
        offseason_bf_ceiling_for_division,
        stage_bf_pct_for_division,
    )
    offseason_ceiling = offseason_bf_ceiling_for_division(division)
    stage_target = stage_bf_pct_for_division(division)
    if bf_pct is not None and offseason_ceiling > stage_target:
        cond_pct = (offseason_ceiling - bf_pct) / (offseason_ceiling - stage_target)
        cond_pct = max(0.0, min(1.1, cond_pct))  # allow slight over-lean
    else:
        cond_pct = 0.0
    if thresholds.conditioning_pct_min > 0:
        _record(
            "conditioning_pct",
            current=cond_pct,
            target=thresholds.conditioning_pct_min,
            met=cond_pct >= thresholds.conditioning_pct_min,
            pct_progress=(cond_pct / thresholds.conditioning_pct_min) if thresholds.conditioning_pct_min > 0 else 1.0,
            bf_pct=round(bf_pct, 1) if bf_pct is not None else None,
            offseason_ceiling_pct=offseason_ceiling,
            stage_target_pct=stage_target,
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
    # Headline "mass distribution" verdict — v2 Sprint 3:
    # use a soft-min (p=6 power-mean) instead of hard-min so the score
    # degrades smoothly when multiple sites cluster near the bottom,
    # avoiding jump discontinuities as worst-site ordering changes.
    # Behaves like hard-min when one site is clearly worst.
    if top_mass_gaps:
        _pcts = [m["pct_of_ideal"] for m in top_mass_gaps if m["pct_of_ideal"] > 0]
        if _pcts:
            _p = 6.0
            _soft_min = (sum(p ** (-_p) for p in _pcts) / len(_pcts)) ** (-1.0 / _p)
            worst_pct = _soft_min / 100.0
        else:
            worst_pct = 0.0
    else:
        worst_pct = 1.0
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
# v2 Sprint 4 replaces the exponential-halving gain curve
# (`11 × 0.5^(years−1)`) with a logistic `LBM(t) = ceiling × (1 − e^(−k·t))`
# aligned with McDonald / Aragon / Helms. The old 5%/cycle diminishing
# term is removed — the logistic already captures diminishing returns
# physiologically, and the per-cycle tax was double-counting.
#
# Sources: engine1.training_age for the curve; v2 doc §9.
from app.engines.engine1.training_age import (
    logistic_annual_gain,
    effective_training_years,
)


def estimate_cycles_to_tier(
    current_metrics: dict,
    target_tier,
    training_years: float,
    training_status: str,
    weight_cap_kg: float,
    division: str = "classic_physique",
    ceiling_lbm_kg: float | None = None,
    surplus_pct_per_week: float | None = None,
    training_consistency: float | None = None,
    training_intensity: float | None = None,
    training_programming: float | None = None,
) -> dict:
    """Project how many 14-week improvement cycles are needed to hit tier.

    v2 Sprint 4 — logistic gain curve with training-age correction:
      * `LBM(t) = ceiling × (1 − e^(−k × t_effective))` per training_age.py
      * Effective training years apply consistency × intensity × programming
        discount (defaulted when the user hasn't supplied inputs).
      * `muscle_fraction`: `0.85 − 0.015 × surplus_pct_per_week` (default 0.70).
      * `proportion_cycles` scales with deficit magnitude, not fixed 3.
    """
    tier = coerce_tier(target_tier)
    thresholds = get_tier_thresholds(division, tier)

    # Effective training age — factors default to conservative priors.
    t_eff = effective_training_years(
        chronological_years=training_years,
        consistency=training_consistency,
        intensity=training_intensity,
        programming=training_programming,
    )

    # LBM ceiling — use passed-in estimate from ceiling_ensemble if available,
    # otherwise fall back to the IFBB class cap × (1 − stage_bf).
    body_weight_kg = float(current_metrics.get("body_weight_kg", 0.0))
    _raw_bf = current_metrics.get("bf_pct")
    bf_for_lbm = float(_raw_bf) if _raw_bf not in (None, 0, 0.0) else 15.0
    current_lbm_kg = body_weight_kg * (1.0 - bf_for_lbm / 100.0)
    if ceiling_lbm_kg is None:
        ceiling_lbm_kg = weight_cap_kg * 0.95  # 5% stage BF implied

    annual_lbm = logistic_annual_gain(
        ceiling_lbm_kg=ceiling_lbm_kg,
        current_lbm_kg=current_lbm_kg,
        training_status=training_status,
    )
    per_cycle_lbm = round(annual_lbm * (14.0 / 52.0), 2)

    # Muscle fraction — how much of the scale-weight gain is actually LBM.
    # Garthe 2011 / Helms 2014: 0.5–0.8 depending on surplus size.
    muscle_fraction = 0.70
    if surplus_pct_per_week is not None:
        muscle_fraction = max(0.50, min(0.85, 0.85 - 0.015 * surplus_pct_per_week))

    # V3 fix: target_weight is a STAGE weight (athlete at 5% BF), but
    # body_weight_kg is the athlete's CURRENT (offseason) weight. Comparing
    # raw BW to target stage BW produced the "0 years HIGH" trap for any
    # user already over the weight-cap-pct floor at high BF. Instead compare
    # LBM-to-LBM: the target LBM at stage weight vs. current LBM.
    #
    # Example (brennan, T2): target_weight = 91.5 kg; target_lbm_at_stage =
    # 86.9 kg; current_lbm = 72.3 kg; lbm_gap = 14.6 kg. Previously the
    # engine emitted lbm_gap = 0 because 93.5 kg > 91.5 kg.
    target_weight = thresholds.weight_cap_pct_min * weight_cap_kg
    stage_bf_fraction = 0.05  # implied stage BF used to derive the cap
    target_lbm_at_stage = target_weight * (1.0 - stage_bf_fraction)
    lbm_gap = max(0.0, target_lbm_at_stage - current_lbm_kg)
    # Keep muscle_fraction unused in this branch — we're comparing LBM→LBM
    # so there's no surplus-to-LBM discount to apply.
    _ = muscle_fraction
    weight_gap = target_weight - body_weight_kg  # retained for diagnostic payload

    # Mass cycles: walk the logistic curve forward until we've closed the gap.
    # No per-cycle 5% tax — the curve already slows as current approaches ceiling.
    mass_cycles = 0
    if lbm_gap > 0 and per_cycle_lbm > 0:
        import math
        # Closed-form: t_needed_years = −ln(1 − lbm_gap/remaining) / (k × 12)
        from app.engines.engine1.training_age import (
            K_MONTHLY_NATURAL, K_MONTHLY_ENHANCED,
        )
        k = K_MONTHLY_ENHANCED if training_status == "enhanced" else K_MONTHLY_NATURAL
        remaining = max(0.01, ceiling_lbm_kg - current_lbm_kg)
        frac = min(0.99, lbm_gap / remaining)
        t_years = -math.log(1.0 - frac) / (k * 12.0)
        mass_cycles = max(0, int(math.ceil(t_years * 52.0 / 14.0)))

    # Proportion metrics — cycles scale with deficit magnitude
    # (v2 doc §9(d)). Each 5% ratio deficit costs one specialization cycle.
    proportion_cycles = 0
    for metric_name in ("shoulder_waist", "chest_waist"):
        m = current_metrics.get(f"{metric_name}_met")
        deficit = current_metrics.get(f"{metric_name}_deficit_pct", 0.0)
        if m is False or (deficit and deficit > 0):
            cycles_for_metric = max(1, int(round(float(deficit) / 0.05))) if deficit else 2
            proportion_cycles = max(proportion_cycles, cycles_for_metric)
    if current_metrics.get("arm_calf_neck_parity_met") is False:
        proportion_cycles = max(proportion_cycles, 2)

    total_cycles = max(mass_cycles, proportion_cycles)

    return {
        "estimated_cycles": total_cycles,
        "estimated_months": round(total_cycles * 3.5, 1),
        "estimated_years": round(total_cycles * 3.5 / 12.0, 1),
        "limiting_dimension": "mass" if mass_cycles >= proportion_cycles else "proportions",
        "mass_cycles_needed": mass_cycles,
        "proportion_cycles_needed": proportion_cycles,
        "annual_lbm_projection_kg": round(annual_lbm, 2),
        "per_cycle_lbm_kg": per_cycle_lbm,
        "t_effective_years": t_eff,
        "muscle_fraction_used": muscle_fraction,
        "ceiling_lbm_kg_used": round(ceiling_lbm_kg, 1),
    }


# ---------------------------------------------------------------------------
# V3 — Achieved-tier classification
# ---------------------------------------------------------------------------
def compute_achieved_tier(
    athlete_metrics: dict,
    weight_cap_kg: float,
    division: str = "classic_physique",
    training_status: str = "natural",
    threshold_pct: float = 0.90,
) -> int | None:
    """Return the highest tier for which the athlete meets ≥ ``threshold_pct``
    of gates. Distinct from target_tier — this is what the athlete has
    *demonstrated*, used to render "current tier" badges in the UI.

    Iterates T5 → T1, returns the first tier that passes the threshold.
    Returns None if no tier is met (pre-T1 athlete).
    """
    for tier in (CompetitiveTier.OLYMPIA, CompetitiveTier.PRO_QUALIFIER,
                 CompetitiveTier.NATIONAL_NPC, CompetitiveTier.REGIONAL_NPC,
                 CompetitiveTier.LOCAL_NPC):
        try:
            result = evaluate_readiness(
                athlete_metrics=athlete_metrics,
                target_tier=tier,
                weight_cap_kg=weight_cap_kg,
                division=division,
                training_status=training_status,
            )
        except Exception:
            continue
        if result.get("pct_met", 0.0) >= threshold_pct:
            return tier.value
    return None


# ---------------------------------------------------------------------------
# V3 — Tier-timing projection across adherence scenarios
# ---------------------------------------------------------------------------
def project_tier_timing_across_adherence(
    current_metrics: dict,
    target_tier,
    training_years: float,
    training_status: str,
    weight_cap_kg: float,
    division: str = "classic_physique",
    ceiling_lbm_kg: float | None = None,
) -> dict:
    """Return tier-timing estimates for HIGH / MED / LOW adherence profiles.

    Adherence scales the consistency × intensity × programming product in the
    training-age effective-years calculation. Profiles:
        HIGH:  0.95 × 0.90 × 0.85 = 0.727
        MED:   0.80 × 0.75 × 0.70 = 0.420
        LOW:   0.60 × 0.55 × 0.50 = 0.165
    """
    from app.constants.competitive_tiers import CompetitiveTier as _CT
    if isinstance(target_tier, int):
        tier_enum = _CT(target_tier)
    else:
        tier_enum = target_tier

    profiles = {
        "high": (0.95, 0.90, 0.85),
        "medium": (0.80, 0.75, 0.70),
        "low": (0.60, 0.55, 0.50),
    }
    out: dict[str, dict] = {}
    for key, (c, i, p) in profiles.items():
        est = estimate_cycles_to_tier(
            current_metrics=current_metrics,
            target_tier=tier_enum,
            training_years=training_years,
            training_status=training_status,
            weight_cap_kg=weight_cap_kg,
            division=division,
            ceiling_lbm_kg=ceiling_lbm_kg,
            training_consistency=c,
            training_intensity=i,
            training_programming=p,
        )
        out[key] = {
            "years": est.get("estimated_years"),
            "cycles": est.get("estimated_cycles"),
            "limiting_dimension": est.get("limiting_dimension"),
            "adherence_product": round(c * i * p, 3),
        }
    return out
