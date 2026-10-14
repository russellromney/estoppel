"""Workflows are pure: a snapshot in, a plan or a response out. No core is involved."""

import pytest
from conftest import order_fact, snapshot

from checkout.app import workflows as wf
from checkout.app.config import HOLD_SECONDS, REFUND_WINDOW_SECONDS
from checkout.core.facts import Payment, Receipt
from checkout.core.moves import OpenOrder, Plan, Release, StartCharge, StartRefund
from spec import Response

pytestmark = pytest.mark.t1


def reason(result):
    assert isinstance(result, Response) and not result.ok
    return result.reason


# place_order

def test_place_order_proposes_a_priced_order_with_a_hold():
    plan = wf.propose_place_order("c1", [("C", 2), ("A", 1)], snapshot(now=40))
    [move] = plan.moves
    assert isinstance(move, OpenOrder) and move.hold_until == 40 + HOLD_SECONDS
    assert [(line.sku, line.qty) for line in move.quote.lines] == [("A", 1), ("C", 2)]
    assert move.quote.total == 1000 + 800


def test_place_order_rejects_bad_items_first():
    assert reason(wf.propose_place_order("c1", [("Z", 1)], snapshot(stock={}))) == "bad_items"


def test_place_order_needs_stock_for_every_line():
    snap = snapshot(stock={"A": 6, "B": 1, "C": 6, "D": 6})
    assert reason(wf.propose_place_order("c1", [("A", 1), ("B", 2)], snap)) == "out_of_stock"


def test_place_order_responds_with_the_new_order():
    order = order_fact(id="o7", lines=(("A", 2, 1000),))
    r = wf.respond_place_order(snapshot(orders=[order]), Receipt(opened=("o7",)))
    assert r == Response(ok=True, order_id="o7", price=2000, status="reserved")


# pay

def test_pay_charges_a_reserved_order():
    assert wf.propose_pay("o1", snapshot(orders=[order_fact()])) == \
        Plan(moves=(StartCharge(order_id="o1"),))


@pytest.mark.parametrize("order, now, expected", [
    (None, 0, "not_found"),
    (order_fact(hold="released"), 0, "expired"),
    (order_fact(hold_until=900), 900, "expired"),
    (order_fact(open_charge=True), 0, "not_payable"),
    (order_fact(charged_at=5), 0, "not_payable"),
    (order_fact(charged_at=5), 10_000, "not_payable"),
])
def test_pay_refusals(order, now, expected):
    snap = snapshot(now=now, orders=[order] if order else [])
    assert reason(wf.propose_pay("o1", snap)) == expected


def test_pay_reports_a_decline():
    order = order_fact()
    declined = Payment(key="k", kind="charge", order_id="o1", amount=1000, per_line=(1000,),
                       created_at=0, state="declined")
    assert reason(wf.respond_payment(snapshot(orders=[order]), Receipt(payments=(declined,)))) == "declined"


def test_pay_reports_the_current_status():
    order = order_fact(open_charge=True)
    unknown = order.payments[0].model_copy(update={"state": "unknown"})
    r = wf.respond_payment(snapshot(orders=[order]), Receipt(payments=(unknown,)))
    assert (r.ok, r.status) == (True, "paying")


# refund

def test_refund_proposes_everything_left_on_every_line():
    order = order_fact(lines=(("A", 2, 1000), ("C", 1, 400)), charged_at=0)
    plan = wf.propose_refund("o1", snapshot(now=10, orders=[order]))
    assert plan == Plan(moves=(StartRefund(order_id="o1", per_line=(2000, 400)),))


@pytest.mark.parametrize("order, now, expected", [
    (None, 0, "not_found"),
    (order_fact(), 0, "not_refundable"),
    (order_fact(charged_at=0, open_refund=True), 0, "not_refundable"),
    (order_fact(charged_at=0, refunds=((1000,),)), 0, "not_refundable"),
    (order_fact(charged_at=0), REFUND_WINDOW_SECONDS + 1, "window_closed"),
])
def test_refund_refusals(order, now, expected):
    snap = snapshot(now=now, orders=[order] if order else [])
    assert reason(wf.propose_refund("o1", snap)) == expected


def test_refund_at_the_end_of_the_window_is_allowed():
    snap = snapshot(now=REFUND_WINDOW_SECONDS, orders=[order_fact(charged_at=0)])
    assert isinstance(wf.propose_refund("o1", snap), Plan)


# expiry

def test_expiry_releases_only_lapsed_reservations():
    orders = [order_fact(id="lapsed", hold_until=100), order_fact(id="live", hold_until=101),
              order_fact(id="paying", hold_until=100, open_charge=True),
              order_fact(id="paid", hold_until=100, charged_at=5),
              order_fact(id="gone", hold_until=100, hold="released")]
    assert wf.propose_expiry(snapshot(now=100, orders=orders)) == \
        Plan(moves=(Release(order_id="lapsed"),))


def test_expiry_with_nothing_to_do():
    assert wf.propose_expiry(snapshot(now=0, orders=[order_fact()])) is None
