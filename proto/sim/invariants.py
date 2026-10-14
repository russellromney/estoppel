"""Safety and progress properties checked by the simulator.

Money properties are checked against the provider's ledger (ground
truth), not against the kernel's own counters.
"""

from app.kernel import LIVE_STATUSES, TTL


def safety(kernel, provider) -> list[str]:
    out = []
    for sku, qty in kernel.stock.items():
        if qty < 0:
            out.append(f"S1 stock[{sku}]={qty} < 0")
    for sku, initial in kernel.initial_stock.items():
        held = sum(q for o in kernel.orders.values() if o.status in LIVE_STATUSES
                   for s, q in o.items if s == sku)
        if kernel.stock[sku] + held != initial:
            out.append(f"S2 conservation[{sku}]: stock {kernel.stock[sku]} + held {held} != {initial}")
    for oid, order in kernel.orders.items():
        charges = provider.count("charge", oid)
        charged = provider.total("charge", oid)
        refunded = provider.total("refund", oid)
        if charges > 1:
            out.append(f"S3 {oid} charged {charges} times")
        if charges and charged != order.price * charges:
            out.append(f"S3 {oid} charged {charged}, price {order.price}")
        if refunded > charged:
            out.append(f"S4 {oid} refunded {refunded} > charged {charged}")
        if order.status == "expired" and charges:
            out.append(f"S6 {oid} expired but charged")
    for a in provider.applied.values():
        order = kernel.orders.get(a.order_id)
        if order is None or a.recipient != order.customer:
            out.append(f"S5 {a.op_id} {a.kind} to {a.recipient}, order customer "
                       f"{order.customer if order else None}")
    return out


def progress(kernel, provider) -> list[str]:
    """Checked only after quiescence: time has advanced, faults are off,
    and all deliverable effects have been delivered and reconciled."""
    out = []
    now = kernel.clock.now
    for e in kernel.effects.values():
        if e.status in ("pending", "in_flight", "unknown"):
            out.append(f"P2 effect {e.op_id} stuck in {e.status}")
    for oid, o in kernel.orders.items():
        if o.status in ("paying", "refunding"):
            out.append(f"P3 order {oid} stuck in {o.status}")
        if o.status == "reserved" and now - o.reserved_at >= TTL:
            out.append(f"P1 order {oid} reserved past TTL")
        charged = provider.count("charge", oid) > 0
        if (o.status in ("paid", "refunding", "refunded")) != charged:
            out.append(f"P4 order {oid} status {o.status} but provider charged={charged}")
        if o.refunded != provider.total("refund", oid):
            out.append(f"P4 order {oid} refunded {o.refunded} != provider "
                       f"{provider.total('refund', oid)}")
    return out
