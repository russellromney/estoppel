"""Seeded simulation of concurrent traffic with payment faults.

Work is interleaved inside in-flight provider calls (the only point
where a handler waits), requests are repeated, and jobs run at random.
Invariants are checked after every step and inside every call.
"""

import random

from checkout import build
from checkout.config import COUPONS, HOLD_SECONDS, INITIAL_STOCK, PRICES, REFUND_WINDOW_SECONDS
from checkout.models import HOLDS_STOCK, OrderStatus
from world import Clock, Provider

CUSTOMERS = ("c1", "c2", "c3", "c4")
COUPON_CHOICES = (None, None, None, "SAVE10", "SAVE10", "bad")
OPEN = ("in_flight", "unknown")


def violations(service, provider) -> list[str]:
    store, out = service.store, []
    for sku in PRICES:
        held = store.held_units(sku)
        if store.stock[sku] < 0 or store.stock[sku] + held != INITIAL_STOCK:
            out.append(f"stock {sku}: {store.stock[sku]} + held {held}")
    for code, limit in COUPONS.items():
        live = [o.id for o in store.orders.values() if o.coupon == code and o.status in (
            OrderStatus.RESERVED, OrderStatus.PAYING, OrderStatus.PAID, OrderStatus.REFUNDING)]
        if len(live) > limit:
            out.append(f"coupon {code} redeemed by {len(live)} live orders: {live}")
    for order in store.orders.values():
        charges, refunds = provider.charges(order.id), provider.refunds(order.id)
        if len(charges) > 1 or any(c.amount != order.price for c in charges):
            out.append(f"{order.id} charges {[c.amount for c in charges]} price {order.price}")
        if any(a.customer != order.customer for a in charges + refunds):
            out.append(f"{order.id} money to another customer")
        if order.status == OrderStatus.EXPIRED and charges:
            out.append(f"{order.id} expired but charged")
        if sum(r.amount for r in refunds) > sum(c.amount for c in charges):
            out.append(f"{order.id} refunded more than charged")
        if charges and any(store.payments[r.key].created_at - charges[0].at > REFUND_WINDOW_SECONDS
                           for r in refunds):
            out.append(f"{order.id} refund accepted outside the window")
        open_charges = [p for p in store.payments_for(order.id, "charge") if p.state in OPEN]
        open_refunds = [p for p in store.payments_for(order.id, "refund") if p.state in OPEN]
        if len(open_charges) + len(open_refunds) > 1:
            out.append(f"{order.id} has {len(open_charges) + len(open_refunds)} open calls")
        if (order.status == OrderStatus.PAYING) != bool(open_charges):
            out.append(f"{order.id} {order.status} with open charges {len(open_charges)}")
        if (order.status == OrderStatus.REFUNDING) != bool(open_refunds):
            out.append(f"{order.id} {order.status} with open refunds {len(open_refunds)}")
    return out


def settled_violations(service, provider) -> list[str]:
    store, out = service.store, []
    now = service.clock.now
    for order in store.orders.values():
        charges, refunds = provider.charges(order.id), provider.refunds(order.id)
        if order.status in (OrderStatus.PAYING, OrderStatus.REFUNDING):
            out.append(f"{order.id} stuck in {order.status}")
        if (order.status in (OrderStatus.PAID, OrderStatus.REFUNDED)) != bool(charges):
            out.append(f"{order.id} {order.status} but charged={bool(charges)}")
        if charges and order.charged_at != charges[0].at:
            out.append(f"{order.id} charged_at {order.charged_at} != {charges[0].at}")
        if order.refunded != sum(r.amount for r in refunds):
            out.append(f"{order.id} refunded {order.refunded} != ledger")
        if order.status == OrderStatus.RESERVED and now - order.reserved_at >= HOLD_SECONDS:
            out.append(f"{order.id} reserved past its hold")
    return out


class Simulation:
    def __init__(self, seed: int, steps: int):
        self.rng = random.Random(seed)
        self.steps = steps
        self.clock = Clock(0)
        self.provider = Provider(self.clock)
        self.service = build(self.clock, self.provider)
        self.sent: list[tuple] = []
        self.requests = 0
        self.provider.choose_fault = lambda kind, key: self.rng.choices(
            ["ok", "declined", "lost_before", "lost_after"], [70, 10, 8, 12])[0]
        self.provider.during = self.meanwhile

    def check(self, where):
        found = violations(self.service, self.provider)
        assert not found, f"{where}: {found}"

    def meanwhile(self, phase):
        self.check(f"in flight ({phase})")
        if self.rng.random() < 0.4:
            self.step()
            self.check(f"after concurrent step ({phase})")

    def target(self, customer, status):
        orders = list(self.service.store.orders.values())
        own = [o for o in orders if o.customer == customer]
        ready = [o for o in own if o.status == status]
        pool = ready if ready and self.rng.random() < 0.75 else own or orders
        return self.rng.choice(pool).id if pool else "none"

    def step(self):
        rng, svc = self.rng, self.service
        r = rng.random()
        customer = rng.choice(CUSTOMERS)
        if r < 0.25:
            items = [(rng.choice(sorted(PRICES)), rng.randint(1, 3)) for _ in range(rng.randint(1, 2))]
            self.send("place_order", customer, items, rng.choice(COUPON_CHOICES))
        elif r < 0.42:
            self.send("pay", customer, self.target(customer, OrderStatus.RESERVED))
        elif r < 0.52:
            self.send("refund", customer, self.target(customer, OrderStatus.PAID))
        elif r < 0.62 and self.sent:
            req_id, kind, args, _ = rng.choice(self.sent)
            getattr(svc, kind)(req_id, *args)
        elif r < 0.85:
            self.clock.advance(rng.choices([rng.randint(1, 120), rng.randint(300, 1200),
                                            rng.randint(1, 40) * 86_400], [80, 15, 5])[0])
        else:
            svc.run_jobs()

    def send(self, kind, *args):
        self.requests += 1
        req_id = f"r{self.requests}"
        response = getattr(self.service, kind)(req_id, *args)
        self.sent.append((req_id, kind, args, response))

    def run(self):
        for i in range(self.steps):
            self.step()
            self.check(f"step {i}")
        self.provider.choose_fault = None
        self.provider.during = None
        for _ in range(5):
            self.service.run_jobs()
        self.check("settled")
        found = settled_violations(self.service, self.provider)
        assert not found, f"settled: {found}"
        for req_id, kind, args, response in self.sent:
            assert getattr(self.service, kind)(req_id, *args) == response, req_id
        return self
