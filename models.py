"""
models.py — Domain objects and status constants for Office Late Reminder.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class RequestStatus(str, Enum):
    AWAITING_CHOICE       = "awaiting_choice"
    AWAITING_CUSTOM_TEXT  = "awaiting_custom_text"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    SENT                  = "sent"
    CANCELLED             = "cancelled"
    EXPIRED               = "expired"
    FAILED                = "failed"


@dataclass
class PromptRequest:
    """
    Represents one end-of-day workflow from prompt to delivery or expiry.
    """
    id: str                          # UUID request ID
    owner_user_id: str              # Telegram user ID of the owner
    recipient_key: str               # Target (always WIFE_TARGET)
    status: RequestStatus
    choice_type: Optional[str] = None      # "end_work" | "extend_preset" | "extend_custom" | "skip"
    custom_text: Optional[str] = None     # Validated custom duration string
    preview_text: Optional[str] = None    # The exact message that will be sent
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: datetime = field(default_factory=datetime.utcnow)
    nudge_due_at: Optional[datetime] = None
    nudged_at: Optional[datetime] = None
    confirmed_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None

    def is_active(self) -> bool:
        return self.status in (
            RequestStatus.AWAITING_CHOICE,
            RequestStatus.AWAITING_CUSTOM_TEXT,
            RequestStatus.AWAITING_CONFIRMATION,
        )

    def is_stale(self, now: datetime) -> bool:
        return now > self.expires_at

    def to_dict(self):
        return {
            "id": self.id,
            "status": self.status.value,
            "choice_type": self.choice_type,
            "preview_text": self.preview_text,
            "created_at": self.created_at.isoformat(),
            "nudge_due_at": self.nudge_due_at.isoformat() if self.nudge_due_at else None,
        }


@dataclass
class SendEvent:
    id: str
    request_id: str
    delivery_mode: str         # "telethon" | "bot_fallback"
    recipient_key: str
    message_text: Optional[str] # May be None in failures
    outcome: str               # "success" | "failed" | "blocked"
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    sent_at: Optional[datetime] = None