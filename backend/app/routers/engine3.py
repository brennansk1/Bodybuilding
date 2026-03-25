from __future__ import annotations

import uuid
from datetime import date as date_cls, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.profile import UserProfile
from app.models.measurement import BodyWeightLog, SkinfoldMeasurement, TapeMeasurement
from app.models.nutrition import (
    NutritionPrescription, AdherenceLog, IngredientMaster, UserMeal, MealItem,
    MealPlanTemplate, PreworkoutLog,
)
from app.models.training import ARILog
from app.models.diagnostic import HQILog, PDSLog

from app.engines.engine3.macros import (
    compute_tdee, compute_macros,
    compute_training_rest_day_macros,
    compute_peri_workout_carb_split,
    compute_division_nutrition_priorities,
)
from app.engines.engine1.body_fat import navy_body_fat, lean_mass_kg as calc_lean_mass
from app.services.diagnostic import _recommend_phase, get_latest_tape, get_latest_skinfold

router = APIRouter(prefix="/engine3", tags=["engine3-nutrition"])


# ---------------------------------------------------------------------------
# Prescription
# ---------------------------------------------------------------------------

@router.get("/prescription/current")
async def get_current_prescription(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(NutritionPrescription)
        .where(NutritionPrescription.user_id == user.id, NutritionPrescription.is_active == True)
        .order_by(desc(NutritionPrescription.created_at))
        .limit(1)
    )
    rx = result.scalar_one_or_none()
    if not rx:
        # Generate initial prescription from profile + latest weight
        profile_result = await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))
        profile = profile_result.scalar_one_or_none()
        if not profile:
            raise HTTPException(status_code=404, detail="Complete onboarding first")

        bw_result = await db.execute(
            select(BodyWeightLog).where(BodyWeightLog.user_id == user.id)
            .order_by(desc(BodyWeightLog.recorded_date), desc(BodyWeightLog.created_at)).limit(1)
        )
        bw = bw_result.scalar_one_or_none()
        if not bw:
            raise HTTPException(status_code=404, detail="No body weight data")

        from app.engines.engine3.macros import compute_tdee, compute_macros
        from app.engines.engine1.body_fat import navy_body_fat, lean_mass_kg as calc_lean_mass
        from app.services.diagnostic import _recommend_phase, get_latest_tape, get_latest_skinfold
        from app.models.diagnostic import HQILog, PDSLog

        # Get recommendation context
        hqi_res = await db.execute(select(HQILog).where(HQILog.user_id == user.id).order_by(desc(HQILog.recorded_date), desc(HQILog.created_at)).limit(1))
        hqi = hqi_res.scalar_one_or_none()
        pds_res = await db.execute(select(PDSLog).where(PDSLog.user_id == user.id).order_by(desc(PDSLog.recorded_date), desc(PDSLog.created_at)).limit(1))
        pds_val = pds_res.scalar_one_or_none()
        
        # Determine phase
        tape = await get_latest_tape(db, user.id)
        skinfold = await get_latest_skinfold(db, user.id)
        bf_pct = skinfold.body_fat_pct if skinfold else None
        if bf_pct is None and tape and tape.waist and tape.neck:
            try:
                bf_pct = navy_body_fat(tape.waist, tape.neck, profile.height_cm, profile.sex, tape.hips)
            except Exception:
                pass
            
        rec = _recommend_phase(
            muscle_gaps=hqi.site_scores if hqi else {},
            pds_score=pds_val.pds_score if pds_val else 50.0,
            body_fat_pct=bf_pct,
            sex=profile.sex,
            profile_prefs=profile.preferences,
            competition_date=profile.competition_date,
        )
        recommended_phase = rec["recommended_phase"]

        # User-override: if initial_phase is set in preferences, honor it
        initial_phase = (profile.preferences or {}).get("initial_phase")
        if initial_phase and initial_phase.strip():
            recommended_phase = initial_phase.strip().lower()

        # Compute lean mass BEFORE TDEE so Katch-McArdle is used (more accurate
        # for muscular athletes than Mifflin-St Jeor fallback)
        lbm = None
        if bf_pct is not None:
            lbm = calc_lean_mass(bw.weight_kg, bf_pct)

        # PAL multiplier — conservative baseline; actual expenditure is
        # captured through weight trend feedback in the kinetic engine.
        # Starting conservatively prevents wasted weeks at fake deficits.
        training_days = (profile.preferences or {}).get("training_days_per_week", 4)
        if training_days <= 2:
            pal = 1.375   # light
        elif training_days <= 3:
            pal = 1.50    # moderate-light
        elif training_days <= 4:
            pal = 1.55    # moderate
        elif training_days == 5:
            pal = 1.60    # active
        else:
            pal = 1.675   # very active — 6+ days

        tdee = compute_tdee(
            weight_kg=bw.weight_kg,
            height_cm=profile.height_cm,
            age=profile.age or 25,
            sex=profile.sex,
            activity_multiplier=pal,
            lean_mass_kg=lbm,
        )
        macros = compute_macros(tdee, recommended_phase, bw.weight_kg, profile.sex, lean_mass_kg=lbm, body_fat_pct=bf_pct)

        rx = NutritionPrescription(
            user_id=user.id,
            tdee=tdee,
            target_calories=macros["target_calories"],
            protein_g=macros["protein_g"],
            carbs_g=macros["carbs_g"],
            fat_g=macros["fat_g"],
            phase=recommended_phase,
            is_active=True,
        )
        db.add(rx)
        await db.flush()

    # --- AUTO-SYNC Phase logic ---
    # If the current prescription phase is 'maintain' but Engine 1 suggests a bulk/cut,
    # and it was created as a default, we should sync it to match the recommendation.
    if rx.phase == "maintain" and profile:
        hqi_res = await db.execute(select(HQILog).where(HQILog.user_id == user.id).order_by(desc(HQILog.recorded_date), desc(HQILog.created_at)).limit(1))
        hqi = hqi_res.scalar_one_or_none()
        pds_res = await db.execute(select(PDSLog).where(PDSLog.user_id == user.id).order_by(desc(PDSLog.recorded_date), desc(PDSLog.created_at)).limit(1))
        pds_val = pds_res.scalar_one_or_none()
        
        tape = await get_latest_tape(db, user.id)
        skinfold = await get_latest_skinfold(db, user.id)
        bf_pct = skinfold.body_fat_pct if skinfold else None
        if bf_pct is None and tape and tape.waist and tape.neck:
            try: bf_pct = navy_body_fat(tape.waist, tape.neck, profile.height_cm, profile.sex, tape.hips)
            except Exception:
                pass

        rec = _recommend_phase(
            muscle_gaps=hqi.site_scores if hqi else {},
            pds_score=pds_val.pds_score if pds_val else 50.0,
            body_fat_pct=bf_pct,
            sex=profile.sex,
            profile_prefs=profile.preferences,
            competition_date=profile.competition_date,
        )
        new_phase = rec["recommended_phase"]
        
        if new_phase != rx.phase:
            bw_res = await db.execute(select(BodyWeightLog).where(BodyWeightLog.user_id == user.id).order_by(desc(BodyWeightLog.recorded_date)).limit(1))
            bw_val = bw_res.scalar_one_or_none()
            curr_weight = bw_val.weight_kg if bw_val else 80.0

            new_macros = compute_macros(rx.tdee, new_phase, curr_weight, profile.sex, body_fat_pct=bf_pct)
            
            rx.target_calories = new_macros["target_calories"]
            rx.protein_g = new_macros["protein_g"]
            rx.carbs_g = new_macros["carbs_g"]
            rx.fat_g = new_macros["fat_g"]
            rx.phase = new_phase
            await db.flush()

    from app.engines.engine3.macros import (
        compute_training_rest_day_macros,
        compute_peri_workout_carb_split,
        compute_division_nutrition_priorities,
    )
    base_macros = {
        "protein_g": rx.protein_g,
        "carbs_g": rx.carbs_g,
        "fat_g": rx.fat_g,
        "target_calories": rx.target_calories,
    }

    bw_result2 = await db.execute(
        select(BodyWeightLog).where(BodyWeightLog.user_id == user.id)
        .order_by(desc(BodyWeightLog.recorded_date), desc(BodyWeightLog.created_at)).limit(1)
    )
    bw2 = bw_result2.scalar_one_or_none()
    weight_kg = bw2.weight_kg if bw2 else 80.0

    # Load profile for division-specific nutrition priorities
    profile_result = await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))
    rx_profile = profile_result.scalar_one_or_none()
    division = getattr(rx_profile, "division", "mens_open") or "mens_open"
    phase = rx.phase or "maintain"

    # Division-specific carb cycling factor overrides the default ±20%
    div_nutrition = compute_division_nutrition_priorities(division, phase)
    cycling_factor = div_nutrition["carb_cycling_factor"]

    # Recompute training/rest day macros with division-specific carb swing
    train_carbs = round(base_macros["carbs_g"] * (1.0 + cycling_factor), 1)
    rest_carbs = round(base_macros["carbs_g"] * (1.0 - cycling_factor), 1)
    fat_floor = round(div_nutrition["fat_per_kg_floor"] * weight_kg, 1)

    from app.engines.engine3.macros import _KCAL_PER_G_CARB, _KCAL_PER_G_FAT
    extra_kcal = (train_carbs - base_macros["carbs_g"]) * _KCAL_PER_G_CARB
    train_fat = round(max(fat_floor, base_macros["fat_g"] - extra_kcal / _KCAL_PER_G_FAT), 1)
    saved_kcal = (base_macros["carbs_g"] - rest_carbs) * _KCAL_PER_G_CARB
    rest_fat = round(base_macros["fat_g"] + saved_kcal / _KCAL_PER_G_FAT, 1)

    train_kcal = round(base_macros["protein_g"] * 4 + train_carbs * 4 + train_fat * 9, 0)
    rest_kcal  = round(base_macros["protein_g"] * 4 + rest_carbs  * 4 + rest_fat  * 9, 0)
    cycling = {
        "training_day": {
            "protein_g": base_macros["protein_g"],
            "carbs_g": train_carbs,
            "fat_g": train_fat,
            "calories": train_kcal,
            "target_calories": train_kcal,
        },
        "rest_day": {
            "protein_g": base_macros["protein_g"],
            "carbs_g": rest_carbs,
            "fat_g": rest_fat,
            "calories": rest_kcal,
            "target_calories": rest_kcal,
        },
    }
    peri_train = compute_peri_workout_carb_split(train_carbs, div_nutrition["meal_frequency_target"])
    peri_rest = compute_peri_workout_carb_split(rest_carbs, div_nutrition["meal_frequency_target"])

    # Alias with field names the frontend expects
    peri_timing_alias = {
        "training": {
            "pre_workout_carbs_g": peri_train["pre_workout_g"],
            "intra_workout_carbs_g": peri_train["intra_workout_g"],
            "post_workout_carbs_g": peri_train["post_workout_g"],
            "other_carbs_g": peri_train["other_meals_g"],
        },
        "rest": {
            "pre_workout_carbs_g": peri_rest["pre_workout_g"],
            "intra_workout_carbs_g": peri_rest["intra_workout_g"],
            "post_workout_carbs_g": peri_rest["post_workout_g"],
            "other_carbs_g": peri_rest["other_meals_g"],
        }
    }

    return {
        "tdee": rx.tdee,
        "target_calories": rx.target_calories,
        "protein_g": rx.protein_g,
        "carbs_g": rx.carbs_g,
        "fat_g": rx.fat_g,
        "peri_workout_carb_pct": rx.peri_workout_carb_pct,
        "phase": rx.phase,
        "training_day_macros": cycling["training_day"],
        "rest_day_macros": cycling["rest_day"],
        "peri_workout_timing": peri_timing_alias,
        "division_nutrition": {
            "carb_cycling_factor": cycling_factor,
            "meal_frequency_target": div_nutrition["meal_frequency_target"],
            "mps_threshold_g": div_nutrition["mps_threshold_g"],
            "notes": div_nutrition["notes"],
        },
    }


