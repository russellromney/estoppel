from oracle import check_safety, check_settled, settle
from spec import HOLD, INITIAL_STOCK


def reserve(svc, rid, customer="c1", items=(("A", 1),)):
    r = svc.place_order(rid(), customer, list(items))
    assert r.ok
    return r.order_id


def test_pay_charges_the_order_price_once(svc, rid, provider, clock, features):
    oid = reserve(svc, rid)
    clock.advance(30)
    r = svc.pay(rid(), "c1", oid)
    assert r.ok and r.status in ("paying", "paid")
    settle(svc)
    o = svc.order(oid)
    assert o.status == "paid"
    [charge] = provider.charges(oid)
    assert charge.amount == o.price and charge.customer == "c1"
    assert o.charged_at == charge.at == 30
    assert check_safety(svc, provider, features) == []
    assert check_settled(svc, provider, clock.now) == []


def test_other_customers_order_is_not_found(svc, rid, provider):
    oid = reserve(svc, rid, "c1")
    r = svc.pay(rid(), "c2", oid)
    assert (r.ok, r.reason) == (False, "not_found")
    r = svc.pay(rid(), "c1", "no-such-order")
    assert (r.ok, r.reason) == (False, "not_found")
    assert provider.calls == 0


def test_hold_lapses_at_exactly_900_seconds_even_before_jobs_run(svc, rid, provider, clock):
    oid = reserve(svc, rid)
    clock.advance(HOLD)
    r = svc.pay(rid(), "c1", oid)
    assert (r.ok, r.reason) == (False, "expired")
    assert provider.calls == 0
    svc.run_jobs()
    assert svc.order(oid).status == "expired"
    assert svc.stock()["A"] == INITIAL_STOCK
    r = svc.pay(rid(), "c1", oid)
    assert (r.ok, r.reason) == (False, "expired")


def test_pay_just_inside_the_hold_succeeds(svc, rid, clock):
    oid = reserve(svc, rid)
    clock.advance(HOLD - 1)
    assert svc.pay(rid(), "c1", oid).ok
    settle(svc)
    assert svc.order(oid).status == "paid"


def test_paid_order_is_not_payable(svc, rid, provider):
    oid = reserve(svc, rid)
    svc.pay(rid(), "c1", oid)
    settle(svc)
    r = svc.pay(rid(), "c1", oid)
    assert (r.ok, r.reason) == (False, "not_payable")
    assert len(provider.charges(oid)) == 1


def test_order_with_unknown_charge_outcome_is_not_payable(svc, rid, provider):
    oid = reserve(svc, rid)
    provider.faults.append("lost_after")
    svc.pay(rid(), "c1", oid)
    r = svc.pay(rid(), "c1", oid)
    assert (r.ok, r.reason) == (False, "not_payable")
    settle(svc)
    assert svc.order(oid).status == "paid"
    assert len(provider.charges(oid)) == 1


def test_declined_charge_returns_to_reserved_and_can_be_retried(svc, rid, provider, clock, features):
    oid = reserve(svc, rid)
    provider.faults.append("declined")
    r = svc.pay(rid(), "c1", oid)
    assert r.ok or r.reason == "declined"
    settle(svc)
    assert svc.order(oid).status == "reserved"
    assert provider.charges(oid) == []
    assert svc.pay(rid(), "c1", oid).ok
    settle(svc)
    assert svc.order(oid).status == "paid"
    assert len(provider.charges(oid)) == 1
    assert check_safety(svc, provider, features) == []


def test_lost_response_is_reconciled_without_a_second_charge(svc, rid, provider, clock, features):
    oid = reserve(svc, rid)
    provider.faults.append("lost_after")
    assert svc.pay(rid(), "c1", oid).ok
    settle(svc)
    assert svc.order(oid).status == "paid"
    assert len(provider.charges(oid)) == 1
    assert check_settled(svc, provider, clock.now) == []


def test_request_that_never_arrived_is_retried(svc, rid, provider, clock):
    oid = reserve(svc, rid)
    provider.faults.extend(["lost_before", "lost_before"])
    assert svc.pay(rid(), "c1", oid).ok
    settle(svc)
    assert svc.order(oid).status == "paid"
    assert len(provider.charges(oid)) == 1
    assert check_settled(svc, provider, clock.now) == []


def test_charged_at_is_the_providers_time_not_the_response_time(svc, rid, provider, clock):
    oid = reserve(svc, rid)
    clock.advance(10)

    def slow_response(phase):
        if phase == "after":
            clock.advance(86_400)

    provider.during = slow_response
    svc.pay(rid(), "c1", oid)
    settle(svc)
    provider.during = None
    [charge] = provider.charges(oid)
    assert charge.at == 10
    assert svc.order(oid).charged_at == 10


def test_hold_lapsing_during_a_charge_does_not_expire_the_order(svc, rid, provider, clock, features):
    oid = reserve(svc, rid)

    def jobs_run_meanwhile(phase):
        if phase == "before":
            clock.advance(HOLD + 60)
            svc.run_jobs()
            assert check_safety(svc, provider, features) == []

    provider.during = jobs_run_meanwhile
    assert svc.pay(rid(), "c1", oid).ok
    settle(svc)
    provider.during = None
    assert svc.order(oid).status == "paid"
    assert check_safety(svc, provider, features) == []
    assert check_settled(svc, provider, clock.now) == []


def test_declined_after_hold_lapsed_then_expires(svc, rid, provider, clock):
    oid = reserve(svc, rid)
    provider.faults.append("declined")

    def time_passes(phase):
        if phase == "before":
            clock.advance(HOLD + 60)

    provider.during = time_passes
    svc.pay(rid(), "c1", oid)
    settle(svc)
    provider.during = None
    assert svc.order(oid).status == "expired"
    assert svc.stock()["A"] == INITIAL_STOCK


def test_repeated_pay_request_returns_the_stored_response(svc, rid, provider):
    oid = reserve(svc, rid)
    req = rid()
    first = svc.pay(req, "c1", oid)
    settle(svc)
    assert svc.pay(req, "c1", oid) == first
    assert len(provider.charges(oid)) == 1


def test_repeat_while_the_original_is_in_flight_has_no_effect(svc, rid, provider, features):
    oid = reserve(svc, rid)
    req = rid()
    seen = []

    def duplicate_arrives(phase):
        if phase == "after" and not seen:
            seen.append(svc.pay(req, "c1", oid))

    provider.during = duplicate_arrives
    first = svc.pay(req, "c1", oid)
    settle(svc)
    provider.during = None
    assert seen and (seen[0] == first or seen[0].reason == "in_progress")
    assert len(provider.charges(oid)) == 1
    assert check_safety(svc, provider, features) == []


def test_two_pay_requests_for_one_order_charge_once(svc, rid, provider, features):
    oid = reserve(svc, rid)
    second = []

    def second_request(phase):
        if phase == "before" and not second:
            second.append(svc.pay(rid(), "c1", oid))

    provider.during = second_request
    svc.pay(rid(), "c1", oid)
    settle(svc)
    provider.during = None
    assert second[0].ok is False
    assert len(provider.charges(oid)) == 1
    assert check_safety(svc, provider, features) == []
