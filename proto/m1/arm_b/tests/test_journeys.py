"""End-to-end journeys through the public interface only."""

import pytest

from checkout import build
from world import Clock, Provider

pytestmark = pytest.mark.t4

DAY = 86_400


@pytest.fixture
def world():
    clock = Clock(0)
    provider = Provider(clock)
    return clock, provider, build(clock, provider)


def test_buy_pay_and_refund(world):
    clock, provider, svc = world
    order = svc.place_order("r1", "alice", [("A", 2), ("C", 1)])
    assert order.ok and order.price == 2400
    clock.advance(60)
    assert svc.pay("r2", "alice", order.order_id).status == "paid"
    clock.advance(3 * DAY)
    assert svc.refund("r3", "alice", order.order_id).status == "refunded"
    view = svc.order(order.order_id)
    assert (view.status, view.refunded, view.charged_at) == ("refunded", 2400, 60)
    assert svc.stock()["A"] == 4
    assert sum(a.amount for a in provider.applied.values() if a.kind == "charge") == 2400


def test_abandoned_cart_releases_stock(world):
    clock, _, svc = world
    order = svc.place_order("r1", "bob", [("D", 6)])
    assert not svc.place_order("r2", "carol", [("D", 1)]).ok
    clock.advance(15 * 60)
    svc.run_jobs()
    assert svc.order(order.order_id).status == "expired"
    assert svc.place_order("r3", "carol", [("D", 1)]).ok


def test_declined_card_then_success(world):
    _, provider, svc = world
    order = svc.place_order("r1", "alice", [("B", 1)])
    provider.faults.append("declined")
    assert svc.pay("r2", "alice", order.order_id).reason == "declined"
    assert svc.pay("r3", "alice", order.order_id).status == "paid"


def test_network_trouble_is_settled_by_jobs(world):
    clock, provider, svc = world
    order = svc.place_order("r1", "alice", [("A", 1)])
    provider.faults.extend(["lost_after"])
    assert svc.pay("r2", "alice", order.order_id).status == "paying"
    clock.advance(30)
    svc.run_jobs()
    assert svc.order(order.order_id).status == "paid"
    assert svc.order(order.order_id).charged_at == 0
    provider.faults.extend(["lost_before"])
    assert svc.refund("r3", "alice", order.order_id).status == "refunding"
    svc.run_jobs()
    assert svc.order(order.order_id).status == "refunded"
    assert len(provider.applied) == 2


def test_customers_cannot_touch_each_others_orders(world):
    _, provider, svc = world
    order = svc.place_order("r1", "alice", [("A", 1)])
    assert svc.pay("r2", "mallory", order.order_id).reason == "not_found"
    svc.pay("r3", "alice", order.order_id)
    assert svc.refund("r4", "mallory", order.order_id).reason == "not_found"
    assert all(a.customer == "alice" for a in provider.applied.values())


def test_late_refund_is_refused(world):
    clock, _, svc = world
    order = svc.place_order("r1", "alice", [("C", 2)])
    svc.pay("r2", "alice", order.order_id)
    clock.advance(31 * DAY)
    assert svc.refund("r3", "alice", order.order_id).reason == "window_closed"
    assert svc.order(order.order_id).status == "paid"


def test_retried_requests_are_safe(world):
    _, provider, svc = world
    first = svc.place_order("r1", "alice", [("A", 1)])
    assert svc.place_order("r1", "alice", [("A", 1)]) == first
    paid = svc.pay("r2", "alice", first.order_id)
    assert svc.pay("r2", "alice", first.order_id) == paid
    assert len(svc.orders()) == 1 and len(provider.applied) == 1


def test_work_during_a_slow_payment(world):
    clock, provider, svc = world
    order = svc.place_order("r1", "alice", [("B", 1)])
    during = []

    def meanwhile(phase):
        if phase == "before":
            during.append(svc.pay("r2", "alice", order.order_id))   # the same request, repeated
            during.append(svc.pay("r3", "alice", order.order_id))   # a second attempt
            clock.advance(15 * 60)
            svc.run_jobs()                                           # the hold lapses meanwhile

    provider.during = meanwhile
    assert svc.pay("r2", "alice", order.order_id).status == "paid"
    assert [r.reason for r in during] == ["in_progress", "not_payable"]
    assert svc.order(order.order_id).status == "paid" and len(provider.charges(order.order_id)) == 1
