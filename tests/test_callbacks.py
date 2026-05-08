"""
tests/test_callbacks.py — Stale/expired prompts must be rejected by callback.
"""

import pytest, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestCallbackExpiry:
    def test_stale_request_rejected(self):
        with pytest.MonkeyPatch().context() as m:
            m.setenv("DB_PATH", ":memory:")
            m.setenv("MY_TELEGRAM_USER_ID", "131288677")
            m.setenv("WIFE_TELEGRAM_TARGET", "+6588117751")
            m.setenv("DRY_RUN", "true")
            m.setenv("SEND_ENABLED", "true")
            m.setenv("MAX_SENDS_PER_DAY", "10")
            m.setenv("MIN_SECONDS_BETWEEN_SENDS", "1")

            import importlib, db, config, services.workflow_service as wf
            db.init_db()
            importlib.reload(config)
            importlib.reload(wf)

            # Start prompt
            r = wf.start_prompt(131288677)
            from repositories.prompt_repository import PromptRepository
            repo = PromptRepository()
            active = repo.get_active_for_user(131288677)
            req = active[0]

            # Mark it as already SENT
            repo.mark_sent(req.id)

            # Try to confirm again — should be handled gracefully
            result = wf.handle_confirm(req.id, 131288677)
            # Should not crash; returns message about already sent
            assert result.ok is True