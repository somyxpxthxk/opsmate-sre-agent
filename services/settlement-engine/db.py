"""
Settlement Engine — Database Layer
===================================
Handles all database operations for merchant settlements.
Uses SQLite with connection pooling for reliability.

WARNING: PR #892 (a3f8b21) modified the get_pending_settlements query.
"""

import sqlite3
import logging
from contextlib import contextmanager

logger = logging.getLogger("settlement-engine.db")

DB_PATH = "infrastructure/data/settlements.db"
MAX_CONNECTIONS = 50

# Connection pool
_pool = []
_active_connections = 0


@contextmanager
def get_connection():
    """Get a connection from the pool."""
    global _active_connections
    if _active_connections >= MAX_CONNECTIONS:
        raise ConnectionError(
            f"ConnectionPoolExhausted: All {MAX_CONNECTIONS} connections are in use. "
            f"Cannot acquire new connection. Active queries may be blocking the pool."
        )
    _active_connections += 1
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()
        _active_connections -= 1


def get_pending_settlements(status="PENDING", merchant_id=None):
    """
    Fetch pending settlements from the database.
    
    BUG (PR #892, commit a3f8b21): Removed the WHERE clause filter.
    This causes a full table scan on the settlements table (2.4M rows),
    exhausting the connection pool and causing cascading timeouts.
    
    Previous (correct) query:
        SELECT * FROM settlements WHERE status = ? AND merchant_id = ?
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        # BUG: Full table scan — no WHERE clause, no index
        cursor.execute("SELECT * FROM settlements")  # <-- THIS IS THE BUG
        return cursor.fetchall()


def update_settlement_status(settlement_id, new_status, reason=""):
    """Update the status of a settlement record."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE settlements SET status = ?, reason = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (new_status, reason, settlement_id)
        )
        conn.commit()
        logger.info(f"Settlement {settlement_id} updated to {new_status}")


def get_settlement_stats():
    """Get aggregate settlement statistics."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT status, COUNT(*), SUM(amount) FROM settlements GROUP BY status"
        )
        return cursor.fetchall()
