"""
services/workflow_service.py — State machine for the end-of-day prompt flow.

Idempotent: every prompt gets a unique request_id; double-taps are rejected.
Expiry: prompts expire after PROMPT_EXPIRY_MINUTES (default 30).
Nudge: scheduled nudge_due_at is set on creation and cancelled on any action.

State transitions:
  None → awaiting_choice (on /testprompt)
  awaiting_choice → awaiting_confirmation (on end_work / extend_preset / extend_custom)
  awaiting_choice → cancelled (on skip / cancel)
  awaiting_custom_text → awaiting_confirmation (on valid custom text)
  awaiting_custom_text → awaiting_choice (on cancel back to main)
  awaiting_confirmation → sent (on confirm)
  awaiting_confirmation → awaiting_choice (on cancel back to main)
  awaiting_confirmation → awaiting_choice (on change)
  any active → expired (on timeout, handled by nudge_service)
"""

import logging
import config
import repositories.prompt_repository as prompt_repo
import repositories.audit_repository as audit_repo
import services.delivery_service as delivery
import services.validation_service as validation
from services.message_templates import end_work_message, extend_message, no_message_text
from utils.time_utils import utc_now
from models import RequestStatus


logger = logging.getLogger(__name__)
_prompt_repo = prompt_repo.PromptRepository()
_audit = audit_repo.AuditRepository()


class WorkflowResult:
    def __init__(
        self,
        ok: bool,
        message: str = "",
        preview_text: str = "",
        buttons: list = None,
        next_state: str = "",
        final_text: str = "",
        error_code: str | None = None,
        expired: bool = False,
        request_id: str = "",
        **kwargs,
    ):
        self.ok = ok
        self.message = message
        self.preview_text = preview_text
        self.buttons = buttons or []
        self.next_state = next_state
        self.final_text = final_text
        self.error_code = error_code
        self.expired = expired
        self.request_id = request_id



# ── Inline keyboard helpers ─────────────────────────────────────────────────

def main_keyboard(req_id: str) -> list:
    from telegram import InlineKeyboardButton
    from utils.callback_data import pack
    return [
        [InlineKeyboardButton("End work", callback_data=pack("end_work", req_id))],
        [InlineKeyboardButton("Extend", callback_data=pack("extend_menu", req_id))],
        [InlineKeyboardButton("No message today", callback_data=pack("skip", req_id))],
    ]


def duration_keyboard(req_id: str) -> list:
    from telegram import InlineKeyboardButton
    from utils.callback_data import pack
    return [
        [InlineKeyboardButton("10 mins",  callback_data=pack("extend_preset", req_id, "10m"))],
        [InlineKeyboardButton("30 mins",  callback_data=pack("extend_preset", req_id, "30m"))],
        [InlineKeyboardButton("1 hour",   callback_data=pack("extend_preset", req_id, "1h"))],
        [InlineKeyboardButton("Custom",   callback_data=pack("extend_custom", req_id))],
        [InlineKeyboardButton("← Back",   callback_data=pack("cancel_back", req_id))],
    ]


def confirm_keyboard(req_id: str, is_extend: bool) -> list:
    from telegram import InlineKeyboardButton
    from utils.callback_data import pack
    suffix = "extend" if is_extend else "end_work"
    return [
        [InlineKeyboardButton("✅ Send now",  callback_data=pack("confirm", req_id))],
        [InlineKeyboardButton("✏️ Change",     callback_data=pack("change", req_id))],
        [InlineKeyboardButton("❌ Cancel",     callback_data=pack("cancel", req_id))],
    ]


# ── Entry point ─────────────────────────────────────────────────────────────

def start_prompt(user_id: int) -> WorkflowResult:
    """Called on /testprompt. Creates a new request and returns the prompt."""
    req = _prompt_repo.create(
        owner_user_id=user_id,
        expires_in_minutes=config.PROMPT_EXPIRY_MINUTES,
        nudge_delay_minutes=config.NUDGE_DELAY_MINUTES,
    )
    _audit.log(event_type="prompt_started", actor_user_id=user_id, request_id=req.id, outcome="OK")
    logger.info("Prompt started req=%s user=%s", req.id[-8:], _mask(user_id))

    return WorkflowResult(
        ok=True,
        message="End work or extend?",
        buttons=main_keyboard(req.id),
        next_state=RequestStatus.AWAITING_CHOICE.value,
        preview_text=req.id,
        request_id=req.id,
    )


