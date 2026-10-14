from oracle import check_safety, check_settled
from spec import HOLD, INITIAL_STOCK


def test_expiry_releases_stock_at_exactly_the_hold(svc, rid, provider, clock, features):
    a = svc.place_order(rid(), "c1", [("A", 2)]).order_id
    clock.advance(HOLD - 1)
    svc.run_jobs()
    assert svc.order(a).status == "reserved"
    clock.advance(1)
    svc.run_jobs()
    assert svc.order(a).status == "expired"
    assert svc.stock()["A"] == INITIAL_STOCK
    assert check_safety(svc, provider, features) == []
    assert check_settled(svc, provider, clock.now) == []


def test_released_stock_can_be_reserved_again(svc, rid, clock):
    svc.place_order(rid(), "c1", [("B", 6)])
    assert not svc.place_order(rid(), "c2", [("B", 1)]).ok
    clock.advance(HOLD)
    svc.run_jobs()
    assert svc.place_order(rid(), "c2", [("B", 1)]).ok


def test_paid_orders_never_expire(svc, rid, clock):
    oid = svc.place_order(rid(), "c1", [("A", 1)]).order_id
    svc.pay(rid(), "c1", oid)
    for _ in range(5):
        svc.run_jobs()
    clock.advance(10 * HOLD)
    svc.run_jobs()
    assert svc.order(oid).status == "paid"
    assert svc.stock()["A"] == INITIAL_STOCK - 1


def test_run_jobs_with_nothing_to_do_changes_nothing(svc, rid, clock):
    oid = svc.place_order(rid(), "c1", [("A", 1)]).order_id
    before = (svc.orders(), svc.stock())
    svc.run_jobs()
    svc.run_jobs()
    assert (svc.orders(), svc.stock()) == before
    assert svc.order(oid).status == "reserved"
