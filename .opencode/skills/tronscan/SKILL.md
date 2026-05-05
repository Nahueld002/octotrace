---
name: tronscan
description: >
  Tronscan API patterns for TRC-20 token transfers and transaction info lookup.
  Trigger: When developing extraction logic for TRON (TRC20) transfers,
  querying transaction details by hash, or fetching USDT on TRON transfers.
metadata:
  author: octotrace
  version: "1.0"
  scope: [root, providers]
  auto_invoke:
    - "Developing extraction logic for TRON"
    - "Modifying providers/tronscan.py"
    - "Calling or modifying Tronscan API integration"
---

## When to Use

- Querying TRC-20 token transfers (USDT, USDC, TUSD, etc.) for a given address
- Fetching transaction details by transaction hash
- Implementing token transfer history for TRON forensic traceability
- Working with TRC20 `token_trc20/transfers` or `token_trc20/transfers-with-status` endpoints
- Auto-detecting address labels from `contractInfo` response metadata

## Critical Patterns

### 1. TRC20 Token Transfer List

**Endpoint**: `GET https://apilist.tronscanapi.com/api/token_trc20/transfers`

**Authentication**: Header `TRON-PRO-API-KEY: your_api_key`

**Key params**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `limit` | int | Items per page (default: `10`) |
| `start` | int | Start index (default: `0`) |
| `contract_address` | string | TRC20 contract address (e.g. `TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t` for USDT) |
| `start_timestamp` | int | Start time in milliseconds |
| `end_timestamp` | int | End time in milliseconds |
| `relatedAddress` | string | Account address (fetch ALL transfers involving this address) |
| `fromAddress` | string | Filter by sender |
| `toAddress` | string | Filter by recipient |
| `confirm` | bool | Confirmed only (default: `true`) |

**Response fields (`token_transfers[]`)**:

| Field | Type | Description |
|-------|------|-------------|
| `transaction_id` | string | Transaction hash |
| `block_ts` | int | Block timestamp (milliseconds) |
| `block` | int | Block number |
| `from_address` | string | Sender address |
| `to_address` | string | Recipient address |
| `contract_address` | string | TRC20 token contract address |
| `quant` | string | Token amount (raw, divide by `tokenDecimal`) |
| `confirmed` | bool | Confirmation status |
| `finalResult` | string | `"SUCCESS"` or error |
| `revert` | bool | Whether transaction reverted |
| `from_address_tag` | dict | Address tag as nested dict: `{"from_address_tag": "Binance-Hot 9", "from_address_tag_logo": ""}` |
| `to_address_tag` | dict | Address tag as nested dict: `{"to_address_tag": "..." | ""}` |
| `tokenInfo.tokenId` | string | Token contract address |
| `tokenInfo.tokenAbbr` | string | Token symbol (e.g. `"USDT"`) |
| `tokenInfo.tokenName` | string | Token name (e.g. `"Tether USD"`) |
| `tokenInfo.tokenDecimal` | int | Decimal places (`6` for USDT on TRON) |

**Amount conversion**: `actual_value = int(quant) / (10 ** tokenInfo.tokenDecimal)`

### ⚠️ Field Name Compatibility Pattern

The `token_trc20/transfers` endpoint uses **snake_case** field names, while the
`transaction-info` endpoint uses **camelCase**. When normalizing, use the
`get("new") or get("old")` pattern for forward/backward compatibility:

```python
txid = raw_data.get("transaction_id") or raw_data.get("hash", "")
from_addr = raw_data.get("from_address") or raw_data.get("fromAddress", "")
to_addr = raw_data.get("to_address") or raw_data.get("toAddress", "")
ts_ms = int(raw_data.get("block_ts") or raw_data.get("timestamp", 0))
block_number = int(raw_data.get("block") or raw_data.get("blockNumber", 0))
```

**Address tags** in `token_trc20/transfers` are **nested dicts**, not strings:

```python
raw_from_tag = raw_data.get("from_address_tag")
if isinstance(raw_from_tag, dict):
    tag_from = raw_from_tag.get("from_address_tag")
else:
    tag_from = raw_from_tag
```

Fallback: the response-level `contractInfo` map (keyed by address, each entry
has `tag1`, `tag1Url`, `name`, `vip`) is also available but the per-transfer
`from_address_tag` / `to_address_tag` fields are the preferred primary source.

### 2. Account TRC20 Transfer History (with direction filtering)

**Endpoint**: `GET https://apilist.tronscanapi.com/api/token_trc20/transfers-with-status`

**Key params**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `address` | string | Account address |
| `trc20Id` | string | TRC20 token contract address |
| `direction` | int | `0`=all, `1`=outgoing, `2`=incoming |
| `limit` | int | Items per page |
| `start` | int | Start index |
| `db_version` | int | `1` includes approval transfers, `0` excludes |
| `reverse` | bool | Sort by creation time |

**Response includes `data[]` with fields**: `amount`, `from`, `to`, `hash`, `block`, `block_timestamp`, `contract_address`, `direction`, `final_result`, `decimals`, `token_name`

### 3. Transaction Info by Hash

**Endpoint**: `GET https://apilist.tronscanapi.com/api/transaction-info?hash={tx_hash}`

**Key params**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `hash` | string | Transaction hash (required) |

**Response fields**:

