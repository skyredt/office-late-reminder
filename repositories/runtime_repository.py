"""
repositories/runtime_repository.py — Runtime state queries.
"""

import db
from utils.time_utils import utc_now


class RuntimeRepository:
    """Read runtime counters and active request summaries."""

    def get_active_request_count(self) -> int:
        with db.get_db() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) as cnt FROM prompt_requests
                WHERE status IN ('awaiting_choice','awaiting_custom_text','awaiting_confirmation')
                """
            ).fetchone()
        return row["cnt"] if row else 0

    def get_pending_nudge_count(self) -> int:
        now_utc = utc_now().isoformat()
        with db.get_db() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) as cnt FROM prompt_requests
                WHERE nudge_due_at IS NOT NULL
                  AND nudged_at IS NULL
                  AND status IN ('awaiting_choice','awaiting_custom_text','awaiting_confirmation')
                  AND nudge_due_at <= ?
                """,
                (now_utc,),
            ).fetchone()
        return row["cnt"] if row else 0

    def get_last_error(self) -> dict | None:
        with db.get_db() as conn:
            row = conn.execute(
                """
                SELECT error_code, error_message, updated_at
                FROM prompt_requests
                WHERE error_code IS NOT NULL
                ORDER BY updated_at DESC LIMIT 1
                """
            ).fetchone()
        return dict(row) if row else None