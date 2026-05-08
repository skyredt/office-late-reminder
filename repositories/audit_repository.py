"""
repositories/audit_repository.py — Audit log for security and debugging.
"""

import db
from utils.ids import new_audit_id
from utils.time_utils import utc_now
from utils.masking import mask_user_id


class AuditRepository:
    """Append-only audit log. No UPDATE or DELETE operations."""

    def log(
        self,
        event_type: str,
        actor_user_id: int | None = None,
        request_id: str | None = None,
        details_masked: str | None = None,
        outcome: str = "OK",
    ):
        now = utc_now()
        row_id = new_audit_id()
        masked_actor = mask_user_id(actor_user_id) if actor_user_id else None

        with db.get_db() as conn:
            conn.execute(
                """
                INSERT INTO audit_log
                (id, timestamp, actor_user_id_masked, event_type, request_id, details_masked, outcome)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (row_id, now.isoformat(), masked_actor, event_type, request_id, details_masked, outcome),
            )

    def recent(self, limit: int = 50) -> list[dict]:
        with db.get_db() as conn:
            rows = conn.execute(
                "SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]