def handle_end_work(req_id: str, user_id: int) -> WorkflowResult:
    """User chose 'End work'."""
    req = _prompt_repo.get(req_id)
    if not req:
        return _reject_unknown(req_id, user_id)

    # Idempotency: reject if already sent/cancelled/expired
    if not req.is_active():
        logger.info("Stale action on req=%s status=%s", req_id[-8:], req.status.value)
        _audit.log(event_type="action_stale", actor_user_id=user_id, request_id=req_id,
                   details_masked=f"status={req.status.value}", outcome="REJECTED")
        return WorkflowResult(ok=False, message="This request is no longer active.", expired=True)

    # Auth check
    if str(user_id) != req.owner_user_id:
        return _reject_unauthorized(req_id, user_id)

    preview = end_work_message()
    _prompt_repo.set_choice(req_id, choice_type="end_work", preview_text=preview)

    return WorkflowResult(
        ok=True,
        message=f"Here's the message:\n\n{preview}",
        preview_text=preview,
        buttons=confirm_keyboard(req_id, is_extend=False),
        next_state=RequestStatus.AWAITING_CONFIRMATION.value,
        final_text=preview,
    )


def handle_extend_preset(req_id: str, user_id: int, minutes: str) -> WorkflowResult:
    """User chose 'Extend' then a preset duration (10m/30m/1h)."""
    req = _prompt_repo.get(req_id)
    if not req:
        return _reject_unknown(req_id, user_id)
    if not req.is_active() or str(user_id) != req.owner_user_id:
        return _reject(req_id, user_id, req)

    # Map minutes label to human-readable duration
    duration_map = {"10m": "10 mins", "30m": "30 mins", "1h": "1 hour"}
    duration = duration_map.get(minutes, minutes)

    preview = extend_message(duration)
    _prompt_repo.set_choice(req_id, choice_type="extend_preset", custom_text=duration, preview_text=preview)

    return WorkflowResult(
        ok=True,
        message=f"Stay back {duration}:\n\n{preview}",
        preview_text=preview,
        buttons=confirm_keyboard(req_id, is_extend=True),
        next_state=RequestStatus.AWAITING_CONFIRMATION.value,
        final_text=preview,
    )


def handle_extend_custom(req_id: str, user_id: int) -> WorkflowResult:
    """User chose 'Extend → Custom' — enter custom duration text."""
    req = _prompt_repo.get(req_id)
    if not req:
        return _reject_unknown(req_id, user_id)
    if not req.is_active() or str(user_id) != req.owner_user_id:
        return _reject(req_id, user_id, req)

    _prompt_repo.update_status(req_id, RequestStatus.AWAITING_CUSTOM_TEXT)

    return WorkflowResult(
        ok=True,
        message="Enter how long you need to stay back (e.g. '20 mins', '1 hour', '45 minutes'):",
        next_state=RequestStatus.AWAITING_CUSTOM_TEXT.value,
    )


def handle_custom_text(req_id: str, user_id: int, text: str) -> WorkflowResult:
    """User entered custom duration text."""
    req = _prompt_repo.get(req_id)
    if not req:
        return _reject_unknown(req_id, user_id)
    if not req.is_active() or str(user_id) != req.owner_user_id:
        return _reject(req_id, user_id, req)

    if req.status != RequestStatus.AWAITING_CUSTOM_TEXT:
        logger.info("Custom text in wrong state req=%s state=%s", req_id[-8:], req.status.value)
        return WorkflowResult(ok=False, message="Unexpected input. Try /testprompt to start fresh.")

    valid, result = validation.validate_duration(text)
    if not valid:
        return WorkflowResult(
            ok=False,
            message=f"{result}\n\nEnter a short duration or /cancel.",
            next_state=RequestStatus.AWAITING_CUSTOM_TEXT.value,
        )

    preview = extend_message(result)
    _prompt_repo.set_choice(req_id, choice_type="extend_custom", custom_text=result, preview_text=preview)

    return WorkflowResult(
        ok=True,
        message=f"Stay back {result}:\n\n{preview}",
        preview_text=preview,
        buttons=confirm_keyboard(req_id, is_extend=True),
        next_state=RequestStatus.AWAITING_CONFIRMATION.value,
        final_text=preview,
    )


