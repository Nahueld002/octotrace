"""Case route — GET /api/case/graph for loading all saved transactions.

Provides a read-only endpoint that queries all saved transactions from the
database and returns them as Cytoscape-compatible graph elements. Used by
the Case View toggle in the frontend.

This module reuses _transfer_to_elements from query.py for consistent
element formatting across both search and case views.
"""

from typing import Any, Dict

from fastapi import APIRouter
from src.db import get_connection
from src.web.routes.query import _transfer_to_elements

router = APIRouter()


@router.get("/case/graph")
async def get_case_graph() -> Dict[str, Any]:
    """Return all saved transactions as graph elements.

    Queries all transactions from the database, deduplicates addresses,
    checks saved status, and builds Cytoscape-compatible graph elements.
    Uses read-only connection. Returns empty elements if no data exists.

    Returns:
        Dictionary with "elements" key containing nodes and edges arrays
        in the standard Octotrace graph format. Empty arrays if no
        transactions have been saved.

    Raises:
        HTTPException: If the database query fails.
    """
    with get_connection(read_only=True) as conn:
        rows = conn.execute(
            """
            SELECT txid, chain, from_address, to_address, amount,
                   datetime_utc, tag_from, tag_to, service_from, service_to,
                   url_tx, raw_json
            FROM transactions
            ORDER BY datetime_utc DESC
            LIMIT 5000
            """
        ).fetchall()
        transfers = [dict(r) for r in rows]

    elements = _transfer_to_elements(transfers, min_amount="0")
    return {"elements": elements}
