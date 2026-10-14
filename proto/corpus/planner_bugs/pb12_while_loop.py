"""PB12: uses a while loop (not allowed: planners must terminate)."""


def propose(request, snapshot):
    tries = 0
    while tries < 3:
        tries += 1
    return {"op": "reject", "reason": "noop"}
