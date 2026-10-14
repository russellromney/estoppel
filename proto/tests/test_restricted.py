import pytest

from app import restricted
from app.runtime import find_planner, load_planner


@pytest.mark.parametrize("name", ["place_order_v1", "pay_v1", "refund_v1"])
def test_v1_planners_are_in_the_subset(name):
    load_planner(name)


@pytest.mark.parametrize("name,msg", [
    ("pb12_while_loop", "While"),
    ("pb13_imports_time", "Import"),
])
def test_bug_planners_rejected_statically(name, msg):
    with pytest.raises(restricted.RestrictionError, match=msg):
        restricted.validate(find_planner(name).read_text())


@pytest.mark.parametrize("src,msg", [
    ("def propose(request, snapshot):\n    return propose(request, snapshot)\n", "recursion"),
    ("def propose(request, snapshot):\n    return request.__class__\n", "underscore"),
    ("def propose(request, snapshot):\n    return open('x')\n", "open"),
    ("x = 1\ndef propose(request, snapshot):\n    return x\n", "UPPER_CASE"),
    ("def propose(request, snapshot):\n    global Y\n    return 1\n", "Global"),
    ("def propose(request, snapshot):\n    return snapshot.now\n", "method call"),
    ("def propose(request, snapshot):\n    return helper()\ndef helper():\n    return 1\n", "helper"),
])
def test_subset_rejections(src, msg):
    with pytest.raises(restricted.RestrictionError, match=msg):
        restricted.validate(src)


def test_snapshots_are_frozen():
    src = "def propose(request, snapshot):\n    snapshot['grants'].update({'x': 1})\n    return {}\n"
    planner = restricted.load("t", src)
    with pytest.raises(AttributeError):
        planner.propose(restricted.freeze({}), restricted.freeze({"grants": {}}))


def test_bounded_range():
    src = "def propose(request, snapshot):\n    return sum(range(10 ** 9))\n"
    planner = restricted.load("t", src)
    with pytest.raises(ValueError):
        planner.propose({}, {})
