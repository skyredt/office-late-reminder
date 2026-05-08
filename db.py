"""
db.py — SQLite persistence for Office Late Reminder.
Uses WAL mode for safe concurrent access from the bot + background scheduler.
"""

import sqlite3
import os
from contextlib import contextmanager
from typing import Generator

import config


_conn = None


def get_db_path() -> str:
    """Return absolute path to the SQLite database file."""
    base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, config.DB_PATH)


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(get_db_path(), check_same_thread=False)
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute("PRAGMA foreign_keys=ON")
        _conn.row_factory = sqlite3.Row   # rows support .keys() and dict access
    return _conn


@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    """Thread-safe read-write transaction context."""
    conn = _get_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def init_db():
    """Run all CREATE TABLE IF NOT EXISTS — idempotent, safe to call multiple times."""
    with get_db() as conn:
        conn.executescript("""
        PRAGMA journal_mode=WAL;
        PRAGMA foreign_keys=ON;

        CREATE TABLE IF NOT EXISTS prompt_requests (
            id                  TEXT PRIMARY KEY,
            owner_user_id       TEXT NOT NULL,
            recipient_key      TEXT NOT NULL,
            status              TEXT NOT NULL DEFAULT 'awaiting_choice',
            choice_type        TEXT,
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
            id                  TEXT PRIMARY KEY,
            timestamp           TEXT NOT NULL,
            actor_user_id_masked TEXT,
            event_type          TEXT NOT NULL,
            request_id          TEXT,
            details_masked      TEXT,
            outcome             TEXT
        );
        """)
    # Seed today's counter row if it doesn't exist
    from datetime import date
    today = date.today().isoformat()
    with get_db() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO runtime_counters (counter_date, send_count) VALUES (?, 0)",
            (today,),
        )
    print(f"[db] Initialised at {get_db_path()}")