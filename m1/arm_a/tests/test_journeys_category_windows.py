"""Journeys for refund windows by category."""

import pytest

from checkout import build
from world import Clock, Provider


pytestmark = pytest.mark.t4

DAY = 86_400


def test_food_has_a_shorter_window_than_general_goods():
    clock = Clock(0)
    svc = build(clock, Provider(clock))
    food = svc.place_order("r1", "alice", [("C", 1)])
    general = svc.place_order("r2", "alice", [("A", 1)])
    assert svc.pay("r3", "alice", food.order_id).status == "paid"
    assert svc.pay("r4", "alice", general.order_id).status == "paid"
    clock.advance(8 * DAY)
    assert svc.refund("r5", "alice", food.order_id).reason == "window_closed"
    assert svc.refund("r6", "alice", general.order_id).status == "refunded"


def test_a_mixed_order_uses_its_shortest_window():
    clock = Clock(0)
    svc = build(clock, Provider(clock))
    order = svc.place_order("r1", "alice", [("A", 1), ("D", 1)])
    assert svc.pay("r2", "alice", order.order_id).status == "paid"
    clock.advance(15 * DAY)
    assert svc.refund("r3", "alice", order.order_id).status == "refunded"
