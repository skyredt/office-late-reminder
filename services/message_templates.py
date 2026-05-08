"""
services/message_templates.py — All outbound message text.

MESSAGE PRESERVATION RULE:
These strings MUST NOT be changed in wording, punctuation, or tone.
They are the exact messages your wife currently receives.

End Work message:
  "Hi bb..\nI end work le… can go off liao. How about you?"

Extend message (custom duration placeholder):
  "Hi bb..\nI need to stay back for {duration}… Are you hungry? Where do you want to go?"
"""

import config


def end_work_message() -> str:
    """The exact message sent when user picks 'End work'."""
    return "Hi bb..\nI end work le… can go off liao. How about you?"


def extend_message(duration: str) -> str:
    """
    The exact message sent when user picks 'Extend' with a duration.
    Duration is injected as-is from validated user input.
    """
    return f"Hi bb..\nI need to stay back for {duration}… Are you hungry? Where do you want to go?"


# ── Internal preview / fallback texts ─────────────────────────────────────────
def dry_run_preview(message: str) -> str:
    return f"[DRY RUN] Would have sent:\n\n{message}"


def no_message_text() -> str:
    return "Okay, no message sent today."