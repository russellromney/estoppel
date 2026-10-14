"""SAVE10: ten percent off the order, rounded down to the cent, for the coupon code SAVE10."""

from checkout.app.items import Cart
from checkout.app.pricing.types import Context, Rule
from checkout.core.api import Quote


def ten_percent_off(cart: Cart, quote: Quote, context: Context) -> tuple[int, ...] | None:
    if context.coupon != "SAVE10":
        return None
    totals = quote.line_totals()
    return tuple(-x for x in allocate(sum(totals) // 10, totals))


def allocate(amount: int, weights: tuple[int, ...]) -> tuple[int, ...]:
    """Split `amount` across lines in proportion to `weights`, exactly. Rounding remainders go to
    the lines with the largest fractions, the first line on a tie."""
    total = sum(weights)
    if total == 0:
        return (0,) * len(weights)
    shares = [amount * w // total for w in weights]
    by_fraction = sorted(range(len(weights)), key=lambda i: -(amount * weights[i] % total))
    for i in by_fraction[:amount - sum(shares)]:
        shares[i] += 1
    return tuple(shares)


SAVE10 = Rule(name="SAVE10", stage="order", apply=ten_percent_off)
