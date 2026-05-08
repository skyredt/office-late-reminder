"""
telegram_handlers/command_handlers.py — All /command handlers.
Every command delegates to auth_service.require_auth().
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes
import services.workflow_service as workflow
import services.status_service as status_svc
import services.auth_service as auth
import repositories.prompt_repository as prompt_repo
import services.nudge_service as nudge_svc
import telegram_handlers.common as common


logger = logging.getLogger(__name__)
_prompt_repo = prompt_repo.PromptRepository()


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not auth.require_auth(update.effective_user.id):
        await common.reply_plain(update, "You are not authorised to use this bot.")
        return
    await update.message.reply_text(
        "Office Late Reminder is running.\n"
        "Commands:\n"
        "/start — restart\n"
        "/testprompt — send a test prompt now\n"
        "/status — check bot health\n"
        "/cancel — cancel current prompt"
    )


async def cmd_testprompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not auth.require_auth(update.effective_user.id):
        await common.reply_plain(update, "You are not authorised to use this bot.")
        return

    result = workflow.start_prompt(update.effective_user.id)
    await update.message.reply_text(
        text=result.message,
        reply_markup=common.InlineKeyboardMarkup(result.buttons),
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not auth.require_auth(update.effective_user.id):
        await common.reply_plain(update, "You are not authorised to use this bot.")
        return

    report = status_svc.get_status(update.effective_user.id)
    await update.message.reply_text(report)


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not auth.require_auth(update.effective_user.id):
        await common.reply_plain(update, "You are not authorised to use this bot.")
        return

    active = _prompt_repo.get_active_for_user(update.effective_user.id)
    if not active:
        await update.message.reply_text("No active prompt to cancel.")
        return

    # Cancel the most recent active request
    req = active[0]
    result = workflow.handle_cancel(req.id, update.effective_user.id)
    if result.buttons:
        await update.message.reply_text(
            text=result.message,
            reply_markup=common.InlineKeyboardMarkup(result.buttons),
        )
    else:
        await update.message.reply_text(result.message)
