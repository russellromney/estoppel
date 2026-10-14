"""The b2g1 rule on its own, before it is activated."""

import pytest

from checkout.app.pricing.composition import STAGES
from checkout.app.pricing.pipeline import quote
from checkout.app.pricing.rules.b2g1 import B2G1
from checkout.app.pricing.types import Context

pytestmark = pytest.mark.t1

CTX = Context(customer="c1")


@pytest.mark.parametrize("cart, total", [
    ((("A", 1),), 1000),
    ((("A", 2),), 2000),
    ((("A", 3),), 2000),
    ((("A", 4),), 3000),
    ((("A", 6),), 4000),
    ((("A", 3), ("C", 3)), 2000 + 800),
    ((("B", 1), ("D", 2)), 2500 + 2 * 9900),
])
def test_every_third_unit_of_a_sku_is_free(cart, total):
    assert quote(cart, CTX, rules=(B2G1,), stages=STAGES).total == total


def test_the_discount_is_on_the_line_it_came_from():
    q = quote((("A", 3), ("C", 1)), CTX, rules=(B2G1,), stages=STAGES)
    [adjustment] = q.adjustments
    assert adjustment.rule == "b2g1" and adjustment.per_line == (-1000, 0)
    assert q.line_totals() == (2000, 400)


def test_no_discount_below_three_units():
    q = quote((("A", 2), ("B", 1)), CTX, rules=(B2G1,), stages=STAGES)
    assert q.adjustments == () and q.total == 4500
