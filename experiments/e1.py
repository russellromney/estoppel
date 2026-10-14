"""E1: authority boundary + closed-loop simulation over the bug corpus.

For each variant (baseline, planner bugs, kernel bugs) this runs the
simulator over N seeds and records which layers detect the bug:

  static        restricted-subset validator rejects the planner
  structural    planner errors because the harm is not expressible
  kernel-reject kernel rejects more plans than baseline, for bug reasons
  property      planner property checks fail
  dst-safety    some seed violates a safety invariant
  dst-progress  some seed violates a progress property after quiescence

For planner bugs it also counts "diverged accepted": plans the kernel
accepted that differ from the v1 reference planner's plan for the same
request and snapshot. Most such divergences are the bug getting through.
Some are benign: the reference declined on a stale snapshot and the
kernel found enough current stock (PB01).

Usage: uv run python -m experiments.e1 [--seeds N]
"""

import argparse
import json
import re
import time
from collections import Counter
from pathlib import Path

from app import restricted
from app.kernel import Kernel
from app.runtime import default_bindings, load_planner
from checks import planner_props
from corpus.kernel_bugs import KERNEL_BUGS
from sim import dst

ROOT = Path(__file__).resolve().parent.parent

PLANNER_BUGS = {
    "PB01": ("place_order", "pb01_place_order_ignores_stock"),
    "PB02": ("place_order", "pb02_place_order_free"),
    "PB03": ("place_order", "pb03_place_order_double_price"),
    "PB04": ("refund", "pb04_refund_no_window"),
    "PB05": ("refund", "pb05_refund_fabricated_grant"),
    "PB06": ("refund", "pb06_refund_half"),
    "PB08": ("place_order", "pb08_place_order_negative_qty"),
    "PB12": ("place_order", "pb12_while_loop"),
    "PB13": ("place_order", "pb13_imports_time"),
    "PB14": ("place_order", "pb14_place_order_reads_other_tenants"),
    "PB16": ("place_order", "pb16_place_order_wrong_items"),
}



def predictions() -> dict[str, str]:
    text = (ROOT / "backlog" / "failure_corpus.md").read_text()
    preds = {}
    for m in re.finditer(r"^\| (PB\d+|KB\d+) \| .*? \| ([^|]+) \|$", text, re.M):
        preds[m.group(1)] = m.group(2).strip().split(" ")[0]
    return preds


def run_variant(seeds, kernel_cls=Kernel, bindings=None, reference=None):
    agg = {"outcomes": Counter(), "safety_seeds": [], "progress_seeds": [],
           "first_safety": None, "first_progress": None,
           "plan_diffs_accepted": 0, "plan_diffs_total": 0, "steps": 0}
    for seed in range(seeds):
        r = dst.run(seed, kernel_cls=kernel_cls, bindings=bindings, reference=reference)
        agg["outcomes"].update(r.outcomes)
        agg["steps"] += r.steps
        agg["plan_diffs_accepted"] += r.plan_diffs_accepted
        agg["plan_diffs_total"] += r.plan_diffs_total
        if r.safety:
            agg["safety_seeds"].append(seed)
            agg["first_safety"] = agg["first_safety"] or (seed, r.safety_step, r.safety[0])
        if r.progress:
            agg["progress_seeds"].append(seed)
            agg["first_progress"] = agg["first_progress"] or (seed, r.progress[0])
    return agg


def kernel_rejections(outcomes: Counter) -> Counter:
    """Kernel rejections of first deliveries, keyed by reason."""
    out = Counter()
    for k, n in outcomes.items():
        reason = k.split(":", 1)[1]
        if ":dup:" in k or reason == "accepted" or reason.startswith("planner"):
            continue
        out[reason] += n
    return out


def blocked_beyond_baseline(variant: Counter, base: Counter) -> dict[str, int]:
    """Reasons whose count exceeds baseline by more than ~3 sigma (Poisson).

    Workloads diverge once a variant behaves differently, so small
    deltas are noise; only clear excesses count as the kernel blocking.
    """
    extra = {}
    for reason in sorted(set(variant) | set(base)):
        delta = variant[reason] - base[reason]
        if delta > 3 * (base[reason] + 1) ** 0.5:
            extra[reason] = delta
    return extra


