"""
Telegram bot service — thin wrapper around the Bot API for sending messages
and building the fixed-response UX. We do NOT use any LLM here: every
outgoing message is either a templated response to a known command, or a
scheduled reminder triggered by the app's existing cron jobs.

Per-user bot architecture: each athlete creates their own Telegram bot via
BotFather and pastes the token into Settings. The backend stores the token
on their UserProfile, calls Telegram's ``setWebhook`` with a unique
``secret_token`` per user, and the incoming webhook discriminates users by
matching the Telegram ``X-Telegram-Bot-Api-Secret-Token`` header.

A legacy single-bot fallback is still supported: if the ``TELEGRAM_BOT_TOKEN``
env var is set, users WITHOUT their own bot can link via the old
``/start <link_code>`` flow. Users WITH their own bot always route via their
own token — the fallback is never used for them.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_API_BASE = "https://api.telegram.org"


def is_enabled() -> bool:
    """True if at least one bot is available (shared or per-user via token arg)."""
    return True  # per-user bots don't need global config — always "enabled"


def shared_bot_enabled() -> bool:
    """True if the legacy global TELEGRAM_BOT_TOKEN is configured."""
    return bool(settings.TELEGRAM_BOT_TOKEN)


def _url(method: str, bot_token: str) -> str:
    return f"{_API_BASE}/bot{bot_token}/{method}"


async def send_message(
    chat_id: int | str,
    text: str,
    *,
    bot_token: str | None = None,
    reply_markup: dict[str, Any] | None = None,
    parse_mode: str = "HTML",
) -> bool:
    """
    Send an HTML message via the provided bot token. When ``bot_token`` is None
    the shared fallback (``settings.TELEGRAM_BOT_TOKEN``) is used, if available.
    Returns True on 200 OK; silently no-ops (False) when no token is available.
    """
    token = bot_token or settings.TELEGRAM_BOT_TOKEN
    if not token:
        logger.debug("Telegram send_message skipped: no bot token")
        return False

    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(_url("sendMessage", token), json=payload)
            if resp.status_code != 200:
                logger.warning("Telegram sendMessage failed: %s %s", resp.status_code, resp.text)
                return False
            return True
    except Exception as exc:
        logger.exception("Telegram sendMessage exception: %s", exc)
        return False


async def get_me(bot_token: str) -> dict | None:
    """Validate a bot token by calling Telegram's getMe. Returns the bot info
    dict on success, None on failure. Used to validate user-pasted tokens."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(_url("getMe", bot_token))
            if resp.status_code != 200:
                return None
            body = resp.json()
            return body.get("result") if body.get("ok") else None
    except Exception as exc:
        logger.warning("Telegram getMe failed: %s", exc)
        return None


async def register_webhook(
    bot_token: str,
    webhook_url: str,
    secret_token: str,
) -> bool:
    """
    Call Telegram's setWebhook on the given bot token. Every incoming
    update will include the ``secret_token`` in an ``X-Telegram-Bot-Api-Secret-Token``
    header so the backend can route to the right user.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                _url("setWebhook", bot_token),
                json={
                    "url": webhook_url,
                    "secret_token": secret_token,
                    "allowed_updates": ["message", "callback_query"],
                    "drop_pending_updates": True,
                },
            )
            return resp.status_code == 200
    except Exception as exc:
        logger.warning("Telegram setWebhook failed: %s", exc)
        return False


async def delete_webhook(bot_token: str) -> bool:
    """Clear a bot's webhook when the user unlinks."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                _url("deleteWebhook", bot_token),
                json={"drop_pending_updates": True},
            )
            return resp.status_code == 200
    except Exception as exc:
        logger.warning("Telegram deleteWebhook failed: %s", exc)
        return False


# Legacy alias kept for back-compat
async def set_webhook(url: str) -> bool:
    """Deprecated: uses the shared fallback bot. Prefer register_webhook()."""
    if not shared_bot_enabled():
        return False
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            _url("setWebhook", settings.TELEGRAM_BOT_TOKEN),
            json={"url": url},
        )
        return resp.status_code == 200


def main_keyboard() -> dict[str, Any]:
    """Inline keyboard shown after /start or /help."""
    return {
        "inline_keyboard": [
            [
                {"text": "📅 Tomorrow's Workout", "callback_data": "workout_tomorrow"},
                {"text": "💪 Today's Workout", "callback_data": "workout_today"},
            ],
            [
                {"text": "🍽 Today's Meal Plan", "callback_data": "meals_today"},
                {"text": "✅ Meal Check-in", "callback_data": "meal_checkin"},
            ],
            [
                {"text": "📊 Daily Check-in", "callback_data": "daily_checkin"},
                {"text": "⚙️ Notifications", "callback_data": "settings"},
            ],
        ]
    }


