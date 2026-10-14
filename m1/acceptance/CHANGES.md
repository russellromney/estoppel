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

## 2. Two features added for the scenario: `category_windows` (Y) and `coupons` (Z)

This change was made after arms A and B were committed, and before either arm implemented any feature.

**Why.** The plan's scenario needs two changes that are independent of `b2g1` (X), and one that interacts with them. `partial_refunds` did not fit, and is deferred.

**What changed:**
- `REQUIREMENTS.md` sections 8 and 9, and their constants in `spec.py`. `OrderView` gains `coupon`, which defaults to none.
- New tests: `test_category_windows.py` and `test_coupons.py`.
- `oracle.py`:
  - B2 uses the order's refund window;
  - `expected_price` takes the coupon;
  - C1 is checked when `coupons` is in force.
- The conformance run sometimes passes a coupon, when `coupons` is in force.

**Left undecided on purpose.** The requirements do not say how `SAVE10` combines with `b2g1`, or whether a refund returns a redemption. These are the joint decisions the scenario's Z must surface. Until they are made:
- `expected_price` returns none for a coupon order with 3 or more units of a SKU while `b2g1` is in force, and B1 is not checked for that order;
- C1 does not count refunded orders;
- no test refunds a coupon order.

**Checked.** Base runs of both arms are unchanged: 89 passed, with the new feature tests skipped. The new tests were run against a throwaway implementation of both features in a scratch copy of arm A. It passed all 120 tests. The copy was then deleted. Six bugs planted in it were all caught:
- expiry not returning the redemption;
- a per-customer budget;
- an off-by-one budget;
- a case-insensitive code;
- the longest window instead of the shortest;
- an exclusive window.
