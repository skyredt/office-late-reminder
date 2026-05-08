"""
tests/test_rate_limits.py — Rate limits must persist and survive restarts.
"""

import pytest, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestRateLimits:
    def test_daily_limit_blocks_at_max(self):
        with pytest.MonkeyPatch().context() as m:
            m.setenv("DB_PATH", ":memory:")
            m.setenv("MAX_SENDS_PER_DAY", "3")
            m.setenv("MIN_SECONDS_BETWEEN_SENDS", "300")

            import importlib, db, repositories.send_repository as sr
            db.init_db()
            importlib.reload(sr)
            repo = sr.SendRepository()

            # Fill up to the limit
            for _ in range(3):
                repo.record_send()

            ok, reason = repo.can_send()
            assert ok is False
            assert "Daily limit" in reason

    def test_min_interval_blocks_ rapid_sends(self):
        with pytest.MonkeyPatch().context() as m:
            m.setenv("DB_PATH", ":memory:")
            m.setenv("MAX_SENDS_PER_DAY", "10")
            m.setenv("MIN_SECONDS_BETWEEN_SENDS", "300")

            import importlib, db, repositories.send_repository as sr
            db.init_db()
            importlib.reload(sr)
            repo = sr.SendRepository()

            repo.record_send()
            ok, reason = repo.can_send()
            assert ok is False
            assert "Too soon" in reason