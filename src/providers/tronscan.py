"""Tronscan API provider for TRON (TRC-20) USDT transfers.

This module implements the TronscanProvider class that fetches USDT
transfer data from the Tronscan API and normalizes it for forensic analysis.
"""

import time
import json
from decimal import Decimal
from typing import Dict, List
from datetime import datetime, timezone
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

    def get_transfers(
        self,
        address: str,
        start_dt: datetime,
        end_dt: datetime,
        chain: str = "tron",
    ) -> List[Dict]:
        """Fetch token transfers for an address within a date range.

        Args:
            address: TRON address to query
            start_dt: Start datetime (timezone-aware)
            end_dt: End datetime (timezone-aware)
            chain: Chain identifier (default: "tron"). Currently only
                TRON mainnet is supported.

        Returns:
            List of normalized transfer dictionaries

        Raises:
            requests.RequestException: If API call fails
        """
        try:
            # Convert datetime objects to timestamps in milliseconds
            # The API accepts timestamps and already filters by range
            start_timestamp = int(start_dt.timestamp() * 1000)
            end_timestamp = int(end_dt.timestamp() * 1000)

            # Prepare API parameters
            params = {
                "relatedAddress": address,
                "start_timestamp": start_timestamp,
                "end_timestamp": end_timestamp,
                "limit": 50,
            }

            # Make API request
            response = requests.get(
                f"{self.API_BASE}/token_trc20/transfers",
                params=params,
                headers=self.headers,
                timeout=30,
            )
            response.raise_for_status()

            data = response.json()

            # Extract contractInfo at response level (dict keyed by address)
            contract_info = data.get("contractInfo", {})

            # Process transfers — API already filters by timestamps,
            # so no redundant secondary filter needed
            transfers = []
            for transfer in data.get("token_transfers", []):
                normalized = self._normalize_tronscan_transfer(
                    transfer, contract_info
                )
                transfers.append(normalized)

            return transfers

        except requests.RequestException:
            # Return empty list on network failure
            return []
        except Exception:
            # Return empty list on any other error
            return []

    def get_transaction(self, txid: str) -> Dict:
        """Fetch a single TRC20 transfer by transaction hash.

        Uses token_trc20/transfers with relatedAddress from a broad search,
        then filters by transaction_id.

        Note:
            Tronscan does not support direct TRC20 lookup by txid for
            normalized transfer data. Use get_transfers() instead.

        Args:
            txid: TRON transaction hash

        Raises:
            NotImplementedError: Always — use get_transfers() instead.
        """
        raise NotImplementedError(
            "Direct TRC20 lookup by txid not supported. Use get_transfers() instead."
        )

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
        raise NotImplementedError(
            "Tronscan address tagging is not implemented in this version"
        )

    def _normalize_tronscan_transfer(
        self, raw_data: Dict, contract_info: Dict = None
    ) -> Dict:
        """Normalize Tronscan API response data into standardized transfer format.

        Args:
            raw_data: Raw data from Tronscan API response
            contract_info: Contract info map keyed by address, used to
                resolve address labels (tag1). Extracted from response-level
                `contractInfo` field.

        Returns:
            Normalized transfer dictionary
        """
        if contract_info is None:
            contract_info = {}

        # Extract token info
        token_info = raw_data.get("tokenInfo", {})
        quant = raw_data.get("quant", 0)
        token_decimal = token_info.get("tokenDecimal", 6)

        # Calculate amount with proper decimal precision
        amount = Decimal(str(quant)) / Decimal(10 ** token_decimal)
        amount = amount.quantize(Decimal("0.000001"))

        # Resolve addresses with fallback — API uses snake_case fields
        # but different endpoints (e.g., /transaction-info) use camelCase
        txid = raw_data.get("transaction_id") or raw_data.get("hash", "")
        from_addr = raw_data.get("from_address") or raw_data.get("fromAddress", "")
        to_addr = raw_data.get("to_address") or raw_data.get("toAddress", "")

        # Extract tags — API may provide them directly in the transfer
        # as nested dicts (e.g., {"from_address_tag": "Binance-Hot 9"})
        # or via contractInfo map keyed by address
        raw_from_tag = raw_data.get("from_address_tag")
        if isinstance(raw_from_tag, dict):
            tag_from = raw_from_tag.get("from_address_tag")
        else:
            tag_from = raw_from_tag
        tag_from = tag_from or (
            contract_info.get(from_addr, {}).get("tag1")
            if contract_info
            else None
        )

        raw_to_tag = raw_data.get("to_address_tag")
        if isinstance(raw_to_tag, dict):
            tag_to = raw_to_tag.get("to_address_tag")
        else:
            tag_to = raw_to_tag
        tag_to = tag_to or (
            contract_info.get(to_addr, {}).get("tag1")
            if contract_info
            else None
        )

        # Build transaction URL
        tx_url = f"https://tronscan.org/#/transaction/{txid}"

        # Determine timestamp — block_ts from token_trc20/transfers,
        # timestamp from transaction-info endpoint (both in milliseconds)
        ts_ms = int(raw_data.get("block_ts") or raw_data.get("timestamp", 0))

        # Normalize the transfer data
        transfer = {
            "txid": txid,
            "chain": self.CHAIN,
            "from_address": from_addr,
            "to_address": to_addr,
            "amount": str(amount),
            "datetime_utc": datetime.utcfromtimestamp(ts_ms / 1000).isoformat(),
            "token_symbol": token_info.get("tokenName", "USDT"),
            "block_number": int(raw_data.get("block") or raw_data.get("blockNumber", 0)),
            "confirmations": int(raw_data.get("confirmations", 0)),
            "tag_from": tag_from,
            "tag_to": tag_to,
            "service_from": None,
            "service_to": None,
            "url_tx": tx_url,
            "raw_json": json.dumps(raw_data),
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
