"""
telegram_handlers/callback_handlers.py — Telegram callback query router.
Calls workflowService for business logic and sends Telegram reply.
"""

import logging
from telegram import Update, InlineKeyboardMarkup
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


def build_dispatcher(workflow, nudge_svc):
    """
    Returns the async callback query handler.
    Accepts workflow and nudge_svc as injected dependencies to avoid circular imports.
    """

    async def cb_root(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()

        user_id = query.from_user.id

        from utils.callback_data import CallbackPayload, unpack
        payload: CallbackPayload = unpack(query.data)
        if payload is None:
            await query.answer("Invalid callback data.", show_alert=True)
            return

        action = payload.action
        req_id = payload.request_id

        logger.info("CALLBACK raw=%s action=%s req_id=%s user=%s",
                    query.data, action, req_id, user_id)

        # Always cancel nudge on any button press
        nudge_svc.on_user_action(req_id)

        # ── Dispatch ──────────────────────────────────────────────────────────
        result = None

        if action == "extend_menu":
            result = workflow.handle_extend_menu(req_id, user_id)
        elif action == "end_work":
            result = workflow.handle_end_work(req_id, user_id)
        elif action == "extend_preset":
            minutes = payload.extra  # e.g. "10m", "30m", "1h"
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

        logger.info("  result: ok=%s msg=%.80s buttons=%s",
                    result.ok, result.message, len(result.buttons) if result.buttons else 0)

        await query.answer()

        # ── Custom text input ─────────────────────────────────────────────────
        if result.next_state == "awaiting_custom_text":
            await query.edit_message_text(text=result.message)
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="Please type your answer below:",
                reply_markup={"force_reply": True, "input_field_placeholder": "e.g. 20 mins, 1 hour"},
            )
            return

        # ── Normal button reply ───────────────────────────────────────────────
        if result.buttons:
            await query.edit_message_text(
                text=result.message,
                reply_markup=InlineKeyboardMarkup(result.buttons),
            )
        else:
            await query.edit_message_text(text=result.message)

    return cb_root
