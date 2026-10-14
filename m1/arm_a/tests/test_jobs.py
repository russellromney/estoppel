import pytest

from checkout.config import HOLD_SECONDS, INITIAL_STOCK
from checkout.models import OrderStatus

pytestmark = pytest.mark.t2


def test_expiry_releases_stock(service, make_order, clock):
    kept = make_order(items=(("A", 2),))
    clock.advance(HOLD_SECONDS - 1)
    later = make_order(items=(("A", 1),))
    clock.advance(1)
    service.run_jobs()
    assert kept.status == OrderStatus.EXPIRED
    assert later.status == OrderStatus.RESERVED
    assert service.store.stock["A"] == INITIAL_STOCK - 1


def test_only_reserved_orders_expire(service, make_order, clock):
    orders = [make_order(status=s) for s in OrderStatus if s != OrderStatus.RESERVED]
    clock.advance(10 * HOLD_SECONDS)
    service.run_jobs()
    assert [o.status for o in orders] == [s for s in OrderStatus if s != OrderStatus.RESERVED]


@pytest.mark.parametrize("fault, final", [("lost_after", OrderStatus.PAID),
                                          ("lost_before", OrderStatus.PAID)])
def test_unknown_charge_is_reconciled_with_the_same_key(service, provider, make_order, rid,
                                                         fault, final):
    order = make_order()
    provider.faults.append(fault)
    service.pay(rid(), "c1", order.id)
    service.run_jobs()
    assert order.status == final
    assert [c.key for c in provider.charges(order.id)] == [f"charge-{order.id}-1"]


def test_charge_declined_at_the_provider_is_reconciled(service, provider, make_order, rid):
    order = make_order()
    provider.faults.append("lost_after")
    provider.declined.add(f"charge-{order.id}-1")  # provider declined, response lost
    service.pay(rid(), "c1", order.id)
    service.run_jobs()
    assert order.status == OrderStatus.RESERVED


def test_unknown_refund_is_reconciled(service, provider, make_order, rid):
    order = make_order(status=OrderStatus.PAID, charged_at=0)
    provider.faults.append("lost_before")
    service.refund(rid(), "c1", order.id)
    service.run_jobs()
    assert order.status == OrderStatus.REFUNDED and order.refunded == order.price


def test_jobs_during_an_in_flight_call_leave_it_alone(service, provider, make_order, rid, clock):
    order = make_order()

    def meanwhile(phase):
        clock.advance(HOLD_SECONDS)
        service.run_jobs()

    provider.during = meanwhile
    assert service.pay(rid(), "c1", order.id).ok
    assert order.status == OrderStatus.PAID
    assert len(provider.charges(order.id)) == 1


def test_retry_that_times_out_again_stays_unknown(service, provider, make_order, rid):
    order = make_order()
    provider.faults.extend(["lost_before", "lost_before"])
    service.pay(rid(), "c1", order.id)
    service.run_jobs()
    assert order.status == OrderStatus.PAYING
    service.run_jobs()
    assert order.status == OrderStatus.PAID