def handle_confirm(req_id: str, user_id: int) -> WorkflowResult:
    """User confirmed — atomically transition to SENDING then send the message."""
    req = _prompt_repo.get(req_id)
    if not req:
        return _reject_unknown(req_id, user_id)
    if str(user_id) != req.owner_user_id:
        return _reject(req_id, user_id, req)

    # ── Atomic state transition: awaiting_confirmation → sending ───────────────
    # If another confirm call wins the race, this returns False and we skip send.
    transitioned = _prompt_repo.transition_status(
        req_id,
        from_status=RequestStatus.AWAITING_CONFIRMATION,
        to_status=RequestStatus.SENDING,
    )
    if not transitioned:
        # Could be: already sent, already failed, already cancelled, or expired
        req_fresh = _prompt_repo.get(req_id)
        if req_fresh and req_fresh.status == RequestStatus.SENT:
            return WorkflowResult(
                ok=True,
                message="Message already sent.",
                final_text=req_fresh.preview_text,
            )
        return WorkflowResult(
            ok=False,
            message="This request is no longer awaiting confirmation. "
                    "It may have already been sent, cancelled, expired, or handled.",
            error_code="STALE_REQUEST",
        )

    # ── Send via Telethon ───────────────────────────────────────────────────
    try:
        if req.choice_type == "end_work":
            result = delivery.send_end_work()
        elif req.choice_type in ("extend_preset", "extend_custom"):
            result = delivery.send_extend(req.custom_text or "")
        else:
            result = None
    except Exception as e:
        logger.error("Delivery exception req=%s: %s", req_id[-8:], e)
        _prompt_repo.transition_status(req_id, RequestStatus.SENDING, RequestStatus.FAILED)
        _prompt_repo.mark_failed(req_id, "DELIVERY_ERROR", str(e))
        return WorkflowResult(
            ok=False,
            message=f"⚠️ Send failed: {e}\n\n"
                    f"Here's the exact message — copy and send it yourself:\n\n"
                    f"{req.preview_text}",
            final_text=req.preview_text,
            error_code="DELIVERY_ERROR",
        )

    # ── Record outcome ──────────────────────────────────────────────────────
    if result and result.success:
        _prompt_repo.transition_status(req_id, RequestStatus.SENDING, RequestStatus.SENT)
        _audit.log(
            event_type="message_sent", actor_user_id=user_id,
            request_id=req_id, outcome="OK",
        )
        return WorkflowResult(
            ok=True,
            message="Message sent to your wife.",
            final_text=result.final_text,
        )
    else:
        _prompt_repo.transition_status(req_id, RequestStatus.SENDING, RequestStatus.FAILED)
        err_code = result.error_code if result else "UNKNOWN"
        err_msg  = result.message  if result else "Unexpected state"
        _prompt_repo.mark_failed(req_id, err_code, err_msg)
        _audit.log(
            event_type="message_failed", actor_user_id=user_id,
            request_id=req_id, outcome="FAILED",
            details_masked=f"code={err_code}",
        )
        return WorkflowResult(
            ok=False,
            message=(
                f"⚠️ Could not send automatically.\n\n"
                f"Here's the exact message — copy and send it yourself:\n\n"
                f"{result.final_text if result else req.preview_text}"
            ),
            final_text=result.final_text if result else req.preview_text,
            error_code=err_code,
        )


