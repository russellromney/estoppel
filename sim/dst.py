"""Deterministic closed-loop simulator.

One seed fully determines a run: the workload, the interleaving of
request steps, effect deliveries and responses, clock advances, and
injected faults. Concurrency is modelled by splitting each request into
a plan step (snapshot + planner) and a commit step, and letting the
scheduler interleave steps from many in-flight requests. That produces
stale snapshots, expired grants and races with expiry naturally.

Faults: lost responses (before or after the provider applied the
operation), declines, and duplicated commit delivery (at-least-once
request delivery).

After every step the safety invariants are checked. After the workload
ends the system is driven to quiescence with faults off, and progress
properties are checked.
"""

import hashlib
import random
from collections import Counter
from dataclasses import dataclass, field

from app.effects import Clock, PaymentProvider
from app.kernel import TTL, Kernel
from app.runtime import Runtime
from sim import invariants

CUSTOMERS = ("c1", "c2", "c3", "c4")


@dataclass
class SimConfig:
    requests: int = 60
    p_lost_after: float = 0.10
    p_lost_before: float = 0.05
    p_declined: float = 0.08
    p_dup_commit: float = 0.10
    max_steps: int = 5000
    quiesce_rounds: int = 20


@dataclass
class Result:
    seed: int
    safety: list[str] = field(default_factory=list)
    safety_step: int | None = None
    progress: list[str] = field(default_factory=list)
    outcomes: Counter = field(default_factory=Counter)
    plan_diffs_accepted: int = 0
    plan_diffs_total: int = 0
    steps: int = 0
    trace_hash: str = ""
    trace: list = field(default_factory=list)


