# PRD — Octotrace Web App v1.0 (MVP)
## Description
An interactive web app for forensic traceability of USDT transactions
on TRON and Ethereum blockchains. Allows tracking fund flows visually,
expanding branches accumulatively, and filtering by date range and
minimum amount.
## Target User
Individual forensic analyst — personal use.
## Problem Statement
A TUI cannot visualize connections between addresses or track branches
accumulatively. The goal is to see where money goes and discard irrelevant
paths without losing visual context.

---

## Main Flow
1. Enter one or more addresses or tx hashes manually (no CSV import)
2. If address: select blockchain + date range + min amount (required)
3. Render interactive graph — accumulates over existing graph
4. Double-click on node → expand branch accumulatively
5. Single click on node → side panel shows all transactions of that address
6. Single click on edge → side panel shows full transaction details
7. Manually save a transaction via dedicated button per row
8. Use 🗑 Clear button to reset the graph when starting a new investigation

---

## Features

### Unified Input

**If ADDRESS:**
- Request date range + blockchain (Ethereum / TRON) + min amount in USDT
- Query provider and render graph — accumulates over any existing graph
- Nodes = addresses, edges = transactions
- If the new data shares a node with the existing graph, they connect
- Evidence URLs are generated automatically per official blockchain format

**If TXID:**
- Render graph with the tx as edge and its from/to nodes
- Returns informative message — direct TXID lookup without known address
  is not supported by Etherscan v2. Use address search instead.

### Interactive Graph

- Single click on node → side panel with all transactions of that address
- Single click on edge → side panel with full transaction data
- Double-click on node → expand graph with that address's movements
- Accumulative expansion: previous graph is never lost
- Search always accumulates — use 🗑 Clear button to reset
- Temporal context: expansions inherit date range from AppState
- Each new manual search from the input uses the current date range inputs
- If address has a public tag → display as node label
- If address belongs to known service (Binance, ByBit, etc.)
  → node rendered as orange diamond with service name as label

### Node Visual States (Forensic Palette)

| State | Fill | Border | Shape |
|---|---|---|---|
| Normal | Grey `#4a4a6a` | `#2a2a4a` | rectangle |
| Saved in DB | Green `#2d8a4e` | `#1e6438` | rectangle |
| Known exchange/service | Orange `#e94560` | `#b8344a` | diamond |
| Expanded (double-clicked) | inherits | Yellow `#f5a623` dashed 4px | inherits |
| Selected (active click) | inherits | White `#ffffff` solid 3px, +30% size | inherits |

States are combinable: a saved+expanded node is green with yellow dashed border.

### Edge Visual States
| State | Color | Width |
|---|---|---|
| Normal | `#0f3460` | 2px |
| Saved in DB | Green `#2d8a4e` | 3px |
| Selected | Yellow `#f5a623` | 3px |

States are combinable: a saved edge is green; if also selected it turns yellow.

### Side Panel

- Opens on single click on node or edge
- **Node view:**
  - Shows: Address, Chain, Tag, Service
  - Evidence URL per blockchain format
  - Table of all transactions for that address within current date range
  - Columns: Type (IN/OUT/SELF badge), Date, Amount, From, To, TXID
  - IN badge (green ▼): address is recipient
  - OUT badge (red ▲): address is sender
  - SELF badge (grey ↔): same address on both sides
  - 💾 Save button per row
- **Edge view:**
  - Shows: Transaction ID, Amount, Date, Chain, From, To
  - Evidence URL per blockchain format
  - 💾 Save button
- Panel is resizable by dragging its left edge
- Alert shown when saving a tx that already exists in DB

### Minimum Amount Filter

- Configurable input (default: 1 USDT)
- Applied on both search and expand
- Eliminates dust transactions (< threshold)
- Does NOT apply to manually saved transactions
- Forensic note: do not set too high — fragmentation patterns
  (e.g. 300 USDT flows) are key evidence in layering schemes

### Persistence

- Manual save via 💾 button: persists tx to `transactions` table
- Auto-saves both from_address and to_address to `addresses` table
  on every tx save
- Upsert semantics: if tx already exists, updates confirmations,
  block_number, tags — preserves original `saved_at` timestamp
- `addresses.times_seen` increments each time an address appears
  in a saved transaction — useful for identifying intermediary wallets
