"""Order pricing."""

from collections.abc import Mapping


def order_total(lines: Mapping[str, int], prices: Mapping[str, int]) -> int:
    """Total in cents for combined order lines (sku -> quantity).

    Buy two, get one free: every third unit of a SKU is free.
    """
    return sum(prices[sku] * (qty - qty // 3) for sku, qty in lines.items())
