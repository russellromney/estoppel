"""Charge the order if the kernel offered a charge move."""


def propose(request, snapshot):
    for gid, g in snapshot["grants"].items():
        if g["kind"] == "charge":
            return {"op": "charge", "grant": gid}
    return {"op": "reject", "reason": "not_payable"}
