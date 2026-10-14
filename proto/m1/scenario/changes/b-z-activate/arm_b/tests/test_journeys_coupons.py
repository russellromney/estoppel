"""Journeys for coupons."""

import pytest

pytestmark = pytest.mark.t4


def test_save10_takes_ten_percent_off_the_charge_and_shows_on_the_order(service, provider, rid):
    order = service.place_order(rid(), "alice", [("A", 1), ("C", 2)], coupon="SAVE10")
    assert order.ok and order.price == 1620
    assert service.order(order.order_id).coupon == "SAVE10"
    assert service.pay(rid(), "alice", order.order_id).status == "paid"
    assert [a.amount for a in provider.applied.values()] == [1620]


def test_three_live_redemptions_then_used_up_until_one_expires(service, clock, rid):
    for customer in ("alice", "bob", "carol"):
        assert service.place_order(rid(), customer, [("A", 1)], coupon="SAVE10").ok
    assert service.place_order(rid(), "dave", [("A", 1)], coupon="SAVE10").reason == "coupon_used_up"
    clock.advance(15 * 60)
    service.run_jobs()
    assert service.place_order(rid(), "dave", [("A", 1)], coupon="SAVE10").ok
