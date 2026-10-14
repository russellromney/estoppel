import pytest

pytestmark = pytest.mark.feature("b2g1")


@pytest.mark.parametrize("items, price", [
    ([("A", 1)], 1000),
    ([("A", 2)], 2000),
    ([("A", 3)], 2000),
    ([("A", 4)], 3000),
    ([("A", 6)], 4000),
    ([("A", 2), ("A", 1)], 2000),
    ([("A", 3), ("C", 3)], 2000 + 800),
    ([("D", 2), ("B", 1)], 2 * 9900 + 2500),
])
def test_every_third_unit_of_a_sku_is_free(svc, rid, items, price):
    r = svc.place_order(rid(), "c1", items)
    assert r.ok and r.price == price
    assert svc.order(r.order_id).price == price


def test_free_units_are_still_reserved(svc, rid):
    svc.place_order(rid(), "c1", [("A", 3)])
    assert svc.stock()["A"] == 3
