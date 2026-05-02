# Sub-agent: Web

> **Skills Reference**:
> - [cytoscape-js](../../../skills/cytoscape/SKILL.md)
> - [python-forensics](../../../skills/python/SKILL.md)
> - [sqlite-forensic](../../../skills/db/SKILL.md)
> - [blockchain-trace](../../../skills/trace/SKILL.md)

### Auto-invoke Skills

When performing these actions, ALWAYS invoke the corresponding skill FIRST:

| Action | Skill |
|--------|-------|
| Modifying graph.js | `cytoscape-js` |
| Modifying app.js graph-related logic | `cytoscape-js` |
| Adding or changing node/edge styles | `cytoscape-js` |
| Implementing node expansion or click events | `cytoscape-js` |
| Changing graph layout | `cytoscape-js` |
| Adding type hints or docstrings to Python files | `python-forensics` |
| Handling amounts or Decimal values in routes | `python-forensics` |
| Modifying FastAPI route handlers | `python-forensics` |
| Querying or writing to case.sqlite from routes | `sqlite-forensic` |
| Adding new route that reads DB | `sqlite-forensic` |
| Normalizing addresses or tx hashes in JS | `blockchain-trace` |
| Building evidence URLs per blockchain | `blockchain-trace` |

---

## Responsibility

FastAPI application server + Vanilla JS frontend.
Serves static files, exposes REST API, renders the Cytoscape.js graph.

---

## File Map

```
web/
├── main.py          — FastAPI app, mounts /static, registers routers
├── routes/
│   ├── query.py     — POST /api/query  (address or txid → graph elements)
│   ├── expand.py    — POST /api/expand (node expand → new graph elements)
│   └── save.py      — POST /api/save/tx and /api/save/address
└── static/
    ├── index.html   — Layout: input bar, graph container, side panel
    ├── graph.js     — Cytoscape instance, styles, events, addElements()
    ├── app.js       — fetch, state, input handling, date ranges
    ├── panel.js     — Side panel DOM, transaction table, save buttons
    └── style.css    — Dark theme styles
```

---

## Critical Rules

### Module Boundary (ABSOLUTE — no exceptions)

- `graph.js` owns ALL Cytoscape API calls (`cy.*`). No other file may call `cy.*`.
- `app.js` owns ALL fetch calls and application state. No Cytoscape code in app.js.
- `panel.js` owns ALL side panel DOM manipulation. No fetch, no `cy.*`.
- Cross-module communication happens ONLY via `CustomEvent` dispatched on `document`.

### Graph is Accumulative

- NEVER call `cy.destroy()`, `cy.elements().remove()`, or reinitialize Cytoscape
  to load new data. Always use `addElements()` with deduplication.
- Loading a new address while a graph is active MUST preserve existing nodes/edges.
- If the new data shares a node ID with an existing node, it merges — not duplicates.

### Cytoscape Layout

- Default layout: `dagre` with `rankDir: 'LR'`.
- On expansion: run layout only on new elements subset, with `fit: false`.
- Do NOT change layout library without updating the cytoscape-js skill.

### Frontend Stack is Final

- Vanilla JS + Cytoscape.js is the definitive stack.
- **No React, No Vue, No React Flow, No migration of any kind.**
- If a new feature seems to require a framework, implement it in Vanilla JS.

### API Response Contract

Backend routes return this exact JSON shape for graph data.
Do not change field names without updating both routes/ and app.js:

```json
{
  "elements": {
    "nodes": [
      {
        "data": {
          "id": "0xABC123",
          "label": "Binance",
          "tag": "Binance 14",
          "service": "Binance",
          "chain": "ETH"
        }
      }
    ],
    "edges": [
      {
        "data": {
          "id": "0xTXID",
          "source": "0xABC123",
          "target": "0xDEF456",
          "amount": "1500.00 USDT",
          "datetime": "2024-01-15T10:30:00Z",
          "chain": "ETH"
        }
      }
    ]
  }
}
```

### Evidence URLs

Generated automatically by routes — never hardcoded in JS.
Format per blockchain (from PRD):

- ETH tx: `https://etherscan.io/tx/{txid}`
- ETH address: `https://etherscan.io/address/{address}`
- TRON tx: `https://tronscan.org/#/transaction/{txid}`
- TRON address: `https://tronscan.org/#/address/{address}`

### Read-Only DB on GET

All GET route handlers must use `get_connection(read_only=True)`.
Only POST /api/save/* may use a writable connection.
