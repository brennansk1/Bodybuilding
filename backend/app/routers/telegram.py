"""
Telegram bot webhook + link flow.

Per-user bot architecture:
- Each athlete creates a bot via BotFather, pastes the token into the app.
- Backend validates with Telegram getMe, generates a per-user webhook secret,
  calls setWebhook on the user's bot, and stores the token on UserProfile.
- Incoming webhook requests include X-Telegram-Bot-Api-Secret-Token — we match
  that against preferences.telegram_webhook_secret to resolve the user.

Legacy fallback: if TELEGRAM_BOT_TOKEN env is set, the old /start <code>
link flow still works for users who haven't brought their own bot.

Authenticated endpoints (JWT):
  - POST /telegram/link/token        — paste a user-provided BotFather token
  - POST /telegram/link/generate     — legacy shared-bot /start <code> flow
  - POST /telegram/unlink            — disconnect + deleteWebhook
  - GET  /telegram/status            — linked state + notification flags
  - PATCH /telegram/notifications    — update flag set

Anonymous endpoint (Telegram):
  - POST /telegram/webhook           — handles commands + callback_query
"""

from __future__ import annotations

import logging
import secrets
import string
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
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
    alphabet = alphabet.replace("0", "").replace("O", "").replace("I", "").replace("1", "")
    return "".join(secrets.choice(alphabet) for _ in range(6))


def _generate_webhook_secret() -> str:
    # 32-char urlsafe secret — fits in Telegram setWebhook secret_token (max 256).
    return secrets.token_urlsafe(24)


def _update_prefs(profile: UserProfile, patch: dict) -> None:
    current = dict(profile.preferences or {})
    current.update(patch)
    profile.preferences = current


def _webhook_public_url() -> str:
    """Best-effort resolution of the public backend URL for setWebhook."""
    # Prefer an explicit env override if present; otherwise fall back to
    # a sensible default that the admin is expected to set for production.
    base = getattr(settings, "PUBLIC_BASE_URL", None) or "https://coronado.example.com"
    return f"{base.rstrip('/')}/api/v1/telegram/webhook"


async def _find_profile_by_chat_id(db: AsyncSession, chat_id: int) -> UserProfile | None:
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


async def _find_profile_by_webhook_secret(db: AsyncSession, secret: str) -> UserProfile | None:
    result = await db.execute(
        select(UserProfile).where(
            UserProfile.preferences["telegram_webhook_secret"].astext == secret
        )
    )
    return result.scalar_one_or_none()


def _bot_token_for(profile: UserProfile | None) -> str | None:
    """Return the token to use when sending messages on behalf of this user.
    Prefers per-user token, falls back to shared bot token if configured."""
    if profile and getattr(profile, "telegram_bot_token", None):
        return profile.telegram_bot_token
    return settings.TELEGRAM_BOT_TOKEN or None


# ---------------------------------------------------------------------------
# Authenticated endpoints (app → backend)
# ---------------------------------------------------------------------------


class LinkTokenRequest(BaseModel):
    bot_token: str


