"""Journeys for buy two, get one free."""

import pytest

pytestmark = pytest.mark.t4


def test_the_third_unit_is_free_and_the_charge_and_refund_match(service, provider, rid):
    order = service.place_order(rid(), "alice", [("A", 3), ("C", 1)])
    assert order.ok and order.price == 2 * 1000 + 400
    assert service.stock()["A"] == 3
    assert service.pay(rid(), "alice", order.order_id).status == "paid"
    assert service.refund(rid(), "alice", order.order_id).status == "refunded"
    amounts = sorted((a.kind, a.amount) for a in provider.applied.values())
    assert amounts == [("charge", 2400), ("refund", 2400)]
