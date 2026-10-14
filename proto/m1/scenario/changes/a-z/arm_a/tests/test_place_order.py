import pytest

from checkout.config import COUPONS, HOLD_SECONDS, INITIAL_STOCK
from checkout.models import OrderStatus

pytestmark = pytest.mark.t2


def test_reserves_stock_and_creates_the_order(service, rid, clock):
    clock.advance(5)
    r = service.place_order(rid(), "c1", [("B", 1), ("A", 2)])
    assert r.ok and r.status == "reserved" and r.price == 4500
    order = service.store.get_order(r.order_id)
    assert order.items == (("A", 2), ("B", 1))
    assert order.status == OrderStatus.RESERVED and order.reserved_at == 5
    assert service.store.stock["A"] == INITIAL_STOCK - 2
    assert service.store.stock["B"] == INITIAL_STOCK - 1


def test_out_of_stock_reserves_nothing(service, rid):
    r = service.place_order(rid(), "c1", [("A", 1), ("B", INITIAL_STOCK + 1)])
    assert (r.ok, r.reason) == (False, "out_of_stock")
    assert service.store.orders == {}
    assert service.store.stock["A"] == INITIAL_STOCK


def test_bad_items_are_rejected(service, rid):
    r = service.place_order(rid(), "c1", [("A", 0)])
    assert (r.ok, r.reason) == (False, "bad_items")
    assert service.store.orders == {}


def test_repeat_returns_the_stored_response(service, rid):
    req = rid()
    first = service.place_order(req, "c1", [("A", 1)])
    assert service.place_order(req, "c1", [("A", 1)]) == first
    assert len(service.store.orders) == 1


def test_handler_failure_releases_the_request_id(service, rid, monkeypatch):
    req = rid()
    monkeypatch.setattr(service, "_place_order", lambda *a: 1 / 0)
    with pytest.raises(ZeroDivisionError):
        service.place_order(req, "c1", [("A", 1)])
    monkeypatch.undo()
    assert service.place_order(req, "c1", [("A", 1)]).ok


def test_a_coupon_order_is_discounted_and_records_its_coupon(service, rid):
    r = service.place_order(rid(), "c1", [("A", 1), ("C", 2)], coupon="SAVE10")
    assert r.ok and r.price == 1620
    assert service.store.get_order(r.order_id).coupon == "SAVE10"


@pytest.mark.parametrize("items, coupon, reason", [
    ([], "nope", "bad_items"),
    ([("A", INITIAL_STOCK + 1)], "nope", "bad_coupon"),
    ([("A", 1)], "save10", "bad_coupon"),
])
def test_coupon_rejections_come_in_order(service, rid, items, coupon, reason):
    r = service.place_order(rid(), "c1", items, coupon=coupon)
    assert (r.ok, r.reason) == (False, reason)
    assert service.store.orders == {}


def test_redemptions_run_out_and_expiry_returns_them(service, rid, clock):
    for _ in range(COUPONS["SAVE10"]):
        assert service.place_order(rid(), "c1", [("A", 1)], coupon="SAVE10").ok
    r = service.place_order(rid(), "c2", [("A", INITIAL_STOCK)], coupon="SAVE10")
    assert r.reason == "out_of_stock"
    r = service.place_order(rid(), "c2", [("B", 1)], coupon="SAVE10")
    assert r.reason == "coupon_used_up" and len(service.store.orders) == COUPONS["SAVE10"]
    clock.advance(HOLD_SECONDS)
    service.run_jobs()
    assert service.place_order(rid(), "c2", [("B", 1)], coupon="SAVE10").ok
