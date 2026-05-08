"""
app.py — Office Late Reminder: main Telegram bot entrypoint.

Wires together:
  telegram_handlers  → command, callback, text handlers
  services           → workflow, nudge, status, delivery, auth, validation
  repositories       → prompt, send, audit, runtime (SQLite persistence)
  telethon_client    → background user-client send
  scheduler          → APScheduler for 6 PM Mon–Fri prompt + nudge delivery
"""

import logging
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
import db
import logging_config
from logging_config import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

# ── Init SQLite ──────────────────────────────────────────────────────────────
db.init_db()

# ── Init Telethon in background thread ────────────────────────────────────────
import telethon_client.telethon_sender as tsender
tsender.init()
logger.info("Telethon background loop started")


def build_app():
    from telegram.ext import (
        Application, CommandHandler, CallbackQueryHandler,
        MessageHandler, filters,
    )
    from telegram_handlers import command_handlers, callback_handlers, text_handlers

    app = (
        Application.builder()
        .token(config.BOT_TOKEN)
        .build()
    )

    # Commands
    app.add_handler(CommandHandler("start",     command_handlers.cmd_start))
    app.add_handler(CommandHandler("testprompt",command_handlers.cmd_testprompt))
    app.add_handler(CommandHandler("status",    command_handlers.cmd_status))
    app.add_handler(CommandHandler("cancel",    command_handlers.cmd_cancel))

    # Callbacks
    app.add_handler(CallbackQueryHandler(callback_handlers.cb_root))

    # Text (free input — only active in AWAITING_CUSTOM_TEXT state)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handlers.handle_text))

    return app


def main():
    logger.info("=== Office Late Reminder starting ===")

    missing = []
    if not config.BOT_TOKEN:       missing.append("BOT_TOKEN")
    if not config.MY_USER_ID:      missing.append("MY_TELEGRAM_USER_ID")
    if not config.WIFE_TARGET:    missing.append("WIFE_TELEGRAM_TARGET")
    if not config.TELETHON_API_ID: missing.append("TELEGRAM_API_ID")
    if not config.TELETHON_API_HASH: missing.append("TELEGRAM_API_HASH")
    if missing:
        logger.error("Missing required .env values: %s", ", ".join(missing))
        sys.exit(1)

    app = build_app()

    if config.ENABLE_SCHEDULER:
        from scheduler import scheduler_runner
        scheduler_runner.start(app)
    else:
        logger.info("Scheduler disabled — use /testprompt to trigger manually")

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down...")
        tsender.close()