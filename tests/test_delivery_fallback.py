"""
tests/test_delivery_fallback.py — Telethon failure must show exact message for manual send.
"""

import pytest, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestDeliveryFallback:
    def test_telethon_failure_returns_final_text(self):
        with pytest.MonkeyPatch().context() as m:
            m.setenv("DB_PATH", ":memory:")
            m.setenv("DRY_RUN", "false")
            m.setenv("SEND_ENABLED", "true")
            m.setenv("WIFE_TELEGRAM_TARGET", "+6588117751")
            m.setenv("MAX_SENDS_PER_DAY", "10")
            m.setenv("MIN_SECONDS_BETWEEN_SENDS", "1")

            import importlib, db, config, services.delivery_service as ds, services.message_templates as mt
            db.init_db()
            importlib.reload(config)
            importlib.reload(mt)
            importlib.reload(ds)

            # Simulate Telethon failure
            class FakeResult:
                success = False
                message = "Network error"
                error_code = "NETWORK_ERROR"
                final_text = ""

            with patch("telethon_client.telethon_sender.send_message_via_telethon") as mock:
                mock.return_value = FakeResult()
                result = ds.send_end_work()

                assert result.success is False
                assert result.final_text == mt.end_work_message()
                # Fallback message must contain the exact text
                assert mt.end_work_message() in result.final_text

from unittest.mock import patch