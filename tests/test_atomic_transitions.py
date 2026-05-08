"""
tests/test_atomic_transitions.py

Tests that handle_confirm() is idempotent:
- First confirm call sends once.
- Second confirm call for the same request does NOT send again.
- Final send count remains 1.
"""

import pytest
from unittest.mock import patch, MagicMock
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import RequestStatus
from repositories.prompt_repository import PromptRepository
import services.workflow_service as wf


class MockSendResult:
    def __init__(self, success=True, final_text="Hello", error_code=None, message=""):
        self.success = success
        self.final_text = final_text
        self.error_code = error_code
        self.message = message


class TestAtomicConfirm:
    """Verify double-confirm does not send twice."""

    @patch("services.delivery_service.send_end_work")
    def test_confirm_once_sends(self, mock_send):
        """First confirm should call delivery exactly once."""
        mock_send.return_value = MockSendResult(success=True)

        # Create a request in awaiting_confirmation state via the normal flow
        result = wf.start_prompt(user_id=131288677)
        req_id = result.message  # not used here

        # Walk to awaiting_confirmation
        req = wf._prompt_repo.get_active_for_user(131288677)[0]
        wf._prompt_repo.set_choice(req.id, choice_type="end_work", preview_text="Hello")

        # Confirm
        r = wf.handle_confirm(req.id, user_id=131288677)

        assert r.ok is True
        assert mock_send.call_count == 1
        # Status should be SENT
        req_after = wf._prompt_repo.get(req.id)
        assert req_after.status == RequestStatus.SENT

    @patch("services.delivery_service.send_end_work")
    def test_confirm_twice_sends_only_once(self, mock_send):
        """
        Confirm called twice on the same request:
        - First call sends (count = 1)
        - Second call returns 'already sent' (count stays 1)
        """
        mock_send.return_value = MockSendResult(success=True)

        result = wf.start_prompt(user_id=131288677)
        req = wf._prompt_repo.get_active_for_user(131288677)[0]
        wf._prompt_repo.set_choice(req.id, choice_type="end_work", preview_text="Hello")

        # First confirm
        r1 = wf.handle_confirm(req.id, user_id=131288677)
        assert r1.ok is True
        assert mock_send.call_count == 1

        # Second confirm — same request ID, same user
        r2 = wf.handle_confirm(req.id, user_id=131288677)
        assert r2.ok is True          # still ok, just already sent
        assert "already sent" in r2.message.lower()
        assert mock_send.call_count == 1  # NOT called a second time

    @patch("services.delivery_service.send_extend")
    def test_confirm_twice_extend_only_once(self, mock_send):
        """Same test but for extend flow."""
        mock_send.return_value = MockSendResult(success=True)

        result = wf.start_prompt(user_id=131288677)
        req = wf._prompt_repo.get_active_for_user(131288677)[0]
        wf._prompt_repo.set_choice(req.id, choice_type="extend_preset", custom_text="30 mins", preview_text="Staying 30 mins")

        r1 = wf.handle_confirm(req.id, user_id=131288677)
        assert r1.ok is True
        assert mock_send.call_count == 1

        r2 = wf.handle_confirm(req.id, user_id=131288677)
        assert r2.ok is True
        assert "already sent" in r2.message.lower()
        assert mock_send.call_count == 1

    def test_transition_status_returns_false_for_wrong_from_state(self):
        """transition_status should return False when the request is not in from_status."""
        result = wf.start_prompt(user_id=131288677)
        req = wf._prompt_repo.get_active_for_user(131288677)[0]

        # Request is in awaiting_choice, not awaiting_confirmation
        ok = wf._prompt_repo.transition_status(
            req.id,
            from_status=RequestStatus.AWAITING_CONFIRMATION,
            to_status=RequestStatus.SENDING,
        )
        assert ok is False

        # Status unchanged
        req_after = wf._prompt_repo.get(req.id)
        assert req_after.status == RequestStatus.AWAITING_CHOICE

    def test_transition_status_returns_true_when_correct_from_state(self):
        """transition_status should return True when request is in the expected from_status."""
        result = wf.start_prompt(user_id=131288677)
        req = wf._prompt_repo.get_active_for_user(131288677)[0]
        wf._prompt_repo.set_choice(req.id, choice_type="end_work", preview_text="Hi")

        # Now request is in awaiting_confirmation
        ok = wf._prompt_repo.transition_status(
            req.id,
            from_status=RequestStatus.AWAITING_CONFIRMATION,
            to_status=RequestStatus.SENDING,
        )
        assert ok is True

        req_after = wf._prompt_repo.get(req.id)
        assert req_after.status == RequestStatus.SENDING
