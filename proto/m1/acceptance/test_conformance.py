"""Seeded random workloads through the public interface, with provider faults,
duplicate requests and work interleaved inside in-flight provider calls.

Safety (S1-S6, B1, B2) is checked after every step and inside every
provider call. Progress (P1-P3) is checked after settling with faults off.
A repeated request must return the stored response and change nothing.
"""

import random

import pytest

from oracle import check_safety, check_settled, settle
from spec import PRICES
from world import Clock, Provider

SEEDS = range(40)
STEPS = 120
CUSTOMERS = ("c1", "c2", "c3")
SKUS = sorted(PRICES)


class Violation(AssertionError):
    pass


class Run:
    def __init__(self, seed, build, features):
        self.rng = random.Random(seed)
        self.features = features
        self.clock = Clock(0)
        self.provider = Provider(self.clock)
        self.svc = build(self.clock, self.provider)
        self.done: dict[str, tuple] = {}     # request_id -> (call, args, response)
        self.inflight: dict[str, tuple] = {}  # request_id -> (call, args)
        self.refund_sends: dict[str, tuple[str, int]] = {}  # not rejected: req -> (order, time)
        self.n = 0
        self.log: list = []
        self.provider.choose_fault = self.fault
        self.provider.during = self.during

    def fault(self, kind, key) -> str:
        return self.rng.choices(["ok", "declined", "lost_before", "lost_after"],
                                [75, 8, 7, 10])[0]

    def check(self, where):
        sends: dict[str, list[int]] = {}
        for order_id, t in self.refund_sends.values():
            sends.setdefault(order_id, []).append(t)
        v = check_safety(self.svc, self.provider, self.features, sends)
        if v:
            raise Violation(f"{where}: {v}\nlog tail: {self.log[-8:]}")

    def during(self, phase):
        self.check(f"in call ({phase})")
        if self.rng.random() < 0.35:
            self.act(nested=True)
            self.check(f"after nested action ({phase})")

    def state(self):
        return (self.svc.orders(), self.svc.stock(), dict(self.provider.applied))

    def pick_order(self, customer, want):
        orders = self.svc.orders()
        own = [o for o in orders if o.customer == customer]
        ready = [o for o in own if o.status == want]
        r = self.rng.random()
        pool = ready if ready and r < 0.7 else own if own and r < 0.9 else orders
        return self.rng.choice(pool).id if pool else "missing"

    def request(self):
        rng = self.rng
        customer = rng.choice(CUSTOMERS)
        kind = rng.choices(["place_order", "pay", "refund"], [5, 3, 2])[0]
        if kind == "place_order":
            items = [(rng.choice(SKUS), rng.randint(1, 3)) for _ in range(rng.randint(1, 2))]
            if rng.random() < 0.05:
                items.append(rng.choice([("Z", 1), ("A", 0)]))
            kwargs = {}
            if "coupons" in self.features and rng.random() < 0.4:
                kwargs["coupon"] = rng.choice(["SAVE10", "SAVE10", "SAVE10", "save10", 7])
            return kind, (customer, items), kwargs
        want = "reserved" if kind == "pay" else "paid"
        args = (customer, self.pick_order(customer, want))
        kwargs = {}
        if kind == "refund" and "partial_refunds" in self.features and rng.random() < 0.6:
            kwargs["amount"] = rng.choice([rng.randint(1, 3000), 0, 10**6])
        return kind, args, kwargs

    def send(self, req_id, kind, args, kwargs):
        self.inflight[req_id] = (kind, args, kwargs)
        if kind == "refund":
            self.refund_sends[req_id] = (args[1], self.clock.now)
        try:
            resp = getattr(self.svc, kind)(req_id, *args, **kwargs)
        finally:
            del self.inflight[req_id]
        if not resp.ok:
            self.refund_sends.pop(req_id, None)
        return resp

    def act(self, nested=False):
        rng = self.rng
        r = rng.random()
        if r < 0.55:
            self.n += 1
            req_id = f"r{self.n}"
            kind, args, kwargs = self.request()
            resp = self.send(req_id, kind, args, kwargs)
            self.done[req_id] = (kind, args, kwargs, resp)
            self.log.append((req_id, kind, args, kwargs, resp.ok, resp.reason))
        elif r < 0.65 and (self.done or self.inflight):
            self.repeat()
        elif r < 0.82:
            seconds = rng.choices([rng.randint(1, 120), rng.randint(300, 1200),
                                   rng.randint(1, 40) * 86_400], [80, 15, 5])[0]
            self.clock.advance(seconds)
            self.log.append(("advance", seconds))
        else:
            self.svc.run_jobs()
            self.log.append(("jobs",))

    def repeat(self):
        pool = sorted(self.done) + sorted(self.inflight)
        req_id = self.rng.choice(pool)
        if req_id in self.inflight:
            kind, args, kwargs = self.inflight[req_id]
            before = self.state()
            resp = getattr(self.svc, kind)(req_id, *args, **kwargs)
            if self.state() != before:
                raise Violation(f"repeat of in-flight {req_id} changed state")
            self.log.append(("repeat-inflight", req_id, resp.reason))
            return
        kind, args, kwargs, first = self.done[req_id]
        before = self.state()
        resp = getattr(self.svc, kind)(req_id, *args, **kwargs)
        if resp != first:
            raise Violation(f"repeat of {req_id} returned {resp}, first {first}")
        if self.state() != before:
            raise Violation(f"repeat of {req_id} changed state")
        self.log.append(("repeat", req_id))

    def run(self):
        for step in range(STEPS):
            self.act()
            self.check(f"step {step}")
        self.provider.choose_fault = None
        self.provider.during = None
        settle(self.svc)
        self.check("after settle")
        v = check_settled(self.svc, self.provider, self.clock.now)
        if v:
            raise Violation(f"settled: {v}\nlog tail: {self.log[-8:]}")
        return self


@pytest.mark.parametrize("seed", SEEDS)
def test_random_workload(build, features, seed):
    run = Run(seed, build, features).run()
    assert run.n > 0
