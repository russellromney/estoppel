import pytest

from checkout.config import HOLD_SECONDS
from checkout.models import OrderStatus

pytestmark = pytest.mark.t2


def test_charges_the_order_price(service, provider, make_order, rid, clock):
    order = make_order(items=(("A", 2),), price=1500)
    clock.advance(7)
    r = service.pay(rid(), "c1", order.id)
    assert r.ok and r.status == "paid"
    assert order.status == OrderStatus.PAID and order.charged_at == 7
    [charge] = provider.charges(order.id)
    assert (charge.amount, charge.customer, charge.key) == (1500, "c1", f"charge-{order.id}-1")


def test_unknown_or_foreign_order_is_not_found(service, provider, make_order, rid):
    order = make_order(customer="c1")
    assert service.pay(rid(), "c2", order.id).reason == "not_found"
    assert service.pay(rid(), "c1", "nope").reason == "not_found"
    assert provider.calls == 0


def test_lapsed_hold_is_expired_before_the_job_runs(service, provider, make_order, rid, clock):
    order = make_order()
    clock.advance(HOLD_SECONDS)
    assert service.pay(rid(), "c1", order.id).reason == "expired"
    assert order.status == OrderStatus.RESERVED
    assert provider.calls == 0


def test_expired_order_is_expired(service, make_order, rid):
    order = make_order(status=OrderStatus.EXPIRED)
    assert service.pay(rid(), "c1", order.id).reason == "expired"


@pytest.mark.parametrize("status", [OrderStatus.PAYING, OrderStatus.PAID,
                                    OrderStatus.REFUNDING, OrderStatus.REFUNDED])
def test_other_statuses_are_not_payable(service, make_order, rid, status):
    order = make_order(status=status)
    assert service.pay(rid(), "c1", order.id).reason == "not_payable"


def test_declined_returns_to_reserved_and_retry_uses_a_new_key(service, provider, make_order, rid):
    order = make_order()
    provider.faults.append("declined")
    assert service.pay(rid(), "c1", order.id).reason == "declined"
    assert order.status == OrderStatus.RESERVED
    assert service.pay(rid(), "c1", order.id).ok
    assert [c.key for c in provider.charges(order.id)] == [f"charge-{order.id}-2"]


@pytest.mark.parametrize("fault", ["lost_before", "lost_after"])
def test_timeout_leaves_the_order_paying(service, provider, make_order, rid, fault):
    order = make_order()
    provider.faults.append(fault)
    r = service.pay(rid(), "c1", order.id)
    assert r.ok and r.status == "paying"
    assert order.status == OrderStatus.PAYING
    [payment] = service.store.payments_for(order.id, "charge")
    assert payment.state == "unknown"


def test_charged_at_comes_from_the_provider(service, provider, make_order, rid, clock):
    order = make_order()
    provider.during = lambda phase: clock.advance(100) if phase == "after" else None
    service.pay(rid(), "c1", order.id)
    assert order.charged_at == 0 and clock.now == 100


def test_repeat_in_flight_is_in_progress(service, provider, make_order, rid):
    order = make_order()
    req = rid()
    seen = []
    provider.during = lambda phase: seen.append(service.pay(req, "c1", order.id))
    first = service.pay(req, "c1", order.id)
    assert {r.reason for r in seen} == {"in_progress"}
    assert service.pay(req, "c1", order.id) == first
    assert len(provider.charges(order.id)) == 1
