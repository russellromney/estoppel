"""E1b: mutation sample of the v1 planners.

Every first-order mutant (operators M1-M8, see experiments/mutate.py) of
place_order_v1, pay_v1 and refund_v1 is validated, property-checked and
run through the closed-loop simulator with v1 as reference. Divergences
are classed by outcome (sim.dst.divergence) and each mutant takes its
worst class: accepted > lost > blocked, or silent if it never diverges.
Predictions are in backlog/failure_corpus.md, section E1b.

Usage: uv run python -m experiments.e1b [--seeds N]
"""

import argparse
import json
from collections import Counter
from pathlib import Path

from app import restricted
from app.runtime import default_bindings, find_planner
from checks import planner_props
from experiments import mutate
from experiments.e1 import run_variant

ROOT = Path(__file__).resolve().parent.parent
PLANNERS = {"place_order": "place_order_v1", "pay": "pay_v1", "refund": "refund_v1"}
ORDER = ("accepted", "lost", "blocked")

# Post hoc (not pre-registered): one happy-path case per kind, the kind of
# example test a conventional suite would have. A mutant fails it if its
# plan differs from v1's plan for that case.
SMOKE = {
    "place_order": ({"id": "r1", "kind": "place_order", "customer": "c1",
                     "items": (("A", 1), ("B", 2))},
                    {"now": 0, "customer": "c1",
                     "catalog": {s: {"price": p, "stock": 6} for s, p in
                                 {"A": 1000, "B": 2500, "C": 400, "D": 9900}.items()},
                     "grants": {"g1": {"kind": "reserve", "order_id": "o1", "expires_at": 300}}}),
    "pay": ({"id": "r1", "kind": "pay", "customer": "c1", "order_id": "o1"},
            {"now": 100, "customer": "c1",
             "order": {"id": "o1", "status": "reserved", "items": (("A", 1),), "price": 1000,
                       "reserved_at": 0, "paid_at": None, "refunded": 0},
             "grants": {"g1": {"kind": "charge", "order_id": "o1", "amount": 1000,
                               "expires_at": 400}}}),
    "refund": ({"id": "r1", "kind": "refund", "customer": "c1", "order_id": "o1"},
               {"now": 86400, "customer": "c1",
                "order": {"id": "o1", "status": "paid", "items": (("A", 1),), "price": 1000,
                          "reserved_at": 0, "paid_at": 100, "refunded": 0},
                "grants": {"g1": {"kind": "refund", "order_id": "o1", "amount": 1000,
                                  "expires_at": 86700}}}),
}


def plan_for(planner, kind):
    request, snapshot = SMOKE[kind]
    try:
        return restricted.thaw(planner.propose(restricted.freeze(request),
                                               restricted.freeze(snapshot)))
    except Exception as e:
        return {"op": "error", "reason": type(e).__name__}


def mutant_class(div: Counter) -> str:
    if div["accepted"]:
        return "accepted"
    if div["lost"] or div["lost_rejected"]:
        return "lost"
    if div["blocked"]:
        return "blocked"
    return "silent"


def run_mutant(kind, m, seeds, base_bindings, reference) -> dict:
    row = {"id": m.id, "kind": kind, "op": m.op, "line": m.line, "change": m.change}
    try:
        planner = restricted.load(m.id, m.source)
    except restricted.RestrictionError as e:
        return dict(row, cls="static", notes=str(e))
    props = planner_props.run(kind, planner)
    smoke_fails = plan_for(planner, kind) != plan_for(reference, kind)
    agg = run_variant(seeds, bindings=dict(base_bindings, **{kind: m.id}),
                      reference=base_bindings, planners={m.id: planner})
    div = agg["divergences"]
    return dict(row, cls=mutant_class(div), divergences=dict(div), props=props,
                smoke_fails=smoke_fails,
                safety_seeds=len(agg["safety_seeds"]), first_safety=agg["first_safety"],
                progress_seeds=len(agg["progress_seeds"]), first_progress=agg["first_progress"])


