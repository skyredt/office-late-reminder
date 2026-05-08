"""
telegram_handlers/text_handlers.py — Free-text input handler.

Text is only accepted in state AWAITING_CUSTOM_TEXT.
All text input is validated via auth_service.require_auth().
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes
import services.workflow_service as workflow
import services.auth_service as auth
import services.nudge_service as nudge_svc
import repositories.prompt_repository as prompt_repo
from telegram_handlers.common import InlineKeyboardButton, InlineKeyboardMarkup


logger = logging.getLogger(__name__)
_prompt_repo = prompt_repo.PromptRepository()


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle free text — only when user is in AWAITING_CUSTOM_TEXT state.
    All other states: safely ignored.
    """
    user_id = update.effective_user.id

    if not auth.require_auth(user_id):
        await update.message.reply_text("You are not authorised to use this bot.")
        return

    # Find the user's most recent AWAITING_CUSTOM_TEXT request
    active = _prompt_repo.get_active_for_user(user_id)
    req = next(
        (r for r in active if r.status.value == "awaiting_custom_text"),
        None,
    )
    if req is None:
        # Silently ignore — user is not in custom-text state
        return

    # Cancel nudge for this request
    nudge_svc.on_user_action(req.id)

    text = update.message.text
    result = workflow.handle_custom_text(req.id, user_id, text)

    if result.buttons:
        await update.message.reply_text(
            text=result.message,
            reply_markup=InlineKeyboardMarkup(result.buttons),
        )
    else:
        await update.message.reply_text(result.message)
