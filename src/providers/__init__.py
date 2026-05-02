"""Octotrace API providers for blockchain data retrieval.

This package contains the provider adapters that interface with external
blockchain explorers (Etherscan and Tronscan) to fetch USDT transfer data
and address metadata for forensic analysis.

Classes:
    BaseProvider: Abstract base for all blockchain providers.
    EtherscanProvider: Ethereum (ERC-20) blockchain data adapter.
    TronscanProvider: TRON (TRC-20) blockchain data adapter.
"""

from src.providers.base import BaseProvider
from src.providers.etherscan import EtherscanProvider
from src.providers.tronscan import TronscanProvider

__all__ = [
    "BaseProvider",
    "EtherscanProvider",
    "TronscanProvider",
]