def summarize(rows) -> dict:
    diverging = [r for r in rows if r["cls"] in ORDER]
    n = len(diverging)
    shares = {c: sum(r["cls"] == c for r in diverging) for c in ORDER}
    no_m4 = [r for r in diverging if r["op"] != "M4"]
    return {
        "mutants": len(rows),
        "by_class": dict(Counter(r["cls"] for r in rows)),
        "diverging": n,
        "diverging_shares": {c: round(k / n, 3) if n else None for c, k in shares.items()},
        "diverging_without_M4": len(no_m4),
        "shares_without_M4": {c: round(sum(r["cls"] == c for r in no_m4) / len(no_m4), 3)
                              if no_m4 else None for c in ORDER},
        "kernel_rejected_an_action": sum(bool(r["divergences"].get("lost_rejected")
                                              or r["divergences"].get("blocked"))
                                         for r in diverging),
        "safety_breaking": [r["id"] for r in rows if r.get("safety_seeds")],
        "progress_breaking": [r["id"] for r in rows if r.get("progress_seeds")],
        "diverging_with_property_failure": sum(bool(r["props"]) for r in diverging),
        "silent_with_property_failure": sum(bool(r.get("props")) for r in rows
                                            if r["cls"] == "silent"),
        "smoke_fails_by_class": {c: f"{sum(r['smoke_fails'] for r in rows if r['cls'] == c)}"
                                    f"/{sum(r['cls'] == c for r in rows)}"
                                 for c in ORDER + ("silent",)},
        "by_kind": {k: dict(Counter(r["cls"] for r in rows if r["kind"] == k)) for k in PLANNERS},
        "by_op": {op: dict(Counter(r["cls"] for r in rows if r["op"] == op))
                  for op in sorted({r["op"] for r in rows})},
    }


def render(s, rows) -> str:
    lines = [f"E1b over {s['seeds']} seeds per mutant", ""]
    lines.append(f"Mutants: {s['mutants']}  by class: {s['by_class']}")
    lines.append(f"Diverging: {s['diverging']}  shares: {s['diverging_shares']}")
    lines.append(f"Diverging without M4: {s['diverging_without_M4']}  "
                 f"shares: {s['shares_without_M4']}")
    lines.append(f"Diverging mutants where the kernel rejected at least one action: "
                 f"{s['kernel_rejected_an_action']}/{s['diverging']}")
    lines.append(f"Safety-breaking mutants: {s['safety_breaking']}")
    lines.append(f"Progress-breaking mutants: {s['progress_breaking']}")
    lines.append(f"Diverging mutants with a property failure: "
                 f"{s['diverging_with_property_failure']}/{s['diverging']}")
    lines.append(f"Silent mutants with a property failure: {s['silent_with_property_failure']}"
                 f"/{s['by_class'].get('silent', 0)}")
    lines.append(f"Post hoc: fail one happy-path case, by class: {s['smoke_fails_by_class']}")
    lines.append(f"By kind: {s['by_kind']}")
    lines.append(f"By op: {s['by_op']}")
    lines.append("")
    lines.append(f"{'mutant':34} {'class':9} {'smoke':6} {'change':55} divergences / props")
    for r in rows:
        if r["cls"] == "silent" and not r.get("props"):
            continue
        smoke = "fail" if r.get("smoke_fails") else "pass"
        lines.append(f"{r['id']:34} {r['cls']:9} {smoke:6} {r['change'][:55]:55} "
                     f"{r.get('divergences', {})} {r.get('props', {})}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=20)
    args = ap.parse_args()
    base = default_bindings()
    rows = []
    for kind, name in PLANNERS.items():
        source = find_planner(name).read_text()
        reference = restricted.load(name, source)
        for m in mutate.mutants(name, source):
            rows.append(run_mutant(kind, m, args.seeds, base, reference))
    summary = dict(summarize(rows), seeds=args.seeds)
    out_dir = ROOT / "results"
    out_dir.mkdir(exist_ok=True)
    (out_dir / "e1b.json").write_text(json.dumps({"summary": summary, "mutants": rows},
                                                 indent=2, default=str))
    print(render(summary, rows))


if __name__ == "__main__":
    main()
