import pytest

from oracle import check_safety, expected_price
from spec import INITIAL_STOCK, PRICES


@pytest.mark.parametrize("items", [
    [],
    [("Z", 1)],
    [("A", 0)],
    [("A", -1)],
    [("A", True)],
    [("A", 1.0)],
    [("A", "1")],
    [("A",)],
    [("A", 1, 2)],
    [("A", 1), ("Z", 1)],
])
def test_bad_items_are_rejected_without_change(svc, rid, items):
    r = svc.place_order(rid(), "c1", items)
    assert (r.ok, r.reason) == (False, "bad_items")
    assert svc.orders() == []
    assert svc.stock() == {sku: INITIAL_STOCK for sku in PRICES}


def test_reserves_stock_and_prices_the_order(svc, rid, features):
    items = [("B", 1), ("A", 2)]
    r = svc.place_order(rid(), "c1", items)
    assert r.ok and r.status == "reserved" and r.order_id
    assert r.price == expected_price(items, features)
    o = svc.order(r.order_id)
    assert o.customer == "c1"
    assert o.items == (("A", 2), ("B", 1))
    assert o.price == r.price
    assert o.status == "reserved"
    assert o.reserved_at == 0 and o.charged_at is None and o.refunded == 0
    assert svc.stock()["A"] == INITIAL_STOCK - 2
    assert svc.stock()["B"] == INITIAL_STOCK - 1


def test_lines_for_the_same_sku_are_combined(svc, rid, features):
    items = [("B", 1), ("A", 2), ("A", 1)]
    r = svc.place_order(rid(), "c1", items)
    assert svc.order(r.order_id).items == (("A", 3), ("B", 1))
    assert r.price == expected_price(items, features)


def test_out_of_stock_is_all_or_nothing(svc, rid):
    r = svc.place_order(rid(), "c1", [("A", 6), ("B", 7)])
    assert (r.ok, r.reason) == (False, "out_of_stock")
    assert svc.stock() == {sku: INITIAL_STOCK for sku in PRICES}
    assert svc.orders() == []


def test_combined_lines_are_checked_against_stock(svc, rid):
    r = svc.place_order(rid(), "c1", [("A", 3), ("A", 4)])
    assert (r.ok, r.reason) == (False, "out_of_stock")


def test_last_units_can_be_reserved_and_then_none_remain(svc, rid):
    assert svc.place_order(rid(), "c1", [("C", 6)]).ok
    assert svc.stock()["C"] == 0
    r = svc.place_order(rid(), "c2", [("C", 1)])
    assert (r.ok, r.reason) == (False, "out_of_stock")


def test_repeated_request_returns_the_stored_response(svc, rid, provider, features):
    req = rid()
    first = svc.place_order(req, "c1", [("A", 1)])
    again = svc.place_order(req, "c1", [("A", 1)])
    assert again == first
    assert len(svc.orders()) == 1
    assert svc.stock()["A"] == INITIAL_STOCK - 1
    assert check_safety(svc, provider, features) == []


def test_repeated_rejection_is_also_stored(svc, rid):
    req = rid()
    first = svc.place_order(req, "c1", [("A", 7)])
    assert svc.place_order(req, "c1", [("A", 7)]) == first


@pytest.mark.without_feature("b2g1")
def test_base_pricing_is_list_price_times_quantity(svc, rid):
    r = svc.place_order(rid(), "c1", [("A", 3), ("D", 1)])
    assert r.price == 3 * 1000 + 9900
