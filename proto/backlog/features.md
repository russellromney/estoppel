# Feature backlog (pre-registered)

This file was written and committed before any kernel code existed. Each feature carries a predicted classification, taken from S8 of the plan:

| Class | Meaning |
|---|---|
| `planner` | Changes only planner code. |
| `contract` | Changes what the kernel exposes in snapshots, or what a consumer depends on. |
| `authority` | Adds or widens an authorized move or token. |
| `kernel` | Changes kernel invariants, the plan language, or what state means. |

A feature can have several classes. When a feature is implemented, its actual classification is recorded next to the prediction.

**Split.** Seed `20261013` decided which features are held out: `random.Random(20261013).sample(F01..F16, 8)`. The held-out features are F02, F04, F06, F07, F08, F10, F12 and F15. They are not used while designing or tuning the system.

## v0 scope (what the initial app does)

- **Catalog:** four SKUs with list prices in integer cents and an initial stock of 6 each.
- **`place_order(customer, items)`:** all-or-nothing reservation, priced at list price, held for 15 minutes.
- **`pay(customer, order_id)`:** charges the full price through an external payment provider. The provider uses idempotency keys and can fail.
- **`refund(customer, order_id)`:** full refund only, within 30 days of payment, sent to the payer.
- **`tick`:** time advances, and unpaid reservations past their TTL expire and release their stock.

## Backlog

| ID | Split | Feature | Predicted class | Notes on the prediction |
|---|---|---|---|---|
| F01 | dev | Percentage discount codes, one per order | contract | Snapshot must expose the code table. Pricing stays in the planner. |
| F02 | held-out | Customer tier pricing (gold gets 10% off) | contract | Snapshot must expose the customer's tier. |
| F03 | dev | Refund window varies by product category | contract | Snapshot must expose the category. The window is planner policy. |
| F04 | held-out | Restocking fee: 10% withheld on refund | kernel | v0 kernel only allows full refunds. |
| F05 | dev | Partial refunds chosen by the customer | kernel, authority | Refund token becomes "up to a maximum". Refunded-amount state changes. |
| F06 | held-out | Refund to store credit | authority, kernel | New effect and a new destination for money. |
| F07 | held-out | Per-customer purchase limit (3 units per SKU per day) | contract (if policy), kernel (if a hard limit) | Ambiguous on purpose: where should a limit live? |
| F08 | held-out | One-time reservation extension | authority, kernel | Changes expiry semantics and adds a new move. |
| F09 | dev | Partial reservation / backorder | kernel | New order states. Reserved items differ from requested items. |
| F10 | held-out | Fraud hold: orders over $500 need manual approval before charging | kernel, planner | New state, and an approval move for a human. |
| F11 | dev | Buy two, get one free | planner | Pricing only. |
| F12 | held-out | Cancel an unpaid order early | authority | New cancel move that releases stock. |
| F13 | dev | Promo SKUs charged at whole-dollar prices | planner | Pricing only. |
| F14 | dev | Stock across multiple warehouses | kernel | The stock state model changes. |
| F15 | held-out | Auto-refund when a paid order is cancelled before shipping | authority, kernel | Needs shipping state and a composed flow. |
| F16 | dev | Gift purchases: refund goes to the purchaser, receipt to the recipient | authority | Changes recipient semantics. |

**Prior, stated before building.** Of the 16 features:
- 2 are predicted planner-only: F11 and F13.
- 4 are predicted to need only a contract change: F01, F02, F03 and F07 (if F07 is treated as policy).
- 10 are predicted to touch authority or the kernel.

If this holds, kernel churn is the dominant cost in this domain, and the architecture's main benefit must come from making kernel changes cheaper to verify. Isolating changes in planners would not be enough. The domain was chosen for its real invariants, so this backlog may lean toward kernel changes more than a typical product backlog would. That bias is noted here, not corrected for.
