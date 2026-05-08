"""
services/delivery_service.py — Telethon delivery with whitelist enforcement.

CRITICAL: This service MUST refuse to send to any recipient other than
config.WIFE_TARGET. This is the last line of defense.
"""

import logging
import config
import repositories.audit_repository as audit_repo
from repositories.send_repository import SendRepository
from services.message_templates import end_work_message, extend_message
import telethon_client.telethon_sender as tsender


logger = logging.getLogger(__name__)
_audit = audit_repo.AuditRepository()
_send_repo = SendRepository()


class DeliveryResult:
    """Standardised delivery outcome."""
    def __init__(
        self,
        success: bool,
        message: str = "",
        final_text: str = "",
        error_code: str | None = None,
        delivery_mode: str = "telethon",
    ):
        self.success = success
        self.message = message          # human-readable status
        self.final_text = final_text   # the exact text that was/would-be sent
        self.error_code = error_code   # machine-readable code
        self.delivery_mode = delivery_mode


def send_end_work() -> DeliveryResult:
    """Send end-of-work message. Returns DeliveryResult."""
    final_text = end_work_message()
    return _deliver(final_text)


def send_extend(duration: str) -> DeliveryResult:
    """Send extend message with given duration. Returns DeliveryResult."""
    final_text = extend_message(duration)
    return _deliver(final_text)


def _deliver(message_text: str) -> DeliveryResult:
    """
    Core delivery path. Always enforces WIFE_TARGET whitelist.
    Records send events and counters on success.
    """
    # ── Whitelist enforcement ──────────────────────────────────────────────
    target = config.WIFE_TARGET
    if target != config.WIFE_TARGET:
        # This branch can NEVER be reached (same-value comparison),
        # but kept as a permanent failsafe
        logger.error("RECIPIENT_MISMATCH: rejecting send to %s", target)
        _audit.log(event_type="send_rejected", details_masked="recipient mismatch", outcome="REJECTED")
        return DeliveryResult(
            success=False,
            message="Recipient not allowed.",
            final_text=message_text,
            error_code="RECIPIENT_MISMATCH",
        )

    # ── Rate-limit check (before any network call) ──────────────────────────
    ok, reason = _send_repo.can_send()
    if not ok:
        logger.info("Send blocked by rate limit: %s", reason)
        _audit.log(event_type="send_blocked", details_masked=f"rate_limit: {reason}", outcome="BLOCKED")
        return DeliveryResult(
            success=False,
            message=reason,
            final_text=message_text,
            error_code="RATE_LIMIT",
        )

    # ── Dry run ─────────────────────────────────────────────────────────────
    if config.DRY_RUN:
        logger.info("[DRY RUN] Would send to %s: %s", _mask(target), message_text[:40])
        _audit.log(event_type="send_dry_run", details_masked=f"to {_mask(target)}", outcome="DRY_RUN")
        return DeliveryResult(
            success=True,
            message="[DRY RUN] Sent.",
            final_text=message_text,
        )

    # ── Actual delivery via Telethon ─────────────────────────────────────────
    result = tsender.send_message_via_telethon(target, message_text)

    if result.success:
        _send_repo.record_send()
        _audit.log(event_type="send_success", details_masked=f"to {_mask(target)}", outcome="OK")
        logger.info("Sent via Telethon to %s", _mask(target))
        return DeliveryResult(
            success=True,
            message="Sent.",
            final_text=message_text,
            delivery_mode="telethon",
        )
    else:
        _audit.log(
            event_type="send_failed",
            request_id=None,
            details_masked=f"code={result.error_code}",
            outcome=f"FAILED:{result.error_code}",
        )
        logger.error("Telethon delivery failed: %s — %s", result.error_code, result.message)
        return DeliveryResult(
            success=False,
            message=result.message,
            final_text=message_text,
            error_code=result.error_code,
            delivery_mode="telethon",
        )


def _mask(s: str) -> str:
    """Mask a phone number for logging."""
    s = s.strip().lstrip("+")
    return f"+{'x' * (len(s) - 4)}{s[-4:]}"