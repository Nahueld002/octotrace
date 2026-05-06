"""Save route for Octotrace API.

Handles POST /api/save/tx and /api/save/address endpoints for saving data.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Literal, Optional, Dict, Any
import json

from src.db import get_connection, save_transaction, save_address
from src.providers.etherscan import EtherscanProvider
from src.providers.tronscan import TronscanProvider
from src.providers.base import BaseProvider

# Evidence URL templates
_URL_TX = {"ETH": "https://etherscan.io/tx/{txid}", "TRON": "https://tronscan.org/#/transaction/{txid}"}
_URL_ADDR = {"ETH": "https://etherscan.io/address/{address}", "TRON": "https://tronscan.org/#/address/{address}"}

router = APIRouter()

class TxRecord(BaseModel):
    """Transaction record model."""
    txid: str
    chain: Literal["ETH", "TRON"]
    from_address: str
    to_address: str
    amount: str  # Decimal as string
    datetime_utc: str
    token_symbol: str = "USDT"
    block_number: Optional[int] = None
    confirmations: Optional[int] = None
    tag_from: Optional[str] = None
    tag_to: Optional[str] = None
    service_from: Optional[str] = None
    service_to: Optional[str] = None
    url_tx: Optional[str] = None
    raw_json: str  # JSON string of raw API response

class AddressRecord(BaseModel):
    """Address record model."""
    address: str
    chain: Literal["ETH", "TRON"]
    tag_public: Optional[str] = None
    service_name: Optional[str] = None
    service_url: Optional[str] = None
    first_seen_utc: Optional[str] = None
    last_seen_utc: Optional[str] = None
    url_address: Optional[str] = None
    raw_json: Optional[str] = None

class SaveTxRequest(BaseModel):
    """Request model for saving transactions."""
    tx: TxRecord

class SaveAddressRequest(BaseModel):
    """Request model for saving addresses."""
    address: AddressRecord

class LabelRequest(BaseModel):
    """Request model for setting a manual label on an address."""
    address: str
    chain: str
    label_manual: str

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

@router.post("/save/tx")
async def save_transaction_endpoint(request: SaveTxRequest):
    """Save a transaction to the database.
    
    Args:
        request: Transaction save request
        
    Returns:
        Success status
    """
    try:
        raw_response = json.loads(request.tx.raw_json)
        tx_dict = request.tx.dict()

        # Clean token suffix from amount if it came from the graph edge
        if tx_dict.get('amount') and isinstance(tx_dict['amount'], str):
            tx_dict['amount'] = tx_dict['amount'].replace(' USDT', '').replace(' TRX', '').strip()

        # If raw_json is empty, enrich with provider data (TRON only)
        if not raw_response and request.tx.chain == "TRON":
            try:
                from datetime import datetime, timedelta
                provider = TronscanProvider()
                # Buscar en un rango amplio alrededor de la fecha de la tx
                tx_dt = datetime.fromisoformat(request.tx.datetime_utc)
                start = tx_dt - timedelta(minutes=5)
                end = tx_dt + timedelta(minutes=5)
                transfers = provider.get_transfers(
                    request.tx.from_address, start, end
                )
                # Buscar el txid específico en los resultados
                match = next(
                    (t for t in transfers if t.get('txid') == request.tx.txid),
                    None
                )
                if match:
                    for field in ['block_number', 'confirmations', 'tag_from',
                                  'tag_to', 'service_from', 'service_to',
                                  'token_symbol', 'amount']:
                        if match.get(field) is not None:
                            tx_dict[field] = match[field]
                    # raw_json viene como string JSON en el transfer normalizado
                    raw_response = json.loads(match.get('raw_json', '{}'))
            except Exception:
                pass  # Si falla, guardar con datos básicos

        with get_connection() as conn:
            existing = conn.execute(
                "SELECT id FROM transactions WHERE txid = ?",
                (request.tx.txid,)
            ).fetchone()
            already_existed = existing is not None

            save_transaction(conn, tx_dict, raw_response,
                             is_new_tx=not already_existed)
            conn.commit()

        return {"status": "success", "already_existed": already_existed}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save transaction: {str(e)}")

@router.post("/save/address")
async def save_address_endpoint(request: SaveAddressRequest):
    """Save an address to the database.
    
    Args:
        request: Address save request
        
    Returns:
        Success status
    """
    try:
        # Parse the raw_json string back to dict
        raw_json = json.loads(request.address.raw_json) if request.address.raw_json else None
        
        # Save the address
        with get_connection() as conn:
            save_address(
                conn,
                request.address.address,
                request.address.chain,
                request.address.tag_public,
                request.address.service_name,
                request.address.service_url,
                request.address.first_seen_utc,
                request.address.last_seen_utc,
                request.address.url_address,
                raw_json
            )
            conn.commit()
        
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save address: {str(e)}")


@router.patch("/address/label")
async def set_address_label(request: LabelRequest):
    """Set or update a manual label for an address.

    Uses INSERT ... ON CONFLICT DO UPDATE so the label persists even if
    the address was not previously in the database. Creates a minimal
    address record (without provider data) labeled by the user.

    Args:
        request: Label request with address, chain, and label_manual.

    Returns:
        Success status.
    """
    try:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO addresses (address, chain, label_manual, times_seen)
                VALUES (?, ?, ?, 1)
                ON CONFLICT(address) DO UPDATE SET
                    label_manual = excluded.label_manual
                """,
                (request.address, request.chain, request.label_manual),
            )
            conn.commit()
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to set address label: {str(e)}",
        )