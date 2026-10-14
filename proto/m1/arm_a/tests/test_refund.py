import pytest

from checkout.config import REFUND_WINDOW_SECONDS
from checkout.models import OrderStatus

pytestmark = pytest.mark.t2


@pytest.fixture
def paid(make_order):
    return lambda **kw: make_order(status=OrderStatus.PAID, charged_at=0, **kw)


def test_refunds_the_full_price_to_the_payer(service, provider, paid, rid):
    order = paid(items=(("B", 1),))
    r = service.refund(rid(), "c1", order.id)
    assert r.ok and r.status == "refunded"
    assert order.status == OrderStatus.REFUNDED and order.refunded == 2500
    [refund] = provider.refunds(order.id)
    assert (refund.amount, refund.customer, refund.key) == (2500, "c1", f"refund-{order.id}-1")


def test_foreign_order_is_not_found(service, paid, rid):
    order = paid(customer="c1")
    assert service.refund(rid(), "c2", order.id).reason == "not_found"


@pytest.mark.parametrize("status", [OrderStatus.RESERVED, OrderStatus.PAYING,
                                    OrderStatus.REFUNDING, OrderStatus.REFUNDED,
                                    OrderStatus.EXPIRED])
def test_only_paid_orders_are_refundable(service, make_order, rid, status):
    order = make_order(status=status)
    assert service.refund(rid(), "c1", order.id).reason == "not_refundable"


def test_window_boundary(service, paid, rid, clock):
    on_time, late = paid(), paid()
    clock.advance(REFUND_WINDOW_SECONDS)
    assert service.refund(rid(), "c1", on_time.id).ok
    clock.advance(1)
    assert service.refund(rid(), "c1", late.id).reason == "window_closed"


def test_declined_returns_to_paid(service, provider, paid, rid):
    order = paid()
    provider.faults.append("declined")
    assert service.refund(rid(), "c1", order.id).reason == "declined"
    assert order.status == OrderStatus.PAID and order.refunded == 0


def test_timeout_leaves_the_order_refunding(service, provider, paid, rid):
    order = paid()
    provider.faults.append("lost_after")
    r = service.refund(rid(), "c1", order.id)
    assert r.ok and r.status == "refunding"
    assert order.refunded == 0
