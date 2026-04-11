"""
Telegram notification dispatcher.

Runs on a 15-minute loop and, for each linked user, checks whether any
time-windowed notification (workout_tomorrow at 9 PM, workout_today at
7 AM, weekly_checkin on Sun 9 AM, etc.) should fire right now.

Idempotency is enforced via the NotificationLog table: each
(user_id, notification_type, today) combination can only fire once per day.
Immediate triggers (ari_red_zone, refeed_triggered) are NOT dispatched
here — they're sent inline from the checkin/engine3 routers.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models.notification import NotificationLog
from app.models.profile import UserProfile
from app.models.training import HRVLog
from app.services import telegram as tg

logger = logging.getLogger(__name__)

# Time-windowed notification schedule. Each entry defines:
#   key: matches preferences.telegram_notify.<key>
#   target_hour, target_minute: local time to fire (UTC for now — user-local TZ in a future sprint)
#   window_minutes: ± tolerance; the dispatcher tick runs every 15 min so
#                   a window of 10 min catches a single firing without duplicates.
#   weekday_filter: optional set of weekday numbers (Monday=0 .. Sunday=6).
#   builder: async function(db, profile) -> (text, reply_markup | None) or None to skip.

_FIRING_WINDOW_MIN = 10


def _is_in_window(now: datetime, hour: int, minute: int) -> bool:
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    delta = abs((now - target).total_seconds() / 60.0)
    return delta <= _FIRING_WINDOW_MIN


async def _already_fired_today(
    db: AsyncSession,
    user_id,
    notification_type: str,
) -> bool:
    """Check the notification log for any row of this type for today."""
    today_start = datetime.combine(date.today(), datetime.min.time(), tzinfo=timezone.utc)
    result = await db.execute(
        select(func.count())
        .select_from(NotificationLog)
        .where(
            NotificationLog.user_id == user_id,
            NotificationLog.notification_type == notification_type,
            NotificationLog.sent_at >= today_start,
            NotificationLog.status == "sent",
        )
    )
    return (result.scalar() or 0) > 0


async def _record_sent(
    db: AsyncSession,
    user_id,
    notification_type: str,
    *,
    status: str = "sent",
    error: str | None = None,
) -> None:
    db.add(NotificationLog(
        user_id=user_id,
        notification_type=notification_type,
        channel="telegram",
        status=status,
        error=error,
    ))


# ---------------------------------------------------------------------------
# Message builders — pull live data + render HTML
# ---------------------------------------------------------------------------

async def _build_workout_tomorrow(db: AsyncSession, profile: UserProfile) -> str | None:
    """Preview of tomorrow's session."""
    from app.routers.telegram import _load_session
    session = await _load_session(db, profile.user_id, date.today() + timedelta(days=1))
    if not session:
        return "<b>Rest day tomorrow 💤</b>\n\nNo session scheduled — recover hard."
    return "📅 <b>Tomorrow's Workout</b>\n\n" + tg.format_workout_summary(session)


async def _build_workout_today(db: AsyncSession, profile: UserProfile) -> str | None:
    """Morning send: today's session + ARI readiness."""
    from app.routers.telegram import _load_session
    session = await _load_session(db, profile.user_id, date.today())
    if not session:
        return None  # don't send on rest days — silence is nice

    # Latest ARI for a readiness tag
    from app.models.training import ARILog
    ari_row = await db.execute(
        select(ARILog).where(ARILog.user_id == profile.user_id)
        .order_by(ARILog.recorded_date.desc(), ARILog.created_at.desc()).limit(1)
    )
    ari = ari_row.scalar_one_or_none()
    readiness = ""
    if ari:
        zone_emoji = {"green": "🟢", "yellow": "🟡", "red": "🔴"}.get(
            "green" if ari.ari_score >= 70 else "yellow" if ari.ari_score >= 40 else "red", "⚪"
        )
        readiness = f"\n\n{zone_emoji} <b>Readiness:</b> {round(ari.ari_score)}"

    return "☀️ <b>Good morning — today's session</b>\n\n" + tg.format_workout_summary(session) + readiness


async def _build_weekly_checkin(db: AsyncSession, profile: UserProfile) -> str | None:
    return (
        "📸 <b>Weekly Check-in Time</b>\n\n"
        "Open the Coronado app → Weekly Check-in and log:\n"
        "• Tape measurements (all sites)\n"
        "• Skinfolds (if you take them)\n"
        "• Front / back / side progress photos\n\n"
        "Consistency is the single biggest predictor of prep success."
    )


async def _build_missed_checkin(db: AsyncSession, profile: UserProfile) -> str | None:
    """Only send if the athlete hasn't logged any HRV/weight today."""
    today = date.today()
    hrv_q = await db.execute(
        select(func.count()).select_from(HRVLog).where(
            HRVLog.user_id == profile.user_id,
            HRVLog.recorded_date == today,
        )
    )
    if (hrv_q.scalar() or 0) > 0:
        return None  # they checked in, no nudge needed
    return (
        "⏰ <b>Daily Check-in Reminder</b>\n\n"
        "You haven't logged your daily check-in yet. Quick ones work:\n"
        "• Body weight\n• HRV (if you measured)\n• Sleep quality + hours\n• Soreness 1-10\n\n"
        "Open the app → Check-in → Daily."
    )


async def _build_meal_reminder(db: AsyncSession, profile: UserProfile) -> str | None:
    """Compact reminder pointing at the user's current meal plan."""
    return (
        "🍽 <b>Meal Check-in</b>\n\n"
        "Time for your next meal. Open the Coronado app → Nutrition for your "
        "exact macros and ingredients."
    )


