"""Bounded review probes for newci/proto at commit 24b431c.

Run with proto's interpreter. This script changes only in-memory objects.
The deliberately nonterminating planner is stopped by a reviewer trace budget.
These probes document findings; they do not fix the implementation.
"""

import json
import os
from pathlib import Path
import subprocess
import sys

PROTO = Path(__file__).resolve().parents[2] / "proto"
sys.path.insert(0, str(PROTO))

from app import restricted
from app.effects import Clock, PaymentProvider
from app.kernel import Kernel
from app.runtime import Runtime
from sim import dst, invariants


def setup():
    clock, provider = Clock(), PaymentProvider()
    kernel = Kernel(clock, provider)
    return clock, provider, kernel, Runtime(kernel)


def request(runtime, rid="r1", kind="place_order", **kwargs):
    return dict(id=rid, kind=kind, customer="c1",
                config=runtime.pinned_config(), **kwargs)


def run():
    findings = {}
    source = '''STATE = []
def propose(request, snapshot):
    STATE.append(1)
    return {"op": "reject", "reason": str(len(STATE))}
'''
    planner = restricted.load("mutable_constant", source)
    findings["mutable_constant"] = [planner.propose({}, {}), planner.propose({}, {})]

    source = '''def propose(request, snapshot):
    xs = [1]
    for x in xs:
        xs.append(x)
    return {"op": "reject"}
'''
    planner = restricted.load("growing_for", source)
    line_events = 0

    class ReviewerBudgetExceeded(Exception):
        pass

    def trace(frame, event, arg):
        nonlocal line_events
        if event == "line":
            line_events += 1
            if line_events > 10_000:
                raise ReviewerBudgetExceeded()
        return trace

    try:
        sys.settrace(trace)
        planner.propose({}, {})
    except ReviewerBudgetExceeded:
        findings["growing_for"] = {"validator_accepted": True,
                                    "reviewer_stopped_after_line_events": line_events}
    finally:
        sys.settrace(None)

    source = '''def propose(request, snapshot):
    return {"op": {}}
'''
    planner = restricted.load("malformed_op", source)
    result = dst.run(0, bindings={"place_order": "malformed_op", "pay": "pay_v1",
                                 "refund": "refund_v1"},
                     planners={"malformed_op": planner})
    findings["malformed_op"] = result.safety

    clock, provider, kernel, runtime = setup()
    req = request(runtime, items=(("A", 1),))
    _, first = runtime.plan(req)
    _, second = runtime.plan(req)
    findings["same_request_replanned"] = {
        "commits": [kernel.commit(req, first), kernel.commit(req, second)],
        "orders": len(kernel.orders), "stock_A": kernel.stock["A"],
        "safety": invariants.safety(kernel, provider),
    }

    clock, provider, kernel, runtime = setup()
    req = request(runtime, items=(("A", 1),))
    _, plan = runtime.plan(req)
    kernel.commit(req, plan)
    order_id = next(iter(kernel.orders))
    pay = request(runtime, "pay1", "pay", order_id=order_id)
    _, plan = runtime.plan(pay)
    kernel.commit(pay, plan)
    effect = kernel.begin_delivery(next(iter(kernel.effects)))
    result = provider.execute(effect.op_id, effect.kind, effect.order_id,
                              effect.amount, effect.recipient)
    clock.advance(40 * 86400)
    kernel.on_result(effect.op_id, result)
    refund = request(runtime, "refund1", "refund", order_id=order_id)
    _, plan = runtime.plan(refund)
    findings["delayed_payment_ack"] = {
        "provider_executed_at": 0, "acknowledged_at": clock.now,
        "recorded_paid_at": kernel.orders[order_id].paid_at,
        "refund_commit": kernel.commit(refund, plan),
        "safety": invariants.safety(kernel, provider),
    }

    clock, provider, kernel, runtime = setup()
    runtime.planners["same"] = restricted.load("old", '''def propose(request, snapshot):
    return {"op": "reject", "reason": "old"}
''')
    runtime.bindings["place_order"] = "same"
    req = request(runtime, items=(("A", 1),))
    runtime.planners["same"] = restricted.load("new", '''def propose(request, snapshot):
    return {"op": "reject", "reason": "new"}
''')
    findings["pinning_not_enforced"] = {
        "pinned": req["config"]["place_order"], "actual_plan": runtime.plan(req)[1],
        "scope": "future activation hazard; Phase 0 does not normally replace versions",
    }

    findings["bad_price_labelled_stale"] = dst.divergence(
        {"op": "reserve", "price": 0},
        {"op": "reject", "reason": "out_of_stock"}, True)

    code = '''from app import restricted
p = restricted.load("sets", "def propose(request, snapshot):\\n    return {'op':'reject','reason':str(tuple({'A','B','C','D'}))}\\n")
print(p.propose({},{}))
'''
    findings["set_order_by_hash_seed"] = {}
    for seed in ("0", "1", "2", "12345"):
        proc = subprocess.run([sys.executable, "-c", code], cwd=PROTO,
                              env=dict(os.environ, PYTHONHASHSEED=seed),
                              capture_output=True, text=True, check=True)
        findings["set_order_by_hash_seed"][seed] = proc.stdout.strip()
    return findings


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
