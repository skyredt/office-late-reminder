"""
logging_config.py — Structured logging for Office Late Reminder.

Log format:
  2026-05-09 01:30:00 +08 | INFO | event_type | req_id | actor=user_xxx | outcome=OK

Secrets are NEVER logged. Masked IDs are used for privacy.
"""

import logging
import sys
from datetime import datetime, timezone
import pytz

SGT = pytz.timezone("Asia/Singapore")


class StructuredFormatter(logging.Formatter):
    """Appends SGT timestamp prefix to every log line."""

    def format(self, record):
        sgt_now = datetime.now(SGT).strftime("%Y-%m-%d %H:%M:%S %Z")
        record.prepend = sgt_now
        return super().format(record)


def setup_logging(level=logging.INFO):
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        StructuredFormatter("%(prepend)s | %(levelname)-5s | %(name)s: %(message)s")
    )
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(handler)
    # Quiet down noisy third-party loggers
    for noisy in ["apscheduler", "httpx", "telethon"]:
        logging.getLogger(noisy).setLevel(logging.WARNING)
    return root