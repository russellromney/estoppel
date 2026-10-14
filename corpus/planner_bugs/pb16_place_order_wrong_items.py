"""PB16: reserves SKU A in the requested total quantity, whatever was requested."""


def propose(request, snapshot):
    grants = [gid for gid, g in snapshot["grants"].items() if g["kind"] == "reserve"]
    if not grants:
        return {"op": "reject", "reason": "no_grant"}
    catalog = snapshot["catalog"]
    total = 0
    for sku, qty in request["items"]:
        if sku not in catalog or qty <= 0:
            return {"op": "reject", "reason": "bad_item"}
        total += qty
    if catalog["A"]["stock"] < total:
        return {"op": "reject", "reason": "out_of_stock"}
    return {"op": "reserve", "grant": grants[0], "items": [("A", total)],
            "price": catalog["A"]["price"] * total}
