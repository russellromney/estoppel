"""Business rules about time: reservation holds and the refund window."""

from checkout.config import HOLD_SECONDS, REFUND_WINDOW_SECONDS
from checkout.models import Order


def hold_lapsed(order: Order, now: int) -> bool:
    return now - order.reserved_at >= HOLD_SECONDS


def refund_window_open(order: Order, now: int) -> bool:
    return order.charged_at is not None and now - order.charged_at <= REFUND_WINDOW_SECONDS
