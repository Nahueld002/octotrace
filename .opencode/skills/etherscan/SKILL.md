---
name: etherscan
description: >
  Etherscan API patterns for ERC-20 token transfers and address metadata lookup.
  Trigger: When developing extraction logic for EVM (ERC20) transfers,
  looking up address name tags for exchange detection, or querying
  USDT/USDC transfers on Ethereum or other EVM chains.
license: Apache-2.0
metadata:
  author: octotrace
  version: "1.1"
  scope: [root, providers]
  auto_invoke:
    - "Developing extraction logic for Ethereum"
    - "Modifying providers/etherscan.py"
    - "Calling or modifying Etherscan API integration"
---

> ⚠️ **V1 DEPRECATED**: The endpoint `https://api.etherscan.io/api` is fully deprecated
> and returns `NOTOK` for all requests. Always use `https://api.etherscan.io/v2/api`
> with `chainid` as a required query parameter.

## When to Use

- Querying ERC-20 token transfer events (`tokentx`) for a given address
- Looking up address metadata via `getaddresstag` to identify known exchanges (Binance, Coinbase, Bitso, ByBit, etc.)
- Implementing ERC-20 transfer history for Ethereum, BSC, Base, Arbitrum, or other EVM-compatible chain
- Working with multichain setups using the `chainid` parameter

## Critical Patterns

### 1. ERC-20 Token Transfer Events (tokentx)

**Endpoint**: `GET https://api.etherscan.io/v2/api?module=account&action=tokentx&chainid=1`

**Key params**:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `apikey` | string | — | Your Etherscan API key |
| `chainid` | string | `1` | Chain ID: `1`=Ethereum, `56`=BSC, `8453`=Base, etc. |
| `module` | string | `account` | **Must be** `account` |
| `action` | string | `tokentx` | **Must be** `tokentx` |
| `contractaddress` | string | — | ERC-20 token contract to filter by (e.g. `0xdac17f958d2ee523a2206206994597c13d831ec7` for USDT) |
| `address` | string | — | The wallet address to query |
| `startblock` | int | `0` | Start block |
| `endblock` | int | `999999999` | End block |
| `page` | int | `1` | Page number |
| `offset` | int | `100` | Records per page |
| `sort` | string | `asc` | `asc` or `desc` |

**Response fields (`result[]`)**:

| Field | Type | Description |
|-------|------|-------------|
| `blockNumber` | string | Block number |
| `timeStamp` | string | Unix timestamp (seconds) |
| `hash` | string | Transaction hash |
| `from` | string | Sender address |
| `to` | string | Recipient address |
| `contractAddress` | string | ERC-20 token contract address |
| `value` | string | Token amount (raw, divide by `tokenDecimal`) |
| `tokenName` | string | Token name (e.g. `"Tether USD"`) |
| `tokenSymbol` | string | Token symbol (e.g. `"USDT"`) |
| `tokenDecimal` | string | Decimal places (`6` for USDT, `18` for most tokens) |
| `gasUsed` | string | Gas used |
| `gasPrice` | string | Gas price in wei |
| `confirmations` | string | Confirmations count |

**Amount conversion**: `actual_value = int(value) / (10 ** int(tokenDecimal))`

### 2. Address Metadata / Name Tag Lookup (getaddresstag) — PRO

**Endpoint**: `GET https://api.etherscan.io/v2/api?module=nametag&action=getaddresstag&chainid=1`

**⚠ PRO endpoint**: Available exclusively on Pro Plus tier. Throttled to **2 calls/second** regardless of tier.

**Key params**:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `apikey` | string | — | Etherscan API key |
| `chainid` | string | `1` | Chain ID |
| `module` | string | `nametag` | **Must be** `nametag` |
| `action` | string | `getaddresstag` | **Must be** `getaddresstag` |
| `address` | string | — | Address to query |

**Response fields (`result[]`)**:

| Field | Type | Description |
|-------|------|-------------|
| `address` | string | The queried address |
| `nametag` | string | Public name tag (e.g. `"Coinbase 10"`, `"Binance 14"`) |
| `internal_nametag` | string | Internal label |
| `url` | string | Official URL (e.g. `https://coinbase.com`) |
| `labels` | array | Categorical labels (e.g. `["Coinbase", "Exchange"]`) |
| `labels_slug` | array | Slugified labels (e.g. `["coinbase", "exchange"]`) |

**Use for exchange detection**: The `labels` and `nametag` fields are the primary source for identifying `DESTINO_TIPO` (e.g. `"Exchange"`) and `DESTINO_SERVICIO` (e.g. `"Coinbase"`).

