import itertools

import pytest

from checkout import build
from checkout.core.facts import Grant, Line, Order, Payment, Quote, Snapshot
from world import Clock, Provider


@pytest.fixture
def clock():
    return Clock(0)


@pytest.fixture
def provider(clock):
    return Provider(clock)


@pytest.fixture
def service(clock, provider):
    return build(clock, provider)


@pytest.fixture
def rid():
    counter = itertools.count(1)
    return lambda: f"req-{next(counter)}"


# Facts for periphery tests, built directly rather than through the core.

def order_fact(id="o1", customer="c1", lines=(("A", 1, 1000),), adjustments=(), opened_at=0,
               hold_until=900, hold="held", charged_at=None, refunds=(), open_charge=False,
               open_refund=False, budgets=()) -> Order:
    """An order fact. `refunds` are applied refund amounts per line; `charged_at` adds an applied charge."""
    quote = Quote(lines=tuple(Line(sku=s, qty=q, unit_price=p) for s, q, p in lines),
                  adjustments=adjustments)
    payments = []
    if charged_at is not None or open_charge:
        payments.append(Payment(key=f"charge-{id}-1", kind="charge", order_id=id,
                                amount=quote.total, per_line=quote.line_totals(), created_at=0,
                                state="in_flight" if open_charge else "applied", at=charged_at))
    for n, per_line in enumerate(refunds, 1):
        payments.append(Payment(key=f"refund-{id}-{n}", kind="refund", order_id=id,
                                amount=sum(per_line), per_line=per_line, created_at=0,
                                state="applied", at=charged_at))
    if open_refund:
        payments.append(Payment(key=f"refund-{id}-x", kind="refund", order_id=id,
                                amount=quote.total, per_line=quote.line_totals(), created_at=0,
                                state="unknown"))
    if charged_at is not None and hold == "held":
        hold = "consumed"
    return Order(id=id, customer=customer, quote=quote, opened_at=opened_at, hold_until=hold_until,
                 hold=hold, budgets=budgets, payments=tuple(payments))


def snapshot(now=0, orders=(), stock=None, kind="test", budgets=None) -> Snapshot:
    grant = Grant(kind=kind, principal="c1", moves=frozenset(), scope="all")
    return Snapshot(now=now, grant=grant, stock=stock if stock is not None else {"A": 6, "B": 6,
                    "C": 6, "D": 6}, orders={o.id: o for o in orders}, budgets=budgets or {})
