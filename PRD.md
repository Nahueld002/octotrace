# PRD — Octotrace Web App v1.0 (MVP)

## Description

An interactive web app for forensic traceability of crypto transactions.
Allows tracking fund flows visually, expanding branches accumulatively,
and filtering by date range.

## Target User

Individual forensic analyst — personal use.

## Problem Statement

A TUI cannot visualize connections between addresses or track branches
accumulatively. The goal is to see where money goes and discard irrelevant
paths without losing visual context.

---

## Main Flow

```
1. Enter an address or tx hash manually as the only seed (no CSV import)
2. If address: select blockchain + date range (required)
3. Render interactive graph
4. Double-click on node → expand branch
5. Side panel shows transactions of the selected node in table format
6. Adjust date range in side panel (editable) → updates graph view
7. Manually save a transaction or address via dedicated button
```

---

## Features

### Unified Input

**If ADDRESS:**
- Request date range + blockchain (Ethereum / TRON)
- Query provider and render graph
- Nodes = addresses, edges = transactions
- Data visible on graph: amount, date, time
- Evidence URLs are generated automatically per official blockchain format

**If TXID:**
- Render graph with the tx as edge and its from/to nodes
- The resulting graph is the starting point for manual expansions

### Interactive Graph

- Hover over edge (TXID) → tooltip with full tx data
- Hover over node (address) → tooltip with full address info
- Single click on node or edge → side panel with detailed data
- Double-click on node → expand graph with that address's movements
- Accumulative expansion: previous graph is never lost
- Temporal context: expansions via double-click automatically inherit
  the date range of the search that originated the node
- Each new manual search from the main input requests its own date range
- If address has a public tag available → display label on the node
- If address belongs to a known service (ByBit, Bitso, Binance, etc.)
  → display service name on the node with a differentiating icon

### Collapsible Side Panel

- Updates on single click on a selected node or edge
- Shows all transactions of that node in table format
- Columns: TXID, amount, date, time, from address, to address,
  public tag, service, tx URL, address URL
- Editable date range at the top of the panel
  (default: inherits from the original seed search)
- Applying date range changes → re-queries and updates the graph view
  for that node
- **"Save transaction" button** per table row:
  - Saves the tx with all its fields to the transactions table
  - Automatically saves both addresses (from/to) to the addresses table
  - Automatically generates functional evidence URLs for the tx and each address

### Evidence URLs

Format per blockchain:

**Ethereum (Etherscan):**
- Tx: `https://etherscan.io/tx/{txid}`
- Address: `https://etherscan.io/address/{address}`

**TRON (Tronscan):**
- Tx: `https://tronscan.org/#/transaction/{txid}`
- Address: `https://tronscan.org/#/address/{address}`

URLs are generated automatically on save and stored in the database
alongside the record. They are clickable from the interface.

### Node Tags and Services

- Etherscan: query `getaddresstag` to obtain public nametag
- Tronscan: extract `contractInfo[address].tag1` from response
- If tag detected → display as secondary label on the graph node
- If known service detected (Binance, ByBit, Bitso, Kraken, etc.)
  → display service name with differentiating icon on the node

### Persistence

- All queried txs are saved to SQLite (append-only)
- Cache: if address was already expanded in the same date range, no re-fetch
- Manual save via button: persists tx + from/to addresses with all fields
  including URLs and tags

---

## Data Model

**Table: transactions**

| Field | Type | Notes |
|-------|------|-------|
| txid | TEXT | Unique, not null |
| chain | TEXT | `'ETH'` or `'TRON'` |
| from_address | TEXT | Not null |
| to_address | TEXT | Not null |
| amount | TEXT | Stored as string, parsed to Decimal in code |
| datetime_utc | TEXT | ISO-8601 |
| token_symbol | TEXT | Default `'USDT'` |
| block_number | INTEGER | |
| confirmations | INTEGER | |
| tag_from | TEXT | Public tag of from_address |
| tag_to | TEXT | Public tag of to_address |
| service_from | TEXT | Known service name of from_address |
| service_to | TEXT | Known service name of to_address |
| url_tx | TEXT | Auto-generated evidence URL |
| raw_json | TEXT | Full original API response — mandatory |

**Table: addresses**

| Field | Type | Notes |
|-------|------|-------|
| address | TEXT | Unique, not null |
| chain | TEXT | `'ETH'` or `'TRON'` |
| tag_public | TEXT | Public nametag from API |
| service_name | TEXT | Known service name |
| service_url | TEXT | Official service URL |
| first_seen_utc | TEXT | ISO-8601 |
| last_seen_utc | TEXT | ISO-8601 |
| url_address | TEXT | Auto-generated evidence URL |
| raw_json | TEXT | Full original API response |

---

## Critical Business Rules

- **No float:** all amounts use `Decimal` stored as `TEXT` in SQLite
- **Append-only:** saved transactions must never be modified or deleted
- **raw_json:** every transaction retains the original API JSON response
- **Read-only on GET:** query endpoints use a read-only SQLite connection
- **Identity neutrality:** do not associate wallets with civil identities
- **Evidence URLs:** always generated per official blockchain format

---

## Out of Scope (MVP)

- Import from Excel or CSV
- Multi-user support
- Other blockchains (Bitcoin, etc.)
- Authentication
- Automated tests

---

## Stack

- **Backend:** FastAPI (Python 3.12+)
- **Frontend:** Vanilla JS + Cytoscape.js + dagre layout
- **Database:** SQLite per case (`data/cases/case.sqlite`)
- **APIs:** Etherscan API v2 + Tronscan API
- **JS dependencies:** vendorized in `static/vendor/` (no CDN)