| Field | Type | Description |
|-------|------|-------------|
| `hash` | string | Transaction hash |
| `block` | int | Block number |
| `timestamp` | int | Block timestamp (milliseconds) |
| `ownerAddress` | string | Sender |
| `toAddress` | string | Primary recipient / contract address |
| `contractType` | int | Contract type enum |
| `confirmed` | bool | Confirmation status |
| `revert` | bool | Whether transaction reverted |
| `contractRet` | string | `"SUCCESS"` or error |
| `contractData` | object | Raw contract call data |
| `srConfirmList` | array | SR (Super Representative) confirmation list with names |
| `cost` | object | Fee breakdown (`net_fee`, `energy_fee`, `fee`) |

### Address Labels from contractInfo

Both `token_trc20/transfers` and `transfers-with-status` responses include a `contractInfo` map. Each entry maps an address to:

| Field | Description |
|-------|-------------|
| `tag1` | Exchange or project name (e.g. `"Binance-Cold 2"`, `"jUSDJ Token"`) |
| `tag1Url` | Official URL |
| `name` | Entity name (e.g. `"CErc20Delegator"`) |
| `vip` | bool, VIP status |

Use `contractInfo` to auto-detect known exchanges in transfer partners.

## Code Examples

### Fetch USDT TRC20 transfers for an address

```python
import requests

TRONSCAN_API_KEY = "your_api_key"
HEADERS = {"TRON-PRO-API-KEY": TRONSCAN_API_KEY}
BASE_URL = "https://apilist.tronscanapi.com/api"

# USDT on TRON contract address
USDT_TRC20 = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"

params = {
    "limit": 20,
    "start": 0,
    "contract_address": USDT_TRC20,
    "relatedAddress": "TV6MuMXfmLbBqPZvBHdwFsDnQeVfnmiuSi",
    "confirm": True,
}

response = requests.get(
    f"{BASE_URL}/token_trc20/transfers",
    headers=HEADERS,
    params=params,
)
data = response.json()

# Extract address labels from contractInfo
labels = data.get("contractInfo", {})

for tx in data["token_transfers"]:
    decimals = tx["tokenInfo"]["tokenDecimal"]
    value = int(tx["quant"]) / 10 ** decimals
    from_label = labels.get(tx["from_address"], {}).get("tag1", "")
    to_label = labels.get(tx["to_address"], {}).get("tag1", "")
    print(f"{tx['transaction_id'][:16]}... "
          f"{value:,.2f} {tx['tokenInfo']['tokenAbbr']} "
          f"{tx['from_address'][:10]}...({from_label}) -> "
          f"{tx['to_address'][:10]}...({to_label})")
```

### Get transaction info by hash

```python
tx_hash = "3194a00c5cf427a931b908453588b2ca3f661dafa3860b76a6362d08b3b08583"
response = requests.get(
    f"{BASE_URL}/transaction-info",
    headers=HEADERS,
    params={"hash": tx_hash},
)
tx = response.json()

print(f"Block: {tx['block']}")
print(f"From: {tx['ownerAddress']} -> To: {tx['toAddress']}")
print(f"Status: {tx['contractRet']} (revert={tx['revert']})")
print(f"Fee: {tx['cost']['fee']} sun")
print(f"SR confirmations: {len(tx.get('srConfirmList', []))}")
```

### Fetch incoming USDT transfers with direction filter

```python
params = {
    "address": "TV6MuMXfmLbBqPZvBHdwFsDnQeVfnmiuSi",
    "trc20Id": USDT_TRC20,
    "direction": 2,   # incoming only
    "limit": 20,
    "start": 0,
}

response = requests.get(
    f"{BASE_URL}/token_trc20/transfers-with-status",
    headers=HEADERS,
    params=params,
)
for tx in response.json()["data"]:
    value = int(tx["amount"]) / 10 ** tx["decimals"]
    print(f"{tx['hash'][:16]}... {value:,.2f} USDT from {tx['from'][:10]}...")
```

## Commands

```bash
# Fetch TRC20 USDT transfers for an address
curl -s -H "TRON-PRO-API-KEY: your_api_key" \
  "https://apilist.tronscanapi.com/api/token_trc20/transfers?limit=5&contract_address=TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t&relatedAddress=TV6MuMXfmLbBqPZvBHdwFsDnQeVfnmiuSi" \
  | jq '.token_transfers[:3]'

# Get transaction info
curl -s -H "TRON-PRO-API-KEY: your_api_key" \
  "https://apilist.tronscanapi.com/api/transaction-info?hash=3194a00c5cf427a931b908453588b2ca3f661dafa3860b76a6362d08b3b08583" \
  | jq '{hash, block, ownerAddress, toAddress, contractRet, cost: .cost.fee}'

# Fetch incoming transfers only with direction=2
curl -s -H "TRON-PRO-API-KEY: your_api_key" \
  "https://apilist.tronscanapi.com/api/token_trc20/transfers-with-status?address=TV6MuMXfmLbBqPZvBHdwFsDnQeVfnmiuSi&trc20Id=TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t&direction=2&limit=3" \
  | jq '.data[:2]'
```

## Resources

- **Documentation**: See [blockchain-trace](../trace/skill.md) for TRON/EVM integration patterns
- **Documentation**: See [AGENTS.md](../../AGENTS.md) for project-specific forensic constraints (identity neutrality, raw_json audit trail)