import pytest

from checkout.config import HOLD_SECONDS, REFUND_WINDOW_SECONDS
from checkout.models import Order, OrderStatus
from checkout.policies import hold_lapsed, refund_window_open

pytestmark = pytest.mark.t1


def order(reserved_at=0, charged_at=None):
    return Order(id="o1", customer="c1", items=(("A", 1),), price=1000,
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
