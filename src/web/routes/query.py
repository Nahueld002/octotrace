"""Query route for Octotrace API.

Handles POST /api/query endpoint for initiating trace queries
and GET /api/node/{address} for fetching address transactions.
"""

from datetime import datetime

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
    min_amount: str = "1"

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

    # Collect all unique addresses to check saved status in DB
    all_addresses = set()
    for t in transfers:
        if t.get('from_address'):
            all_addresses.add(t['from_address'])
        if t.get('to_address'):
            all_addresses.add(t['to_address'])

    saved_set: set = set()
    if all_addresses:
        placeholders = ','.join('?' * len(all_addresses))
        with get_connection(read_only=True) as conn:
            rows = conn.execute(
                f"SELECT address FROM addresses WHERE address IN ({placeholders})",
                list(all_addresses),
            ).fetchall()
            saved_set = {r[0] for r in rows}

    # Fetch label_manual for all addresses in the batch
    label_manual_map: dict = {}
    if all_addresses:
        placeholders = ','.join('?' * len(all_addresses))
        with get_connection(read_only=True) as conn:
            rows = conn.execute(
                f"SELECT address, label_manual FROM addresses "
                f"WHERE address IN ({placeholders})",
                list(all_addresses),
            ).fetchall()
            label_manual_map = {r[0]: r[1] for r in rows}

    tx_saved_set: set = set()
    all_txids = {t['txid'] for t in transfers if t.get('txid')}
    if all_txids:
        placeholders = ','.join('?' * len(all_txids))
        with get_connection(read_only=True) as conn:
            rows = conn.execute(
                f"SELECT txid FROM transactions WHERE txid IN ({placeholders})",
                list(all_txids),
            ).fetchall()
            tx_saved_set = {r[0] for r in rows}

    nodes: Dict[str, Any] = {}
    edges = []

    for transfer in transfers:
        from_addr = transfer['from_address']
        if from_addr not in nodes:
            nodes[from_addr] = {
                "data": {
                    "id": from_addr,
                    "label": _build_label(from_addr, transfer.get('tag_from')),
                    "tag": transfer.get('tag_from'),
                    "service": transfer.get('service_from'),
                    "chain": transfer['chain'],
                    "saved": from_addr in saved_set,
                    "is_service": bool(transfer.get('service_from')),
                    "label_manual": label_manual_map.get(from_addr),
                }
            }

        to_addr = transfer['to_address']
        if to_addr not in nodes:
            nodes[to_addr] = {
                "data": {
                    "id": to_addr,
                    "label": _build_label(to_addr, transfer.get('tag_to')),
                    "tag": transfer.get('tag_to'),
                    "service": transfer.get('service_to'),
                    "chain": transfer['chain'],
                    "saved": to_addr in saved_set,
                    "is_service": bool(transfer.get('service_to')),
                    "label_manual": label_manual_map.get(to_addr),
                }
            }

        edge = {
            "data": {
                "id": transfer['txid'],
                "source": from_addr,
                "target": to_addr,
                "amount": f"{transfer['amount']} USDT",
                "datetime": transfer['datetime_utc'],
                "chain": transfer['chain'],
                "saved": transfer['txid'] in tx_saved_set,
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
        # Etherscan V2 does not support direct txhash lookup on the tokentx
        # endpoint without a known address. The provider raises
        # NotImplementedError. Return an empty graph with an informative
        # message instead of a HTTP 500.
        try:
            tx_data = provider.get_transaction(request.input)
            transfers = [tx_data] if tx_data else []
        except NotImplementedError:
            return {
                "elements": {"nodes": [], "edges": []},
                "message": "TXID lookup requires known address. Use address search and expand from there."
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to fetch transaction: {str(e)}")
    else:
        # If it's an address, get transfers for that address
        try:
            # Convert ISO strings to datetime objects for the provider interface
            start_dt = datetime.fromisoformat(request.start_dt)
            end_dt = datetime.fromisoformat(request.end_dt)
            transfers = provider.get_transfers(request.input, start_dt, end_dt)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to fetch transfers: {str(e)}")
    
    # Convert to graph elements
    elements = _transfer_to_elements(transfers, request.min_amount)
    
    return {"elements": elements}


@router.get("/node/{address}")
async def get_node_transactions(
    address: str,
    chain: str,
    start_dt: str,
    end_dt: str,
):
    """Retorna todas las transacciones de una address para mostrar en el panel.

    Args:
        address: Wallet address to query
        chain: Blockchain identifier ("ETH" or "TRON")
        start_dt: Start datetime in ISO format
        end_dt: End datetime in ISO format

    Returns:
        Dictionary with address and its transfers list
    """
    provider = _get_provider(chain.upper())
    start = datetime.fromisoformat(start_dt)
    end = datetime.fromisoformat(end_dt)
    transfers = provider.get_transfers(address, start, end)

    # Mark which transfers are already saved in the DB
    all_txids = [t['txid'] for t in transfers if t.get('txid')]
    saved_txids: set = set()
    if all_txids:
        placeholders = ','.join('?' * len(all_txids))
        with get_connection(read_only=True) as conn:
            rows = conn.execute(
                f"SELECT txid FROM transactions WHERE txid IN ({placeholders})",
                all_txids,
            ).fetchall()
            saved_txids = {r[0] for r in rows}

    for t in transfers:
        t['saved'] = t.get('txid') in saved_txids

    return {"address": address, "chain": chain.upper(), "transfers": transfers}