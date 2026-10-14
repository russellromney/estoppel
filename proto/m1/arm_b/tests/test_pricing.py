"""The pricing pipeline's mechanics, with made-up rules. Real rules are tested in their own files."""

import pytest
from pydantic import ValidationError

from checkout.app.pricing.pipeline import CompositionError, list_price_quote, quote
from checkout.app.pricing.types import Context, Rule, Stage

pytestmark = pytest.mark.t1

CTX = Context(customer="c1")
CART = (("A", 2), ("C", 3))


def flat(name, stage, amount):
    """A rule that takes `amount` off the first line."""
    return Rule(name=name, stage=stage, apply=lambda cart, q, ctx: (-amount,) + (0,) * (len(cart) - 1))


def test_list_price():
    q = quote(CART, CTX, rules=(), stages=(Stage(name="item", stacking="all"),))
    assert q.total == 2 * 1000 + 3 * 400 and q.adjustments == ()
    assert q == list_price_quote(CART)


def test_all_stacking_applies_every_rule():
    stages = (Stage(name="s", stacking="all"),)
    q = quote(CART, CTX, rules=(flat("a", "s", 100), flat("b", "s", 50)), stages=stages)
    assert [a.rule for a in q.adjustments] == ["a", "b"] and q.total == 3200 - 150


def test_best_stacking_keeps_the_largest_discount():
    stages = (Stage(name="s", stacking="best"),)
    q = quote(CART, CTX, rules=(flat("a", "s", 100), flat("b", "s", 150)), stages=stages)
    assert [a.rule for a in q.adjustments] == ["b"]


def test_best_stacking_tie_goes_to_the_first_registered():
    stages = (Stage(name="s", stacking="best"),)
    q = quote(CART, CTX, rules=(flat("a", "s", 100), flat("b", "s", 100)), stages=stages)
    assert [a.rule for a in q.adjustments] == ["a"]


def test_exclusive_stage_refuses_two_rules_at_once():
    stages = (Stage(name="s", stacking="exclusive"),)
    with pytest.raises(CompositionError):
        quote(CART, CTX, rules=(flat("a", "s", 100), flat("b", "s", 100)), stages=stages)
    assert quote(CART, CTX, rules=(flat("a", "s", 100),), stages=stages).total == 3100


def test_rules_in_one_stage_see_the_quote_from_the_stage_start():
    seen = []

    def spy(cart, q, ctx):
        seen.append(q.total)
        return None

    stages = (Stage(name="first", stacking="all"), Stage(name="second", stacking="all"))
    rules = (flat("a", "first", 100), Rule(name="spy1", stage="first", apply=spy),
             Rule(name="spy2", stage="second", apply=spy))
    quote(CART, CTX, rules=rules, stages=stages)
    assert seen == [3200, 3100]


def test_a_rule_that_does_not_apply_leaves_no_adjustment():
    stages = (Stage(name="s", stacking="all"),)
    zero = Rule(name="zero", stage="s", apply=lambda cart, q, ctx: (0, 0))
    assert quote(CART, CTX, rules=(zero,), stages=stages).adjustments == ()


def test_undeclared_stage_is_an_error():
    with pytest.raises(CompositionError):
        quote(CART, CTX, rules=(flat("a", "nowhere", 1),), stages=(Stage(name="s", stacking="all"),))


def test_a_rule_cannot_price_a_line_below_zero():
    stages = (Stage(name="s", stacking="all"),)
    with pytest.raises(ValidationError):
        quote(CART, CTX, rules=(flat("a", "s", 5000),), stages=stages)
