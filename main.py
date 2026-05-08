"""
Office Late Reminder — Phase 1
Bot handles prompts + buttons. Telethon sends to wife.
All sends are owner-only, whitelist-enforced, rate-limited, and dry-runnable.
Nudge reminder fires 10 minutes after prompt if user hasn't responded.
"""

import logging
import os
import sys
import asyncio
from datetime import datetime, timedelta
from typing import Final

import pytz
from dotenv import load_dotenv

load_dotenv()

# ── Config ───────────────────────────────────────────────────────────────────
BOT_TOKEN        = os.getenv("BOT_TOKEN", "")
MY_USER_ID       = int(os.getenv("MY_TELEGRAM_USER_ID", "0"))
WIFE_TARGET      = os.getenv("WIFE_TELEGRAM_TARGET", "").strip()
TIMEZONE_STR     = os.getenv("TIMEZONE", "Asia/Singapore")
ENABLE_SCHEDULER = os.getenv("ENABLE_SCHEDULER", "false").lower() == "true"
TIMEZONE         = pytz.timezone(TIMEZONE_STR)

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# ── Authorisation ─────────────────────────────────────────────────────────────
def is_authorised(user_id: int) -> bool:
    return user_id == MY_USER_ID


# ── Nudge reminder system ──────────────────────────────────────────────────────
_nudge_scheduled_at: datetime | None = None
_nudge_job_id = "nudge_reminder"
_nudge_chat_id: int | None = None
_scheduler_ref: "Application | None" = None  # type: ignore[name-defined]


def _cancel_nudge():
    global _nudge_scheduled_at, _nudge_chat_id
    _nudge_scheduled_at = None
    _nudge_chat_id = None
    try:
        from apscheduler.schedulers.background import BlockingScheduler
        from apscheduler.jobstores.memory import MemoryJobStore
        js = MemoryJobStore()
        temp_sched = BlockingScheduler(timezone=TIMEZONE_STR, jobstores={"default": js})
        temp_sched.remove_job(_nudge_job_id, jobstore="default")
    except Exception:
        pass


def _schedule_nudge(chat_id: int):
    """
    Schedule a nudge DM to the user in 10 minutes if no response received.
    Idempotent — cancels any previously scheduled nudge first.
    """
    global _nudge_scheduled_at, _nudge_chat_id, _scheduler_ref

    _cancel_nudge()
    _nudge_chat_id = chat_id
    run_at = datetime.now(TIMEZONE) + timedelta(minutes=10)
    _nudge_scheduled_at = run_at

    def _nudge_callback():
        global _nudge_scheduled_at, _nudge_chat_id
        _nudge_scheduled_at = None
        _nudge_chat_id = None
        app = _scheduler_ref
        if app is None:
            logger.error("Nudge: app not available")
            return
        msg = (
            "You haven't responded to the end-of-day prompt yet.\n"
            "Are you still at work or are you done for the day?"
        )
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(
                    app.bot.send_message(chat_id=chat_id, text=msg)
                )
            finally:
                loop.close()
            logger.info("Nudge sent to %s", chat_id)
        except Exception as e:
            logger.error("Nudge send failed: %s", e)

    # Use the shared BlockingScheduler
    from main import scheduler as shared_scheduler
    if shared_scheduler is not None:
        shared_scheduler.add_job(
            _nudge_callback,
            "date",
            run_date=run_at,
            id=_nudge_job_id,
            misfire_grace_time=60,
            replace_existing=True,
        )
        logger.info("Nudge scheduled for %s SGT", run_at.strftime("%H:%M"))
    else:
        logger.warning("Scheduler not ready — nudge will not fire")


# ── Conversation states ────────────────────────────────────────────────────────
WAITING_CUSTOM_DURATION: Final[int] = 1


# ── Inline keyboards ───────────────────────────────────────────────────────────
def main_keyboard():
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("End work",          callback_data="end_work")],
        [InlineKeyboardButton("Extend",            callback_data="extend")],
        [InlineKeyboardButton("No message today", callback_data="no_message")],
    ])


def duration_keyboard():
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("10 mins",  callback_data="dur_10")],
        [InlineKeyboardButton("30 mins",  callback_data="dur_30")],
        [InlineKeyboardButton("1 hour",    callback_data="dur_60")],
        [InlineKeyboardButton("Custom…",   callback_data="dur_custom")],
    ])


def preview_keyboard():
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Yes, send", callback_data="confirm_yes")],
        [InlineKeyboardButton("Cancel",    callback_data="confirm_no")],
    ])


