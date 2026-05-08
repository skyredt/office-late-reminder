"""
tests/test_nudges.py — Nudges fire only for active requests.
"""

import pytest, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestNudges:
    def test_nudge_not_sent_for_sent_request(self):
        with pytest.MonkeyPatch().context() as m:
            m.setenv("DB_PATH", ":memory:")
            m.setenv("MY_TELEGRAM_USER_ID", "131288677")
            m.setenv("WIFE_TELEGRAM_TARGET", "+6588117751")

            import importlib, db
            db.init_db()   # creates tables

            from repositories.prompt_repository import PromptRepository
            # Ensure module is fresh with in-memory DB
            importlib.reload(db)
            repo = PromptRepository()
            req = repo.create(131288677)
            repo.mark_sent(req.id)

            pending = repo.get_pending_nudges()
            assert all(r.id != req.id for r in pending)

    def test_nudge_not_sent_for_cancelled_request(self):
        with pytest.MonkeyPatch().context() as m:
            m.setenv("DB_PATH", ":memory:")
            m.setenv("MY_TELEGRAM_USER_ID", "131288677")
            m.setenv("WIFE_TELEGRAM_TARGET", "+6588117751")

            import importlib, db
            db.init_db()
            importlib.reload(db)
            from repositories.prompt_repository import PromptRepository

            repo = PromptRepository()
            req = repo.create(131288677)
            repo.mark_cancelled(req.id)

            pending = repo.get_pending_nudges()
            assert all(r.id != req.id for r in pending)