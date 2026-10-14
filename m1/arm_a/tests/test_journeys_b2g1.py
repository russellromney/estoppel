"""Journeys for buy two, get one free."""

import pytest

from checkout import build
from world import Clock, Provider

pytestmark = pytest.mark.t4


def test_the_third_unit_is_free_and_the_charge_and_refund_match():
    clock = Clock(0)
    provider = Provider(clock)
    svc = build(clock, provider)
    order = svc.place_order("r1", "alice", [("A", 3), ("C", 1)])
    assert order.ok and order.price == 2 * 1000 + 400
    assert svc.stock()["A"] == 3
    assert svc.pay("r2", "alice", order.order_id).status == "paid"
    assert svc.refund("r3", "alice", order.order_id).status == "refunded"
    amounts = sorted((a.kind, a.amount) for a in provider.applied.values())
    assert amounts == [("charge", 2400), ("refund", 2400)]
