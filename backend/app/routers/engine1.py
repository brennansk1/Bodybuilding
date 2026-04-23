import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

logger = logging.getLogger(__name__)
from app.dependencies import get_current_user
from app.models.user import User
from app.services.diagnostic import run_full_diagnostic, get_pds_history, get_lcsa_history

router = APIRouter(prefix="/engine1", tags=["engine1-diagnostic"])


@router.post("/run")
async def run_diagnostic(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await run_full_diagnostic(db, user)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/pds")
async def get_pds(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    history = await get_pds_history(db, user.id)
    if not history:
        raise HTTPException(status_code=404, detail="No PDS data found. Run diagnostics first.")
    return {"current": history[-1], "history": history}


@router.get("/pds/trajectory")
async def get_trajectory(
    weeks: int = 52,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.models.profile import UserProfile
    from app.models.diagnostic import PDSLog
    from app.engines.engine1.trajectory import predict_trajectory
    from sqlalchemy import select, desc

    result = await db.execute(
        select(PDSLog).where(PDSLog.user_id == user.id).order_by(desc(PDSLog.recorded_date), desc(PDSLog.created_at)).limit(1)
    )
    pds = result.scalar_one_or_none()
    if not pds:
        raise HTTPException(status_code=404, detail="No PDS data")

    result = await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))
    profile = result.scalar_one_or_none()

    ceiling = min(95.0, pds.pds_score + 30)
    trajectory = predict_trajectory(
        pds.pds_score, ceiling, weeks,
        profile.training_experience_years if profile else 3,
    )
    return {"current_pds": pds.pds_score, "ceiling": ceiling, "trajectory": trajectory}


@router.get("/lcsa")
async def get_lcsa(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    history = await get_lcsa_history(db, user.id)
    if not history:
        raise HTTPException(status_code=404, detail="No LCSA data")
    return {"current": history[-1], "history": history}


@router.get("/muscle-gaps")
async def get_muscle_gaps(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Return per-site muscle gap analysis — raw cm gaps from current lean size
    to the ideal. V3: gaps are scaled to the athlete's target tier
    (T1 0.87 → T5 1.03 of the absolute division ceiling) so a Tier-1 athlete
    isn't told their bicep is 9 cm short of an Olympia-level target they
    don't care about.
    """
    from app.models.diagnostic import HQILog
    from app.engines.engine1.muscle_gaps import (
        rank_sites_by_gap, compute_total_gap, compute_avg_pct_of_ideal,
        compute_site_gap, TIER_IDEAL_SCALING,
    )
    from sqlalchemy import select, desc

    result = await db.execute(
        select(HQILog).where(HQILog.user_id == user.id).order_by(desc(HQILog.recorded_date), desc(HQILog.created_at)).limit(1)
    )
    log = result.scalar_one_or_none()
    if not log:
        raise HTTPException(status_code=404, detail="No muscle gap data. Run diagnostics first.")

    from app.models.profile import UserProfile
    profile_result = await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))
    profile = profile_result.scalar_one_or_none()
    division = profile.division if profile else None
    target_tier = profile.target_tier if profile else None

    site_data = log.site_scores
    # Detect format: new format has gap_cm/pct_of_ideal keys.
    # If a target tier is set, post-process each entry to scale the ideal.
    # Waist/hips (stay-small sites) are passed through at absolute ideal.
    if site_data and isinstance(next(iter(site_data.values()), None), dict):
        if target_tier in TIER_IDEAL_SCALING:
            factor = TIER_IDEAL_SCALING[target_tier]
            rescaled: dict[str, dict] = {}
            from app.engines.engine1.muscle_gaps import _RATIO_SITES
            for site, d in site_data.items():
                ideal_abs = float(d.get("ideal_lean_cm") or 0.0)
                current  = float(d.get("current_lean_cm") or 0.0)
                if site in _RATIO_SITES or ideal_abs <= 0:
                    tier_ideal = ideal_abs
                else:
                    tier_ideal = round(ideal_abs * factor, 1)
                recomputed = compute_site_gap(current, tier_ideal, site)
                recomputed["absolute_ideal_cm"] = round(ideal_abs, 1)
                recomputed["tier_ideal_cm"] = round(tier_ideal, 1)
                recomputed["target_tier"] = target_tier
                rescaled[site] = recomputed
            site_data = rescaled

        ranked = rank_sites_by_gap(site_data, division=division)
        total_gap = compute_total_gap(site_data)
        avg_pct = compute_avg_pct_of_ideal(site_data, division=division)
    else:
        ranked = []
        total_gap = 0.0
        avg_pct = log.overall_hqi

    return {
        "sites": site_data,
        "total_gap_cm": total_gap,
        "avg_pct_of_ideal": avg_pct,
        "ranked_gaps": ranked,
        "target_tier": target_tier,
    }


@router.get("/hqi")
async def get_hqi(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Legacy endpoint — redirects to muscle-gaps."""
    return await get_muscle_gaps(user=user, db=db)


@router.get("/weight-cap")
async def get_weight_cap(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.models.profile import UserProfile
    from app.constants.weight_caps import lookup_weight_cap, lookup_target_lbm
    from sqlalchemy import select

    result = await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    cap_kg = lookup_weight_cap(profile.height_cm, profile.division)
    target_lbm = lookup_target_lbm(profile.height_cm, profile.division)

    return {
        "weight_cap_kg": cap_kg,
        "target_lbm_kg": target_lbm,
        "stage_weight_kg": cap_kg,
    }


@router.get("/class-estimate")
async def get_class_estimate(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the athlete's estimated competition class based on height/weight."""
    from app.models.profile import UserProfile
    from app.models.measurement import BodyWeightLog
    from app.constants.division_classes import estimate_class
    from sqlalchemy import select

    result = await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    bw_result = await db.execute(
        select(BodyWeightLog).where(BodyWeightLog.user_id == user.id)
        .order_by(desc(BodyWeightLog.recorded_date), desc(BodyWeightLog.created_at)).limit(1)
    )
    bw = bw_result.scalar_one_or_none()

    cls = estimate_class(
        height_cm=profile.height_cm,
        division=profile.division,
        body_weight_kg=bw.weight_kg if bw else None,
    )
    return cls


@router.post("/feasibility")
async def check_feasibility(
    data: dict,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Assess whether a target PDS is achievable within a given timeframe.
    Body: { "target_pds": float, "weeks_available": int (optional) }
    """
    from app.models.diagnostic import PDSLog
    from app.models.profile import UserProfile
    from app.engines.engine1.feasibility import compute_feasibility
    from sqlalchemy import select, desc
    from datetime import date as _date

    pds_result = await db.execute(
        select(PDSLog).where(PDSLog.user_id == user.id).order_by(desc(PDSLog.recorded_date), desc(PDSLog.created_at)).limit(1)
    )
    pds = pds_result.scalar_one_or_none()

    profile_result = await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))
    profile = profile_result.scalar_one_or_none()

    current_pds = pds.pds_score if pds else 0.0
    target_pds = float(data.get("target_pds", min(100.0, current_pds + 15)))

    # Weeks from competition date or explicit override
    weeks = 52
    if profile and profile.competition_date:
        days = (profile.competition_date - _date.today()).days
        weeks = max(1, days // 7)
    if "weeks_available" in data:
        weeks = int(data["weeks_available"])

    result = compute_feasibility(
        current_pds=current_pds,
        target_pds=target_pds,
        weeks_available=weeks,
        training_experience_years=profile.training_experience_years if profile else 3,
    )
    result["current_pds"] = current_pds
    result["target_pds"] = target_pds
    result["weeks_available"] = weeks
    if profile and profile.competition_date:
        result["competition_date"] = str(profile.competition_date)
    return result


@router.get("/diagnostic")
async def get_latest_diagnostic(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Return the most recent cached diagnostic result (body_fat + prep_timeline)
    without re-running the full Engine 1 pipeline.
    """
    from app.models.profile import UserProfile
    from app.models.measurement import SkinfoldMeasurement, BodyWeightLog
    from app.models.diagnostic import PDSLog
    from sqlalchemy import select, desc
    from app.engines.engine1.body_fat import categorize_body_fat, lean_mass_kg
    from app.engines.engine1.prep_timeline import prep_phase_for_date, weeks_out, phase_description

    profile_result = await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))
    profile = profile_result.scalar_one_or_none()

    # Body fat from latest skinfold or manual override
    bf_pct = profile.manual_body_fat_pct if profile else None
    bf_source = "manual_override" if bf_pct is not None else None

    # Fetch latest skinfold anyway to build sf_data later
    sf_result = await db.execute(
        select(SkinfoldMeasurement).where(SkinfoldMeasurement.user_id == user.id)
        .order_by(desc(SkinfoldMeasurement.recorded_date), desc(SkinfoldMeasurement.created_at)).limit(1)
    )
    sf = sf_result.scalar_one_or_none()

    if bf_pct is None:
        bf_pct = sf.body_fat_pct if sf else None
        bf_source = "skinfold" if bf_pct else None

    bw_result = await db.execute(
        select(BodyWeightLog).where(BodyWeightLog.user_id == user.id)
        .order_by(desc(BodyWeightLog.recorded_date), desc(BodyWeightLog.created_at)).limit(1)
    )
    bw = bw_result.scalar_one_or_none()

    sex = profile.sex if profile else "male"

    # Fallback: estimate BF from tape via Navy circumference method
    if bf_pct is None and profile:
        from app.models.measurement import TapeMeasurement
        from app.engines.engine1.body_fat import navy_body_fat
        tape_result = await db.execute(
            select(TapeMeasurement).where(TapeMeasurement.user_id == user.id)
            .order_by(desc(TapeMeasurement.recorded_date), desc(TapeMeasurement.created_at)).limit(1)
        )
        tape = tape_result.scalar_one_or_none()
        if tape and tape.waist and tape.neck and profile.height_cm:
            try:
                bf_pct = navy_body_fat(tape.waist, tape.neck, profile.height_cm, sex, tape.hips)
                bf_source = "navy_circumference"
            except (ValueError, ZeroDivisionError) as e:
                logger.warning("Navy body fat calculation failed: %s", e)

    if bf_pct is not None:
        lm = lean_mass_kg(bw.weight_kg, bf_pct) if bw else None
        body_fat_info = {
            "body_fat_pct": bf_pct,
            "category": categorize_body_fat(bf_pct, sex),
            "lean_mass_kg": lm,
            "source": bf_source,
        }

    # Prep timeline from profile competition date
    comp_date = getattr(profile, "competition_date", None) if profile else None
    current_phase = prep_phase_for_date(comp_date)
    phase_info = phase_description(current_phase)
    weeks_remaining = weeks_out(comp_date)

    # Weight cap, ghost model, and advanced measurements
    weight_cap_info = None
    ghost_model_info = None
    advanced_info = None

    if profile and profile.height_cm:
        from app.constants.weight_caps import lookup_weight_cap, lookup_target_lbm
        from app.services.diagnostic import (
            get_latest_tape, _tape_to_dict, _average_sites,
            _lean_adjust_measurements, _build_advanced_measurements,
        )
        from app.engines.engine1.volumetric_ghost import run_ghost_pipeline

        division = profile.division or "mens_open"
        cap_kg = lookup_weight_cap(profile.height_cm, division)
        target_lbm = lookup_target_lbm(profile.height_cm, division)
        weight_cap_info = {
            "weight_cap_kg": cap_kg,
            "target_lbm_kg": target_lbm,
            "stage_weight_kg": cap_kg,
        }

        # Fetch tape measurements for ghost model + advanced metrics
        tape = await get_latest_tape(db, user.id)
        if tape:
            raw = _tape_to_dict(tape)
            averaged = _average_sites(raw)

            # Build skinfold dict from model object (if available)
            sf_data = None
            if sf:
                sf_data = {}
                for col in ("chest", "tricep", "subscapular", "abdominal",
                             "suprailiac", "thigh", "bicep", "lower_back", "calf",
                             "midaxillary"):
                    val = getattr(sf, col, None)
                    if val is not None:
                        sf_data[col] = val

            lean_meas = _lean_adjust_measurements(averaged, bf_pct or 15.0, sf_data)

            # Ghost model
            ghost_result = run_ghost_pipeline(
                height_cm=profile.height_cm,
                division=division,
                lean_measurements=lean_meas,
                sex=sex,
            )
            weight_cap_info["ghost_mass_kg"] = ghost_result["ghost_mass_kg"]
            weight_cap_info["allometric_multiplier"] = ghost_result["allometric_multiplier"]
            ghost_model_info = {
                "ghost_mass_kg": ghost_result["ghost_mass_kg"],
                "allometric_multiplier": ghost_result["allometric_multiplier"],
                "hanavan_volumes": ghost_result["hanavan_volumes"],
                "scaled_ghost": ghost_result["scaled_ghost"],
            }

            # Advanced measurements (lat activation, back width, quad VMO)
            advanced_info = _build_advanced_measurements(tape, lean_meas)

    return {
        "body_fat": body_fat_info,
        "weight_cap": weight_cap_info,
        "ghost_model": ghost_model_info,
        "advanced_measurements": advanced_info,
        "prep_timeline": {
            "current_phase": current_phase,
            "weeks_out": weeks_remaining,
            "competition_date": str(comp_date) if comp_date else None,
            "phase_info": phase_info,
        },
    }


@router.get("/aesthetic-vector")
async def get_aesthetic_vector(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.models.profile import UserProfile
    from app.services.diagnostic import get_latest_tape, _tape_to_dict, _average_sites
    from app.constants.divisions import DIVISION_VECTORS
    from app.engines.engine1.aesthetic_vector import (
        compute_proportion_vector, compute_delta_vector, compute_priority_scores,
    )
    from sqlalchemy import select

    result = await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    tape = await get_latest_tape(db, user.id)
    if not tape:
        raise HTTPException(status_code=404, detail="No measurements found")

    tape_dict = _tape_to_dict(tape)
    averaged = _average_sites(tape_dict)
    division_vector = DIVISION_VECTORS.get(profile.division, DIVISION_VECTORS["mens_open"])

    # Apply lean adjustment so the comparison is muscle vs division ideal,
    # not fat-inflated circumference vs division ideal
    from app.services.diagnostic import _lean_adjust_measurements
    from app.models.measurement import SkinfoldMeasurement
    bf_pct = profile.manual_body_fat_pct if profile else None
    if bf_pct is None:
        sf_r = await db.execute(
            select(SkinfoldMeasurement).where(SkinfoldMeasurement.user_id == user.id)
            .order_by(desc(SkinfoldMeasurement.recorded_date), desc(SkinfoldMeasurement.created_at)).limit(1)
        )
        sf = sf_r.scalar_one_or_none()
        bf_pct = sf.body_fat_pct if sf else None
        if bf_pct is None and tape.waist and tape.neck and profile.height_cm:
            try:
                bf_pct = navy_body_fat(tape.waist, tape.neck, profile.height_cm, profile.sex, tape.hips)
            except (ValueError, ZeroDivisionError) as e:
                logger.warning("Navy body fat fallback failed: %s", e)
    lean_averaged = _lean_adjust_measurements(averaged, bf_pct or 15.0)

    actual = compute_proportion_vector(lean_averaged, profile.height_cm)
    delta = compute_delta_vector(actual, division_vector)
    priority_scores = compute_priority_scores(delta, division=profile.division)

    # Return priorities as sorted list of site names (highest priority first)
    sorted_priorities = [
        site for site, _ in sorted(priority_scores.items(), key=lambda x: -x[1])
    ]

    return {
        "actual": actual,
        "ideal": division_vector,
        "delta": delta,
        "priorities": sorted_priorities,
        "priority_scores": priority_scores,
        "body_fat_pct": bf_pct,
    }


@router.get("/annual-calendar")
async def get_annual_calendar(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the annual phase calendar working backwards from competition date."""
    from app.models.profile import UserProfile
    from app.engines.engine1.prep_timeline import generate_annual_calendar, prep_phase_for_date, weeks_out, phase_description, compute_smart_phase_plan
    from app.models.measurement import BodyWeightLog, SkinfoldMeasurement

    result = await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    comp_date = getattr(profile, "competition_date", None)

    # Fetch latest body composition for smart calendar
    bf_pct = getattr(profile, "manual_body_fat_pct", None)
    if bf_pct is None:
        sf_result = await db.execute(
            select(SkinfoldMeasurement).where(SkinfoldMeasurement.user_id == user.id)
            .order_by(desc(SkinfoldMeasurement.recorded_date)).limit(1)
        )
        sf = sf_result.scalar_one_or_none()
        if sf:
            bf_pct = sf.body_fat_pct

    bw_result = await db.execute(
        select(BodyWeightLog).where(BodyWeightLog.user_id == user.id)
        .order_by(desc(BodyWeightLog.recorded_date)).limit(1)
    )
    bw = bw_result.scalar_one_or_none()
    weight_kg = bw.weight_kg if bw else None

    division = (profile.preferences or {}).get("division", "classic_physique")

    calendar = generate_annual_calendar(
        comp_date,
        current_bf_pct=bf_pct,
        current_weight_kg=weight_kg,
        sex=profile.sex,
        division=division,
    ) if comp_date else []

    current_phase = prep_phase_for_date(comp_date)

    response: dict = {
        "competition_date": str(comp_date) if comp_date else None,
        "current_phase": current_phase,
        "weeks_out": weeks_out(comp_date),
        "calendar": calendar,
    }

    # Include smart prep plan if we have body composition data
    if comp_date and bf_pct is not None and weight_kg is not None:
        wo = weeks_out(comp_date)
        if wo is not None and wo > 0:
            plan = compute_smart_phase_plan(
                competition_date=comp_date,
                current_bf_pct=bf_pct,
                current_weight_kg=weight_kg,
                sex=profile.sex,
                division=division,
            )
            response["prep_plan"] = plan

    return response


@router.get("/symmetry")
async def get_symmetry(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return bilateral symmetry analysis with per-pair breakdown."""
    from app.services.diagnostic import get_latest_tape, _tape_to_dict
    from app.engines.engine1.pds import compute_symmetry_score, compute_symmetry_details

    tape = await get_latest_tape(db, user.id)
    if not tape:
        raise HTTPException(status_code=404, detail="No measurements found")

    tape_dict = _tape_to_dict(tape)
    score = compute_symmetry_score(tape_dict)
    details = compute_symmetry_details(tape_dict)

    return {
        "symmetry_score": score,
        "details": details,
        "lagging_sides": [
            d for d in details if d["deviation_pct"] > 2.0
        ],
    }


@router.get("/phase-recommendation")
async def get_phase_recommendation(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return phase recommendation based on current physique state (cross-engine E1→E3)."""
    from app.models.profile import UserProfile
    from app.models.diagnostic import HQILog, PDSLog
    from app.engines.engine1.muscle_gaps import compute_avg_pct_of_ideal

    result = await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    hqi_result = await db.execute(
        select(HQILog).where(HQILog.user_id == user.id).order_by(desc(HQILog.recorded_date), desc(HQILog.created_at)).limit(1)
    )
    hqi_log = hqi_result.scalar_one_or_none()

    pds_result = await db.execute(
        select(PDSLog).where(PDSLog.user_id == user.id).order_by(desc(PDSLog.recorded_date), desc(PDSLog.created_at)).limit(1)
    )
    pds_log = pds_result.scalar_one_or_none()

    bf_pct = profile.manual_body_fat_pct if profile else None
    if bf_pct is None:
        from app.models.measurement import SkinfoldMeasurement
        sf_result = await db.execute(
            select(SkinfoldMeasurement).where(SkinfoldMeasurement.user_id == user.id)
            .order_by(desc(SkinfoldMeasurement.recorded_date), desc(SkinfoldMeasurement.created_at)).limit(1)
        )
        sf = sf_result.scalar_one_or_none()
        bf_pct = sf.body_fat_pct if sf else None

    from app.services.diagnostic import _recommend_phase
    muscle_gaps = hqi_log.site_scores if hqi_log else {}
    pds_score = pds_log.pds_score if pds_log else 50.0

    # Get actual body weight for accurate cut duration projections
    from app.models.measurement import BodyWeightLog
    bw_result = await db.execute(
        select(BodyWeightLog).where(BodyWeightLog.user_id == user.id)
        .order_by(desc(BodyWeightLog.recorded_date)).limit(1)
    )
    bw = bw_result.scalar_one_or_none()
    weight_kg = bw.weight_kg if bw else 85.0

    return _recommend_phase(muscle_gaps, pds_score, bf_pct, profile.sex, profile.preferences, competition_date=profile.competition_date, body_weight_kg=weight_kg)
