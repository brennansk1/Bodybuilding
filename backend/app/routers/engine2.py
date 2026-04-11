from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from datetime import date, timedelta

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.profile import UserProfile
from app.models.measurement import BodyWeightLog
from app.models.training import (
    TrainingProgram, TrainingSession, TrainingSet,
    HRVLog, ARILog, Exercise, StrengthLog,
)
from app.models.diagnostic import HQILog
from app.services.training import generate_program_sessions, DEFAULT_VOLUME

router = APIRouter(prefix="/engine2", tags=["engine2-training"])

VALID_SPLITS = ("ppl", "upper_lower", "full_body", "bro_split")


# ---------------------------------------------------------------------------
# ARI
# ---------------------------------------------------------------------------

@router.get("/ari")
async def get_ari(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.engines.engine2.ari import get_ari_zone, get_zone_recommendation

    result = await db.execute(
        select(ARILog).where(ARILog.user_id == user.id)
        .order_by(desc(ARILog.recorded_date), desc(ARILog.created_at)).limit(1)
    )
    ari = result.scalar_one_or_none()
    if ari:
        return {
            "ari_score": ari.ari_score,
            "zone": get_ari_zone(ari.ari_score),
            "components": {
                "hrv": ari.hrv_component,
                "sleep": ari.sleep_component,
                "soreness": ari.soreness_component,
                "hr": getattr(ari, "hr_component", None),
                "wellness": getattr(ari, "stress_component", None),
            },
            "recommendation": get_zone_recommendation(ari.ari_score),
        }

    # Fall back to computing from latest HRV (no persisted ARILog yet).
    hrv_result = await db.execute(
        select(HRVLog).where(HRVLog.user_id == user.id)
        .order_by(desc(HRVLog.recorded_date), desc(HRVLog.created_at)).limit(1)
    )
    hrv = hrv_result.scalar_one_or_none()
    if not hrv:
        raise HTTPException(status_code=404, detail="No HRV data available")

    # 7-day rolling baseline (HRV research standard)
    baseline_result = await db.execute(
        select(HRVLog).where(HRVLog.user_id == user.id)
        .order_by(desc(HRVLog.recorded_date), desc(HRVLog.created_at)).limit(7)
    )
    hrv_history = baseline_result.scalars().all()
    baseline_rmssd = sum(h.rmssd for h in hrv_history) / len(hrv_history)
    hr_history = [h.resting_hr for h in hrv_history if h.resting_hr is not None]
    baseline_hr = sum(hr_history) / len(hr_history) if hr_history else None

    from app.engines.engine2.ari import compute_ari_breakdown
    breakdown = compute_ari_breakdown(
        rmssd=hrv.rmssd,
        resting_hr=hrv.resting_hr,
        sleep_quality_1_10=hrv.sleep_quality,
        soreness_1_10=getattr(hrv, "soreness_score", None) or 5.0,
        baseline_rmssd=baseline_rmssd,
        baseline_hr=baseline_hr,
        sleep_hours=getattr(hrv, "sleep_hours", None),
        stress_1_10=getattr(hrv, "stress_score", None),
        mood_1_10=getattr(hrv, "mood_score", None),
        energy_1_10=getattr(hrv, "energy_score", None),
    )
    return {
        "ari_score": breakdown["score"],
        "zone": breakdown["zone"],
        "components": {
            "hrv": breakdown["hrv"],
            "sleep": breakdown["sleep"],
            "soreness": breakdown["soreness"],
            "hr": breakdown["hr"],
            "wellness": breakdown["wellness"],
        },
        "recommendation": get_zone_recommendation(breakdown["score"]),
    }


# ---------------------------------------------------------------------------
# Volume allocation
# ---------------------------------------------------------------------------

@router.get("/volume-allocation")
async def get_volume_allocation(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Compute gap-driven weekly volume allocation per muscle group.
    Primary driver: HQI gap_cm (how many cm of lean circumference to add).
    Bigger gap → more volume (closer to MRV). Smaller gap → maintenance (closer to MEV).
    """
    profile_result = await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))
    profile = profile_result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    # Load latest HQI data (nested format: {site: {score, gap_cm, ...}})
    hqi_result = await db.execute(
        select(HQILog).where(HQILog.user_id == user.id)
        .order_by(desc(HQILog.recorded_date), desc(HQILog.created_at)).limit(1)
    )
    hqi_log = hqi_result.scalar_one_or_none()

    if not hqi_log or not hqi_log.site_scores:
        return {"volume_allocation": DEFAULT_VOLUME, "muscle_gaps": {}}

    # Extract gap_cm from nested HQI data
    hqi_gaps: dict[str, float] = {}
    for site, data in hqi_log.site_scores.items():
        if isinstance(data, dict):
            hqi_gaps[site.lower()] = max(0.0, data.get("gap_cm", 0.0))
        else:
            hqi_gaps[site.lower()] = 0.0

    # Map tape sites → training muscles, with defaults for unmeasured muscles
    site_to_muscles = {
        "shoulders": ["shoulders"], "chest": ["chest"],
        "bicep": ["biceps"], "forearm": ["forearms"],
        "neck": ["traps"], "thigh": ["quads", "hamstrings"],
        "calf": ["calves"], "hips": ["glutes"],
    }
    # Default gaps for muscles not directly measured by tape
    _UNMEASURED_DEFAULTS = {
        "back": 4.0,       # No tape measurement; always a priority
        "triceps": 2.0,    # Indirect from arm tape; gets overflow from pressing
        "abs": 0.0,        # Not size-driven
    }

    muscle_gaps: dict[str, float] = {}
    for site, gap_cm in hqi_gaps.items():
        for muscle in site_to_muscles.get(site, []):
            muscle_gaps[muscle] = gap_cm
    for muscle, default_gap in _UNMEASURED_DEFAULTS.items():
        if muscle not in muscle_gaps:
            muscle_gaps[muscle] = default_gap

    # Division-aware volume: use the split designer's need-score + importance
    # weighting so hidden muscles (e.g. calves/quads in MP) get maintenance
    # volume while priority muscles (shoulders, back) get pushed toward MRV.
    from app.engines.engine2.split_designer import (
        compute_need_scores,
        compute_volume_budget,
    )
    division = getattr(profile, "division", "classic_physique") or "classic_physique"
    need_scores = compute_need_scores(muscle_gaps, division)
    split_volume = compute_volume_budget(muscle_gaps, need_scores, division)

    # Apply the split designer's aggregation safety clamp (Rule 1C).
    # Division-aware: men's divisions get higher shoulder caps (24 sets)
    # because delts are a primary judging criterion. Women's divisions get
    # lower caps (16 sets) because excessive shoulder mass is penalized.
    _DELT_CAP_BY_DIVISION = {
        "mens_physique": 24, "classic_physique": 24, "mens_open": 24,
        "womens_bikini": 14, "womens_figure": 18, "womens_physique": 22, "wellness": 14,
    }
    _MAX_COMBINED_DELT_VOL = _DELT_CAP_BY_DIVISION.get(division, 20)
    raw_delt_vol = sum(split_volume.get(h, 0) for h in ("front_delt", "side_delt", "rear_delt"))
    if raw_delt_vol > _MAX_COMBINED_DELT_VOL:
        scale = _MAX_COMBINED_DELT_VOL / raw_delt_vol
        for h in ("front_delt", "side_delt", "rear_delt"):
            if h in split_volume:
                split_volume[h] = round(split_volume[h] * scale)

    # Map split_designer muscle names back to the router's aggregated format
    volume_allocation: dict[str, int] = {}
    for muscle in DEFAULT_VOLUME:
        if muscle == "shoulders":
            volume_allocation[muscle] = (
                split_volume.get("front_delt", 0)
                + split_volume.get("side_delt", 0)
                + split_volume.get("rear_delt", 0)
            )
        elif muscle in split_volume:
            volume_allocation[muscle] = split_volume[muscle]
        else:
            volume_allocation[muscle] = DEFAULT_VOLUME.get(muscle, 8)

    return {"volume_allocation": volume_allocation, "muscle_gaps": muscle_gaps}


# ---------------------------------------------------------------------------
# Exercise library
# ---------------------------------------------------------------------------

@router.get("/exercises")
async def list_exercises(
    muscle: str | None = None,
    equipment: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(Exercise)
    if muscle:
        q = q.where(Exercise.primary_muscle == muscle.lower())
    if equipment:
        q = q.where(Exercise.equipment.ilike(f"%{equipment}%"))
    q = q.order_by(Exercise.primary_muscle, Exercise.biomechanical_efficiency.desc()).limit(200)
    result = await db.execute(q)
    exercises = result.scalars().all()
    def _ex_dict(e):
        secondary = [m.strip() for m in (e.secondary_muscles or "").split(",") if m.strip()]
        compound = e.movement_pattern in ("push", "pull", "squat", "hinge", "carry", "compound")
        return {
            "id": str(e.id),
            "name": e.name,
            "primary_muscle": e.primary_muscle,
            "secondary_muscles": secondary,
            "movement_type": e.movement_pattern,
            "equipment": e.equipment,
            "compound": compound,
            "efficiency": round(e.biomechanical_efficiency, 3),
            "fatigue_ratio": round(e.fatigue_ratio, 3),
        }
    return [_ex_dict(e) for e in exercises]


@router.get("/exercises/search")
async def search_exercises(
    q: str = "",
    muscle: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Exercise)
    if q:
        query = query.where(Exercise.name.ilike(f"%{q}%"))
    if muscle:
        query = query.where(Exercise.primary_muscle == muscle.lower())
    query = query.order_by(Exercise.biomechanical_efficiency.desc()).limit(50)
    result = await db.execute(query)
    exercises = result.scalars().all()
    def _ex_dict(e):
        secondary = [m.strip() for m in (e.secondary_muscles or "").split(",") if m.strip()]
        compound = e.movement_pattern in ("push", "pull", "squat", "hinge", "carry", "compound")
        return {
            "id": str(e.id),
            "name": e.name,
            "primary_muscle": e.primary_muscle,
            "secondary_muscles": secondary,
            "movement_type": e.movement_pattern,
            "equipment": e.equipment,
            "compound": compound,
        }
    return [_ex_dict(e) for e in exercises]


# ---------------------------------------------------------------------------
# Optimal split recommendation
# ---------------------------------------------------------------------------

@router.get("/optimal-split")
async def get_optimal_split(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Design a custom training split based on HQI gaps, division importance,
    and recovery constraints. Returns a fully custom weekly template.
    """
    profile_result = await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))
    profile = profile_result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    prefs = profile.preferences or {}
    days_per_week = max(2, min(7, int(prefs.get("training_days_per_week", 4))))
    division = getattr(profile, "division", "mens_open") or "mens_open"

    # Load latest HQI data
    hqi_result = await db.execute(
        select(HQILog).where(HQILog.user_id == user.id)
        .order_by(desc(HQILog.recorded_date), desc(HQILog.created_at)).limit(1)
    )
    hqi_log = hqi_result.scalar_one_or_none()

    hqi_gaps: dict[str, float] = {}
    if hqi_log and hqi_log.site_scores:
        for k, v in hqi_log.site_scores.items():
            if isinstance(v, dict):
                hqi_gaps[k.lower()] = max(0.0, v.get("gap_cm", 0.0))
            else:
                hqi_gaps[k.lower()] = 0.0

    from app.engines.engine2.split_designer import design_split
    result = design_split(hqi_gaps, division, days_per_week)

    return {
        "optimal_split": "custom",
        "label": "Custom Split",
        "days_per_week": days_per_week,
        "division": division,
        "reasoning": result["reasoning"],
        "template": [
            {"day": t["day"], "muscles": t["muscles"]}
            for t in result["template"]
        ],
        "need_scores": result["need_scores"],
        "volume_budget": result["volume_budget"],
        "desired_frequency": result["desired_frequency"],
        "hqi_available": bool(hqi_gaps),
    }


