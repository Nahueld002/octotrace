"""Expand route for Octotrace API.

Handles POST /api/expand endpoint for expanding traces from an address.
Cache is disabled — always fetches fresh data from the provider API.
"""

from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.db import get_connection
from src.providers.etherscan import EtherscanProvider
from src.providers.tronscan import TronscanProvider
from src.providers.base import BaseProvider

# Evidence URL templates
_URL_TX = {
    "ETH": "https://etherscan.io/tx/{txid}",
    "TRON": "https://tronscan.org/#/transaction/{txid}",
}
_URL_ADDR = {
    "ETH": "https://etherscan.io/address/{address}",
    "TRON": "https://tronscan.org/#/address/{address}",
}

router = APIRouter()


class ExpandRequest(BaseModel):
    """Request model for expand endpoint."""
    address: str
    chain: Literal["ETH", "TRON"]
    start_dt: str
    end_dt: str
    min_amount: str = "1"


def _build_label(address: str, tag: str | None) -> str:
    """Build a display label for a graph node from address and optional tag.

    Args:
        address: Full wallet address.
        tag: Public nametag from API, or None.

    Returns:
        Display label — the tag if present, otherwise a truncated address.
    """
    if tag:
        return tag
    return f"{address[:6]}...{address[-4:]}"


def _get_saved_addresses(conn, addresses: list) -> set:
    """Query which addresses are already saved in the database.

    Args:
        conn: Active read-only sqlite3 connection.
        addresses: List of wallet addresses to check.

    Returns:
        Set of addresses that exist in the addresses table.
    """
    if not addresses:
        return set()
    placeholders = ",".join("?" * len(addresses))
    rows = conn.execute(
        f"SELECT address FROM addresses WHERE address IN ({placeholders})",
        addresses,
    ).fetchall()
    return {r[0] for r in rows}


def _transfer_to_elements(transfers: list, min_amount: str = "1") -> Dict[str, Any]:
    """Convert list of transfers to graph elements format.

    Args:
        transfers: List of normalized transfer dictionaries
        min_amount: Minimum amount filter as Decimal string (default "1").
            Transfers below this threshold are excluded.

    Returns:
        Dictionary with nodes and edges in graph format.
    """
    min_amt = Decimal(min_amount)

    # Filter out transfers with empty critical fields and apply min_amount
    transfers = [
        t for t in transfers
        if t.get("from_address") and t.get("to_address") and t.get("txid")
        and Decimal(t.get("amount", "0")) >= min_amt
    ]

    # Collect all unique addresses to check saved status in DB
    all_addresses = set()
    for t in transfers:
        if t.get("from_address"):
            all_addresses.add(t["from_address"])
        if t.get("to_address"):
            all_addresses.add(t["to_address"])

    saved_set: set = set()
    if all_addresses:
        with get_connection(read_only=True) as conn:
            saved_set = _get_saved_addresses(conn, list(all_addresses))

    nodes: Dict[str, Any] = {}
    edges = []

    for transfer in transfers:
        from_addr = transfer["from_address"]
        if from_addr not in nodes:
            nodes[from_addr] = {
                "data": {
                    "id": from_addr,
                    "label": _build_label(from_addr, transfer.get("tag_from")),
                    "tag": transfer.get("tag_from"),
                    "service": transfer.get("service_from"),
                    "chain": transfer["chain"],
                    "saved": from_addr in saved_set,
                    "is_service": bool(transfer.get("service_from")),
                }
            }

        to_addr = transfer["to_address"]
        if to_addr not in nodes:
            nodes[to_addr] = {
                "data": {
                    "id": to_addr,
                    "label": _build_label(to_addr, transfer.get("tag_to")),
                    "tag": transfer.get("tag_to"),
                    "service": transfer.get("service_to"),
                    "chain": transfer["chain"],
                    "saved": to_addr in saved_set,
                    "is_service": bool(transfer.get("service_to")),
                }
            }

        edge = {
            "data": {
                "id": transfer["txid"],
                "source": from_addr,
                "target": to_addr,
                "amount": f"{transfer['amount']} USDT",
                "datetime": transfer["datetime_utc"],
                "chain": transfer["chain"],
            }
        }
        edges.append(edge)

    return {"nodes": list(nodes.values()), "edges": edges}


def _get_provider(chain: str) -> BaseProvider:
    """Get appropriate provider based on chain.

    Args:
        chain: Blockchain identifier ("ETH" or "TRON")

    Returns:
        Provider instance for the specified chain

    Raises:
        ValueError: If chain is not supported
    """
    if chain == "ETH":
        return EtherscanProvider()
    elif chain == "TRON":
        return TronscanProvider()
    raise ValueError(f"Unsupported chain: {chain}")


@router.post("/expand")
async def expand_endpoint(request: ExpandRequest):
    """Handle expand requests for USDT traces from an address.

    Cache is disabled — always fetches fresh data from the provider API.
    The provider handles its own rate limiting and timestamp filtering.

    Args:
        request: Expand request with address, chain, start_dt, end_dt, min_amount

    Returns:
        Graph elements representing the expanded trace, always uncached.

    Raises:
        HTTPException: If provider fetch fails.
    """
    provider = _get_provider(request.chain)

    try:
        start_dt = datetime.fromisoformat(request.start_dt)
        end_dt = datetime.fromisoformat(request.end_dt)
        transfers = provider.get_transfers(request.address, start_dt, end_dt)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    elements = _transfer_to_elements(transfers, request.min_amount)
    return {"elements": elements, "cached": False}
