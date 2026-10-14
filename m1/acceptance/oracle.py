"""Checks written from REQUIREMENTS.md, using only the public interface and the provider's ledger."""

from spec import HOLD, HOLDING, INITIAL_STOCK, PRICES, REFUND_WINDOW


def combine(items) -> dict[str, int]:
    wanted: dict[str, int] = {}
    for sku, qty in items:
        wanted[sku] = wanted.get(sku, 0) + qty
    return wanted


def expected_price(items, features) -> int:
    total = 0
    for sku, qty in combine(items).items():
        paid_units = qty - qty // 3 if "b2g1" in features else qty
        total += PRICES[sku] * paid_units
    return total


def ledger_by_order(provider):
    charges: dict[str, list] = {}
    refunds: dict[str, list] = {}
    for a in provider.applied.values():
        (charges if a.kind == "charge" else refunds).setdefault(a.order_id, []).append(a)
    return charges, refunds


def check_safety(svc, provider, features) -> list[str]:
    """S1-S6, B1, B2: must hold at every point."""
    out = []
    stock = svc.stock()
    orders = {o.id: o for o in svc.orders()}
    if set(stock) != set(PRICES):
        out.append(f"stock keys {sorted(stock)}")
        return out
    for sku in PRICES:
        if stock[sku] < 0:
            out.append(f"S1 stock[{sku}]={stock[sku]}")
        held = sum(q for o in orders.values() if o.status in HOLDING
                   for s, q in o.items if s == sku)
        if stock[sku] + held != INITIAL_STOCK:
            out.append(f"S2 {sku}: stock {stock[sku]} + held {held} != {INITIAL_STOCK}")
    charges, refunds = ledger_by_order(provider)
    for a in provider.applied.values():
        o = orders.get(a.order_id)
        if o is None or a.customer != o.customer:
            out.append(f"S5 {a.kind} {a.key} to {a.customer} for order {a.order_id}")
    for oid, cs in charges.items():
        o = orders.get(oid)
        if o is None:
            continue
        if len(cs) > 1:
            out.append(f"S3 {oid} charged {len(cs)} times")
        if any(c.amount != o.price for c in cs):
            out.append(f"S3 {oid} charged {[c.amount for c in cs]}, price {o.price}")
        if o.status == "expired":
            out.append(f"S6 {oid} expired but charged")
    for oid, rs in refunds.items():
        charged = sum(c.amount for c in charges.get(oid, []))
        refunded = sum(r.amount for r in rs)
        if refunded > charged:
            out.append(f"S4 {oid} refunded {refunded} > charged {charged}")
        if charges.get(oid):
            charge_at = charges[oid][0].at
            for r in rs:
                if r.at - charge_at > REFUND_WINDOW:
                    out.append(f"B2 {oid} refund {r.key} at {r.at}, charged at {charge_at}")
    for o in orders.values():
        if o.price != expected_price(o.items, features):
            out.append(f"B1 {o.id} items {o.items} price {o.price}, "
                       f"expected {expected_price(o.items, features)}")
    return out


def check_settled(svc, provider, now) -> list[str]:
    """P1-P3: must hold after settling with faults off."""
    out = []
    charges, refunds = ledger_by_order(provider)
    for o in svc.orders():
        if o.status in ("paying", "refunding"):
            out.append(f"P1 {o.id} stuck in {o.status}")
        charged = bool(charges.get(o.id))
        if (o.status in ("paid", "refunding", "refunded")) != charged:
            out.append(f"P2 {o.id} status {o.status}, ledger charged={charged}")
        if charged and o.charged_at != charges[o.id][0].at:
            out.append(f"P2 {o.id} charged_at {o.charged_at}, ledger {charges[o.id][0].at}")
        if not charged and o.charged_at is not None:
            out.append(f"P2 {o.id} charged_at {o.charged_at} with no charge")
        ledger_refunded = sum(r.amount for r in refunds.get(o.id, []))
        if o.refunded != ledger_refunded:
            out.append(f"P2 {o.id} refunded {o.refunded}, ledger {ledger_refunded}")
        if o.status == "reserved" and now - o.reserved_at >= HOLD:
            out.append(f"P3 {o.id} reserved past hold")
    return out


def settle(svc, rounds: int = 5):
    """REQUIREMENTS 3.4: with faults off, at most 5 calls to run_jobs settle every order."""
    for _ in range(rounds):
        svc.run_jobs()
