"""
tests/test_workflow.py — Workflow state machine transitions.
"""

import pytest, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestWorkflowStates:
    def test_start_prompt_returns_awaiting_choice(self):
        with pytest.MonkeyPatch().context() as m:
            m.setenv("DB_PATH", ":memory:")
            m.setenv("MY_TELEGRAM_USER_ID", "131288677")
            m.setenv("WIFE_TELEGRAM_TARGET", "+6588117751")
            m.setenv("NUDGE_DELAY_MINUTES", "10")
            m.setenv("PROMPT_EXPIRY_MINUTES", "30")

            import importlib, db, config, services.workflow_service as wf
            db.init_db()
            # Force re-read of config
            importlib.reload(config)
            importlib.reload(wf)

            result = wf.start_prompt(131288677)
            assert result.ok is True
            assert result.next_state == "awaiting_choice"

    def test_double_confirm_does_not_send_twice(self):
        """Idempotency: confirming an already-sent request is rejected."""
        with pytest.MonkeyPatch().context() as m:
            m.setenv("DB_PATH", ":memory:")
            m.setenv("MY_TELEGRAM_USER_ID", "131288677")
            m.setenv("WIFE_TELEGRAM_TARGET", "+6588117751")
            m.setenv("DRY_RUN", "true")

            import importlib, db, config, services.workflow_service as wf, services.delivery_service as ds
            db.init_db()
            importlib.reload(config)
            importlib.reload(wf)
            importlib.reload(ds)

            # Start
            r = wf.start_prompt(131288677)
            req_id = r.message.split("\n")[-1]  # not ideal but works for this test
            # This test needs the actual request ID from the repo
            from repositories.prompt_repository import PromptRepository
            repo = PromptRepository()
            active = repo.get_active_for_user(131288677)
            req = active[0]

            # End work path
            r1 = wf.handle_end_work(req.id, 131288677)
            assert r1.ok is True

            # First confirm
            with patch.object(ds, "send_end_work") as mock_send:
                mock_send.return_value = ds.DeliveryResult(success=True, final_text="Hi bb..")
                r2 = wf.handle_confirm(req.id, 131288677)
                assert r2.ok is True

            # Second confirm — must be rejected
            r3 = wf.handle_confirm(req.id, 131288677)
            assert r3.ok is True  # Already sent, returns "already sent" not error
            assert "already sent" in r3.message

from unittest.mock import patch