"""SQLite database layer for Octotrace forensic storage.

Provides the core database interface using sqlite3 stdlib only (no ORM).
Implements the append-only forensic storage pattern for transaction records.

Database Schema (per PRD.md):
    - transactions: Immutable record of USDT transfers with full audit trail.
    - addresses: Cached address metadata with tags and service info.

Key Functions:
    - get_connection(): Factory for sqlite3 connections with FK enforcement.
    - init_db(): Initialize or upgrade the database schema.

Forensic Constraints:
    - raw_json is NOT NULL in transactions — original API response preserved.
    - amount stored as TEXT (Decimal string) — never float.
    - All writes use INSERT OR IGNORE — never UPDATE or DELETE.
    - Read-only queries use immutable URI mode.

Example:
    >>> from src.db import get_connection, init_db
    >>> init_db()
    >>> with get_connection(read_only=True) as conn:
    ...     rows = conn.execute("SELECT txid FROM transactions").fetchall()
"""

import json
import sqlite3
from pathlib import Path
from typing import Final

# Absolute path to the case SQLite database
_DB_PATH: Final[Path] = Path("data/cases/case.sqlite")

# Schema: transactions table (append-only, raw_json NOT NULL)
SCHEMA_TRANSACTIONS: Final[str] = """
CREATE TABLE IF NOT EXISTS transactions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    txid            TEXT    NOT NULL UNIQUE,
    chain           TEXT    NOT NULL CHECK(chain IN ('ETH', 'TRON')),
    from_address    TEXT    NOT NULL,
    to_address      TEXT    NOT NULL,
    amount          TEXT    NOT NULL,
    datetime_utc    TEXT    NOT NULL,
    token_symbol    TEXT    NOT NULL DEFAULT 'USDT',
    block_number    INTEGER,
    confirmations   INTEGER,
    tag_from        TEXT,
    tag_to          TEXT,
    service_from    TEXT,
    service_to      TEXT,
    url_tx          TEXT,
    raw_json        TEXT    NOT NULL,
    saved_at        TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""

# Schema: addresses table (cached metadata)
SCHEMA_ADDRESSES: Final[str] = """
CREATE TABLE IF NOT EXISTS addresses (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    address         TEXT    NOT NULL UNIQUE,
    chain           TEXT    NOT NULL CHECK(chain IN ('ETH', 'TRON')),
    tag_public      TEXT,
    service_name    TEXT,
    service_url     TEXT,
    first_seen_utc  TEXT,
    last_seen_utc   TEXT,
    url_address     TEXT,
    raw_json        TEXT,
    times_seen      INTEGER NOT NULL DEFAULT 1,
    saved_at        TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""


def get_connection(read_only: bool = False) -> sqlite3.Connection:
    """Return a sqlite3 connection with foreign keys enabled and row factory.

    All database access MUST go through this factory. Never open a raw
    sqlite3.connect() outside of this module.

    Args:
        read_only: If True, opens connection in immutable URI mode to
            prevent accidental writes. Use for SELECT queries only.

    Returns:
        sqlite3.Connection: Configured connection with Row factory and
            foreign keys pragma enabled.
    """
    if read_only:
        uri = f"file:{_DB_PATH}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
    else:
        conn = sqlite3.connect(_DB_PATH)

    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """Initialize the SQLite schema for the active case.

    Creates both transactions and addresses tables if they do not exist.
    Safe to call multiple times (uses CREATE TABLE IF NOT EXISTS).

    The transactions.raw_json column is NOT NULL, ensuring every saved
    transaction retains its complete original API response as an
    immutable audit trail.

    Raises:
        sqlite3.Error: If database initialization fails.
    """
    # Ensure parent directory exists
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with get_connection() as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(SCHEMA_TRANSACTIONS)
        conn.executescript(SCHEMA_ADDRESSES)
        # Migration: add times_seen to existing addresses tables created
        # before v0.1.1. Safe — adds column with DEFAULT 1 for existing rows.
        try:
            conn.execute(
                "ALTER TABLE addresses ADD COLUMN times_seen "
                "INTEGER NOT NULL DEFAULT 1"
            )
        except sqlite3.OperationalError:
            # Column already exists — migration was already applied
            pass
        conn.commit()


def is_cached(
    conn: sqlite3.Connection,
    address: str,
    chain: str,
    start: str,
    end: str,
) -> bool:
    """Check if an address was already expanded for a given date range.

    Used to implement the expand-cache check before calling provider APIs,
    avoiding redundant fetches for addresses already queried.

    Args:
        conn: Active sqlite3 connection (from get_connection()).
        address: Wallet address to check.
        chain: Blockchain identifier ('ETH' or 'TRON').
        start: ISO-8601 start datetime string (inclusive).
        end: ISO-8601 end datetime string (inclusive).

    Returns:
        True if at least one transaction exists for this address and range.
    """
    row = conn.execute(
        """
        SELECT 1 FROM transactions
        WHERE (from_address = ? OR to_address = ?)
          AND chain = ?
          AND datetime_utc BETWEEN ? AND ?
        LIMIT 1
        """,
        (address, address, chain, start, end),
    ).fetchone()
    return row is not None


def save_transaction(
    conn: sqlite3.Connection,
    tx: dict,
    raw_response: dict,
) -> None:
    """Persist a normalized transaction with its original API payload.

    Uses INSERT OR IGNORE to enforce append-only semantics — if the txid
    already exists, the row is silently skipped.

    Args:
        conn: Active sqlite3 connection from get_connection().
        tx: Normalized transaction dict with all required fields:
            txid, chain, from_address, to_address, amount (as Decimal str),
            datetime_utc, token_symbol, block_number, confirmations,
            tag_from, tag_to, service_from, service_to, url_tx.
        raw_response: Original dict returned by the provider API. Will be
            serialized to JSON string for raw_json field.

    Raises:
        sqlite3.IntegrityError: If unique constraint on txid is violated
            by a concurrent insert (should not occur with OR IGNORE).
    """
    conn.execute(
        """
        INSERT OR IGNORE INTO transactions
            (txid, chain, from_address, to_address, amount,
             datetime_utc, token_symbol, block_number, confirmations,
             tag_from, tag_to, service_from, service_to,
             url_tx, raw_json)
        VALUES
            (:txid, :chain, :from_address, :to_address, :amount,
             :datetime_utc, :token_symbol, :block_number, :confirmations,
             :tag_from, :tag_to, :service_from, :service_to,
             :url_tx, :raw_json)
        """,
        {**tx, "raw_json": json.dumps(raw_response)},
    )

    # Auto-guardar ambas addresses involucradas en la transacción
    _now = tx.get("datetime_utc")
    for addr, tag in [
        (tx.get("from_address"), tx.get("tag_from")),
        (tx.get("to_address"), tx.get("tag_to")),
    ]:
        if addr:
            chain = tx["chain"]
            url = (
                f"https://etherscan.io/address/{addr}"
                if chain == "ETH"
                else f"https://tronscan.org/#/address/{addr}"
            )
            save_address(conn, addr, chain, tag, None, None, _now, _now, url, None)


def save_address(
    conn: sqlite3.Connection,
    address: str,
    chain: str,
    tag_public: str | None,
    service_name: str | None,
    service_url: str | None,
    first_seen_utc: str | None,
    last_seen_utc: str | None,
    url_address: str | None,
    raw_json: dict | None,
) -> None:
    """Persist or update address metadata.

    Uses INSERT with ON CONFLICT DO UPDATE to track address sightings.
    On first insert: sets times_seen = 1.
    On subsequent inserts for the same address: increments times_seen by 1.
    first_seen_utc is preserved on conflict (COALESCE) — the first
    observation timestamp is never overwritten.

    Args:
        conn: Active sqlite3 connection from get_connection().
        address: Wallet address (unique key).
        chain: Blockchain identifier ('ETH' or 'TRON').
        tag_public: Public nametag from provider API.
        service_name: Known service name if detected.
        service_url: Official service URL.
        first_seen_utc: ISO-8601 timestamp of first observation.
        last_seen_utc: ISO-8601 timestamp of most recent observation.
        url_address: Auto-generated evidence URL.
        raw_json: Full original API response dict.
    """
    conn.execute(
        """
        INSERT INTO addresses
            (address, chain, tag_public, service_name, service_url,
             first_seen_utc, last_seen_utc, url_address, raw_json,
             times_seen)
        VALUES
            (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        ON CONFLICT(address) DO UPDATE SET
            tag_public     = excluded.tag_public,
            service_name   = excluded.service_name,
            service_url    = excluded.service_url,
            first_seen_utc = COALESCE(addresses.first_seen_utc, excluded.first_seen_utc),
            last_seen_utc  = excluded.last_seen_utc,
            url_address    = excluded.url_address,
            raw_json       = COALESCE(excluded.raw_json, addresses.raw_json),
            times_seen     = addresses.times_seen + 1
        """,
        (
            address,
            chain,
            tag_public,
            service_name,
            service_url,
            first_seen_utc,
            last_seen_utc,
            url_address,
            json.dumps(raw_json) if raw_json else None,
        ),
    )
