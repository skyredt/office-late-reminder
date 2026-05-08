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
from telegram import InlineKeyboardButton


logger = logging.getLogger(__name__)
_scheduler = None
_scheduler_ref = None


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
    """Called at 6 PM Mon–Fri. Starts the workflow and schedules the nudge."""
    from datetime import datetime
    req = workflow.start_prompt(chat_id)

    # Schedule nudge
    nudge_time = datetime.now(pytz.timezone(config.TIMEZONE_STR))
    nudge_time = nudge_time.replace(second=0, microsecond=0)
    nudge_time = nudge_time.replace(minute=nudge_time.minute + config.NUDGE_DELAY_MINUTES)

    if _scheduler_ref is not None:
        _scheduler_ref.add_job(
            _deliver_nudge,
            "date",
            run_date=nudge_time,
            args=[req.preview_text.split("||")[0] if "||" in (req.preview_text or "") else req.message, chat_id, bot],
            id=f"nudge_{req.preview_text}",
            misfire_grace_time=60,
            replace_existing=True,
        )


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
            run_date=req.nudge_due_at,
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
