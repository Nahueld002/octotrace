# Octotrace

A local forensic web tool for USDT traceability on Ethereum and TRON networks. 
Renders transaction graphs, supports incremental graph expansion and public address tagging. 
Developed as a degree thesis project.

## Features

- Interactive graph visualization with Cytoscape.js
- Incremental branch expansion without context loss
- Date range filtering for investigation scope
- Public address tags and exchange detection
- Evidence persistence with forensic integrity
- Dual blockchain support (Ethereum + TRON)

## Tech Stack

- **Backend**: FastAPI + Python 3.14
- **Frontend**: Vanilla JS + Cytoscape.js
- **Database**: SQLite (per-case)
- **APIs**: Etherscan v2, Tronscan

## Status

🔄 Early development - Thesis project

## Project Structure

```
octotrace/
├── src/cryptotrace/
│   ├── providers/       # Etherscan & Tronscan API clients
│   ├── services/        # Business logic (crawler, analysis)
│   ├── exports/         # GraphML, CSV exporters
│   ├── db.py           # SQLite models & persistence
│   └── web/            # FastAPI backend + Cytoscape.js frontend
├── data/input/         # Input seeds (immutable)
└── docs/               # Doumentation 
```
