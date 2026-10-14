# Arm B: design notes

Arm B implements the same requirements as arm A. Its business logic *proposes* plans, and a small core *decides* whether to allow them. [`AGENTS.md`](AGENTS.md) is the guide for working on it. This file records design choices for review.

## Choices worth challenging

- **The core knows orders, but not statuses.** An order is an accepted quote, the stock held for it, and the payments made for it. Status (`reserved`, `paying`, and so on) is derived in `app/status.py`. The core's rules are stated in facts:
  - a charge needs held stock whose hold has not lapsed, and no live charge;
  - a refund is per line, up to what is left on the line, counting refunds in flight;
  - stock is released only while no charge is in flight or applied.
- **Ownership is core authority.** A customer's snapshot contains only that customer's order, so tenant scoping cannot be forgotten in a workflow. Eligibility beyond ownership, such as "only reserved orders can be paid", is periphery policy.
- **The core rechecks what the periphery checks.** For example, the pay workflow refuses a lapsed hold, and the core also refuses a charge on one. A periphery bug that would be unsafe becomes a refused plan (`PlanRejected`), not a wrong state. A periphery bug that is merely wrong, such as a price, is not caught by the core.
- **Quotes carry per-line amounts.** Each pricing rule's adjustment is allocated to lines, and the charge and every refund are recorded per line. This is the only part of the core added with later features in mind. Item-level refunds need it.
- **Not built:** budgets (shared limits such as coupon redemptions) and quote conditions. The coupon change will need them, so it will cross the core boundary.
- **One open order per plan, and each order at most once per plan.** This keeps "check everything, then apply everything" simple. A feature that needs more would change the core.

## Suite strength

`checks/planted_bugs.py b` plants 16 bugs:
- **The 13 that have arm A equivalents:** both arm B's own suite and the acceptance suite catch all of them.
- **The 3 core-only bugs:** the core accepts a move it should refuse. Only the core's own tests catch these, because a correct periphery never proposes such a move.

## Timings

| Tier | Tests | Time |
|---|---|---|
| T1 | 85 | 0.2 s |
| T2 | 40 | 1.1 s (the exhaustive test explores 4,639 states and 20,389 moves) |
| T3 | 302 | 5.2 s |
| T4 | 8 | 0.2 s |
