"""Configuration management for Octotrace.

Loads environment variables from `.env` file using Pydantic BaseSettings.
Provides validated API credentials for blockchain data providers.

Environment Variables:
    ETHERSCAN_API_KEY: Etherscan API token for Ethereum (ERC20) data.
    TRONSCAN_API_KEY: Tronscan API token for TRON (TRC20) data.

Example:
    >>> from src.config import settings
    >>> settings.ETHERSCAN_API_KEY
    'IJNS45FYV1U8E4DA6BN38EESGCFNCTFZ1W'
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Attributes:
        ETHERSCAN_API_KEY: API token for Etherscan (Ethereum blockchain).
        TRONSCAN_API_KEY: API token for Tronscan (TRON blockchain).
    """

    ETHERSCAN_API_KEY: str
    TRONSCAN_API_KEY: str

    model_config = SettingsConfigDict(
        env_file=Path(__file__).parent.parent / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings singleton.

    Returns:
        Settings: The cached Settings instance with loaded environment values.
    """
    return Settings()