# ---------------------------------------------------------------------------
# Peak week
# ---------------------------------------------------------------------------

@router.get("/peak-week")
async def get_peak_week(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    profile_result = await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))
    profile = profile_result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Complete onboarding first")

    competition_date = profile.competition_date
    if not competition_date:
        raise HTTPException(status_code=400, detail="No competition date set in profile")

    today = date_cls.today()
    days_out = (competition_date - today).days
    if days_out > 21:
        raise HTTPException(status_code=400, detail=f"Peak week protocol activates within 21 days of competition ({days_out} days out)")

    bw_result = await db.execute(
        select(BodyWeightLog).where(BodyWeightLog.user_id == user.id)
        .order_by(desc(BodyWeightLog.recorded_date), desc(BodyWeightLog.created_at)).limit(1)
    )
    bw = bw_result.scalar_one_or_none()
    if not bw:
        raise HTTPException(status_code=404, detail="No body weight data")

    sf_result = await db.execute(
        select(SkinfoldMeasurement).where(SkinfoldMeasurement.user_id == user.id)
        .order_by(desc(SkinfoldMeasurement.recorded_date), desc(SkinfoldMeasurement.created_at)).limit(1)
    )
    sf = sf_result.scalar_one_or_none()

    from app.engines.engine3.peak_week import compute_peak_week_protocol
    from app.engines.engine1.body_fat import lean_mass_kg

    if sf and sf.body_fat_pct:
        lbm = lean_mass_kg(bw.weight_kg, sf.body_fat_pct)
    else:
        lbm = bw.weight_kg * 0.85

    protocol = compute_peak_week_protocol(lean_mass_kg=lbm, show_date=competition_date)

    return {
        "protocol": protocol,
        "show_date": str(competition_date),
        "days_out": days_out,
    }


