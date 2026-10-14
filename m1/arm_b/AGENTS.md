# Working on the checkout service (arm B)

Requirements are in [`../REQUIREMENTS.md`](../REQUIREMENTS.md).

The code has two parts:

| Part | Where | What it does |
|---|---|---|
| **Core** | `checkout/core/` | Holds the facts (orders, stock, payments) and decides whether a proposed plan is allowed. It is the only code that changes state or calls the payment provider. |
| **Periphery** | everything else in `checkout/` | Business rules and workflows. A workflow reads a snapshot and *proposes* a plan; the core commits it or refuses it. |

Most features belong in the periphery. Change the core only when a feature needs a new kind of fact or move. Core changes rerun the core's checks and affect every feature.

## Layout

| File | Contents |
|---|---|
| `checkout/core/facts.py` | Immutable facts: `Quote`, `Order`, `Payment`, `Snapshot` |
| `checkout/core/moves.py` | The plan language: `OpenOrder`, `StartCharge`, `StartRefund`, `Release` |
| `checkout/core/authority.py` | Which request kinds may propose which moves, on which orders |
| `checkout/core/commit.py` | Checks a plan and applies all of it or none of it |
| `checkout/core/runtime.py` | Requests (idempotent by `request_id`), jobs, provider calls and reconciliation |
| `checkout/core/api.py` | **The only core module the periphery may import** |
| `checkout/app/workflows.py` | One pure `propose_*` function per request, plus responses |
| `checkout/app/service.py` | The public interface; it runs workflows through the runtime |
| `checkout/app/pricing/` | The pricing pipeline (see below) |
| `checkout/app/policies.py` | Hold time and refund window |
| `checkout/app/status.py` | Order status, derived from facts |
| `checkout/app/config.py` | Catalog and settings |

## Pricing

Pricing is a pipeline of rules, run in stages.

- **A rule** is a pure function that returns an amount for each line, negative for a discount. Put each rule in its own module under `pricing/rules/`, then activate it by adding it to `RULES` in `pricing/rules/__init__.py`.
- **`pricing/composition.py` holds every decision about how rules combine:**
  - the stages and their order;
  - each stage's stacking policy: all apply, the best one wins, or exclusive;
  - the properties every quote must have.

  Read it before adding a rule. Adding a rule to an existing stage is a local change. Adding a stage, or changing an order, a policy or a property, is a joint decision: say so in the commit message.

## Rules for periphery code

`boundary.py` enforces these:
- import only `checkout.core.api` from the core;
- do not read the clock or randomness, and do no I/O. The time is `snapshot.now`;
- no reflection, no mutable module-level or class-level state, and no private attributes of other objects.

## Tests

Every test file is marked with its tier.

| Tier | Files | What it covers |
|---|---|---|
| `t1` | `test_items`, `test_pricing`, `test_composition`, `test_policies`, `test_status`, `test_workflows`, `test_boundary` | Periphery rules and workflows. Workflows are pure, so their tests build snapshots from facts (`conftest.order_fact`). |
| `t2` | `test_core_commit`, `test_core_runtime`, `test_core_exhaustive` | Core moves with generated plans. The exhaustive test explores every state of a small world. |
| `t3` | `test_core_sim`, `core_sim.py` | Seeded core simulation with generated plans, provider faults and interleavings |
| `t4` | `test_journeys` | End-to-end journeys through the public interface |

Core tests never use the real rules or workflows, so periphery changes do not rerun them.

Commands, from this directory:

```bash
uv run python boundary.py    # the boundary lint
uv run pytest --testmon      # tests affected by your change
uv run pytest                # everything
```

**CI** runs the boundary lint, then `pytest --testmon` against the main branch's testmon data. A change merges when both pass.

## Adding a feature

1. Add or change the rule or policy, with T1 tests.
2. If a workflow changes, add T1 tests for its decisions.
3. If you need a new kind of fact or move, change the core, with T2 tests and an extension of `core_sim.py`.
4. Add or update a journey in `test_journeys.py`.
