# Sub-agent: Services

> **Skills Reference**:
> - [sqlite-forensic](../../../skills/db/SKILL.md)
> - [python-forensics](../../../skills/python/SKILL.md)
> - [blockchain-trace](../../../skills/trace/SKILL.md)

### Auto-invoke Skills

When performing these actions, ALWAYS invoke the corresponding skill FIRST:

| Action | Skill |
|--------|-------|
| Adding new tables or columns | `sqlite-forensic` |
| Adding type hints or docstrings | `python-forensics` |
| Handling amounts, balances, or transaction values | `python-forensics` |
| Interacting with data/input/ or seeds | `sqlite-forensic` |
| Modifying database schema or SQLite models | `sqlite-forensic` |
| Querying or writing to case.sqlite | `sqlite-forensic` |
| Writing or modifying any Python function | `python-forensics` |
| Building graph response for Cytoscape.js | `cytoscape-js` |

---

## Responsibility

Business logic: crawling, analysis, and seed import.
Orchestrates providers and persists results to SQLite.

## Critical Rules

- All DB writes go through db.py get_connection()
- Crawl operations are append-only — no updates to existing txs
- Audit trail: every operation logs timestamp + source
- graph_service.py output format is a contract with the frontend 
- never change the JSON structure without updating routes/ and static/app.js
