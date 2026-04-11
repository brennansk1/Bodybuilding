import logging
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException

logger = logging.getLogger(__name__)
from pydantic import BaseModel
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.profile import UserProfile
from app.models.measurement import BodyWeightLog, TapeMeasurement, SkinfoldMeasurement
from app.models.training import HRVLog, ARILog
from app.models.nutrition import AdherenceLog, WeeklyCheckin, NutritionPrescription
from app.dependencies import get_user_via_api_key
from app.schemas.checkin import DailyCheckin, HealthKitPayload, WeeklyCheckinRequest
from app.engines.engine1.body_fat import jackson_pollock_7

router = APIRouter(prefix="/checkin", tags=["checkin"])


@router.post("/daily")
async def submit_daily(
    data: DailyCheckin,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    today = date.today()

    # 1. Resolve body weight
    weight_kg = data.body_weight_kg
    if weight_kg is None:
        last_bw_result = await db.execute(
            select(BodyWeightLog).where(BodyWeightLog.user_id == user.id)
            .order_by(desc(BodyWeightLog.recorded_date), desc(BodyWeightLog.created_at)).limit(1)
        )
        last_bw = last_bw_result.scalar_one_or_none()
        weight_kg = last_bw.weight_kg if last_bw else None

    if weight_kg is not None:
        existing_bw = await db.execute(
            select(BodyWeightLog).where(BodyWeightLog.user_id == user.id, BodyWeightLog.recorded_date == today)
        )
        if old := existing_bw.scalar_one_or_none():
            await db.delete(old)
        bw = BodyWeightLog(user_id=user.id, weight_kg=weight_kg, recorded_date=today)
        db.add(bw)

    # 2. HRV and Soreness
    recent_result = await db.execute(
        select(HRVLog).where(HRVLog.user_id == user.id)
        .order_by(desc(HRVLog.recorded_date), desc(HRVLog.created_at)).limit(7)
    )
    recent_hrv = recent_result.scalars().all()

    def _avg(field: str, fallback: float) -> float:
        vals = [getattr(h, field) for h in recent_hrv if getattr(h, field) is not None]
        return round(sum(vals) / len(vals), 1) if vals else fallback

    rmssd = data.rmssd if data.rmssd is not None else _avg("rmssd", 50.0)
    sleep_quality = data.sleep_quality if data.sleep_quality is not None else _avg("sleep_quality", 7.0)
    soreness_score = data.soreness_score if data.soreness_score is not None else _avg("soreness_score", 5.0)

    existing_hrv = await db.execute(
        select(HRVLog).where(HRVLog.user_id == user.id, HRVLog.recorded_date == today)
    )
    if old := existing_hrv.scalar_one_or_none():
        await db.delete(old)

    hrv = HRVLog(
        user_id=user.id,
        rmssd=rmssd,
        resting_hr=data.resting_hr,
        sleep_quality=sleep_quality,
        sleep_hours=data.sleep_hours,
        soreness_score=soreness_score,
        sore_muscles=data.sore_muscles,
        stress_score=data.stress_score,
        mood_score=data.mood_score,
        energy_score=data.energy_score,
        notes=data.notes,
        recorded_date=today,
    )
    db.add(hrv)

    # 3. Adherence
    if data.nutrition_adherence_pct is not None and data.training_adherence_pct is not None:
        overall = (data.nutrition_adherence_pct + data.training_adherence_pct) / 2
        log = AdherenceLog(
            user_id=user.id,
            recorded_date=today,
            nutrition_adherence_pct=data.nutrition_adherence_pct,
            training_adherence_pct=data.training_adherence_pct,
            overall_adherence_pct=overall,
        )
        db.add(log)

    await db.flush()

    # Compute ARI — 7-day rolling baseline per HRV research (Plews/Buchheit).
    baseline_result = await db.execute(
        select(HRVLog).where(HRVLog.user_id == user.id)
        .order_by(desc(HRVLog.recorded_date), desc(HRVLog.created_at)).limit(7)
    )
    hrv_history = baseline_result.scalars().all()
    baseline_rmssd = sum(h.rmssd for h in hrv_history) / len(hrv_history) if hrv_history else rmssd
    hr_history = [h.resting_hr for h in hrv_history if h.resting_hr is not None]
    baseline_hr = sum(hr_history) / len(hr_history) if hr_history else data.resting_hr

    from app.engines.engine2.ari import (
        compute_ari_breakdown,
        get_zone_recommendation,
        menstrual_phase,
        apply_cycle_modifier,
        get_ari_zone,
    )
    ari_breakdown = compute_ari_breakdown(
        rmssd=rmssd,
        resting_hr=data.resting_hr,
        sleep_quality_1_10=sleep_quality,
        soreness_1_10=soreness_score,
        baseline_rmssd=baseline_rmssd,
        baseline_hr=baseline_hr,
        sleep_hours=data.sleep_hours,
        stress_1_10=data.stress_score,
        mood_1_10=data.mood_score,
        energy_1_10=data.energy_score,
    )

    # Menstrual cycle adjustment for female athletes with tracking enabled.
    profile_row = await db.execute(
        select(UserProfile).where(UserProfile.user_id == user.id)
    )
    _profile = profile_row.scalar_one_or_none()
    cycle_info = None
    if _profile and getattr(_profile, "sex", None) == "female" and getattr(_profile, "cycle_tracking_enabled", False):
        cycle_info = menstrual_phase(getattr(_profile, "cycle_start_date", None))

    if cycle_info:
        adjusted_score = apply_cycle_modifier(ari_breakdown["score"], cycle_info)
        ari_breakdown["score"] = adjusted_score
        ari_breakdown["zone"] = get_ari_zone(adjusted_score)

    ari_score = ari_breakdown["score"]
    ari_zone = ari_breakdown["zone"]
    ari_recommendation = get_zone_recommendation(ari_score)
    if cycle_info:
        ari_recommendation += " " + cycle_info["coaching_note"]

    # Persist ARI breakdown so future queries can explain the score.
    ari_log = ARILog(
        user_id=user.id,
        ari_score=ari_score,
        hrv_component=ari_breakdown["hrv"],
        sleep_component=ari_breakdown["sleep"],
        soreness_component=ari_breakdown["soreness"],
        hr_component=ari_breakdown["hr"],
        stress_component=ari_breakdown["wellness"],
        recorded_date=today,
    )
    # Replace any prior entry for today so the row reflects the latest check-in.
    existing_ari = await db.execute(
        select(ARILog).where(ARILog.user_id == user.id, ARILog.recorded_date == today)
    )
    if old_ari := existing_ari.scalar_one_or_none():
        await db.delete(old_ari)
    db.add(ari_log)

    # 4. Engine 2 — Daily session autoregulation for morning soreness
    from app.models.training import TrainingSession
    from app.services.training import autoregulate_session_for_soreness
    
    session_res = await db.execute(
        select(TrainingSession)
        .where(
            TrainingSession.user_id == user.id, 
            TrainingSession.session_date == today, 
            TrainingSession.completed == False
        )
    )
    active_session = session_res.scalar_one_or_none()
    autoreg_msg = None
    if active_session and hrv.sore_muscles:
        dropped, affected = await autoregulate_session_for_soreness(db, user.id, active_session, hrv.sore_muscles)
        if dropped > 0:
            autoreg_msg = f"Autoregulated {len(affected)} exercise(s), reduced local volume by {dropped} sets."
            await db.flush()

    # Immediate ARI red-zone Telegram alert (fires at most once per day)
    if ari_zone == "red" and _profile:
        try:
            from app.services.notification_dispatcher import dispatch_ari_red_zone
            await dispatch_ari_red_zone(db, _profile, ari_score, ari_recommendation)
        except Exception as exc:
            logger.warning("ARI red-zone notification failed: %s", exc)

    return {
        "message": "Daily check-in saved",
        "weight_kg": weight_kg,
        "ari_score": ari_score,
        "zone": ari_zone,
        "recommendation": ari_recommendation,
        "components": {
            "hrv": ari_breakdown["hrv"],
            "sleep": ari_breakdown["sleep"],
            "soreness": ari_breakdown["soreness"],
            "hr": ari_breakdown["hr"],
            "wellness": ari_breakdown["wellness"],
        },
        "menstrual_phase": cycle_info,
        "autoregulation": autoreg_msg,
    }


# ---------------------------------------------------------------------------
# HealthKit / iPhone Shortcut ingest
# ---------------------------------------------------------------------------

@router.post("/daily/healthkit")
async def submit_daily_healthkit(
    payload: HealthKitPayload,
    user: User = Depends(get_user_via_api_key),
    db: AsyncSession = Depends(get_db),
):
    """
    iPhone Shortcut → backend ingest for morning HealthKit data.

    Authenticated via long-lived ``X-API-Key`` header (Shortcuts can't do
    OAuth/JWT flows). Maps Apple HealthKit quantities into the regular
    DailyCheckin shape and delegates to submit_daily() so all downstream
    analysis (ARI breakdown, red-zone alert, soreness autoregulation)
    runs identically whether the check-in came from the web UI or a Shortcut.

    HKQuantityTypeIdentifierHeartRateVariabilitySDNN → rMSSD via the 0.8
    approximation (see notes field). If the caller provides hrv_rmssd_ms
    directly, that's used instead.
    """
    # Convert HealthKit SDNN to rMSSD if the caller didn't already do it.
    rmssd = payload.hrv_rmssd_ms
    note_parts = []
    if rmssd is None and payload.hrv_sdnn_ms is not None:
        rmssd = round(payload.hrv_sdnn_ms * 0.8, 1)
        note_parts.append(
            f"HealthKit SDNN {payload.hrv_sdnn_ms:.0f} → rMSSD ≈ {rmssd:.0f} (×0.8)"
        )
    if payload.step_count is not None:
        note_parts.append(f"Steps: {payload.step_count}")
    if payload.notes:
        note_parts.append(payload.notes)

    daily = DailyCheckin(
        recorded_date=payload.recorded_date,
        body_weight_kg=payload.body_weight_kg,
        rmssd=rmssd,
        resting_hr=payload.resting_hr,
        sleep_quality=payload.sleep_quality_1_10,
        sleep_hours=payload.sleep_hours,
        soreness_score=None,   # HealthKit has no soreness; leave null to trigger fallback
        sore_muscles=[],
        stress_score=payload.stress_1_10,
        mood_score=payload.mood_1_10,
        energy_score=payload.energy_1_10,
        nutrition_adherence_pct=None,
        training_adherence_pct=None,
        notes="; ".join(note_parts) if note_parts else None,
    )
    return await submit_daily(daily, user=user, db=db)


@router.post("/weekly")
async def submit_weekly(
    data: WeeklyCheckinRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Process a weekly check-in: save tape/skinfold/photos, then run Engine 1 (physique diagnostic),
    Engine 2 (ARI + volume modifier), and Engine 3 (kinetic calorie adjustment).
    """
    today = date.today()

    # Save Tape Measurements
    tape_fields = {
        "neck", "shoulders", "chest", "left_bicep", "right_bicep",
        "left_forearm", "right_forearm", "waist", "hips",
        "left_thigh", "right_thigh", "left_calf", "right_calf",
        "chest_relaxed", "chest_lat_spread", "back_width",
        "left_proximal_thigh", "right_proximal_thigh",
        "left_distal_thigh", "right_distal_thigh",
    }
    tape_data = {f: getattr(data, f) for f in tape_fields if getattr(data, f) is not None}
    if tape_data:
        tape = TapeMeasurement(user_id=user.id, recorded_date=today, **tape_data)
        db.add(tape)

    # Save Skinfolds (JP7 caliper sites)
    sf_map = {
        "sf_chest": "chest", "sf_midaxillary": "midaxillary", "sf_tricep": "tricep",
        "sf_subscapular": "subscapular", "sf_abdominal": "abdominal",
        "sf_suprailiac": "suprailiac", "sf_thigh": "thigh",
        "sf_bicep": "bicep", "sf_lower_back": "lower_back", "sf_calf": "calf",
    }
    sf_data = {sf_map[f]: getattr(data, f) for f in sf_map if getattr(data, f) is not None}
    direct_bf = data.body_fat_pct  # from Fit3D / DEXA / InBody
    if sf_data or direct_bf is not None:
        body_fat_pct = direct_bf  # prefer direct scan value
        if body_fat_pct is None and len(sf_data) == 7:
            profile_result = await db.execute(
                select(UserProfile).where(UserProfile.user_id == user.id)
            )
            profile = profile_result.scalar_one_or_none()
            if profile:
                body_fat_pct = jackson_pollock_7(
                    chest=sf_data["chest"], midaxillary=sf_data["midaxillary"],
                    tricep=sf_data["tricep"], subscapular=sf_data["subscapular"],
                    abdominal=sf_data["abdominal"], suprailiac=sf_data["suprailiac"],
                    thigh=sf_data["thigh"], age=profile.age or 25, sex=profile.sex,
                )
        skinfold = SkinfoldMeasurement(
            user_id=user.id, recorded_date=today, body_fat_pct=body_fat_pct, **sf_data,
        )
        db.add(skinfold)

        # Sync scan-provided BF% to UserProfile so all engines see it immediately
        if direct_bf is not None:
            profile_result = await db.execute(
                select(UserProfile).where(UserProfile.user_id == user.id)
            )
            profile = profile_result.scalar_one_or_none()
            if profile:
                profile.manual_body_fat_pct = direct_bf

    await db.flush()

    # Week number
    count_result = await db.execute(
        select(func.count()).select_from(WeeklyCheckin).where(WeeklyCheckin.user_id == user.id)
    )
    week_number = count_result.scalar() + 1

    # Fetch data
    bw_result = await db.execute(
        select(BodyWeightLog).where(BodyWeightLog.user_id == user.id)
        .order_by(desc(BodyWeightLog.recorded_date), desc(BodyWeightLog.created_at)).limit(1)
    )
    latest_bw = bw_result.scalar_one_or_none()
    if not latest_bw:
        raise HTTPException(status_code=400, detail="Submit daily biological data first for weight context")

    hrv_result = await db.execute(
        select(HRVLog).where(HRVLog.user_id == user.id)
        .order_by(desc(HRVLog.recorded_date), desc(HRVLog.created_at)).limit(1)
    )
    latest_hrv = hrv_result.scalar_one_or_none()

    adh_result = await db.execute(
        select(AdherenceLog).where(AdherenceLog.user_id == user.id)
        .order_by(desc(AdherenceLog.recorded_date), desc(AdherenceLog.created_at)).limit(1)
    )
    latest_adh = adh_result.scalar_one_or_none()

    profile_result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == user.id)
    )
    profile = profile_result.scalar_one_or_none()

    # -----------------------------------------------------------------------
    # Engine 1: Physique diagnostic
    # -----------------------------------------------------------------------
    from app.services.diagnostic import run_full_diagnostic
    try:
        engine1_result = await run_full_diagnostic(db, user)
    except ValueError:
        engine1_result = None

    # -----------------------------------------------------------------------
    # Engine 2: ARI computation → store ARILog
    # -----------------------------------------------------------------------
    ari_score = None
    ari_zone = None
    if latest_hrv:
        # 7-day rolling baseline (HRV research standard)
        baseline_result = await db.execute(
            select(HRVLog).where(HRVLog.user_id == user.id)
            .order_by(desc(HRVLog.recorded_date), desc(HRVLog.created_at)).limit(7)
        )
        hrv_history = baseline_result.scalars().all()
        baseline_rmssd = sum(h.rmssd for h in hrv_history) / len(hrv_history)
        hr_values = [h.resting_hr for h in hrv_history if h.resting_hr]
        baseline_hr = sum(hr_values) / len(hr_values) if hr_values else None

        soreness = getattr(latest_hrv, "soreness_score", None) or 5.0

        from app.engines.engine2.ari import compute_ari_breakdown
        ari_breakdown = compute_ari_breakdown(
            rmssd=latest_hrv.rmssd,
            resting_hr=latest_hrv.resting_hr,
            sleep_quality_1_10=latest_hrv.sleep_quality,
            soreness_1_10=soreness,
            baseline_rmssd=baseline_rmssd,
            baseline_hr=baseline_hr,
            sleep_hours=getattr(latest_hrv, "sleep_hours", None),
            stress_1_10=getattr(latest_hrv, "stress_score", None),
            mood_1_10=getattr(latest_hrv, "mood_score", None),
            energy_1_10=getattr(latest_hrv, "energy_score", None),
        )
        ari_score = ari_breakdown["score"]
        ari_zone = ari_breakdown["zone"]

        ari_log = ARILog(
            user_id=user.id,
            ari_score=ari_score,
            hrv_component=ari_breakdown["hrv"],
            sleep_component=ari_breakdown["sleep"],
            soreness_component=ari_breakdown["soreness"],
            hr_component=ari_breakdown["hr"],
            stress_component=ari_breakdown["wellness"],
            recorded_date=today,
        )
        db.add(ari_log)

    # Early deload detection — trigger when ≥3 of the last 5 ARI scores
    # dropped below 42. The previous "all 5 below 40" gate was too strict
    # and missed clearly overtrained athletes with a lucky high day.
    early_deload_recommended = False
    ari_history_result = await db.execute(
        select(ARILog).where(ARILog.user_id == user.id)
        .order_by(desc(ARILog.recorded_date), desc(ARILog.created_at)).limit(5)
    )
    recent_ari_logs = ari_history_result.scalars().all()
    if len(recent_ari_logs) >= 5:
        low_days = sum(1 for a in recent_ari_logs if a.ari_score < 42)
        if low_days >= 3:
            early_deload_recommended = True

    # -----------------------------------------------------------------------
    # Engine 3: Kinetic rate-of-change → calorie adjustment
    # -----------------------------------------------------------------------
    calorie_adjustment = None
    adherence_locked = False
    adherence_pct = latest_adh.overall_adherence_pct if latest_adh else 100.0

    from app.engines.engine3.autoregulation import adherence_lock
    rx_result = await db.execute(
        select(NutritionPrescription).where(
            NutritionPrescription.user_id == user.id,
            NutritionPrescription.is_active == True,
        ).limit(1)
    )
    rx = rx_result.scalar_one_or_none()

    actual_rate = None
    if rx:
        lock_result = adherence_lock(adherence_pct, {
            "target_calories": rx.target_calories,
            "protein_g": rx.protein_g,
            "carbs_g": rx.carbs_g,
            "fat_g": rx.fat_g,
        })
        adherence_locked = lock_result.get("locked", False)

        if not adherence_locked:
            # Run kinetic adjustment if we have enough weight history
            bw_history_result = await db.execute(
                select(BodyWeightLog).where(BodyWeightLog.user_id == user.id)
                .order_by(desc(BodyWeightLog.recorded_date), desc(BodyWeightLog.created_at)).limit(8)
            )
            bw_history = bw_history_result.scalars().all()

            if len(bw_history) >= 2:
                weight_tuples = [
                    (str(bw.recorded_date), bw.weight_kg)
                    for bw in reversed(bw_history)
                ]
                from app.engines.engine3.kinetic import (
                    compute_rate_of_change, target_rate, adjust_calories,
                )
                actual_rate = compute_rate_of_change(weight_tuples)
                t_rate = target_rate(rx.phase, latest_bw.weight_kg)
                new_calories = adjust_calories(rx.target_calories, actual_rate, t_rate)

                if abs(new_calories - rx.target_calories) >= 50:
                    # Adjust carbs to hit new calorie target (keep protein + fat stable)
                    carb_delta_g = (new_calories - rx.target_calories) / 4.0
                    rx.is_active = False
                    new_rx = NutritionPrescription(
                        user_id=user.id,
                        tdee=rx.tdee,
                        target_calories=new_calories,
                        protein_g=rx.protein_g,
                        carbs_g=max(0.0, round(rx.carbs_g + carb_delta_g, 1)),
                        fat_g=rx.fat_g,
                        phase=rx.phase,
                        is_active=True,
                    )
                    db.add(new_rx)
                    calorie_adjustment = round(new_calories - rx.target_calories, 0)

    # Phase auto-detection
    phase_mismatch = False
    phase_mismatch_detail = None
    if profile and rx and actual_rate is not None:
        from app.engines.engine1.prep_timeline import prep_phase_for_date
        auto_phase = prep_phase_for_date(profile.competition_date)
        current_phase = rx.phase
        rate_per_week = actual_rate * 7
        if current_phase == "cut" and rate_per_week > 0.1:
            phase_mismatch = True
            phase_mismatch_detail = (
                f"Phase is 'cut' but gaining {rate_per_week:.2f} kg/week. "
                "Increase deficit or reduce calories."
            )
        elif current_phase in ("bulk", "lean_bulk") and rate_per_week < -0.1:
            phase_mismatch = True
            phase_mismatch_detail = (
                f"Phase is '{current_phase}' but losing {abs(rate_per_week):.2f} kg/week. "
                "Increase calories to support muscle building."
            )

    # LBM protection guardrail
    lbm_risk = False
    lbm_risk_detail = None
    if rx and rx.phase in ("cut", "peak") and actual_rate is not None:
        rate_per_week = actual_rate * 7
        threshold = -(latest_bw.weight_kg * 0.01)
        if rate_per_week < threshold:
            # Check if this has been true for 2 consecutive weeks by looking at 2-week bw trend
            bw_4wk_result = await db.execute(
                select(BodyWeightLog).where(BodyWeightLog.user_id == user.id)
                .order_by(desc(BodyWeightLog.recorded_date), desc(BodyWeightLog.created_at)).limit(16)
            )
            bw_4wk = bw_4wk_result.scalars().all()
            if len(bw_4wk) >= 8:
                from app.engines.engine3.kinetic import compute_rate_of_change
                week1_tuples = [(str(b.recorded_date), b.weight_kg) for b in reversed(bw_4wk[:8])]
                week2_tuples = [(str(b.recorded_date), b.weight_kg) for b in reversed(bw_4wk[8:])]
                rate1 = compute_rate_of_change(week1_tuples) * 7
                rate2 = compute_rate_of_change(week2_tuples) * 7 if len(week2_tuples) >= 2 else rate1
                if rate1 < threshold and rate2 < threshold:
                    lbm_risk = True
                    lbm_risk_detail = (
                        f"Weight loss rate ({rate_per_week:.2f} kg/week) exceeds 1% body weight "
                        f"({threshold:.2f} kg/week) for 2 consecutive weeks. "
                        "Risk of LBM loss — consider reducing deficit."
                    )

    # -----------------------------------------------------------------------
    # Persist weekly check-in record
    # -----------------------------------------------------------------------
    checkin = WeeklyCheckin(
        user_id=user.id,
        week_number=week_number,
        checkin_date=today,
        body_weight_kg=latest_bw.weight_kg,
        avg_rmssd=latest_hrv.rmssd if latest_hrv else None,
        avg_resting_hr=latest_hrv.resting_hr if latest_hrv else None,
        avg_sleep_quality=latest_hrv.sleep_quality if latest_hrv else None,
        soreness_score=getattr(latest_hrv, "soreness_score", None) if latest_hrv else None,
        nutrition_adherence_pct=latest_adh.nutrition_adherence_pct if latest_adh else None,
        training_adherence_pct=latest_adh.training_adherence_pct if latest_adh else None,
        pds_score=engine1_result["pds"]["score"] if engine1_result else None,
        ari_score=ari_score,
        front_photo_url=data.front_photo_url,
        back_photo_url=data.back_photo_url,
        side_left_photo_url=data.side_left_photo_url,
        side_right_photo_url=data.side_right_photo_url,
        front_pose_photo_url=data.front_pose_photo_url,
        back_pose_photo_url=data.back_pose_photo_url,
        notes=data.notes,
        processed=True,
    )
    db.add(checkin)
    await db.flush()

    response: dict = {
        "message": "Check-in processed",
        "week": week_number,
        "body_weight_kg": latest_bw.weight_kg,
        "pds": engine1_result["pds"] if engine1_result else None,
    }
    if ari_score is not None:
        response["ari"] = {"score": ari_score, "zone": ari_zone}
    if calorie_adjustment is not None:
        response["calorie_adjustment"] = calorie_adjustment
        response["calorie_adjustment_reason"] = (
            f"Weight trend adjusted: {'+' if calorie_adjustment > 0 else ''}{int(calorie_adjustment)} kcal"
        )
    if adherence_locked:
        response["adherence_lock"] = (
            "Prescription locked — bring adherence above 85% before adjustments resume"
        )
    if early_deload_recommended:
        response["early_deload_recommended"] = True
    if phase_mismatch:
        response["phase_mismatch"] = True
        response["phase_mismatch_detail"] = phase_mismatch_detail
    if lbm_risk:
        response["lbm_risk"] = True
        response["lbm_risk_detail"] = lbm_risk_detail

    # ── Build coaching feedback report ────────────────────────────────────
    feedback_items: list[dict] = []

    # Weight analysis
    bw_history_result2 = await db.execute(
        select(BodyWeightLog).where(BodyWeightLog.user_id == user.id)
        .order_by(desc(BodyWeightLog.recorded_date), desc(BodyWeightLog.created_at)).limit(14)
    )
    bw_hist = bw_history_result2.scalars().all()
    if len(bw_hist) >= 7:
        week1 = [b.weight_kg for b in bw_hist[:7]]
        week2 = [b.weight_kg for b in bw_hist[7:14]] if len(bw_hist) >= 10 else []
        avg1 = sum(week1) / len(week1)
        avg2 = sum(week2) / len(week2) if week2 else avg1
        delta = avg1 - avg2
        rate_lbs = delta * 2.20462
        if rx and rx.phase in ("cut", "peak"):
            if delta < -0.1:
                feedback_items.append({
                    "category": "weight",
                    "icon": "check",
                    "text": f"Weight trending down ({rate_lbs:+.1f} lbs/week). On track for prep.",
                })
            elif delta > 0.1:
                feedback_items.append({
                    "category": "weight",
                    "icon": "warning",
                    "text": f"Weight trending up ({rate_lbs:+.1f} lbs/week) during {rx.phase}. Review adherence or consider calorie reduction.",
                })
            else:
                feedback_items.append({
                    "category": "weight",
                    "icon": "info",
                    "text": "Weight stable this week. May need to increase deficit if progress has stalled.",
                })
        elif rx and rx.phase in ("bulk", "lean_bulk"):
            if 0 < delta <= 0.35:
                feedback_items.append({
                    "category": "weight",
                    "icon": "check",
                    "text": f"Weight gaining at a controlled rate ({rate_lbs:+.1f} lbs/week). Good surplus management.",
                })
            elif delta > 0.35:
                feedback_items.append({
                    "category": "weight",
                    "icon": "warning",
                    "text": f"Gaining too fast ({rate_lbs:+.1f} lbs/week). Risk of excess fat gain — consider reducing surplus.",
                })
            elif delta < -0.05:
                feedback_items.append({
                    "category": "weight",
                    "icon": "warning",
                    "text": f"Losing weight ({rate_lbs:+.1f} lbs/week) during bulk. Increase calories.",
                })

    # Adherence analysis
    if latest_adh:
        if latest_adh.overall_adherence_pct >= 90:
            feedback_items.append({
                "category": "adherence",
                "icon": "check",
                "text": f"Adherence excellent at {latest_adh.overall_adherence_pct:.0f}%. Keep it up.",
            })
        elif latest_adh.overall_adherence_pct >= 75:
            feedback_items.append({
                "category": "adherence",
                "icon": "info",
                "text": f"Adherence at {latest_adh.overall_adherence_pct:.0f}%. Room for improvement — consistency drives results.",
            })
        else:
            feedback_items.append({
                "category": "adherence",
                "icon": "warning",
                "text": f"Adherence low at {latest_adh.overall_adherence_pct:.0f}%. Macros locked until above 85%. Focus on hitting the plan.",
            })

    # Recovery / ARI analysis
    if ari_score is not None:
        if ari_zone == "green":
            feedback_items.append({
                "category": "recovery",
                "icon": "check",
                "text": f"Recovery optimal (ARI {ari_score}). Full volume prescribed for next week.",
            })
        elif ari_zone == "yellow":
            feedback_items.append({
                "category": "recovery",
                "icon": "info",
                "text": f"Recovery moderate (ARI {ari_score}). Volume maintained but watch sleep and stress.",
            })
        else:
            feedback_items.append({
                "category": "recovery",
                "icon": "warning",
                "text": f"Recovery compromised (ARI {ari_score}). Autoregulated volume reduction in effect.",
            })

    # Calorie changes for next week
    if calorie_adjustment:
        direction = "increased" if calorie_adjustment > 0 else "decreased"
        feedback_items.append({
            "category": "nutrition",
            "icon": "change",
            "text": f"Calories {direction} by {abs(int(calorie_adjustment))} kcal/day for the upcoming week based on your weight trend.",
        })
    elif rx and not adherence_locked:
        feedback_items.append({
            "category": "nutrition",
            "icon": "check",
            "text": "No calorie changes needed. Current prescription maintained for next week.",
        })

    # Deload recommendation
    if early_deload_recommended:
        feedback_items.append({
            "category": "training",
            "icon": "warning",
            "text": "ARI has been red zone for 5+ days. Deload recommended next week — reduce volume 40% and intensity 10%.",
        })

    # PDS progress
    if engine1_result and engine1_result.get("pds"):
        pds_data = engine1_result["pds"]
        feedback_items.append({
            "category": "physique",
            "icon": "info",
            "text": f"Physique Development Score: {pds_data['score']} ({pds_data.get('tier', 'N/A')} tier).",
        })

    # Phase mismatch
    if phase_mismatch:
        feedback_items.append({
            "category": "phase",
            "icon": "warning",
            "text": phase_mismatch_detail,
        })

    # LBM risk
    if lbm_risk:
        feedback_items.append({
            "category": "muscle_preservation",
            "icon": "warning",
            "text": lbm_risk_detail,
        })

    response["feedback_report"] = {
        "week": week_number,
        "summary": f"Week {week_number} analysis complete. {len([f for f in feedback_items if f['icon'] == 'check'])} items on track, {len([f for f in feedback_items if f['icon'] == 'warning'])} items need attention.",
        "items": feedback_items,
    }

    return response





@router.get("/posing-recommendation")
async def get_posing_recommendation_endpoint(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return posing practice recommendations based on division and competition proximity."""
    profile_result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == user.id)
    )
    profile = profile_result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Complete onboarding first")

    division = (profile.preferences or {}).get("division", "mens_open")
    weeks_out = None
    if profile.competition_date:
        delta = (profile.competition_date - date.today()).days
        weeks_out = max(0, delta // 7)

    from app.constants.posing import get_posing_recommendation
    return get_posing_recommendation(division, weeks_out)


@router.get("/timeline")
async def get_timeline(
    days: int = 365,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return a comprehensive timeline of all check-ins, weight, and key metrics."""
    from sqlalchemy import and_
    from app.models.diagnostic import PDSLog

    cutoff = date.today() - timedelta(days=days)

    # Weight history
    bw_result = await db.execute(
        select(BodyWeightLog)
        .where(and_(BodyWeightLog.user_id == user.id, BodyWeightLog.recorded_date >= cutoff))
        .order_by(BodyWeightLog.recorded_date)
    )
    bw_logs = bw_result.scalars().all()

    # Weekly check-ins
    checkin_result = await db.execute(
        select(WeeklyCheckin)
        .where(and_(WeeklyCheckin.user_id == user.id, WeeklyCheckin.checkin_date >= cutoff))
        .order_by(WeeklyCheckin.checkin_date)
    )
    checkins = checkin_result.scalars().all()

    # Daily HRV/notes
    from app.models.training import HRVLog
    hrv_result = await db.execute(
        select(HRVLog)
        .where(and_(HRVLog.user_id == user.id, HRVLog.recorded_date >= cutoff))
        .order_by(HRVLog.recorded_date)
    )
    hrv_logs = hrv_result.scalars().all()

    # PDS history
    pds_result = await db.execute(
        select(PDSLog)
        .where(and_(PDSLog.user_id == user.id, PDSLog.recorded_date >= cutoff))
        .order_by(PDSLog.recorded_date)
    )
    pds_logs = pds_result.scalars().all()

    # Build timeline entries
    entries = []

    for bw in bw_logs:
        entries.append({
            "date": str(bw.recorded_date),
            "type": "weight",
            "weight_kg": bw.weight_kg,
        })

    for c in checkins:
        entry: dict = {
            "date": str(c.checkin_date),
            "type": "weekly_checkin",
            "week_number": c.week_number,
            "body_weight_kg": c.body_weight_kg,
            "pds_score": c.pds_score,
            "ari_score": c.ari_score,
            "nutrition_adherence_pct": c.nutrition_adherence_pct,
            "training_adherence_pct": c.training_adherence_pct,
            "notes": c.notes,
            "photos": {
                "front": c.front_photo_url,
                "back": c.back_photo_url,
                "side_left": c.side_left_photo_url,
                "side_right": c.side_right_photo_url,
                "front_pose": c.front_pose_photo_url,
                "back_pose": c.back_pose_photo_url,
            },
        }
        entries.append(entry)

    for h in hrv_logs:
        entry = {
            "date": str(h.recorded_date),
            "type": "daily_checkin",
            "rmssd": h.rmssd,
            "sleep_quality": h.sleep_quality,
            "soreness_score": h.soreness_score,
            "notes": h.notes,
        }
        entries.append(entry)

    for p in pds_logs:
        entries.append({
            "date": str(p.recorded_date),
            "type": "pds",
            "pds_score": p.pds_score,
            "tier": p.tier,
        })

    # Deduplicate: remove standalone weight entries for dates that already have
    # a daily or weekly check-in (which embed weight data)
    checkin_dates = {e["date"] for e in entries if e["type"] in ("daily_checkin", "weekly_checkin")}
    entries = [e for e in entries if not (e["type"] == "weight" and e["date"] in checkin_dates)]

    # Deduplicate: remove standalone PDS entries for dates that have a weekly check-in
    weekly_dates = {e["date"] for e in entries if e["type"] == "weekly_checkin"}
    entries = [e for e in entries if not (e["type"] == "pds" and e["date"] in weekly_dates)]

    # Sort all entries by date (most recent first)
    entries.sort(key=lambda e: e["date"], reverse=True)

    return {"entries": entries}


@router.get("/weight-history")
async def get_weight_history(
    days: int = 90,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import and_

    cutoff = date.today() - timedelta(days=days)
    result = await db.execute(
        select(BodyWeightLog)
        .where(and_(BodyWeightLog.user_id == user.id, BodyWeightLog.recorded_date >= cutoff))
        .order_by(BodyWeightLog.recorded_date)
    )
    logs = result.scalars().all()
    return [{"date": str(bw.recorded_date), "weight_kg": bw.weight_kg} for bw in logs]


@router.get("/weekly/previous")
async def get_previous_weekly(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Fetch the latest tape and skinfold measurements for ghost gap auto-prefill"""
    tape_result = await db.execute(
        select(TapeMeasurement)
        .where(TapeMeasurement.user_id == user.id)
        .order_by(desc(TapeMeasurement.recorded_date), desc(TapeMeasurement.created_at))
        .limit(1)
    )
    latest_tape = tape_result.scalar_one_or_none()

    sf_result = await db.execute(
        select(SkinfoldMeasurement)
        .where(SkinfoldMeasurement.user_id == user.id)
        .order_by(desc(SkinfoldMeasurement.recorded_date), desc(SkinfoldMeasurement.created_at))
        .limit(1)
    )
    latest_sf = sf_result.scalar_one_or_none()

    tape_dict = {}
    if latest_tape:
        tape_dict = {
            col.name: getattr(latest_tape, col.name)
            for col in latest_tape.__table__.columns
            if col.name not in ('id', 'user_id', 'recorded_date', 'created_at') and getattr(latest_tape, col.name) is not None
        }

    sf_dict = {}
    if latest_sf:
        sf_dict = {
            col.name: getattr(latest_sf, col.name)
            for col in latest_sf.__table__.columns
            if col.name not in ('id', 'user_id', 'recorded_date', 'created_at', 'body_fat_pct') and getattr(latest_sf, col.name) is not None
        }

    return {"tape": tape_dict, "skinfolds": sf_dict}


# ---------------------------------------------------------------------------
# Weekly review — coaching heartbeat aggregation
# ---------------------------------------------------------------------------

@router.get("/weekly/review")
async def get_weekly_review(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Build a weekly review aggregation for the most recent complete week.
    Combines weight trend, training summary, nutrition adherence, photos,
    and PDS engine changes into a single coaching heartbeat payload.
    """
    from collections import defaultdict
    from app.models.training import TrainingSession, TrainingSet, TrainingProgram
    from app.models.diagnostic import PDSLog

    today = date.today()

    # -----------------------------------------------------------------------
    # 1. Weight trend: last 14 days of body weight with 7-day rolling average
    # -----------------------------------------------------------------------
    cutoff_14d = today - timedelta(days=14)
    bw_result = await db.execute(
        select(BodyWeightLog)
        .where(BodyWeightLog.user_id == user.id, BodyWeightLog.recorded_date >= cutoff_14d)
        .order_by(BodyWeightLog.recorded_date)
    )
    bw_logs = bw_result.scalars().all()

    weight_trend = []
    for i, bw in enumerate(bw_logs):
        # Compute rolling 7-day average using available prior entries
        window_start = max(0, i - 6)
        window = bw_logs[window_start : i + 1]
        rolling_avg = round(sum(w.weight_kg for w in window) / len(window), 2)
        weight_trend.append({
            "date": str(bw.recorded_date),
            "weight_kg": bw.weight_kg,
            "rolling_avg": rolling_avg,
        })

    # Current week avg (last 7 days) vs previous week avg (days 8-14)
    cutoff_7d = today - timedelta(days=7)
    current_week_weights = [bw.weight_kg for bw in bw_logs if bw.recorded_date > cutoff_7d]
    previous_week_weights = [bw.weight_kg for bw in bw_logs if bw.recorded_date <= cutoff_7d]

    current_avg = round(sum(current_week_weights) / len(current_week_weights), 2) if current_week_weights else None
    previous_avg = round(sum(previous_week_weights) / len(previous_week_weights), 2) if previous_week_weights else None
    delta_kg = round(current_avg - previous_avg, 2) if current_avg is not None and previous_avg is not None else None

    weight_section = {
        "current_avg": current_avg,
        "previous_avg": previous_avg,
        "delta_kg": delta_kg,
        "trend": weight_trend,
    }

    # -----------------------------------------------------------------------
    # 2. Training summary: sessions completed vs scheduled this week, total volume
    # -----------------------------------------------------------------------
    # Determine the most recent Monday as the start of the current week
    days_since_monday = today.weekday()  # Monday=0, Sunday=6
    week_start = today - timedelta(days=days_since_monday)
    week_end = week_start + timedelta(days=6)

    # Scheduled sessions this week
    scheduled_result = await db.execute(
        select(func.count())
        .select_from(TrainingSession)
        .where(
            TrainingSession.user_id == user.id,
            TrainingSession.session_date >= week_start,
            TrainingSession.session_date <= week_end,
        )
    )
    sessions_scheduled = scheduled_result.scalar() or 0

    # Completed sessions this week
    completed_result = await db.execute(
        select(func.count())
        .select_from(TrainingSession)
        .where(
            TrainingSession.user_id == user.id,
            TrainingSession.session_date >= week_start,
            TrainingSession.session_date <= week_end,
            TrainingSession.completed == True,
        )
    )
    sessions_completed = completed_result.scalar() or 0

    completion_pct = round((sessions_completed / sessions_scheduled) * 100) if sessions_scheduled > 0 else 0

    # Total working sets this week (non-warmup, from completed sessions)
    total_sets_result = await db.execute(
        select(func.count())
        .select_from(TrainingSet)
        .join(TrainingSession, TrainingSet.session_id == TrainingSession.id)
        .where(
            TrainingSession.user_id == user.id,
            TrainingSession.session_date >= week_start,
            TrainingSession.session_date <= week_end,
            TrainingSession.completed == True,
            TrainingSet.is_warmup == False,
        )
    )
    total_sets = total_sets_result.scalar() or 0

    training_section = {
        "sessions_completed": sessions_completed,
        "sessions_scheduled": sessions_scheduled,
        "completion_pct": completion_pct,
        "total_sets": total_sets,
    }

    # -----------------------------------------------------------------------
    # 3. Nutrition adherence: last 7 days from adherence_log
    # -----------------------------------------------------------------------
    adh_result = await db.execute(
        select(AdherenceLog)
        .where(AdherenceLog.user_id == user.id, AdherenceLog.recorded_date >= cutoff_7d)
        .order_by(AdherenceLog.recorded_date)
    )
    adh_logs = adh_result.scalars().all()

    adh_entries = [
        {
            "date": str(a.recorded_date),
            "nutrition": a.nutrition_adherence_pct,
            "training": a.training_adherence_pct,
            "overall": a.overall_adherence_pct,
        }
        for a in adh_logs
    ]

    avg_adherence_pct = (
        round(sum(a.overall_adherence_pct for a in adh_logs) / len(adh_logs), 1)
        if adh_logs else None
    )

    nutrition_section = {
        "avg_adherence_pct": avg_adherence_pct,
        "days_logged": len(adh_logs),
        "entries": adh_entries,
    }

    # -----------------------------------------------------------------------
    # 4. Photos: most recent weekly_checkins photos
    # -----------------------------------------------------------------------
    checkin_result = await db.execute(
        select(WeeklyCheckin)
        .where(WeeklyCheckin.user_id == user.id)
        .order_by(desc(WeeklyCheckin.checkin_date), desc(WeeklyCheckin.created_at))
        .limit(1)
    )
    latest_checkin = checkin_result.scalar_one_or_none()

    photos_section = {
        "front_photo_url": latest_checkin.front_photo_url if latest_checkin else None,
        "back_photo_url": latest_checkin.back_photo_url if latest_checkin else None,
        "side_left_photo_url": latest_checkin.side_left_photo_url if latest_checkin else None,
        "side_right_photo_url": latest_checkin.side_right_photo_url if latest_checkin else None,
    }

    # -----------------------------------------------------------------------
    # 5. Engine changes: latest PDS score vs previous
    # -----------------------------------------------------------------------
    pds_result = await db.execute(
        select(PDSLog)
        .where(PDSLog.user_id == user.id)
        .order_by(desc(PDSLog.recorded_date), desc(PDSLog.created_at))
        .limit(2)
    )
    pds_logs = pds_result.scalars().all()

    if pds_logs:
        current_pds = pds_logs[0]
        previous_pds = pds_logs[1] if len(pds_logs) > 1 else None
        pds_section = {
            "current": current_pds.pds_score,
            "previous": previous_pds.pds_score if previous_pds else None,
            "delta": round(current_pds.pds_score - previous_pds.pds_score, 2) if previous_pds else None,
            "tier": current_pds.tier,
        }
    else:
        pds_section = {
            "current": None,
            "previous": None,
            "delta": None,
            "tier": None,
        }

    # -----------------------------------------------------------------------
    # Determine the week number from the latest check-in or fallback to ISO week
    # -----------------------------------------------------------------------
    week_number = latest_checkin.week_number if latest_checkin else today.isocalendar()[1]

    return {
        "week_number": week_number,
        "weight": weight_section,
        "training": training_section,
        "nutrition": nutrition_section,
        "photos": photos_section,
        "pds": pds_section,
    }


# ---------------------------------------------------------------------------
# Block 4 — Missed Check-In Handling
# ---------------------------------------------------------------------------


@router.get("/gaps")
async def get_checkin_gaps(
    since: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns dates with missing daily check-ins and missed workout sessions
    since the given date (default: 14 days ago).
    """
    from app.models.training import TrainingSession
    from sqlalchemy import and_

    today_date = date.today()

    # Default cutoff = 14 days ago, clamped so we never report gaps before
    # the program actually started (otherwise new users see a missing-checkin
    # banner the moment they finish onboarding).
    profile_result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == user.id)
    )
    profile = profile_result.scalar_one_or_none()
    program_start = getattr(profile, "program_start_date", None) if profile else None

    default_cutoff = today_date - timedelta(days=14)
    if program_start and program_start > default_cutoff:
        default_cutoff = program_start
    cutoff = date.fromisoformat(since) if since else default_cutoff
    if program_start and cutoff < program_start:
        cutoff = program_start
    if cutoff > today_date:
        # Program hasn't started yet — nothing to check.
        return {
            "missing_daily_checkins": [],
            "missing_weight_entries": [],
            "missed_workouts": [],
            "since": str(cutoff),
            "total_gaps": 0,
        }

    # Find all dates that SHOULD have check-ins (every day since cutoff)
    all_dates = []
    d = cutoff
    while d <= today_date:
        all_dates.append(d)
        d += timedelta(days=1)

    # Dates with daily check-ins (HRV log entries)
    hrv_result = await db.execute(
        select(HRVLog.recorded_date).where(
            and_(HRVLog.user_id == user.id, HRVLog.recorded_date >= cutoff)
        )
    )
    checkin_dates = {row[0] for row in hrv_result.all()}

    # Dates with body weight entries
    bw_result = await db.execute(
        select(BodyWeightLog.recorded_date).where(
            and_(BodyWeightLog.user_id == user.id, BodyWeightLog.recorded_date >= cutoff)
        )
    )
    weight_dates = {row[0] for row in bw_result.all()}

    # Workout sessions that should have been completed
    session_result = await db.execute(
        select(TrainingSession.session_date, TrainingSession.completed).where(
            and_(
                TrainingSession.user_id == user.id,
                TrainingSession.session_date >= cutoff,
                TrainingSession.session_date <= today_date,
            )
        )
    )
    missed_workouts = []
    for sess_date, completed in session_result.all():
        if not completed and sess_date < today_date:
            missed_workouts.append(str(sess_date))

    missing_daily = [str(d) for d in all_dates if d not in checkin_dates and d < today_date]
    missing_weight = [str(d) for d in all_dates if d not in weight_dates and d < today_date]

    return {
        "missing_daily_checkins": missing_daily,
        "missing_weight_entries": missing_weight,
        "missed_workouts": missed_workouts,
        "since": str(cutoff),
        "total_gaps": len(missing_daily) + len(missed_workouts),
    }


@router.get("/recovery/trend")
async def get_recovery_trend(
    days: int = 30,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Return the ARI composite recovery score per day for the last N days.
    Falls back to a raw HRV-derived estimate when no ARI entry exists.
    """
    cutoff = date.today() - timedelta(days=max(1, min(days, 365)))

    ari_result = await db.execute(
        select(ARILog.recorded_date, ARILog.ari_score)
        .where(ARILog.user_id == user.id, ARILog.recorded_date >= cutoff)
        .order_by(ARILog.recorded_date)
    )
    ari_rows = ari_result.all()

    if ari_rows:
        return {
            "data": [
                {"date": str(d), "score": round(float(s), 1)}
                for d, s in ari_rows
            ]
        }

    # Fallback: derive a rough score from HRV + sleep + soreness (no ARI yet).
    hrv_result = await db.execute(
        select(HRVLog.recorded_date, HRVLog.rmssd, HRVLog.sleep_quality, HRVLog.soreness_score)
        .where(HRVLog.user_id == user.id, HRVLog.recorded_date >= cutoff)
        .order_by(HRVLog.recorded_date)
    )
    fallback = []
    for d, rmssd, sleep_q, sore in hrv_result.all():
        # Normalize: rmssd 20-80 → 0-100, sleep 1-10 → 0-100, soreness 1-10 inverted.
        hrv_pct = max(0.0, min(100.0, ((rmssd - 20) / 60) * 100)) if rmssd is not None else 50.0
        sleep_pct = (float(sleep_q) * 10) if sleep_q is not None else 50.0
        sore_pct = ((10 - float(sore)) * 10) if sore is not None else 50.0
        score = 0.5 * hrv_pct + 0.3 * sleep_pct + 0.2 * sore_pct
        fallback.append({"date": str(d), "score": round(score, 1)})
    return {"data": fallback}


class DailyBackfillRequest(BaseModel):
    recorded_date: str
    body_weight_kg: float | None = None
    sleep_quality: float | None = None
    soreness_score: float | None = None
    nutrition_adherence_pct: float | None = None
    training_adherence_pct: float | None = None
    notes: str | None = None


@router.post("/daily/backfill")
async def backfill_daily(
    data: DailyBackfillRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Backfill a missed daily check-in for a past date.
    Creates HRV log (with defaults for missing fields), body weight, and adherence entries.
    """
    rec_date = date.fromisoformat(data.recorded_date)
    if rec_date >= date.today():
        raise HTTPException(status_code=400, detail="Can only backfill past dates")

    # Body weight
    if data.body_weight_kg:
        existing = await db.execute(
            select(BodyWeightLog).where(
                BodyWeightLog.user_id == user.id, BodyWeightLog.recorded_date == rec_date
            )
        )
        if old := existing.scalar_one_or_none():
            await db.delete(old)
        db.add(BodyWeightLog(user_id=user.id, weight_kg=data.body_weight_kg, recorded_date=rec_date))

    # HRV log with sensible defaults
    existing_hrv = await db.execute(
        select(HRVLog).where(HRVLog.user_id == user.id, HRVLog.recorded_date == rec_date)
    )
    if old := existing_hrv.scalar_one_or_none():
        await db.delete(old)
    db.add(HRVLog(
        user_id=user.id,
        rmssd=50.0,  # default
        sleep_quality=data.sleep_quality or 7.0,
        soreness_score=data.soreness_score or 5.0,
        recorded_date=rec_date,
        notes=data.notes or "Backfilled",
    ))

    # Adherence log — BUG-02 fix: delete duplicates before inserting
    existing_adh = await db.execute(
        select(AdherenceLog).where(
            AdherenceLog.user_id == user.id, AdherenceLog.recorded_date == rec_date
        )
    )
    for dup in existing_adh.scalars().all():
        await db.delete(dup)

    nut_pct = data.nutrition_adherence_pct or 80.0
    trn_pct = data.training_adherence_pct or 80.0
    db.add(AdherenceLog(
        user_id=user.id,
        recorded_date=rec_date,
        nutrition_adherence_pct=nut_pct,
        training_adherence_pct=trn_pct,
        overall_adherence_pct=(nut_pct + trn_pct) / 2,
    ))

    await db.flush()
    return {"message": f"Backfilled check-in for {data.recorded_date}", "date": data.recorded_date}


@router.post("/adherence/dedupe")
async def dedupe_adherence(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """BUG-02 fix: Detect and delete duplicate AdherenceLog entries per date."""
    from sqlalchemy import and_

    result = await db.execute(
        select(AdherenceLog.recorded_date, func.count(AdherenceLog.id).label("cnt"))
        .where(AdherenceLog.user_id == user.id)
        .group_by(AdherenceLog.recorded_date)
        .having(func.count(AdherenceLog.id) > 1)
    )
    dup_dates = [row[0] for row in result.all()]
    deleted = 0

    for dup_date in dup_dates:
        entries = await db.execute(
            select(AdherenceLog).where(
                and_(AdherenceLog.user_id == user.id, AdherenceLog.recorded_date == dup_date)
            ).order_by(desc(AdherenceLog.created_at))
        )
        all_entries = entries.scalars().all()
        # Keep the most recent, delete the rest
        for old in all_entries[1:]:
            await db.delete(old)
            deleted += 1

    await db.flush()
    return {"duplicates_removed": deleted, "dates_affected": len(dup_dates)}


@router.get("/sleep-week")
async def get_sleep_week(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the last 7 days of sleep quality + hours for the dashboard widget.

    Fills null entries for days that have no HRV log, so the frontend can render
    a muted "no data" cell instead of collapsing the bar chart.
    """
    today = date.today()
    start = today - timedelta(days=6)
    rows_result = await db.execute(
        select(HRVLog)
        .where(
            HRVLog.user_id == user.id,
            HRVLog.recorded_date >= start,
            HRVLog.recorded_date <= today,
        )
        .order_by(desc(HRVLog.recorded_date), desc(HRVLog.created_at))
    )
    rows = rows_result.scalars().all()
    latest_per_day: dict[date, HRVLog] = {}
    for row in rows:
        latest_per_day.setdefault(row.recorded_date, row)

    days = []
    for i in range(7):
        d = start + timedelta(days=i)
        row = latest_per_day.get(d)
        days.append({
            "date": d.isoformat(),
            "weekday": d.strftime("%a"),
            "quality": float(row.sleep_quality) if row and row.sleep_quality is not None else None,
            "hours": float(row.sleep_hours) if row and row.sleep_hours is not None else None,
        })
    logged = [d for d in days if d["quality"] is not None]
    avg_quality = round(sum(d["quality"] for d in logged) / len(logged), 1) if logged else None
    avg_hours = round(
        sum(d["hours"] for d in logged if d["hours"] is not None)
        / max(1, sum(1 for d in logged if d["hours"] is not None)),
        1,
    ) if logged else None
    return {
        "days": days,
        "avg_quality": avg_quality,
        "avg_hours": avg_hours,
        "logged_count": len(logged),
    }