def handle_skip(req_id: str, user_id: int) -> WorkflowResult:
    """User chose 'No message today'."""
    req = _prompt_repo.get(req_id)
    if not req:
        return _reject_unknown(req_id, user_id)
    if str(user_id) != req.owner_user_id:
        return _reject(req_id, user_id, req)

    _prompt_repo.mark_cancelled(req_id)
    _audit.log(event_type="prompt_skipped", actor_user_id=user_id, request_id=req_id, outcome="OK")

    return WorkflowResult(
        ok=True,
        message=no_message_text(),
        next_state=RequestStatus.CANCELLED.value,
    )


def handle_cancel(req_id: str, user_id: int) -> WorkflowResult:
    """User cancelled from confirmation screen."""
    req = _prompt_repo.get(req_id)
    if not req:
        return _reject_unknown(req_id, user_id)
    if str(user_id) != req.owner_user_id:
        return _reject(req_id, user_id, req)

    # Reset to awaiting_choice to let user choose again
    _prompt_repo.update_status(req_id, RequestStatus.AWAITING_CHOICE)
    _prompt_repo.cancel_nudge(req_id)
    _audit.log(event_type="prompt_cancelled", actor_user_id=user_id, request_id=req_id, outcome="OK")

    return WorkflowResult(
        ok=True,
        message="Cancelled. What would you like to do?",
        buttons=main_keyboard(req_id),
        next_state=RequestStatus.AWAITING_CHOICE.value,
    )


def handle_cancel_back(req_id: str, user_id: int) -> WorkflowResult:
    """User pressed '← Back' from duration screen — return to main menu."""
    req = _prompt_repo.get(req_id)
    if not req:
        return _reject_unknown(req_id, user_id)
    if str(user_id) != req.owner_user_id:
        return _reject(req_id, user_id, req)

    _prompt_repo.update_status(req_id, RequestStatus.AWAITING_CHOICE)

    return WorkflowResult(
        ok=True,
        message="End work or extend?",
        buttons=main_keyboard(req_id),
        next_state=RequestStatus.AWAITING_CHOICE.value,
    )


def handle_change(req_id: str, user_id: int) -> WorkflowResult:
    """User pressed 'Change' from confirmation — return to main menu."""
    req = _prompt_repo.get(req_id)
    if not req:
        return _reject_unknown(req_id, user_id)
    if str(user_id) != req.owner_user_id:
        return _reject(req_id, user_id, req)

    _prompt_repo.update_status(req_id, RequestStatus.AWAITING_CHOICE)

    return WorkflowResult(
        ok=True,
        message="What would you like to do?",
        buttons=main_keyboard(req_id),
        next_state=RequestStatus.AWAITING_CHOICE.value,
    )


# ── Helpers ─────────────────────────────────────────────────────────────────

def _reject(req_id: str, user_id: int, req) -> WorkflowResult:
    """Reject an action on a stale or unauthorized request."""
    if req and not req.is_active():
        return WorkflowResult(ok=False, message="This request has expired. Try /testprompt to start fresh.", expired=True)
    return WorkflowResult(ok=False, message="Unauthorized.", error_code="UNAUTHORISED")


def _reject_unknown(req_id: str, user_id: int) -> WorkflowResult:
    logger.warning("Unknown request %s from user %s", req_id[-8:], _mask(user_id))
    _audit.log(event_type="unknown_request", actor_user_id=user_id, request_id=req_id, outcome="REJECTED")
    return WorkflowResult(ok=False, message="Unknown request. Try /testprompt to start fresh.", error_code="UNKNOWN_REQUEST")


def _mask(uid: int) -> str:
    s = str(uid)
    return f"user_{'x' * (len(s) - 3)}{s[-3:]}"

def handle_extend_menu(req_id: str, user_id: int) -> WorkflowResult:
    """Show the duration-selection sub-menu."""
    req = _prompt_repo.get(req_id)
    if not req:
        return _reject_unknown(req_id, user_id)
    if not req.is_active() or str(user_id) != req.owner_user_id:
        return _reject(req_id, user_id, req)

    return WorkflowResult(
        ok=True,
        message="How long do you need to stay back?",
        buttons=duration_keyboard(req_id),
        next_state=req.status.value,
    )
