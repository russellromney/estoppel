"""Journeys for refund windows by category."""

import pytest

pytestmark = pytest.mark.t4

DAY = 86_400


def test_food_has_a_shorter_window_than_general_goods(service, clock, rid):
    food = service.place_order(rid(), "alice", [("C", 1)])
    general = service.place_order(rid(), "alice", [("A", 1)])
    assert service.pay(rid(), "alice", food.order_id).status == "paid"
    assert service.pay(rid(), "alice", general.order_id).status == "paid"
    clock.advance(8 * DAY)
    assert service.refund(rid(), "alice", food.order_id).reason == "window_closed"
    assert service.refund(rid(), "alice", general.order_id).status == "refunded"


def test_a_mixed_order_uses_its_shortest_window(service, clock, rid):
    order = service.place_order(rid(), "alice", [("A", 1), ("D", 1)])
    assert service.pay(rid(), "alice", order.order_id).status == "paid"
    clock.advance(15 * DAY)
    assert service.refund(rid(), "alice", order.order_id).status == "refunded"
