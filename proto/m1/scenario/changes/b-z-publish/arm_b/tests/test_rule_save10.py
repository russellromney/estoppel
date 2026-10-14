"""The SAVE10 rule on its own, before it is activated. It runs in an order stage of its own."""

import itertools

import pytest

from checkout.app.config import PRICES
from checkout.app.pricing.pipeline import quote
from checkout.app.pricing.rules.save10 import SAVE10, allocate
from checkout.app.pricing.types import Context, Stage

pytestmark = pytest.mark.t1

STAGES = (Stage(name="order", stacking="best"),)
COUPON = Context(customer="c1", coupon="SAVE10")


@pytest.mark.parametrize("cart, total", [
    ((("A", 1),), 900),
    ((("A", 1), ("C", 2)), 1620),
    ((("B", 2),), 4500),
    ((("D", 1),), 8910),
])
def test_ten_percent_off(cart, total):
    assert quote(cart, COUPON, rules=(SAVE10,), stages=STAGES).total == total


@pytest.mark.parametrize("context", [Context(customer="c1"), Context(customer="c1", coupon="X")])
def test_no_discount_without_the_code(context):
    q = quote((("A", 1),), context, rules=(SAVE10,), stages=STAGES)
    assert q.adjustments == () and q.total == 1000


def test_the_total_is_the_list_total_less_a_tenth_rounded_down_for_small_carts():
    for qtys in itertools.product(range(4), repeat=len(PRICES)):
        cart = tuple((s, q) for s, q in zip(sorted(PRICES), qtys) if q)
        if cart:
            gross = sum(PRICES[s] * q for s, q in cart)
            assert quote(cart, COUPON, rules=(SAVE10,), stages=STAGES).total == gross - gross // 10


@pytest.mark.parametrize("amount, weights, shares", [
    (180, (1000, 800), (100, 80)),
    (1, (3, 3, 3), (1, 0, 0)),
    (2, (1, 1, 1), (1, 1, 0)),
    (0, (0, 5), (0, 0)),
    (3, (0, 10, 20), (0, 1, 2)),
])
def test_allocation_is_exact_and_proportional(amount, weights, shares):
    assert allocate(amount, weights) == shares
