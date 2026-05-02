---
name: python-forensics
description: >
  Python best practices for forensic tooling: decimal precision, type hints, and thesis-grade docstrings.
  Trigger: When writing or modifying any Python file in this project.
license: Apache-2.0
metadata:
  author: octotrace
  version: "1.0"
  scope: [root, providers, services, web]
  auto_invoke:
    - "Writing or modifying any Python function"
    - "Handling amounts, balances, or transaction values"
    - "Adding type hints or docstrings"
---

## When to Use

- Writing any new Python module or function
- Handling amounts, balances, or transaction values
- Adding type hints or documentation to existing code
- Creating functions that process financial data

## Critical Patterns

### Arithmetic Precision (MANDATORY)

```python
# WRONG - NEVER use float for money
balance = 100.50  # ❌

# CORRECT - Always use Decimal
from decimal import Decimal, ROUND_HALF_UP
balance = Decimal("100.50")  # ✓
```

| Operation | Use | Avoid |
|------------|-----|-------|
| USDT amounts | `Decimal` | `float`, `int` |
| Balance calculations | `Decimal` | `float` |
| API response parsing | `Decimal(str(value))` | `float(value)` |

### Type Hints (MANDATORY)

```python
from decimal import Decimal
from typing import Optional

def calculate_net_amount(gross: Decimal, fee_percent: Decimal) -> Decimal:
    """Calculate net amount after fee deduction."""
    fee = (gross * fee_percent) / Decimal("100")
    return gross - fee
```

### Docstrings (Thesis Standard)

Every function requires:
- Purpose statement
- Parameter descriptions with types
- Return type
- Potential exceptions

```python
def normalize_hash(raw: str, chain: str) -> str:
    """Normalize a blockchain transaction hash to lowercase hex.
    
    Args:
        raw: The raw hash string from API response.
        chain: The blockchain network ('tron' or 'ethereum').
    
    Returns:
        Normalized lowercase hex string without 0x prefix.
    
    Raises:
        ValueError: If chain is not supported.
    """
```

## Code Examples

### Module Header

```python
"""Cryptotrace data models for USDT transfer tracking.

This module defines the core data structures used across the forensic
pipeline for storing and processing TRC20/ERC20 transfer records.
"""
```

### Decimal Operations

```python
from decimal import Decimal, ROUND_HALF_UP

def quantize_usdt(amount: Decimal) -> Decimal:
    """Quantize to 6 decimal places for USDT precision."""
    return amount.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)

# Safe arithmetic
total = sum((Decimal("10.5"), Decimal("5.25")), Decimal("0"))
```

### Database Field Handling

```python
from decimal import Decimal

def parse_amount(value: str | int | float) -> Decimal:
    """Parse API amount field to Decimal."""
    return Decimal(str(value))
```

## Commands

```bash
# Type checking
mypy src/

# Linting
ruff check src/

# Format
ruff format src/

# All checks
mypy src/ && ruff check src/ && ruff format src/
```

## Resources

- **Decimal docs**: https://docs.python.org/3/library/decimal.html
- **typing module**: https://docs.python.org/3/library/typing.html