def yes_no_keyboard(callback_yes: str, callback_no: str) -> dict[str, Any]:
    return {
        "inline_keyboard": [
            [
                {"text": "✅ Yes", "callback_data": callback_yes},
                {"text": "❌ No", "callback_data": callback_no},
            ]
        ]
    }


# -- Templated responses -----------------------------------------------------

WELCOME_UNLINKED = (
    "<b>Welcome to Coronado 🏆</b>\n\n"
    "I'm your personal training + nutrition coach, straight from the Coronado app.\n\n"
    "To link this chat to your account, open the Coronado app → "
    "<b>Settings → Account → Link Telegram</b> and send me the 6-character code.\n\n"
    "Tap <code>/help</code> to see what I can do once we're linked."
)

WELCOME_LINKED = (
    "<b>You're linked ✅</b>\n\n"
    "Here's what I can do:\n"
    "• <code>/workout_tomorrow</code> — preview tomorrow's session\n"
    "• <code>/workout_today</code> — today's working sets\n"
    "• <code>/meals_today</code> — today's meal plan\n"
    "• <code>/checkin</code> — log today's check-in\n"
    "• <code>/settings</code> — notification preferences\n"
    "• <code>/unlink</code> — disconnect this chat"
)

UNLINKED_OK = "You've been disconnected. Run <code>/start</code> to re-link anytime."

HELP_TEXT = WELCOME_LINKED

NOT_LINKED_ERROR = (
    "This chat isn't linked to a Coronado account yet. "
    "Open the app → <b>Settings → Account → Link Telegram</b> to get a link code."
)

NO_WORKOUT_TOMORROW = "No workout scheduled for tomorrow — rest day 💤"
NO_WORKOUT_TODAY = "No workout scheduled for today — rest day 💤"
NO_MEAL_PLAN = "No meal plan generated yet. Open the app to create one."


def format_workout_summary(session: dict[str, Any]) -> str:
    """Render a compact workout preview from the engine2 session dict shape."""
    if not session:
        return NO_WORKOUT_TOMORROW
    label = (session.get("session_type") or "training").replace("_", " ").title()
    duration = session.get("estimated_duration_min")
    window = session.get("workout_window") or {}

    lines = [f"<b>{label} Day</b>"]
    if duration:
        lines.append(f"⏱ ~{duration} min")
    if window.get("start_time") and window.get("end_time"):
        lines.append(f"🕐 {window['start_time']} → {window['end_time']}")

    # Group by exercise, show distinct list
    seen = []
    for s in session.get("sets", []):
        if s.get("is_warmup"):
            continue
        name = s.get("exercise_name", "")
        if name and name not in seen:
            seen.append(name)

    if seen:
        lines.append("")
        lines.append("<b>Exercises:</b>")
        for name in seen[:12]:
            lines.append(f"• {name}")
        if len(seen) > 12:
            lines.append(f"… and {len(seen) - 12} more")
    return "\n".join(lines)


def format_meal_plan_summary(meals: list[dict[str, Any]]) -> str:
    if not meals:
        return NO_MEAL_PLAN
    lines = ["<b>Today's Meals</b>"]
    for m in meals:
        if not m.get("ingredients"):
            continue  # skip fasted/blank meals
        lines.append(
            f"🍽 <b>{m.get('label', 'Meal')}</b>"
            f" · {m.get('time', '')}"
            f" · {round(m.get('totals', {}).get('calories', 0))} kcal"
        )
        for ing in m.get("ingredients", [])[:4]:
            lines.append(
                f"  — {ing.get('name', '')} · {ing.get('quantity_g', 0)}g"
            )
    return "\n".join(lines)


NOTIFICATION_KEYS: list[tuple[str, str]] = [
    ("workout_tomorrow", "Tomorrow's workout preview (9 PM)"),
    ("workout_today",    "Today's workout + readiness (7 AM)"),
    ("meal_reminder",    "Meal time reminders"),
    ("weekly_checkin",   "Weekly check-in reminder (Sun 9 AM)"),
    ("missed_checkin",   "Missed check-in nudge (8 PM)"),
    ("ari_red_zone",     "Low readiness alert (immediate)"),
    ("refeed_triggered", "Refeed / diet break triggered (immediate)"),
]


def format_notification_settings(prefs: dict[str, bool] | None) -> str:
    prefs = prefs or {}
    lines = ["<b>Notification Preferences</b>"]
    for key, label in NOTIFICATION_KEYS:
        on = prefs.get(key, True)
        lines.append(f"{'🔔' if on else '🔕'} {label}")
    lines.append("")
    lines.append("Adjust these in the Coronado app → Settings → Account → Telegram.")
    return "\n".join(lines)
