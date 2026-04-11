"""
Telegram bot webhook + link flow.

Two authenticated endpoints for the app to manage linking:
  - POST /telegram/link/generate → returns a 6-char link code + deep link
  - POST /telegram/unlink → clears Telegram fields from the profile

One anonymous endpoint for Telegram to call:
  - POST /telegram/webhook → handles commands and callback queries

Fixed-response UX only — no LLM. Commands are dispatched via a simple map.
"""

from __future__ import annotations

import logging
import secrets
import string
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models.profile import UserProfile
from app.models.user import User
from app.services import telegram as tg

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/telegram", tags=["telegram"])

_LINK_CODE_TTL_MINUTES = 15


def _generate_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    # Exclude visually ambiguous chars
    alphabet = alphabet.replace("0", "").replace("O", "").replace("I", "").replace("1", "")
    return "".join(secrets.choice(alphabet) for _ in range(6))


def _update_prefs(profile: UserProfile, patch: dict) -> None:
    current = dict(profile.preferences or {})
    current.update(patch)
    profile.preferences = current


async def _find_profile_by_chat_id(db: AsyncSession, chat_id: int) -> UserProfile | None:
    # JSONB query: preferences->>'telegram_chat_id' = <chat_id>
    result = await db.execute(
        select(UserProfile).where(
            UserProfile.preferences["telegram_chat_id"].astext == str(chat_id)
        )
    )
    return result.scalar_one_or_none()


async def _find_profile_by_link_code(db: AsyncSession, code: str) -> UserProfile | None:
    result = await db.execute(
        select(UserProfile).where(
            UserProfile.preferences["telegram_pending_code"].astext == code
        )
    )
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Authenticated endpoints (app → backend)
# ---------------------------------------------------------------------------


