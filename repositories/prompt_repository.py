"""
repositories/prompt_repository.py — Prompt request persistence.
"""

import db
from models import PromptRequest, RequestStatus
from utils.time_utils import utc_now, parse_iso_utc, add_minutes
from utils.ids import new_request_id
import config
from datetime import datetime


class PromptRepository:
    """CRUD for prompt_request rows."""

    def create(
        self,
        owner_user_id: str,
        expires_in_minutes: int = 30,
        nudge_delay_minutes: int = 10,
    ) -> PromptRequest:
        now_utc = utc_now()
        expires_at = add_minutes(now_utc, expires_in_minutes)
        nudge_due_at = add_minutes(now_utc, nudge_delay_minutes)

        req = PromptRequest(
            id=new_request_id(),
            owner_user_id=str(owner_user_id),
            recipient_key=config.WIFE_TARGET,
            status=RequestStatus.AWAITING_CHOICE,
            created_at=now_utc,
            updated_at=now_utc,
            expires_at=expires_at,
            nudge_due_at=nudge_due_at,
        )

        with db.get_db() as conn:
            conn.execute(
                """
                INSERT INTO prompt_requests
                (id, owner_user_id, recipient_key, status, created_at, updated_at,
                 expires_at, nudge_due_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    req.id, req.owner_user_id, req.recipient_key, req.status.value,
                    req.created_at.isoformat(), req.updated_at.isoformat(),
                    req.expires_at.isoformat(), req.nudge_due_at.isoformat(),
                ),
            )
        return req

    def get(self, request_id: str) -> PromptRequest | None:
        with db.get_db() as conn:
            row = conn.execute(
                "SELECT * FROM prompt_requests WHERE id = ?", (request_id,)
            ).fetchone()
        return self._row_to_model(row) if row else None

    def get_active_for_user(self, owner_user_id: str) -> list[PromptRequest]:
        with db.get_db() as conn:
            rows = conn.execute(
                """
                SELECT * FROM prompt_requests
                WHERE owner_user_id = ?
                  AND status IN ('awaiting_choice','awaiting_custom_text','awaiting_confirmation')
                ORDER BY created_at DESC
                """,
                (str(owner_user_id),),
            ).fetchall()
        return [self._row_to_model(r) for r in rows]

    def get_pending_nudges(self) -> list[PromptRequest]:
        """Requests that are still active and have a nudge due."""
        now_utc = utc_now().isoformat()
        with db.get_db() as conn:
            rows = conn.execute(
                """
                SELECT * FROM prompt_requests
                WHERE nudge_due_at IS NOT NULL
                  AND nudged_at IS NULL
                  AND status IN ('awaiting_choice','awaiting_custom_text','awaiting_confirmation')
                  AND nudge_due_at <= ?
                """,
                (now_utc,),
            ).fetchall()
        return [self._row_to_model(r) for r in rows]

    def update_status(self, request_id: str, status: RequestStatus) -> bool:
        now = utc_now().isoformat()
        with db.get_db() as conn:
            cur = conn.execute(
                "UPDATE prompt_requests SET status = ?, updated_at = ? WHERE id = ?",
                (status.value, now, request_id),
            )
        return cur.rowcount > 0

    def transition_status(
        self,
        request_id: str,
        from_status: RequestStatus,
        to_status: RequestStatus,
    ) -> bool:
        """
        Atomically transition a request's status.
        Returns True only if the request existed and was in from_status.
        This prevents double-send race conditions.
        """
        now = utc_now().isoformat()
        with db.get_db() as conn:
            cur = conn.execute(
                """
                UPDATE prompt_requests
                SET status = ?, updated_at = ?
                WHERE id = ? AND status = ?
                """,
                (to_status.value, now, request_id, from_status.value),
            )
        return cur.rowcount == 1

    def set_choice(
        self,
        request_id: str,
        choice_type: str,
        custom_text: str | None = None,
        preview_text: str | None = None,
    ):
        now = utc_now().isoformat()
        with db.get_db() as conn:
            conn.execute(
                """
                UPDATE prompt_requests
                SET choice_type=?, custom_text=?, preview_text=?,
                    status=?, updated_at=?
                WHERE id=?
                """,
                (
                    choice_type, custom_text, preview_text,
                    RequestStatus.AWAITING_CONFIRMATION.value, now, request_id,
                ),
            )

    def mark_sent(self, request_id: str):
        now = utc_now().isoformat()
        with db.get_db() as conn:
            conn.execute(
                """
                UPDATE prompt_requests
                SET status='sent', sent_at=?, updated_at=?, nudge_due_at=NULL
                WHERE id=?
                """,
                (now, now, request_id),
            )

    def mark_cancelled(self, request_id: str):
        now = utc_now().isoformat()
        with db.get_db() as conn:
            conn.execute(
                """
                UPDATE prompt_requests
                SET status='cancelled', cancelled_at=?, updated_at=?, nudge_due_at=NULL
                WHERE id=?
                """,
                (now, now, request_id),
            )

    def mark_expired(self, request_id: str):
        now = utc_now().isoformat()
        with db.get_db() as conn:
            conn.execute(
                """
                UPDATE prompt_requests
                SET status='expired', updated_at=?, nudge_due_at=NULL
                WHERE id=?
                """,
                (now, request_id),
            )

    def mark_failed(self, request_id: str, error_code: str, error_message: str):
        now = utc_now().isoformat()
        with db.get_db() as conn:
            conn.execute(
                """
                UPDATE prompt_requests
                SET status='failed', failed_at=?, updated_at=?,
                    error_code=?, error_message=?, nudge_due_at=NULL
                WHERE id=?
                """,
                (now, now, error_code, error_message, request_id),
            )

    def mark_nudged(self, request_id: str):
        now = utc_now().isoformat()
        with db.get_db() as conn:
            conn.execute(
                "UPDATE prompt_requests SET nudged_at=? WHERE id=?",
                (now, request_id),
            )

    def cancel_nudge(self, request_id: str):
        with db.get_db() as conn:
            conn.execute(
                "UPDATE prompt_requests SET nudge_due_at=NULL WHERE id=?",
                (request_id,),
            )

    def _row_to_model(self, row) -> PromptRequest:
        def _dt(val):
            return parse_iso_utc(val) if val else None

        return PromptRequest(
            id=row["id"],
            owner_user_id=row["owner_user_id"],
            recipient_key=row["recipient_key"],
            status=RequestStatus(row["status"]),
            choice_type=row["choice_type"],
            custom_text=row["custom_text"],
            preview_text=row["preview_text"],
            created_at=_dt(row["created_at"]),
            updated_at=_dt(row["updated_at"]),
            expires_at=_dt(row["expires_at"]),
            nudge_due_at=_dt(row["nudge_due_at"]),
            nudged_at=_dt(row["nudged_at"]),
            confirmed_at=_dt(row["confirmed_at"]),
            sent_at=_dt(row["sent_at"]),
            cancelled_at=_dt(row["cancelled_at"]),
            failed_at=_dt(row["failed_at"]),
            error_code=row["error_code"],
            error_message=row["error_message"],
        )