# ---------------------------------------------------------------------------
# Adherence
# ---------------------------------------------------------------------------

@router.get("/adherence")
async def get_adherence_history(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AdherenceLog).where(AdherenceLog.user_id == user.id)
        .order_by(desc(AdherenceLog.recorded_date), desc(AdherenceLog.created_at)).limit(12)
    )
    logs = result.scalars().all()
    return [
        {
            "date": str(log.recorded_date),
            "nutrition": log.nutrition_adherence_pct,
            "training": log.training_adherence_pct,
            "overall": log.overall_adherence_pct,
        }
        for log in reversed(logs)
    ]


# ---------------------------------------------------------------------------
# Autoregulation
# ---------------------------------------------------------------------------

@router.post("/autoregulation")
async def run_autoregulation(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rx_result = await db.execute(
        select(NutritionPrescription)
        .where(NutritionPrescription.user_id == user.id, NutritionPrescription.is_active == True)
        .order_by(desc(NutritionPrescription.created_at))
        .limit(1)
    )
    rx = rx_result.scalar_one_or_none()
    if not rx:
        raise HTTPException(status_code=404, detail="No active prescription")

    adh_result = await db.execute(
        select(AdherenceLog).where(AdherenceLog.user_id == user.id)
        .order_by(desc(AdherenceLog.recorded_date), desc(AdherenceLog.created_at)).limit(1)
    )
    adh = adh_result.scalar_one_or_none()

    # Load profile for sex and phase
    profile_result = await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))
    profile = profile_result.scalar_one_or_none()
    sex = getattr(profile, "sex", "male") or "male"
    phase = rx.phase or "maintain"

    # EWMA weight tracking — compute smoothed rate of change from last 28 days
    from app.engines.engine3.kinetic import compute_rate_of_change_detailed
    bw_result = await db.execute(
        select(BodyWeightLog).where(BodyWeightLog.user_id == user.id)
        .order_by(BodyWeightLog.recorded_date)
        .limit(28)
    )
    bw_logs = bw_result.scalars().all()
    ewma_rate = None
    trend_direction = "stable"
    if len(bw_logs) >= 2:
        weight_history = [(str(bw.recorded_date), bw.weight_kg) for bw in bw_logs]
        cycle_day = (profile.preferences or {}).get("current_cycle_day") if profile else None
        try:
            rate_detail = compute_rate_of_change_detailed(weight_history, sex=sex, cycle_day=cycle_day)
            ewma_rate = rate_detail["rate_kg_per_week"]
            trend_direction = rate_detail["trend_direction"]
        except (ValueError, Exception):
            pass

    # Metabolic adaptation — compute weeks in deficit from prescription creation date
    from app.engines.engine3.thermodynamic import compute_adapted_tdee
    adapted_tdee = rx.tdee
    weeks_in_deficit = 0.0
    if phase in ("cut", "peak_week") and rx.created_at:
        weeks_in_deficit = (date_cls.today() - rx.created_at.date()).days / 7.0
        if weeks_in_deficit > 0:
            adapted_tdee = compute_adapted_tdee(rx.tdee, weeks_in_deficit)

    # ARI-triggered refeed check — query last 5 days of ARI scores
    from app.engines.engine3.autoregulation import check_ari_triggered_refeed, adherence_lock
    five_days_ago = date_cls.today() - timedelta(days=5)
    ari_result = await db.execute(
        select(ARILog)
        .where(ARILog.user_id == user.id, ARILog.recorded_date >= five_days_ago)
        .order_by(ARILog.recorded_date)
    )
    recent_ari_logs = ari_result.scalars().all()
    refeed_check = None
    if recent_ari_logs:
        # Get current BF% for refeed threshold
        sf_result = await db.execute(
            select(SkinfoldMeasurement).where(SkinfoldMeasurement.user_id == user.id)
            .order_by(desc(SkinfoldMeasurement.recorded_date), desc(SkinfoldMeasurement.created_at)).limit(1)
        )
        sf = sf_result.scalar_one_or_none()
        current_bf_pct = sf.body_fat_pct if sf else 15.0
        try:
            refeed_check = check_ari_triggered_refeed(
                recent_ari_scores=[log.ari_score for log in recent_ari_logs],
                phase=phase,
                current_bf_pct=current_bf_pct,
                sex=sex,
            )
        except (ValueError, Exception):
            pass

    # Adherence lock — applies macro reduction at <85% adherence
    adherence_pct = adh.overall_adherence_pct if adh else 100.0
    base_macros = {
        "target_calories": rx.target_calories,
        "protein_g": rx.protein_g,
        "carbs_g": rx.carbs_g,
        "fat_g": rx.fat_g,
    }
    locked = adherence_lock(adherence_pct, base_macros)

    return {
        **locked,
        "metabolic_adaptation": {
            "weeks_in_deficit": round(weeks_in_deficit, 1),
            "adapted_tdee": adapted_tdee,
            "adaptation_active": weeks_in_deficit > 0 and phase in ("cut", "peak_week"),
        },
        "weight_trend": {
            "ewma_rate_kg_per_week": ewma_rate,
            "trend_direction": trend_direction,
        },
        "ari_refeed": refeed_check,
    }