- raw_json mandatory in every saved transaction

### Evidence URLs

**Ethereum (Etherscan):**
- Tx: `https://etherscan.io/tx/{txid}`
- Address: `https://etherscan.io/address/{address}`

**TRON (Tronscan):**
- Tx: `https://tronscan.org/#/transaction/{txid}`
- Address: `https://tronscan.org/#/address/{address}`

---

## Data Model

**Table: transactions**

| Field | Type | Notes |
|-------|------|-------|
| txid | TEXT | Unique, not null |
| chain | TEXT | `'ETH'` or `'TRON'` |
| from_address | TEXT | Not null |
| to_address | TEXT | Not null |
| amount | TEXT | Decimal as string, never float |
| datetime_utc | TEXT | ISO-8601 UTC |
| token_symbol | TEXT | Default `'USDT'` |
| block_number | INTEGER | |
| confirmations | INTEGER | Updated on upsert |
| tag_from | TEXT | COALESCE on upsert — never overwritten with null |
| tag_to | TEXT | COALESCE on upsert — never overwritten with null |
| service_from | TEXT | |
| service_to | TEXT | |
| url_tx | TEXT | Auto-generated per blockchain format |
| raw_json | TEXT | Full original API response — mandatory |
| saved_at | TEXT | Set on first insert, never updated |

**Table: addresses**

| Field | Type | Notes |
|-------|------|-------|
| address | TEXT | Unique, not null |
| chain | TEXT | `'ETH'` or `'TRON'` |
| tag_public | TEXT | Public nametag from API |
| service_name | TEXT | Known service name |
| service_url | TEXT | Official service URL |
| first_seen_utc | TEXT | ISO-8601 — preserved on upsert |
| last_seen_utc | TEXT | Updated on each upsert |
| url_address | TEXT | Auto-generated per blockchain format |
| raw_json | TEXT | |
| saved_at | TEXT | First insert timestamp |
| times_seen | INTEGER | Increments on each upsert — default 1 |

---

## Critical Business Rules

- **No float:** all amounts use `Decimal` stored as `TEXT` in SQLite
- **Upsert semantics:** transactions update on conflict, never duplicate
- **saved_at immutable:** first save timestamp is never overwritten
- **raw_json mandatory:** every transaction retains full original API JSON
- **Read-only on GET:** query endpoints use read-only SQLite connection
- **Identity neutrality:** do not associate wallets with civil identities
- **Evidence URLs:** always generated per official blockchain format
- **No cache:** expand always fetches from API — cache disabled pending
  proper implementation with a dedicated query-tracking table

---

## Module Architecture (JS)

| Module | Owns | Never |
|---|---|---|
| `graph.js` | All `cy.*` calls, styles, layout | fetch, DOM outside graph |
| `app.js` | All fetch calls, AppState | `cy.*` calls |
| `panel.js` | Panel DOM manipulation | fetch, `cy.*` calls |

Inter-module communication: only via `CustomEvent` on `document`.
Never call `cy.destroy()`.

---

## Known API Limitations

- **Etherscan v2:** `tokentx` does not support `txhash` parameter.
  TXID lookup requires a known address. Use address search + expand.
- **Etherscan nametag (`getaddresstag`):** requires paid API plan.
  Tag fields will be null for most addresses on free tier.
- **Tronscan tags:** available via `from_address_tag.from_address_tag`
  field in `token_trc20/transfers` response (nested dict).
- **Tronscan pagination:** API filters by `start_timestamp`/`end_timestamp`
  in milliseconds. Max 50 results per page.
- **Etherscan pagination:** API does not filter by date — client-side
  timestamp filtering applied. Max 100 results per page, up to 10 pages.

---

## Out of Scope (MVP)

- Import from Excel or CSV
- Multi-user support
- Other blockchains (Bitcoin, etc.)
- Authentication
- Automated tests
- Query cache (planned: dedicated tracking table)
- Case panel / saved investigations view (planned next)

---

## Stack

- **Backend:** FastAPI (Python 3.12+)
- **Frontend:** Vanilla JS + Cytoscape.js + elk layout (layered, RIGHT direction)
- **Database:** SQLite per case (`data/cases/case.sqlite`)
- **APIs:** Etherscan API v2 + Tronscan API
- **JS dependencies:** vendorized in `static/vendor/` (no CDN, offline-first)