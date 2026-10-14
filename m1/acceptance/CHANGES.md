# Changes to the acceptance suite after it was first committed

The suite and `REQUIREMENTS.md` were committed in `5717e81`, before any arm existed. Every later change is listed here with its reason.

## 1. B2 is about when a refund was accepted, not when it was applied

This change was made while arm A was being written, before arm A was committed.

**Before.** Every applied refund had to be applied within 30 days of the provider's charge time.

**Problem.** Arm A's own T3 simulation failed on 7 of 300 seeds. In each failure, a refund accepted inside the window was applied after it, because the request was in transit while time passed. A retry after a timeout has the same effect.

Applying a refund late is correct behaviour: the customer was promised the refund. The requirement was wrong.

**After:**
- B2 requires each applied refund to come from a refund request the service accepted while the window was open.
- `REQUIREMENTS.md` section 6 is updated.
- `check_safety` checks B2 only when given the send times of refund requests that were not rejected.
- The conformance run records those send times.
- The explicit refund-window tests in `test_refund.py` are unchanged.

**Detection is unchanged.** `checks/planted_bugs.py` still shows `window_ignored` and `window_exclusive` caught.
