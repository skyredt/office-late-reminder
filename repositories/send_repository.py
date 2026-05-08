"""
repositories/send_repository.py — Daily send counter persistence.
"""

import db
from utils.time_utils import utc_now, to_sgt_iso
import config


class SendRepository:
    """Manages daily send count and last-send timestamp via SQLite."""

    def get_today_count(self) -> int:
        today = str(utc_now().date())
        with db.get_db() as conn:
            row = conn.execute(
                "SELECT send_count FROM runtime_counters WHERE counter_date = ?",
                (today,),
            ).fetchone()
        return row["send_count"] if row else 0

    def get_last_send_time(self) -> str:
        today = str(utc_now().date())
        with db.get_db() as conn:
            row = conn.execute(
                "SELECT last_send_at FROM runtime_counters WHERE counter_date = ?",
                (today,),
            ).fetchone()
        if not row or not row["last_send_at"]:
            return "Never"
        return to_sgt_iso(float(row["last_send_at"]))

    def can_send(self) -> tuple[bool, str]:
        """
        Returns (allowed, reason).
        Checks both daily limit and minimum interval.
        """
        today = str(utc_now().date())
        with db.get_db() as conn:
            row = conn.execute(
                "SELECT send_count, last_send_at FROM runtime_counters WHERE counter_date = ?",
                (today,),
            ).fetchone()

        count = row["send_count"] if row else 0
        if count >= config.MAX_SENDS_PER_DAY:
            return False, f"Daily limit reached ({count}/{config.MAX_SENDS_PER_DAY})."

        if row and row["last_send_at"]:
            elapsed = utc_now().timestamp() - float(row["last_send_at"])
            if elapsed < config.MIN_SECONDS_BETWEEN_SENDS:
                remaining = int(config.MIN_SECONDS_BETWEEN_SENDS - elapsed)
                return False, f"Too soon — wait {remaining}s between sends."

        return True, ""

    def record_send(self):
        """Increment today's counter and update last-send time."""
        today = str(utc_now().date())
        now_ts = str(utc_now().timestamp())
        with db.get_db() as conn:
            conn.execute(
                """
                INSERT INTO runtime_counters (counter_date, send_count, last_send_at)
                VALUES (?, 1, ?)
                ON CONFLICT(counter_date) DO UPDATE SET
                    send_count = send_count + 1,
                    last_send_at = excluded.last_send_at
                """,
                (today, now_ts),
            )