"""
sender.py — Safe message sender for Office Late Reminder.

Rules:
  - Only sends to WIFE_TELEGRAM_TARGET (whitelist enforcement)
  - Only sends fixed message templates (no arbitrary text)
  - Respects DRY_RUN and SEND_ENABLED
  - Rate limiting
  - DRY_RUN/SEND_ENABLED checked BEFORE any Telethon call
"""

import logging
import os
import re
import asyncio
import threading
import time
from collections import deque
from datetime import datetime, date

from dotenv import load_dotenv
from telethon import TelegramClient

load_dotenv()

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
SEND_MODE         = os.getenv("SEND_MODE", "telethon").lower()
WIFE_TARGET      = os.getenv("WIFE_TELEGRAM_TARGET", "").strip()
API_ID           = int(os.getenv("TELEGRAM_API_ID", "0"))
API_HASH         = os.getenv("TELEGRAM_API_HASH", "")
SESSION_NAME     = os.getenv("TELETHON_SESSION_NAME", "office_late_reminder")
DRY_RUN          = os.getenv("DRY_RUN", "true").lower() == "true"
SEND_ENABLED     = os.getenv("SEND_ENABLED", "true").lower() == "true"
MAX_SENDS_PER_DAY = int(os.getenv("MAX_SENDS_PER_DAY", "3"))
MIN_SECONDS_BETWEEN = float(os.getenv("MIN_SECONDS_BETWEEN_SENDS", "300"))

# ── Approved message templates ────────────────────────────────────────────────
TEMPLATE_END_WORK = "Hi bb..\nI end work le… can go off liao. How about you?"
TEMPLATE_EXTEND   = "Hi bb..\nI need to stay back for {duration}… Are you hungry? Where do you want to go?"

# ── Rate-limit tracking (in-memory, per-process) ───────────────────────────────
_send_times: deque = deque()   # wall-clock timestamps of successful sends

# ── Custom duration validation ────────────────────────────────────────────────
# Accept: "10 mins", "15 min", "45 minutes", "1 hour", "2 hours", "1h", "30m"
# Max 20 chars. No URLs, @mentions, phone numbers, or command-like content.
DURATION_RE = re.compile(r"^\s*\d{1,2}\s*(?:mins?|minutes?|hours?|h|m)\s*$", re.IGNORECASE)
MAX_DURATION_CHARS = 20


def validate_duration(duration: str) -> tuple[bool, str]:
    """
    Returns (ok, cleaned_or_reason).
    ok=True  -> cleaned duration string (stripped, lowercase)
    ok=False -> reason string
    """
    d = duration.strip()
    if len(d) > MAX_DURATION_CHARS:
        return False, f"Too long (max {MAX_DURATION_CHARS} chars). Try again or /cancel."

    # Block obviously bad patterns
    blocked = [
        r"@\w+",          # @mentions
        r"https?://",      # URLs
        r"\+65\d",        # phone numbers
        r"^/.*",          # command-like
        r"t\.me",         # t.me links
    ]
    for pattern in blocked:
        if re.search(pattern, d):
            return False, "Invalid characters. Try again or /cancel."

    if not DURATION_RE.match(d):
        return False, "Unclear duration. Try e.g. '10 mins', '1 hour', or /cancel."

    # Normalise
    return True, d.lower()


# ── Send pre-flight checks ─────────────────────────────────────────────────────
def _check_send_allowed() -> tuple[bool, str]:
    """Returns (allowed, reason). Called BEFORE any Telethon call."""
    if not SEND_ENABLED:
        logger.info("Send blocked: SEND_ENABLED=false")
        return False, "SEND_ENABLED=false — sending is disabled."

    if not DRY_RUN and not WIFE_TARGET:
        logger.error("Send blocked: WIFE_TARGET not configured")
        return False, "WIFE_TELEGRAM_TARGET is not set in .env."

    today = date.today()
    today_sends = sum(1 for t in _send_times if datetime.fromtimestamp(t).date() == today)
    if today_sends >= MAX_SENDS_PER_DAY:
        logger.info("Send blocked: daily limit reached (%s/%s)", today_sends, MAX_SENDS_PER_DAY)
        return False, f"Daily limit reached ({MAX_SENDS_PER_DAY}/{MAX_SENDS_PER_DAY})."

    if _send_times:
        last = _send_times[-1]
        elapsed = time.time() - last
        if elapsed < MIN_SECONDS_BETWEEN:
            remaining = int(MIN_SECONDS_BETWEEN - elapsed)
            logger.info("Send blocked: rate limit %s sec still waiting", remaining)
            return False, f"Too soon — wait {remaining}s between sends."

    return True, ""


# ── Telethon client (background thread) ───────────────────────────────────────
_bg_loop: asyncio.AbstractEventLoop | None = None
_bg_thread: threading.Thread | None = None
_telethon_client = None


def _run_async(coro) -> any:
    if _bg_loop is None or not _bg_loop.is_running():
        raise RuntimeError("Background event loop not running.")
    future = asyncio.run_coroutine_threadsafe(coro, _bg_loop)
    return future.result(timeout=30)


