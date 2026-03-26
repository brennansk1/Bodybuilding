"""
Admin API — System maintenance, health checks, and user management.

All endpoints require admin authentication (coronado_admin account).
These run background cleanup tasks similar to `doctor --fix`.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete, func, text, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.profile import UserProfile
from app.models.training import (
    TrainingSession, TrainingSet, TrainingProgram,
    Exercise, StrengthBaseline, StrengthLog,
)
from app.models.measurement import BodyWeightLog, TapeMeasurement, SkinfoldMeasurement
from app.models.nutrition import (
    NutritionPrescription, AdherenceLog, WeeklyCheckin,
    NutritionLog, MealPlanTemplate,
)
from app.models.diagnostic import PDSLog, LCSALog, HQILog
from app.models.training import ARILog

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])

ADMIN_USERNAME = "coronado_admin"


def _require_admin(user: User):
    """Raise 403 if the user is not the admin account."""
    if user.username != ADMIN_USERNAME:
        raise HTTPException(status_code=403, detail="Admin access required")


# ═══════════════════════════════════════════════════════════════════════════════
# SYSTEM HEALTH / DOCTOR
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/health")
async def system_health(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Full system health check — finds all issues without fixing them."""
    _require_admin(user)
    issues = []

    # 1. Orphaned sessions (sessions from inactive programs that aren't completed)
    orphan_count = await db.execute(
        select(func.count()).select_from(TrainingSession)
        .join(TrainingProgram, TrainingSession.program_id == TrainingProgram.id)
        .where(TrainingProgram.is_active == False, TrainingSession.completed == False)
    )
    orphans = orphan_count.scalar() or 0
    if orphans > 0:
        issues.append({
            "type": "orphaned_sessions",
            "severity": "warning",
            "count": orphans,
            "description": f"{orphans} uncompleted sessions from deactivated programs",
            "fix": "POST /admin/fix/orphaned-sessions",
        })

    # 2. Users without profiles
    no_profile = await db.execute(
        select(func.count()).select_from(User)
        .outerjoin(UserProfile, User.id == UserProfile.user_id)
        .where(UserProfile.id == None, User.is_active == True)
    )
    profileless = no_profile.scalar() or 0
    if profileless > 0:
        issues.append({
            "type": "users_without_profiles",
            "severity": "warning",
            "count": profileless,
            "description": f"{profileless} active users have no profile",
        })

    # 3. Stale programs (current_week > mesocycle_weeks)
    stale_prog = await db.execute(
        select(func.count()).select_from(TrainingProgram)
        .where(
            TrainingProgram.is_active == True,
            TrainingProgram.current_week > TrainingProgram.mesocycle_weeks,
        )
    )
    stale = stale_prog.scalar() or 0
    if stale > 0:
        issues.append({
            "type": "stale_programs",
            "severity": "info",
            "count": stale,
            "description": f"{stale} programs past their mesocycle length",
            "fix": "POST /admin/fix/stale-programs",
        })

    # 4. Sessions with no sets (in active programs)
    empty_sessions = await db.execute(
        select(func.count()).select_from(TrainingSession)
        .join(TrainingProgram, TrainingSession.program_id == TrainingProgram.id)
        .outerjoin(TrainingSet, TrainingSet.session_id == TrainingSession.id)
        .where(
            TrainingProgram.is_active == True,
            TrainingSession.completed == False,
            TrainingSet.id == None,
        )
    )
    empty = empty_sessions.scalar() or 0
    if empty > 0:
        issues.append({
            "type": "empty_sessions",
            "severity": "warning",
            "count": empty,
            "description": f"{empty} scheduled sessions have no exercises assigned",
        })

    # 5. Users without active nutrition prescription
    no_rx = await db.execute(
        select(func.count()).select_from(User)
        .where(User.onboarding_complete == True)
        .outerjoin(
            NutritionPrescription,
            (NutritionPrescription.user_id == User.id) & (NutritionPrescription.is_active == True),
        )
        .where(NutritionPrescription.id == None)
    )
    no_rx_count = no_rx.scalar() or 0
    if no_rx_count > 0:
        issues.append({
            "type": "no_nutrition_rx",
            "severity": "warning",
            "count": no_rx_count,
            "description": f"{no_rx_count} onboarded users have no active nutrition prescription",
            "fix": "/admin/fix/missing-nutrition",
        })

    # 6. Duplicate active programs per user
    dup_progs = await db.execute(
        select(TrainingProgram.user_id, func.count().label("cnt"))
        .where(TrainingProgram.is_active == True)
        .group_by(TrainingProgram.user_id)
        .having(func.count() > 1)
    )
    dups = dup_progs.all()
    if dups:
        issues.append({
            "type": "duplicate_active_programs",
            "severity": "error",
            "count": len(dups),
            "description": f"{len(dups)} users have multiple active programs",
            "fix": "POST /admin/fix/duplicate-programs",
        })

    # Summary
    total_users = (await db.execute(select(func.count()).select_from(User))).scalar() or 0
    total_sessions = (await db.execute(select(func.count()).select_from(TrainingSession))).scalar() or 0
    total_sets = (await db.execute(select(func.count()).select_from(TrainingSet))).scalar() or 0

    return {
        "status": "healthy" if not any(i["severity"] == "error" for i in issues) else "unhealthy",
        "issues": issues,
        "issue_count": len(issues),
        "stats": {
            "total_users": total_users,
            "total_sessions": total_sessions,
            "total_sets": total_sets,
        },
    }


