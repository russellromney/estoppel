"""Reserve every requested item at list price, or reject."""


def wanted_items(request, catalog):
    wanted = {}
    for line in request["items"]:
        sku = line[0]
        qty = line[1]
        if sku not in catalog or qty <= 0:
            return None
        wanted[sku] = wanted.get(sku, 0) + qty
    return wanted


def propose(request, snapshot):
    grants = [gid for gid, g in snapshot["grants"].items() if g["kind"] == "reserve"]
    if not grants:
        return {"op": "reject", "reason": "no_grant"}
    catalog = snapshot["catalog"]
    wanted = wanted_items(request, catalog)
    if wanted is None:
        return {"op": "reject", "reason": "bad_item"}
    for sku, qty in wanted.items():
        if catalog[sku]["stock"] < qty:
            return {"op": "reject", "reason": "out_of_stock"}
    price = sum(catalog[sku]["price"] * qty for sku, qty in wanted.items())
    return {"op": "reserve", "grant": grants[0], "items": sorted(wanted.items()), "price": price}
