import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.profile import UserProfile
from app.models.training import (
    TrainingProgram, TrainingSession, TrainingSet,
    HRVLog, ARILog, Exercise,
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
    result = await db.execute(
        select(ARILog).where(ARILog.user_id == user.id)
        .order_by(desc(ARILog.recorded_date), desc(ARILog.created_at)).limit(1)
    )
    ari = result.scalar_one_or_none()
    if ari:
        from app.engines.engine2.ari import get_ari_zone
        return {
            "ari_score": ari.ari_score,
            "zone": get_ari_zone(ari.ari_score),
            "components": {
                "hrv": ari.hrv_component,
                "sleep": ari.sleep_component,
                "soreness": ari.soreness_component,
            },
        }

    # Fall back to computing from latest HRV
    hrv_result = await db.execute(
        select(HRVLog).where(HRVLog.user_id == user.id)
        .order_by(desc(HRVLog.recorded_date), desc(HRVLog.created_at)).limit(1)
    )
    hrv = hrv_result.scalar_one_or_none()
    if not hrv:
        raise HTTPException(status_code=404, detail="No HRV data available")

    baseline_result = await db.execute(
        select(HRVLog).where(HRVLog.user_id == user.id)
        .order_by(desc(HRVLog.recorded_date), desc(HRVLog.created_at)).limit(14)
    )
    hrv_history = baseline_result.scalars().all()
    baseline_rmssd = sum(h.rmssd for h in hrv_history) / len(hrv_history)

    from app.engines.engine2.ari import compute_ari, get_ari_zone
    soreness = getattr(hrv, "soreness_score", None) or 5.0
    ari_score = compute_ari(
        rmssd=hrv.rmssd,
        resting_hr=hrv.resting_hr or 60,
        sleep_quality_1_10=hrv.sleep_quality or 7,
        soreness_1_10=soreness,
        baseline_rmssd=baseline_rmssd,
    )
    return {"ari_score": ari_score, "zone": get_ari_zone(ari_score)}


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

    # Gap-driven volume: bigger gap → closer to MRV
    from app.engines.engine2.periodization import VOLUME_LANDMARKS
    volume_allocation: dict[str, int] = {}
    for muscle in DEFAULT_VOLUME:
        gap = muscle_gaps.get(muscle, 3.0)
        mev, _mav, mrv = VOLUME_LANDMARKS.get(muscle, (6, 12, 20))
        gap_norm = min(1.0, max(0.0, gap / 10.0))
        volume_allocation[muscle] = round(mev + gap_norm * (mrv - mev))

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
    mesocycle_weeks = max(4, phase_config.get("recommended_meso_weeks", 4))

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

            from app.engines.engine2.periodization import VOLUME_LANDMARKS
            for muscle in volume_allocation:
                gap = muscle_gaps.get(muscle, 3.0)
                mev, _mav, mrv = VOLUME_LANDMARKS.get(muscle, (6, 12, 20))
                gap_norm = min(1.0, max(0.0, gap / 10.0))
                volume_allocation[muscle] = round(mev + gap_norm * (mrv - mev))
    except Exception:
        pass

    # Deactivate old programs
    old_result = await db.execute(
        select(TrainingProgram).where(
            TrainingProgram.user_id == user.id, TrainingProgram.is_active == True
        )
    )
    for old in old_result.scalars().all():
        old.is_active = False

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

    sessions_created = await generate_program_sessions(
        db=db,
        user_id=user.id,
        program=program,
        volume_allocation=volume_allocation,
        start_date=date.today(),
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
        # Fall back to any session on that date
        result = await db.execute(
            select(TrainingSession)
            .where(
                TrainingSession.user_id == user.id,
                TrainingSession.session_date == resolved,
            )
            .order_by(desc(TrainingSession.created_at))
            .limit(1)
        )
        session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="No session for this date")

    sets_result = await db.execute(
        select(TrainingSet, Exercise.name, Exercise.primary_muscle)
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

    sets = []
    for ts, name, muscle in sets_rows:
        key = f"{name}_{ts.set_number}"
        ghost = prev_actuals.get(key, {})
        sets.append({
            "id": str(ts.id),
            "exercise_name": name,
            "muscle_group": muscle,
            "set_number": ts.set_number,
            "prescribed_reps": ts.prescribed_reps,
            "prescribed_weight_kg": ts.prescribed_weight_kg,
            "actual_reps": ts.actual_reps,
            "actual_weight_kg": ts.actual_weight_kg,
            "rpe": ts.rpe,
            "is_warmup": ts.is_warmup,
            "last_actual_reps": ghost.get("last_actual_reps"),
            "last_actual_weight_kg": ghost.get("last_actual_weight_kg"),
        })

    return {
        "id": str(session.id),
        "session_type": session.session_type,
        "session_date": str(session.session_date),
        "week_number": session.week_number,
        "day_number": session.day_number,
        "completed": session.completed,
        "stale_baselines": session.stale_baselines,
        "split_type": session.split_type,
        "sets": sets,
    }


class SetLog(BaseModel):
    set_id: str
    actual_reps: int | None = None
    actual_weight_kg: float | None = None
    rpe: float | None = None


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
# Generate program — update to use auto-split + stale baseline flag
# ---------------------------------------------------------------------------
