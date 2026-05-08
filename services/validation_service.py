"""
services/validation_service.py — Input validation for custom durations.

Preserves the exact current behaviour:
- Validates "10 mins", "15 min", "45 minutes", "1 hour", "2 hours", "1h", "30m" etc.
- Max 20 characters (configurable via MAX_CUSTOM_TEXT_CHARS).
- Blocks URLs, @mentions, phone numbers, command-like patterns.
- Returns (ok, cleaned_or_reason).
- Does NOT rewrite or rephrase the user's final message content.
"""

import re
import config


DURATION_RE = re.compile(r"^\s*\d{1,2}\s*(?:mins?|minutes?|hours?|h|m)\s*$", re.IGNORECASE)

BLOCKED_PATTERNS = [
    r"@\w+",       # @mentions
    r"https?://",   # URLs
    r"\+65\d",      # phone numbers
    r"^/.*",        # command-like
    r"t\.me",       # t.me links
]


def validate_duration(text: str) -> tuple[bool, str]:
    """
    Returns (ok, cleaned_or_reason).
    ok=True  → cleaned duration string (stripped, lowercase)
    ok=False → reason string
    """
    d = text.strip()

    if len(d) > config.MAX_CUSTOM_TEXT_CHARS:
        return False, f"Too long (max {config.MAX_CUSTOM_TEXT_CHARS} chars). Try again or /cancel."

    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, d):
            return False, "Invalid characters. Try again or /cancel."

    if not DURATION_RE.match(d):
        return False, "Unclear duration. Try e.g. '10 mins', '1 hour', or /cancel."

    return True, d.lower()