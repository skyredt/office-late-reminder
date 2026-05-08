"""
utils/masking.py — Privacy helpers. Full values NEVER appear in logs.
"""

import config


def mask_user_id(user_id: int | str) -> str:
    """Mask a Telegram user ID: 131288677 → user_xxx677"""
    s = str(user_id)
    return f"user_{'x' * (len(s) - config.USER_ID_MASK_TRAILING)}{s[-config.USER_ID_MASK_TRAILING:]}"


def mask_phone(phone: str) -> str:
    """Mask a phone number, showing only trailing digits."""
    s = phone.strip().lstrip("+")
    if len(s) <= config.PHONE_MASK_TRAILING:
        masked = "x" * len(s)
    else:
        masked = "x" * (len(s) - config.PHONE_MASK_TRAILING) + s[-config.PHONE_MASK_TRAILING:]
    return f"+{masked}"


def mask_request_id(req_id: str) -> str:
    """Show only the short suffix of a request ID."""
    if "_" in req_id:
        return req_id
    return req_id[-8:]
