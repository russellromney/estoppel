"""Bounded-exhaustive check of the core: every state reachable in a small world within a few
steps, and every generated move from each of them.

For each move, an independent statement of the core's rules says whether it must be accepted.
Accepted moves must keep the invariants; refused moves must change nothing. From every state,
reconciling with faults off must settle every provider call.
"""

import itertools
from collections import deque

import pytest
from core_support import (clone, echo, fingerprint, make_world, propose, quote, settled_violations,
                          violations)

from checkout.core.commit import PlanRejected
from checkout.core.moves import OpenOrder, Plan, Release, StartCharge, StartRefund

pytestmark = pytest.mark.t2

STOCK = {"X": 2, "Y": 1}
BUDGETS = {"P": 1}
QUOTES = (quote(("X", 1)), quote(("X", 1), ("Y", 1), discount=(-20, -10)), quote(("X", 2)))
HOLD = 10
MAX_ORDERS = 2
MAX_TIME = 2 * HOLD
DEPTH = 5
ids = itertools.count()


def moves(world):
    """Every generated transition from this world: (label, must_accept, run)."""
    clock, provider, runtime = world
    orders = runtime._state.orders
    stock = runtime._state.stock
    if len(orders) < MAX_ORDERS:
        opens = [("c1", qq, ()) for qq in QUOTES] + [("c2", QUOTES[0], ()), ("c2", QUOTES[0], ("P",))]
        for customer, q, budgets in opens:
            ok = (all(stock[line.sku] >= line.qty for line in q.lines)
                  and all(runtime._state.budgets[b] >= 1 for b in budgets))
            plan = Plan(moves=(OpenOrder(quote=q, hold_until=clock.now + HOLD, budgets=budgets),))
            yield (f"open {customer} {q.total} {budgets}", ok,
                   request("place_order", customer, None, plan))
    for oid, order in orders.items():
        live_charge = any(p.kind == "charge" and p.state != "declined" for p in order.payments)
        can_charge = order.hold == "held" and clock.now < order.hold_until and not live_charge
        charge = Plan(moves=(StartCharge(order_id=oid),))
        for fault in ("ok", "declined", "lost_before", "lost_after"):
            yield f"charge {oid} {fault}", can_charge, request("pay", order.customer, oid, charge, fault)
        yield f"charge {oid} by stranger", False, request("pay", "c9", oid, charge)
        left = order.refundable_per_line
        charged = order.charge is not None
        if charged and sum(left) >= 1:
            full = Plan(moves=(StartRefund(order_id=oid, per_line=left),))
            for fault in ("ok", "declined", "lost_after"):
                yield f"refund {oid} all {fault}", True, request("refund", order.customer, oid, full, fault)
        one = (1,) + (0,) * (len(left) - 1)
        yield (f"refund {oid} one", charged and left[0] >= 1,
               request("refund", order.customer, oid, Plan(moves=(StartRefund(order_id=oid, per_line=one),))))
        over = (left[0] + 1,) + (0,) * (len(left) - 1)
        yield (f"refund {oid} over", False,
               request("refund", order.customer, oid, Plan(moves=(StartRefund(order_id=oid, per_line=over),))))
        can_release = order.hold == "held" and order.open_charge is None
        yield f"release {oid}", can_release, job(Plan(moves=(Release(order_id=oid),)))
    yield "reconcile", True, lambda w: w[2].reconcile()
    if clock.now + HOLD <= MAX_TIME:
        yield "advance", True, lambda w: w[0].advance(HOLD)


def request(kind, customer, subject, plan, fault="ok"):
    def run(world):
        world[1].faults.append(fault)
        try:
            world[2].request(f"r{next(ids)}", kind, customer, subject, propose(plan), echo)
        finally:
            world[1].faults.clear()
    return run


def job(plan):
    return lambda world: world[2].job("expire", propose(plan))


def settles(world) -> list[str]:
    settled = clone(world)
    for _ in range(2):
        settled[2].reconcile()
    return (violations(settled[2], settled[1], STOCK, BUDGETS)
            + settled_violations(settled[2], settled[1]))


def explore(depth=DEPTH):
    start = make_world(STOCK, BUDGETS)
    seen = {fingerprint(start)}
    frontier = deque([(start, ())])
    transitions = 0
    while frontier:
        world, path = frontier.popleft()
        assert settles(world) == [], path
        if len(path) == depth:
            continue
        for label, must_accept, run in moves(world):
            transitions += 1
            after = clone(world)
            before = fingerprint(after)
            try:
                run(after)
            except PlanRejected:
                assert not must_accept, (path, label, "refused")
                assert fingerprint(after) == before, (path, label, "changed state when refused")
                continue
            assert must_accept, (path, label, "accepted")
            assert violations(after[2], after[1], STOCK, BUDGETS) == [], (path, label)
            key = fingerprint(after)
            if key not in seen:
                seen.add(key)
                frontier.append((after, path + (label,)))
    return len(seen), transitions


def test_every_reachable_state_and_move():
    states, transitions = explore()
    assert states > 1000 and transitions > 10_000
