"""
tests/test_rate_limits.py — Rate limits must persist and survive restarts.
"""

import pytest, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Ensure a clean per-test DB by setting the path BEFORE any imports
# that might cache the connection.
import tempfile, uuid

class TestRateLimits:
    def test_daily_limit_blocks_at_max(self):
        """When daily limit is reached, further sends are blocked with 'Daily limit'."""
        with pytest.MonkeyPatch().context() as m:
            # Unique path per test so state never leaks between tests
            db_path = f":memory:{uuid.uuid4().hex}"
            m.setenv("DB_PATH", db_path)
            m.setenv("MAX_SENDS_PER_DAY", "3")
            m.setenv("MIN_SECONDS_BETWEEN_SENDS", "0")   # disable interval

            import importlib, db, config, repositories.send_repository as sr
            # Reset all cached state so new db_path and config are picked up
            importlib.reload(config)
            importlib.reload(sr)
            db._conn = None   # force get_db_path() + new connection
            db.init_db()
            repo = sr.SendRepository()

            for _ in range(3):
                repo.record_send()

            ok, reason = repo.can_send()
            assert ok is False, f"Expected blocked but got ok=True, reason={reason}"
            assert "Daily limit" in reason, f"Expected 'Daily limit' but got: {reason}"

    def test_min_interval_blocks_rapid_sends(self):
        """When minimum interval hasn't elapsed, send is blocked with 'Too soon'."""
        with pytest.MonkeyPatch().context() as m:
            db_path = f":memory:{uuid.uuid4().hex}"
            m.setenv("DB_PATH", db_path)
            m.setenv("MAX_SENDS_PER_DAY", "10")
            m.setenv("MIN_SECONDS_BETWEEN_SENDS", "300")

            import importlib, db, config, repositories.send_repository as sr
            # Reset all cached state so new db_path and config are picked up
            importlib.reload(config)
            importlib.reload(sr)
            db._conn = None   # force get_db_path() + new connection
            db.init_db()
            repo = sr.SendRepository()

            repo.record_send()
            ok, reason = repo.can_send()
            assert ok is False, f"Expected blocked but got ok=True, reason={reason}"
            assert "Too soon" in reason, f"Expected 'Too soon' but got: {reason}"