@router.post("/link/token")
async def link_via_bot_token(
    data: LinkTokenRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    User pastes their BotFather token. We validate it with Telegram's
    getMe, register a webhook with a per-user secret, and store the token
    on their profile. From then on, all messages to/from this user route
    through their own bot.
    """
    raw = (data.bot_token or "").strip()
    if not raw or ":" not in raw:
        raise HTTPException(status_code=400, detail="bot_token must be in the form 123456:ABC...")

    bot_info = await tg.get_me(raw)
    if not bot_info:
        raise HTTPException(
            status_code=400,
            detail="Telegram rejected that bot token. Double-check you copied it from BotFather.",
        )
    username = bot_info.get("username") or "your_bot"

    # Generate a per-user webhook secret and register the webhook on the
    # user's bot pointing at our public URL.
    webhook_secret = _generate_webhook_secret()
    public_url = _webhook_public_url()
    ok = await tg.register_webhook(raw, public_url, webhook_secret)
    if not ok:
        raise HTTPException(
            status_code=502,
            detail=(
                "Validated the token but failed to register a webhook. "
                "Make sure the backend is reachable from Telegram's servers "
                "(PUBLIC_BASE_URL must be https:// and publicly routable)."
            ),
        )

    profile_row = await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))
    profile = profile_row.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    profile.telegram_bot_token = raw
    _update_prefs(
        profile,
        {
            "telegram_webhook_secret": webhook_secret,
            "telegram_bot_username": username,
            "telegram_enabled": True,
            # Default notification flags on for new links.
            "telegram_notify": {
                "workout_tomorrow": True,
                "workout_today": True,
                "meal_reminder": False,      # off by default (chatty)
                "weekly_checkin": True,
                "missed_checkin": True,
                "ari_red_zone": True,
                "refeed_triggered": True,
            },
        },
    )
    await db.commit()

    return {
        "linked": True,
        "bot_username": username,
        "deep_link": f"https://t.me/{username}",
        "message": (
            f"Linked to @{username}. Open the bot in Telegram and send /start "
            f"to confirm the connection."
        ),
    }


@router.post("/link/generate")
async def generate_link_code(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Legacy shared-bot link flow. Only works if TELEGRAM_BOT_TOKEN is set
    on the server. Prefer /link/token for real users."""
    if not tg.shared_bot_enabled():
        raise HTTPException(
            status_code=503,
            detail=(
                "Shared bot is not configured. Use POST /telegram/link/token "
                "to link your own bot instead."
            ),
        )

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
        "instructions": f"Open Telegram and message @{bot_username} with: /start {code}",
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

    token_to_unhook = profile.telegram_bot_token
    current = dict(profile.preferences or {})
    chat_id = current.get("telegram_chat_id")
    for key in (
        "telegram_chat_id",
        "telegram_enabled",
        "telegram_pending_code",
        "telegram_pending_expires_at",
        "telegram_webhook_secret",
        "telegram_bot_username",
    ):
        current.pop(key, None)
    profile.preferences = current
    profile.telegram_bot_token = None
    await db.commit()

    # Best-effort: clear the webhook on Telegram's side so updates stop coming.
    if token_to_unhook:
        await tg.delete_webhook(token_to_unhook)

    if chat_id:
        await tg.send_message(
            int(chat_id),
            tg.UNLINKED_OK,
            bot_token=token_to_unhook,
        )

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
        "enabled": True,  # always — per-user bots are always an option
        "shared_bot_available": tg.shared_bot_enabled(),
        "linked": bool(prefs.get("telegram_chat_id") or profile.telegram_bot_token),
        "has_own_bot": bool(profile.telegram_bot_token),
        "bot_username": prefs.get("telegram_bot_username") or settings.TELEGRAM_BOT_USERNAME or None,
        "notify": prefs.get("telegram_notify") or {
            "workout_tomorrow": True,
            "workout_today": True,
            "meal_reminder": False,
            "weekly_checkin": True,
            "missed_checkin": True,
            "ari_red_zone": True,
            "refeed_triggered": True,
        },
    }


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
    *,
    profile: UserProfile | None,
    bot_token: str | None,
) -> None:
    """Dispatch an incoming command text to a canned response."""
    parts = text.strip().split(maxsplit=1)
    cmd = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""

    # /start <code> — legacy shared-bot link flow
    if cmd == "/start":
        if arg and not profile:
            # Try shared-bot link code flow
            candidate = await _find_profile_by_link_code(db, arg.upper())
            if not candidate:
                await tg.send_message(
                    chat_id,
                    "❌ Invalid or expired link code. Generate a fresh one in the app.",
                    bot_token=bot_token,
                )
                return
            prefs = dict(candidate.preferences or {})
            expires_raw = prefs.get("telegram_pending_expires_at")
            if expires_raw:
                try:
                    if datetime.fromisoformat(expires_raw) < datetime.utcnow():
                        await tg.send_message(
                            chat_id,
                            "❌ That link code expired. Generate a fresh one in the app.",
                            bot_token=bot_token,
                        )
                        return
                except ValueError:
                    pass
            prefs["telegram_chat_id"] = chat_id
            prefs["telegram_enabled"] = True
            prefs.pop("telegram_pending_code", None)
            prefs.pop("telegram_pending_expires_at", None)
            prefs.setdefault("telegram_notify", {
                "workout_tomorrow": True,
                "workout_today": True,
                "meal_reminder": False,
                "weekly_checkin": True,
                "missed_checkin": True,
                "ari_red_zone": True,
                "refeed_triggered": True,
            })
            candidate.preferences = prefs
            await db.commit()
            await tg.send_message(
                chat_id,
                tg.WELCOME_LINKED,
                reply_markup=tg.main_keyboard(),
                bot_token=bot_token,
            )
            return

        # Per-user bot: /start needs to persist the chat_id so future messages
        # (from the server-side dispatcher) know where to land.
        if profile:
            prefs = dict(profile.preferences or {})
            if prefs.get("telegram_chat_id") != chat_id:
                prefs["telegram_chat_id"] = chat_id
                prefs["telegram_enabled"] = True
                profile.preferences = prefs
                await db.commit()
            await tg.send_message(
                chat_id,
                tg.WELCOME_LINKED,
                reply_markup=tg.main_keyboard(),
                bot_token=bot_token,
            )
        else:
            await tg.send_message(chat_id, tg.WELCOME_UNLINKED, bot_token=bot_token)
        return

    if not profile:
        await tg.send_message(chat_id, tg.NOT_LINKED_ERROR, bot_token=bot_token)
        return

    if cmd == "/help":
        await tg.send_message(
            chat_id,
            tg.HELP_TEXT,
            reply_markup=tg.main_keyboard(),
            bot_token=bot_token,
        )
        return

    if cmd == "/unlink":
        prefs = dict(profile.preferences or {})
        for key in ("telegram_chat_id", "telegram_enabled"):
            prefs.pop(key, None)
        profile.preferences = prefs
        await db.commit()
        await tg.send_message(chat_id, tg.UNLINKED_OK, bot_token=bot_token)
        return

    if cmd in ("/settings", "/notifications"):
        prefs = (profile.preferences or {}).get("telegram_notify", {})
        await tg.send_message(
            chat_id, tg.format_notification_settings(prefs), bot_token=bot_token,
        )
        return

    if cmd in ("/workout_tomorrow", "/tomorrow"):
        session = await _load_session(db, profile.user_id, date.today() + timedelta(days=1))
        await tg.send_message(
            chat_id, tg.format_workout_summary(session), bot_token=bot_token,
        )
        return

    if cmd in ("/workout_today", "/today"):
        session = await _load_session(db, profile.user_id, date.today())
        await tg.send_message(
            chat_id, tg.format_workout_summary(session), bot_token=bot_token,
        )
        return

    if cmd in ("/meals_today", "/meals"):
        meals = await _load_meals_today(db, profile.user_id)
        await tg.send_message(
            chat_id, tg.format_meal_plan_summary(meals), bot_token=bot_token,
        )
        return

    if cmd in ("/checkin", "/daily"):
        await tg.send_message(
            chat_id,
            "Open the Coronado app to log your daily check-in (weight, HRV, sleep, soreness). "
            "A short reminder: consistent check-ins unlock smarter autoregulation.",
            bot_token=bot_token,
        )
        return

    await tg.send_message(chat_id, "Unknown command. Try <code>/help</code>.", bot_token=bot_token)