@router.post("/link/generate")
async def generate_link_code(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not tg.is_enabled():
        raise HTTPException(status_code=503, detail="Telegram bot is not configured on this deployment")

    result = await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    code = _generate_code()
    expires_at = datetime.utcnow() + timedelta(minutes=_LINK_CODE_TTL_MINUTES)
    _update_prefs(
        profile,
        {
            "telegram_pending_code": code,
            "telegram_pending_expires_at": expires_at.isoformat(),
        },
    )
    await db.commit()

    bot_username = settings.TELEGRAM_BOT_USERNAME or "your_bot"
    return {
        "code": code,
        "expires_in_minutes": _LINK_CODE_TTL_MINUTES,
        "bot_username": bot_username,
        "deep_link": f"https://t.me/{bot_username}?start={code}",
        "instructions": (
            f"Open Telegram and message @{bot_username} with: /start {code}"
        ),
    }


@router.post("/unlink")
async def unlink_account(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    current = dict(profile.preferences or {})
    chat_id = current.get("telegram_chat_id")
    for key in (
        "telegram_chat_id",
        "telegram_enabled",
        "telegram_pending_code",
        "telegram_pending_expires_at",
    ):
        current.pop(key, None)
    profile.preferences = current
    await db.commit()

    if chat_id and tg.is_enabled():
        await tg.send_message(int(chat_id), tg.UNLINKED_OK)

    return {"unlinked": True}


@router.get("/status")
async def get_link_status(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    prefs = profile.preferences or {}
    return {
        "enabled": tg.is_enabled(),
        "linked": bool(prefs.get("telegram_chat_id")),
        "bot_username": settings.TELEGRAM_BOT_USERNAME or None,
        "notify": prefs.get("telegram_notify") or {
            "workout_reminder": True,
            "tomorrow_workout": True,
            "meal_reminder": True,
            "weekly_checkin": True,
            "missed_checkin": True,
        },
    }


class NotifyUpdate(dict):
    pass


@router.patch("/notifications")
async def update_notifications(
    data: dict,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    current = dict(profile.preferences or {})
    existing = dict(current.get("telegram_notify") or {})
    valid_keys = {key for key, _ in tg.NOTIFICATION_KEYS}
    for k, v in (data or {}).items():
        if k in valid_keys and isinstance(v, bool):
            existing[k] = v
    current["telegram_notify"] = existing
    profile.preferences = current
    await db.commit()
    return {"notify": existing}


# ---------------------------------------------------------------------------
# Anonymous webhook (Telegram → backend)
# ---------------------------------------------------------------------------


async def _handle_command(
    db: AsyncSession,
    chat_id: int,
    text: str,
) -> None:
    """Dispatch an incoming command text to a canned response."""
    parts = text.strip().split(maxsplit=1)
    cmd = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""

    profile = await _find_profile_by_chat_id(db, chat_id)

    # /start <code> — link flow
    if cmd == "/start":
        if arg:
            # Validate and consume link code
            candidate = await _find_profile_by_link_code(db, arg.upper())
            if not candidate:
                await tg.send_message(chat_id, "❌ Invalid or expired link code. Generate a fresh one in the app.")
                return
            prefs = dict(candidate.preferences or {})
            expires_raw = prefs.get("telegram_pending_expires_at")
            if expires_raw:
                try:
                    if datetime.fromisoformat(expires_raw) < datetime.utcnow():
                        await tg.send_message(chat_id, "❌ That link code expired. Generate a fresh one in the app.")
                        return
                except ValueError:
                    pass
            prefs["telegram_chat_id"] = chat_id
            prefs["telegram_enabled"] = True
            prefs.pop("telegram_pending_code", None)
            prefs.pop("telegram_pending_expires_at", None)
            prefs.setdefault("telegram_notify", {
                "workout_reminder": True,
                "tomorrow_workout": True,
                "meal_reminder": True,
                "weekly_checkin": True,
                "missed_checkin": True,
            })
            candidate.preferences = prefs
            await db.commit()
            await tg.send_message(chat_id, tg.WELCOME_LINKED, reply_markup=tg.main_keyboard())
            return
        # No arg
        if profile:
            await tg.send_message(chat_id, tg.WELCOME_LINKED, reply_markup=tg.main_keyboard())
        else:
            await tg.send_message(chat_id, tg.WELCOME_UNLINKED)
        return

    if not profile:
        await tg.send_message(chat_id, tg.NOT_LINKED_ERROR)
        return

    if cmd == "/help":
        await tg.send_message(chat_id, tg.HELP_TEXT, reply_markup=tg.main_keyboard())
        return

    if cmd == "/unlink":
        prefs = dict(profile.preferences or {})
        for key in ("telegram_chat_id", "telegram_enabled"):
            prefs.pop(key, None)
        profile.preferences = prefs
        await db.commit()
        await tg.send_message(chat_id, tg.UNLINKED_OK)
        return

    if cmd in ("/settings", "/notifications"):
        prefs = (profile.preferences or {}).get("telegram_notify", {})
        await tg.send_message(chat_id, tg.format_notification_settings(prefs))
        return

    if cmd in ("/workout_tomorrow", "/tomorrow"):
        session = await _load_session(db, profile.user_id, date.today() + timedelta(days=1))
        await tg.send_message(chat_id, tg.format_workout_summary(session))
        return

    if cmd in ("/workout_today", "/today"):
        session = await _load_session(db, profile.user_id, date.today())
        await tg.send_message(chat_id, tg.format_workout_summary(session))
        return

    if cmd in ("/meals_today", "/meals"):
        meals = await _load_meals_today(db, profile.user_id)
        await tg.send_message(chat_id, tg.format_meal_plan_summary(meals))
        return

    if cmd in ("/checkin", "/daily"):
        await tg.send_message(
            chat_id,
            "Open the Coronado app to log your daily check-in (weight, HRV, sleep, soreness). "
            "A short reminder: consistent check-ins unlock smarter autoregulation.",
        )
        return

    # Unknown command — nudge to /help
    await tg.send_message(chat_id, "Unknown command. Try <code>/help</code>.")


async def _handle_callback(db: AsyncSession, chat_id: int, data: str) -> None:
    profile = await _find_profile_by_chat_id(db, chat_id)
    if not profile:
        await tg.send_message(chat_id, tg.NOT_LINKED_ERROR)
        return
    if data == "workout_tomorrow":
        session = await _load_session(db, profile.user_id, date.today() + timedelta(days=1))
        await tg.send_message(chat_id, tg.format_workout_summary(session))
    elif data == "workout_today":
        session = await _load_session(db, profile.user_id, date.today())
        await tg.send_message(chat_id, tg.format_workout_summary(session))
    elif data == "meals_today":
        meals = await _load_meals_today(db, profile.user_id)
        await tg.send_message(chat_id, tg.format_meal_plan_summary(meals))
    elif data == "meal_checkin":
        await tg.send_message(chat_id, "Log your meal adherence in the Coronado app → Nutrition tab.")
    elif data == "daily_checkin":
        await tg.send_message(chat_id, "Open the Coronado app to log your daily check-in.")
    elif data == "settings":
        prefs = (profile.preferences or {}).get("telegram_notify", {})
        await tg.send_message(chat_id, tg.format_notification_settings(prefs))


async def _load_session(db: AsyncSession, user_id, target_date: date) -> dict | None:
    """
    Resolve a session for a given date using the same logic the /engine2/session
    endpoint uses. Returns a dict shaped like the API response, or None.
    """
    from app.models.training import TrainingProgram, TrainingSession, TrainingSet, Exercise
    from sqlalchemy import desc

    result = await db.execute(
        select(TrainingSession)
        .join(TrainingProgram, TrainingSession.program_id == TrainingProgram.id)
        .where(
            TrainingSession.user_id == user_id,
            TrainingSession.session_date == target_date,
            TrainingProgram.is_active == True,
        )
        .limit(1)
    )
    session = result.scalar_one_or_none()
    if not session:
        return None
    sets_result = await db.execute(
        select(TrainingSet, Exercise.name, Exercise.primary_muscle)
        .join(Exercise, TrainingSet.exercise_id == Exercise.id)
        .where(TrainingSet.session_id == session.id)
        .order_by(TrainingSet.set_number)
    )
    rows = sets_result.all()

    from app.services.training import estimate_session_duration_minutes, compute_workout_window

    duration_min = estimate_session_duration_minutes([r[0] for r in rows])

    profile_row = await db.execute(
        select(UserProfile).where(UserProfile.user_id == user_id)
    )
    profile = profile_row.scalar_one_or_none()
    anchor_mode = (getattr(profile, "training_time_anchor", None) or "start") if profile else "start"
    anchor_time = (
        getattr(profile, "training_end_time", None)
        if profile and anchor_mode == "end"
        else getattr(profile, "training_start_time", None)
    )
    window = compute_workout_window(anchor_time, anchor_mode, duration_min)

    return {
        "session_type": session.session_type,
        "estimated_duration_min": duration_min,
        "workout_window": {
            "anchor_mode": anchor_mode,
            "start_time": window["start"],
            "end_time": window["end"],
        },
        "sets": [
            {"exercise_name": name, "is_warmup": ts.is_warmup}
            for ts, name, _muscle in rows
        ],
    }


async def _load_meals_today(db: AsyncSession, user_id) -> list[dict]:
    """Pull today's meal plan via the existing engine3 helper."""
    from app.models.nutrition import MealPlanTemplate, NutritionPrescription
    from sqlalchemy import desc

    result = await db.execute(
        select(MealPlanTemplate)
        .where(MealPlanTemplate.user_id == user_id)
        .order_by(desc(MealPlanTemplate.created_at))
        .limit(1)
    )
    template = result.scalar_one_or_none()
    if not template or not template.meals_json:
        return []
    meals = template.meals_json.get("training") or template.meals_json.get("training_day") or []
    return meals or []


@router.post("/webhook")
async def telegram_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    if not tg.is_enabled():
        return {"ok": True}

    # If a webhook secret is configured (set via Telegram setWebhook with
    # secret_token), require it on every incoming request so attackers can't
    # forge update payloads.
    if settings.TELEGRAM_WEBHOOK_SECRET:
        provided = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if provided != settings.TELEGRAM_WEBHOOK_SECRET:
            logger.warning("Telegram webhook rejected: bad secret token")
            raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        update = await request.json()
    except Exception:
        return {"ok": True}

    try:
        if "message" in update and update["message"].get("chat"):
            chat_id = update["message"]["chat"]["id"]
            text = update["message"].get("text") or ""
            if text.startswith("/"):
                await _handle_command(db, int(chat_id), text)
            else:
                await tg.send_message(int(chat_id), "Try <code>/help</code> to see what I can do.")
        elif "callback_query" in update:
            cq = update["callback_query"]
            chat_id = cq["message"]["chat"]["id"] if cq.get("message") else None
            data = cq.get("data") or ""
            if chat_id:
                await _handle_callback(db, int(chat_id), data)
    except Exception as exc:
        logger.exception("Telegram webhook handler error: %s", exc)

    return {"ok": True}
