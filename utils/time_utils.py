"""
utils/time_utils.py — Timezone-aware helpers.
"""

import pytz
from datetime import datetime, timedelta


SGT = pytz.timezone("Asia/Singapore")


def now_sgt() -> datetime:
    """Current time in Singapore."""
    return datetime.now(SGT)


def utc_now() -> datetime:
    """Current UTC time (naive — for SQLite storage)."""
    return datetime.utcnow()


def sgt_from_utc(utc_dt: datetime) -> datetime:
    """Convert a naive UTC datetime to SGT."""
    return utc_dt.replace(tzinfo=pytz.UTC).astimezone(SGT)


def to_sgt_iso(ts: float) -> str:
    """Unix timestamp → SGT ISO string with TZ suffix."""
    return (
        datetime.fromtimestamp(ts, SGT)
        .strftime("%Y-%m-%d %H:%M:%S %Z")
    )


def format_sgt(dt: datetime) -> str:
    """Format a timezone-aware datetime in SGT, or return 'Never' if None."""
    if dt is None:
        return "Never"
    if dt.tzinfo is None:
        dt = pytz.UTC.localize(dt)
    return dt.astimezone(SGT).strftime("%Y-%m-%d %H:%M:%S %Z")


def parse_iso_utc(s: str) -> datetime:
    """Parse an ISO8601 string as naive UTC (as stored by SQLite)."""
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S.%f")


def add_minutes(dt: datetime, minutes: int) -> datetime:
    return dt + timedelta(minutes=minutes)
