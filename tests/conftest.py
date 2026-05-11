"""
conftest.py — Pytest fixtures for Office Late Reminder.
Ensures a clean in-memory database before each test.
"""

import sys
from pathlib import Path

# Ensure the project root is on the import path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import db


@pytest.fixture(autouse=True)
def clean_memory_db(monkeypatch):
    """Reset _conn and point tests at :memory: before every test."""
    monkeypatch.setenv("USE_MEMORY_DB", "true")
    db.reset_db()
