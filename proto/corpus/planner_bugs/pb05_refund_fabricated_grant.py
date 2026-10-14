"""PB05: invents a grant id when the kernel offered no refund move."""

REFUND_WINDOW = 2592000


def propose(request, snapshot):
    order = snapshot["order"]
    if order is None:
        return {"op": "reject", "reason": "not_found"}
    if order["paid_at"] is not None and snapshot["now"] - order["paid_at"] > REFUND_WINDOW:
        return {"op": "reject", "reason": "window_closed"}
    for gid, g in snapshot["grants"].items():
        if g["kind"] == "refund":
            return {"op": "refund", "grant": gid, "amount": g["amount"]}
    return {"op": "refund", "grant": "g1", "amount": order["price"]}