# ---------------------------------------------------------------------------
# Restoration (post-show reverse diet)
# ---------------------------------------------------------------------------

@router.get("/prescription/restoration")
async def get_restoration_prescription(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns the post-show restoration (reverse diet) macro prescription.
    Activates when competition_date is in the past.
    """
    profile_result = await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))
    profile = profile_result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Complete onboarding first")

    competition_date = profile.competition_date
    if not competition_date or competition_date > date_cls.today():
        raise HTTPException(
            status_code=400,
            detail="Restoration phase requires a past competition date. Set your show date in profile."
        )

    weeks_post_show = (date_cls.today() - competition_date).days // 7
    if weeks_post_show < 1:
        weeks_post_show = 1

    # Get current weight and TDEE baseline
    bw_result = await db.execute(
        select(BodyWeightLog).where(BodyWeightLog.user_id == user.id)
        .order_by(desc(BodyWeightLog.recorded_date), desc(BodyWeightLog.created_at)).limit(1)
    )
    bw = bw_result.scalar_one_or_none()
    if not bw:
        raise HTTPException(status_code=404, detail="No body weight data")

    # Use TDEE from active prescription, or compute fresh
    rx_result = await db.execute(
        select(NutritionPrescription)
        .where(NutritionPrescription.user_id == user.id, NutritionPrescription.is_active == True)
        .order_by(desc(NutritionPrescription.created_at)).limit(1)
    )
    rx = rx_result.scalar_one_or_none()
    base_tdee = rx.tdee if rx else 2200.0

    from app.engines.engine3.macros import compute_restoration_macros
    sex = getattr(profile, "sex", "male") or "male"
    restoration = compute_restoration_macros(
        base_tdee=base_tdee,
        weight_kg=bw.weight_kg,
        sex=sex,
        weeks_post_show=weeks_post_show,
    )

    return {
        "phase": "restoration",
        "weeks_post_show": weeks_post_show,
        "competition_date": str(competition_date),
        **restoration,
    }


# ---------------------------------------------------------------------------
# Reactive peak week adjustment
# ---------------------------------------------------------------------------

class PeakWeekConditionInput(BaseModel):
    condition: str = Field(description="Visual state: flat, spilled, or peaked")
    day_index: int = Field(ge=0, le=6, description="Day index in the 7-day protocol (0=Monday)")


@router.post("/peak-week/adjust")
async def adjust_peak_week_day(
    data: PeakWeekConditionInput,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Reactively adjust a peak week day based on morning visual check-in."""
    profile_result = await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))
    profile = profile_result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Complete onboarding first")

    competition_date = profile.competition_date
    if not competition_date:
        raise HTTPException(status_code=400, detail="No competition date set")

    bw_result = await db.execute(
        select(BodyWeightLog).where(BodyWeightLog.user_id == user.id)
        .order_by(desc(BodyWeightLog.recorded_date)).limit(1)
    )
    bw = bw_result.scalar_one_or_none()
    if not bw:
        raise HTTPException(status_code=404, detail="No body weight data")

    from app.engines.engine3.peak_week import compute_peak_week_protocol, adjust_peak_day_for_condition
    from app.engines.engine1.body_fat import lean_mass_kg

    sf_result = await db.execute(
        select(SkinfoldMeasurement).where(SkinfoldMeasurement.user_id == user.id)
        .order_by(desc(SkinfoldMeasurement.recorded_date)).limit(1)
    )
    sf = sf_result.scalar_one_or_none()
    lbm = lean_mass_kg(bw.weight_kg, sf.body_fat_pct) if sf and sf.body_fat_pct else bw.weight_kg * 0.85
    division = getattr(profile, "division", "mens_open") or "mens_open"

    protocol = compute_peak_week_protocol(lean_mass_kg=lbm, show_date=competition_date, division=division)

    if data.day_index >= len(protocol):
        raise HTTPException(status_code=400, detail="Day index out of range")

    original = protocol[data.day_index]
    adjusted = adjust_peak_day_for_condition(original, data.condition)

    return {
        "original": original,
        "adjusted": adjusted,
        "condition": data.condition,
        "day": original["day"],
    }


