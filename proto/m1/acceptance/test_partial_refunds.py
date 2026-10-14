import pytest

from oracle import check_safety, check_settled, settle
from spec import REFUND_WINDOW

pytestmark = pytest.mark.feature("partial_refunds")


def paid_order(svc, rid, items=(("A", 2),)):
    r = svc.place_order(rid(), "c1", list(items))
    svc.pay(rid(), "c1", r.order_id)
    settle(svc)
    return r.order_id, r.price


def test_partial_refunds_add_up_to_a_full_refund(svc, rid, provider, clock, features):
    oid, price = paid_order(svc, rid)
    assert svc.refund(rid(), "c1", oid, amount=300).ok
    settle(svc)
    o = svc.order(oid)
    assert (o.status, o.refunded) == ("paid", 300)
    assert svc.refund(rid(), "c1", oid, amount=price - 300).ok
    settle(svc)
    o = svc.order(oid)
    assert (o.status, o.refunded) == ("refunded", price)
    assert [r.amount for r in provider.refunds(oid)] == [300, price - 300]
    assert check_safety(svc, provider, features) == []
    assert check_settled(svc, provider, clock.now) == []


def test_omitted_amount_refunds_the_remainder(svc, rid):
    oid, price = paid_order(svc, rid)
    svc.refund(rid(), "c1", oid, amount=500)
    settle(svc)
    assert svc.refund(rid(), "c1", oid).ok
    settle(svc)
    o = svc.order(oid)
    assert (o.status, o.refunded) == ("refunded", price)


@pytest.mark.parametrize("amount", [0, -1, 2001, True, 1.5, "100"])
def test_out_of_range_amounts_are_rejected(svc, rid, provider, amount):
    oid, price = paid_order(svc, rid)
    assert price == 2000
    r = svc.refund(rid(), "c1", oid, amount=amount)
    assert (r.ok, r.reason) == (False, "bad_amount")
    assert provider.refunds(oid) == []


def test_amount_is_checked_against_the_remainder(svc, rid):
    oid, price = paid_order(svc, rid)
    svc.refund(rid(), "c1", oid, amount=price - 100)
    settle(svc)
    r = svc.refund(rid(), "c1", oid, amount=101)
    assert (r.ok, r.reason) == (False, "bad_amount")
    assert svc.refund(rid(), "c1", oid, amount=100).ok


def test_window_is_checked_before_the_amount(svc, rid, clock):
    oid, _ = paid_order(svc, rid)
    clock.advance(REFUND_WINDOW + 1)
    r = svc.refund(rid(), "c1", oid, amount=0)
    assert (r.ok, r.reason) == (False, "window_closed")


def test_declined_partial_refund_leaves_the_refunded_total(svc, rid, provider):
    oid, _ = paid_order(svc, rid)
    svc.refund(rid(), "c1", oid, amount=300)
    settle(svc)
    provider.faults.append("declined")
    svc.refund(rid(), "c1", oid, amount=400)
    settle(svc)
    o = svc.order(oid)
    assert (o.status, o.refunded) == ("paid", 300)


def test_concurrent_partial_refunds_cannot_exceed_the_price(svc, rid, provider, features):
    oid, price = paid_order(svc, rid)
    second = []

    def second_request(phase):
        if phase == "before" and not second:
            second.append(svc.refund(rid(), "c1", oid, amount=price))

    provider.during = second_request
    svc.refund(rid(), "c1", oid, amount=price)
    settle(svc)
    provider.during = None
    assert (second[0].ok, second[0].reason) == (False, "not_refundable")
    assert sum(r.amount for r in provider.refunds(oid)) == price
    assert check_safety(svc, provider, features) == []


@pytest.mark.parametrize("fault", ["lost_after", "lost_before"])
def test_unknown_partial_refund_is_reconciled_once(svc, rid, provider, clock, features, fault):
    oid, _ = paid_order(svc, rid)
    provider.faults.append(fault)
    svc.refund(rid(), "c1", oid, amount=700)
    settle(svc)
    o = svc.order(oid)
    assert (o.status, o.refunded) == ("paid", 700)
    assert [r.amount for r in provider.refunds(oid)] == [700]
    assert check_settled(svc, provider, clock.now) == []