# ── /start ───────────────────────────────────────────────────────────────────
async def cmd_start(update, context):
    if not is_authorised(update.effective_user.id):
        logger.info("Unauthorized /start from user_id=%s", update.effective_user.id)
        return
    import sender
    ss = sender.get_status_snapshot()
    await update.message.reply_text(
        "Office Late Reminder — Phase 1\n\n"
        "Commands:\n"
        "/start     — restart\n"
        "/status    — check everything\n"
        "/testprompt — send the daily prompt now\n"
        "/cancel    — cancel current input\n\n"
        f"DRY_RUN:      {ss['dry_run']}\n"
        f"SEND_ENABLED: {ss['send_enabled']}"
    )


# ── /status ───────────────────────────────────────────────────────────────────
async def cmd_status(update, context):
    if not is_authorised(update.effective_user.id):
        return
    import sender
    ss = sender.get_status_snapshot()
    lines = [
        "Status:",
        f"  App running:      Yes",
        f"  Send mode:        {ss['send_mode']}",
        f"  Telethon ready:   {'Yes' if ss['telethon_ready'] else 'No — run telethon_login.py'}",
        f"  DRY_RUN:          {ss['dry_run']}",
        f"  SEND_ENABLED:     {ss['send_enabled']}",
        f"  Wife target:      {ss['wife_target']}",
        "",
        "Rate limiting:",
        f"  Sends today:      {ss['sends_today']}/{ss['max_sends_per_day']}",
        f"  Min gap:          {ss['min_seconds_between']}s",
        f"  Last send:        {ss['last_send']}",
        "",
        "Nudge reminder:",
        f"  Pending:          {'Yes' if _nudge_scheduled_at else 'No'}",
        f"  Fires at:         {_nudge_scheduled_at.strftime('%H:%M') if _nudge_scheduled_at else '—'}",
    ]
    await update.message.reply_text("\n".join(lines))


# ── /testprompt ────────────────────────────────────────────────────────────────
async def cmd_testprompt(update, context):
    if not is_authorised(update.effective_user.id):
        return
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="End work or extend?",
        reply_markup=main_keyboard(),
    )
    _schedule_nudge(update.effective_chat.id)
    logger.info("/testprompt sent to user_id=%s", update.effective_user.id)


# ── /cancel ────────────────────────────────────────────────────────────────────
async def cmd_cancel(update, context):
    if not is_authorised(update.effective_user.id):
        return
    _cancel_nudge()
    await update.message.reply_text("Cancelled.")
    return ConversationHandler.END


# ── Custom duration text handler ───────────────────────────────────────────────
async def handle_custom_duration(update, context):
    if not is_authorised(update.effective_user.id):
        return WAITING_CUSTOM_DURATION

    import sender
    duration = update.message.text.strip()
    valid, result = sender.validate_duration(duration)

    if not valid:
        await update.message.reply_text(
            f"{result}\n\nEnter a short duration (e.g. '20 mins', '1 hour') or /cancel."
        )
        return WAITING_CUSTOM_DURATION

    context.user_data["_pending_duration"] = result
    context.user_data["_send_type"] = "extend"
    preview_msg = sender.TEMPLATE_EXTEND.format(duration=result)
    await update.message.reply_text(
        f"Send this message?\n\n{preview_msg}",
        reply_markup=preview_keyboard(),
    )
    return ConversationHandler.END


# ── Callback: main menu ────────────────────────────────────────────────────────
async def cb_main(update, context):
    query = update.callback_query
    await query.answer()
    if not is_authorised(query.from_user.id):
        return

    choice = query.data

    if choice == "end_work":
        _cancel_nudge()
        import sender
        ok, msg = sender.send_end_work()
        if ok:
            preview_msg = sender.TEMPLATE_END_WORK
            context.user_data["_send_type"] = "end_work"
            context.user_data["_pending_preview"] = preview_msg
            await query.edit_message_text(
                text=f"Send this message?\n\n{preview_msg}",
                reply_markup=preview_keyboard(),
            )
        else:
            await query.edit_message_text(text=f"⚠️ {msg}")

    elif choice == "extend":
        await query.edit_message_text(
            text="How long do you need to stay back?",
            reply_markup=duration_keyboard(),
        )

    elif choice == "no_message":
        _cancel_nudge()
        await query.edit_message_text(text="Okay, no message sent today.")


