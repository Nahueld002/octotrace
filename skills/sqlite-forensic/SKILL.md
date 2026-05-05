---
name: sqlite-forensic
description: >
  SQLite patterns for forensic tooling: referential integrity, raw_json storage, and immutable schema.
  Trigger: When modifying database schemas, ORM models, or data persistence logic.
license: Apache-2.0
metadata:
  author: octotrace
  version: "1.1"
  scope: [root, providers, services, web]
  auto_invoke:
    - "Modifying database schema or SQLite models"
    - "Querying or writing to case.sqlite"
    - "Interacting with data/input/ or seeds"
    - "Adding new tables or columns"
---

## When to Use

- Creating or modifying database tables
- Writing raw SQL schema definitions
- Designing foreign key relationships
- Storing API responses or raw data
- Schema versioning

## Stack

This project uses **sqlite3 (stdlib)** directly. Do NOT use SQLAlchemy, Tortoise,
or any ORM. All queries are raw SQL executed via `sqlite3.Connection`.

---

## Critical Patterns

### Connection Factory (MANDATORY)

All database access must go through a single `get_connection()` factory.
Never open a raw `sqlite3.connect()` outside of `db.py`.

```python
import sqlite3
from pathlib import Path

DB_PATH = Path("data/cases/case.sqlite")

def get_connection(read_only: bool = False) -> sqlite3.Connection:
    """Return a sqlite3 connection with foreign keys enabled.

    Args:
        read_only: If True, opens connection in immutable URI mode.

    Returns:
        sqlite3.Connection with row_factory and FK pragma set.
    """
    if read_only:
        uri = f"file:{DB_PATH}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
    else:
        conn = sqlite3.connect(DB_PATH)

    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
```

---

### Schema Definition

Tables are defined as raw `CREATE TABLE IF NOT EXISTS` statements in `db.py`.

```python
SCHEMA_TRANSACTIONS = """
CREATE TABLE IF NOT EXISTS transactions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    txid            TEXT    NOT NULL UNIQUE,
    chain           TEXT    NOT NULL CHECK(chain IN ('ETH', 'TRON')),
    from_address    TEXT    NOT NULL,
    to_address      TEXT    NOT NULL,
    amount          TEXT    NOT NULL,        -- Decimal stored as string
    datetime_utc    TEXT    NOT NULL,        -- ISO-8601
    token_symbol    TEXT    NOT NULL DEFAULT 'USDT',
    block_number    INTEGER,
    confirmations   INTEGER,
    tag_from        TEXT,
    tag_to          TEXT,
    service_from    TEXT,
    service_to      TEXT,
    url_tx          TEXT,
    raw_json        TEXT    NOT NULL,        -- Full API response, mandatory
    saved_at        TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""

SCHEMA_ADDRESSES = """
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

def init_db() -> None:
    """Initialize the SQLite schema for the active case.

    Creates all tables if they do not exist. Safe to call multiple times.
    """
    with get_connection() as conn:
        conn.executescript(SCHEMA_TRANSACTIONS + SCHEMA_ADDRESSES)
```

---

### Immutable Schema

Existing data columns are never altered or dropped. However, **adding new
columns with `DEFAULT` values** via `ALTER TABLE ADD COLUMN` is acceptable
for schema migrations, since it does not break existing rows.

```python
# ACCEPTABLE — add new column with DEFAULT (preserves existing data)
"ALTER TABLE addresses ADD COLUMN times_seen INTEGER NOT NULL DEFAULT 1"  # ✓

# WRONG — altering or dropping existing columns breaks the audit trail
"ALTER TABLE transactions DROP COLUMN raw_json;"      # ❌
"ALTER TABLE transactions RENAME COLUMN amount TO amt;"  # ❌
```

---

### Referential Integrity (MANDATORY)

All foreign keys use `ON DELETE RESTRICT`. Enable per connection via PRAGMA
(already handled by `get_connection()`).

```sql
-- Example: if addresses were referenced by transactions
FOREIGN KEY (from_address) REFERENCES addresses(address) ON DELETE RESTRICT
```

---

### Save Transaction (auto-saves addresses)

Every transaction write **must** include the complete original API response
as a JSON string in `raw_json`. Additionally, both `from_address` and
`to_address` are auto-saved to the addresses table with `times_seen = 1`
(only for new transactions — controlled by `is_new_tx`).

