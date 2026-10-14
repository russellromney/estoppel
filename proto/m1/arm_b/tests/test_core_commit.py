"""Each core move: when the core accepts it, what it does, and when it refuses."""

import pytest
from core_support import echo, fingerprint, make_world, propose, quote

from checkout.core.authority import Unauthorized
from checkout.core.commit import PlanRejected
from checkout.core.moves import OpenOrder, Plan, Release, StartCharge, StartRefund

pytestmark = pytest.mark.t2

STOCK = {"X": 3, "Y": 1}


@pytest.fixture
def world():
    return make_world(STOCK)


def request(world, kind, customer, plan, subject=None, rid=[0]):
    rid[0] += 1
    return world[2].request(f"r{rid[0]}", kind, customer, subject, propose(plan), echo)


def opened(world, q=None, customer="c1", until=10) -> str:
    plan = Plan(moves=(OpenOrder(quote=q or quote(("X", 1)), hold_until=until),))
    return request(world, "place_order", customer, plan).opened[0]


def charged(world, customer="c1", q=None) -> str:
    oid = opened(world, q, customer)
    request(world, "pay", customer, Plan(moves=(StartCharge(order_id=oid),)), oid)
    return oid


def order(world, oid):
    return world[2]._state.orders[oid]


def refused(world, kind, customer, plan, subject=None):
    before = fingerprint(world)
    with pytest.raises(PlanRejected) as e:
        request(world, kind, customer, plan, subject)
    assert fingerprint(world) == before
    return e.value.problems


# open_order

def test_open_holds_stock_for_every_line(world):
    oid = opened(world, quote(("X", 2), ("Y", 1)))
    assert world[2]._state.stock == {"X": 1, "Y": 0}
    assert order(world, oid).hold == "held" and order(world, oid).customer == "c1"


def test_open_is_all_or_nothing(world):
    plan = Plan(moves=(OpenOrder(quote=quote(("X", 1), ("Y", 2)), hold_until=10),))
    assert "only 1 Y available" in refused(world, "place_order", "c1", plan)


def test_open_needs_a_future_hold(world):
    plan = Plan(moves=(OpenOrder(quote=quote(("X", 1)), hold_until=0),))
    assert refused(world, "place_order", "c1", plan)


def test_open_refuses_unknown_resources(world):
    plan = Plan(moves=(OpenOrder(quote=quote(("Z", 1)), hold_until=10),))
    assert refused(world, "place_order", "c1", plan) == ["unknown resource Z"]


def test_a_plan_opens_at_most_one_order(world):
    move = OpenOrder(quote=quote(("X", 1)), hold_until=10)
    assert refused(world, "place_order", "c1", Plan(moves=(move, move)))


def test_an_invalid_quote_smuggled_past_construction_is_refused(world):
    good = quote(("X", 1), discount=(-50,))
    bad = good.model_copy(update={"adjustments": (good.adjustments[0].model_copy(
        update={"per_line": (-500,)}),)})
    plan = Plan.model_construct(moves=(OpenOrder.model_construct(quote=bad, hold_until=10,
                                                                 kind="open_order"),))
    assert "malformed plan" in refused(world, "place_order", "c1", plan)[0]


def test_something_that_is_not_a_plan_is_refused(world):
    assert "malformed plan" in refused(world, "place_order", "c1", Plan.model_construct(moves=()))[0]


# start_charge

def test_charge_is_the_quote_total_for_the_orders_customer(world):
    oid = charged(world, q=quote(("X", 2), ("Y", 1), discount=(-20, -5)))
    [charge] = world[1].charges(oid)
    assert (charge.amount, charge.customer) == (2 * 100 + 50 - 25, "c1")
    assert order(world, oid).hold == "consumed"


def test_charge_after_the_hold_lapses_is_refused(world):
    oid = opened(world, until=10)
    world[0].advance(10)
    assert refused(world, "pay", "c1", Plan(moves=(StartCharge(order_id=oid),)), oid)


def test_second_charge_is_refused_unless_the_first_was_declined(world):
    oid = opened(world)
    world[1].faults.append("declined")
    request(world, "pay", "c1", Plan(moves=(StartCharge(order_id=oid),)), oid)
    request(world, "pay", "c1", Plan(moves=(StartCharge(order_id=oid),)), oid)
    assert refused(world, "pay", "c1", Plan(moves=(StartCharge(order_id=oid),)), oid)
    assert len(world[1].charges(oid)) == 1


