import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.profile import UserProfile
from app.models.measurement import BodyWeightLog, TapeMeasurement, SkinfoldMeasurement

logger = logging.getLogger(__name__)
from app.models.training import StrengthBaseline, Exercise
from app.engines.engine1.body_fat import jackson_pollock_7
from app.schemas.onboarding import (
    MeasurementsCreate,
    OnboardingCompleteResponse,
    PreferencesCreate,
    ProfileCreate,
    StrengthBaselinesCreate,
)

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.post("/profile")
async def create_profile(
    data: ProfileCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))
    profile = existing.scalar_one_or_none()

    if profile:
        # Upsert: update existing profile so re-running onboarding doesn't block
        profile.sex = data.sex
        profile.age = data.age
        profile.height_cm = data.height_cm
        profile.division = data.division
        profile.competition_date = data.competition_date
        profile.training_experience_years = data.training_experience_years
        profile.wrist_circumference_cm = data.wrist_circumference_cm
        profile.ankle_circumference_cm = data.ankle_circumference_cm
        if data.manual_body_fat_pct is not None:
            profile.manual_body_fat_pct = data.manual_body_fat_pct
        # Store current_phase in preferences JSONB
        if data.current_phase:
            prefs = profile.preferences or {}
            prefs["initial_phase"] = data.current_phase
            profile.preferences = prefs
    else:
        prefs = {}
        if data.current_phase:
            prefs["initial_phase"] = data.current_phase
        profile = UserProfile(
            user_id=user.id,
            sex=data.sex,
            age=data.age,
            height_cm=data.height_cm,
            division=data.division,
            competition_date=data.competition_date,
            training_experience_years=data.training_experience_years,
            wrist_circumference_cm=data.wrist_circumference_cm,
            ankle_circumference_cm=data.ankle_circumference_cm,
            manual_body_fat_pct=data.manual_body_fat_pct,
            preferences=prefs if prefs else None,
        )
        db.add(profile)

    await db.flush()
    return {"message": "Profile created", "step": 1}


