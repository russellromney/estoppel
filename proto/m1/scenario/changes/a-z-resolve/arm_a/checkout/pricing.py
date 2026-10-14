"""Order pricing."""

from collections.abc import Mapping


def order_total(lines: Mapping[str, int], prices: Mapping[str, int]) -> int:
    """Total in cents for combined order lines (sku -> quantity).

    Buy two, get one free: every third unit of a SKU is free.
    """
    return sum(prices[sku] * (qty - qty // 3) for sku, qty in lines.items())


def apply_coupon(total: int, coupon: str | None) -> int:
    """SAVE10 takes ten percent off the total, rounded down to the cent."""
    return total - total // 10 if coupon == "SAVE10" else total
