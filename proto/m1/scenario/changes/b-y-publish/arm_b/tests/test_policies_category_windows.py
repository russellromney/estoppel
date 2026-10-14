"""Refund windows by category, before the refund policy uses them."""

import pytest
from conftest import order_fact

from checkout.app.policies import refund_window

pytestmark = pytest.mark.t1

DAY = 86_400


@pytest.mark.parametrize("skus, window", [
    (("A",), 30 * DAY),
    (("B",), 30 * DAY),
    (("C",), 7 * DAY),
    (("D",), 15 * DAY),
    (("A", "C"), 7 * DAY),
    (("B", "D"), 15 * DAY),
])
def test_an_orders_window_is_the_shortest_of_its_categories(skus, window):
    order = order_fact(lines=tuple((sku, 1, 100) for sku in skus), charged_at=0)
    assert refund_window(order) == window
