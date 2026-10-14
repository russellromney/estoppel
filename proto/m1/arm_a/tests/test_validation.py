import pytest

from checkout.config import PRICES
from checkout.validation import parse_items

pytestmark = pytest.mark.t1


@pytest.mark.parametrize("items", [
    [], None, "A", [("Z", 1)], [("A", 0)], [("A", -2)], [("A", True)], [("A", 1.0)],
    [("A", "1")], [("A",)], [("A", 1, 2)], [(["A"], 1)], [("A", 1), ("Z", 1)],
])
def test_invalid_items(items):
    assert parse_items(items, PRICES) is None


def test_lines_are_combined_by_sku():
    assert parse_items([("B", 1), ("A", 2), ("A", 1)], PRICES) == {"A": 3, "B": 1}


def test_lists_and_tuples_are_both_accepted():
    assert parse_items([["A", 1]], PRICES) == parse_items((("A", 1),), PRICES) == {"A": 1}
