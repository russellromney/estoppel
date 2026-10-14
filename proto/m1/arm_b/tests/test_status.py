import pytest
from conftest import order_fact

from checkout.app.status import status

pytestmark = pytest.mark.t1


@pytest.mark.parametrize("order, expected", [
    (order_fact(), "reserved"),
    (order_fact(open_charge=True), "paying"),
    (order_fact(charged_at=10), "paid"),
    (order_fact(charged_at=10, open_refund=True), "refunding"),
    (order_fact(charged_at=10, refunds=((1000,),)), "refunded"),
    (order_fact(lines=(("A", 2, 1000),), charged_at=10, refunds=((500,),)), "paid"),
    (order_fact(hold="released"), "expired"),
], ids=lambda x: x if isinstance(x, str) else "")
def test_status_is_derived_from_facts(order, expected):
    assert status(order) == expected
