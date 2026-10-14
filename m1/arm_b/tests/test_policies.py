import pytest
from conftest import order_fact

from checkout.app.config import HOLD_SECONDS, REFUND_WINDOW_SECONDS
from checkout.app.policies import hold_lapsed, hold_until, refund_window_open

pytestmark = pytest.mark.t1


def test_hold_lasts_the_configured_time():
    order = order_fact(opened_at=100, hold_until=hold_until(100))
    assert order.hold_until == 100 + HOLD_SECONDS
    assert not hold_lapsed(order, 100 + HOLD_SECONDS - 1)
    assert hold_lapsed(order, 100 + HOLD_SECONDS)


def test_refund_window_is_inclusive_and_runs_from_the_charge():
    order = order_fact(charged_at=50)
    assert refund_window_open(order, 50 + REFUND_WINDOW_SECONDS)
    assert not refund_window_open(order, 50 + REFUND_WINDOW_SECONDS + 1)


def test_no_window_without_a_charge():
    assert not refund_window_open(order_fact(), 0)
