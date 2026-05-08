"""
utils/ids.py — ID and key generation.
"""

import uuid


def new_request_id() -> str:
    """Generate a new unique request ID."""
    return f"req_{uuid.uuid4().hex[:12]}"


def new_event_id() -> str:
    """Generate a new unique event ID."""
    return f"evt_{uuid.uuid4().hex[:12]}"


def new_audit_id() -> str:
    """Generate a new unique audit log ID."""
    return f"aud_{uuid.uuid4().hex[:12]}"


def new_send_id() -> str:
    """Generate a new unique send event ID."""
    return f"snd_{uuid.uuid4().hex[:12]}"
