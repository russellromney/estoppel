"""Request validation for order items."""

from collections.abc import Mapping

Cart = tuple[tuple[str, int], ...]


def parse_items(items, catalog: Mapping[str, int]) -> Cart | None:
    """Combine order lines by SKU, sorted by SKU. Returns None if any line is invalid."""
    if not isinstance(items, (list, tuple)) or not items:
        return None
    lines: dict[str, int] = {}
    for line in items:
        if not isinstance(line, (list, tuple)) or len(line) != 2:
            return None
        sku, qty = line
        if not isinstance(sku, str) or sku not in catalog:
            return None
        if type(qty) is not int or qty < 1:
            return None
        lines[sku] = lines.get(sku, 0) + qty
    return tuple(sorted(lines.items()))
