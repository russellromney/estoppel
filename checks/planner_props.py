"""Planner obligations: properties a planner must satisfy on its own.

The kernel does not enforce these. They are the planner's evidence.
Cases are generated from a seed, so a check is a pure function of
(planner source, check source, seed, case count).

Caveat recorded for S6: these properties were written by the same
author as the v1 planners, so they share any misunderstanding of the
requirements. They are not independent evidence.
"""

import random

from app import restricted
from app.kernel import PRICES

REFUND_WINDOW = 30 * 86400
STATUSES = ("reserved", "paying", "paid", "refunding", "refunded", "expired")


def gen_place_order(rng):
    stock = {sku: rng.randint(0, 6) for sku in PRICES}
    catalog = {sku: {"price": p, "stock": stock[sku]} for sku, p in PRICES.items()}
    grants = {"g1": {"kind": "reserve", "order_id": "o1", "expires_at": 300}} if rng.random() < 0.9 else {}
    skus = sorted(PRICES) + (["Z"] if rng.random() < 0.05 else [])
    items = tuple((rng.choice(skus), rng.randint(-1, 3) if rng.random() < 0.05 else rng.randint(1, 3))
                  for _ in range(rng.randint(1, 3)))
    request = {"id": "r1", "kind": "place_order", "customer": "c1", "items": items}
    snapshot = {"now": 0, "customer": "c1", "catalog": catalog, "grants": grants}
    return request, snapshot


def check_place_order(request, snapshot, plan) -> list[str]:
    fails = []
    catalog = snapshot["catalog"]
    wanted, valid = {}, True
    for sku, qty in request["items"]:
        if sku not in catalog or qty <= 0:
            valid = False
            break
        wanted[sku] = wanted.get(sku, 0) + qty
    if plan.get("op") == "reserve":
        items = dict(plan["items"]) if all(len(l) == 2 for l in plan["items"]) else None
        if plan.get("grant") not in snapshot["grants"]:
            fails.append("PO5 reserve must use an offered grant")
        if not valid or items != wanted:
            fails.append("PO2 reserved items must equal requested items")
        if items and any(catalog.get(s, {}).get("stock", -1) < q for s, q in items.items()):
            fails.append("PO3 reserved quantity must not exceed snapshot stock")
        if items and plan.get("price") != sum(catalog[s]["price"] * q for s, q in items.items()
                                               if s in catalog):
            fails.append("PO1 price must equal list total of reserved items")
    else:
        can = (valid and snapshot["grants"]
               and all(catalog[s]["stock"] >= q for s, q in wanted.items()))
        if can:
            fails.append("PO4 must reserve a valid, in-stock order")
    return fails


def gen_order_request(rng, kind):
    now = rng.randint(0, 60) * 86400
    order = None
    grants = {}
    if rng.random() < 0.9:
        status = rng.choice(STATUSES)
        paid_at = now - rng.randint(0, 40 * 86400) if status in ("paid", "refunding", "refunded") else None
        order = {"id": "o1", "status": status, "items": (("A", 1),), "price": 1000,
                 "reserved_at": 0, "paid_at": paid_at,
                 "refunded": 1000 if status == "refunded" else 0}
        if kind == "pay" and status == "reserved" and rng.random() < 0.95:
            grants["g1"] = {"kind": "charge", "order_id": "o1", "amount": 1000, "expires_at": now + 300}
        if kind == "refund" and status == "paid" and rng.random() < 0.95:
            grants["g1"] = {"kind": "refund", "order_id": "o1", "amount": 1000, "expires_at": now + 300}
    request = {"id": "r1", "kind": kind, "customer": "c1", "order_id": "o1"}
    snapshot = {"now": now, "customer": "c1", "order": order, "grants": grants}
    return request, snapshot


def check_refund(request, snapshot, plan) -> list[str]:
    order, grants = snapshot["order"], snapshot["grants"]
    eligible = (order is not None and order["status"] == "paid"
                and snapshot["now"] - order["paid_at"] <= REFUND_WINDOW and bool(grants))
    fails = []
    if plan.get("op") == "refund":
        if not eligible:
            fails.append("RF1 refund only paid orders within the window, with a grant")
        elif plan.get("grant") not in grants or plan.get("amount") != grants[plan["grant"]]["amount"]:
            fails.append("RF1 refund the granted amount with the offered grant")
    elif eligible:
        fails.append("RF2 must refund an eligible order")
    return fails


def check_pay(request, snapshot, plan) -> list[str]:
    offered = [g for g, v in snapshot["grants"].items() if v["kind"] == "charge"]
    if plan.get("op") == "charge":
        return [] if plan.get("grant") in offered else ["PY1 charge only with an offered grant"]
    return ["PY1 must charge when a charge grant is offered"] if offered else []


CHECKS = {
    "place_order": (gen_place_order, check_place_order),
    "refund": (lambda rng: gen_order_request(rng, "refund"), check_refund),
    "pay": (lambda rng: gen_order_request(rng, "pay"), check_pay),
}


def run(kind: str, planner: restricted.Planner, seed: int = 0, cases: int = 500) -> dict:
    """Return {property: count of failing cases}, plus 'error' for exceptions."""
    gen, check = CHECKS[kind]
    rng = random.Random(seed)
    failures: dict[str, int] = {}
    for _ in range(cases):
        request, snapshot = gen(rng)
        try:
            plan = restricted.thaw(planner.propose(restricted.freeze(request),
                                                   restricted.freeze(snapshot)))
            fails = check(request, snapshot, plan)
        except Exception as e:
            fails = [f"ERR planner raised {type(e).__name__}"]
        for f in fails:
            key = f.split(" ")[0]
            failures[key] = failures.get(key, 0) + 1
    return failures
