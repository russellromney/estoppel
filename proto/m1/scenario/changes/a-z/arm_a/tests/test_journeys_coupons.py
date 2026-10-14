"""Journeys for coupons."""

import pytest

from checkout import build
from world import Clock, Provider

pytestmark = pytest.mark.t4


def test_save10_takes_ten_percent_off_the_charge_and_shows_on_the_order():
    clock = Clock(0)
    provider = Provider(clock)
    svc = build(clock, provider)
    order = svc.place_order("r1", "alice", [("A", 1), ("C", 2)], coupon="SAVE10")
    assert order.ok and order.price == 1620
    assert svc.order(order.order_id).coupon == "SAVE10"
    assert svc.pay("r2", "alice", order.order_id).status == "paid"
    assert [a.amount for a in provider.applied.values()] == [1620]


def test_three_live_redemptions_then_used_up_until_one_expires():
    clock = Clock(0)
    svc = build(clock, Provider(clock))
    for n, customer in enumerate(("alice", "bob", "carol")):
        assert svc.place_order(f"r{n}", customer, [("A", 1)], coupon="SAVE10").ok
    assert svc.place_order("r4", "dave", [("A", 1)], coupon="SAVE10").reason == "coupon_used_up"
    clock.advance(15 * 60)
    svc.run_jobs()
    assert svc.place_order("r5", "dave", [("A", 1)], coupon="SAVE10").ok
