"""PB08: emits a negative quantity for multi-unit lines (sign bug)."""


def propose(request, snapshot):
    grants = [gid for gid, g in snapshot["grants"].items() if g["kind"] == "reserve"]
    if not grants:
        return {"op": "reject", "reason": "no_grant"}
    catalog = snapshot["catalog"]
    wanted = {}
    for sku, qty in request["items"]:
        if sku not in catalog or qty <= 0:
            return {"op": "reject", "reason": "bad_item"}
        wanted[sku] = wanted.get(sku, 0) + qty
    for sku, qty in wanted.items():
        if catalog[sku]["stock"] < qty:
            return {"op": "reject", "reason": "out_of_stock"}
    lines = []
    for sku, qty in sorted(wanted.items()):
        if qty > 1:
            lines.append((sku, 1 - qty))
        else:
            lines.append((sku, qty))
    price = sum(catalog[sku]["price"] * qty for sku, qty in wanted.items())
    return {"op": "reserve", "grant": grants[0], "items": lines, "price": price}
