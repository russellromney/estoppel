import pytest
from hypothesis import given
from hypothesis import strategies as st

from checkout.config import PRICES
from checkout.pricing import order_total

pytestmark = pytest.mark.t1

lines = st.dictionaries(st.sampled_from(sorted(PRICES)), st.integers(1, 6), min_size=1)


@pytest.mark.parametrize("lines, total", [
    ({"A": 1}, 1000),
    ({"A": 2}, 2000),
    ({"A": 3}, 2000),
    ({"A": 4}, 3000),
    ({"A": 6}, 4000),
    ({"A": 2, "B": 1}, 4500),
    ({"C": 6, "D": 1}, 1600 + 9900),
])
def test_examples(lines, total):
    assert order_total(lines, PRICES) == total


@given(lines)
def test_total_is_within_zero_and_list_total(lines):
    total = order_total(lines, PRICES)
    assert 0 <= total <= sum(PRICES[s] * q for s, q in lines.items())


@given(lines, st.sampled_from(sorted(PRICES)))
def test_adding_a_unit_never_lowers_the_total(lines, sku):
    more = dict(lines, **{sku: lines.get(sku, 0) + 1})
    assert order_total(more, PRICES) >= order_total(lines, PRICES)


@given(lines)
def test_total_is_additive_across_skus(lines):
    assert order_total(lines, PRICES) == sum(order_total({s: q}, PRICES) for s, q in lines.items())


@given(lines)
def test_every_third_unit_of_a_sku_is_free(lines):
    assert order_total(lines, PRICES) == sum(PRICES[s] * (q - q // 3) for s, q in lines.items())
