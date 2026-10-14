"""PB13: reads ambient time (not allowed: planners are pure)."""

import time


def propose(request, snapshot):
    if time.time() > 0:
        return {"op": "reject", "reason": "noop"}
    return {"op": "reject", "reason": "noop"}
