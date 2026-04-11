from __future__ import annotations

import logging
import uuid
from datetime import date as date_cls, timedelta

logger = logging.getLogger(__name__)

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
            except (ValueError, ZeroDivisionError) as e:
                logger.warning("Navy BF failed in prescription init: %s", e)

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

        # Atomically deactivate any stale active rows (protects against the
        # race where two concurrent requests both find no active rx).
        from sqlalchemy import update as _update
        await db.execute(
            _update(NutritionPrescription)
            .where(
                NutritionPrescription.user_id == user.id,
                NutritionPrescription.is_active == True,
            )
            .values(is_active=False)
        )

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
            try:
                bf_pct = navy_body_fat(tape.waist, tape.neck, profile.height_cm, profile.sex, tape.hips)
            except (ValueError, ZeroDivisionError) as e:
                logger.warning("Navy BF failed in recalculate: %s", e)

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

    # Division-specific carb cycling factor overrides the default ±20%.
    # Pass BF% and sex so the cycling factor widens appropriately during
    # late-cut prep (see macros.compute_division_nutrition_priorities).
    latest_bf = getattr(rx_profile, "manual_body_fat_pct", None)
    sex = getattr(rx_profile, "sex", "male") or "male"
    div_nutrition = compute_division_nutrition_priorities(division, phase, body_fat_pct=latest_bf, sex=sex)
    cycling_factor = div_nutrition["carb_cycling_factor"]

    # Recompute coach warnings on the fly — they depend on current BF + phase,
    # and we want them to appear immediately even if the prescription row
    # was saved before the warnings feature existed.
    from app.engines.engine3.macros import compute_macros as _cm
    warning_payload: list[str] = []
    try:
        fresh_macros = _cm(rx.tdee, phase, weight_kg, sex, body_fat_pct=latest_bf)
        warning_payload = list(fresh_macros.get("coach_warnings") or [])
    except Exception:
        warning_payload = []

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
        "coach_warnings": warning_payload,
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
        except (ValueError, KeyError) as e:
            logger.warning("Rate-of-change computation failed: %s", e)

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

        # Pass the per-day ARI component breakdown so refeed logic can tell
        # whether the drop is HRV-driven (needs carbs) or stress-driven
        # (needs a rest day, not food).
        recent_components = [
            {
                "hrv": log.hrv_component,
                "sleep": log.sleep_component,
                "soreness": log.soreness_component,
                "hr": getattr(log, "hr_component", None) or 50,
                "wellness": getattr(log, "stress_component", None) or 50,
            }
            for log in recent_ari_logs
        ]

        # Resolve menstrual cycle phase for female athletes
        cycle_phase_name = None
        if getattr(profile, "sex", None) == "female" and getattr(profile, "cycle_tracking_enabled", False):
            from app.engines.engine2.ari import menstrual_phase
            cycle_info = menstrual_phase(getattr(profile, "cycle_start_date", None))
            if cycle_info:
                cycle_phase_name = cycle_info.get("phase")

        try:
            refeed_check = check_ari_triggered_refeed(
                recent_ari_scores=[log.ari_score for log in recent_ari_logs],
                phase=phase,
                current_bf_pct=current_bf_pct,
                sex=sex,
                recent_components=recent_components,
                cycle_phase=cycle_phase_name,
            )
            # Fire immediate Telegram alert if the refeed was triggered
            if refeed_check and refeed_check.get("ari_refeed_triggered"):
                try:
                    from app.services.notification_dispatcher import dispatch_refeed_triggered
                    await dispatch_refeed_triggered(db, profile, refeed_check)
                except Exception as exc:
                    logger.warning("Refeed trigger notification failed: %s", exc)
        except (ValueError, KeyError) as e:
            logger.warning("ARI-triggered refeed check failed: %s", e)

    # Adherence lock — applies macro reduction at <85% adherence
    adherence_pct = adh.overall_adherence_pct if adh else 100.0
    base_macros = {
        "target_calories": rx.target_calories,
        "protein_g": rx.protein_g,
        "carbs_g": rx.carbs_g,
        "fat_g": rx.fat_g,
    }
    locked = adherence_lock(adherence_pct, base_macros)

    # Energy Availability floor check — RED-S protection
    ea_check = None
    try:
        from app.engines.engine3.autoregulation import (
            check_energy_availability_floor,
            detect_metabolic_adaptation,
        )
        # Rough exercise kcal estimate: use 300 kcal/training session + NEAT.
        # A proper estimate would pull from the cardio prescription; this is
        # a pragmatic first pass.
        training_days = (profile.preferences or {}).get("training_days_per_week", 5) if profile else 5
        exercise_kcal = int(300 * training_days / 7)
        ffm_kg = None
        if sf_result and (sf := sf_result.scalar_one_or_none()):
            ffm_kg = sf.lean_mass_kg
        if not ffm_kg:
            from app.models.measurement import BodyWeightLog as _BW
            bw_q = await db.execute(
                select(_BW).where(_BW.user_id == user.id)
                .order_by(desc(_BW.recorded_date), desc(_BW.created_at)).limit(1)
            )
            latest_bw = bw_q.scalar_one_or_none()
            if latest_bw:
                # Assume 15% bf if unknown, so FFM = 0.85 × bw
                ffm_kg = latest_bw.weight_kg * 0.85
        if ffm_kg:
            ea_check = check_energy_availability_floor(
                target_calories=rx.target_calories,
                exercise_kcal_per_day=exercise_kcal,
                ffm_kg=ffm_kg,
                sex=sex,
            )
    except Exception as e:
        logger.warning("EA floor check failed: %s", e)

    # Metabolic adaptation detector — needs 4+ weeks of weight history
    adaptation_check = None
    if phase in ("cut", "peak_week"):
        try:
            bw_history_q = await db.execute(
                select(BodyWeightLog).where(BodyWeightLog.user_id == user.id)
                .order_by(BodyWeightLog.recorded_date).limit(60)
            )
            bw_history = [
                (row.recorded_date, row.weight_kg)
                for row in bw_history_q.scalars().all()
            ]
            expected_rate = -0.5 if phase == "cut" else -0.3  # kg/week defaults
            adaptation_check = detect_metabolic_adaptation(
                weight_history=bw_history,
                expected_rate_kg_per_week=expected_rate,
                adherence_pct=adherence_pct,
                weeks_window=4,
            )
        except Exception as e:
            logger.warning("Metabolic adaptation detection failed: %s", e)

    return {
        **locked,
        "metabolic_adaptation": {
            "weeks_in_deficit": round(weeks_in_deficit, 1),
            "adapted_tdee": adapted_tdee,
            "adaptation_active": weeks_in_deficit > 0 and phase in ("cut", "peak_week"),
        },
        "metabolic_adaptation_detector": adaptation_check,
        "energy_availability": ea_check,
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
        except (ValueError, KeyError) as e:
            logger.warning("Weight stall check failed: %s", e)

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

    # Determine user's cardio preferences
    prefs = profile.preferences or {}
    fasted_pref = prefs.get("fasted_cardio", True)  # default True during cut
    preferred_machine = prefs.get("cardio_machine", "treadmill")

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

    # Override fasted flag based on user preference, phase, and body fat
    if plan.get("cardio"):
        # During cut/peak, fasted cardio is the coach standard if user allows it.
        # Also allow fasted cardio during offseason/bulk if the athlete is above
        # 16% BF — at higher body fat, fasted LISS aids fat oxidation and the
        # athlete benefits from the additional expenditure pathway.
        bf_pct = getattr(profile, "manual_body_fat_pct", None) or 15.0
        if phase in ("cut", "peak", "peak_week"):
            plan["cardio"]["fasted"] = fasted_pref
        elif fasted_pref and bf_pct > 16.0:
            plan["cardio"]["fasted"] = True
        else:
            plan["cardio"]["fasted"] = False
        plan["cardio"]["preferred_machine"] = preferred_machine

        # Filter modality options to prioritize user's preferred machine
        if preferred_machine:
            machine_map = {
                "treadmill": ["liss_incline_walk", "hiit_sprint"],
                "stairmaster": ["liss_stairmaster"],
                "bike": ["zone2_cycling", "liss_cycling", "hiit_cycling"],
                "rowing": ["hiit_rowing"],
                "elliptical": ["steady_state_elliptical"],
            }
            preferred_modalities = machine_map.get(preferred_machine, [])
            if preferred_modalities:
                options = plan["cardio"].get("modality_options", [])
                # Put preferred modalities first, keep others as fallback
                reordered = [m for m in preferred_modalities if m in options]
                reordered += [m for m in options if m not in reordered]
                if reordered:
                    plan["cardio"]["modality_options"] = reordered

    return plan


# ---------------------------------------------------------------------------
# Cardio logging
# ---------------------------------------------------------------------------

class CardioLogRequest(BaseModel):
    activity_type: str = Field(default="treadmill")
    duration_min: int = Field(default=30, ge=5, le=120)
    intensity: str = Field(default="low")
    recorded_date: str = Field(default="")
    fasted: bool = Field(default=False)
    speed_mph: float | None = None       # treadmill speed
    incline_pct: int | None = None       # treadmill incline
    stair_level: int | None = None       # stairmaster level


@router.post("/cardio/log")
async def log_cardio(
    data: CardioLogRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Log a cardio session with machine-specific parameters."""
    from app.models.nutrition import NutritionLog

    rec_date = date_cls.fromisoformat(data.recorded_date) if data.recorded_date else date_cls.today()

    # Estimate calorie burn based on machine type and duration
    base_per_min = {
        "treadmill": 6.5,
        "stairmaster": 8.5,
        "stationary_bike": 7.0,
        "elliptical": 7.5,
    }.get(data.activity_type, 7.0)

    # Treadmill: adjust for speed and incline
    if data.activity_type == "treadmill":
        speed = data.speed_mph or 3.0
        incline = data.incline_pct or 0
        # Higher speed and incline = more calories
        speed_factor = speed / 3.0  # normalized to 3.0 mph walk
        incline_factor = 1.0 + (incline * 0.03)  # each 1% incline adds ~3%
        base_per_min = 6.5 * speed_factor * incline_factor
    elif data.activity_type == "stairmaster":
        level = data.stair_level or 6
        base_per_min = 5.0 + level * 0.5  # level 6 = 8 kcal/min

    estimated_kcal = round(data.duration_min * base_per_min)

    # Store as a cardio-specific note in the response (no dedicated table needed
    # for MVP — the caloric impact is what matters to the engines)
    details = {
        "type": "cardio",
        "machine": data.activity_type,
        "duration_min": data.duration_min,
        "fasted": data.fasted,
        "estimated_kcal": estimated_kcal,
    }
    if data.speed_mph:
        details["speed_mph"] = data.speed_mph
    if data.incline_pct is not None:
        details["incline_pct"] = data.incline_pct
    if data.stair_level is not None:
        details["stair_level"] = data.stair_level

    return {
        "message": "Cardio logged",
        "estimated_kcal": estimated_kcal,
        "duration_min": data.duration_min,
        "machine": data.activity_type,
        "fasted": data.fasted,
        "details": details,
    }


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

    # Use actual body weight for fat floor (must come before cycling calc)
    bw_result = await db.execute(
        select(BodyWeightLog).where(BodyWeightLog.user_id == user.id)
        .order_by(desc(BodyWeightLog.recorded_date)).limit(1)
    )
    bw = bw_result.scalar_one_or_none()
    weight_for_fat = bw.weight_kg if bw else 80.0
    fat_floor = round(div_nutrition["fat_per_kg_floor"] * weight_for_fat, 1)

    # Calorie-neutral carb cycling — exact same formula as the prescription endpoint.
    # Training day gets more carbs (funded by reducing fat).
    # Rest day gets fewer carbs (saved calories go to fat for hormonal health).
    from app.engines.engine3.macros import _KCAL_PER_G_CARB, _KCAL_PER_G_FAT
    if is_training:
        carbs_g = round(rx.carbs_g * (1.0 + cycling_factor), 1)
        extra_kcal = (carbs_g - rx.carbs_g) * _KCAL_PER_G_CARB
        day_fat_g = round(max(fat_floor, rx.fat_g - extra_kcal / _KCAL_PER_G_FAT), 1)
    else:
        carbs_g = round(rx.carbs_g * (1.0 - cycling_factor), 1)
        saved_kcal = (rx.carbs_g - carbs_g) * _KCAL_PER_G_CARB
        day_fat_g = round(rx.fat_g + saved_kcal / _KCAL_PER_G_FAT, 1)
    target_cals = round(rx.protein_g * 4 + carbs_g * 4 + day_fat_g * 9)
    fat_g = max(fat_floor, day_fat_g)

    # Fetch today's session muscles for intra-workout drink HBCD scaling
    intra_enabled = prefs.get("intra_workout_nutrition", False)
    session_muscles: list[str] = []
    if is_training and intra_enabled:
        from app.models.training import TrainingSession, TrainingSet, TrainingProgram, Exercise
        from datetime import date as _date
        today = _date.today()
        sess_result = await db.execute(
            select(TrainingSession)
            .join(TrainingProgram, TrainingSession.program_id == TrainingProgram.id)
            .where(
                TrainingProgram.user_id == user.id,
                TrainingSession.session_date == today,
                TrainingProgram.is_active == True,
            )
            .limit(1)
        )
        sess = sess_result.scalar_one_or_none()
        if sess:
            muscle_result = await db.execute(
                select(Exercise.primary_muscle)
                .join(TrainingSet, TrainingSet.exercise_id == Exercise.id)
                .where(TrainingSet.session_id == sess.id, TrainingSet.is_warmup == False)
                .distinct()
            )
            session_muscles = [row[0] for row in muscle_result.all() if row[0]]

    # Only opt into fasted training if the user has explicitly set it.
    # Previously the meal planner auto-forced fasted mode for any workout
    # before 7 AM, which gave early lifters an empty "Meal 1 — Fasted"
    # instead of a real pre-workout breakfast.
    fasted_training = prefs.get("fasted_training", False)

    return generate_meal_plan(
        phase=phase,
        division=division,
        meal_count=meal_count,
        protein_g=rx.protein_g,
        carbs_g=carbs_g,
        fat_g=fat_g,
        target_calories=target_cals,
        training_start_time=training_start_time,
        training_duration_min=int(training_duration_min),
        is_training_day=is_training,
        is_refeed=False,
        dietary_restrictions=dietary_restrictions,
        preferred_proteins=prefs.get("preferred_proteins", []),
        preferred_carbs=prefs.get("preferred_carbs", []),
        preferred_fats=prefs.get("preferred_fats", []),
        preferred_vegetables=prefs.get("preferred_vegetables", []),
        intra_workout_nutrition=intra_enabled and is_training,
        fasted_training=fasted_training,
        body_weight_kg=weight_for_fat,
        session_muscles=session_muscles,
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

    # When intra-workout nutrition is enabled, always regenerate training-day
    # plans fresh (the intra drink depends on today's session muscles).
    prefs_check = profile.preferences or {}
    intra_on = prefs_check.get("intra_workout_nutrition", False)
    if "training" not in cached or intra_on:
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

    # Per-meal protein distribution validation — elite prep requires 4–6
    # doses of ≥0.40 g/kg BW to keep MPS maximally stimulated all day.
    from app.engines.engine3.macros import (
        validate_protein_distribution,
        compute_hydration_target,
        validate_micronutrient_coverage,
    )
    bw_row = await db.execute(
        select(BodyWeightLog).where(BodyWeightLog.user_id == user.id)
        .order_by(desc(BodyWeightLog.recorded_date), desc(BodyWeightLog.created_at)).limit(1)
    )
    latest_bw = bw_row.scalar_one_or_none()
    bw_kg = latest_bw.weight_kg if latest_bw else None

    protein_training = None
    protein_rest = None
    hydration = None
    micros_training = None
    micros_rest = None
    if bw_kg:
        protein_training = validate_protein_distribution(cached["training"], bw_kg)
        protein_rest = validate_protein_distribution(cached["rest"], bw_kg)
        hydration = compute_hydration_target(bw_kg, rx.phase, training_session_today=True)

    sex = getattr(profile, "sex", "male") or "male"
    micros_training = validate_micronutrient_coverage(cached["training"], sex)
    micros_rest = validate_micronutrient_coverage(cached["rest"], sex)

    from app.engines.engine3.meal_planner import compute_filtered_picks
    _prefs_for_filter = profile.preferences or {}
    filtered_picks = compute_filtered_picks(
        phase=rx.phase,
        dietary_restrictions=_prefs_for_filter.get("dietary_restrictions"),
        preferred_proteins=_prefs_for_filter.get("preferred_proteins"),
        preferred_carbs=_prefs_for_filter.get("preferred_carbs"),
        preferred_fats=_prefs_for_filter.get("preferred_fats"),
        preferred_vegetables=_prefs_for_filter.get("preferred_vegetables"),
    )

    return {
        "phase": rx.phase,
        "training_day": cached["training"],
        "rest_day": cached["rest"],
        "protein_distribution": {
            "training": protein_training,
            "rest": protein_rest,
        } if protein_training else None,
        "hydration": hydration,
        "micronutrients": {
            "training": micros_training,
            "rest": micros_rest,
        },
        "filtered_picks": filtered_picks,
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

    # Delete ALL existing templates for this user first — otherwise
    # regeneration just layers a new template on top of the old ones and
    # GET /meal-plan/current can still surface the stale version when the
    # desc(created_at) ordering ties or a cached read races.
    old_tpl_result = await db.execute(
        select(MealPlanTemplate).where(MealPlanTemplate.user_id == user.id)
    )
    for old_tpl in old_tpl_result.scalars().all():
        await db.delete(old_tpl)
    await db.flush()

    plans: dict[str, list] = {}
    for day_type in ("training", "rest"):
        plans[day_type] = await _build_meal_plan_for_day(db, user, profile, rx, day_type)
        db.add(MealPlanTemplate(
            user_id=user.id, day_type=day_type, phase=rx.phase, meals_json=plans[day_type]
        ))

    await db.flush()

    from app.engines.engine3.meal_planner import compute_filtered_picks
    _prefs_for_filter = profile.preferences or {}
    return {
        "phase": rx.phase,
        "training_day": plans["training"],
        "rest_day": plans["rest"],
        "regenerated": True,
        "filtered_picks": compute_filtered_picks(
            phase=rx.phase,
            dietary_restrictions=_prefs_for_filter.get("dietary_restrictions"),
            preferred_proteins=_prefs_for_filter.get("preferred_proteins"),
            preferred_carbs=_prefs_for_filter.get("preferred_carbs"),
            preferred_fats=_prefs_for_filter.get("preferred_fats"),
            preferred_vegetables=_prefs_for_filter.get("preferred_vegetables"),
        ),
    }


@router.post("/meal-plan/invalidate")
async def invalidate_meal_plan_cache(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Invalidate cached meal plan templates. Called when nutrition-relevant
    settings change (meal count, dietary restrictions, food preferences).
    The next GET /meal-plan/current will regenerate fresh plans.
    """
    deleted = await db.execute(
        select(MealPlanTemplate).where(MealPlanTemplate.user_id == user.id)
    )
    templates = deleted.scalars().all()
    count = len(templates)
    for tpl in templates:
        await db.delete(tpl)
    await db.flush()
    return {"invalidated": count}


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


# ---------------------------------------------------------------------------
# Shopping List
# ---------------------------------------------------------------------------

@router.get("/shopping-list/weekly")
async def get_weekly_shopping_list(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate a consolidated weekly shopping list from the current meal plan.
    Aggregates training-day and rest-day ingredients, rounds to purchase
    quantities, and organizes by grocery section.
    """
    from app.engines.engine3.shopping_list import generate_weekly_shopping_list

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

    prefs = profile.preferences or {}
    days_per_week = prefs.get("training_days_per_week", profile.days_per_week or 5)

    # Generate both day types
    training_meals = await _build_meal_plan_for_day(db, user, profile, rx, "training")
    rest_meals = await _build_meal_plan_for_day(db, user, profile, rx, "rest")

    shopping_list = generate_weekly_shopping_list(
        training_day_meals=training_meals,
        rest_day_meals=rest_meals,
        training_days_per_week=days_per_week,
    )

    return shopping_list


# ---------------------------------------------------------------------------
# Supplement Protocol
# ---------------------------------------------------------------------------

@router.get("/supplements/current")
async def get_supplement_protocol(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the evidence-based supplement stack for the user's current phase."""
    rx_result = await db.execute(
        select(NutritionPrescription)
        .where(NutritionPrescription.user_id == user.id, NutritionPrescription.is_active == True)
        .order_by(desc(NutritionPrescription.created_at)).limit(1)
    )
    rx = rx_result.scalar_one_or_none()
    phase = rx.phase if rx else "maintain"

    from app.engines.engine3.supplements import get_supplement_protocol
    protocol = get_supplement_protocol(phase)
    return {"phase": phase, "supplements": protocol, "count": len(protocol)}


# ---------------------------------------------------------------------------
# Block 5 — Mini-Cut Trigger & Phase Transition
# ---------------------------------------------------------------------------


@router.get("/mini-cut/evaluate")
async def evaluate_mini_cut(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Evaluate whether the user should transition to a mini-cut based on:
    1. Body fat threshold relative to weight cap
    2. User-configured cut_threshold_bf_pct
    3. Current phase (only triggers from offseason/bulk)
    """
    profile_result = await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))
    profile = profile_result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    # Get current weight
    bw_result = await db.execute(
        select(BodyWeightLog).where(BodyWeightLog.user_id == user.id)
        .order_by(desc(BodyWeightLog.recorded_date)).limit(1)
    )
    latest_bw = bw_result.scalar_one_or_none()
    if not latest_bw:
        return {"should_mini_cut": False, "reason": "No weight data available"}

    # Get current BF% from profile or latest measurement
    current_bf = getattr(profile, "manual_body_fat_pct", None)

    # Get current phase
    rx_result = await db.execute(
        select(NutritionPrescription)
        .where(NutritionPrescription.user_id == user.id, NutritionPrescription.is_active == True)
        .order_by(desc(NutritionPrescription.created_at)).limit(1)
    )
    rx = rx_result.scalar_one_or_none()
    current_phase = rx.phase if rx else "offseason"

    # Only evaluate from offseason/bulk phases
    if current_phase not in ("offseason", "bulk", "lean_bulk"):
        return {"should_mini_cut": False, "reason": f"Currently in {current_phase} — mini-cut only triggers from offseason/bulk"}

    # Check user-configured threshold
    prefs = profile.preferences or {}
    user_threshold = prefs.get("cut_threshold_bf_pct")

    if user_threshold and current_bf and current_bf >= user_threshold:
        return {
            "should_mini_cut": True,
            "reason": f"Body fat ({current_bf}%) exceeds your threshold ({user_threshold}%)",
            "current_bf_pct": current_bf,
            "threshold_bf_pct": user_threshold,
            "recommended_duration_weeks": 4,
        }

    # Weight-cap-based evaluation
    from app.engines.engine1.weight_cap import compute_bf_threshold_from_weight_cap
    eval_result = compute_bf_threshold_from_weight_cap(
        height_cm=profile.height_cm,
        current_weight_kg=latest_bw.weight_kg,
        wrist_cm=getattr(profile, "wrist_circumference_cm", None),
        ankle_cm=getattr(profile, "ankle_circumference_cm", None),
        sex=profile.sex,
        division=profile.division,
    )

    return {
        "should_mini_cut": eval_result["should_mini_cut"],
        "reason": f"{'Excess weight detected' if eval_result['should_mini_cut'] else 'Within offseason range'}",
        "current_bf_pct": current_bf,
        "threshold_bf_pct": eval_result["threshold_bf_pct"],
        "offseason_cap_kg": eval_result["offseason_cap_kg"],
        "excess_kg": eval_result["excess_kg"],
        "recommended_duration_weeks": 4 if eval_result["should_mini_cut"] else 0,
    }


class PhaseTransitionRequest(BaseModel):
    target_phase: str


@router.post("/phase/transition")
async def transition_phase(
    data: PhaseTransitionRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Transition the user to a new nutrition phase.
    Creates a new NutritionPrescription with the target phase,
    invalidates meal plan cache, and returns the new prescription.
    """
    valid_phases = {"offseason", "bulk", "lean_bulk", "maintain", "cut", "mini_cut", "peak_week", "contest", "restoration"}
    if data.target_phase not in valid_phases:
        raise HTTPException(status_code=400, detail=f"Invalid phase: {data.target_phase}")

    # Atomically deactivate current prescription (avoids race between two
    # concurrent phase transitions leaving multiple is_active=True rows).
    from sqlalchemy import update as _update
    await db.execute(
        _update(NutritionPrescription)
        .where(
            NutritionPrescription.user_id == user.id,
            NutritionPrescription.is_active == True,
        )
        .values(is_active=False)
    )

    # Get current prescription values to base the new one on
    latest_result = await db.execute(
        select(NutritionPrescription).where(NutritionPrescription.user_id == user.id)
        .order_by(desc(NutritionPrescription.created_at)).limit(1)
    )
    latest_rx = latest_result.scalar_one_or_none()

    if latest_rx:
        # Adjust macros for the new phase
        from app.engines.engine3.macros import adjust_macros_for_phase
        adjusted = adjust_macros_for_phase(
            current_calories=latest_rx.target_calories,
            current_protein_g=latest_rx.protein_g,
            current_carbs_g=latest_rx.carbs_g,
            current_fat_g=latest_rx.fat_g,
            from_phase=latest_rx.phase,
            to_phase=data.target_phase,
        )
        new_rx = NutritionPrescription(
            user_id=user.id,
            phase=data.target_phase,
            tdee=latest_rx.tdee,
            target_calories=adjusted["calories"],
            protein_g=adjusted["protein_g"],
            carbs_g=adjusted["carbs_g"],
            fat_g=adjusted["fat_g"],
            peri_workout_carb_pct=latest_rx.peri_workout_carb_pct or 0.4,
            is_active=True,
        )
    else:
        new_rx = NutritionPrescription(
            user_id=user.id,
            phase=data.target_phase,
            tdee=2500,
            target_calories=2500,
            protein_g=200,
            carbs_g=250,
            fat_g=80,
            peri_workout_carb_pct=0.4,
            is_active=True,
        )

    db.add(new_rx)

    # Invalidate meal plan cache for old phase
    tpl_result = await db.execute(
        select(MealPlanTemplate).where(MealPlanTemplate.user_id == user.id)
    )
    for tpl in tpl_result.scalars().all():
        await db.delete(tpl)

    await db.flush()

    return {
        "message": f"Transitioned to {data.target_phase}",
        "phase": data.target_phase,
        "target_calories": new_rx.target_calories,
        "protein_g": new_rx.protein_g,
        "carbs_g": new_rx.carbs_g,
        "fat_g": new_rx.fat_g,
    }


# ---------------------------------------------------------------------------
# Cheat meal tracking
# ---------------------------------------------------------------------------

class CheatMealCreate(BaseModel):
    description: str = Field(..., max_length=200)
    calories: int = Field(..., ge=0, le=10000)


def _cheat_week_start(today: date_cls) -> date_cls:
    """Return the Monday that starts today's ISO week."""
    return today - timedelta(days=today.weekday())


def _cheat_meal_stats(prefs: dict) -> dict:
    allowed = int(prefs.get("cheat_meals_per_week", 0) or 0)
    log: list = list(prefs.get("cheat_meal_log", []) or [])
    today = date_cls.today()
    week_start = _cheat_week_start(today)
    used_this_week = 0
    recent: list[dict] = []
    for entry in log:
        try:
            d = date_cls.fromisoformat(str(entry.get("date", "")))
        except ValueError:
            continue
        recent.append({
            "date": d.isoformat(),
            "description": str(entry.get("description", ""))[:200],
            "calories": int(entry.get("calories", 0) or 0),
        })
        if d >= week_start:
            used_this_week += 1
    recent.sort(key=lambda e: e["date"], reverse=True)
    return {
        "allowed": allowed,
        "used_this_week": used_this_week,
        "remaining": max(0, allowed - used_this_week),
        "week_start": week_start.isoformat(),
        "recent": recent[:10],
    }


@router.get("/cheat-meal/stats")
async def get_cheat_meal_stats(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    profile_result = await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))
    profile = profile_result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Complete onboarding first")
    return _cheat_meal_stats(profile.preferences or {})


@router.post("/cheat-meal")
async def log_cheat_meal(
    data: CheatMealCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    profile_result = await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))
    profile = profile_result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Complete onboarding first")

    current = dict(profile.preferences or {})
    log: list = list(current.get("cheat_meal_log", []) or [])
    log.append({
        "date": date_cls.today().isoformat(),
        "description": data.description.strip(),
        "calories": data.calories,
    })
    # Keep the last 30 entries so the log doesn't grow unbounded
    current["cheat_meal_log"] = log[-30:]
    profile.preferences = current
    await db.flush()
    return _cheat_meal_stats(current)
