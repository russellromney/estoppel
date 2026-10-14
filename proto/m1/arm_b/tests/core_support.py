"""Support for core tests: generated plans, cheap cloning, and the core's invariants.

Core tests never run the real pricing rules or workflows. They propose plans directly.
"""

from checkout.core.commit import State
from checkout.core.facts import OPEN, Adjustment, Line, Quote
from checkout.core.runtime import Runtime
from world import Clock, Provider

PRICES = {"X": 100, "Y": 50, "Z": 30}


def make_world(stock):
    clock = Clock(0)
    provider = Provider(clock)
    return clock, provider, Runtime(clock, provider, stock)


def clone(world):
    """Copy a world. Facts are immutable, so copying the containers is enough."""
    clock, provider, runtime = world
    new_clock = Clock(clock.now)
    new_provider = Provider(new_clock)
    new_provider.applied = dict(provider.applied)
    new_provider.declined = set(provider.declined)
    new_runtime = Runtime(new_clock, new_provider, {})
    state = runtime._state
    new_runtime._state = State(stock=dict(state.stock), orders=dict(state.orders),
                               payment_orders=dict(state.payment_orders), opened=state.opened)
    new_runtime._requests = dict(runtime._requests)
    return new_clock, new_provider, new_runtime


def fingerprint(world):
    clock, provider, runtime = world
    state = runtime._state
    return (clock.now, tuple(sorted(state.stock.items())), tuple(state.orders.values()),
            frozenset(provider.applied.items()), frozenset(provider.declined))


def quote(*lines, discount: tuple[int, ...] | None = None) -> Quote:
    """lines are (sku, qty); discount is an amount per line (negative)."""
    adjustments = (Adjustment(rule="generated", per_line=discount),) if discount else ()
    return Quote(lines=tuple(Line(sku=s, qty=q, unit_price=PRICES[s]) for s, q in lines),
                 adjustments=adjustments)


def propose(plan):
    return lambda snap: plan


def echo(snap, receipt):
    return receipt


def violations(runtime: Runtime, provider: Provider, initial: dict[str, int]) -> list[str]:
    """The core's invariants. They must hold at every point, including during provider calls."""
    state, out = runtime._state, []
    held = dict.fromkeys(initial, 0)
    for order in state.orders.values():
        if order.hold != "released":
            for line in order.quote.lines:
                held[line.sku] += line.qty
    for sku, start in initial.items():
        if state.stock[sku] < 0 or state.stock[sku] + held[sku] != start:
            out.append(f"stock {sku}: {state.stock[sku]} available + {held[sku]} held != {start}")
    ledger: dict[tuple[str, str], list] = {}
    for applied in provider.applied.values():
        ledger.setdefault((applied.kind, applied.order_id), []).append(applied)
    for order in state.orders.values():
        charges = ledger.get(("charge", order.id), [])
        refunds = ledger.get(("refund", order.id), [])
        if len(charges) > 1 or any(c.amount != order.quote.total for c in charges):
            out.append(f"{order.id} charges {[c.amount for c in charges]}, total {order.quote.total}")
        if any(a.customer != order.customer for a in charges + refunds):
            out.append(f"{order.id} money moved for another customer")
        if order.hold == "released" and charges:
            out.append(f"{order.id} released but charged")
        if sum(r.amount for r in refunds) > sum(c.amount for c in charges):
            out.append(f"{order.id} refunded more than charged")
        if not order.payments:
            if order.hold == "consumed":
                out.append(f"{order.id} consumed without a charge")
            continue
        totals = order.quote.line_totals()
        refunded = [0] * len(totals)    # applied at the provider
        committed = [0] * len(totals)   # accepted by the core and not declined
        live_charges = core_charged = 0
        for p in order.payments:
            if p.state == "applied" and p.key not in provider.applied:
                out.append(f"{order.id} core records {p.key} applied; the provider never applied it")
            if p.kind == "charge":
                live_charges += p.state != "declined"
                core_charged += p.state == "applied"
                continue
            for i, amount in enumerate(p.per_line):
                committed[i] += amount if p.state != "declined" else 0
                refunded[i] += amount if p.key in provider.applied else 0
        paid = totals if charges else (0,) * len(totals)
        if any(r > p for r, p in zip(refunded, paid)):
            out.append(f"{order.id} line refunds {refunded} exceed paid {paid}")
        if committed != [0] * len(totals) and (not core_charged or any(
                c > t for c, t in zip(committed, totals))):
            out.append(f"{order.id} committed refunds {committed} exceed paid {totals}")
        if live_charges > 1:
            out.append(f"{order.id} has {live_charges} live charges")
        if (order.hold == "consumed") != bool(core_charged):
            out.append(f"{order.id} hold {order.hold} with {core_charged} applied charges")
    return out


def settled_violations(runtime: Runtime, provider: Provider) -> list[str]:
    """After reconciling with faults off: no open calls, and the core agrees with the provider."""
    out = []
    for order in runtime._state.orders.values():
        for p in order.payments:
            if p.state in OPEN:
                out.append(f"{p.key} still {p.state}")
            if (p.state == "applied") != (p.key in provider.applied):
                out.append(f"{p.key} core {p.state}, provider applied {p.key in provider.applied}")
            if p.state == "applied" and p.at != provider.applied[p.key].at:
                out.append(f"{p.key} applied at {p.at}, provider says {provider.applied[p.key].at}")
    return out