async def _handle_callback(
    db: AsyncSession,
    chat_id: int,
    data: str,
    *,
    profile: UserProfile | None,
    bot_token: str | None,
) -> None:
    if not profile:
        await tg.send_message(chat_id, tg.NOT_LINKED_ERROR, bot_token=bot_token)
        return
    if data == "workout_tomorrow":
        session = await _load_session(db, profile.user_id, date.today() + timedelta(days=1))
        await tg.send_message(chat_id, tg.format_workout_summary(session), bot_token=bot_token)
    elif data == "workout_today":
        session = await _load_session(db, profile.user_id, date.today())
        await tg.send_message(chat_id, tg.format_workout_summary(session), bot_token=bot_token)
    elif data == "meals_today":
        meals = await _load_meals_today(db, profile.user_id)
        await tg.send_message(chat_id, tg.format_meal_plan_summary(meals), bot_token=bot_token)
    elif data == "meal_checkin":
        await tg.send_message(chat_id, "Log your meal adherence in the Coronado app → Nutrition tab.", bot_token=bot_token)
    elif data == "daily_checkin":
        await tg.send_message(chat_id, "Open the Coronado app to log your daily check-in.", bot_token=bot_token)
    elif data == "settings":
        prefs = (profile.preferences or {}).get("telegram_notify", {})
        await tg.send_message(chat_id, tg.format_notification_settings(prefs), bot_token=bot_token)


