"""Buy two, get one free: every third unit of a SKU is free."""

from checkout.app.items import Cart
from checkout.app.pricing.types import Context, Rule
from checkout.core.api import Quote


def every_third_unit_free(cart: Cart, quote: Quote, context: Context) -> tuple[int, ...]:
    return tuple(-(line.qty // 3) * line.unit_price for line in quote.lines)


B2G1 = Rule(name="b2g1", stage="item", apply=every_third_unit_free)