```python
import json
from decimal import Decimal

def save_transaction(conn: sqlite3.Connection, tx: dict, raw_response: dict,
                     is_new_tx: bool = True) -> None:
    """Persist a normalized transaction with its original API payload.

    Uses INSERT ... ON CONFLICT DO UPDATE for upsert semantics:
    - On conflict: updates confirmations, tags, raw_json
    - saved_at is preserved (never updated)
    - Addresses are auto-saved but times_seen only increments for new txs

    Args:
        conn: Active sqlite3 connection from get_connection().
        tx: Normalized transaction dict with all required fields.
        raw_response: Original dict returned by the provider API.
        is_new_tx: If False, addresses auto-saved but times_seen does NOT
            increment (avoids double-counting on tx re-save).

    Raises:
        sqlite3.IntegrityError: If txid already exists (append-only).
    """
    conn.execute(
        """
        INSERT INTO transactions
            (txid, chain, from_address, to_address, amount,
             datetime_utc, token_symbol, block_number, confirmations,
             tag_from, tag_to, service_from, service_to,
             url_tx, raw_json)
        VALUES
            (:txid, :chain, :from_address, :to_address, :amount,
             :datetime_utc, :token_symbol, :block_number, :confirmations,
             :tag_from, :tag_to, :service_from, :service_to,
             :url_tx, :raw_json)
        ON CONFLICT(txid) DO UPDATE SET
            confirmations = excluded.confirmations,
            block_number  = excluded.block_number,
            tag_from      = COALESCE(excluded.tag_from, transactions.tag_from),
            tag_to        = COALESCE(excluded.tag_to, transactions.tag_to),
            service_from  = COALESCE(excluded.service_from, transactions.service_from),
            service_to    = COALESCE(excluded.service_to, transactions.service_to),
            raw_json      = excluded.raw_json
        """,
        {**tx, "raw_json": json.dumps(raw_response)},
    )

    # Auto-save both addresses
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
            save_address(conn, addr, chain, tag, None, None, _now, _now, url, None,
                         increment_seen=is_new_tx)
```

### Save Address (with times_seen counter)

Uses `INSERT ... ON CONFLICT DO UPDATE`. On first insert `times_seen = 1`.
On subsequent inserts for the same address, `times_seen` increments by 1
(unless `increment_seen=False` is passed — used when re-saving an existing
transaction to avoid double-counting). `first_seen_utc` is preserved via
`COALESCE`.

```python
def save_address(conn: sqlite3.Connection, address: str, chain: str,
                 tag_public: str | None, ...,
                 increment_seen: bool = True) -> None:
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
            times_seen     = addresses.times_seen + (CASE WHEN ? THEN 1 ELSE 0 END)
        """,
        (address, chain, tag_public, ...,
         1 if increment_seen else 0),
    )
```

---

### Safe Amount Storage

Amounts are stored as `TEXT` and reconstructed as `Decimal` on read.
**Never store as REAL or INTEGER.**

```python
from decimal import Decimal

# Write — convert Decimal to string before INSERT
amount_str = str(Decimal("1500.000000"))   # "1500.000000"

# Read — reconstruct from string
row = conn.execute("SELECT amount FROM transactions WHERE txid = ?", (txid,)).fetchone()
amount = Decimal(row["amount"])            # Decimal('1500.000000')
```

---

### Append-Only Writes

Use `INSERT OR IGNORE` for transactions. Never `UPDATE` or `DELETE` on
existing records — the forensic record must remain immutable.

```python
# CORRECT
conn.execute("INSERT OR IGNORE INTO transactions (...) VALUES (...)", data)

# WRONG
conn.execute("UPDATE transactions SET amount = ? WHERE txid = ?", ...)  # ❌
conn.execute("DELETE FROM transactions WHERE txid = ?", ...)             # ❌
```

---

### Read-Only Queries (GET endpoints)

FastAPI GET route handlers must use `read_only=True` to prevent accidental
writes from query-layer code.

```python
def get_saved_transactions() -> list[dict]:
    """Fetch all manually saved transactions for display.

    Returns:
        List of transaction dicts ordered by datetime_utc descending.
    """
    with get_connection(read_only=True) as conn:
        rows = conn.execute(
            "SELECT * FROM transactions ORDER BY datetime_utc DESC"
        ).fetchall()
        return [dict(row) for row in rows]
```

---

### Expand Cache Check

Before calling a provider API, check if the address was already expanded
in the same date range to avoid redundant fetches.

```python
def is_cached(conn: sqlite3.Connection, address: str, chain: str,
               start: str, end: str) -> bool:
    """Check if an address was already expanded for a given date range.

    Args:
        conn: Active read-only connection.
        address: Wallet address to check.
        chain: Blockchain identifier ('ETH' or 'TRON').
        start: ISO-8601 start datetime string.
        end: ISO-8601 end datetime string.

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
```

---

## Commands

```bash
# Enable foreign keys and check integrity
sqlite3 data/cases/case.sqlite "PRAGMA foreign_keys = ON; PRAGMA foreign_key_check;"

# Inspect schema
sqlite3 data/cases/case.sqlite ".schema"

# Count saved transactions
sqlite3 data/cases/case.sqlite "SELECT chain, COUNT(*) FROM transactions GROUP BY chain;"

# Verify no float values in amount column
sqlite3 data/cases/case.sqlite "SELECT txid, amount FROM transactions LIMIT 5;"
```

---

## Resources

- **sqlite3 stdlib**: https://docs.python.org/3/library/sqlite3.html
- **SQLite PRAGMA**: https://www.sqlite.org/pragma.html
- **SQLite datatypes**: https://www.sqlite.org/datatype3.html
