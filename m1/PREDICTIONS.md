# M1 predictions

These are committed after arm A (`3bed8ff`) and before any arm B code exists. They follow sections 4 and 5 of the [Prototype plan](../../reports/Prototype%20plan.md).

Results will be recorded next to each prediction, without editing the prediction.

## Terms

| Term | Meaning |
|---|---|
| **Core** | Arm B's `checkout/core/`: facts, general operations, validation and effects |
| **Shared code** | In arm A: `service.py`, `store.py`, `models.py` and `gateway.py`. That is, code every request path runs through. |
| **Local** | A change that adds a rule or policy without editing a file that holds a cross-feature decision |
| **Joint** | A change that edits such a file. In arm B, that is `composition.py`, or a plan field the core requires. |
| **Surfaced** | The feature cannot be implemented without stating the interaction decision somewhere a reviewer would look. "Silent" means the decision is implicit in code order or in a default. |

**Classes for a feature in arm B:**

| Class | Meaning |
|---|---|
| P | Periphery only: rules, policies, workflows, composition and config |
| A | P, plus a new entry in the core's authority table (who may request which operation), with no core logic change |
| C | Core logic change: a new primitive or operation, or changed semantics |

## 1. The dev sequence

| Feature | | Arm A | Arm B |
|---|---|---|---|
| F1 buy two, get one free | **Code** | Edits `pricing.py` only | **P, local.** A new rule module in the item stage, plus one line in the rule registry. |
| | **Gate (testmon)** | Selects pricing T1, the 5 `test_place_order.py` T2 tests, **all 301 T3 tests** and all 7 T4 journeys | Selects pricing and workflow T1 and the T4 tests that place orders. **No core T2. No T3.** |
| | **Decisions** | None to surface | None to surface |
| F2 coupon with a shared redemption budget | **Code** | Changes shared code: models, store (redemption counts), handler (coupon argument, release on expiry) and pricing | **P, joint.** A coupon rule, a budget declared in config, the `place_order` workflow (a budget use) and a new order-level stage in `composition.py`. **No core change.** |
| | **Gate** | Selects nearly every T2, T3 and T4 test | Selects T1 and T4. **No core T2. No T3.** |
| | **Decisions** | Whether the coupon applies before or after `b2g1` is **silent**: it is the order of the code. Release on expiry is silent: it lives in the expiry job. | Stacking is **surfaced** by the new stage in `composition.py`. Release on expiry is **decided once by the core** for every budget (uses lapse with their reservation). |
| F3 item-level partial refunds of discounted orders | **Code** | Changes shared code: per-line amounts stored on orders, the refund handler, and how outcomes are recorded | **P, local.** The refund workflow takes per-line amounts from the quote's allocations. **No core change.** |
| | **Gate** | Selects the refund and job T2 tests, all T3 and the refund T4 tests | Selects workflow T1 and refund T4. **No core T2. No T3.** |
| | **Decisions** | Whether a refund restores the coupon is **silent**. How the discount is allocated across returned items is silent. | Restoring the coupon is **surfaced**: the core rejects a refund plan that does not state restore or keep for every budget use. The allocation is explicit in the quote, as each rule allocated it. |

**Prediction about the foresight confound.** If F2 or F3 needs a class C change in arm B, the primitives are wrong. That would happen even though they were designed knowing these features.

## 2. The held-out sample

The held-out features are F02, F04, F06, F07, F08, F10, F12 and F15. They were set aside on 2026-10-13 by seed `20261013`.

**The draw happens after arm B's base is committed:**

```python
import random
random.Random(20261014).sample(["F02", "F04", "F06", "F07", "F08", "F10", "F12", "F15"], 3)
```

**Predicted class for every held-out feature, so that any draw is scored:**

| Feature | Phase 0 kernel (backlog prior) | Arm B | Arm A |
|---|---|---|---|
| F02 tier pricing | contract | **P.** A rule, with the tier as periphery data. A joint stacking decision. | Shared code, if tier data joins the order flow. Stacking is silent. |
| F04 restocking fee | kernel | **P.** Per-line partial refunds already allow it. | The refund handler: shared code |
| F06 refund to store credit | authority, kernel | **C.** A new money destination. | Shared code, plus a new store table |
| F07 purchase limit, 3 per SKU per day | contract or kernel | **P.** A budget keyed by customer, SKU and day. | Shared code: store and handler |
| F08 one-time reservation extension | authority, kernel | **C.** A new hold operation. | Shared code |
| F10 fraud hold before charging | kernel, planner | **C.** A new precondition and an approval authority. | Shared code |
| F12 cancel an unpaid order early | authority | **A.** The release operation exists, but customers need authority to request it. | Shared code: a new handler |
| F15 auto-refund on cancel before shipping | authority, kernel | **C.** New shipping facts. | Shared code |

**Totals.**
- **Arm B:** 3 P, 1 A and 4 C. So 4 of 8 need no core logic change.
- **Phase 0 kernel:** the backlog predicted 2 or 3 of 8 with no kernel logic change. Those are F02, F12 (authority only) and F07 if it is treated as policy.
- **Arm A:** every held-out feature touches shared code.

## 3. Redirect conditions

- **F2 or F3 is class C in arm B.** Then the primitives are wrong; redesign them before the draw.
- **Two or more of the three drawn features are class C in arm B, while arm A's changes are no larger.** Then the boundary is not buying stability in this domain.
- **F2 can be written in arm B without editing `composition.py` and without choosing a stage whose stacking policy is documented.** Then the claim that coupling is explicit fails.
- **The core grows more than the periphery,** measured in lines over F1, F2, F3 and the sample. That is the inner-platform failure.
- **The gate in either arm admits a change that the audit fails.** This is reported in every case, as a soundness failure of that arm's gate.
