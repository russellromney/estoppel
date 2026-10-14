"""Seeded simulation of the core with generated plans, provider faults and interleavings.

Plans are random, and many are invalid on purpose. Work runs inside in-flight provider calls,
requests are repeated, and jobs and reconciliation run at random. The core's invariants are
checked after every step and inside every provider call.
"""

import random

from core_support import echo, settled_violations, violations

from checkout.core.commit import PlanRejected
from checkout.core.facts import Adjustment, Line, Quote
from checkout.core.moves import OpenOrder, Plan, Release, StartCharge, StartRefund
from checkout.core.runtime import Runtime
from world import Clock, Provider

STOCK = {"X": 12, "Y": 8, "Z": 6}
CUSTOMERS = ("c1", "c2", "c3")


class CoreSimulation:
    def __init__(self, seed: int, steps: int):
        self.rng = random.Random(seed)
        self.steps = steps
        self.clock = Clock(0)
        self.provider = Provider(self.clock)
        self.runtime = Runtime(self.clock, self.provider, STOCK)
        self.sent: list[tuple] = []
        self.requests = 0
        self.refused = 0
        self.provider.choose_fault = lambda kind, key: self.rng.choices(
            ["ok", "declined", "lost_before", "lost_after"], [70, 10, 8, 12])[0]
        self.provider.during = self.meanwhile

    def check(self, where):
        found = violations(self.runtime, self.provider, STOCK)
        assert not found, f"{where}: {found}"

    def meanwhile(self, phase):
        self.check(f"in flight ({phase})")
        if self.rng.random() < 0.4:
            self.step()
            self.check(f"after concurrent step ({phase})")

    # Generated plans

    def random_quote(self) -> Quote:
        rng = self.rng
        skus = rng.sample(sorted(STOCK), rng.randint(1, 2))
        lines = tuple(Line(sku=s, qty=rng.randint(1, 2), unit_price=rng.choice([0, 30, 100]))
                      for s in skus)
        adjustments = ()
        if rng.random() < 0.5:
            per_line = tuple(-rng.randint(0, line.gross) for line in lines)
            adjustments = (Adjustment(rule="generated", per_line=per_line),)
        return Quote(lines=lines, adjustments=adjustments)

    def some_order(self, prefer=None):
        """A random order, usually one that `prefer` picks out, so that most moves can succeed."""
        orders = list(self.runtime._state.orders.values())
        ready = [o for o in orders if prefer(o)] if prefer else []
        pool = ready if ready and self.rng.random() < 0.8 else orders
        return self.rng.choice(pool) if pool else None

    def refund_amounts(self, order) -> tuple[int, ...]:
        rng = self.rng
        left = order.refundable_per_line
        return tuple(rng.choice([x, rng.randint(0, max(x, 0)), x + 1, 0]) for x in left)

    def step(self):
        rng, now = self.rng, self.clock.now
        r = rng.random()
        prefer = (lambda o: o.hold == "held") if r < 0.42 else (lambda o: o.charge is not None)
        order = self.some_order(prefer)
        customer = order.customer if order and rng.random() < 0.85 else rng.choice(CUSTOMERS)
        if r < 0.25 or order is None:
            plan = Plan(moves=(OpenOrder(quote=self.random_quote(),
                                         hold_until=now + rng.choices([-1, 60, 900], [1, 3, 6])[0]),))
            self.send("place_order", customer, None, plan)
        elif r < 0.42:
            self.send("pay", customer, order.id, Plan(moves=(StartCharge(order_id=order.id),)))
        elif r < 0.55:
            plan = Plan(moves=(StartRefund(order_id=order.id, per_line=self.refund_amounts(order)),))
            self.send("refund", customer, order.id, plan)
        elif r < 0.62:
            lapsed = lambda o: o.hold == "held" and o.hold_until <= now
            targets = {self.some_order(lapsed).id for _ in range(rng.randint(1, 2))}
            self.attempt(lambda: self.runtime.job(
                "expire", lambda snap: Plan(moves=tuple(Release(order_id=t) for t in targets))))
        elif r < 0.7 and self.sent:
            request_id, kind, customer, subject, plan = rng.choice(self.sent)
            self.attempt(lambda: self.runtime.request(request_id, kind, customer, subject,
                                                      lambda snap: plan, echo))
        elif r < 0.88:
            self.clock.advance(rng.choices([rng.randint(1, 60), rng.randint(300, 1200)], [80, 20])[0])
        else:
            self.runtime.reconcile()

    def send(self, kind, customer, subject, plan):
        self.requests += 1
        request_id = f"r{self.requests}"
        self.sent.append((request_id, kind, customer, subject, plan))
        self.attempt(lambda: self.runtime.request(request_id, kind, customer, subject,
                                                  lambda snap: plan, echo))

    def attempt(self, call):
        try:
            call()
        except PlanRejected:
            self.refused += 1

    def run(self):
        for i in range(self.steps):
            self.step()
            self.check(f"step {i}")
        self.provider.choose_fault = None
        self.provider.during = None
        for _ in range(2):
            self.runtime.reconcile()
        self.check("settled")
        found = settled_violations(self.runtime, self.provider)
        assert not found, f"settled: {found}"
        return self
