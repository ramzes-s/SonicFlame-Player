"""
System Data Module

Key-value store for system-level metadata (db version, api keys, etc.).
"""

from typing import Optional
from musicplayer.core.db.connection import get_connection


def set_system_value(key: str, value: str):
    """Set a system data key-value pair."""
    with get_connection() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO system_data (key, value) VALUES (?, ?)
        """, (key, value))


def get_system_value(key: str) -> Optional[str]:
    """Get a system data value by key, or None if not set."""
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT value FROM system_data WHERE key = ?", (key,)
        )
        row = cursor.fetchone()
        return row[0] if row else None
