"""Coupons in the place-order workflow and the order view."""

import pytest
from conftest import order_fact, snapshot

from checkout.app import workflows as wf
from checkout.app.coupons import coupon_budget, coupon_of, known_coupon
from checkout.app.views import view
from checkout.core.moves import OpenOrder
from spec import Response

pytestmark = pytest.mark.t1

BUDGET = coupon_budget("SAVE10")
AVAILABLE = {BUDGET: 3}


def reason(result):
    assert isinstance(result, Response) and not result.ok
    return result.reason


def test_a_coupon_order_draws_one_redemption():
    [move] = wf.propose_place_order("c1", [("A", 1)], snapshot(budgets=AVAILABLE), "SAVE10").moves
    assert isinstance(move, OpenOrder) and move.budgets == (BUDGET,)


def test_an_order_without_a_coupon_draws_nothing():
    [move] = wf.propose_place_order("c1", [("A", 1)], snapshot(budgets=AVAILABLE)).moves
    assert move.budgets == ()


@pytest.mark.parametrize("code", ["save10", "SAVE20", "", " SAVE10", 10, ["SAVE10"]])
def test_unknown_codes_are_bad_coupons(code):
    assert not known_coupon(code)
    snap = snapshot(budgets=AVAILABLE)
    assert reason(wf.propose_place_order("c1", [("A", 1)], snap, code)) == "bad_coupon"


@pytest.mark.parametrize("items, budgets, code, expected", [
    ([], AVAILABLE, "nope", "bad_items"),
    ([("A", 7)], AVAILABLE, "nope", "bad_coupon"),
    ([("A", 7)], {BUDGET: 0}, "SAVE10", "out_of_stock"),
    ([("A", 1)], {BUDGET: 0}, "SAVE10", "coupon_used_up"),
])
def test_checks_come_in_the_required_order(items, budgets, code, expected):
    assert reason(wf.propose_place_order("c1", items, snapshot(budgets=budgets), code)) == expected


def test_the_view_shows_the_coupon():
    assert view(order_fact(budgets=(BUDGET,))).coupon == "SAVE10"
    assert view(order_fact()).coupon is None
    assert coupon_of(order_fact(budgets=("other",))) is None
