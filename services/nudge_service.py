"""
services/nudge_service.py — Nudge reminder scheduling and delivery.

- On prompt start: nudge_due_at is stored in SQLite (via PromptRepository)
- On any user action: nudge is cancelled (nudge_due_at = NULL)
- On startup: pending nudges are restored and rescheduled via APScheduler
- Nudge fires only for still-active requests (not sent/cancelled/expired/failed)
"""

import logging
import config
import repositories.prompt_repository as prompt_repo
from telegram import InlineKeyboardButton
from utils.callback_data import pack


logger = logging.getLogger(__name__)
_prompt_repo = prompt_repo.PromptRepository()


def on_prompt_started(request_id: str):
    """Called after a prompt is created. Nudge is already stored in SQLite."""
    logger.info("Nudge scheduled for req=%s", request_id[-8:])


def on_user_action(request_id: str):
    """Called on any button press — cancels the nudge for this request."""
    _prompt_repo.cancel_nudge(request_id)
    logger.info("Nudge cancelled req=%s", request_id[-8:])


def get_pending_nudges() -> list:
    """Returns prompt requests that need a nudge now."""
    return _prompt_repo.get_pending_nudges()


def mark_nudged(request_id: str):
    _prompt_repo.mark_nudged(request_id)


def nudge_message() -> str:
    return (
        "You haven't responded to the end-of-day prompt yet.\n"
        "Are you still at work or are you done for the day?"
    )


def nudge_keyboard(request_id: str) -> list:
    return [
        [InlineKeyboardButton("End work",  callback_data=pack("end_work", request_id))],
        [InlineKeyboardButton("Extend",    callback_data=pack("extend_preset", request_id, "custom"))],
        [InlineKeyboardButton("No message today", callback_data=pack("skip", request_id))],
    ]