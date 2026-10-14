"""The boundary lint's rules, on small examples. The gate runs the lint itself on the real code."""

import ast

import pytest

from boundary import check_core, check_periphery

pytestmark = pytest.mark.t1


def periphery(source):
    return [message for _, message in check_periphery(ast.parse(source))]


@pytest.mark.parametrize("source", [
    "from checkout.core.commit import State",
    "from checkout.core import runtime",
    "import checkout.core.facts",
    "import time",
    "from datetime import datetime",
    "import random",
    "from world import Clock",
    "x = open('f')",
    "print('hi')",
    "getattr(obj, 'name')",
    "CACHE = {}",
    "SEEN = []",
    "PAIRS = (1, [])",
    "ITEMS = list()",
    "class C:\n    seen = set()",
    "def f():\n    global X",
    "runtime._state",
])
def test_forbidden_in_the_periphery(source):
    assert periphery(source)


@pytest.mark.parametrize("source", [
    "from checkout.core.api import Plan",
    "from checkout.core import api",
    "from types import MappingProxyType\nPRICES = MappingProxyType({'A': 1})",
    "RULES = ()",
    "def f():\n    seen = {}\n    return seen",
    "class C:\n    def f(self):\n        return self._x",
    "x.__class__",
])
def test_allowed_in_the_periphery(source):
    assert periphery(source) == []


def test_core_may_not_import_the_periphery():
    assert check_core(ast.parse("from checkout.app.config import PRICES"))
    assert check_core(ast.parse("from world import Clock")) == []
