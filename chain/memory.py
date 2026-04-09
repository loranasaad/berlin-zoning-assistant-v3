"""
chain/memory.py — SQLite persistence: SqliteSaver checkpointer + address cache.

Two layers in one file (memory.db):
  1. SqliteSaver checkpointer tables — managed by LangGraph, keyed by thread_id.
  2. address_cache table — managed here, keyed by canonical Nominatim display_name.

Pattern: chatbot-external-memory.ipynb (LangChain Academy)
"""

import json
import logging
import sqlite3

from langgraph.checkpoint.sqlite import SqliteSaver
from config import SQLITE_MEMORY_PATH

logger = logging.getLogger(__name__)

_CREATE_ADDRESS_CACHE = """
CREATE TABLE IF NOT EXISTS address_cache (
    canonical_address TEXT PRIMARY KEY,
    prefix35          TEXT NOT NULL,
    zoning_report     TEXT NOT NULL,
    created_at        DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""


# ---------------------------------------------------------------------------
# Checkpointer (used by graph.compile)
# ---------------------------------------------------------------------------

def get_checkpointer() -> SqliteSaver:
    """
    Open the SQLite connection, ensure the address_cache table exists,
    and return a SqliteSaver wrapping the same connection.
    check_same_thread=False is required for Streamlit's multi-threaded env.
    """
    conn = sqlite3.connect(SQLITE_MEMORY_PATH, check_same_thread=False)
    conn.execute(_CREATE_ADDRESS_CACHE)
    conn.commit()
    return SqliteSaver(conn)


# ---------------------------------------------------------------------------
# Address cache helpers
# ---------------------------------------------------------------------------

def _normalise(address: str) -> str:
    return address.strip().lower()


def cache_lookup(address: str) -> dict | None:
    """
    Lookup strategy:
      1. Exact normalised match.
      2. 35-char prefix fuzzy match — single result accepted.
      3. Multiple prefix matches → ambiguous, treat as miss.
    Returns the cached zoning_report dict or None.
    """
    norm   = _normalise(address)
    prefix = norm[:35]

    conn = sqlite3.connect(SQLITE_MEMORY_PATH, check_same_thread=False)
    try:
        # 1. Exact match
        row = conn.execute(
            "SELECT zoning_report FROM address_cache WHERE canonical_address = ?",
            (norm,),
        ).fetchone()
        if row:
            logger.info(f"Address cache exact hit: {norm[:60]}")
            return json.loads(row[0])

        # 2. Prefix match
        rows = conn.execute(
            "SELECT canonical_address, zoning_report FROM address_cache WHERE prefix35 = ?",
            (prefix,),
        ).fetchall()
        if len(rows) == 1:
            logger.info(f"Address cache prefix hit: {prefix}")
            return json.loads(rows[0][1])
        if len(rows) > 1:
            logger.info(f"Address cache ambiguous prefix ({len(rows)} matches): {prefix}")
            return None

        return None
    finally:
        conn.close()


def cache_save(canonical_address: str, zoning_report: dict) -> None:
    """Persist a completed zoning report. Uses INSERT OR REPLACE on the canonical key."""
    norm   = _normalise(canonical_address)
    prefix = norm[:35]

    conn = sqlite3.connect(SQLITE_MEMORY_PATH, check_same_thread=False)
    try:
        conn.execute(
            """INSERT OR REPLACE INTO address_cache
               (canonical_address, prefix35, zoning_report)
               VALUES (?, ?, ?)""",
            (norm, prefix, json.dumps(zoning_report, ensure_ascii=False)),
        )
        conn.commit()
        logger.info(f"Address cache saved: {norm[:60]}")
    finally:
        conn.close()
