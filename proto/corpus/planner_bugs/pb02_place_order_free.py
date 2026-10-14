"""PB02: a discount bug prices every order at 0."""


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
    price = sum(catalog[sku]["price"] * qty for sku, qty in wanted.items())
    discount = price
    return {"op": "reserve", "grant": grants[0], "items": sorted(wanted.items()),
            "price": price - discount}