# ── Callback: duration selection ────────────────────────────────────────────────
async def cb_duration(update, context):
    query = update.callback_query
    await query.answer()
    if not is_authorised(query.from_user.id):
        return

    choice = query.data

    if choice == "dur_custom":
        await query.edit_message_text(
            text="Enter how long you need to stay back (e.g. '20 mins', '1 hour', '45 minutes'):"
        )
        return WAITING_CUSTOM_DURATION

    duration_map = {"dur_10": "10 mins", "dur_30": "30 mins", "dur_60": "1 hour"}
    duration = duration_map.get(choice)
    if not duration:
        return

    import sender
    preview_msg = sender.TEMPLATE_EXTEND.format(duration=duration)
    context.user_data["_pending_duration"] = duration
    context.user_data["_send_type"] = "extend"
    context.user_data["_pending_preview"] = preview_msg

    await query.edit_message_text(
        text=f"Send this message?\n\n{preview_msg}",
        reply_markup=preview_keyboard(),
    )
    logger.info("Preview for EXTEND (%s) by user_id=%s", duration, query.from_user.id)


# ── Callback: send confirmation ────────────────────────────────────────────────
async def cb_confirm(update, context):
    query = update.callback_query
    await query.answer()
    if not is_authorised(query.from_user.id):
        return

    choice = query.data

    if choice == "confirm_no":
        _cancel_nudge()
        await query.edit_message_text(text="Cancelled — nothing sent.")
        return

    if choice != "confirm_yes":
        return

    import sender

    send_type = context.user_data.get("_send_type", "extend")
    duration  = context.user_data.get("_pending_duration", "")
    preview   = context.user_data.get("_pending_preview", "")

    if send_type == "end_work":
        ok, msg = sender.send_end_work()
    else:
        ok, msg = sender.send_extend(duration or "unknown")

    context.user_data.pop("_pending_preview", None)
    context.user_data.pop("_pending_duration", None)
    context.user_data.pop("_send_type", None)

    if ok:
        _cancel_nudge()
        if sender.DRY_RUN:
            await query.edit_message_text(
                text=f"DRY RUN — nothing actually sent.\n\n{preview}"
            )
        else:
            await query.edit_message_text(text="✅ Message sent to your wife.")
    else:
        await query.edit_message_text(text=f"⚠️ Send failed: {msg}")


# ── Build app ─────────────────────────────────────────────────────────────────
def build_app():
    from telegram.ext import (
        Application, CommandHandler, CallbackQueryHandler,
        ConversationHandler, MessageHandler, filters,
    )
    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_duration, pattern="^dur_custom$")],
        states={
            WAITING_CUSTOM_DURATION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_custom_duration),
                CommandHandler("cancel", cmd_cancel),
            ],
        },
        fallbacks=[CommandHandler("cancel", cmd_cancel)],
    )

    app.add_handler(CommandHandler("start",      cmd_start))
    app.add_handler(CommandHandler("status",     cmd_status))
    app.add_handler(CommandHandler("testprompt", cmd_testprompt))
    app.add_handler(CommandHandler("cancel",    cmd_cancel))
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(cb_main,     pattern="^(end_work|extend|no_message)$"))
    app.add_handler(CallbackQueryHandler(cb_duration, pattern="^dur_"))
    app.add_handler(CallbackQueryHandler(cb_confirm,   pattern="^confirm_"))

    return app


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    global _scheduler_ref

    logger.info("=== Office Late Reminder starting ===")

    missing = []
    if not BOT_TOKEN:   missing.append("BOT_TOKEN")
    if not MY_USER_ID:  missing.append("MY_TELEGRAM_USER_ID")
    if not WIFE_TARGET: missing.append("WIFE_TELEGRAM_TARGET")
    if missing:
        logger.error("Missing required .env values: %s", ", ".join(missing))
        sys.exit(1)

    import sender
    sender.init_telethon()

    app = build_app()

    if ENABLE_SCHEDULER:
        from apscheduler.schedulers.blocking import BlockingScheduler
        from apscheduler.triggers.cron import CronTrigger
        scheduler = BlockingScheduler(timezone=TIMEZONE_STR)
        _scheduler_ref = app

        scheduler.add_job(
            lambda: cmd_testprompt(
                type("Req", (), {"effective_user": type("U", (), {"id": MY_USER_ID})(),
                                  "effective_chat": type("C", (), {"id": MY_USER_ID})()})(),
                None,
            ),
            CronTrigger(day_of_week="mon-fri", hour=18, minute=0, timezone=TIMEZONE),
            id="office_late_reminder",
            misfire_grace_time=60,
        )
        scheduler.add_job(
            lambda: _schedule_nudge(MY_USER_ID),
            CronTrigger(day_of_week="mon-fri", hour=18, minute=10, timezone=TIMEZONE),
            id="nudge_reminder",
            misfire_grace_time=60,
        )
        import threading
        t = threading.Thread(target=scheduler.start, daemon=True)
        t.start()
        logger.info("Scheduler started — 6 PM Mon-Fri SGT, nudge at 6:10 PM")
    else:
        logger.info("Scheduler disabled — use /testprompt to trigger manually")

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down...")
        import sender
        sender.close_telethon_client()