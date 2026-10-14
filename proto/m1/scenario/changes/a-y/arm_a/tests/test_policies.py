import pytest

from checkout.config import HOLD_SECONDS, REFUND_WINDOW_SECONDS
from checkout.models import Order, OrderStatus
from checkout.policies import hold_lapsed, refund_window_open

pytestmark = pytest.mark.t1


DAY = 86_400


def order(reserved_at=0, charged_at=None, items=(("A", 1),)):
    return Order(id="o1", customer="c1", items=items, price=1000,
                 status=OrderStatus.PAID, reserved_at=reserved_at, charged_at=charged_at)


@pytest.mark.parametrize("now, lapsed", [(0, False), (HOLD_SECONDS - 1, False),
                                         (HOLD_SECONDS, True), (HOLD_SECONDS + 1, True)])
def test_hold_lapses_at_the_hold(now, lapsed):
    assert hold_lapsed(order(reserved_at=0), now) is lapsed


@pytest.mark.parametrize("since_charge, open_", [(0, True), (REFUND_WINDOW_SECONDS, True),
                                                 (REFUND_WINDOW_SECONDS + 1, False)])
def test_refund_window_is_inclusive(since_charge, open_):
    assert refund_window_open(order(charged_at=100), 100 + since_charge) is open_


def test_refund_window_needs_a_charge():
    assert not refund_window_open(order(charged_at=None), 0)


@pytest.mark.parametrize("items, window", [
    ((("A", 1),), 30 * DAY),
    ((("B", 2),), 30 * DAY),
    ((("C", 1),), 7 * DAY),
    ((("D", 1),), 15 * DAY),
    ((("A", 1), ("C", 1)), 7 * DAY),
    ((("B", 1), ("D", 1)), 15 * DAY),
])
def test_an_orders_window_is_the_shortest_of_its_categories(items, window):
    o = order(charged_at=0, items=items)
    assert refund_window_open(o, window) and not refund_window_open(o, window + 1)
