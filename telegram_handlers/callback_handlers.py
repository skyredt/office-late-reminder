"""
telegram_handlers/callback_handlers.py — All callback query handlers.
Every callback delegates to auth_service.require_auth().
"""

import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
import services.workflow_service as workflow
import services.auth_service as auth
import services.nudge_service as nudge_svc
import utils.callback_data as cb

logger = logging.getLogger(__name__)


async def cb_root(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Main callback dispatcher. All callback data uses the format:
      v1|<action>|<request_id>|<extra>
    """
    query = update.callback_query
    user_id = query.from_user.id

    if not auth.require_auth(user_id):
        await query.answer("Not authorised.", show_alert=True)
        return

    payload = cb.unpack(query.data)
    if payload is None:
        await query.answer("Invalid callback data.", show_alert=True)
        return

    req_id = payload.request_id
    action = payload.action

    # Always cancel nudge on any button press
    nudge_svc.on_user_action(req_id)

    result = None

    if action == "end_work":
        result = workflow.handle_end_work(req_id, user_id)
    elif action == "extend_preset":
        minutes = payload.extra  # "10m", "30m", "1h"
        result = workflow.handle_extend_preset(req_id, user_id, minutes)
    elif action == "extend_custom":
        result = workflow.handle_extend_custom(req_id, user_id)
    elif action == "confirm":
        result = workflow.handle_confirm(req_id, user_id)
    elif action == "cancel":
        result = workflow.handle_cancel(req_id, user_id)
    elif action == "skip":
        result = workflow.handle_skip(req_id, user_id)
    elif action == "cancel_back":
        result = workflow.handle_cancel_back(req_id, user_id)
    elif action == "change":
        result = workflow.handle_change(req_id, user_id)
    else:
        await query.answer(f"Unknown action: {action}")
        return

    await query.answer()

    # ── Custom text input: use ForceReply to prompt the keyboard ──────────────
    if result.next_state == "awaiting_custom_text":
        await query.edit_message_text(text=result.message)
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="Please type your answer below:",
            reply_markup={"force_reply": True, "input_field_placeholder": "e.g. 20 mins, 1 hour"},
        )
        return

    # ── Normal button reply ────────────────────────────────────────────────────
    if result.buttons:
        await query.edit_message_text(
            text=result.message,
            reply_markup=InlineKeyboardMarkup(result.buttons),
        )
    else:
        await query.edit_message_text(text=result.message)