# Notification catalog.
# Each tuple: (key, target_hour, target_minute, weekday_filter, builder_fn, default_on)
_SCHEDULE: list[tuple[str, int, int, set[int] | None, Any, bool]] = [
    ("workout_tomorrow", 21, 0, None,          _build_workout_tomorrow, True),
    ("workout_today",     7, 0, None,          _build_workout_today,    True),
    ("weekly_checkin",    9, 0, {6},           _build_weekly_checkin,   True),  # Sunday=6
    ("missed_checkin",   20, 0, None,          _build_missed_checkin,   True),
    # meal_reminder intentionally fires from a per-user meal-time window —
    # the cron dispatcher skips it and leaves that for a future upgrade
    # that reads each user's actual meal times.
]


async def dispatch_telegram_notifications(db: AsyncSession, now: datetime | None = None) -> int:
    """
    Scan all users with linked Telegram chats and dispatch any notifications
    whose time window contains `now`. Returns the number of messages sent.
    """
    now = now or datetime.now(timezone.utc)
    today = now.date()
    weekday = now.weekday()
    sent_count = 0

    # Load every profile with a Telegram chat_id in preferences
    profiles_q = await db.execute(
        select(UserProfile).where(
            UserProfile.preferences["telegram_chat_id"].astext.is_not(None)
        )
    )
    profiles = profiles_q.scalars().all()

    for profile in profiles:
        prefs = profile.preferences or {}
        chat_id = prefs.get("telegram_chat_id")
        if not chat_id:
            continue
        notify_flags: dict[str, bool] = prefs.get("telegram_notify") or {}
        bot_token = getattr(profile, "telegram_bot_token", None)
        # Fallback to shared bot if the user hasn't BYO'd.
        from app.config import settings as _cfg
        if not bot_token and not _cfg.TELEGRAM_BOT_TOKEN:
            continue

        for (key, hr, mn, weekday_filter, builder, default_on) in _SCHEDULE:
            if weekday_filter is not None and weekday not in weekday_filter:
                continue
            if not notify_flags.get(key, default_on):
                continue
            if not _is_in_window(now, hr, mn):
                continue
            if await _already_fired_today(db, profile.user_id, key):
                continue

            try:
                text = await builder(db, profile)
            except Exception as exc:
                logger.exception("Notification builder %s failed: %s", key, exc)
                await _record_sent(db, profile.user_id, key, status="failed", error=str(exc)[:500])
                continue

            if not text:
                continue

            ok = await tg.send_message(int(chat_id), text, bot_token=bot_token)
            if ok:
                await _record_sent(db, profile.user_id, key)
                sent_count += 1
            else:
                await _record_sent(db, profile.user_id, key, status="failed", error="send_message returned False")

    await db.commit()
    return sent_count


# ---------------------------------------------------------------------------
# Immediate dispatchers (called from routers, not cron)
# ---------------------------------------------------------------------------

async def dispatch_ari_red_zone(
    db: AsyncSession,
    profile: UserProfile,
    ari_score: float,
    recommendation: str,
) -> bool:
    """Fire an immediate ARI red-zone alert if preferences allow and we
    haven't already sent one today."""
    prefs = profile.preferences or {}
    chat_id = prefs.get("telegram_chat_id")
    if not chat_id:
        return False
    if not (prefs.get("telegram_notify") or {}).get("ari_red_zone", True):
        return False
    if await _already_fired_today(db, profile.user_id, "ari_red_zone"):
        return False

    bot_token = getattr(profile, "telegram_bot_token", None)
    text = (
        f"⚠️ <b>Low Readiness — ARI {round(ari_score)}</b>\n\n"
        f"{recommendation}\n\n"
        f"Consider trimming volume 30-50% or taking a full rest day."
    )
    ok = await tg.send_message(int(chat_id), text, bot_token=bot_token)
    await _record_sent(db, profile.user_id, "ari_red_zone", status="sent" if ok else "failed")
    await db.commit()
    return ok


async def dispatch_refeed_triggered(
    db: AsyncSession,
    profile: UserProfile,
    refeed_payload: dict,
) -> bool:
    prefs = profile.preferences or {}
    chat_id = prefs.get("telegram_chat_id")
    if not chat_id:
        return False
    if not (prefs.get("telegram_notify") or {}).get("refeed_triggered", True):
        return False
    if await _already_fired_today(db, profile.user_id, "refeed_triggered"):
        return False

    bot_token = getattr(profile, "telegram_bot_token", None)
    message = refeed_payload.get("message") or "Refeed prescribed by autoregulation."
    recommendation = refeed_payload.get("recommendation", "")
    text = (
        f"🍚 <b>Refeed Triggered</b>\n\n"
        f"{message}\n\n"
        f"Action: <code>{recommendation}</code>"
    )
    ok = await tg.send_message(int(chat_id), text, bot_token=bot_token)
    await _record_sent(db, profile.user_id, "refeed_triggered", status="sent" if ok else "failed")
    await db.commit()
    return ok


# ---------------------------------------------------------------------------
# Background loop (started from main lifespan)
# ---------------------------------------------------------------------------

async def notification_loop(interval_seconds: int = 900):
    """
    Runs dispatch_telegram_notifications every `interval_seconds` (default 15 min).
    This is a separate loop from the 6-hour maintenance cycle so we get
    fine-grained timing for morning/evening notification windows.
    """
    logger.info("Notification dispatcher started — interval %ds", interval_seconds)
    while True:
        try:
            async with async_session() as db:
                count = await dispatch_telegram_notifications(db)
                if count > 0:
                    logger.info("Dispatched %d telegram notifications", count)
        except Exception as exc:
            logger.exception("Notification dispatch cycle failed: %s", exc)
        await asyncio.sleep(interval_seconds)
