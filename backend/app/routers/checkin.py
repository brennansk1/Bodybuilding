from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
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
from app.schemas.checkin import DailyCheckin, WeeklyCheckinRequest
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
        soreness_score=soreness_score,
        sore_muscles=data.sore_muscles,
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

    # Compute ARI to feedback immediately
    baseline_result = await db.execute(
        select(HRVLog).where(HRVLog.user_id == user.id)
        .order_by(desc(HRVLog.recorded_date), desc(HRVLog.created_at)).limit(14)
    )
    hrv_history = baseline_result.scalars().all()
    baseline_rmssd = sum(h.rmssd for h in hrv_history) / len(hrv_history) if hrv_history else rmssd

    from app.engines.engine2.ari import compute_ari, get_ari_zone
    ari_score = compute_ari(
        rmssd=rmssd,
        resting_hr=data.resting_hr or 60,
        sleep_quality_1_10=sleep_quality,
        soreness_1_10=soreness_score,
        baseline_rmssd=baseline_rmssd,
    )
    ari_zone = get_ari_zone(ari_score)

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

    return {
        "message": "Daily check-in saved",
        "weight_kg": weight_kg,
        "ari_score": ari_score,
        "zone": ari_zone,
        "autoregulation": autoreg_msg,
    }


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
        baseline_result = await db.execute(
            select(HRVLog).where(HRVLog.user_id == user.id)
            .order_by(desc(HRVLog.recorded_date), desc(HRVLog.created_at)).limit(14)
        )
        hrv_history = baseline_result.scalars().all()
        baseline_rmssd = sum(h.rmssd for h in hrv_history) / len(hrv_history)
        hr_values = [h.resting_hr for h in hrv_history if h.resting_hr]
        baseline_hr = sum(hr_values) / len(hr_values) if hr_values else None

        soreness = getattr(latest_hrv, "soreness_score", None) or 5.0

        from app.engines.engine2.ari import (
            compute_ari, get_ari_zone,
            _hrv_score, _sleep_score, _soreness_score,
        )
        ari_score = compute_ari(
            rmssd=latest_hrv.rmssd,
            resting_hr=latest_hrv.resting_hr or 60,
            sleep_quality_1_10=latest_hrv.sleep_quality or 7,
            soreness_1_10=soreness,
            baseline_rmssd=baseline_rmssd,
            baseline_hr=baseline_hr,
        )
        ari_zone = get_ari_zone(ari_score)

        ari_log = ARILog(
            user_id=user.id,
            ari_score=ari_score,
            hrv_component=_hrv_score(latest_hrv.rmssd, baseline_rmssd),
            sleep_component=_sleep_score(latest_hrv.sleep_quality or 7),
            soreness_component=_soreness_score(soreness),
            recorded_date=today,
        )
        db.add(ari_log)

    # Early deload detection: last 5 ARI logs
    early_deload_recommended = False
    ari_history_result = await db.execute(
        select(ARILog).where(ARILog.user_id == user.id)
        .order_by(desc(ARILog.recorded_date), desc(ARILog.created_at)).limit(5)
    )
    recent_ari_logs = ari_history_result.scalars().all()
    if len(recent_ari_logs) >= 5 and all(a.ari_score < 40 for a in recent_ari_logs):
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

    return response





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
