"""Business rules about time: reservation holds and the refund window."""

from checkout.app.config import HOLD_SECONDS, REFUND_WINDOW_SECONDS
from checkout.core.api import Order


def hold_until(now: int) -> int:
    return now + HOLD_SECONDS


def hold_lapsed(order: Order, now: int) -> bool:
    return now >= order.hold_until


def refund_window_open(order: Order, now: int) -> bool:
    return order.charge is not None and now - order.charge.at <= REFUND_WINDOW_SECONDS