async def _load_session(db: AsyncSession, user_id, target_date: date) -> dict | None:
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
    """
    Telegram → backend.

    Routing: find the user by matching X-Telegram-Bot-Api-Secret-Token against
    preferences.telegram_webhook_secret. If no match (could be a shared-bot
    update), fall back to chat_id-based lookup. If neither works, the chat
    is treated as "not linked" and the bot responds accordingly.
    """
    # Authentication: the shared-bot fallback path uses a global secret.
    # Per-user bots attach their own per-user secret, which we match below.
    provided_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")

    # Reject obvious tamper attempts: if the global secret is set and the
    # header doesn't match a known user secret AND doesn't match the global
    # secret, bail.
    if settings.TELEGRAM_WEBHOOK_SECRET and provided_secret == settings.TELEGRAM_WEBHOOK_SECRET:
        # Shared-bot call: no per-user secret lookup needed; use chat_id.
        target_profile = None
    elif provided_secret:
        target_profile = await _find_profile_by_webhook_secret(db, provided_secret)
        if not target_profile:
            logger.warning("Telegram webhook rejected: unknown secret token")
            raise HTTPException(status_code=401, detail="Unauthorized")
    else:
        if settings.TELEGRAM_WEBHOOK_SECRET:
            logger.warning("Telegram webhook rejected: missing secret header")
            raise HTTPException(status_code=401, detail="Unauthorized")
        target_profile = None  # anonymous shared-bot call (dev mode)

    try:
        update = await request.json()
    except Exception:
        return {"ok": True}

    try:
        if "message" in update and update["message"].get("chat"):
            chat_id = int(update["message"]["chat"]["id"])
            text = update["message"].get("text") or ""
            profile = target_profile or await _find_profile_by_chat_id(db, chat_id)
            bot_token = _bot_token_for(profile)
            if text.startswith("/"):
                await _handle_command(db, chat_id, text, profile=profile, bot_token=bot_token)
            else:
                await tg.send_message(
                    chat_id,
                    "Try <code>/help</code> to see what I can do.",
                    bot_token=bot_token,
                )
        elif "callback_query" in update:
            cq = update["callback_query"]
            chat_id = cq["message"]["chat"]["id"] if cq.get("message") else None
            data = cq.get("data") or ""
            if chat_id:
                chat_id = int(chat_id)
                profile = target_profile or await _find_profile_by_chat_id(db, chat_id)
                bot_token = _bot_token_for(profile)
                await _handle_callback(db, chat_id, data, profile=profile, bot_token=bot_token)
    except Exception as exc:
        logger.exception("Telegram webhook handler error: %s", exc)

    return {"ok": True}
