import pytest

from oracle import check_safety, check_settled, settle
from spec import REFUND_WINDOW


def paid_order(svc, rid, customer="c1", items=(("A", 2),)):
    r = svc.place_order(rid(), customer, list(items))
    assert svc.pay(rid(), customer, r.order_id).ok
    settle(svc)
    assert svc.order(r.order_id).status == "paid"
    return r.order_id


def test_full_refund_to_the_payer(svc, rid, provider, clock, features):
    oid = paid_order(svc, rid)
    clock.advance(3600)
    r = svc.refund(rid(), "c1", oid)
    assert r.ok and r.status in ("refunding", "refunded")
    settle(svc)
    o = svc.order(oid)
    assert o.status == "refunded" and o.refunded == o.price
    [refund] = provider.refunds(oid)
    assert refund.amount == o.price and refund.customer == "c1"
    assert check_safety(svc, provider, features) == []
    assert check_settled(svc, provider, clock.now) == []


def test_other_customers_order_is_not_found(svc, rid, provider):
    oid = paid_order(svc, rid, "c1")
    r = svc.refund(rid(), "c2", oid)
    assert (r.ok, r.reason) == (False, "not_found")
    assert provider.refunds(oid) == []


def test_unpaid_order_is_not_refundable(svc, rid):
    r = svc.place_order(rid(), "c1", [("A", 1)])
    r = svc.refund(rid(), "c1", r.order_id)
    assert (r.ok, r.reason) == (False, "not_refundable")


def test_refunded_order_is_not_refundable_again(svc, rid, provider):
    oid = paid_order(svc, rid)
    svc.refund(rid(), "c1", oid)
    settle(svc)
    r = svc.refund(rid(), "c1", oid)
    assert (r.ok, r.reason) == (False, "not_refundable")
    assert len(provider.refunds(oid)) == 1


def test_refund_at_exactly_30_days_is_allowed(svc, rid, clock):
    oid = paid_order(svc, rid)
    clock.advance(REFUND_WINDOW)
    assert svc.refund(rid(), "c1", oid).ok
    settle(svc)
    assert svc.order(oid).status == "refunded"


def test_refund_after_30_days_is_rejected(svc, rid, provider, clock):
    oid = paid_order(svc, rid)
    clock.advance(REFUND_WINDOW + 1)
    r = svc.refund(rid(), "c1", oid)
    assert (r.ok, r.reason) == (False, "window_closed")
    assert provider.refunds(oid) == []


def test_window_runs_from_the_providers_charge_time(svc, rid, provider, clock):
    r = svc.place_order(rid(), "c1", [("A", 1)])
    oid = r.order_id

    def slow_response(phase):
        if phase == "after":
            clock.advance(10 * 86_400)

    provider.during = slow_response
    svc.pay(rid(), "c1", oid)
    settle(svc)
    provider.during = None
    [charge] = provider.charges(oid)
    clock.advance(charge.at + REFUND_WINDOW + 1 - clock.now)
    r = svc.refund(rid(), "c1", oid)
    assert (r.ok, r.reason) == (False, "window_closed")


def test_declined_refund_returns_to_paid(svc, rid, provider, clock):
    oid = paid_order(svc, rid)
    provider.faults.append("declined")
    r = svc.refund(rid(), "c1", oid)
    assert r.ok or r.reason == "declined"
    settle(svc)
    o = svc.order(oid)
    assert o.status == "paid" and o.refunded == 0
    assert provider.refunds(oid) == []
    assert check_settled(svc, provider, clock.now) == []


@pytest.mark.parametrize("fault", ["lost_after", "lost_before"])
def test_unknown_refund_outcome_is_reconciled(svc, rid, provider, clock, features, fault):
    oid = paid_order(svc, rid)
    provider.faults.append(fault)
    assert svc.refund(rid(), "c1", oid).ok
    settle(svc)
    assert svc.order(oid).status == "refunded"
    assert len(provider.refunds(oid)) == 1
    assert check_safety(svc, provider, features) == []
    assert check_settled(svc, provider, clock.now) == []


def test_repeated_refund_request_returns_the_stored_response(svc, rid, provider):
    oid = paid_order(svc, rid)
    req = rid()
    first = svc.refund(req, "c1", oid)
    settle(svc)
    assert svc.refund(req, "c1", oid) == first
    assert len(provider.refunds(oid)) == 1


def test_second_refund_during_an_in_flight_refund_is_rejected(svc, rid, provider, features):
    oid = paid_order(svc, rid)
    second = []

    def second_request(phase):
        if phase == "before" and not second:
            second.append(svc.refund(rid(), "c1", oid))

    provider.during = second_request
    svc.refund(rid(), "c1", oid)
    settle(svc)
    provider.during = None
    assert (second[0].ok, second[0].reason) == (False, "not_refundable")
    assert len(provider.refunds(oid)) == 1
    assert check_safety(svc, provider, features) == []