def init_telethon():
    """Start background loop + connect Telethon. Safe to call multiple times."""
    global _bg_loop, _bg_thread, _telethon_client

    if _bg_loop is not None:
        return

    def bg_target():
        global _bg_loop
        _bg_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_bg_loop)
        _bg_loop.run_forever()

    _bg_thread = threading.Thread(target=bg_target, name="telethon-bg", daemon=True)
    _bg_thread.start()

    while _bg_loop is None or not _bg_loop.is_running():
        time.sleep(0.05)

    async def _connect():
        global _telethon_client
        session_file = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            f"{SESSION_NAME}.session"
        )
        _telethon_client = TelegramClient(session_file, API_ID, API_HASH)
        await _telethon_client.connect()
        if await _telethon_client.is_user_authorized():
            me = await _telethon_client.get_me()
            logger.info("Telethon authorised as: %s", me.first_name)
        else:
            logger.warning("Telethon session not authorised — run telethon_login.py")

    _run_async(_connect())


def is_telethon_ready() -> bool:
    if _telethon_client is None:
        return False
    try:
        async def _check():
            return await _telethon_client.is_user_authorized()
        return _run_async(_check())
    except Exception:
        return False


def get_telethon_display() -> str:
    if _telethon_client is None:
        return "Not connected"
    try:
        async def _get():
            me = await _telethon_client.get_me()
            return me.first_name or "Unknown"
        return _run_async(_get())
    except Exception:
        return "Not authorised"


def close_telethon_client():
    global _bg_loop, _bg_thread, _telethon_client
    if _telethon_client is not None:
        try:
            async def _d():
                await _telethon_client.disconnect()
            _run_async(_d())
        except Exception:
            pass
        _telethon_client = None
    if _bg_loop is not None:
        _bg_loop.call_soon_threadsafe(_bg_loop.stop)
        _bg_loop = None
        _bg_thread = None


# ── Core send ─────────────────────────────────────────────────────────────────

def send_end_work() -> tuple[bool, str]:
    """
    Returns (success, message_or_reason).
    DRY_RUN/SEND_ENABLED/rate-limit checked first.
    """
    ok, reason = _check_send_allowed()
    if not ok:
        return False, reason

    if DRY_RUN:
        logger.info("[DRY RUN] Would send END_WORK to %s", WIFE_TARGET)
        return True, f"[DRY RUN] Would have sent:\n\n{TEMPLATE_END_WORK}"

    # Telethon only fires here — WIFE_TARGET enforced
    return _do_send_telethon(WIFE_TARGET, TEMPLATE_END_WORK)


def send_extend(duration: str) -> tuple[bool, str]:
    ok, reason = _check_send_allowed()
    if not ok:
        return False, reason

    valid, result = validate_duration(duration)
    if not valid:
        return False, result

    message = TEMPLATE_EXTEND.format(duration=result)

    if DRY_RUN:
        logger.info("[DRY RUN] Would send EXTEND (%s) to %s", result, WIFE_TARGET)
        return True, f"[DRY RUN] Would have sent:\n\n{message}"

    return _do_send_telethon(WIFE_TARGET, message)


def _do_send_telethon(target: str, message: str) -> tuple[bool, str]:
    """
    Actually sends via Telethon. Target is ALWAYS WIFE_TARGET (enforced by caller).
    """
    if target != WIFE_TARGET:
        logger.error("Send rejected: recipient '%s' != WIFE_TARGET '%s'", target, WIFE_TARGET)
        return False, "Recipient not allowed."

    if _telethon_client is None:
        logger.error("Send blocked: Telethon client not initialised")
        return False, "Telethon client not ready."

    try:
        async def _send():
            await _telethon_client.send_message(target, message)

        _run_async(_send())
        _send_times.append(time.time())
        logger.info("Message sent successfully to %s: %s", target, message[:40])
        return True, "Sent."
    except Exception as e:
        logger.error("Telethon send failed: %s", e)
        return False, f"Telethon error: {e}"


# ── Status helpers ───────────────────────────────────────────────────────────

def get_status_snapshot() -> dict:
    """Thread-safe snapshot of all sender state for /status."""
    today = date.today()
    today_count = sum(1 for t in _send_times if datetime.fromtimestamp(t).date() == today)
    last_send = datetime.fromtimestamp(_send_times[-1], pytz.timezone('Asia/Singapore')).strftime('%Y-%m-%d %H:%M:%S %Z') if _send_times else "Never"
    return {
        "send_mode":         SEND_MODE,
        "telethon_ready":    is_telethon_ready(),
        "telethon_display":  get_telethon_display() if is_telethon_ready() else "N/A",
        "dry_run":           DRY_RUN,
        "send_enabled":      SEND_ENABLED,
        "sends_today":       today_count,
        "max_sends_per_day": MAX_SENDS_PER_DAY,
        "min_seconds_between": MIN_SECONDS_BETWEEN,
        "last_send":         last_send,
        "wife_target":       WIFE_TARGET,
    }
