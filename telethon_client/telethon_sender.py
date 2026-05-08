"""
telethon_client/telethon_sender.py — Telethon user-client send implementation.

Single responsibility: send a message to a SINGLE whitelisted recipient.
Never sends anywhere else.
"""

import logging
import os
import asyncio
import threading
import time
from typing import Optional

import config


logger = logging.getLogger(__name__)

# ── Singleton background loop ─────────────────────────────────────────────────
_bg_loop: Optional[asyncio.AbstractEventLoop] = None
_bg_thread: Optional[threading.Thread] = None
_client = None


class SendResult:
    """Standardised result from a send attempt."""
    def __init__(self, success: bool, message: str = "", error_code: str | None = None):
        self.success = success
        self.message = message
        self.error_code = error_code


def _run_async(coro) -> any:
    if _bg_loop is None or not _bg_loop.is_running():
        raise RuntimeError("Background event loop not running")
    return asyncio.run_coroutine_threadsafe(coro, _bg_loop).result(timeout=30)


def _ensure_started():
    """Start the background event loop if not already running. Safe to call multiple times."""
    global _bg_loop, _bg_thread, _client

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
        global _client
        from telethon import TelegramClient
        base = os.path.dirname(os.path.abspath(__file__))
        session_file = os.path.join(base, "..", f"{config.TELETHON_SESSION_NAME}.session")
        _client = TelegramClient(session_file, config.TELETHON_API_ID, config.TELETHON_API_HASH)
        await _client.connect()
        if await _client.is_user_authorized():
            me = await _client.get_me()
            logger.info("Telethon authorized as: %s", me.first_name)
        else:
            logger.warning("Telethon session not authorized — run telethon_login.py")

    _run_async(_connect())


def init():
    _ensure_started()


def is_authorized() -> bool:
    if _client is None:
        return False
    try:
        return _run_async(_client.is_user_authorized())
    except Exception:
        return False


def get_display_name() -> str:
    if _client is None:
        return "Not connected"
    try:
        async def _get():
            me = await _client.get_me()
            return me.first_name or "Unknown"
        return _run_async(_get())
    except Exception:
        return "Not authorised"


def send_message_via_telethon(target: str, message: str) -> SendResult:
    """
    Send a message via Telethon. Target is always enforced to be config.WIFE_TARGET.
    Returns SendResult (never raises).
    """
    # ── Final whitelist enforcement ───────────────────────────────────────────
    if target != config.WIFE_TARGET:
        logger.error("REJECTED send to non-whitelisted recipient: %s", target)
        return SendResult(False, "Recipient not allowed.", "RECIPIENT_REJECTED")

    if _client is None:
        return SendResult(False, "Telethon client not initialized.", "CLIENT_NOT_READY")

    try:
        async def _send():
            await _client.send_message(target, message)

        _run_async(_send())
        logger.info("Sent via Telethon to %s: %s", _mask_phone(target), message[:40])
        return SendResult(True)
    except Exception as e:
        logger.error("Telethon send failed: %s", e)
        return SendResult(False, str(e), "TELETHON_ERROR")


def close():
    global _bg_loop, _bg_thread, _client
    if _client is not None:
        try:
            async def _d():
                await _client.disconnect()
            _run_async(_d())
        except Exception:
            pass
        _client = None
    if _bg_loop is not None:
        _bg_loop.call_soon_threadsafe(_bg_loop.stop)
        _bg_loop = None
        _bg_thread = None


def _mask_phone(p: str) -> str:
    s = p.strip().lstrip("+")
    return f"+{'x' * (len(s) - 4)}{s[-4:]}"