# Office Late Reminder

A hardened, production-ready Telegram bot that prompts you at end of day and sends a message to your wife via your own Telegram user account (Telethon).

## Architecture

```
User → Telegram Bot API (prompts + buttons)
     → Your Telegram User Account (Telethon) → Wife's phone
```

**Two Telegram identities:**
- Bot (`@GeniusGab`) — receives commands, sends prompts and buttons to you
- Your Telethon user account — sends the actual message to your wife

## Project Structure

```
office_late_reminder/
├── app.py                        # Main entrypoint
├── config.py                     # All environment config
├── db.py                         # SQLite connection + init
├── models.py                     # Domain objects
├── logging_config.py              # Structured logging
├── telethon_login.py             # One-time session setup
├── repositories/
│   ├── prompt_repository.py      # Prompt request CRUD
│   ├── send_repository.py        # Daily send counter
│   ├── audit_repository.py       # Audit log
│   └── runtime_repository.py     # Runtime counters
├── services/
│   ├── auth_service.py           # Centralised auth guard
│   ├── workflow_service.py       # State machine
│   ├── delivery_service.py       # Telethon delivery + whitelist
│   ├── validation_service.py     # Custom duration validation
│   ├── rate_limit_service.py     # Rate limit helpers
│   ├── nudge_service.py          # Nudge scheduling
│   ├── status_service.py         # /status report
│   └── message_templates.py      # **Exact message text — do not change**
├── telegram_handlers/
│   ├── command_handlers.py       # /testprompt, /status, /cancel, /start
│   ├── callback_handlers.py      # All inline button handlers
│   ├── text_handlers.py          # Custom duration text input
│   └── common.py                 # Shared reply helpers
├── telethon_client/
│   └── telethon_sender.py        # Background Telethon send
├── scheduler/
│   └── scheduler_runner.py       # APScheduler + nudge delivery
├── utils/
│   ├── ids.py                    # UUID helpers
│   ├── masking.py                # Privacy helpers
│   ├── time_utils.py             # SGT timezone helpers
│   └── callback_data.py           # Callback payload pack/unpack
├── migrations/
│   └── 001_initial_schema.sql   # SQLite schema reference
└── tests/
    ├── test_auth.py
    ├── test_rate_limits.py
    ├── test_workflow.py
    ├── test_callbacks.py
    ├── test_nudges.py
    ├── test_delivery_fallback.py
    └── test_status.py
```

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure `.env`

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

### 3. Create Telegram API credentials

1. Go to https://my.telegram.org → API development tools
2. Create a new app (Platform: **Android**)
3. Note your `api_id` and `api_hash`

### 4. Create the bot

1. Message `@BotFather` on Telegram
2. Send `/newbot`
3. Follow the steps and note the **bot token** (`123456789:ABC...`)

### 5. Authorise Telethon (one-time)

```bash
python telethon_login.py +6512345678
```
- OTP is sent to your Telegram app (not SMS)
- Re-run with the OTP code:
```bash
python telethon_login.py +6512345678 82825
```

### 6. Run the bot

```bash
python app.py
```

## Commands

| Command | Description |
|---|---|
| `/testprompt` | Send the end-of-day prompt now |
| `/status` | Show bot health, counts, and active requests |
| `/cancel` | Cancel the current prompt |
| `/start` | Restart / show help |

## Message Flow

```
/testprompt
  ├─ "End work"     → Preview → ✅ Send → Wife receives:
  │                    "Hi bb..\nI end work le… can go off liao. How about you?"
  │
  ├─ "Extend"
  │   ├─ "10 / 30 / 1 hour" → Preview → ✅ Send → Wife receives:
  │   │   "Hi bb..\nI need to stay back for {duration}… Are you hungry? Where do you want to go?"
  │   └─ "Custom" → Free text → Validate → Preview → ✅ Send
  │
  └─ "No message today" → Cancelled
```

