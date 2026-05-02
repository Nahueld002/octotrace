"""Expand route for Octotrace API.

Handles POST /api/expand endpoint for expanding traces from an address.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Literal
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

def _transfer_to_elements(transfers: list) -> Dict[str, Any]:
    """Convert list of transfers to graph elements format.
    
    Args:
        transfers: List of normalized transfer dictionaries
        
    Returns:
        Dictionary with nodes and edges in graph format
    """
    nodes = {}
    edges = []
    
    for transfer in transfers:
        # Create node for from_address if not exists
        from_addr = transfer['from_address']
        if from_addr not in nodes:
            nodes[from_addr] = {
                "data": {
                    "id": from_addr,
                    "label": transfer.get('tag_from', from_addr[:6] + '...' + from_addr[-4:]),
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
                    "label": transfer.get('tag_to', to_addr[:6] + '...' + to_addr[-4:]),
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
        transfers = provider.get_transfers(request.address, request.start_dt, request.end_dt)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch transfers: {str(e)}")
    
    # Convert to graph elements
    elements = _transfer_to_elements(transfers)
    
    return {"elements": elements, "cached": False}