"""
utils/callback_data.py — Pack/unpack callback query payloads.

Format: v1|<action>|<request_id>|<extra>

Examples:
  v1|end_work|req_abc123|-
  v1|extend_preset|req_abc123|30m
  v1|extend_custom|req_abc123|-
  v1|confirm|req_abc123|-
  v1|cancel|req_abc123|-
  v1|skip|req_abc123|-

Actions: end_work, extend_preset, extend_custom, confirm, cancel, skip
"""

from dataclasses import dataclass
from typing import Optional


PAYLOAD_SEPARATOR = "|"
PAYLOAD_VERSION = "v1"


@dataclass
class CallbackPayload:
    version: str
    action: str
    request_id: str
    extra: str  # preset minutes, or "-" if not applicable

    def to_string(self) -> str:
        return PAYLOAD_SEPARATOR.join([self.version, self.action, self.request_id, self.extra])

    @classmethod
    def from_string(cls, raw: str) -> Optional["CallbackPayload"]:
        parts = raw.split(PAYLOAD_SEPARATOR)
        if len(parts) != 4 or parts[0] != PAYLOAD_VERSION:
            return None
        return cls(version=parts[0], action=parts[1], request_id=parts[2], extra=parts[3])

    @classmethod
    def new(
        cls,
        action: str,
        request_id: str,
        extra: str = "-",
    ) -> "CallbackPayload":
        return cls(version=PAYLOAD_VERSION, action=action, request_id=request_id, extra=extra)


def pack(action: str, request_id: str, extra: str = "-") -> str:
    return CallbackPayload.new(action, request_id, extra).to_string()


def unpack(raw: str) -> Optional[CallbackPayload]:
    return CallbackPayload.from_string(raw)