If no button is pressed within **10 minutes**, a nudge is sent automatically.

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `BOT_TOKEN` | *(required)* | Telegram bot token |
| `MY_TELEGRAM_USER_ID` | *(required)* | Your Telegram user ID |
| `TELEGRAM_API_ID` | *(required)* | From my.telegram.org |
| `TELEGRAM_API_HASH` | *(required)* | From my.telegram.org |
| `WIFE_TELEGRAM_TARGET` | *(required)* | Wife's phone number |
| `TELETHON_SESSION_NAME` | `office_late_reminder` | Session file name |
| `SEND_MODE` | `telethon` | Delivery backend |
| `DRY_RUN` | `true` | Set `false` to enable live sending |
| `SEND_ENABLED` | `true` | Master send toggle |
| `MAX_SENDS_PER_DAY` | `3` | Daily send limit |
| `MIN_SECONDS_BETWEEN_SENDS` | `300` | Gap between sends (seconds) |
| `TIMEZONE` | `Asia/Singapore` | All timestamps in SGT |
| `ENABLE_SCHEDULER` | `false` | Enable 6 PM auto-prompt |
| `SCHEDULER_HOUR` | `18` | 24-hour format |
| `SCHEDULER_MINUTE` | `0` | |
| `NUDGE_DELAY_MINUTES` | `10` | Minutes after prompt before nudge |
| `PROMPT_EXPIRY_MINUTES` | `30` | Prompt expires after this |
| `DB_PATH` | `office_late_reminder.db` | SQLite file |

## Security Properties

- **Owner-only access** — every command, callback, and text input is checked against `MY_TELEGRAM_USER_ID`
- **Recipient whitelist** — `delivery_service` enforces sending only to `WIFE_TELEGRAM_TARGET`; no bypass is possible
- **Message integrity** — only fixed templates are sent; custom text is validated duration only
- **Idempotent workflow** — unique request ID per prompt; double-confirm is safely rejected
- **Privacy** — logs use masked IDs; raw phone numbers and secrets are never logged
- **SQLite WAL** — safe concurrent access from the bot and background scheduler thread

## Test Plan

```bash
# Run all tests
pytest tests/ -v

# Specific test files
pytest tests/test_auth.py               -v  # Unauthorised access rejected
pytest tests/test_rate_limits.py        -v  # Daily/interval limits enforced
pytest tests/test_workflow.py           -v  # State transitions, double-confirm
pytest tests/test_callbacks.py           -v  # Stale prompts rejected
pytest tests/test_nudges.py             -v  # Nudge only for active requests
pytest tests/test_delivery_fallback.py  -v  # Telethon failure shows message
pytest tests/test_status.py             -v  # /status has all required fields
```

## Acceptance Checklist

### Message Preservation
- [ ] End work message unchanged: `"Hi bb..\nI end work le… can go off liao. How about you?"`
- [ ] Extend preset messages unchanged: `"Hi bb..\nI need to stay back for {duration}… Are you hungry? Where do you want to go?"`
- [ ] Custom duration behaviour unchanged
- [ ] Preview behaviour unchanged

### Authorisation
- [ ] Unauthorized `/testprompt` rejected
- [ ] Unauthorized callback rejected
- [ ] Unauthorized text input rejected
- [ ] Only configured owner user ID can interact

### Recipient Safety
- [ ] No code path allows sending to anyone other than `WIFE_TELEGRAM_TARGET`
- [ ] Recipient mismatch is permanently enforced in `delivery_service`

### Workflow Integrity
- [ ] Every prompt has a unique request ID
- [ ] Old/stale prompts rejected
- [ ] Expired prompts cannot be confirmed
- [ ] Double-tapping Confirm does not send twice
- [ ] Cancel works safely

### Persistence
- [ ] Active request survives restart
- [ ] Daily send count survives restart
- [ ] Pending nudge restored from SQLite on startup

### Reliability
- [ ] Telethon auth state visible in `/status`
- [ ] Send failure shows exact final message for manual send
- [ ] Nudge sent only for still-active requests

### Observability
- [ ] `/status` shows all required fields
- [ ] Logs do not contain secrets or full phone numbers
- [ ] Audit log records auth rejections and send outcomes