# ---------------------------------------------------------------------------
# Program management
# ---------------------------------------------------------------------------

@router.get("/program/current")
async def get_current_program(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(TrainingProgram)
        .where(TrainingProgram.user_id == user.id, TrainingProgram.is_active == True)
        .order_by(desc(TrainingProgram.created_at))
        .limit(1)
    )
    program = result.scalar_one_or_none()
    if not program:
        raise HTTPException(status_code=404, detail="No active program")

    return {
        "id": str(program.id),
        "name": program.name,
        "split_type": program.split_type,
        "days_per_week": program.days_per_week,
        "mesocycle_weeks": program.mesocycle_weeks,
        "current_week": program.current_week,
        "volume_allocation": program.volume_allocation,
    }


@router.post("/program/generate")
async def generate_program(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    profile_result = await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))
    profile = profile_result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=400, detail="Complete onboarding first")

    # Read phase for strategic mesocycle length (e.g. 6w bulk, 4w cut)
    from app.engines.engine1.prep_timeline import prep_phase_for_date, get_phase_config
    comp_date = getattr(profile, "competition_date", None)
    current_phase = prep_phase_for_date(comp_date)
    phase_config = get_phase_config(current_phase)
    mesocycle_weeks = max(4, phase_config.get("recommended_meso_weeks", 6))

    # Read preferences — split is auto-selected by the engine based on HQI gaps
    prefs = profile.preferences or {}
    days_per_week = max(2, min(7, int(prefs.get("training_days_per_week", 4))))
    # split_type will be overwritten by auto_select_split() inside generate_program_sessions()
    split_type = "ppl"  # placeholder — will be replaced during generation

    # Build volume allocation from HQI gap_cm (bigger gap → more volume)
    volume_allocation = dict(DEFAULT_VOLUME)
    try:
        hqi_result = await db.execute(
            select(HQILog).where(HQILog.user_id == user.id)
            .order_by(desc(HQILog.recorded_date), desc(HQILog.created_at)).limit(1)
        )
        hqi_log = hqi_result.scalar_one_or_none()
        if hqi_log and hqi_log.site_scores:
            hqi_gaps: dict[str, float] = {}
            for site, data in hqi_log.site_scores.items():
                if isinstance(data, dict):
                    hqi_gaps[site.lower()] = max(0.0, data.get("gap_cm", 0.0))
                else:
                    hqi_gaps[site.lower()] = 0.0

            site_to_muscles = {
                "shoulders": ["shoulders"], "chest": ["chest"],
                "bicep": ["biceps"], "forearm": ["forearms"],
                "neck": ["traps"], "thigh": ["quads", "hamstrings"],
                "calf": ["calves"], "hips": ["glutes"],
            }
            _UNMEASURED_DEFAULTS = {"back": 4.0, "triceps": 2.0, "abs": 0.0}
            muscle_gaps: dict[str, float] = {}
            for site, gap_cm in hqi_gaps.items():
                for muscle in site_to_muscles.get(site, []):
                    muscle_gaps[muscle] = gap_cm
            for muscle, default_gap in _UNMEASURED_DEFAULTS.items():
                if muscle not in muscle_gaps:
                    muscle_gaps[muscle] = default_gap

            # Division-aware volume via split designer (respects importance weights)
            from app.engines.engine2.split_designer import (
                compute_need_scores,
                compute_volume_budget,
            )
            division = getattr(profile, "division", "classic_physique") or "classic_physique"
            need_scores = compute_need_scores(muscle_gaps, division)
            split_volume = compute_volume_budget(muscle_gaps, need_scores, division)
            # Division-aware delt aggregation safety clamp
            _DELT_CAPS = {
                "mens_physique": 24, "classic_physique": 24, "mens_open": 24,
                "womens_bikini": 14, "womens_figure": 18, "womens_physique": 22, "wellness": 14,
            }
            _MAX_DELT = _DELT_CAPS.get(division, 20)
            raw_delt = sum(split_volume.get(h, 0) for h in ("front_delt", "side_delt", "rear_delt"))
            if raw_delt > _MAX_DELT:
                sc = _MAX_DELT / raw_delt
                for h in ("front_delt", "side_delt", "rear_delt"):
                    if h in split_volume:
                        split_volume[h] = round(split_volume[h] * sc)
            for muscle in volume_allocation:
                if muscle == "shoulders":
                    volume_allocation[muscle] = (
                        split_volume.get("front_delt", 0)
                        + split_volume.get("side_delt", 0)
                        + split_volume.get("rear_delt", 0)
                    )
                elif muscle in split_volume:
                    volume_allocation[muscle] = split_volume[muscle]
    except (ValueError, KeyError) as e:
        logger.warning("HQI-driven volume allocation failed: %s", e)

    # Atomically deactivate old programs — use a single UPDATE so two
    # concurrent generation requests can't both leave multiple is_active=True rows.
    from sqlalchemy import update as _update
    await db.execute(
        _update(TrainingProgram)
        .where(TrainingProgram.user_id == user.id, TrainingProgram.is_active == True)
        .values(is_active=False)
    )

    program = TrainingProgram(
        user_id=user.id,
        name="Coronado Mesocycle",
        split_type=split_type,
        days_per_week=days_per_week,
        mesocycle_weeks=mesocycle_weeks,
        current_week=1,
        is_active=True,
        volume_allocation=volume_allocation,
    )
    db.add(program)
    await db.flush()

    # Use program_start_date from profile if set, otherwise default to today
    prof_result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == user.id)
    )
    _prof = prof_result.scalar_one_or_none()
    program_start = getattr(_prof, "program_start_date", None) or date.today()

    sessions_created = await generate_program_sessions(
        db=db,
        user_id=user.id,
        program=program,
        volume_allocation=volume_allocation,
        start_date=program_start,
    )

    # Check stale baselines on first session
    stale = False
    first_sess_result = await db.execute(
        select(TrainingSession).where(TrainingSession.program_id == program.id)
        .order_by(TrainingSession.session_date).limit(1)
    )
    first_sess = first_sess_result.scalar_one_or_none()
    if first_sess:
        stale = first_sess.stale_baselines

    return {
        "id": str(program.id),
        "name": program.name,
        "split_type": program.split_type,  # now auto-selected
        "days_per_week": program.days_per_week,
        "mesocycle_weeks": program.mesocycle_weeks,
        "current_week": program.current_week,
        "sessions_created": sessions_created,
        "stale_baselines": stale,
        "message": (
            f"Program generated: {program.split_type.upper()} split selected based on your physique gaps. "
            f"{sessions_created} sessions scheduled from next Monday."
        ),
    }


