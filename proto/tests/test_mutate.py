from app import restricted
from app.runtime import find_planner
from experiments import mutate
from sim.dst import divergence


def test_mutants_are_stable_valid_and_distinct():
    source = find_planner("refund_v1").read_text()
    a, b = mutate.mutants("refund_v1", source), mutate.mutants("refund_v1", source)
    assert [m.id for m in a] == [m.id for m in b]
    assert len({m.source for m in a}) == len(a)
    for m in a:
        restricted.load(m.id, m.source)


def test_guard_deletion_removes_the_check():
    source = find_planner("refund_v1").read_text()
    ms = [m for m in mutate.mutants("refund_v1", source)
          if m.op == "M7" and "REFUND_WINDOW" in m.change]
    assert len(ms) == 1 and "window_closed" not in ms[0].source


def test_divergence_classes():
    reserve = {"op": "reserve", "grant": "g1", "items": [("A", 1)], "price": 1000}
    cheap = dict(reserve, price=0)
    no_stock = {"op": "reject", "reason": "out_of_stock"}
    bad_item = {"op": "reject", "reason": "bad_item"}
    assert divergence(reserve, reserve, True) is None
    assert divergence(bad_item, no_stock, False) is None  # both decline
    assert divergence(cheap, reserve, True) == "accepted"
    assert divergence(reserve, no_stock, True) == "stale"
    assert divergence(reserve, bad_item, True) == "accepted"
    assert divergence(no_stock, reserve, False) == "lost"
    assert divergence({"op": "error"}, reserve, False) == "lost"
    assert divergence(cheap, reserve, False) == "lost_rejected"
    assert divergence(reserve, bad_item, False) == "blocked"
