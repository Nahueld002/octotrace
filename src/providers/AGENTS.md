# Sub-agent: Providers

> **Skills Reference**:
> - [etherscan-api](../../../.opencode/skills/etherscan/SKILL.md)
> - [tronscan-api](../../../.opencode/skills/tronscan/SKILL.md)
> - [blockchain-trace](../../../.opencode/skills/trace/SKILL.md)
> - [python-forensics](../../../.opencode/skills/python-forensics/SKILL.md)

### Auto-invoke Skills

When performing these actions, ALWAYS invoke the corresponding skill FIRST:

| Action | Skill |
|--------|-------|
| Adding type hints or docstrings | `python-forensics` |
| Calling or modifying Etherscan API integration | `etherscan` |
| Calling or modifying Tronscan API integration | `tronscan` |
| Classifying input as address or TXID | `blockchain-trace` |
| Detecting blockchain network from input format | `blockchain-trace` |
| Developing extraction logic for Ethereum | `etherscan` |
| Developing extraction logic for TRON | `tronscan` |
| Handling amounts, balances, or transaction values | `python-forensics` |
| Interacting with data/input/ or seeds | `sqlite-forensic` |
| Modifying database schema or SQLite models | `sqlite-forensic` |
| Modifying providers/etherscan.py | `etherscan` |
| Modifying providers/tronscan.py | `tronscan` |
| Normalizing addresses or transaction hashes | `blockchain-trace` |
| Querying or writing to case.sqlite | `sqlite-forensic` |
| Writing or modifying any Python function | `python-forensics` |

---

## Responsibility

API adapters for Etherscan and Tronscan. Fetches raw transfer data
and normalizes it to internal Pydantic models.

## Critical Rules

- Never use float for amounts — always Decimal
- Always store raw_json from API response
- Never modify data/input/ seeds
- Rate limit: respect API throttling (Etherscan 5/s, Tronscan varies)
