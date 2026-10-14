"""The runtime: idempotent requests, provider outcomes, and reconciliation."""

import pytest
from core_support import echo, make_world, propose, quote, settled_violations, violations

from checkout.core.moves import OpenOrder, Plan, StartCharge, StartRefund
from checkout.core.runtime import IN_PROGRESS

pytestmark = pytest.mark.t2

STOCK = {"X": 3}


@pytest.fixture
def world():
    return make_world(STOCK)


def open_plan():
    return Plan(moves=(OpenOrder(quote=quote(("X", 1)), hold_until=10),))


def charge(world, oid, request_id="pay"):
    return world[2].request(request_id, "pay", "c1", oid, propose(Plan(moves=(StartCharge(order_id=oid),))), echo)


def place(world, request_id="place"):
    return world[2].request(request_id, "place_order", "c1", None, propose(open_plan()), echo).opened[0]


def payment(world, oid, kind="charge"):
    return next(p for p in world[2]._state.orders[oid].payments if p.kind == kind)


# idempotency

def test_a_repeat_returns_the_stored_response_and_does_nothing():
    world = make_world(STOCK)
    first = world[2].request("r", "place_order", "c1", None, propose(open_plan()), echo)
    again = world[2].request("r", "place_order", "c1", None, propose(open_plan()), echo)
    assert again == first and world[2]._state.stock == {"X": 2}


def test_a_repeat_while_in_flight_is_in_progress(world):
    oid = place(world)
    seen = []
    world[1].during = lambda phase: seen.append(charge(world, oid, "pay"))
    charge(world, oid, "pay")
    assert seen == [IN_PROGRESS, IN_PROGRESS]
    assert len(world[1].charges(oid)) == 1


def test_a_failed_request_can_be_retried(world):
    def boom(snap):
        raise RuntimeError("periphery bug")

    with pytest.raises(RuntimeError):
        world[2].request("r", "place_order", "c1", None, boom, echo)
    assert world[2].request("r", "place_order", "c1", None, propose(open_plan()), echo).opened


def test_a_refusal_from_the_periphery_is_stored_as_the_response(world):
    assert world[2].request("r", "pay", "c1", "nope", lambda snap: "no", echo) == "no"
    assert world[2].request("r", "pay", "c1", "nope", propose(None), echo) == "no"


# provider outcomes

@pytest.mark.parametrize("fault, state", [
    ("ok", "applied"), ("declined", "declined"), ("lost_before", "unknown"), ("lost_after", "unknown"),
])
def test_provider_outcomes(world, fault, state):
    oid = place(world)
    world[1].faults.append(fault)
    receipt = charge(world, oid)
    assert receipt.payments[0].state == state == payment(world, oid).state


def test_applied_charge_records_the_providers_time(world):
    oid = place(world)
    world[1].during = lambda phase: world[0].advance(5) if phase == "after" else None
    charge(world, oid)
    assert payment(world, oid).at == 0 == world[1].charges(oid)[0].at


@pytest.mark.parametrize("fault, expected", [("lost_before", "applied"), ("lost_after", "applied")])
def test_reconcile_settles_unknown_calls_with_the_same_key(world, fault, expected):
    oid = place(world)
    world[1].faults.append(fault)
    charge(world, oid)
    world[2].reconcile()
    assert payment(world, oid).state == expected
    assert list(world[1].applied) == [f"charge-{oid}-1"]
    assert settled_violations(world[2], world[1]) == []


def test_reconcile_finds_a_decline(world):
    oid = place(world)
    world[1].faults.extend(["lost_before", "declined"])
    charge(world, oid)
    world[2].reconcile()
    assert payment(world, oid).state == "declined"


def test_reconcile_leaves_calls_in_flight_alone(world):
    oid = place(world)
    world[1].during = lambda phase: world[2].reconcile()
    charge(world, oid)
    assert world[1].calls == 1 and payment(world, oid).state == "applied"


def test_nested_reconcile_during_a_retry_does_not_double_settle(world):
    oid = place(world)
    world[1].faults.extend(["lost_before", "ok"])
    charge(world, oid)
    world[1].during = lambda phase: world[2].reconcile()
    world[2].reconcile()   # nothing found: retried, and the nested reconcile skips the retry
    assert world[1].calls == 2
    assert payment(world, oid).state == "applied" and len(world[1].charges(oid)) == 1
    assert violations(world[2], world[1], STOCK) == []


def test_refunds_go_to_the_payer(world):
    oid = place(world)
    charge(world, oid)
    world[2].request("ref", "refund", "c1", oid, propose(Plan(moves=(StartRefund(order_id=oid, per_line=(100,)),))), echo)
    [refund] = world[1].refunds(oid)
    assert (refund.customer, refund.amount) == ("c1", 100)
