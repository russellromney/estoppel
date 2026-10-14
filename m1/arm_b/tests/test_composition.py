"""The declared composition properties, checked exhaustively over small carts and every subset
of the active rules."""

import itertools

import pytest

from checkout.app.config import PRICES
from checkout.app.pricing.composition import PROPERTIES, STAGES
from checkout.app.pricing.pipeline import quote
from checkout.app.pricing.rules import RULES
from checkout.app.pricing.types import Context

pytestmark = pytest.mark.t1

MAX_QTY = 4
CONTEXTS = (Context(customer="c1"),)


def small_carts():
    skus = sorted(PRICES)
    for qtys in itertools.product(range(MAX_QTY + 1), repeat=len(skus)):
        cart = tuple((s, q) for s, q in zip(skus, qtys) if q)
        if cart:
            yield cart


def rule_subsets():
    for n in range(len(RULES) + 1):
        yield from itertools.combinations(RULES, n)


def test_every_rule_uses_a_declared_stage():
    declared = {stage.name for stage in STAGES}
    assert all(rule.stage in declared for rule in RULES)


def test_stage_names_are_unique():
    assert len({s.name for s in STAGES}) == len(STAGES)


@pytest.mark.parametrize("prop", PROPERTIES, ids=lambda p: p.name)
def test_property_holds_for_small_carts_and_every_subset_of_rules(prop):
    for rules, context, cart in itertools.product(list(rule_subsets()), CONTEXTS, small_carts()):
        q = quote(cart, context, rules=rules)
        assert prop.holds(cart, q), (prop.name, [r.name for r in rules], context, cart)
