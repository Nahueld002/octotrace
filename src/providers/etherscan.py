"""Etherscan API provider for Ethereum (ERC-20) USDT transfers.

This module implements the EtherscanProvider class that fetches USDT
transfer data from the Etherscan API and normalizes it for forensic analysis.
"""

import time
import json
from decimal import Decimal
from typing import Dict, List
from datetime import datetime
import requests

from src.providers.base import BaseProvider
from src.config import get_settings


class EtherscanProvider(BaseProvider):
    """Ethereum (ERC-20) blockchain data provider using Etherscan API."""

    CHAIN = "ETH"
    USDT_CONTRACT = "0xdAC17F958D2ee523a2206206994597C13D831ec7"
    API_BASE = "https://api.etherscan.io/v2/api"
    
    def __init__(self):
        """Initialize Etherscan provider with API key from settings."""
        self.api_key = get_settings().ETHERSCAN_API_KEY

    def get_transfers(self, address: str, start_dt: str, end_dt: str) -> List[Dict]:
        """Fetch token transfers for an address within a date range.

        Args:
            address: Ethereum address to query
            start_dt: Start datetime in ISO format (e.g., "2024-01-01T00:00:00")
            end_dt: End datetime in ISO format (e.g., "2024-01-02T00:00:00")

        Returns:
            List of normalized transfer dictionaries

        Raises:
            requests.RequestException: If API call fails
        """
        try:
            # Prepare API parameters
            params = {
                "module": "account",
                "action": "tokentx",
                "chainid": 1,
                "contractaddress": self.USDT_CONTRACT,
                "address": address,
                "sort": "desc",
                "offset": 100,
                "page": 1,
                "apikey": self.api_key
            }
            
            # Make API request
            response = requests.get(self.API_BASE, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            # Handle API errors
            if data.get('status') == '0':
                # Log error but return empty list
                return []
            
            # Process transfers
            transfers = []
            for transfer in data.get('result', []):
                # Convert timestamp to datetime for filtering
                timestamp = int(transfer.get('timeStamp', 0))
                transfer_datetime = datetime.utcfromtimestamp(timestamp).isoformat()
                
                # Filter by date range
                if start_dt <= transfer_datetime <= end_dt:
                    # Normalize the transfer data
                    normalized = self._normalize_etherscan_transfer(transfer)
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
            txid: Ethereum transaction hash

        Returns:
            Normalized transaction dictionary

        Raises:
            requests.RequestException: If API call fails
            ValueError: If transaction not found
        """
        try:
            # Prepare API parameters
            params = {
                "module": "account",
                "action": "tokentx",
                "chainid": 1,
                "txhash": txid,
                "apikey": self.api_key
            }
            
            # Make API request
            response = requests.get(self.API_BASE, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            # Handle API errors
            if data.get('status') == '0':
                raise ValueError("Transaction not found")
            
            # Find the transaction in results
            for transfer in data.get('result', []):
                if transfer.get('hash') == txid:
                    # Normalize the transfer data
                    return self._normalize_etherscan_transfer(transfer)
                    
            raise ValueError("Transaction not found")
            
        except requests.RequestException:
            raise
        except Exception:
            raise ValueError("Transaction not found")

    def get_address_info(self, address: str) -> Dict:
        """Fetch address metadata (tags, service info) from Etherscan.

        Args:
            address: Ethereum address to query

        Returns:
            Dictionary with address metadata:
                - tag_public: Public tag associated with address
                - service_name: Service name if address represents a service
                - url: URL to view address on explorer

        Raises:
            requests.RequestException: If API call fails
        """
        try:
            # Prepare API parameters
            params = {
                "module": "nametag",
                "action": "getaddresstag",
                "chainid": 1,
                "address": address,
                "apikey": self.api_key
            }
            
            # Make API request
            response = requests.get(self.API_BASE, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            # Handle API errors gracefully
            if data.get('status') == '0':
                # Return empty metadata for failed requests
                return {
                    'tag_public': None,
                    'service_name': None,
                    'url': f"https://etherscan.io/address/{address}"
                }
            
            # Extract address metadata
            result = data.get('result', [{}])[0] if data.get('result') else {}
            
            return {
                'tag_public': result.get('tag', None),
                'service_name': result.get('service', None),
                'url': f"https://etherscan.io/address/{address}"
            }
            
        except requests.RequestException:
            # Return empty metadata on network failure
            return {
                'tag_public': None,
                'service_name': None,
                'url': f"https://etherscan.io/address/{address}"
            }
        except Exception:
            # Return empty metadata on any other error
            return {
                'tag_public': None,
                'service_name': None,
                'url': f"https://etherscan.io/address/{address}"
            }

    def _normalize_etherscan_transfer(self, raw_data: Dict) -> Dict:
        """Normalize Etherscan API response data into standardized transfer format.

        Args:
            raw_data: Raw data from Etherscan API response

        Returns:
            Normalized transfer dictionary
        """
        # Convert amount to proper Decimal format
        value = raw_data.get('value', '0')
        token_decimal = raw_data.get('tokenDecimal', '6')
        
        # Calculate amount with proper decimal precision
        amount = Decimal(str(value)) / Decimal(10 ** int(token_decimal))
        amount = amount.quantize(Decimal("0.000001"))
        
        # Build transaction URL
        tx_url = f"https://etherscan.io/tx/{raw_data.get('hash', '')}"
        
        # Get tags if available
        tag_from = raw_data.get('from_tag')
        tag_to = raw_data.get('to_tag')
        
        # Normalize the transfer data
        transfer = {
            "txid": raw_data.get('hash', ''),
            "chain": self.CHAIN,
            "from_address": raw_data.get('from', ''),
            "to_address": raw_data.get('to', ''),
            'amount': str(amount),
            "datetime_utc": datetime.utcfromtimestamp(int(raw_data.get('timeStamp', 0))).isoformat(),
            "token_symbol": raw_data.get('tokenSymbol', 'USDT'),
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
        """Build Etherscan transaction URL.

        Args:
            txid: Transaction hash

        Returns:
            URL to transaction on Etherscan
        """
        return f"https://etherscan.io/tx/{txid}"