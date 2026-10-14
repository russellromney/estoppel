"""Held-out acceptance suite. It is run only by the audit, never by an arm's gate.

    pytest acceptance --arm a --features b2g1
"""

import importlib
import sys
from pathlib import Path

import pytest

from world import Clock, Provider

M1 = Path(__file__).resolve().parent.parent
ARMS = {"a": "arm_a", "b": "arm_b", "c": "arm_c"}
FEATURES = {"b2g1", "category_windows", "coupons", "partial_refunds"}


def pytest_addoption(parser):
    parser.addoption("--arm", default="a", choices=sorted(ARMS))
    parser.addoption("--features", default="", help="comma-separated: b2g1, category_windows, coupons, partial_refunds")


@pytest.fixture(scope="session")
def features(request) -> frozenset[str]:
    raw = request.config.getoption("--features")
    names = frozenset(f for f in raw.split(",") if f)
    unknown = names - FEATURES
    if unknown:
        raise pytest.UsageError(f"unknown features {sorted(unknown)}")
    return names


@pytest.fixture(autouse=True)
def _feature_gate(request, features):
    for mark in request.node.iter_markers("feature"):
        if mark.args[0] not in features:
            pytest.skip(f"feature {mark.args[0]} not in force")
    for mark in request.node.iter_markers("without_feature"):
        if mark.args[0] in features:
            pytest.skip(f"superseded by feature {mark.args[0]}")


@pytest.fixture(scope="session")
def build(request):
    arm_dir = M1 / ARMS[request.config.getoption("--arm")]
    sys.path.insert(0, str(arm_dir))
    return importlib.import_module("checkout").build


@pytest.fixture
def clock():
    return Clock(0)


@pytest.fixture
def provider(clock):
    return Provider(clock)


@pytest.fixture
def svc(build, clock, provider):
    return build(clock, provider)


class Ids:
    def __init__(self):
        self.n = 0

    def __call__(self) -> str:
        self.n += 1
        return f"req-{self.n}"


@pytest.fixture
def rid():
    return Ids()
