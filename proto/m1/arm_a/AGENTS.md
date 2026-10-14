# Working on the checkout service

This is a conventional Python service. Requirements are in [`../REQUIREMENTS.md`](../REQUIREMENTS.md).

## Layout

| File | Contents |
|---|---|
| `checkout/config.py` | Catalog prices, stock and policy settings |
| `checkout/models.py` | `Order`, `Payment`, `Outcome` and idempotency records (pydantic) |
| `checkout/pricing.py` | Pricing rules |
| `checkout/policies.py` | Time-based rules: reservation hold and refund window |
| `checkout/validation.py` | Request validation |
| `checkout/store.py` | Persistence. It is in memory and stands in for a database; each method is atomic. |
| `checkout/gateway.py` | Payment provider client |
| `checkout/service.py` | Request handlers, background jobs and read views |

## Rules

- **Business rules live in `pricing.py`, `policies.py` and `validation.py`,** not in handlers.
- **Every provider call goes through `PaymentGateway`** and a `Payment` record with a stable idempotency key. A retry of the same call reuses its key. A new attempt gets a new key, and only after the previous attempt was declined.
- **Nothing is held across a provider call.** Other requests and jobs can run while a call is in flight, so re-read the order after the call.
- **Requests are idempotent by `request_id`** (`CheckoutService._once`).
- **Time comes only from the injected clock.**

## Tests

Every test file is marked with its tier.

| Tier | Files | What it covers |
|---|---|---|
| `t1` | `test_pricing.py`, `test_policies.py`, `test_validation.py` | Business rules: examples, and properties with hypothesis |
| `t2` | `test_place_order.py`, `test_pay.py`, `test_refund.py`, `test_jobs.py` | One operation's state transitions. Orders are seeded with the `make_order` fixture. |
| `t3` | `test_simulation.py`, `simulation.py` | Seeded concurrent traffic with payment faults. Invariants are checked after every step and inside every provider call. |
| `t4` | `test_journeys.py` | End-to-end journeys through the public interface |

Commands, from this directory:

```bash
uv run pytest --testmon      # tests affected by your change (what CI runs)
uv run pytest                # everything
uv run pytest -m t3          # one tier
```

**CI** runs `pytest --testmon` against the main branch's testmon data. A change merges when the selected tests pass.

## Adding a feature

1. Change the rule module, and add T1 examples and properties.
2. If a handler changes, add T2 tests for its transitions.
3. If payment flows or concurrency change, extend the invariants in `tests/simulation.py`.
4. Add the feature's journeys in a new file, `tests/test_journeys_<feature>.py`, so that concurrent changes do not edit the same file.