def test_charge_while_one_is_in_flight_is_refused(world):
    oid = opened(world)
    world[1].faults.append("lost_after")
    request(world, "pay", "c1", Plan(moves=(StartCharge(order_id=oid),)), oid)
    assert refused(world, "pay", "c1", Plan(moves=(StartCharge(order_id=oid),)), oid)


def test_charging_another_customers_order_is_refused(world):
    oid = opened(world, customer="c1")
    problems = refused(world, "pay", "c2", Plan(moves=(StartCharge(order_id=oid),)), oid)
    assert problems == [f"order {oid} is outside the grant"]


# start_refund

def test_refund_per_line_up_to_what_was_paid(world):
    oid = charged(world, q=quote(("X", 2), ("Y", 1), discount=(-20, -5)))
    request(world, "refund", "c1", Plan(moves=(StartRefund(order_id=oid, per_line=(80, 0)),)), oid)
    assert order(world, oid).refundable_per_line == (100, 45)
    plan = Plan(moves=(StartRefund(order_id=oid, per_line=(101, 0)),))
    assert refused(world, "refund", "c1", plan, oid) == ["line 0 refund 101 exceeds the 100 left to refund"]


def test_refund_counts_refunds_still_in_flight(world):
    oid = charged(world)
    world[1].faults.append("lost_after")
    request(world, "refund", "c1", Plan(moves=(StartRefund(order_id=oid, per_line=(100,)),)), oid)
    assert refused(world, "refund", "c1", Plan(moves=(StartRefund(order_id=oid, per_line=(1,)),)), oid)


@pytest.mark.parametrize("per_line", [(0,), (-1,), (0, 1)])
def test_malformed_refunds_are_refused(world, per_line):
    oid = charged(world)
    assert refused(world, "refund", "c1", Plan(moves=(StartRefund(order_id=oid, per_line=per_line),)), oid)


def test_refund_of_an_uncharged_order_is_refused(world):
    oid = opened(world)
    assert refused(world, "refund", "c1", Plan(moves=(StartRefund(order_id=oid, per_line=(1,)),)), oid)


# release

def test_release_returns_stock(world):
    oid = opened(world, quote(("X", 2)))
    world[2].job("expire", propose(Plan(moves=(Release(order_id=oid),))))
    assert world[2]._state.stock["X"] == 3 and order(world, oid).hold == "released"


def test_release_is_refused_while_a_charge_is_in_flight_or_applied(world):
    in_flight = opened(world)
    world[1].faults.append("lost_after")
    request(world, "pay", "c1", Plan(moves=(StartCharge(order_id=in_flight),)), in_flight)
    paid = charged(world)
    for oid in (in_flight, paid):
        before = fingerprint(world)
        with pytest.raises(PlanRejected):
            world[2].job("expire", propose(Plan(moves=(Release(order_id=oid),))))
        assert fingerprint(world) == before


def test_a_plan_is_applied_whole_or_not_at_all(world):
    a, b = opened(world), charged(world)
    before = fingerprint(world)
    with pytest.raises(PlanRejected):
        world[2].job("expire", propose(Plan(moves=(Release(order_id=a), Release(order_id=b)))))
    assert fingerprint(world) == before


# authority

def test_moves_outside_the_grant_are_refused(world):
    oid = opened(world)
    assert refused(world, "pay", "c1", Plan(moves=(Release(order_id=oid),)), oid) == \
        ["release is not granted to pay"]


def test_customers_cannot_run_jobs_and_jobs_cannot_make_requests(world):
    with pytest.raises(Unauthorized):
        request(world, "expire", "c1", Plan(moves=(Release(order_id="o1"),)))
    with pytest.raises(Unauthorized):
        world[2].job("pay", propose(None))


def test_a_customer_sees_only_their_own_order(world):
    oid = opened(world, customer="c1")
    seen = {}
    world[2].request("x", "pay", "c2", oid, lambda snap: seen.update(snap.orders), echo)
    assert seen == {}
