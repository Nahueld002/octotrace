"""Base provider interface for blockchain data retrieval.

This module defines the abstract base class for all blockchain providers
used by Octotrace to fetch USDT transfer data and address metadata.
"""

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Dict, List
from datetime import datetime


class BaseProvider(ABC):
    """Abstract base class for blockchain data providers.

    All blockchain providers must implement this interface to ensure
    consistent data retrieval and normalization across different chains.
    """

    CHAIN: str  # "ETH" or "TRON"

    @abstractmethod
    def get_transfers(self, address: str, start_dt: str, end_dt: str) -> List[Dict]:
        """Fetch token transfers for an address within a date range.

        Args:
            address: Blockchain address to query
            start_dt: Start datetime in ISO format (e.g., "2024-01-01T00:00:00")
            end_dt: End datetime in ISO format (e.g., "2024-01-02T00:00:00")

        Returns:
            List of normalized transfer dictionaries containing:
                - txid: Transaction hash
                - chain: Blockchain identifier ("ETH" or "TRON")
                - from_address: Sender address
                - to_address: Recipient address
                - amount: Transfer amount as string (Decimal formatted)
                - datetime_utc: Transaction datetime in ISO format
                - token_symbol: Token symbol (e.g., "USDT")
                - block_number: Block number
                - confirmations: Number of confirmations
                - tag_from: Optional sender tag
                - tag_to: Optional recipient tag
                - service_from: Optional sender service
                - service_to: Optional recipient service
                - url_tx: Evidence URL for transaction
                - raw_json: Original API response as JSON string

        Raises:
            Exception: If data fetching fails
        """

    @abstractmethod
    def get_transaction(self, txid: str) -> Dict:
        """Fetch a single transaction by hash.

        Args:
            txid: Transaction hash to retrieve

        Returns:
            Normalized transaction dictionary with same schema as get_transfers

        Raises:
            Exception: If transaction cannot be found or API call fails
        """

    @abstractmethod
    def get_address_info(self, address: str) -> Dict:
        """Fetch address metadata (tags, service info).

        Args:
            address: Blockchain address to query

        Returns:
            Dictionary with address metadata:
                - tag_public: Public tag associated with address
                - service_name: Service name if address represents a service
                - url: URL to view address on explorer

        Raises:
            Exception: If address metadata cannot be retrieved
        """

    def _normalize_transfer(self, raw_data: Dict) -> Dict:
        """Normalize raw API response data into standardized transfer format.

        Args:
            raw_data: Raw data from API response

        Returns:
            Normalized transfer dictionary with standardized structure
        """
        # Convert amount to string representation of Decimal
        amount = str(Decimal(raw_data.get('value', '0')))

        # Extract common fields
        transfer = {
            "txid": raw_data.get('hash', ''),
            "chain": self.CHAIN,
            "from_address": raw_data.get('from', ''),
            "to_address": raw_data.get('to', ''),
            'amount': amount,
            "datetime_utc": raw_data.get('timeStamp', ''),
            "token_symbol": raw_data.get('tokenSymbol', 'USDT'),
            "block_number": int(raw_data.get('blockNumber', 0)),
            "confirmations": int(raw_data.get('confirmations', 0)),
            "tag_from": raw_data.get('tag_from'),
            "tag_to": raw_data.get('tag_to'),
            "service_from": raw_data.get('service_from'),
            "service_to": raw_data.get('service_to'),
            "url_tx": self._build_tx_url(raw_data.get('hash', '')),
            "raw_json": str(raw_data)
        }

        return transfer

    def _build_tx_url(self, txid: str) -> str:
        """Build transaction URL for the blockchain explorer.

        Args:
            txid: Transaction hash

        Returns:
            URL to transaction on blockchain explorer
        """
        # This should be overridden by subclasses
        return ""