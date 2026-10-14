"""Full refund of a paid order within 30 days of payment."""

REFUND_WINDOW = 2592000  # 30 days in seconds


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
            return {"op": "refund", "grant": gid, "amount": g["amount"]}
    return {"op": "reject", "reason": "no_grant"}
