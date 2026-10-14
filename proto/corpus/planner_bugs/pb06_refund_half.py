"""PB06: refunds half the granted amount."""

REFUND_WINDOW = 2592000


def propose(request, snapshot):
    order = snapshot["order"]
    if order is None:
        return {"op": "reject", "reason": "not_found"}
    if order["status"] != "paid":
        return {"op": "reject", "reason": "not_refundable"}
    if snapshot["now"] - order["paid_at"] > REFUND_WINDOW:
        return {"op": "reject", "reason": "window_closed"}
    for gid, g in snapshot["grants"].items():
        if g["kind"] == "refund":
            return {"op": "refund", "grant": gid, "amount": g["amount"] // 2}
    return {"op": "reject", "reason": "no_grant"}
