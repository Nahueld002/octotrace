"""Expand route for Octotrace API.

Handles POST /api/expand endpoint for expanding traces from an address.
"""

from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Literal
from decimal import Decimal
import json

from src.db import get_connection, is_cached
from src.providers.etherscan import EtherscanProvider
from src.providers.tronscan import TronscanProvider
from src.providers.base import BaseProvider

# Evidence URL templates
_URL_TX = {"ETH": "https://etherscan.io/tx/{txid}", "TRON": "https://tronscan.org/#/transaction/{txid}"}
_URL_ADDR = {"ETH": "https://etherscan.io/address/{address}", "TRON": "https://tronscan.org/#/address/{address}"}

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


def _transfer_to_elements(transfers: list, min_amount: str = "1") -> Dict[str, Any]:
    """Convert list of transfers to graph elements format.
    
    Args:
        transfers: List of normalized transfer dictionaries
        min_amount: Minimum amount filter as Decimal string (default "1").
            Transfers below this threshold are excluded.
        
    Returns:
        Dictionary with nodes and edges in graph format
    """
    min_amt = Decimal(min_amount)
    # Filter out transfers with empty critical fields that would
    # cause Cytoscape to reject element creation, and apply
    # minimum amount threshold
    transfers = [
        t for t in transfers
        if t.get('from_address') and t.get('to_address') and t.get('txid')
        and Decimal(t.get('amount', '0')) >= min_amt
    ]

    nodes = {}
    edges = []
    
    for transfer in transfers:
        # Create node for from_address if not exists
        from_addr = transfer['from_address']
        if from_addr not in nodes:
            nodes[from_addr] = {
                "data": {
                    "id": from_addr,
                    "label": _build_label(from_addr, transfer.get('tag_from')),
                    "tag": transfer.get('tag_from'),
                    "service": transfer.get('service_from'),
                    "chain": transfer['chain']
                }
            }
        
        # Create node for to_address if not exists  
        to_addr = transfer['to_address']
        if to_addr not in nodes:
            nodes[to_addr] = {
                "data": {
                    "id": to_addr,
                    "label": _build_label(to_addr, transfer.get('tag_to')),
                    "tag": transfer.get('tag_to'),
                    "service": transfer.get('service_to'),
                    "chain": transfer['chain']
                }
            }
        
        # Create edge for this transfer
        edge = {
            "data": {
                "id": transfer['txid'],
                "source": from_addr,
                "target": to_addr,
                "amount": f"{transfer['amount']} USDT",
                "datetime": transfer['datetime_utc'],
                "chain": transfer['chain']
            }
        }
        edges.append(edge)
    
    return {
        "nodes": list(nodes.values()),
        "edges": edges
    }

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
    else:
        raise ValueError(f"Unsupported chain: {chain}")

@router.post("/expand")
async def expand_endpoint(request: ExpandRequest):
    """Handle expand requests for USDT traces from an address.
    
    Checks cache first, then fetches data from provider or database.
    
    Args:
        request: Expand request with address, chain, start_dt, end_dt
        
    Returns:
        Graph elements representing the expanded trace and cache status
    """
    # Check if data is already cached
    with get_connection(read_only=True) as conn:
        cached = is_cached(conn, request.address, request.chain, request.start_dt, request.end_dt)
    
    # If cached, fetch from database
    if cached:
        # This would require implementing a function to fetch from DB
        # For now, we'll simulate by returning empty elements
        elements = {"nodes": [], "edges": []}
        return {"elements": elements, "cached": True}
    
    # If not cached, fetch from provider
    provider = _get_provider(request.chain)

    try:
        # Convert ISO strings to datetime objects for the provider interface
        start_dt = datetime.fromisoformat(request.start_dt)
        end_dt = datetime.fromisoformat(request.end_dt)
        transfers = provider.get_transfers(request.address, start_dt, end_dt)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch transfers: {str(e)}")
    
    # Convert to graph elements
    elements = _transfer_to_elements(transfers, request.min_amount)
    
    return {"elements": elements, "cached": False}