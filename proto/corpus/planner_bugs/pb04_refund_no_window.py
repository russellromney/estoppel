"""PB04: refunds paid orders without checking the 30-day window."""


def propose(request, snapshot):
    order = snapshot["order"]
    if order is None:
        return {"op": "reject", "reason": "not_found"}
    if order["status"] != "paid":
        return {"op": "reject", "reason": "not_refundable"}
    for gid, g in snapshot["grants"].items():
        if g["kind"] == "refund":
            return {"op": "refund", "grant": gid, "amount": g["amount"]}
    return {"op": "reject", "reason": "no_grant"}
