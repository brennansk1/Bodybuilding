"""
Background Cron Service — Automated maintenance tasks.

Runs on a configurable interval (default: every 6 hours) inside the
FastAPI process. Logs results to an in-memory ring buffer that the
admin dashboard can query.

Tasks:
  1. Orphan cleanup — remove uncompleted sessions from inactive programs
  2. Stale program check — deactivate programs past their mesocycle length
  3. Duplicate program fix — keep only newest active program per user
  4. Data integrity check — flag empty sessions, missing profiles, etc.
"""
from __future__ import annotations

import asyncio
import logging
from collections import deque
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, delete, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models.training import TrainingSession, TrainingSet, TrainingProgram
from app.models.user import User
from app.models.profile import UserProfile
from app.models.nutrition import NutritionPrescription
from app.models.measurement import BodyWeightLog

logger = logging.getLogger(__name__)

# In-memory log buffer — last 100 entries, queryable from admin API
MAX_LOG_ENTRIES = 100
_cron_logs: deque[dict[str, Any]] = deque(maxlen=MAX_LOG_ENTRIES)


def get_cron_logs() -> list[dict[str, Any]]:
    """Return cron logs newest-first."""
    return list(reversed(_cron_logs))


def _log(task: str, status: str, detail: str, fixed: int = 0):
    """Add an entry to the cron log buffer."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "task": task,
        "status": status,
        "detail": detail,
        "fixed": fixed,
    }
    _cron_logs.append(entry)
    logger.info("CRON [%s] %s: %s (fixed: %d)", task, status, detail, fixed)


async def _cleanup_orphaned_sessions(db: AsyncSession) -> int:
    """Remove uncompleted sessions from deactivated programs."""
    inactive = await db.execute(
        select(TrainingProgram.id).where(TrainingProgram.is_active == False)
    )
    inactive_ids = [r[0] for r in inactive.all()]
    if not inactive_ids:
        return 0

    total_cleaned = 0
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
            total_cleaned += len(session_ids)
    return total_cleaned


async def _fix_stale_programs(db: AsyncSession) -> int:
    """Deactivate programs that have exceeded their mesocycle length."""
    result = await db.execute(
        select(TrainingProgram).where(
            TrainingProgram.is_active == True,
            TrainingProgram.current_week > TrainingProgram.mesocycle_weeks,
        )
    )
    stale = result.scalars().all()
    for prog in stale:
        prog.is_active = False
    return len(stale)


async def _fix_duplicate_programs(db: AsyncSession) -> int:
    """Keep only the newest active program per user."""
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
        for prog in all_progs[1:]:
            prog.is_active = False
            fixed += 1
    return fixed


async def run_maintenance_cycle():
    """Run all maintenance tasks in a single DB session."""
    import time as _time
    _cycle_start = _time.monotonic()
    try:
        async with async_session() as db:
            # 1. Orphan cleanup
            orphans = await _cleanup_orphaned_sessions(db)
            _log("orphan_cleanup", "ok" if orphans == 0 else "fixed",
                 f"Cleaned {orphans} orphaned sessions", orphans)

            # 2. Stale programs
            stale = await _fix_stale_programs(db)
            _log("stale_programs", "ok" if stale == 0 else "fixed",
                 f"Deactivated {stale} stale programs", stale)

            # 3. Duplicate programs
            dups = await _fix_duplicate_programs(db)
            _log("duplicate_programs", "ok" if dups == 0 else "fixed",
                 f"Deactivated {dups} duplicate programs", dups)

            # 4. Generate missing nutrition prescriptions
            missing_rx = await db.execute(
                select(User, UserProfile)
                .join(UserProfile, User.id == UserProfile.user_id)
                .outerjoin(
                    NutritionPrescription,
                    (NutritionPrescription.user_id == User.id) & (NutritionPrescription.is_active == True),
                )
                .where(User.onboarding_complete == True, NutritionPrescription.id == None)
            )
            missing_users = missing_rx.all()
            rx_fixed = 0
            if missing_users:
                from app.engines.engine3.macros import compute_tdee, compute_macros
                from app.engines.engine1.body_fat import lean_mass_kg as _lbm
                for u, profile in missing_users:
                    w_r = await db.execute(
                        select(BodyWeightLog.weight_kg)
                        .where(BodyWeightLog.user_id == u.id)
                        .order_by(desc(BodyWeightLog.recorded_date)).limit(1)
                    )
                    weight = w_r.scalar() or 85.0
                    bf = getattr(profile, "manual_body_fat_pct", None) or 15.0
                    lbm_val = _lbm(weight, bf)
                    age = profile.age or 28
                    sex = profile.sex or "male"
                    am = 1.725 if (profile.days_per_week or 4) >= 5 else 1.55
                    tdee = compute_tdee(weight, profile.height_cm, age, sex, am, lean_mass_kg=lbm_val)
                    macros = compute_macros(tdee, "maintain", weight, sex, lean_mass_kg=lbm_val, body_fat_pct=bf)
                    rx = NutritionPrescription(
                        user_id=u.id, tdee=round(tdee), target_calories=round(macros["target_calories"]),
                        protein_g=round(macros["protein_g"], 1), carbs_g=round(macros["carbs_g"], 1),
                        fat_g=round(macros["fat_g"], 1), phase="maintain", is_active=True,
                    )
                    db.add(rx)
                    rx_fixed += 1
            _log("missing_nutrition", "ok" if rx_fixed == 0 else "fixed",
                 f"Generated {rx_fixed} nutrition prescriptions", rx_fixed)

            # 5. Data integrity scan (read-only)
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
                _log("integrity_check", "warning",
                     f"{empty} active sessions have no exercises", 0)
            else:
                _log("integrity_check", "ok", "All active sessions have exercises", 0)

            # 6. Stale check-in detector — flag users who haven't checked in for 14+ days during prep
            from app.models.nutrition import WeeklyCheckin, AdherenceLog
            stale_checkins = 0
            prep_users = await db.execute(
                select(User, UserProfile)
                .join(UserProfile, User.id == UserProfile.user_id)
                .where(User.onboarding_complete == True)
            )
            for u, profile in prep_users.all():
                prefs = profile.preferences or {}
                phase = prefs.get("initial_phase", "maintain")
                if phase not in ("cut", "peak"):
                    continue
                latest_checkin = await db.execute(
                    select(func.max(BodyWeightLog.recorded_date))
                    .where(BodyWeightLog.user_id == u.id)
                )
                last_date = latest_checkin.scalar()
                if last_date and (date.today() - last_date).days >= 14:
                    stale_checkins += 1
            if stale_checkins > 0:
                _log("stale_checkins", "warning",
                     f"{stale_checkins} prep athletes haven't logged weight in 14+ days", 0)
            else:
                _log("stale_checkins", "ok", "All prep athletes have recent check-ins", 0)

            # 7. Weight stall detector — flag users whose weight hasn't changed in 14+ days during cut
            weight_stalls = 0
            cut_users = await db.execute(
                select(User.id).join(UserProfile, User.id == UserProfile.user_id)
                .where(User.onboarding_complete == True)
            )
            for (uid,) in cut_users.all():
                recent_weights = await db.execute(
                    select(BodyWeightLog.weight_kg)
                    .where(
                        BodyWeightLog.user_id == uid,
                        BodyWeightLog.recorded_date >= date.today() - timedelta(days=14),
                    )
                    .order_by(BodyWeightLog.recorded_date)
                )
                weights = [r[0] for r in recent_weights.all()]
                if len(weights) >= 4:
                    weight_range = max(weights) - min(weights)
                    if weight_range < 0.3:  # less than 300g change in 2 weeks
                        weight_stalls += 1
            if weight_stalls > 0:
                _log("weight_stalls", "warning",
                     f"{weight_stalls} users have stalled weight (<0.3kg change in 14 days)", 0)
            else:
                _log("weight_stalls", "ok", "No weight stalls detected", 0)

            await db.commit()

        elapsed = _time.monotonic() - _cycle_start
        total = orphans + stale + dups + rx_fixed
        _log("maintenance_cycle", "complete",
             f"Cycle complete — {total} fixes applied in {elapsed:.1f}s", total)

    except Exception as e:
        _log("maintenance_cycle", "error", f"Cycle failed: {str(e)}", 0)
        logger.exception("Cron maintenance cycle failed")


async def cron_loop(interval_seconds: int = 21600):
    """
    Background loop that runs maintenance every `interval_seconds`.
    Default: 6 hours (21600 seconds).
    """
    _log("cron_start", "ok", f"Cron started — interval: {interval_seconds}s", 0)

    # Run immediately on startup
    await run_maintenance_cycle()

    while True:
        await asyncio.sleep(interval_seconds)
        await run_maintenance_cycle()
