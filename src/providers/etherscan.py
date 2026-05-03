"""Etherscan API provider for Ethereum (ERC-20) USDT transfers.

This module implements the EtherscanProvider class that fetches USDT
transfer data from the Etherscan API and normalizes it for forensic analysis.
"""

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

    def get_transfers(
        self,
        address: str,
        start_dt: datetime,
        end_dt: datetime,
        chain: str = "ethereum",
    ) -> List[Dict]:
        """Fetch token transfers for an address within a date range.

        Paginates through Etherscan results (max 100 per page, up to 10 pages
        max) and filters by numeric Unix timestamp comparison for reliable
        date range matching.

        The API returns results in descending order. The method skips pages
        until it reaches the target time window, then collects all matching
        transfers until results are older than start_dt.

        Args:
            address: Ethereum address to query
            start_dt: Start datetime (timezone-aware)
            end_dt: End datetime (timezone-aware)
            chain: EVM chain identifier (default: "ethereum").
                Currently only "ethereum" is supported.

        Returns:
            List of normalized transfer dictionaries

        Raises:
            requests.RequestException: If API call fails
        """
        try:
            start_ts = int(start_dt.timestamp())
            # Extend end_ts to end of day (23:59:59) for inclusive filtering
            end_ts = int(end_dt.timestamp()) + 86399

            transfers: List[Dict] = []
            page = 1
            MAX_PAGES = 10

            while page <= MAX_PAGES:
                params = {
                    "module": "account",
                    "action": "tokentx",
                    "chainid": 1,
                    "contractaddress": self.USDT_CONTRACT,
                    "address": address,
                    "startblock": 0,
                    "endblock": 99999999,
                    "sort": "desc",
                    "offset": 100,
                    "page": page,
                    "apikey": self.api_key,
                }

                response = requests.get(self.API_BASE, params=params, timeout=30)
                response.raise_for_status()

                data = response.json()

                # API returns status="0" on error or empty results
                if data.get("status") == "0":
                    break

                result = data.get("result", [])
                if not result:
                    break

                # Track oldest timestamp on this page
                oldest_ts_in_page = 0
                found_target_page = False

                for tx in result:
                    ts = int(tx.get("timeStamp", 0))

                    # Track the oldest (smallest) timestamp on this page
                    if oldest_ts_in_page == 0 or ts < oldest_ts_in_page:
                        oldest_ts_in_page = ts

                    if start_ts <= ts <= end_ts:
                        found_target_page = True
                        normalized = self._normalize_etherscan_transfer(tx)
                        transfers.append(normalized)

                # If ALL results on this page are OLDER than start_ts, stop
                if oldest_ts_in_page > 0 and oldest_ts_in_page < start_ts:
                    break

                # If we found the target range but the oldest result is
                # within range, there may be more — keep paginating
                page += 1

            return transfers

        except requests.RequestException:
            return []
        except Exception:
            return []

    def get_transaction(self, txid: str) -> Dict:
        """Fetch a single transaction by hash.

        Etherscan v2 does NOT support direct txhash lookup on the tokentx
        endpoint. The old approach (action=tokentx with txhash param) was
        invalid and silently returned empty results.

        For single transaction forensic lookup, use get_transfers() with
        the known sender/recipient address and a narrow time window
        instead. For already-processed transfers, the data is available
        from case.sqlite.

        Args:
            txid: Ethereum transaction hash

        Raises:
            NotImplementedError: Single txhash lookup not supported on
                Etherscan v2 tokentx endpoint
        """
        raise NotImplementedError(
            "Single transaction lookup by hash is not supported on Etherscan v2. "
            "Use get_transfers() with the known address, or retrieve from case.sqlite."
        )

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
            params = {
                "module": "nametag",
                "action": "getaddresstag",
                "chainid": 1,
                "address": address,
                "apikey": self.api_key,
            }

            response = requests.get(self.API_BASE, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()

            # Handle API errors gracefully
            if data.get("status") == "0":
                return {
                    "tag_public": None,
                    "service_name": None,
                    "url": f"https://etherscan.io/address/{address}",
                }

            # Extract address metadata
            result = data.get("result", [{}])[0] if data.get("result") else {}

            return {
                "tag_public": result.get("tag", None),
                "service_name": result.get("service", None),
                "url": f"https://etherscan.io/address/{address}",
            }

        except requests.RequestException:
            return {
                "tag_public": None,
                "service_name": None,
                "url": f"https://etherscan.io/address/{address}",
            }
        except Exception:
            return {
                "tag_public": None,
                "service_name": None,
                "url": f"https://etherscan.io/address/{address}",
            }

    def _normalize_etherscan_transfer(self, raw_data: Dict) -> Dict:
        """Normalize Etherscan API response data into standardized transfer format.

        Args:
            raw_data: Raw data from Etherscan API response

        Returns:
            Normalized transfer dictionary
        """
        # Convert amount to proper Decimal format
        value = raw_data.get("value", "0")
        token_decimal = raw_data.get("tokenDecimal", "6")

        # Calculate amount with proper decimal precision
        amount = Decimal(str(value)) / Decimal(10 ** int(token_decimal))
        amount = amount.quantize(Decimal("0.000001"))

        # Build transaction URL
        tx_url = f"https://etherscan.io/tx/{raw_data.get('hash', '')}"

        # Get tags if available
        tag_from = raw_data.get("from_tag")
        tag_to = raw_data.get("to_tag")

        transfer = {
            "txid": raw_data.get("hash", ""),
            "chain": self.CHAIN,
            "from_address": raw_data.get("from", ""),
            "to_address": raw_data.get("to", ""),
            "amount": str(amount),
            "datetime_utc": datetime.utcfromtimestamp(
                int(raw_data.get("timeStamp", 0))
            ).isoformat(),
            "token_symbol": raw_data.get("tokenSymbol", "USDT"),
            "block_number": int(raw_data.get("blockNumber", 0)),
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
        """Build Etherscan transaction URL.

        Args:
            txid: Transaction hash

        Returns:
            URL to transaction on Etherscan
        """
        return f"https://etherscan.io/tx/{txid}"