# ---------------------------------------------------------------------------
# Pre-workout supplement logging
# ---------------------------------------------------------------------------

class PreworkoutLogCreate(BaseModel):
    brand: str | None = None
    caffeine_mg: float | None = Field(default=None, ge=0, le=1000)
    citrulline_mg: float | None = Field(default=None, ge=0, le=20000)
    beta_alanine_mg: float | None = Field(default=None, ge=0, le=10000)
    creatine_mg: float | None = Field(default=None, ge=0, le=10000)
    calories: float | None = Field(default=None, ge=0, le=2000)
    protein_g: float | None = Field(default=None, ge=0, le=100)
    carbs_g: float | None = Field(default=None, ge=0, le=200)


@router.post("/preworkout/log")
async def log_preworkout(
    data: PreworkoutLogCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    today = date_cls.today()
    # Upsert: one log per day
    existing = await db.execute(
        select(PreworkoutLog)
        .where(PreworkoutLog.user_id == user.id, PreworkoutLog.recorded_date == today)
        .limit(1)
    )
    log = existing.scalar_one_or_none()
    if log:
        for field in ("brand", "caffeine_mg", "citrulline_mg", "beta_alanine_mg", "creatine_mg", "calories", "protein_g", "carbs_g"):
            val = getattr(data, field)
            if val is not None:
                setattr(log, field, val)
    else:
        log = PreworkoutLog(
            user_id=user.id,
            recorded_date=today,
            brand=data.brand,
            caffeine_mg=data.caffeine_mg,
            citrulline_mg=data.citrulline_mg,
            beta_alanine_mg=data.beta_alanine_mg,
            creatine_mg=data.creatine_mg,
            calories=data.calories,
            protein_g=data.protein_g,
            carbs_g=data.carbs_g,
        )
        db.add(log)
    await db.flush()
    return {"message": "Pre-workout logged", "date": str(today)}


@router.get("/preworkout/today")
async def get_preworkout_today(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    today = date_cls.today()
    result = await db.execute(
        select(PreworkoutLog)
        .where(PreworkoutLog.user_id == user.id, PreworkoutLog.recorded_date == today)
        .limit(1)
    )
    log = result.scalar_one_or_none()
    if not log:
        return None
    return {
        "brand": log.brand,
        "caffeine_mg": log.caffeine_mg,
        "citrulline_mg": log.citrulline_mg,
        "beta_alanine_mg": log.beta_alanine_mg,
        "creatine_mg": log.creatine_mg,
        "calories": log.calories,
        "protein_g": log.protein_g,
        "carbs_g": log.carbs_g,
        "date": str(log.recorded_date),
    }


# ---------------------------------------------------------------------------
# GI distress check
# ---------------------------------------------------------------------------

class GIDistressInput(BaseModel):
    gi_distress_index: int = Field(ge=1, le=10, description="Self-reported GI distress 1-10")


@router.post("/gi-distress")
async def check_gi_distress_route(
    data: GIDistressInput,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Evaluate GI distress and return food source swap recommendations."""
    profile_result = await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))
    profile = profile_result.scalar_one_or_none()
    division = getattr(profile, "division", "mens_open") or "mens_open"

    from app.engines.engine3.autoregulation import check_gi_distress
    result = check_gi_distress(
        gi_distress_index=data.gi_distress_index,
        division=division,
    )
    return result


# ---------------------------------------------------------------------------
# Engine 4 — Cardio & NEAT
# ---------------------------------------------------------------------------

@router.get("/cardio/prescription")
async def get_cardio_prescription(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get phase-appropriate cardio and NEAT prescription."""
    profile_result = await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))
    profile = profile_result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Complete onboarding first")

    # Determine current phase
    from app.engines.engine1.prep_timeline import prep_phase_for_date
    phase = prep_phase_for_date(profile.competition_date)

    # Get current weight
    bw_result = await db.execute(
        select(BodyWeightLog).where(BodyWeightLog.user_id == user.id)
        .order_by(desc(BodyWeightLog.recorded_date)).limit(1)
    )
    bw = bw_result.scalar_one_or_none()
    weight_kg = bw.weight_kg if bw else 80.0
    sex = getattr(profile, "sex", "male") or "male"

    # Get current prescription for calorie context
    rx_result = await db.execute(
        select(NutritionPrescription)
        .where(NutritionPrescription.user_id == user.id, NutritionPrescription.is_active == True)
        .order_by(desc(NutritionPrescription.created_at)).limit(1)
    )
    rx = rx_result.scalar_one_or_none()
    current_calories = rx.target_calories if rx else 2500.0

    # Check for weight stall (EWMA rate < 0.1 kg/week for cut phases)
    weight_stall = False
    from app.engines.engine3.kinetic import compute_rate_of_change_detailed
    bw_logs_result = await db.execute(
        select(BodyWeightLog).where(BodyWeightLog.user_id == user.id)
        .order_by(BodyWeightLog.recorded_date).limit(28)
    )
    bw_logs = bw_logs_result.scalars().all()
    if len(bw_logs) >= 7 and phase in ("cut", "peak"):
        weight_history = [(str(b.recorded_date), b.weight_kg) for b in bw_logs]
        try:
            rate_detail = compute_rate_of_change_detailed(weight_history, sex=sex)
            if abs(rate_detail["rate_kg_per_week"]) < 0.1:
                weight_stall = True
        except Exception:
            pass

    # Get average ARI for recovery-aware cardio adjustment
    avg_ari = None
    seven_days_ago = date_cls.today() - timedelta(days=7)
    ari_result = await db.execute(
        select(ARILog).where(ARILog.user_id == user.id, ARILog.recorded_date >= seven_days_ago)
    )
    recent_ari = ari_result.scalars().all()
    if recent_ari:
        avg_ari = sum(a.ari_score for a in recent_ari) / len(recent_ari)

    # Weeks in phase
    weeks_in_phase = 0
    if rx and rx.created_at:
        weeks_in_phase = max(0, (date_cls.today() - rx.created_at.date()).days // 7)

    from app.engines.engine4.cardio import compute_total_expenditure_plan
    plan = compute_total_expenditure_plan(
        phase=phase,
        weight_kg=weight_kg,
        sex=sex,
        current_calories=current_calories,
        target_deficit=400 if phase in ("cut", "peak") else 0,
        weeks_in_phase=weeks_in_phase,
        avg_ari=avg_ari,
        weight_stall=weight_stall,
    )

    return plan


# ---------------------------------------------------------------------------
# Meal plan
# ---------------------------------------------------------------------------

async def _build_meal_plan_for_day(
    db: AsyncSession,
    user: "User",
    profile: "UserProfile",
    rx: "NutritionPrescription",
    day_type: str,  # "training" or "rest"
) -> list[dict]:
    """Build a meal plan using curated bodybuilding food database."""
    from app.engines.engine3.meal_planner import generate_meal_plan
    from app.engines.engine3.macros import compute_division_nutrition_priorities

    division = getattr(profile, "division", "mens_open") or "mens_open"
    phase = rx.phase or "maintain"
    prefs = profile.preferences or {}
    meal_count = prefs.get("meal_count", 5)
    training_start_time = getattr(profile, "training_start_time", None) or "10:00"
    training_duration_min = getattr(profile, "training_duration_min", None) or 75
    dietary_restrictions = prefs.get("dietary_restrictions", [])

    div_nutrition = compute_division_nutrition_priorities(division, phase)
    cycling_factor = div_nutrition["carb_cycling_factor"]
    is_training = day_type == "training"
    carbs_g = round(rx.carbs_g * (1.0 + cycling_factor if is_training else 1.0 - cycling_factor), 1)
    fat_floor = round(div_nutrition["fat_per_kg_floor"] * 80.0, 1)
    fat_g = max(fat_floor, rx.fat_g)

    return generate_meal_plan(
        phase=phase,
        division=division,
        meal_count=meal_count,
        protein_g=rx.protein_g,
        carbs_g=carbs_g,
        fat_g=fat_g,
        target_calories=rx.target_calories,
        training_start_time=training_start_time,
        training_duration_min=int(training_duration_min),
        is_training_day=is_training,
        is_refeed=False,
        dietary_restrictions=dietary_restrictions,
    )


@router.get("/meal-plan/current")
async def get_current_meal_plan(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return (or generate) training-day and rest-day meal plans for the current prescription."""
    profile_result = await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))
    profile = profile_result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Complete onboarding first")

    rx_result = await db.execute(
        select(NutritionPrescription)
        .where(NutritionPrescription.user_id == user.id, NutritionPrescription.is_active == True)
        .order_by(desc(NutritionPrescription.created_at)).limit(1)
    )
    rx = rx_result.scalar_one_or_none()
    if not rx:
        raise HTTPException(status_code=404, detail="No active nutrition prescription. Complete a check-in first.")

    # Check for cached templates for this phase
    cached: dict[str, list] = {}
    for day_type in ("training", "rest"):
        tpl_result = await db.execute(
            select(MealPlanTemplate)
            .where(
                MealPlanTemplate.user_id == user.id,
                MealPlanTemplate.phase == rx.phase,
                MealPlanTemplate.day_type == day_type,
            )
            .order_by(desc(MealPlanTemplate.created_at)).limit(1)
        )
        tpl = tpl_result.scalar_one_or_none()
        if tpl:
            cached[day_type] = tpl.meals_json

    if "training" not in cached:
        cached["training"] = await _build_meal_plan_for_day(db, user, profile, rx, "training")
        db.add(MealPlanTemplate(
            user_id=user.id, day_type="training", phase=rx.phase, meals_json=cached["training"]
        ))
    if "rest" not in cached:
        cached["rest"] = await _build_meal_plan_for_day(db, user, profile, rx, "rest")
        db.add(MealPlanTemplate(
            user_id=user.id, day_type="rest", phase=rx.phase, meals_json=cached["rest"]
        ))

    await db.flush()
    return {
        "phase": rx.phase,
        "training_day": cached["training"],
        "rest_day": cached["rest"],
    }


@router.post("/meal-plan/generate")
async def generate_meal_plan_endpoint(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Force-regenerate meal plans, replacing cached templates."""
    profile_result = await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))
    profile = profile_result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Complete onboarding first")

    rx_result = await db.execute(
        select(NutritionPrescription)
        .where(NutritionPrescription.user_id == user.id, NutritionPrescription.is_active == True)
        .order_by(desc(NutritionPrescription.created_at)).limit(1)
    )
    rx = rx_result.scalar_one_or_none()
    if not rx:
        raise HTTPException(status_code=404, detail="No active nutrition prescription")

    plans: dict[str, list] = {}
    for day_type in ("training", "rest"):
        plans[day_type] = await _build_meal_plan_for_day(db, user, profile, rx, day_type)
        db.add(MealPlanTemplate(
            user_id=user.id, day_type=day_type, phase=rx.phase, meals_json=plans[day_type]
        ))

    await db.flush()
    return {
        "phase": rx.phase,
        "training_day": plans["training"],
        "rest_day": plans["rest"],
        "regenerated": True,
    }


# ---------------------------------------------------------------------------
# Ingredient search
# ---------------------------------------------------------------------------

@router.get("/ingredients/search")
async def search_ingredients(
    q: str = "",
    category: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(IngredientMaster)
    if q:
        query = query.where(IngredientMaster.name.ilike(f"%{q}%"))
    if category:
        query = query.where(IngredientMaster.category == category)
    query = query.order_by(IngredientMaster.protein_per_100g.desc()).limit(20)

    result = await db.execute(query)
    ingredients = result.scalars().all()
    return [
        {
            "id": str(i.id),
            "name": i.name,
            "category": i.category,
            "calories_per_100g": i.calories_per_100g,
            "protein_per_100g": i.protein_per_100g,
            "carbs_per_100g": i.carbs_per_100g,
            "fat_per_100g": i.fat_per_100g,
            "fiber_per_100g": i.fiber_per_100g,
            "is_peri_workout": i.is_peri_workout,
        }
        for i in ingredients
    ]


# ---------------------------------------------------------------------------
# Meal logging
# ---------------------------------------------------------------------------

class MealItemCreate(BaseModel):
    ingredient_id: str
    quantity_g: float = Field(gt=0, le=2000)


class MealCreate(BaseModel):
    meal_number: int = Field(ge=1, le=8)
    meal_type: str = "standard"  # standard / pre_workout / post_workout
    items: list[MealItemCreate]


def _macro_for_item(ingredient: IngredientMaster, quantity_g: float) -> dict:
    scale = quantity_g / 100.0
    return {
        "calories": round(ingredient.calories_per_100g * scale, 1),
        "protein_g": round(ingredient.protein_per_100g * scale, 1),
        "carbs_g": round(ingredient.carbs_per_100g * scale, 1),
        "fat_g": round(ingredient.fat_per_100g * scale, 1),
    }


@router.post("/meals")
async def log_meal(
    data: MealCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    today = date_cls.today()

    meal_type = data.meal_type if data.meal_type in ("standard", "pre_workout", "post_workout") else "standard"
    meal = UserMeal(
        user_id=user.id,
        meal_number=data.meal_number,
        meal_type=meal_type,
        recorded_date=today,
    )
    db.add(meal)
    await db.flush()

    total_cal = total_prot = total_carbs = total_fat = 0.0
    items_out = []

    for item_data in data.items:
        ing_result = await db.execute(
            select(IngredientMaster).where(
                IngredientMaster.id == uuid.UUID(item_data.ingredient_id)
            )
        )
        ingredient = ing_result.scalar_one_or_none()
        if not ingredient:
            continue

        meal_item = MealItem(
            meal_id=meal.id,
            ingredient_id=ingredient.id,
            quantity_g=item_data.quantity_g,
        )
        db.add(meal_item)

        macros = _macro_for_item(ingredient, item_data.quantity_g)
        total_cal += macros["calories"]
        total_prot += macros["protein_g"]
        total_carbs += macros["carbs_g"]
        total_fat += macros["fat_g"]

        items_out.append({
            "ingredient_name": ingredient.name,
            "quantity_g": item_data.quantity_g,
            **macros,
        })

    await db.flush()

    return {
        "id": str(meal.id),
        "meal_number": meal.meal_number,
        "meal_type": meal.meal_type,
        "items": items_out,
        "totals": {
            "calories": round(total_cal, 1),
            "protein_g": round(total_prot, 1),
            "carbs_g": round(total_carbs, 1),
            "fat_g": round(total_fat, 1),
        },
    }


@router.get("/meals/{meal_date}")
async def get_meals_for_date(
    meal_date: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        target_date = date_cls.fromisoformat(meal_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    result = await db.execute(
        select(UserMeal)
        .where(UserMeal.user_id == user.id, UserMeal.recorded_date == target_date)
        .order_by(UserMeal.meal_number)
    )
    meals = result.scalars().all()

    meals_out = []
    for meal in meals:
        items_result = await db.execute(
            select(MealItem, IngredientMaster)
            .join(IngredientMaster, MealItem.ingredient_id == IngredientMaster.id)
            .where(MealItem.meal_id == meal.id)
        )
        items = items_result.all()

        total_cal = total_prot = total_carbs = total_fat = 0.0
        items_out = []
        for mi, ing in items:
            macros = _macro_for_item(ing, mi.quantity_g)
            total_cal += macros["calories"]
            total_prot += macros["protein_g"]
            total_carbs += macros["carbs_g"]
            total_fat += macros["fat_g"]
            items_out.append({"ingredient_name": ing.name, "quantity_g": mi.quantity_g, **macros})

        meals_out.append({
            "id": str(meal.id),
            "meal_number": meal.meal_number,
            "meal_type": meal.meal_type,
            "items": items_out,
            "totals": {
                "calories": round(total_cal, 1),
                "protein_g": round(total_prot, 1),
                "carbs_g": round(total_carbs, 1),
                "fat_g": round(total_fat, 1),
            },
        })

    return meals_out


@router.get("/daily-totals/{meal_date}")
async def get_daily_totals(
    meal_date: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        target_date = date_cls.fromisoformat(meal_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    result = await db.execute(
        select(UserMeal)
        .where(UserMeal.user_id == user.id, UserMeal.recorded_date == target_date)
    )
    meals = result.scalars().all()

    MPS_THRESHOLD = 30
    total_cal = total_prot = total_carbs = total_fat = 0.0
    meal_protein_totals = []

    for meal in meals:
        items_result = await db.execute(
            select(MealItem, IngredientMaster)
            .join(IngredientMaster, MealItem.ingredient_id == IngredientMaster.id)
            .where(MealItem.meal_id == meal.id)
        )
        meal_prot = 0.0
        for mi, ing in items_result.all():
            macros = _macro_for_item(ing, mi.quantity_g)
            total_cal += macros["calories"]
            total_prot += macros["protein_g"]
            total_carbs += macros["carbs_g"]
            total_fat += macros["fat_g"]
            meal_prot += macros["protein_g"]
        meal_protein_totals.append(meal_prot)

    # MPS assessment
    mps_meals = sum(1 for p in meal_protein_totals if p >= MPS_THRESHOLD)
    total_meals = len(meal_protein_totals)
    mps_score = min(100, round((mps_meals / 4) * 100))

    if mps_meals == 0:
        mps_guidance = "No MPS-stimulating meals yet today. Aim for 30g+ protein per meal, 4 times."
    elif mps_meals < 3:
        mps_guidance = f"{mps_meals} MPS-stimulating meal(s) so far. Target 4 meals with 30g+ protein spread evenly."
    elif mps_meals == 3:
        mps_guidance = "Good — 3 MPS meals hit. One more high-protein meal to reach optimal stimulation."
    else:
        mps_guidance = "Excellent — 4+ MPS-stimulating meals. Protein distribution is optimal."

    # Compare against active prescription
    rx_result = await db.execute(
        select(NutritionPrescription)
        .where(NutritionPrescription.user_id == user.id, NutritionPrescription.is_active == True)
        .limit(1)
    )
    rx = rx_result.scalar_one_or_none()

    return {
        "date": meal_date,
        "total_calories": round(total_cal, 1),
        "total_protein_g": round(total_prot, 1),
        "total_carbs_g": round(total_carbs, 1),
        "total_fat_g": round(total_fat, 1),
        "target_calories": rx.target_calories if rx else None,
        "remaining_calories": round(rx.target_calories - total_cal, 1) if rx else None,
        "mps_assessment": {
            "mps_threshold_meals": mps_meals,
            "total_meals": total_meals,
            "score": mps_score,
            "guidance": mps_guidance,
        },
    }
