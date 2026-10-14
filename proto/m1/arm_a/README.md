# Arm A: conventional design

Arm A is the baseline. It is meant to be the service a competent team would write today, gated by a real test-selection tool (pytest-testmon). Agent instructions are in [AGENTS.md](AGENTS.md).

## Choices a reviewer should challenge

These choices affect the comparison with arm B. Each one is stated so it can be argued with before arm B exists.

1. **Pricing is a direct call from the `place_order` handler.** It is not an injected dependency. Every test that places an order therefore runs pricing. That includes the T3 simulation and most journeys.
   - A team that injects a pricer, and stubs it in T3, would run less for a pricing change.
   - But a stubbed pricer means T3 never checks real prices against the handlers.
   - Arm B's proposal is a structural version of that separation, where the core enforces price bounds for any plan. If you think injected pricing is the norm, arm A should change before arm B is built.

2. **Persistence is an in-memory store, and each method is atomic.** The only point where other work can interleave is a provider call. A database-backed service has more interleaving points, between reads and writes in separate transactions. This favours arm A: it has fewer races to handle.

3. **Provider calls are synchronous inside request handlers,** with a reconciliation job for unknown outcomes. This is common.
   - The alternative is an outbox, where handlers record the call and a worker sends it. It is closer to arm B's asynchronous effects.
   - The acceptance suite accepts either style.

4. **T3 size was chosen.** It is 300 seeds × 200 steps, so T3 is the dominant tier, as integration and concurrency tests usually are.

   | Tier | Tests | Time |
   |---|---|---|
   | T1 | 30 | 0.34 s |
   | T2 | 36 | 0.12 s |
   | T3 | 301 | 3.9 s |
   | T4 | 7 | 0.10 s |

   The ratio is a parameter, so the comparison will report tests and named obligations as well as seconds.

5. **T2 tests seed orders directly** with `make_order`, so pay, refund and job tests do not run pricing. This is the strong-conventional choice. Writing those tests through `place_order` would make arm A rerun more on pricing changes.

## How strong the suite is

`uv run python checks/planted_bugs.py`, run from `m1/`, plants 14 bugs in a copy of arm A. Arm A's own suite catches all 14. The held-out acceptance suite catches 13.

The 14th planted bug retries a timed-out call with a new key. That is harmless under the shared fault model, because a lost request never arrives later. Arm A's suite still catches it, because a test pins the key.

The bugs cover:
- the charge time;
- idempotency, including a repeat while the original is in flight;
- the hold check at pay time;
- stock release on expiry;
- the refund window, both its boundary and ignoring it entirely;
- reconciling an in-flight call;
- declined refunds;
- charge attempt keys;
- pricing;
- tenant scoping of refunds;
- expiring orders that are being paid.

**One bug is caught only by T3:** `reconcile_in_flight`, where a job run during an in-flight call settles that call twice.

## A requirements bug found by T3

Arm A's simulation found that requirement B2 was wrong as first written. It said every refund must be *applied* within 30 days of the charge. But a refund accepted on day 29 can be applied after day 30, if its request is delayed or retried.

B2 now refers to when the service accepted the refund. See [`../acceptance/CHANGES.md`](../acceptance/CHANGES.md).

## Gate behaviour

- **The gate is `uv run pytest --testmon`, run from this directory.**
- **Coverage overhead.** A full run with testmon recording takes about 12 s, against 4.2 s without coverage.
- **No change selects nothing.** With no change, testmon selects 0 tests.
- **testmon needs pytest's cache plugin.** With `-p no:cacheprovider` it fails with an internal error.

The measured comparison has not been run yet. It comes after the predictions are committed.