Known exchange patterns in nametags:
- `"Coinbase"` — Coinbase
- `"Binance"` — Binance
- `"Bitso"` — Bitso
- `"ByBit"` — ByBit
- `"Kraken"` — Kraken
- `"OKX"` — OKX
- `"KuCoin"` — KuCoin
- `"Gemini"` — Gemini

### 3. Multichain Support

Etherscan API V2 supports 60+ EVM chains via the `chainid` parameter:

| Chain | `chainid` |
|-------|-----------|
| Ethereum | `1` |
| BNB Smart Chain | `56` |
| Base | `8453` |
| Arbitrum | `42161` |
| Optimism | `10` |
| Polygon | `137` |
| Avalanche C-Chain | `43114` |

## Code Examples

### Fetch USDT ERC-20 transfers for an address

```python
import requests

ETHERSCAN_API_KEY = "your_api_key"
BASE_URL = "https://api.etherscan.io/v2/api"

# USDT on Ethereum contract address
USDT_ERC20 = "0xdac17f958d2ee523a2206206994597c13d831ec7"

params = {
    "module": "account",
    "action": "tokentx",
    "chainid": 1,
    "contractaddress": USDT_ERC20,
    "address": "0x4e83362442b8d1bec281594cea3050c8eb01311c",
    "startblock": 0,
    "endblock": 999999999,
    "sort": "desc",
    "offset": 20,
    "page": 1,
    "apikey": ETHERSCAN_API_KEY,
}

response = requests.get(BASE_URL, params=params)
data = response.json()

if data["status"] == "1":
    for tx in data["result"]:
        decimals = int(tx["tokenDecimal"])
        value = int(tx["value"]) / 10 ** decimals
        print(f"{tx['hash'][:16]}... "
              f"{value:,.2f} {tx['tokenSymbol']} "
              f"{tx['from'][:10]}... -> {tx['to'][:10]}...")
```

### Lookup address name tag for exchange detection

```python
params = {
    "module": "nametag",
    "action": "getaddresstag",
    "chainid": 1,
    "address": "0xa9d1e08c7793af67e9d92fe308d5697fb81d3e43",
    "apikey": ETHERSCAN_API_KEY,
}

response = requests.get(BASE_URL, params=params)
result = response.json()

if result["status"] == "1" and result["result"]:
    tag = result["result"][0]
    destino_tipo = "Exchange"
    destino_servicio = tag["nametag"].split(" ")[0]  # e.g. "Coinbase"
    print(f"Address: {tag['address']}")
    print(f"Service: {destino_servicio}")
    print(f"Type: {destino_tipo}")
    print(f"URL: {tag['url']}")
else:
    print("No tag found — address is not a known entity")
```

### Search for transfers on BSC (chainid=56)

```python
params = {
    "module": "account",
    "action": "tokentx",
    "chainid": 56,                               # BNB Smart Chain
    "contractaddress": "0x55d398326f99059ff775485246999027b3197955",  # USDT on BSC
    "address": "0x...",
    "apikey": ETHERSCAN_API_KEY,
}
```

## Commands

```bash
# Fetch USDT ERC-20 transfers (latest 5, descending) — Ethereum mainnet
curl -s "https://api.etherscan.io/v2/api?module=account&action=tokentx\
&chainid=1\
&contractaddress=0xdac17f958d2ee523a2206206994597c13d831ec7\
&address=0x4e83362442b8d1bec281594cea3050c8eb01311c\
&sort=desc&offset=5&apikey=YourApiKeyToken" | jq '.result[:3]'

# Lookup address name tag (PRO endpoint — requires Pro Plus tier)
curl -s "https://api.etherscan.io/v2/api?module=nametag&action=getaddresstag\
&chainid=1\
&address=0xa9d1e08c7793af67e9d92fe308d5697fb81d3e43\
&apikey=YourApiKeyToken" | jq '.result'

# Fetch transfers on BSC (USDT on BSC, chainid=56)
curl -s "https://api.etherscan.io/v2/api?module=account&action=tokentx\
&chainid=56\
&contractaddress=0x55d398326f99059ff775485246999027b3197955\
&address=0x...\
&sort=desc&offset=3&apikey=YourApiKeyToken" | jq '.result[:2]'
```

## Fallback sin PRO
Si `getaddresstag` devuelve status != "1", el tag es null.
No lanzar error — el nodo se renderiza sin label, no bloquear el flujo.

---

## Resources

- **Documentation**: See [blockchain-trace](../trace/skill.md) for EVM/TRON integration patterns
- **Documentation**: See [AGENTS.md](../../AGENTS.md) for project-specific forensic constraints (identity neutrality, raw_json audit trail)
