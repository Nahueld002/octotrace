"""Tronscan API provider for TRON (TRC-20) USDT transfers.

This module implements the TronscanProvider class that fetches USDT
transfer data from the Tronscan API and normalizes it for forensic analysis.
"""

import time
import json
from decimal import Decimal
from typing import Dict, List
from datetime import datetime
import requests

from src.providers.base import BaseProvider
from src.config import get_settings


class TronscanProvider(BaseProvider):
    """TRON (TRC-20) blockchain data provider using Tronscan API."""

    CHAIN = "TRON"
    USDT_CONTRACT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
    API_BASE = "https://apilist.tronscanapi.com/api"
    
    def __init__(self):
        """Initialize Tronscan provider with API key from settings."""
        self.api_key = get_settings().TRONSCAN_API_KEY
        self.headers = {"TRON-PRO-API-KEY": self.api_key}

    def get_transfers(self, address: str, start_dt: str, end_dt: str) -> List[Dict]:
        """Fetch token transfers for an address within a date range.

        Args:
            address: TRON address to query
            start_dt: Start datetime in ISO format (e.g., "2024-01-01T00:00:00")
            end_dt: End datetime in ISO format (e.g., "2024-01-02T00:00:00")

        Returns:
            List of normalized transfer dictionaries

        Raises:
            requests.RequestException: If API call fails
        """
        try:
            # Convert datetime strings to timestamps in milliseconds
            start_timestamp = int(datetime.fromisoformat(start_dt.replace('Z', '+00:00')).timestamp() * 1000)
            end_timestamp = int(datetime.fromisoformat(end_dt.replace('Z', '+00:00')).timestamp() * 1000)
            
            # Prepare API parameters
            params = {
                "relatedAddress": address,
                "start_timestamp": start_timestamp,
                "end_timestamp": end_timestamp,
                "limit": 50  # Limit to prevent overwhelming responses
            }
            
            # Make API request
            response = requests.get(
                f"{self.API_BASE}/token_trc20/transfers", 
                params=params, 
                headers=self.headers,
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Process transfers
            transfers = []
            for transfer in data.get('data', []):
                # Convert timestamp to datetime for filtering
                timestamp = int(transfer.get('timestamp', 0))
                transfer_datetime = datetime.utcfromtimestamp(timestamp / 1000).isoformat()
                
                # Filter by date range
                if start_dt <= transfer_datetime <= end_dt:
                    # Normalize the transfer data
                    normalized = self._normalize_tronscan_transfer(transfer)
                    transfers.append(normalized)
            
            return transfers
            
        except requests.RequestException:
            # Return empty list on network failure
            return []
        except Exception:
            # Return empty list on any other error
            return []

    def get_transaction(self, txid: str) -> Dict:
        """Fetch a single transaction by hash.

        Args:
            txid: TRON transaction hash

        Returns:
            Normalized transaction dictionary

        Raises:
            requests.RequestException: If API call fails
            ValueError: If transaction not found
        """
        try:
            # Prepare API parameters
            params = {
                "hash": txid
            }
            
            # Make API request
            response = requests.get(
                f"{self.API_BASE}/transaction-info", 
                params=params, 
                headers=self.headers,
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Check if transaction was found
            if not data.get('success', False):
                raise ValueError("Transaction not found")
            
            # Normalize the transfer data
            return self._normalize_tronscan_transfer(data.get('data', {}))
            
        except requests.RequestException:
            raise
        except Exception:
            raise ValueError("Transaction not found")

    def get_address_info(self, address: str) -> Dict:
        """Fetch address metadata (tags, service info) from Tronscan.

        Args:
            address: TRON address to query

        Returns:
            Dictionary with address metadata:
                - tag_public: Public tag associated with address
                - service_name: Service name if address represents a service
                - url: URL to view address on explorer

        Raises:
            NotImplementedError: Tronscan address tagging not implemented
        """
        # Tronscan address tagging is not available in the current API
        # We raise NotImplementedError as noted in requirements
        raise NotImplementedError("Tronscan address tagging is not implemented in this version")

    def _normalize_tronscan_transfer(self, raw_data: Dict) -> Dict:
        """Normalize Tronscan API response data into standardized transfer format.

        Args:
            raw_data: Raw data from Tronscan API response

        Returns:
            Normalized transfer dictionary
        """
        # Extract token info
        token_info = raw_data.get('tokenInfo', {})
        quant = raw_data.get('quant', 0)
        token_decimal = token_info.get('tokenDecimal', 6)
        
        # Calculate amount with proper decimal precision
        amount = Decimal(quant) / Decimal(10 ** token_decimal)
        amount = amount.quantize(Decimal("0.000001"))
        
        # Extract tags from contractInfo if available
        contract_info = raw_data.get('contractInfo', {})
        tag_from = contract_info.get('tag1') if contract_info else None
        tag_to = contract_info.get('tag2') if contract_info else None
        
        # Build transaction URL
        tx_url = f"https://tronscan.org/#/transaction/{raw_data.get('hash', '')}"
        
        # Normalize the transfer data
        transfer = {
            "txid": raw_data.get('hash', ''),
            "chain": self.CHAIN,
            "from_address": raw_data.get('fromAddress', ''),
            "to_address": raw_data.get('toAddress', ''),
            'amount': str(amount),
            "datetime_utc": datetime.utcfromtimestamp(int(raw_data.get('timestamp', 0)) / 1000).isoformat(),
            "token_symbol": token_info.get('tokenName', 'USDT'),
            "block_number": int(raw_data.get('blockNumber', 0)),
            "confirmations": int(raw_data.get('confirmations', 0)),
            "tag_from": tag_from,
            "tag_to": tag_to,
            "service_from": None,
            "service_to": None,
            "url_tx": tx_url,
            "raw_json": json.dumps(raw_data)
        }
        
        return transfer

    def _build_tx_url(self, txid: str) -> str:
        """Build Tronscan transaction URL.

        Args:
            txid: Transaction hash

        Returns:
            URL to transaction on Tronscan
        """
        return f"https://tronscan.org/#/transaction/{txid}"