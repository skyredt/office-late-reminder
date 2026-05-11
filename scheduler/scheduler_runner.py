"""
scheduler/scheduler_runner.py — APScheduler setup and nudge delivery.

Responsibilities:
- Schedule the daily 6 PM prompt (Mon–Fri)
- On startup, restore and reschedule any pending nudges from SQLite
- Run nudge delivery jobs when they come due
"""

import logging
import threading
import config
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

import services.workflow_service as workflow
import services.nudge_service as nudge_svc
import repositories.prompt_repository as prompt_repo
import telegram_handlers.common as common
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


logger = logging.getLogger(__name__)
_scheduler = None
_scheduler_ref = None



def _utc_naive_to_scheduler_tz(dt):
    """Convert a naive UTC datetime to timezone-aware Singapore time for APScheduler."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = pytz.UTC.localize(dt)
    return dt.astimezone(pytz.timezone(config.TIMEZONE_STR))

def _deliver_nudge(request_id: str, chat_id: int, bot):
    """
    Called by APScheduler when a nudge is due.
    Runs in the scheduler thread — safe to call sync bot.send_message.
    """
    req = prompt_repo.PromptRepository().get(request_id)

    if req is None:
        logger.info("Nudge skipped: request %s not found", request_id[-8:])
        return

    if not req.is_active():
        logger.info("Nudge skipped: request %s is %s (not active)", request_id[-8:], req.status.value)
        prompt_repo.PromptRepository().mark_nudged(request_id)
        return

    # Send nudge to user
    try:
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(
            bot.send_message(
                chat_id=chat_id,
                text=nudge_svc.nudge_message(),
                reply_markup=InlineKeyboardMarkup(nudge_svc.nudge_keyboard(request_id)),
            )
        )
        loop.close()
        prompt_repo.PromptRepository().mark_nudged(request_id)
        logger.info("Nudge sent for req=%s", request_id[-8:])
    except Exception as e:
        logger.error("Nudge delivery failed for req=%s: %s", request_id[-8:], e)


def _scheduled_prompt(chat_id: int, bot):
    """Called at 6 PM Mon–Fri. Starts the workflow and sends the prompt to Telegram."""
    import asyncio
    from datetime import datetime

    result = workflow.start_prompt(chat_id)

    if result.ok:
        # ── Send the prompt message to the user's Telegram chat ────────────
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(
                bot.send_message(
                    chat_id=chat_id,
                    text=result.message,
                    reply_markup=InlineKeyboardMarkup(result.buttons) if result.buttons else None,
                )
            )
            loop.close()
            logger.info("Scheduled prompt sent req=%s", result.request_id[-8:] if result.request_id else "n/a")
        except Exception as e:
            logger.error("Scheduled prompt send failed: %s", e)
    else:
        logger.error("Scheduled prompt workflow failed: %s", result.message)

    # ── Schedule nudge using nudge_due_at stored in SQLite by prompt_repo.create() ──
    if result.request_id and _scheduler_ref is not None:
        req = prompt_repo.PromptRepository().get(result.request_id)
        nudge_time = _utc_naive_to_scheduler_tz(req.nudge_due_at) if req and req.nudge_due_at else None

        if nudge_time:
            _scheduler_ref.add_job(
                _deliver_nudge,
                "date",
                run_date=nudge_time,
                args=[result.request_id, chat_id, bot],
                id=f"nudge_{result.request_id[-8:]}",
                misfire_grace_time=60,
                replace_existing=True,
            )
            logger.info("Nudge scheduled for req=%s at %s", result.request_id[-8:], nudge_time)
        else:
            logger.warning("No nudge_due_at found for req=%s", result.request_id[-8:])
    elif _scheduler_ref is None:
        logger.warning("Scheduler not ready — nudge not scheduled")


def start(app) -> BlockingScheduler:
    global _scheduler, _scheduler_ref

    _scheduler = BlockingScheduler(timezone=config.TIMEZONE_STR)
    _scheduler_ref = _scheduler

    # ── Daily 6 PM prompt (Mon–Fri) ──────────────────────────────────────
    _scheduler.add_job(
        _scheduled_prompt,
        CronTrigger(day_of_week="mon-fri", hour=config.SCHEDULER_HOUR,
                    minute=config.SCHEDULER_MINUTE, timezone=config.TIMEZONE_STR),
        args=[config.MY_USER_ID, app.bot],
        id="office_late_prompt",
        misfire_grace_time=60,
    )

    # ── Restore pending nudges from SQLite on startup ──────────────────────
    pending = prompt_repo.PromptRepository().get_pending_nudges()
    for req in pending:
        if req.nudge_due_at is None:
            continue
        # Schedule nudge at stored nudge_due_at
        _scheduler.add_job(
            _deliver_nudge,
            "date",
            run_date=_utc_naive_to_scheduler_tz(req.nudge_due_at),
            args=[req.id, config.MY_USER_ID, app.bot],
            id=f"nudge_{req.id}",
            misfire_grace_time=300,
            replace_existing=True,
        )
        logger.info("Restored pending nudge for req=%s (due %s)", req.id[-8:], req.nudge_due_at)

    t = threading.Thread(target=_scheduler.start, daemon=True, name="apscheduler")
    t.start()
    logger.info("Scheduler started — prompt at %02d:%02d Mon–Fri %s",
                config.SCHEDULER_HOUR, config.SCHEDULER_MINUTE, config.TIMEZONE_STR)

    return _scheduler


def get_scheduler():
    return _scheduler_ref
