"""
services/auth_service.py — Centralised authorization guard.
Every handler (commands, callbacks, text) delegates here.
"""

import logging
import config
import repositories.audit_repository as audit_repo


logger = logging.getLogger(__name__)
_audit = audit_repo.AuditRepository()


def is_authorised(user_id: int) -> bool:
    """Return True iff the user matches the configured owner."""
    return user_id == config.MY_USER_ID


def require_auth(user_id: int, request_id: str | None = None) -> bool:
    """
    Authorize or reject a user. Logs all attempts (masked).
    Returns True if authorized, False otherwise.
    """
    if is_authorised(user_id):
        return True

    logger.warning(
        "Unauthorized access attempt | user=%s | req=%s",
        _mask(user_id),
        request_id or "-",
    )
    _audit.log(
        event_type="auth_rejected",
        actor_user_id=user_id,
        request_id=request_id,
        outcome="REJECTED",
    )
    return False


def _mask(uid: int) -> str:
    s = str(uid)
    return f"user_{'x' * (len(s) - 3)}{s[-3:]}"