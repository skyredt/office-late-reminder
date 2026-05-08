"""
config.py — All environment configuration for Office Late Reminder.
Single source of truth. No hardcoded values anywhere.
"""

import os
from dotenv import load_dotenv

load_dotenv()


def _str(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


def _int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except ValueError:
        return default


def _bool(key: str, default: bool = False) -> bool:
    return os.getenv(key, str(default)).lower() in ("true", "1", "yes")


# ── Telegram ───────────────────────────────────────────────────────────────────
BOT_TOKEN: str = _str("BOT_TOKEN")
MY_USER_ID: int = _int("MY_TELEGRAM_USER_ID", 0)

# ── Telethon user-client credentials ──────────────────────────────────────────
TELETHON_API_ID: int = _int("TELEGRAM_API_ID", 0)
TELETHON_API_HASH: str = _str("TELEGRAM_API_HASH")
TELETHON_SESSION_NAME: str = _str("TELETHON_SESSION_NAME", "office_late_reminder")

# ── Recipient whitelist ────────────────────────────────────────────────────────
# The ONLY destination outbound messages may be sent to.
WIFE_TARGET: str = _str("WIFE_TELEGRAM_TARGET").strip()

# ── Send behaviour ─────────────────────────────────────────────────────────────
SEND_MODE: str = _str("SEND_MODE", "telethon").lower()
DRY_RUN: bool = _bool("DRY_RUN", True)
SEND_ENABLED: bool = _bool("SEND_ENABLED", True)

# ── Rate limits ────────────────────────────────────────────────────────────────
MAX_SENDS_PER_DAY: int = _int("MAX_SENDS_PER_DAY", 3)
MIN_SECONDS_BETWEEN_SENDS: int = _int("MIN_SECONDS_BETWEEN_SENDS", 300)

# ── Timezone ───────────────────────────────────────────────────────────────────
TIMEZONE_STR: str = _str("TIMEZONE", "Asia/Singapore")

# ── Scheduler ──────────────────────────────────────────────────────────────────
ENABLE_SCHEDULER: bool = _bool("ENABLE_SCHEDULER", False)
SCHEDULER_HOUR: int = _int("SCHEDULER_HOUR", 18)
SCHEDULER_MINUTE: int = _int("SCHEDULER_MINUTE", 0)

# ── Nudge reminder ─────────────────────────────────────────────────────────────
NUDGE_DELAY_MINUTES: int = _int("NUDGE_DELAY_MINUTES", 10)
PROMPT_EXPIRY_MINUTES: int = _int("PROMPT_EXPIRY_MINUTES", 30)

# ── Validation ────────────────────────────────────────────────────────────────
MAX_CUSTOM_TEXT_CHARS: int = _int("MAX_CUSTOM_TEXT_CHARS", 200)

# ── Database ──────────────────────────────────────────────────────────────────
DB_PATH: str = _str("DB_PATH", "office_late_reminder.db")

# ── Masking ────────────────────────────────────────────────────────────────────
# How many chars of a phone number to reveal (trailing)
PHONE_MASK_TRAILING: int = 4
# How many chars of a user ID to mask
USER_ID_MASK_TRAILING: int = 3