def planner_errors(outcomes: Counter) -> int:
    return sum(n for k, n in outcomes.items() if k.endswith(":planner_error") and ":dup:" not in k)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=200)
    args = ap.parse_args()
    seeds = args.seeds
    preds = predictions()
    base_bindings = default_bindings()
    rows = []

    t0 = time.perf_counter()
    base = run_variant(seeds, reference=base_bindings)
    base_time = time.perf_counter() - t0
    base_rej = kernel_rejections(base["outcomes"])

    for vid, (kind, name) in PLANNER_BUGS.items():
        layers, notes = [], ""
        try:
            planner = load_planner(name)
        except restricted.RestrictionError as e:
            rows.append({"id": vid, "predicted": preds.get(vid), "layers": ["static"],
                         "diverged_accepted": 0, "notes": str(e)})
            continue
        bindings = dict(base_bindings, **{kind: name})
        agg = run_variant(seeds, bindings=bindings, reference=base_bindings)
        props = planner_props.run(kind, planner)
        extra_rej = blocked_beyond_baseline(kernel_rejections(agg["outcomes"]), base_rej)
        if planner_errors(agg["outcomes"]):
            layers.append("structural")
        if extra_rej:
            layers.append("kernel-reject")
        if props:
            layers.append("property")
        if agg["safety_seeds"]:
            layers.append("dst-safety")
        if agg["progress_seeds"]:
            layers.append("dst-progress")
        rows.append({
            "id": vid, "predicted": preds.get(vid), "layers": layers or ["miss"],
            "diverged_accepted": agg["plan_diffs_accepted"],
            "kernel_blocked": extra_rej, "planner_errors": planner_errors(agg["outcomes"]),
            "property_failures": props,
            "safety_seeds": len(agg["safety_seeds"]), "first_safety": agg["first_safety"],
        })

    for vid, cls in KERNEL_BUGS.items():
        agg = run_variant(seeds, kernel_cls=cls)
        layers = []
        if agg["safety_seeds"]:
            layers.append("dst-safety")
        if agg["progress_seeds"]:
            layers.append("dst-progress")
        rows.append({
            "id": vid, "predicted": preds.get(vid), "layers": layers or ["miss"],
            "safety_seeds": len(agg["safety_seeds"]), "progress_seeds": len(agg["progress_seeds"]),
            "first_safety": agg["first_safety"], "first_progress": agg["first_progress"],
        })

    out_dir = ROOT / "results"
    out_dir.mkdir(exist_ok=True)
    summary = {
        "seeds": seeds,
        "baseline": {
            "outcomes": dict(sorted(base["outcomes"].items())),
            "safety_seeds": base["safety_seeds"], "progress_seeds": base["progress_seeds"],
            "steps": base["steps"], "seconds": round(base_time, 2),
            "requests": seeds * dst.SimConfig().requests,
            "kernel_rejections": dict(sorted(base_rej.items())),
        },
        "variants": rows,
    }
    (out_dir / "e1.json").write_text(json.dumps(summary, indent=2, default=str))
    print(render(summary))


def render(s) -> str:
    lines = [f"E1 over {s['seeds']} seeds", ""]
    b = s["baseline"]
    lines.append(f"Baseline: safety violations in {len(b['safety_seeds'])} seeds, "
                 f"progress violations in {len(b['progress_seeds'])} seeds, "
                 f"{b['steps']} steps in {b['seconds']}s")
    rej = b["kernel_rejections"]
    lines.append(f"Baseline kernel rejections of first deliveries over {b['requests']} requests: "
                 + ", ".join(f"{k}={v}" for k, v in rej.items()))
    lines.append("")
    lines.append(f"{'id':5} {'predicted':14} {'observed':40} detail")
    for r in s["variants"]:
        pred = r["predicted"] or "?"
        obs = ",".join(r["layers"])
        match = "ok " if pred in r["layers"] or (pred == "miss" and r["layers"] == ["miss"]) else "XX "
        if r["id"].startswith("PB"):
            detail = (f"diverged_accepted={r.get('diverged_accepted', 0)} "
                      f"kernel_blocked={r.get('kernel_blocked', {})} "
                      f"props={r.get('property_failures', {})}")
        else:
            detail = f"safety_seeds={r['safety_seeds']} progress_seeds={r['progress_seeds']}"
            first = r.get("first_safety") or r.get("first_progress")
            if first:
                detail += f" first={first}"
        lines.append(f"{r['id']:5} {pred:14} {match}{obs:37} {detail}")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
