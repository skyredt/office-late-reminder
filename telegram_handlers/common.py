"""
telegram_handlers/common.py — Shared response helpers for all handlers.
"""

import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from services import auth_service

logger = logging.getLogger(__name__)


async def safe_reply(update: Update, text: str, reply_markup=None, quote=False):
    """Reply to user, logging but not crashing on Telegram errors."""
    try:
        await update.message.reply_text(text, reply_markup=reply_markup, quote=quote)
    except Exception as e:
        logger.error("safe_reply failed: %s", e)


async def safe_edit(update: Update, text: str, reply_markup=None):
    """Edit the existing message, gracefully handling if it was already deleted."""
    try:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
    except Exception as e:
        logger.warning("safe_edit skipped (message gone or unchanged): %s", e)
