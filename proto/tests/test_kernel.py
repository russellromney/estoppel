from app.effects import Clock, PaymentProvider
from app.kernel import GRANT_TTL, TTL, Kernel
from app.runtime import Runtime, default_bindings


def make():
    clock, provider = Clock(), PaymentProvider()
    kernel = Kernel(clock, provider)
    return clock, provider, kernel, Runtime(kernel)


def request(rt, rid, kind, customer="c1", **kw):
    return {"id": rid, "kind": kind, "customer": customer, "config": rt.pinned_config(), **kw}


def test_order_pay_refund_happy_path():
    clock, provider, kernel, rt = make()
    r1 = request(rt, "r1", "place_order", items=(("A", 2),))
    _, plan = rt.plan(r1)
    assert kernel.commit(r1, plan) == (True, "reserved")
    oid = plan["items"] and kernel.grants[plan["grant"]].order_id
    r2 = request(rt, "r2", "pay", order_id=oid)
    _, plan = rt.plan(r2)
    assert kernel.commit(r2, plan) == (True, "charging")
    (op,) = kernel.pending_effects()
    e = kernel.begin_delivery(op)
    kernel.on_result(op, provider.execute(e.op_id, e.kind, e.order_id, e.amount, e.recipient))
    assert kernel.orders[oid].status == "paid"
    r3 = request(rt, "r3", "refund", order_id=oid)
    _, plan = rt.plan(r3)
    assert kernel.commit(r3, plan) == (True, "refunding")
    assert provider.total("charge", oid) == 2000


def test_stale_snapshot_rejected_at_commit():
    clock, provider, kernel, rt = make()
    r1 = request(rt, "r1", "place_order", items=(("A", 5),))
    r2 = request(rt, "r2", "place_order", customer="c2", items=(("A", 5),))
    _, p1 = rt.plan(r1)
    _, p2 = rt.plan(r2)  # both saw 6 in stock
    assert kernel.commit(r1, p1)[0]
    assert kernel.commit(r2, p2) == (False, "insufficient_stock")


def test_grant_is_request_scoped_and_single_use():
    clock, provider, kernel, rt = make()
    r1 = request(rt, "r1", "place_order", items=(("A", 1),))
    _, plan = rt.plan(r1)
    other = request(rt, "r9", "place_order", items=(("A", 1),))
    assert kernel.commit(other, plan) == (False, "unknown_grant")
    assert kernel.commit(r1, plan)[0]
    assert kernel.commit(r1, plan) == (False, "grant_used")


def test_grant_expires():
    clock, provider, kernel, rt = make()
    r1 = request(rt, "r1", "place_order", items=(("A", 1),))
    _, plan = rt.plan(r1)
    clock.advance(GRANT_TTL + 1)
    assert kernel.commit(r1, plan) == (False, "grant_expired")


def test_other_tenant_order_is_invisible():
    clock, provider, kernel, rt = make()
    r1 = request(rt, "r1", "place_order", items=(("A", 1),))
    _, plan = rt.plan(r1)
    kernel.commit(r1, plan)
    oid = kernel.grants[plan["grant"]].order_id
    snap = kernel.snapshot(request(rt, "r2", "pay", customer="c2", order_id=oid))
    assert snap["order"] is None and snap["grants"] == {}


def test_expiry_releases_stock():
    clock, provider, kernel, rt = make()
    r1 = request(rt, "r1", "place_order", items=(("B", 3),))
    _, plan = rt.plan(r1)
    kernel.commit(r1, plan)
    clock.advance(TTL)
    kernel.tick()
    assert kernel.stock["B"] == 6


def test_bindings_load():
    assert set(default_bindings()) == {"place_order", "pay", "refund"}
