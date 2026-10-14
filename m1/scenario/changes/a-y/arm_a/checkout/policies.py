"""Business rules about time: reservation holds and the refund window."""

from checkout.config import CATEGORIES, CATEGORY_REFUND_WINDOWS, HOLD_SECONDS
from checkout.models import Order


def hold_lapsed(order: Order, now: int) -> bool:
    return now - order.reserved_at >= HOLD_SECONDS


def refund_window(order: Order) -> int:
    """The shortest refund window among the categories of the order's items."""
    return min(CATEGORY_REFUND_WINDOWS[CATEGORIES[sku]] for sku, _ in order.items)


def refund_window_open(order: Order, now: int) -> bool:
    return order.charged_at is not None and now - order.charged_at <= refund_window(order)
