"""
services/status_service.py — Consolidated /status output.
"""

import logging
import config
import repositories.send_repository as send_repo
import repositories.runtime_repository as runtime_repo
import repositories.audit_repository as audit_repo
import telethon_client.telethon_sender as tsender


logger = logging.getLogger(__name__)
_send_repo = send_repo.SendRepository()
_runtime_repo = runtime_repo.RuntimeRepository()


def get_status(user_id: int) -> str:
    """Build a comprehensive status report."""
    telethon_ready = tsender.is_authorized()
    telethon_display = tsender.get_display_name() if telethon_ready else "N/A"

    today_count = _send_repo.get_today_count()
    last_send = _send_repo.get_last_send_time()
    active_count = _runtime_repo.get_active_request_count()
    pending_nudges = _runtime_repo.get_pending_nudge_count()
    last_error = _runtime_repo.get_last_error()

    lines = [
        "Status:",
        f"  Bot running:       Yes",
        f"  Send mode:         {config.SEND_MODE}",
        f"  Telethon:          {'OK' if telethon_ready else 'MISSING or UNAUTHORISED'} ({telethon_display})",
        f"  Dry run:           {config.DRY_RUN}",
        f"  Send enabled:      {config.SEND_ENABLED}",
        f"  Sends today:       {today_count}/{config.MAX_SENDS_PER_DAY}",
        f"  Min send gap:      {config.MIN_SECONDS_BETWEEN_SENDS}s",
        f"  Last send:         {last_send}",
        f"  Active requests:   {active_count}",
        f"  Pending nudges:    {pending_nudges}",
        f"  Scheduler:         {'enabled' if config.ENABLE_SCHEDULER else 'disabled'} ({config.SCHEDULER_HOUR}:{config.SCHEDULER_MINUTE:02d} SGT Mon–Fri)",
        f"  Wife target:        {config.WIFE_TARGET}",
    ]

    if last_error:
        lines.append(f"  Last error:        [{last_error['error_code']}] {last_error['error_message']}")

    return "\n".join(lines)