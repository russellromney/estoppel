"""Checks written from REQUIREMENTS.md, using only the public interface and the provider's ledger."""

from spec import (CATEGORIES, CATEGORY_WINDOWS, COUPON, COUPON_REDEMPTIONS, HOLD, HOLDING,
                  INITIAL_STOCK, PRICES, REFUND_WINDOW)


def combine(items) -> dict[str, int]:
    wanted: dict[str, int] = {}
    for sku, qty in items:
        wanted[sku] = wanted.get(sku, 0) + qty
    return wanted


def expected_price(items, features, coupon=None) -> int | None:
    """None when the requirements do not decide the price."""
    wanted = combine(items)
    total = 0
    for sku, qty in wanted.items():
        paid_units = qty - qty // 3 if "b2g1" in features else qty
        total += PRICES[sku] * paid_units
    if coupon is None:
        return total
    if "b2g1" in features and any(qty >= 3 for qty in wanted.values()):
        return None  # how the coupon combines with b2g1 is not yet decided
    return total - total // 10


def refund_window(items, features) -> int:
    if "category_windows" not in features:
        return REFUND_WINDOW
    return min(CATEGORY_WINDOWS[CATEGORIES[sku]] for sku, _ in items)


def ledger_by_order(provider):
    charges: dict[str, list] = {}
    refunds: dict[str, list] = {}
    for a in provider.applied.values():
        (charges if a.kind == "charge" else refunds).setdefault(a.order_id, []).append(a)
    return charges, refunds


def check_safety(svc, provider, features, refund_requests=None) -> list[str]:
    """S1-S6, B1, B2: must hold at every point.

    B2 needs the times of refund requests that were not rejected
    (order_id -> [send time]); it is checked only when they are given.
    """
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
        if refund_requests is not None and charges.get(oid) and oid in orders:
            deadline = charges[oid][0].at + refund_window(orders[oid].items, features)
            in_window = [t for t in refund_requests.get(oid, []) if t <= deadline]
            if len(rs) > len(in_window):
                out.append(f"B2 {oid} {len(rs)} refunds applied, {len(in_window)} "
                           f"requests accepted by {deadline}")
    for o in orders.values():
        expected = expected_price(o.items, features, o.coupon)
        if expected is not None and o.price != expected:
            out.append(f"B1 {o.id} items {o.items} coupon {o.coupon} price {o.price}, "
                       f"expected {expected}")
    if "coupons" in features:
        redeemed = [o.id for o in orders.values() if o.coupon == COUPON
                    and o.status in ("reserved", "paying", "paid", "refunding")]
        if len(redeemed) > COUPON_REDEMPTIONS:
            out.append(f"C1 {len(redeemed)} live orders redeemed {COUPON}: {redeemed}")
    if "coupons" not in features and any(o.coupon for o in orders.values()):
        out.append("an order has a coupon, but coupons are not in force")
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
