-- 001_initial_schema.sql
-- Run once on first deployment; safe to re-run (CREATE TABLE IF NOT EXISTS)
-- Pragma WAL mode must be set BEFORE any other statement in the session.

PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS prompt_requests (
    id                  TEXT PRIMARY KEY,
    owner_user_id       TEXT NOT NULL,
    recipient_key       TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'awaiting_choice',
    choice_type         TEXT,
    custom_text         TEXT,
    preview_text        TEXT,
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL,
    expires_at          TEXT NOT NULL,
    nudge_due_at        TEXT,
    nudged_at           TEXT,
    confirmed_at        TEXT,
    sent_at             TEXT,
    cancelled_at        TEXT,
    failed_at           TEXT,
    error_code          TEXT,
    error_message       TEXT
);

CREATE TABLE IF NOT EXISTS send_events (
    id              TEXT PRIMARY KEY,
    request_id      TEXT NOT NULL,
    delivery_mode   TEXT NOT NULL,
    recipient_key   TEXT NOT NULL,
    message_text    TEXT,
    outcome         TEXT NOT NULL,
    error_code      TEXT,
    error_message   TEXT,
    created_at      TEXT NOT NULL,
    sent_at         TEXT,
    FOREIGN KEY (request_id) REFERENCES prompt_requests(id)
);

CREATE TABLE IF NOT EXISTS runtime_counters (
    counter_date    TEXT PRIMARY KEY,
    send_count      INTEGER NOT NULL DEFAULT 0,
    last_send_at    TEXT
);

CREATE TABLE IF NOT EXISTS audit_log (
    id                      TEXT PRIMARY KEY,
    timestamp               TEXT NOT NULL,
    actor_user_id_masked    TEXT,
    event_type              TEXT NOT NULL,
    request_id              TEXT,
    details_masked          TEXT,
    outcome                 TEXT
);