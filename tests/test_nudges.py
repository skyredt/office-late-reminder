"""
tests/test_nudges.py — Nudges fire only for active requests.
"""

import pytest
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestNudges:
    def test_nudge_not_sent_for_sent_request(self):
        """mark_sent() removes the request from the pending nudge queue."""
        import db
        from repositories.prompt_repository import PromptRepository

        db.reset_db()
        repo = PromptRepository()
        req = repo.create(131288677)
        repo.mark_sent(req.id)

        pending = repo.get_pending_nudges()
        assert all(r.id != req.id for r in pending)

    def test_nudge_not_sent_for_cancelled_request(self):
        """mark_cancelled() removes the request from the pending nudge queue."""
        import db
        from repositories.prompt_repository import PromptRepository

        db.reset_db()
        repo = PromptRepository()
        req = repo.create(131288677)
        repo.mark_cancelled(req.id)

        pending = repo.get_pending_nudges()
        assert all(r.id != req.id for r in pending)