# ---------------------------------------------------------------------------
# Session view + logging
# ---------------------------------------------------------------------------

@router.get("/session/{session_date}")
async def get_session(
    session_date: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from datetime import date as _date
    resolved = _date.today() if session_date == "today" else _date.fromisoformat(session_date)
    # Prefer session from the active program; fall back to any session on that date
    result = await db.execute(
        select(TrainingSession)
        .join(TrainingProgram, TrainingSession.program_id == TrainingProgram.id)
        .where(
            TrainingSession.user_id == user.id,
            TrainingSession.session_date == resolved,
            TrainingProgram.is_active == True,
        )
        .limit(1)
    )
    session = result.scalar_one_or_none()
    if not session:
        # Fall back to any session on that date, but ONLY from programs that
        # were active (not orphaned sessions from old deactivated programs).
        # Completed sessions are always visible (historical data).
        result = await db.execute(
            select(TrainingSession)
            .where(
                TrainingSession.user_id == user.id,
                TrainingSession.session_date == resolved,
                TrainingSession.completed == True,
            )
            .order_by(desc(TrainingSession.created_at))
            .limit(1)
        )
        session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="No session for this date")

    sets_result = await db.execute(
        select(TrainingSet, Exercise.name, Exercise.primary_muscle, Exercise.equipment,
               Exercise.movement_pattern, Exercise.load_type)
        .join(Exercise, TrainingSet.exercise_id == Exercise.id)
        .where(TrainingSet.session_id == session.id)
        .order_by(TrainingSet.set_number)
    )
    sets_rows = sets_result.all()

    # Load previous session of same type for ghost (last actual values)
    prev_actuals: dict[str, dict] = {}
    prev_session_result = await db.execute(
        select(TrainingSession)
        .where(
            TrainingSession.user_id == user.id,
            TrainingSession.session_type == session.session_type,
            TrainingSession.completed == True,
            TrainingSession.session_date < session.session_date,
        )
        .order_by(desc(TrainingSession.session_date))
        .limit(1)
    )
    prev_session = prev_session_result.scalar_one_or_none()
    if prev_session:
        prev_sets_result = await db.execute(
            select(TrainingSet, Exercise.name)
            .join(Exercise, TrainingSet.exercise_id == Exercise.id)
            .where(TrainingSet.session_id == prev_session.id, TrainingSet.is_warmup == False)
            .order_by(TrainingSet.set_number)
        )
        # Key by exercise_name + set_number for matching
        for pts, pname in prev_sets_result.all():
            key = f"{pname}_{pts.set_number}"
            prev_actuals[key] = {
                "last_actual_reps": pts.actual_reps,
                "last_actual_weight_kg": pts.actual_weight_kg,
            }

    from app.services.training import _TECHNIQUE_COACHING

    sets = []
    for ts, name, muscle, equipment, movement_pattern, load_type in sets_rows:
        key = f"{name}_{ts.set_number}"
        ghost = prev_actuals.get(key, {})
        technique = getattr(ts, "set_technique", None)
        sets.append({
            "id": str(ts.id),
            "exercise_name": name,
            "muscle_group": muscle,
            "equipment": equipment or "bodyweight",
            "movement_pattern": movement_pattern or "isolation",
            "load_type": load_type or "",
            "set_number": ts.set_number,
            "prescribed_reps": ts.prescribed_reps,
            "prescribed_weight_kg": ts.prescribed_weight_kg,
            "prescribed_rir": getattr(ts, "prescribed_rir", None),
            "prescribed_rpe": getattr(ts, "prescribed_rpe", None),
            "tempo": getattr(ts, "tempo", None),
            "set_technique": technique,
            "technique_cue": _TECHNIQUE_COACHING.get(technique) if technique else None,
            "actual_reps": ts.actual_reps,
            "actual_weight_kg": ts.actual_weight_kg,
            "rpe": ts.rpe,
            "is_warmup": ts.is_warmup,
            "is_fst7": ts.is_fst7,
            "rest_seconds": ts.rest_seconds,
            "last_actual_reps": ghost.get("last_actual_reps"),
            "last_actual_weight_kg": ghost.get("last_actual_weight_kg"),
        })

    # Compute estimated duration + workout window from the user's profile anchor.
    from app.services.training import estimate_session_duration_minutes, compute_workout_window
    profile_row = await db.execute(
        select(UserProfile).where(UserProfile.user_id == user.id)
    )
    _profile = profile_row.scalar_one_or_none()
    duration_min = estimate_session_duration_minutes([r[0] for r in sets_rows])
    anchor_mode = (getattr(_profile, "training_time_anchor", None) or "start") if _profile else "start"
    if _profile and anchor_mode == "end":
        anchor_time = getattr(_profile, "training_end_time", None)
    else:
        anchor_time = getattr(_profile, "training_start_time", None) if _profile else None
    window = compute_workout_window(anchor_time, anchor_mode, duration_min)

    return {
        "id": str(session.id),
        "session_type": session.session_type,
        "session_date": str(session.session_date),
        "week_number": session.week_number,
        "day_number": session.day_number,
        "completed": session.completed,
        "stale_baselines": session.stale_baselines,
        "split_type": session.split_type,
        "dup_profile": session.dup_profile,
        "estimated_duration_min": duration_min,
        "workout_window": {
            "anchor_mode": anchor_mode,
            "start_time": window["start"],
            "end_time": window["end"],
        },
        "sets": sets,
    }


