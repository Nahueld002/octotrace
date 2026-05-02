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

Schema changes require new versioned tables. **Never use ALTER TABLE** on
existing data tables — it breaks the forensic audit trail.

```python
# WRONG
"ALTER TABLE transactions ADD COLUMN new_field TEXT;"  # ❌

# CORRECT — create a new versioned table
SCHEMA_TRANSACTIONS_V2 = """
CREATE TABLE IF NOT EXISTS transactions_v2 (
    -- full new definition here
);
"""
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

### Raw JSON Storage (MANDATORY)

Every transaction write **must** include the complete original API response
as a JSON string in `raw_json`. This is the forensic audit trail.

```python
import json
from decimal import Decimal

def save_transaction(conn: sqlite3.Connection, tx: dict, raw_response: dict) -> None:
    """Persist a normalized transaction with its original API payload.

    Args:
        conn: Active sqlite3 connection from get_connection().
        tx: Normalized transaction dict with all required fields.
        raw_response: Original dict returned by the provider API.

    Raises:
        sqlite3.IntegrityError: If txid already exists (append-only).
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
