"""Octotrace — USDT Forensic Traceability Tool.

A specialized local forensic tool for tracking USDT transaction flows
across TRON (TRC20) and Ethereum (ERC20) blockchains.

This package contains the core infrastructure:
- Configuration management (src/config.py)
- SQLite database layer (src/db.py)
- Blockchain providers (src/providers/)
- Business logic services (src/services/)
- FastAPI web interface (src/web/)
"""

try:
    from importlib.metadata import version as _version
    __version__ = _version("octotrace")
except Exception:
    __version__ = "0.0.0"
