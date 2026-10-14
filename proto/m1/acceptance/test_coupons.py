"""Coupons. These tests do not decide how a coupon combines with b2g1 or what a refund
does to a redemption: carts have at most 2 units of a SKU, and no coupon order is refunded."""

import pytest

from oracle import check_safety, expected_price, settle
from spec import COUPON, COUPON_REDEMPTIONS, HOLD, INITIAL_STOCK, PRICES

pytestmark = pytest.mark.feature("coupons")


def redeem(svc, rid, customer="c1", items=(("A", 1),)):
    r = svc.place_order(rid(), customer, list(items), coupon=COUPON)
    assert r.ok, r
    return r.order_id


@pytest.mark.parametrize("items, price", [
    ([("A", 1)], 900),
    ([("A", 1), ("C", 2)], 1620),
    ([("B", 2)], 4500),
    ([("D", 1)], 8910),
])
def test_save10_takes_ten_percent_off(svc, rid, features, items, price):
    r = svc.place_order(rid(), "c1", items, coupon=COUPON)
    assert r.ok and r.price == price == expected_price(items, features, COUPON)
    o = svc.order(r.order_id)
    assert o.price == price and o.coupon == COUPON


def test_no_coupon_means_no_discount(svc, rid):
    r = svc.place_order(rid(), "c1", [("A", 1)], coupon=None)
    assert r.ok and r.price == PRICES["A"]
    assert svc.order(r.order_id).coupon is None


@pytest.mark.parametrize("code", ["save10", "SAVE20", "", " SAVE10", 10, ["SAVE10"]])
def test_unknown_codes_are_rejected_without_change(svc, rid, code):
    r = svc.place_order(rid(), "c1", [("A", 1)], coupon=code)
    assert (r.ok, r.reason) == (False, "bad_coupon")
    assert svc.orders() == []
    assert svc.stock() == {sku: INITIAL_STOCK for sku in PRICES}


def test_bad_items_are_reported_before_a_bad_coupon(svc, rid):
    r = svc.place_order(rid(), "c1", [], coupon="nope")
    assert (r.ok, r.reason) == (False, "bad_items")


def test_a_bad_coupon_is_reported_before_out_of_stock(svc, rid):
    r = svc.place_order(rid(), "c1", [("A", INITIAL_STOCK + 1)], coupon="nope")
    assert (r.ok, r.reason) == (False, "bad_coupon")


def test_out_of_stock_is_reported_before_coupon_used_up(svc, rid):
    for _ in range(COUPON_REDEMPTIONS):
        redeem(svc, rid, items=[("B", 1)])
    r = svc.place_order(rid(), "c1", [("A", INITIAL_STOCK + 1)], coupon=COUPON)
    assert (r.ok, r.reason) == (False, "out_of_stock")


def test_redemptions_are_shared_across_customers(svc, rid, provider, features):
    for customer in ("c1", "c2", "c3"):
        redeem(svc, rid, customer)
    stock, orders = svc.stock(), svc.orders()
    r = svc.place_order(rid(), "c4", [("A", 1)], coupon=COUPON)
    assert (r.ok, r.reason) == (False, "coupon_used_up")
    assert svc.stock() == stock and svc.orders() == orders
    assert svc.place_order(rid(), "c4", [("A", 1)]).ok
    assert check_safety(svc, provider, features) == []


def test_a_rejected_order_does_not_redeem(svc, rid):
    r = svc.place_order(rid(), "c1", [("A", INITIAL_STOCK + 1)], coupon=COUPON)
    assert r.reason == "out_of_stock"
    for _ in range(COUPON_REDEMPTIONS):
        redeem(svc, rid)


def test_expiry_returns_the_redemption(svc, rid, clock, provider, features):
    first = [redeem(svc, rid) for _ in range(COUPON_REDEMPTIONS)]
    clock.advance(HOLD)
    svc.run_jobs()
    assert {svc.order(oid).status for oid in first} == {"expired"}
    redeem(svc, rid, "c2")
    assert check_safety(svc, provider, features) == []


def test_a_paid_order_keeps_its_redemption(svc, rid, clock):
    paid, *others = [redeem(svc, rid) for _ in range(COUPON_REDEMPTIONS)]
    assert svc.pay(rid(), "c1", paid).ok
    settle(svc)
    clock.advance(HOLD)
    svc.run_jobs()
    assert svc.order(paid).status == "paid"
    assert {svc.order(oid).status for oid in others} == {"expired"}
    for _ in range(COUPON_REDEMPTIONS - 1):
        redeem(svc, rid, "c2")
    r = svc.place_order(rid(), "c2", [("A", 1)], coupon=COUPON)
    assert (r.ok, r.reason) == (False, "coupon_used_up")


def test_a_declined_order_keeps_its_redemption_until_it_expires(svc, rid, provider, clock):
    orders = [redeem(svc, rid) for _ in range(COUPON_REDEMPTIONS)]
    provider.faults.append("declined")
    svc.pay(rid(), "c1", orders[0])
    settle(svc)
    assert svc.order(orders[0]).status == "reserved"
    r = svc.place_order(rid(), "c2", [("A", 1)], coupon=COUPON)
    assert (r.ok, r.reason) == (False, "coupon_used_up")
    clock.advance(HOLD)
    svc.run_jobs()
    redeem(svc, rid, "c2")


def test_a_repeated_request_redeems_once(svc, rid):
    req = rid()
    first = svc.place_order(req, "c1", [("A", 1)], coupon=COUPON)
    assert svc.place_order(req, "c1", [("A", 1)], coupon=COUPON) == first
    for _ in range(COUPON_REDEMPTIONS - 1):
        redeem(svc, rid)
    r = svc.place_order(rid(), "c1", [("A", 1)], coupon=COUPON)
    assert (r.ok, r.reason) == (False, "coupon_used_up")


def test_orders_placed_during_a_payment_share_the_limit(svc, rid, provider, features):
    paying = redeem(svc, rid)
    during = []

    def place_more(phase):
        if phase == "before" and not during:
            for customer in ("c2", "c3", "c4"):
                during.append(svc.place_order(rid(), customer, [("B", 1)], coupon=COUPON))
            assert check_safety(svc, provider, features) == []

    provider.during = place_more
    svc.pay(rid(), "c1", paying)
    provider.during = None
    settle(svc)
    assert [r.ok for r in during] == [True, True, False]
    assert during[2].reason == "coupon_used_up"
    assert check_safety(svc, provider, features) == []
