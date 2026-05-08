"""
tests/test_status.py — /status shows all required fields.
"""

from unittest.mock import patch
import pytest, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestStatus:
    def test_status_includes_all_required_fields(self):
        with pytest.MonkeyPatch().context() as m:
            m.setenv("DB_PATH", ":memory:")
            m.setenv("BOT_TOKEN", "123456:ABC")
            m.setenv("MY_TELEGRAM_USER_ID", "131288677")
            m.setenv("TELEGRAM_API_ID", "12345")
            m.setenv("TELEGRAM_API_HASH", "abcdef")
            m.setenv("WIFE_TELEGRAM_TARGET", "+6588117751")
            m.setenv("SEND_MODE", "telethon")
            m.setenv("DRY_RUN", "true")
            m.setenv("SEND_ENABLED", "true")
            m.setenv("MAX_SENDS_PER_DAY", "3")
            m.setenv("MIN_SECONDS_BETWEEN_SENDS", "300")
            m.setenv("TIMEZONE", "Asia/Singapore")
            m.setenv("ENABLE_SCHEDULER", "false")
            m.setenv("SCHEDULER_HOUR", "18")
            m.setenv("SCHEDULER_MINUTE", "0")

            import importlib, db, config
            db.init_db()
            importlib.reload(config)
            import services.status_service as ss

            # Mock Telethon sender
            class FakeSender:
                def is_authorized(self): return False
                def get_display_name(self): return "Test User"
            with patch("services.status_service.tsender", FakeSender()):
                with patch("services.status_service.audit_repo"):
                    report = ss.get_status(131288677)

            required = [
                "Bot running", "Send mode", "Telethon", "Dry run",
                "Send enabled", "Sends today", "Last send",
                "Active requests", "Pending nudges",
                "Scheduler", "Wife target",
            ]
            for field in required:
                assert field in report, f"Missing field in /status: {field}"