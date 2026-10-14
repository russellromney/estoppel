"""Order pricing."""

from collections.abc import Mapping


def order_total(lines: Mapping[str, int], prices: Mapping[str, int]) -> int:
    """Total in cents for combined order lines (sku -> quantity)."""
    return sum(prices[sku] * qty for sku, qty in lines.items())
