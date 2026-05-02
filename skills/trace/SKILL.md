---
name: blockchain-trace
description: >
  Blockchain tracing for USDT traceability: TRON (TRC20) and EVM (ERC20) API integration, hash parsing, and normalization.
  Trigger: When extracting transfer data from Tronscan or Etherscan APIs.
license: Apache-2.0
metadata:
  author: octotrace
  version: "1.0"
  scope: [root, providers, web]
  auto_invoke:
    - "Classifying input as address or TXID"
    - "Normalizing addresses or transaction hashes"
    - "Detecting blockchain network from input format"
---

## When to Use

- Fetching token transfers from Tronscan API
- Fetching token transfers from Etherscan API
- Parsing transaction hashes (tx_hash)
- Normalizing addresses between TRON and EVM formats
- Extracting USDT transfer amounts from API responses

## Critical Patterns

### API Authentication

| Provider | Header | Endpoint Base |
|----------|--------|---------------|
| Tronscan | `TRON-PRO-API-KEY` | `https://apilist.tronscanapi.com` |
| Etherscan | Query param `apikey` | `https://api.etherscan.io` |

### TRON Address Formats

| Format | Prefix | Length |
|--------|--------|--------|
| Base58 | `T` | 34 chars |
| Hex | `0x` + 40 hex | 42 chars |

**Always normalize to lowercase hex for consistency.**

### ERC20 Token Addresses

| Token | Contract Address |
|-------|------------------|
| USDT (Ethereum) | `0xdAC17F958D2ee523a2206206994597C13D831ec7` |
| USDC | `0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48` |

### TRC20 Token Addresses

| Token | Contract Address |
|-------|-------------------|
| USDT (TRON) | `TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t` |

## API Reference

### Etherscan: Token Transfers (ERC20)

**Endpoint:** `GET https://api.etherscan.io/v2/api`

| Param | Required | Description |
|-------|----------|-------------|
| `chainid` | Yes | `1` for Ethereum, `8453` for Base, etc. |
| `module` | Yes | `account` |
| `action` | Yes | `tokentx` |
| `contractaddress` | Yes | Token contract address |
| `address` | Yes | Wallet address to query |
| `page` | No | Page number (default: 1) |
| `offset` | No | Records per page (default: 100) |
| `sort` | No | `asc` or `desc` (default: `asc`) |

**Response Fields for Destination:**
- `from`: Sender address
- `to`: **Recipient address** (exact destination)
- `value`: Token amount (apply `tokenDecimal`)
- `tokenDecimal`: Divisor for amount (18 for USDT)

```python
# Example response parsing
response = {
    "from": "0x642ae78fafbb8032da552d619ad43f1d81e4dd7c",
    "to": "0x4e83362442b8d1bec281594cea3050c8eb01311c",
    "value": "5901522149285533025181",
    "tokenDecimal": "18"
}

decimals = int(response["tokenDecimal"])  # 18
amount = Decimal(response["value"]) / Decimal(10) ** decimals
```

### Tronscan: TRC20 Transfers

**Endpoint:** `GET https://apilist.tronscanapi.com/api/token_trc20/transfers`

| Param | Required | Description |
|-------|----------|-------------|
| `contract_address` | Yes | TRC20 token contract |
| `relatedAddress` | No | Filter by wallet |
| `fromAddress` | No | Filter by sender |
| `toAddress` | No | Filter by recipient |
| `start` | No | Pagination offset |
| `limit` | No | Results per page (default: 20) |

**Header:** `TRON-PRO-API-KEY: your_api_key`

**Response Fields for Destination:**
- `from_address`: Sender address
- `to_address`: **Recipient address** (exact destination)
- `quant`: Token amount (string, apply `tokenDecimal`)
- `tokenInfo.tokenDecimal`: Divisor for amount

```python
# Example response parsing
transfer = {
    "from_address": "TH3N6kYXow3FUP8Giyjm344qpDgjpChQx7",
    "to_address": "TL5x9MtSnDy537FXKx53yAaHRRNdg9TkkA",
    "quant": "11258727923280441931",
    "tokenInfo": {"tokenDecimal": 18}
}

decimals = transfer["tokenInfo"]["tokenDecimal"]
amount = Decimal(transfer["quant"]) / Decimal(10) ** decimals
```

## Code Examples

### Tronscan API Client

```python
import requests
from decimal import Decimal

TRONSCAN_BASE = "https://apilist.tronscanapi.com/api"

def fetch_trc20_transfers(contract: str, address: str, api_key: str) -> list:
    """Fetch TRC20 transfers from Tronscan API."""
    headers = {"TRON-PRO-API-KEY": api_key}
    params = {
        "contract_address": contract,
        "relatedAddress": address,
        "limit": 50
    }
    response = requests.get(
        f"{TRONSCAN_BASE}/token_trc20/transfers",
        headers=headers,
        params=params,
        timeout=30
    )
    data = response.json()
    return data.get("token_transfers", [])
```

### Etherscan API Client

```python
import requests
from decimal import Decimal

ETHERSCAN_BASE = "https://api.etherscan.io/v2/api"

def fetch_erc20_transfers(
    contract: str,
    address: str,
    chain_id: int,
    api_key: str
) -> list:
    """Fetch ERC20 transfers from Etherscan API."""
    params = {
        "chainid": chain_id,
        "module": "account",
        "action": "tokentx",
        "contractaddress": contract,
        "address": address,
        "sort": "asc",
        "apikey": api_key
    }
    response = requests.get(ETHERSCAN_BASE, params=params, timeout=30)
    data = response.json()
    return data.get("result", [])
```

### Address Normalization

```python
def tron_to_hex(address: str) -> str:
    """Convert TRON Base58 address to hex format."""
    from tronpy.keys import Base58Encoder
    decoded = Base58Encoder.decode(address)
    return decoded.hex()

def normalize_address(address: str) -> str:
    """Normalize any address to lowercase hex."""
    address = address.lower()
    if address.startswith("0x"):
        return address
    if len(address) == 34 and address.startswith("T"):
        return tron_to_hex(address)
    return address
```

### Hash Normalization

```python
def normalize_tx_hash(tx_hash: str) -> str:
    """Normalize transaction hash to lowercase hex without prefix."""
    hash_hex = tx_hash.lower()
    if hash_hex.startswith("0x"):
        hash_hex = hash_hex[2:]
    return hash_hex
```

## Commands

```bash
# Test Tronscan endpoint
curl -H "TRON-PRO-API-KEY: $TRON_API_KEY" \
  "https://apilist.tronscanapi.com/api/token_trc20/transfers?limit=1"

# Test Etherscan endpoint
curl "https://api.etherscan.io/v2/api?chainid=1&module=account&action=tokentx&address=0x...&apikey=$ETHER_API_KEY"
```

## Resources

- **Etherscan API**: https://docs.etherscan.io/
- **Tronscan API**: https://docs.tronscan.org/