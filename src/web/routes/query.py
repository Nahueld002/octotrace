"""Query route for Octotrace API.

Handles POST /api/query endpoint for initiating trace queries.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Literal, Dict, Any
from decimal import Decimal
import json

from src.db import get_connection
from src.providers.etherscan import EtherscanProvider
from src.providers.tronscan import TronscanProvider
from src.providers.base import BaseProvider

# Evidence URL templates
_URL_TX = {"ETH": "https://etherscan.io/tx/{txid}", "TRON": "https://tronscan.org/#/transaction/{txid}"}
_URL_ADDR = {"ETH": "https://etherscan.io/address/{address}", "TRON": "https://tronscan.org/#/address/{address}"}

router = APIRouter()

class QueryRequest(BaseModel):
    """Request model for query endpoint."""
    input: str
    chain: Literal["ETH", "TRON"]
    start_dt: str
    end_dt: str

def _classify_input(input_str: str) -> str:
    """Classify input as either address or transaction ID.
    
    Args:
        input_str: Input string to classify
        
    Returns:
        "address" or "txid" based on input format
    """
    # Simple heuristic: if it looks like a transaction hash (starts with 0x, 64 hex chars)
    if input_str.startswith("0x") and len(input_str) == 66:
        return "txid"
    # Otherwise treat as address (simplified check)
    elif len(input_str) >= 30 and len(input_str) <= 50:
        return "address"
    else:
        # Default to address for now
        return "address"

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

@router.post("/query")
async def query_endpoint(request: QueryRequest):
    """Handle query requests for USDT traces.
    
    Args:
        request: Query request with input, chain, start_dt, end_dt
        
    Returns:
        Graph elements representing the trace
    """
    # Classify input
    input_type = _classify_input(request.input)
    
    # Get appropriate provider
    provider = _get_provider(request.chain)
    
    # Fetch transfers based on input type
    if input_type == "txid":
        # If it's a transaction ID, get the specific transaction
        try:
            tx_data = provider.get_transaction(request.input)
            transfers = [tx_data] if tx_data else []
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to fetch transaction: {str(e)}")
    else:
        # If it's an address, get transfers for that address
        try:
            transfers = provider.get_transfers(request.input, request.start_dt, request.end_dt)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to fetch transfers: {str(e)}")
    
    # Convert to graph elements
    elements = _transfer_to_elements(transfers)
    
    return {"elements": elements}