class SetLog(BaseModel):
    set_id: str
    actual_reps: int | None = None
    actual_weight_kg: float | None = None
    rpe: float | None = None
    actual_exercise_name: str | None = None


class SessionLogRequest(BaseModel):
    sets: list[SetLog]
    notes: str | None = None


@router.post("/session/{session_id}/log")
async def log_session(
    session_id: str,
    data: SessionLogRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(TrainingSession).where(
            TrainingSession.id == uuid.UUID(session_id),
            TrainingSession.user_id == user.id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    progressions = []
    for set_log in data.sets:
        set_result = await db.execute(
            select(TrainingSet, Exercise.name)
            .join(Exercise, TrainingSet.exercise_id == Exercise.id)
            .where(TrainingSet.id == uuid.UUID(set_log.set_id))
        )
        row = set_result.one_or_none()
        if not row:
            continue
        training_set, ex_name = row

        if set_log.actual_reps is not None:
            training_set.actual_reps = set_log.actual_reps
        if set_log.actual_weight_kg is not None:
            training_set.actual_weight_kg = set_log.actual_weight_kg
        if set_log.rpe is not None:
            training_set.rpe = set_log.rpe

        is_substitute = bool(set_log.actual_exercise_name and set_log.actual_exercise_name.strip().lower() != ex_name.strip().lower())

        if is_substitute and set_log.actual_reps and set_log.actual_weight_kg:
            from app.engines.engine2.resistance import estimate_1rm
            e1rm = estimate_1rm(set_log.actual_weight_kg, set_log.actual_reps)
            # BUG-01 fix: look up exercise_id by name for substitute exercise
            sub_ex_result = await db.execute(
                select(Exercise).where(
                    func.lower(Exercise.name) == set_log.actual_exercise_name.strip().lower()
                )
            )
            sub_ex = sub_ex_result.scalar_one_or_none()
            sub_exercise_id = sub_ex.id if sub_ex else training_set.exercise_id
            db.add(StrengthLog(
                user_id=user.id,
                recorded_date=date.today(),
                exercise_id=sub_exercise_id,
                weight_kg=set_log.actual_weight_kg,
                reps=set_log.actual_reps,
                rpe=set_log.rpe,
                estimated_1rm=e1rm,
            ))
            continue

        # Double progression check with equipment-specific increments
        if training_set.actual_reps and training_set.actual_weight_kg and training_set.rpe:
            from app.engines.engine2.resistance import compute_progression
            # Load exercise for load_type-aware progression
            ex_full_result = await db.execute(select(Exercise).where(Exercise.id == training_set.exercise_id))
            ex_full = ex_full_result.scalar_one_or_none()
            rep_ceiling = training_set.prescribed_reps + 2
            prog = compute_progression(
                current_weight=training_set.actual_weight_kg,
                current_reps=training_set.actual_reps,
                target_reps=rep_ceiling,
                rpe=training_set.rpe,
                rep_floor=training_set.prescribed_reps,
                load_type=getattr(ex_full, "load_type", "") or "",
                exercise_name=ex_full.name if ex_full else "",
            )
            if prog["action"] == "increase_weight":
                progressions.append({
                    "exercise": ex_name,
                    "action": "increase_weight",
                    "next_weight_kg": prog["next_weight"],
                    "next_reps": prog["next_reps"],
                    "estimated_1rm": prog["estimated_1rm"],
                })

    session.completed = True
    if data.notes is not None:
        session.notes = data.notes
    await db.flush()

    return {
        "message": "Session logged successfully",
        "progressions": progressions,
    }


@router.post("/session/{session_id}/start")
async def start_session(
    session_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark session as started (sets started_at timestamp)."""
    from datetime import datetime, timezone
    result = await db.execute(
        select(TrainingSession).where(
            TrainingSession.id == uuid.UUID(session_id),
            TrainingSession.user_id == user.id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if not session.started_at:
        session.started_at = datetime.now(timezone.utc)
        await db.flush()
    return {"started_at": str(session.started_at)}


# ---------------------------------------------------------------------------
# Per-set auto-save (Block 1 — Workout Auto-Save)
# ---------------------------------------------------------------------------


class SetPatchRequest(BaseModel):
    actual_reps: int | None = None
    actual_weight_kg: float | None = None
    rpe: float | None = None
    actual_exercise_name: str | None = None


@router.patch("/session/{session_id}/set/{set_id}")
async def patch_set(
    session_id: str,
    set_id: str,
    data: SetPatchRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Per-set persistence endpoint for auto-save.

    Fires on every set completion and on debounced input changes.
    Only updates the fields that are provided (non-None).
    Returns the updated set data plus a progression hint if applicable.
    """
    # Validate session ownership
    sess_result = await db.execute(
        select(TrainingSession).where(
            TrainingSession.id == uuid.UUID(session_id),
            TrainingSession.user_id == user.id,
        )
    )
    session = sess_result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Load the set + exercise name
    set_result = await db.execute(
        select(TrainingSet, Exercise.name, Exercise)
        .join(Exercise, TrainingSet.exercise_id == Exercise.id)
        .where(
            TrainingSet.id == uuid.UUID(set_id),
            TrainingSet.session_id == session.id,
        )
    )
    row = set_result.one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Set not found in this session")
    training_set, ex_name, exercise = row

    # Apply partial updates
    if data.actual_reps is not None:
        training_set.actual_reps = data.actual_reps
    if data.actual_weight_kg is not None:
        training_set.actual_weight_kg = data.actual_weight_kg
    if data.rpe is not None:
        training_set.rpe = data.rpe

    # Handle substitute exercise logging
    is_substitute = bool(
        data.actual_exercise_name
        and data.actual_exercise_name.strip().lower() != ex_name.strip().lower()
    )
    if is_substitute and data.actual_reps and data.actual_weight_kg:
        from app.engines.engine2.resistance import estimate_1rm
        e1rm = estimate_1rm(data.actual_weight_kg, data.actual_reps)
        # Look up exercise_id for the substitute by name; fall back to original
        sub_ex_result = await db.execute(
            select(Exercise).where(
                func.lower(Exercise.name) == data.actual_exercise_name.strip().lower()
            )
        )
        sub_ex = sub_ex_result.scalar_one_or_none()
        sub_exercise_id = sub_ex.id if sub_ex else exercise.id
        db.add(StrengthLog(
            user_id=user.id,
            recorded_date=date.today(),
            exercise_id=sub_exercise_id,
            weight_kg=data.actual_weight_kg,
            reps=data.actual_reps,
            rpe=data.rpe,
            estimated_1rm=e1rm,
        ))

    # Progression hint — only when all 3 values present and not a substitute
    progression = None
    if (
        not is_substitute
        and training_set.actual_reps is not None
        and training_set.actual_weight_kg is not None
        and training_set.rpe is not None
    ):
        from app.engines.engine2.resistance import compute_progression
        rep_ceiling = training_set.prescribed_reps + 2
        prog = compute_progression(
            current_weight=training_set.actual_weight_kg,
            current_reps=training_set.actual_reps,
            target_reps=rep_ceiling,
            rpe=training_set.rpe,
            rep_floor=training_set.prescribed_reps,
            load_type=getattr(exercise, "load_type", "") or "",
            exercise_name=exercise.name,
        )
        if prog["action"] == "increase_weight":
            progression = {
                "exercise": ex_name,
                "action": "increase_weight",
                "next_weight_kg": prog["next_weight"],
                "next_reps": prog["next_reps"],
                "estimated_1rm": prog["estimated_1rm"],
            }

    await db.flush()

    return {
        "set_id": str(training_set.id),
        "actual_reps": training_set.actual_reps,
        "actual_weight_kg": training_set.actual_weight_kg,
        "rpe": training_set.rpe,
        "progression": progression,
    }


class FinishSessionRequest(BaseModel):
    notes: str | None = None


@router.post("/session/{session_id}/finish")
async def finish_session(
    session_id: str,
    data: FinishSessionRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Mark session as completed + run final progression checks.

    Called when user clicks "Finish Session". All set data should already
    be persisted via PATCH calls. This endpoint:
    1. Marks session.completed = True
    2. Sets completed_at timestamp
    3. Runs double-progression check on all completed sets
    4. Returns aggregated progressions
    """
    from datetime import datetime, timezone

    result = await db.execute(
        select(TrainingSession).where(
            TrainingSession.id == uuid.UUID(session_id),
            TrainingSession.user_id == user.id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session.completed = True
    session.completed_at = datetime.now(timezone.utc)
    if data.notes is not None:
        session.notes = data.notes

    # Run progression checks on all completed (non-warmup) sets
    sets_result = await db.execute(
        select(TrainingSet, Exercise)
        .join(Exercise, TrainingSet.exercise_id == Exercise.id)
        .where(
            TrainingSet.session_id == session.id,
            TrainingSet.is_warmup == False,
        )
        .order_by(TrainingSet.set_number)
    )

    progressions = []
    seen_exercises: set[str] = set()
    from app.engines.engine2.resistance import compute_progression

    for training_set, exercise in sets_result.all():
        if (
            training_set.actual_reps is None
            or training_set.actual_weight_kg is None
            or training_set.rpe is None
        ):
            continue
        # One progression per exercise (use last completed set)
        ex_key = exercise.name.lower()
        rep_ceiling = training_set.prescribed_reps + 2
        prog = compute_progression(
            current_weight=training_set.actual_weight_kg,
            current_reps=training_set.actual_reps,
            target_reps=rep_ceiling,
            rpe=training_set.rpe,
            rep_floor=training_set.prescribed_reps,
            load_type=getattr(exercise, "load_type", "") or "",
            exercise_name=exercise.name,
        )
        if prog["action"] == "increase_weight" and ex_key not in seen_exercises:
            progressions.append({
                "exercise": exercise.name,
                "action": "increase_weight",
                "next_weight_kg": prog["next_weight"],
                "next_reps": prog["next_reps"],
                "estimated_1rm": prog["estimated_1rm"],
            })
            seen_exercises.add(ex_key)

    await db.flush()

    return {
        "message": "Session completed",
        "progressions": progressions,
    }


# ---------------------------------------------------------------------------
# Strength logging (outside of sessions — e.g. 1RM tests)
# ---------------------------------------------------------------------------

@router.post("/strength-log")
async def log_strength_test(
    data: dict,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Log a strength test or max-effort set outside of a training session.
    Body: { "exercise_name": str, "weight_kg": float, "reps": int, "rpe": float? }
    """
    from app.models.training import StrengthLog
    from sqlalchemy import select
    from datetime import date as _date

    ex_result = await db.execute(
        select(Exercise).where(Exercise.name.ilike(f"%{data['exercise_name']}%"))
    )
    ex = ex_result.scalar_one_or_none()
    if not ex:
        raise HTTPException(status_code=404, detail=f"Exercise '{data['exercise_name']}' not found")

    weight = float(data["weight_kg"])
    reps = int(data["reps"])
    # Epley 1RM formula
    e1rm = weight * (1 + reps / 30) if reps < 30 else weight

    log = StrengthLog(
        user_id=user.id,
        exercise_id=ex.id,
        weight_kg=weight,
        reps=reps,
        rpe=data.get("rpe"),
        estimated_1rm=round(e1rm, 1),
        recorded_date=_date.today(),
    )
    db.add(log)
    await db.flush()

    return {
        "message": "Strength test logged",
        "exercise": ex.name,
        "weight_kg": weight,
        "reps": reps,
        "estimated_1rm": round(e1rm, 1),
    }


@router.get("/strength-log")
async def get_strength_history(
    exercise_name: str | None = None,
    limit: int = 50,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.models.training import StrengthLog
    from sqlalchemy import select, desc

    q = (
        select(StrengthLog, Exercise.name)
        .join(Exercise, StrengthLog.exercise_id == Exercise.id)
        .where(StrengthLog.user_id == user.id)
    )
    if exercise_name:
        q = q.where(Exercise.name.ilike(f"%{exercise_name}%"))
    q = q.order_by(desc(StrengthLog.recorded_date), desc(StrengthLog.created_at)).limit(min(limit, 100))

    result = await db.execute(q)
    return [
        {
            "date": str(log.recorded_date),
            "exercise": name,
            "weight_kg": log.weight_kg,
            "reps": log.reps,
            "rpe": log.rpe,
            "estimated_1rm": log.estimated_1rm,
        }
        for log, name in result.all()
    ]


# ---------------------------------------------------------------------------
# Autoregulation & Progression
# ---------------------------------------------------------------------------

@router.post("/program/autoregulate-today")
async def autoregulate_today(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Lookup today's active session
    today = date.today()
    result_session = await db.execute(
        select(TrainingSession)
        .where(
            TrainingSession.user_id == user.id, 
            TrainingSession.session_date == today, 
            TrainingSession.completed == False
        )
    )
    session = result_session.scalar_one_or_none()
    if not session:
        return {"message": "No active session today.", "dropped_sets": 0}

    # Fetch today's HRVLog for soreness data
    result_hrv = await db.execute(
        select(HRVLog)
        .where(HRVLog.user_id == user.id, HRVLog.recorded_date == today)
    )
    hrv = result_hrv.scalar_one_or_none()
    if not hrv or not getattr(hrv, "sore_muscles", None):
        return {"message": "No sore muscles logged today.", "dropped_sets": 0}

    # Call the training service
    from app.services.training import autoregulate_session_for_soreness
    dropped, affected = await autoregulate_session_for_soreness(db, user.id, session, hrv.sore_muscles)
    await db.commit()

    return {
        "message": f"Session autoregulated. Dropped {dropped} sets.",
        "dropped_sets": dropped,
        "affected_exercises": affected,
    }

# Progression status
# ---------------------------------------------------------------------------

@router.get("/progression-status")
async def get_progression_status(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(TrainingSession)
        .where(TrainingSession.user_id == user.id, TrainingSession.completed == True)
        .order_by(desc(TrainingSession.session_date))
        .limit(5)
    )
    sessions = result.scalars().all()
    return [
        {
            "session_date": str(s.session_date),
            "session_type": s.session_type,
            "week_number": s.week_number,
        }
        for s in sessions
    ]


# ---------------------------------------------------------------------------
# Session history
# ---------------------------------------------------------------------------

@router.get("/sessions/history")
async def get_session_history(
    limit: int = 20,
    offset: int = 0,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return completed sessions ordered by date descending, with exercise names."""
    result = await db.execute(
        select(TrainingSession)
        .where(TrainingSession.user_id == user.id, TrainingSession.completed == True)
        .order_by(desc(TrainingSession.session_date))
        .limit(min(limit, 50))
        .offset(offset)
    )
    sessions = result.scalars().all()
    output = []
    for s in sessions:
        sets_result = await db.execute(
            select(Exercise.name, Exercise.primary_muscle)
            .join(TrainingSet, TrainingSet.exercise_id == Exercise.id)
            .where(TrainingSet.session_id == s.id, TrainingSet.is_warmup == False)
            .distinct()
        )
        ex_rows = sets_result.all()
        set_count_result = await db.execute(
            select(TrainingSet)
            .where(TrainingSet.session_id == s.id, TrainingSet.is_warmup == False)
        )
        set_count = len(set_count_result.scalars().all())
        output.append({
            "id": str(s.id),
            "session_date": str(s.session_date),
            "session_type": s.session_type,
            "week_number": s.week_number,
            "completed": s.completed,
            "set_count": set_count,
            "exercises": [name for name, _ in ex_rows],
            "muscles": list({muscle for _, muscle in ex_rows}),
        })
    return output


# ---------------------------------------------------------------------------
# Program schedule overview
# ---------------------------------------------------------------------------

@router.get("/program/schedule")
async def get_program_schedule(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return all sessions for the active program, for calendar/overview display."""
    prog_result = await db.execute(
        select(TrainingProgram)
        .where(TrainingProgram.user_id == user.id, TrainingProgram.is_active == True)
        .order_by(desc(TrainingProgram.created_at)).limit(1)
    )
    program = prog_result.scalar_one_or_none()
    if not program:
        raise HTTPException(status_code=404, detail="No active program")

    sessions_result = await db.execute(
        select(TrainingSession)
        .where(TrainingSession.program_id == program.id)
        .order_by(TrainingSession.session_date)
    )
    sessions = sessions_result.scalars().all()

    session_list = []
    for s in sessions:
        # Get distinct muscle groups for this session
        muscle_result = await db.execute(
            select(Exercise.primary_muscle)
            .join(TrainingSet, TrainingSet.exercise_id == Exercise.id)
            .where(TrainingSet.session_id == s.id, TrainingSet.is_warmup == False)
            .distinct()
        )
        muscles = [row[0] for row in muscle_result.all()]
        session_list.append({
            "id": str(s.id),
            "session_date": str(s.session_date),
            "session_type": s.session_type,
            "week_number": s.week_number,
            "day_number": s.day_number,
            "completed": s.completed,
            "is_deload": (s.week_number % 4 == 0),
            "primary_muscles": muscles,
        })

    return {
        "program": {
            "id": str(program.id),
            "name": program.name,
            "split_type": program.split_type,
            "days_per_week": program.days_per_week,
            "mesocycle_weeks": program.mesocycle_weeks,
            "current_week": program.current_week,
        },
        "sessions": session_list,
    }


# ---------------------------------------------------------------------------
# Custom exercise creation
# ---------------------------------------------------------------------------

class CustomExerciseRequest(BaseModel):
    name: str
    primary_muscle: str
    equipment: str
    movement_pattern: str
    biomechanical_efficiency: float = 5.0
    fatigue_ratio: float = 1.0
    secondary_muscles: str | None = None


@router.post("/exercises")
async def create_custom_exercise(
    data: CustomExerciseRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a user-specific custom exercise."""
    # Check for name collision
    existing = await db.execute(
        select(Exercise).where(Exercise.name.ilike(data.name))
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="An exercise with this name already exists")

    ex = Exercise(
        name=data.name,
        primary_muscle=data.primary_muscle.lower(),
        equipment=data.equipment.lower(),
        movement_pattern=data.movement_pattern.lower(),
        biomechanical_efficiency=data.biomechanical_efficiency,
        fatigue_ratio=data.fatigue_ratio,
        secondary_muscles=data.secondary_muscles,
        user_id=user.id,
        is_custom=True,
    )
    db.add(ex)
    await db.flush()

    return {
        "id": str(ex.id),
        "name": ex.name,
        "primary_muscle": ex.primary_muscle,
        "equipment": ex.equipment,
        "movement_pattern": ex.movement_pattern,
        "is_custom": True,
        "message": "Custom exercise created",
    }


# ---------------------------------------------------------------------------
# Volume history — weekly working sets per muscle group (last 8 weeks)
# ---------------------------------------------------------------------------

@router.get("/volume-history")
async def get_volume_history(
    weeks: int = 8,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Return weekly volume (total working sets) per muscle group for the last N weeks.
    Queries training_sessions → training_sets → exercises, grouped by week_number and
    exercise.primary_muscle. Only completed sessions with non-warmup sets are counted.
    """
    weeks = max(1, min(weeks, 52))

    # Find the maximum week_number for this user's completed sessions
    max_week_result = await db.execute(
        select(func.max(TrainingSession.week_number))
        .where(
            TrainingSession.user_id == user.id,
            TrainingSession.completed == True,
        )
    )
    max_week = max_week_result.scalar()
    if max_week is None:
        return {"weeks": []}

    min_week = max(1, max_week - weeks + 1)

    # Query: join sessions → sets → exercises, filter completed + non-warmup
    rows = await db.execute(
        select(
            TrainingSession.week_number,
            Exercise.primary_muscle,
            func.count(TrainingSet.id).label("set_count"),
        )
        .join(TrainingSet, TrainingSet.session_id == TrainingSession.id)
        .join(Exercise, TrainingSet.exercise_id == Exercise.id)
        .where(
            TrainingSession.user_id == user.id,
            TrainingSession.completed == True,
            TrainingSession.week_number >= min_week,
            TrainingSession.week_number <= max_week,
            TrainingSet.is_warmup == False,
        )
        .group_by(TrainingSession.week_number, Exercise.primary_muscle)
        .order_by(TrainingSession.week_number)
    )
    result_rows = rows.all()

    # Aggregate into per-week structures
    week_data: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for week_number, muscle, set_count in result_rows:
        week_data[week_number][muscle] += set_count

    output_weeks = []
    for wk in range(min_week, max_week + 1):
        by_muscle = dict(week_data.get(wk, {}))
        total_sets = sum(by_muscle.values())
        output_weeks.append({
            "week_number": wk,
            "total_sets": total_sets,
            "by_muscle": by_muscle,
        })

    return {"weeks": output_weeks}


# ---------------------------------------------------------------------------
# Strength history — estimated 1RM over time for top exercises
# ---------------------------------------------------------------------------

@router.get("/strength-history")
async def get_strength_history_top(
    top_n: int = 5,
    entries_per_exercise: int = 12,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Return estimated 1RM history for the top N most-logged exercises.
    Queries strength_log joined with exercises, returning the last M entries
    per exercise, ordered by date descending.
    """
    top_n = max(1, min(top_n, 20))
    entries_per_exercise = max(1, min(entries_per_exercise, 50))

    # Step 1: Find the top N most-logged exercises for this user
    top_exercises_result = await db.execute(
        select(
            Exercise.id,
            Exercise.name,
            func.count(StrengthLog.id).label("log_count"),
        )
        .join(StrengthLog, StrengthLog.exercise_id == Exercise.id)
        .where(StrengthLog.user_id == user.id)
        .group_by(Exercise.id, Exercise.name)
        .order_by(func.count(StrengthLog.id).desc())
        .limit(top_n)
    )
    top_exercises = top_exercises_result.all()

    if not top_exercises:
        return {"exercises": {}}

    # Step 2: For each top exercise, fetch the last N entries
    exercises_output: dict[str, list] = {}
    for ex_id, ex_name, _count in top_exercises:
        entries_result = await db.execute(
            select(StrengthLog)
            .where(
                StrengthLog.user_id == user.id,
                StrengthLog.exercise_id == ex_id,
            )
            .order_by(desc(StrengthLog.recorded_date), desc(StrengthLog.created_at))
            .limit(entries_per_exercise)
        )
        entries = entries_result.scalars().all()
        exercises_output[ex_name] = [
            {
                "date": str(e.recorded_date),
                "estimated_1rm": e.estimated_1rm,
                "weight_kg": e.weight_kg,
                "reps": e.reps,
            }
            for e in entries
        ]

    return {"exercises": exercises_output}


# ---------------------------------------------------------------------------
# Strength Progression — e1RM of main compounds over time
# ---------------------------------------------------------------------------

_MAIN_LIFT_KEYS = {
    "squat": ["back squat", "barbell squat", "squat"],
    "bench": ["bench press", "barbell bench"],
    "deadlift": ["deadlift", "conventional deadlift"],
    "ohp": ["overhead press", "military press", "standing press"],
}

_LIFT_LABELS = {
    "squat": "Squat",
    "bench": "Bench",
    "deadlift": "Deadlift",
    "ohp": "OHP",
}

_LIFT_COLORS = {
    "squat": "#22c55e",
    "bench": "#c8a84e",
    "deadlift": "#ef4444",
    "ohp": "#3b82f6",
}


def _classify_main_lift(exercise_name: str) -> str | None:
    name = (exercise_name or "").lower()
    for lift_key, patterns in _MAIN_LIFT_KEYS.items():
        if any(pat in name for pat in patterns):
            return lift_key
    return None


@router.get("/strength/progression")
async def get_strength_progression(
    days: int = 180,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns e1RM time series for each of the main compound lifts.
    Uses StrengthLog entries where available, or falls back to computing
    e1RM from completed TrainingSets via the Epley formula.
    """
    from datetime import date as _d, timedelta as _td
    cutoff = _d.today() - _td(days=max(1, min(days, 365)))

    result = await db.execute(
        select(StrengthLog, Exercise.name)
        .join(Exercise, StrengthLog.exercise_id == Exercise.id)
        .where(StrengthLog.user_id == user.id, StrengthLog.recorded_date >= cutoff)
        .order_by(StrengthLog.recorded_date)
    )
    entries = result.all()

    series: dict[str, list[dict]] = {k: [] for k in _MAIN_LIFT_KEYS.keys()}
    for log, ex_name in entries:
        lift = _classify_main_lift(ex_name)
        if not lift:
            continue
        e1rm = log.estimated_1rm
        if e1rm is None and log.weight_kg and log.reps:
            # Epley formula
            e1rm = log.weight_kg * (1 + log.reps / 30)
        if e1rm is None:
            continue
        series[lift].append({
            "date": str(log.recorded_date),
            "e1rm_kg": round(float(e1rm), 1),
        })

    return {
        "series": [
            {
                "lift": lift,
                "label": _LIFT_LABELS[lift],
                "color": _LIFT_COLORS[lift],
                "data": series[lift],
            }
            for lift in _MAIN_LIFT_KEYS.keys()
        ],
    }


# ---------------------------------------------------------------------------
# Weekly Volume vs MEV/MAV/MRV Landmarks
# ---------------------------------------------------------------------------

@router.get("/volume/weekly")
async def get_weekly_volume(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Aggregate working-set volume per muscle group for the current training week
    (Monday-Sunday). Returns rows of {muscle, sets, mev, mav, mrv} so the
    frontend can display landmark-relative bars.
    """
    from datetime import date as _d, timedelta as _td
    from sqlalchemy import and_
    from app.engines.engine2.split_designer import _VOLUME_LANDMARKS

    today = _d.today()
    monday = today - _td(days=today.weekday())
    sunday = monday + _td(days=6)

    result = await db.execute(
        select(Exercise.primary_muscle, TrainingSet.is_warmup)
        .join(TrainingSet, TrainingSet.exercise_id == Exercise.id)
        .join(TrainingSession, TrainingSet.session_id == TrainingSession.id)
        .where(
            and_(
                TrainingSession.user_id == user.id,
                TrainingSession.session_date >= monday,
                TrainingSession.session_date <= sunday,
            )
        )
    )
    counts: dict[str, int] = {}
    for muscle, is_warmup in result.all():
        if is_warmup or not muscle:
            continue
        counts[muscle] = counts.get(muscle, 0) + 1

    rows = []
    for muscle, landmarks in _VOLUME_LANDMARKS.items():
        mev, mav, mrv = landmarks
        rows.append({
            "muscle": muscle,
            "sets": counts.get(muscle, 0),
            "mev": mev,
            "mav": mav,
            "mrv": mrv,
        })
    # Sort by muscle name alphabetically for a stable layout
    rows.sort(key=lambda r: r["muscle"])
    return {
        "week_start": str(monday),
        "week_end": str(sunday),
        "rows": rows,
    }


# ---------------------------------------------------------------------------
# Generate program — update to use auto-split + stale baseline flag
# ---------------------------------------------------------------------------