@router.post("/measurements")
async def create_measurements(
    data: MeasurementsCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    today = date.today()

    bw = BodyWeightLog(user_id=user.id, weight_kg=data.body_weight_kg, recorded_date=today)
    db.add(bw)

    tape_fields = {
        "neck", "shoulders", "chest", "left_bicep", "right_bicep",
        "left_forearm", "right_forearm", "waist", "hips",
        "left_thigh", "right_thigh", "left_calf", "right_calf",
    }
    tape_data = {f: getattr(data, f) for f in tape_fields if getattr(data, f) is not None}
    if tape_data:
        tape = TapeMeasurement(user_id=user.id, recorded_date=today, **tape_data)
        db.add(tape)

    sf_map = {
        "sf_chest": "chest", "sf_midaxillary": "midaxillary", "sf_tricep": "tricep",
        "sf_subscapular": "subscapular", "sf_abdominal": "abdominal",
        "sf_suprailiac": "suprailiac", "sf_thigh": "thigh",
    }
    sf_data = {sf_map[f]: getattr(data, f) for f in sf_map if getattr(data, f) is not None}
    if sf_data:
        body_fat_pct = None
        if len(sf_data) == 7:
            profile_result = await db.execute(
                select(UserProfile).where(UserProfile.user_id == user.id)
            )
            profile = profile_result.scalar_one_or_none()
            if profile:
                body_fat_pct = jackson_pollock_7(
                    chest=sf_data["chest"],
                    midaxillary=sf_data["midaxillary"],
                    tricep=sf_data["tricep"],
                    subscapular=sf_data["subscapular"],
                    abdominal=sf_data["abdominal"],
                    suprailiac=sf_data["suprailiac"],
                    thigh=sf_data["thigh"],
                    age=profile.age or 25,
                    sex=profile.sex,
                )
        skinfold = SkinfoldMeasurement(
            user_id=user.id, recorded_date=today, body_fat_pct=body_fat_pct, **sf_data,
        )
        db.add(skinfold)

    await db.flush()
    return {"message": "Measurements recorded", "step": 2}


@router.post("/strength-baselines")
async def create_strength_baselines(
    data: StrengthBaselinesCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    today = date.today()
    for bl in data.baselines:
        result = await db.execute(select(Exercise).where(func.lower(Exercise.name) == bl.exercise_name.lower()))
        exercise = result.scalar_one_or_none()
        if not exercise:
            raise HTTPException(status_code=404, detail=f"Exercise not found: {bl.exercise_name}")

        baseline = StrengthBaseline(
            user_id=user.id,
            exercise_id=exercise.id,
            one_rm_kg=bl.one_rm_kg,
            recorded_date=today,
        )
        db.add(baseline)

    await db.flush()
    return {"message": "Strength baselines recorded", "step": 3}


@router.post("/preferences")
async def set_preferences(
    data: PreferencesCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=400, detail="Complete profile step first")

    prefs: dict = {
        "training_days_per_week": data.training_days_per_week,
        "preferred_split": data.preferred_split,
        "meal_count": data.meal_count,
        "dietary_restrictions": data.dietary_restrictions,
    }
    if data.display_name is not None:
        prefs["display_name"] = data.display_name
    if data.cardio_machine is not None:
        prefs["cardio_machine"] = data.cardio_machine
    if data.cheat_meals_per_week is not None:
        prefs["cheat_meals_per_week"] = data.cheat_meals_per_week
    if data.intra_workout_nutrition is not None:
        prefs["intra_workout_nutrition"] = data.intra_workout_nutrition
    # Food preferences — consumed by meal planner engine
    if data.preferred_proteins:
        prefs["preferred_proteins"] = data.preferred_proteins
    if data.preferred_carbs:
        prefs["preferred_carbs"] = data.preferred_carbs
    if data.preferred_fats:
        prefs["preferred_fats"] = data.preferred_fats
    if data.blacklisted_foods:
        prefs["blacklisted_foods"] = data.blacklisted_foods
    profile.preferences = prefs
    profile.training_start_time = data.training_start_time
    profile.training_duration_min = data.training_duration_min
    await db.flush()
    return {"message": "Preferences saved", "step": 4}


@router.get("/profile")
async def get_profile(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    prefs = profile.preferences or {}
    return {
        "sex": profile.sex,
        "age": profile.age,
        "height_cm": profile.height_cm,
        "division": profile.division,
        "competition_date": str(profile.competition_date) if profile.competition_date else None,
        "training_experience_years": profile.training_experience_years,
        "wrist_circumference_cm": profile.wrist_circumference_cm,
        "ankle_circumference_cm": profile.ankle_circumference_cm,
        "manual_body_fat_pct": profile.manual_body_fat_pct,
        "training_start_time": profile.training_start_time,
        "training_duration_min": profile.training_duration_min,
        "cycle_tracking_enabled": profile.cycle_tracking_enabled,
        "cycle_start_date": str(profile.cycle_start_date) if profile.cycle_start_date else None,
        "available_equipment": profile.available_equipment or [],
        "disliked_exercises": profile.disliked_exercises or [],
        "injury_history": profile.injury_history or [],
        "preferences": prefs,
        "display_name": prefs.get("display_name"),
    }


@router.patch("/profile")
async def update_profile(
    data: dict,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from datetime import date as date_type
    result = await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    allowed_fields = {
        "age", "sex", "height_cm", "division", "competition_date",
        "training_experience_years", "wrist_circumference_cm", "ankle_circumference_cm",
        "manual_body_fat_pct", "training_start_time", "training_duration_min",
        "cycle_tracking_enabled", "cycle_start_date",
    }
    list_fields = {"available_equipment", "disliked_exercises", "injury_history"}
    for field, value in data.items():
        if field in allowed_fields and value is not None:
            if field == "competition_date" and isinstance(value, str):
                from datetime import date as _d
                try:
                    value = _d.fromisoformat(value)
                except ValueError:
                    continue
            if field == "cycle_start_date" and isinstance(value, str):
                from datetime import date as _d
                try:
                    value = _d.fromisoformat(value)
                except ValueError:
                    continue
            setattr(profile, field, value)
        elif field in list_fields:
            if isinstance(value, list):
                setattr(profile, field, value)

    if "preferences" in data and isinstance(data["preferences"], dict):
        # Force a copy so SQLAlchemy detects change in JSONB column
        current = dict(profile.preferences or {})
        current.update(data["preferences"])
        profile.preferences = current
        logger.debug("Preferences updated for user %s", user.id)

    await db.flush()
    return {"message": "Profile updated"}


@router.post("/complete", response_model=OnboardingCompleteResponse)
async def complete_onboarding(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Verify profile exists
    result = await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=400, detail="Complete profile step first")

    user.onboarding_complete = True
    await db.flush()

    # Run initial Engine 1 diagnostic
    pds_score = None
    tier = None
    try:
        from app.services.diagnostic import run_full_diagnostic
        result = await run_full_diagnostic(db, user)
        pds_score = result["pds"]["score"]
        tier = result["pds"]["tier"]
    except ValueError:
        pass  # Missing measurements — diagnostics will run after first check-in

    return OnboardingCompleteResponse(
        message="Onboarding complete! Your initial Physique Development Score has been computed.",
        pds_score=pds_score,
        tier=tier,
    )