class Sim:
    def __init__(self, seed, kernel_cls=Kernel, bindings=None, reference=None,
                 cfg: SimConfig | None = None, keep_trace=False):
        self.rng = random.Random(seed)
        self.cfg = cfg or SimConfig()
        self.clock = Clock(0)
        self.provider = PaymentProvider()
        self.kernel = kernel_cls(self.clock, self.provider)
        self.runtime = Runtime(self.kernel, bindings)
        # Reference bindings for plan diffs: the same request and snapshot
        # are also given to the reference planner, and accepted plans that
        # differ from its plan are counted.
        self.reference = reference
        self.result = Result(seed=seed)
        self.keep_trace = keep_trace
        self.hasher = hashlib.sha256()
        self.inflight: list[dict] = []
        self.responses: list[tuple[str, str]] = []
        self.arrived = 0
        self.faults_on = True

    # -- tracing -------------------------------------------------------

    def record(self, *event):
        self.hasher.update(repr(event).encode())
        if self.keep_trace:
            self.result.trace.append(event)

    # -- workload ------------------------------------------------------

    def new_request(self) -> dict:
        rng = self.rng
        rid = f"r{self.arrived}"
        self.arrived += 1
        customer = rng.choice(CUSTOMERS)
        kind = rng.choices(["place_order", "pay", "refund"], [5, 3, 2])[0]
        order_ids = list(self.kernel.orders)
        if kind != "place_order" and not order_ids:
            kind = "place_order"
        req = {"id": rid, "kind": kind, "customer": customer,
               "config": self.runtime.pinned_config()}
        if kind == "place_order":
            skus = sorted(self.kernel.prices)
            req["items"] = tuple((rng.choice(skus), rng.randint(1, 3))
                                 for _ in range(rng.randint(1, 2)))
        else:
            # Clients mostly act on their own orders in a sensible state;
            # some requests target arbitrary orders (wrong state or tenant).
            want = "reserved" if kind == "pay" else "paid"
            own = [o for o in order_ids if self.kernel.orders[o].customer == customer]
            ready = [o for o in own if self.kernel.orders[o].status == want]
            r = rng.random()
            if ready and r < 0.7:
                pool = ready
            elif own and r < 0.9:
                pool = own
            else:
                pool = order_ids
            req["order_id"] = rng.choice(pool)
        req["state"] = "new"
        return req

    # -- steps ---------------------------------------------------------

    def step_arrive(self):
        req = self.new_request()
        self.inflight.append(req)
        self.record("arrive", req["id"], req["kind"], req["customer"],
                    req.get("items"), req.get("order_id"))

    def step_plan(self, req):
        snapshot, plan = self.runtime.plan(req)
        req["plan"] = plan
        req["state"] = "planned"
        if self.reference is not None:
            ref_name = self.reference[req["kind"]]
            req["ref_plan"] = self.runtime.propose(ref_name, req, snapshot)
        self.record("plan", req["id"], plan)

    def step_commit(self, req):
        accepted, reason = self.kernel.commit(req, req["plan"])
        dup = req.get("dup", False)
        key = f"{req['kind']}:" + ("dup:" if dup else "") + ("accepted" if accepted else reason)
        self.result.outcomes[key] += 1
        if not dup and "ref_plan" in req and req["plan"] != req["ref_plan"]:
            self.result.plan_diffs_total += 1
            if accepted:
                self.result.plan_diffs_accepted += 1
        self.record("commit", req["id"], dup, accepted, reason)
        self.inflight.remove(req)
        if not dup and self.faults_on and self.rng.random() < self.cfg.p_dup_commit:
            copy = dict(req)
            copy["dup"] = True
            copy["state"] = "planned"
            self.inflight.append(copy)

    def choose_fault(self) -> str:
        if not self.faults_on:
            return "ok"
        r = self.rng.random()
        c = self.cfg
        if r < c.p_lost_after:
            return "lost_after"
        if r < c.p_lost_after + c.p_lost_before:
            return "lost_before"
        if r < c.p_lost_after + c.p_lost_before + c.p_declined:
            return "declined"
        return "ok"

    def step_deliver(self, op_id):
        e = self.kernel.begin_delivery(op_id)
        fault = self.choose_fault()
        result = self.provider.execute(e.op_id, e.kind, e.order_id, e.amount,
                                       e.recipient, fault)
        self.responses.append((op_id, result))
        self.record("deliver", op_id, fault, result)

    def step_respond(self, item):
        self.responses.remove(item)
        self.kernel.on_result(*item)
        self.record("respond", *item)

    def step_reconcile(self):
        self.kernel.reconcile()
        self.record("reconcile")

    def step_tick(self, seconds=None):
        if seconds is None:
            r = self.rng.random()
            if r < 0.80:
                seconds = self.rng.randint(1, 120)
            elif r < 0.95:
                seconds = self.rng.randint(300, 1200)
            else:
                seconds = self.rng.randint(1, 40) * 86400
        self.clock.advance(seconds)
        self.kernel.tick()
        self.record("tick", seconds)

    # -- scheduling ----------------------------------------------------

    def actions(self):
        acts = []
        if self.arrived < self.cfg.requests:
            acts.append((3, self.step_arrive, ()))
        for req in self.inflight:
            if req["state"] == "new":
                acts.append((2, self.step_plan, (req,)))
            else:
                acts.append((2, self.step_commit, (req,)))
        for op in self.kernel.pending_effects():
            acts.append((2, self.step_deliver, (op,)))
        for item in self.responses:
            acts.append((2, self.step_respond, (item,)))
        if self.kernel.unknown_effects():
            acts.append((1, self.step_reconcile, ()))
        return acts

    def check_safety(self) -> bool:
        violations = invariants.safety(self.kernel, self.provider)
        violations += [f"anomaly: {a}" for a in self.kernel.anomalies]
        if violations:
            self.result.safety = violations
            self.result.safety_step = self.result.steps
            return False
        return True

    def run_step(self, fn, args) -> bool:
        self.result.steps += 1
        try:
            fn(*args)
        except Exception as e:  # a kernel crash is a safety failure
            self.result.safety = [f"exception in {fn.__name__}: {type(e).__name__}: {e}"]
            self.result.safety_step = self.result.steps
            return False
        return self.check_safety()

    def run(self) -> Result:
        while self.result.steps < self.cfg.max_steps:
            acts = self.actions()
            if not acts:
                break
            acts.append((1, self.step_tick, ()))
            weight, fn, args = self.rng.choices(acts, [a[0] for a in acts])[0]
            if not self.run_step(fn, args):
                return self.finish()
        self.quiesce()
        return self.finish()

    def quiesce(self):
        """Faults off; deliver, respond, reconcile and expire until stable."""
        self.faults_on = False
        for _ in range(self.cfg.quiesce_rounds):
            for req in list(self.inflight):
                step = self.step_plan if req["state"] == "new" else self.step_commit
                if not self.run_step(step, (req,)):
                    return
            for op in self.kernel.pending_effects():
                if not self.run_step(self.step_deliver, (op,)):
                    return
            for item in list(self.responses):
                if not self.run_step(self.step_respond, (item,)):
                    return
            if self.kernel.unknown_effects() and not self.run_step(self.step_reconcile, ()):
                return
            if not self.run_step(self.step_tick, (TTL + 1,)):
                return
            if not (self.inflight or self.responses or self.kernel.pending_effects()
                    or self.kernel.unknown_effects()):
                break
        self.result.progress = invariants.progress(self.kernel, self.provider)

    def finish(self) -> Result:
        self.result.trace_hash = self.hasher.hexdigest()[:16]
        return self.result


def run(seed, **kwargs) -> Result:
    return Sim(seed, **kwargs).run()
