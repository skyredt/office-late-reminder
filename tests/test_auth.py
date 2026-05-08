"""
tests/test_auth.py — Authorization guards must reject everyone except the owner.
"""

import pytest
from unittest.mock import patch
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

OWNER_ID = 131288677
STRANGER_ID = 999999999


class FakeAudit:
    def log(self, **kwargs): pass


class TestAuth:
    def test_owner_is_authorized(self):
        with patch("services.auth_service.config") as cfg:
            cfg.MY_USER_ID = OWNER_ID
            from services.auth_service import is_authorised
            assert is_authorised(OWNER_ID) is True

    def test_stranger_is_not_authorized(self):
        with patch("services.auth_service.config") as cfg:
            cfg.MY_USER_ID = OWNER_ID
            # reload to pick up patched config
            import importlib, services.auth_service as a
            importlib.reload(a)
            assert a.is_authorised(STRANGER_ID) is False

    def test_require_auth_returns_false_for_stranger(self):
        with patch("services.auth_service.config") as cfg:
            cfg.MY_USER_ID = OWNER_ID
            import importlib, services.auth_service as a
            importlib.reload(a)
            with patch.object(a, "_audit", FakeAudit()):
                result = a.require_auth(STRANGER_ID, request_id="req_test123")
                assert result is False