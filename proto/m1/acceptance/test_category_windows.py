import pytest

from oracle import settle
from spec import CATEGORIES, CATEGORY_WINDOWS

pytestmark = pytest.mark.feature("category_windows")


def paid_order(svc, rid, items, customer="c1"):
    r = svc.place_order(rid(), customer, list(items))
    assert svc.pay(rid(), customer, r.order_id).ok
    settle(svc)
    assert svc.order(r.order_id).status == "paid"
    return r.order_id


@pytest.mark.parametrize("sku", sorted(CATEGORIES))
def test_refund_at_exactly_the_category_window_is_allowed(svc, rid, clock, sku):
    oid = paid_order(svc, rid, [(sku, 1)])
    clock.advance(CATEGORY_WINDOWS[CATEGORIES[sku]])
    assert svc.refund(rid(), "c1", oid).ok
    settle(svc)
    assert svc.order(oid).status == "refunded"


@pytest.mark.parametrize("sku", sorted(CATEGORIES))
def test_refund_after_the_category_window_is_rejected(svc, rid, provider, clock, sku):
    oid = paid_order(svc, rid, [(sku, 1)])
    clock.advance(CATEGORY_WINDOWS[CATEGORIES[sku]] + 1)
    r = svc.refund(rid(), "c1", oid)
    assert (r.ok, r.reason) == (False, "window_closed")
    assert provider.refunds(oid) == []


def test_a_mixed_order_uses_the_shortest_window(svc, rid, provider, clock):
    oid = paid_order(svc, rid, [("A", 1), ("C", 1)])
    clock.advance(CATEGORY_WINDOWS["food"] + 1)
    r = svc.refund(rid(), "c1", oid)
    assert (r.ok, r.reason) == (False, "window_closed")
    assert provider.refunds(oid) == []


def test_a_mixed_order_is_refundable_inside_the_shortest_window(svc, rid, clock):
    oid = paid_order(svc, rid, [("D", 1), ("B", 2)])
    clock.advance(CATEGORY_WINDOWS["electronics"])
    assert svc.refund(rid(), "c1", oid).ok