# ═══════════════════════════════════════════════════════════════════════════════
# FIX ENDPOINTS (doctor --fix)
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/fix/orphaned-sessions")
async def fix_orphaned_sessions(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete uncompleted sessions from deactivated programs."""
    _require_admin(user)

    # Find inactive program IDs
    inactive = await db.execute(
        select(TrainingProgram.id).where(TrainingProgram.is_active == False)
    )
    inactive_ids = [r[0] for r in inactive.all()]

    if not inactive_ids:
        return {"fixed": 0, "message": "No inactive programs found"}

    # Delete sets from orphaned sessions first (cascade)
    for prog_id in inactive_ids:
        orphan_sessions = await db.execute(
            select(TrainingSession.id).where(
                TrainingSession.program_id == prog_id,
                TrainingSession.completed == False,
            )
        )
        session_ids = [r[0] for r in orphan_sessions.all()]
        if session_ids:
            await db.execute(
                delete(TrainingSet).where(TrainingSet.session_id.in_(session_ids))
            )
            await db.execute(
                delete(TrainingSession).where(TrainingSession.id.in_(session_ids))
            )

    await db.commit()
    return {"fixed": len(inactive_ids), "message": f"Cleaned orphaned sessions from {len(inactive_ids)} inactive programs"}


@router.post("/fix/stale-programs")
async def fix_stale_programs(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Deactivate programs that have exceeded their mesocycle length."""
    _require_admin(user)

    result = await db.execute(
        select(TrainingProgram).where(
            TrainingProgram.is_active == True,
            TrainingProgram.current_week > TrainingProgram.mesocycle_weeks,
        )
    )
    stale = result.scalars().all()
    for prog in stale:
        prog.is_active = False

    await db.commit()
    return {"fixed": len(stale), "message": f"Deactivated {len(stale)} stale programs"}


@router.post("/fix/duplicate-programs")
async def fix_duplicate_programs(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Keep only the newest active program per user, deactivate the rest."""
    _require_admin(user)

    dup_result = await db.execute(
        select(TrainingProgram.user_id, func.count().label("cnt"))
        .where(TrainingProgram.is_active == True)
        .group_by(TrainingProgram.user_id)
        .having(func.count() > 1)
    )
    dup_users = [r[0] for r in dup_result.all()]

    fixed = 0
    for uid in dup_users:
        progs = await db.execute(
            select(TrainingProgram)
            .where(TrainingProgram.user_id == uid, TrainingProgram.is_active == True)
            .order_by(desc(TrainingProgram.created_at))
        )
        all_progs = progs.scalars().all()
        # Keep the newest, deactivate the rest
        for prog in all_progs[1:]:
            prog.is_active = False
            fixed += 1

    await db.commit()
    return {"fixed": fixed, "message": f"Deactivated {fixed} duplicate programs"}


@router.post("/fix/missing-nutrition")
async def fix_missing_nutrition(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate nutrition prescriptions for onboarded users missing one."""
    _require_admin(user)
    from app.engines.engine3.macros import compute_tdee, compute_macros
    from app.engines.engine1.body_fat import lean_mass_kg

    # Find onboarded users without active nutrition rx
    result = await db.execute(
        select(User, UserProfile)
        .join(UserProfile, User.id == UserProfile.user_id)
        .outerjoin(
            NutritionPrescription,
            (NutritionPrescription.user_id == User.id) & (NutritionPrescription.is_active == True),
        )
        .where(User.onboarding_complete == True, NutritionPrescription.id == None)
    )
    rows = result.all()

    fixed = 0
    for u, profile in rows:
        # Get latest weight or use a default
        weight_r = await db.execute(
            select(BodyWeightLog.weight_kg)
            .where(BodyWeightLog.user_id == u.id)
            .order_by(desc(BodyWeightLog.recorded_date))
            .limit(1)
        )
        weight = weight_r.scalar() or 85.0  # fallback

        bf_pct = getattr(profile, "manual_body_fat_pct", None) or 15.0
        lbm = lean_mass_kg(weight, bf_pct)
        age = profile.age or 28
        sex = profile.sex or "male"
        phase = "maintain"
        activity_mult = 1.725 if (profile.days_per_week or 4) >= 5 else 1.55

        tdee = compute_tdee(weight, profile.height_cm, age, sex, activity_mult, lean_mass_kg=lbm)
        macros = compute_macros(tdee, phase, weight, sex, lean_mass_kg=lbm, body_fat_pct=bf_pct)

        rx = NutritionPrescription(
            user_id=u.id,
            tdee=round(tdee, 0),
            target_calories=round(macros["target_calories"], 0),
            protein_g=round(macros["protein_g"], 1),
            carbs_g=round(macros["carbs_g"], 1),
            fat_g=round(macros["fat_g"], 1),
            phase=phase,
            is_active=True,
        )
        db.add(rx)
        fixed += 1

    await db.commit()
    return {"fixed": fixed, "message": f"Generated nutrition prescriptions for {fixed} users"}


@router.post("/fix/all")
async def fix_all(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Run all fixes in sequence — the full doctor --fix."""
    _require_admin(user)
    results = []

    # Run each fix and collect results
    r1 = await fix_orphaned_sessions(user, db)
    results.append({"fix": "orphaned_sessions", **r1})

    r2 = await fix_stale_programs(user, db)
    results.append({"fix": "stale_programs", **r2})

    r3 = await fix_duplicate_programs(user, db)
    results.append({"fix": "duplicate_programs", **r3})

    r4 = await fix_missing_nutrition(user, db)
    results.append({"fix": "missing_nutrition", **r4})

    total_fixed = sum(r.get("fixed", 0) for r in results)
    return {
        "total_fixed": total_fixed,
        "results": results,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# CRON LOGS & MANUAL TRIGGER
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/cron/logs")
async def get_cron_logs_endpoint(
    user: User = Depends(get_current_user),
):
    """Return the last 100 cron log entries (newest first)."""
    _require_admin(user)
    from app.services.cron import get_cron_logs
    logs = get_cron_logs()
    return {"logs": logs, "count": len(logs)}


@router.post("/cron/run")
async def trigger_cron_manually(
    user: User = Depends(get_current_user),
):
    """Manually trigger a maintenance cycle."""
    _require_admin(user)
    from app.services.cron import run_maintenance_cycle
    await run_maintenance_cycle()
    from app.services.cron import get_cron_logs
    latest = get_cron_logs()
    return {"message": "Maintenance cycle completed", "latest_logs": latest[:6]}


# ═══════════════════════════════════════════════════════════════════════════════
# USER MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/users")
async def list_users(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all users with summary stats."""
    _require_admin(user)

    result = await db.execute(
        select(User, UserProfile)
        .outerjoin(UserProfile, User.id == UserProfile.user_id)
        .order_by(User.created_at)
    )
    rows = result.all()

    users = []
    for u, profile in rows:
        # Get latest weight
        weight_r = await db.execute(
            select(BodyWeightLog.weight_kg)
            .where(BodyWeightLog.user_id == u.id)
            .order_by(desc(BodyWeightLog.recorded_date))
            .limit(1)
        )
        latest_weight = weight_r.scalar()

        # Get latest PDS
        pds_r = await db.execute(
            select(PDSLog.pds_score, PDSLog.tier)
            .where(PDSLog.user_id == u.id)
            .order_by(desc(PDSLog.recorded_date))
            .limit(1)
        )
        pds_row = pds_r.first()

        # Count sessions
        sess_count = await db.execute(
            select(func.count()).select_from(TrainingSession)
            .where(TrainingSession.user_id == u.id, TrainingSession.completed == True)
        )

        users.append({
            "id": str(u.id),
            "username": u.username,
            "email": u.email,
            "is_active": u.is_active,
            "onboarding_complete": u.onboarding_complete,
            "created_at": str(u.created_at) if u.created_at else None,
            "division": profile.division if profile else None,
            "sex": profile.sex if profile else None,
            "height_cm": profile.height_cm if profile else None,
            "latest_weight_kg": latest_weight,
            "latest_pds": pds_row[0] if pds_row else None,
            "latest_tier": pds_row[1] if pds_row else None,
            "completed_sessions": sess_count.scalar() or 0,
        })

    return {"users": users, "total": len(users)}


@router.get("/users/{user_id}/detail")
async def user_detail(
    user_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Detailed view of a single user's data."""
    _require_admin(user)
    import uuid
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID")

    target_r = await db.execute(select(User).where(User.id == uid))
    target = target_r.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    profile_r = await db.execute(select(UserProfile).where(UserProfile.user_id == uid))
    profile = profile_r.scalar_one_or_none()

    # Counts
    weights = (await db.execute(
        select(func.count()).select_from(BodyWeightLog).where(BodyWeightLog.user_id == uid)
    )).scalar() or 0
    sessions = (await db.execute(
        select(func.count()).select_from(TrainingSession).where(TrainingSession.user_id == uid)
    )).scalar() or 0
    completed = (await db.execute(
        select(func.count()).select_from(TrainingSession)
        .where(TrainingSession.user_id == uid, TrainingSession.completed == True)
    )).scalar() or 0
    checkins = (await db.execute(
        select(func.count()).select_from(WeeklyCheckin).where(WeeklyCheckin.user_id == uid)
    )).scalar() or 0
    pds_entries = (await db.execute(
        select(func.count()).select_from(PDSLog).where(PDSLog.user_id == uid)
    )).scalar() or 0

    # Active program
    prog_r = await db.execute(
        select(TrainingProgram).where(TrainingProgram.user_id == uid, TrainingProgram.is_active == True)
    )
    active_prog = prog_r.scalar_one_or_none()

    # Active nutrition
    rx_r = await db.execute(
        select(NutritionPrescription)
        .where(NutritionPrescription.user_id == uid, NutritionPrescription.is_active == True)
        .limit(1)
    )
    rx = rx_r.scalar_one_or_none()

    return {
        "user": {
            "id": str(target.id),
            "username": target.username,
            "email": target.email,
            "is_active": target.is_active,
            "onboarding_complete": target.onboarding_complete,
        },
        "profile": {
            "division": profile.division if profile else None,
            "sex": profile.sex if profile else None,
            "age": profile.age if profile else None,
            "height_cm": profile.height_cm if profile else None,
            "competition_date": str(profile.competition_date) if profile and profile.competition_date else None,
            "training_years": profile.training_experience_years if profile else None,
            "days_per_week": profile.days_per_week if profile else None,
        } if profile else None,
        "data_counts": {
            "weight_entries": weights,
            "total_sessions": sessions,
            "completed_sessions": completed,
            "weekly_checkins": checkins,
            "pds_entries": pds_entries,
        },
        "active_program": {
            "name": active_prog.name,
            "split": active_prog.split_type,
            "week": f"{active_prog.current_week}/{active_prog.mesocycle_weeks}",
        } if active_prog else None,
        "nutrition": {
            "calories": rx.target_calories,
            "protein_g": rx.protein_g,
            "carbs_g": rx.carbs_g,
            "fat_g": rx.fat_g,
            "phase": rx.phase,
        } if rx else None,
    }
