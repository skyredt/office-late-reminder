"""
services/rate_limit_service.py — Rate limiting using SQLite persistence.
"""

import logging
import config
import repositories.send_repository as send_repo


logger = logging.getLogger(__name__)
_repo = send_repo.SendRepository()


class RateLimitResult:
    def __init__(self, allowed: bool, reason: str = ""):
        self.allowed = allowed
        self.reason = reason


def check() -> RateLimitResult:
    """
    Primary rate-limit check.
    Called by workflow_service BEFORE any delivery is attempted.
    """
    allowed, reason = _repo.can_send()
    if not allowed:
        logger.info("Rate limit blocked: %s", reason)
    return RateLimitResult(allowed, reason)


def get_today_count() -> int:
    return _repo.get_today_count()


def get_last_send_time() -> str:
    return _repo.get_last_send_time()