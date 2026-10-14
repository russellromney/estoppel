# Prototype plan v5: a general core and a feature sequence

> **Archived.** Superseded by [Prototype plan](../Prototype%20plan.md), which summarises this version in its section 7.

This is the current plan. It is revised in place. Earlier versions are in [`archive/`](.), and section 9 summarises them.

Last revised on 2026-10-14, after the third review. That review argued that the work was shrinking into "well-structured code with smarter test selection". The original aim is larger: change the unit of software development so that agents can make useful changes without repeatedly reopening the whole system.

## 1. The idea

**The product is a programming model that makes independent change dependable.**
- Business logic *proposes* actions.
- A small, stable core *decides* whether they are allowed.
- An agent can then have wide freedom inside a boundary, while the core controls authority over money, inventory and state.

CI gets less work as a consequence: fewer changes interact, and the interactions that remain are visible when the code is written. Typed plans, pure functions, test selection and caching are mechanisms, not the product.

**Two questions decide whether this works:**

1. **Does the core stay stable?** If interesting features keep changing the core, the coordination problem has moved, not shrunk. Whoever understands the core becomes the new bottleneck.

   Our own prior says the risk is real. The [pre-registered backlog](../../proto/backlog/features.md) predicted that 10 of 16 features would touch the Phase 0 kernel or its authority. That kernel holds checkout-specific states. A core built from *general operations* should change less, so this plan tests that.

2. **Do business rules compose?** The core's invariants (no double charge, refunds ≤ payments) do not stop two reasonable promotions from combining into an unintended discount.
   - A tool cannot detect "unintended" without a declared intent.
   - So the model's job is to make every interaction decision explicit, in one place, before code lands, and to check the properties declared there.
   - An agent adding a promotion should be able to find out whether discounts stack, compete, or apply in a defined order, and which rule owns that decision.

## 2. What changed from v4

| v4 | Now |
|---|---|
| Arm C: minimal `newci` (footprints, call recording, early cutoff, evidence store) | **Deferred.** Arm B gets only a boundary lint. Tooling is built when a feature shows a concrete need (section 9). |
| The core holds checkout states and checkout-specific checks | **The core holds facts and general operations:** holds, budgets, a money ledger with allocations, and quotes with conditions. Order status becomes a derived view. |
| Pricing is one function | **Pricing is a pipeline of rules in declared stages,** with the stacking decisions and composition properties in one owned file |
| Changes C1, C1x, C1y and C2, all friendly | **A sequence of increasingly awkward features:** a promotion, a coupon with a shared budget, then item-level partial refunds of discounted orders. After those, a seeded sample of *held-out* features. |
| Headline measure: tests skipped | **Headline measure: where each feature had to go** (core or periphery, local or joint), and whether its interaction decisions were forced into the open. CI work is measured as the consequence. |
| Arm A to be reviewed | **Arm A stays as built** (`3bed8ff`). It is the baseline for every feature. |

## 3. Arm B's design

### 3.1 The core: facts and general operations

| Primitive | Operations | Invariants the core enforces |
|---|---|---|
| Holds on resources | `hold(resource, qty, until)`, `release`, `consume` | Stock is never negative and is conserved |
| Budgets | `consume(budget, key, amount, ref)`, `restore(ref)` | Consumption stays within the cap for each `(budget, key)` |
| Money ledger with allocations | One charge per order, for the accepted quote's total. Refunds are given per line. | Per-line refunds ≤ per-line paid. Total refunds ≤ the charge. Money goes only to the payer. |
| Quotes | Accept a quote: lines, adjustments allocated to lines, and validity conditions | Allocations add up, line totals are ≥ 0, and the conditions hold at commit |
| Authority | Grants issued for each request | A plan uses only the moves offered to it |
| Effects | Provider calls with stable keys, and reconciliation | As in arm A and Phase 0 |

- **Order status is not core state.** It is a view computed from facts: whether stock is held, whether the order was charged, how much was refunded, and whether the hold lapsed.
- **Eligibility is periphery policy.** That covers the refund window and who may pay.
- **The core knows nothing about promotions, coupons, refund windows or statuses.**

**The risk is the inner-platform effect,** where the core grows into a general rules engine or a database inside the app. To guard against it:
- a primitive exists only when a dev feature needs it;
- core size and churn are measured over the whole sequence.

### 3.2 The periphery: rules and their composition

**Pricing is a pipeline.**
- Each rule is a pure function from (cart, quote so far, facts) to adjustments, each allocated to lines.
- Each rule declares its stage.

**`composition.py` owns the interaction decisions:**
- the order of the stages;
- the stacking policy within each stage: all apply, best one wins, or exclusive;
- composition properties, for example "line totals are never negative" or a cap on the combined discount. The cap is a business decision.

**Local and joint changes:**
- **Local:** adding a rule to an existing stage.
- **Joint:** adding a stage, reordering stages, changing a stacking policy or changing a composition property. These all mean editing `composition.py`, so the change is flagged for a joint decision.

An agent reads `composition.py` to learn the existing decisions before adding a promotion. The composition properties are checked exhaustively over small carts and every subset of the active rules.

Other cross-feature decisions are forced the same way: by fields in the plan type. A refund plan must say whether it restores a coupon redemption; it cannot leave the question unstated.

**What is not new here.** Staged discount pipelines are a known pattern in commerce engines. The idea under test is different: using the declared composition to classify changes as local or joint, and to limit what each change reopens.

### 3.3 Enforcing the boundary

A small lint forbids these in periphery code:
- importing core state or effects;
- reading the clock, randomness or I/O;
- keeping mutable state at module level.

Without the lint, "periphery changes cannot reopen core checks" is an assumption, not a property. This keeps the useful part of v4's C1y.

### 3.4 Core guarantees, and how strongly each is supported

These carry over from v4.

| Strength | What it covers |
|---|---|
| Structural | Plans are pydantic tagged unions, and commit is the only path that changes state |
| Bounded-exhaustive | Every primitive operation, over every small state and plan |
| Sampled | Seeded simulation of faults and interleavings with *generated* plans |

Core checks never run the real rules.

## 4. Features

### 4.1 The dev sequence

Both arms implement these, in this order. Requirements and acceptance tests are written before either arm implements a feature.

| ID | Feature | What it forces |
|---|---|---|
| F1 | Buy two, get one free (`b2g1`, already in `REQUIREMENTS.md`) | Pure calculation |
| F2 | Coupon codes with a shared redemption budget across orders. A redemption is held with the reservation and released if the reservation expires. | Shared state, races for the last redemption, and stacking with F1 |
| F3 | Item-level partial refunds for orders that used both discounts. This replaces the amount-based `partial_refunds` in `REQUIREMENTS.md`. | The lasting meaning of an earlier calculation: how a refund is allocated across discounts, and whether a refund restores a coupon redemption |

The shared interface grows to include a coupon argument on `place_order` and an items argument on `refund`. It is gated by feature, as before.

**Interaction decisions.** Examples are whether the coupon applies before or after `b2g1`, and whether a refund returns a coupon redemption. These are business decisions.
- Each feature is first written as a product request *without* them.
- For each arm, the measurement asks: **can the feature be implemented without stating the decision anywhere a reviewer would look?**
  - In arm A I expect yes: the decision is implicit in the order of the code.
  - In arm B I expect no: the decision must go in `composition.py` or in a plan field.
- The decision is then added to `REQUIREMENTS.md` and to the acceptance suite. Tests for interaction decisions are therefore the only acceptance tests written after implementation, and they are labelled as such.

**Foresight.** Arm B's core is designed knowing the dev backlog, as a team with a roadmap would design it. So the dev sequence shows whether the model *expresses* these features naturally. It cannot show whether the core stays stable. The held-out sample does that.

### 4.2 The held-out sample

These features were set aside on 2026-10-13 by seed `20261013` and have not been used in any design:

> F02 tier pricing, F04 restocking fee, F06 refund to store credit, F07 purchase limit, F08 reservation extension, F10 fraud hold, F12 early cancel, F15 auto-refund on cancel

**The draw.** Three are drawn by `random.Random(20261014).sample(held_out, 3)`. The draw happens only after arm B's base is committed, so the core cannot be shaped to fit them. Both arms implement all three.

## 5. Predictions

These are committed to `proto/m1/PREDICTIONS.md` before arm B exists.

### 5.1 The dev sequence

| Feature | Arm A | Arm B |
|---|---|---|
| F1 | Edits `pricing.py`. testmon reruns pricing T1, the T2 tests that place orders, all of T3, and most of T4. | A new rule in the item stage: a local change. Reruns the rule's tests, the composition properties and the T4 tests that order. No core tests. |
| F2 | Changes the models, store, handler and pricing. The stacking order is implicit in the code, and the decision is not surfaced. Reruns nearly everything. | A coupon rule plus a budget instance in config. A new order stage, so a joint decision in `composition.py`. Periphery workflow changes. **No core change.** No core T2 or T3. |
| F3 | Orders gain stored per-line amounts, and the refund handler changes. Whether a refund restores the coupon is implicit. Reruns everything touching refunds, including all of T3. | Refund policy computes per-line amounts from the quote's allocations. Restoring the coupon is a required plan field, so it is surfaced. **No core change.** No core T2 or T3. |

### 5.2 The held-out features

The predicted class of each held-out feature, for the Phase 0 kernel (from the backlog) and for arm B's general core. Classes: P is periphery only; A adds an authority entry with no core logic change; C changes core logic. `PREDICTIONS.md` is the committed version.

| Feature | Phase 0 kernel | Arm B core |
|---|---|---|
| F02 tier pricing | contract | P: a rule, with the tier as periphery data |
| F04 restocking fee | kernel | P: per-line partial refunds already allow it |
| F06 store credit | authority, kernel | C: a new money destination |
| F07 purchase limit | contract or kernel | P: a budget keyed by customer, SKU and day |
| F08 reservation extension | authority, kernel | C: a new hold operation |
| F10 fraud hold | kernel, planner | C: a new precondition and an approval authority |
| F12 early cancel | authority | A: `release` exists, but customers need authority to request it |
| F15 auto-refund on cancel | authority, kernel | C: shipping facts |

**Totals.** For arm B, 4 of 8 are predicted to need no core logic change, against 2 or 3 for the Phase 0 kernel. The three-feature sample checks part of this.

### 5.3 Redirect if

- **F2 or F3 needs a core change in arm B despite foresight.** Then the primitives are wrong. Redesign before drawing the held-out sample.
- **Most of the held-out sample needs core changes in arm B, while arm A needs comparable changes to shared code.** Then the boundary is not buying stability in this domain. Record whether the domain, which is heavy with invariants, is unrepresentative.
- **F2 can be added in arm B without facing the stacking decision.** Then the claim that coupling is made explicit fails.
- **The core grows faster than the periphery across the sequence.** That is the inner-platform failure.

## 6. Measures, for every feature and arm

- **Where the code changed:** core or shared files versus periphery or local files, with lines changed.
- **Interaction decisions:**
  - forced into a designated place before landing;
  - found later by the acceptance suite;
  - or never surfaced.
- **What the gate ran:** tests selected by testmon, and CPU seconds, split by tier.
- **Audit:** the full suite plus the acceptance suite.
- **Core size and churn** over the whole sequence.

**What cannot be measured without fresh agents.** "Does the agent keep escaping into the core?" needs agents that did not design the core. I designed it, so my implementations test only structure.

After F1–F3, a small study with fresh agents would close this gap:
- each agent gets an arm's `AGENTS.md` and a held-out feature request;
- both arms, with a few repeats each.

That study costs API spend and needs your approval first.

## 7. Steps, with stopping points

1. **Predictions.** Commit `PREDICTIONS.md` with sections 5.1–5.3 and the draw procedure.
2. **Arm B's base.** The core primitives, the periphery rules and composition, the boundary lint, and tests T1–T4, with core checks using generated plans. It must pass the base acceptance suite.
   - **Stop for review.**
3. **F2 and F3 requirements.** Write the product requests and their acceptance tests, leaving out the interaction decisions.
4. **The dev sequence.** Implement F1, F2 and F3 in both arms, measuring each. Add the interaction decisions and their tests after each feature.
5. **The held-out sample.** Draw the three features. Write their requirements and acceptance tests, then implement them in both arms.
6. **Report.**
   - **Stop.** The fresh-agent study needs approval.

## 8. Not now

- **The v3 toolchain** (section 9).
- **The concurrency experiment.** Several changes in flight at once, and a merge queue.
- **A larger subject codebase.**

Each is revisited if the feature sequence shows that it is needed.

## 9. History and deferred design

**v2, [Synthesis and prototype plan](Synthesis%20and%20prototype%20plan.md).** It produced Phase 0 in `proto/`:
- a kernel that validates plans from restricted planners;
- an explicit effect model;
- a deterministic closed-loop simulator;
- experiments E1 and E1b.

The main result was that the kernel bounds *safety* but not *harm*. The harmful bugs were business rules inside the kernel's bounds. The second review then found holes: the restricted language was not pure, a malformed plan crashed the kernel, replanning was not idempotent, and refund time was taken from the wrong clock. M1 fixes them.

**v3, [Prototype plan v3](Prototype%20plan%20v3.md).** It proposed `newci`, a toolchain. It was superseded because it risked becoming a better test cache and merge system, and because it postponed the central experiment.

These parts of its design are deferred, not rejected:

| Part | What it is |
|---|---|
| Dialect and lint | Explicit imports, no reflection, effects only through capabilities, frozen data. The boundary lint in 3.3 is the first piece. |
| Definitions and footprints | Hash each top-level definition's normalized syntax tree. A definition's footprint is everything it transitively references. Data files enter through declared resources. |
| Claims and evidence | Store results keyed by footprint hash, environment and seed, and reuse them across branches and agents. A claim's meaning is anchored by the hash of its checker, so a changed checker is a contract change that goes to a human. Soundness is audited by occasional full re-runs. |
| Change kinds | `add`, `refactor`, `modify` and `gc`. A refactor is verified by early cutoff: re-evaluate the changed definitions on the calls recorded during earlier checks. |
| Landing without a queue | Store changes as operations on definitions, including renames. Replay them onto main, and re-run only the claims whose footprints overlap concurrent changes. Leases at definition level are optional. |
| Risk tags and review routing | `risk:money`, `risk:auth`, etc. spread to everything that reaches the tagged code. They decide which changes a human sees before landing. |
| The lab | Change streams, baselines, ablations and pre-registered criteria |

**When to build them.** Build these when the feature sequence or a later concurrency experiment shows the gate re-running work that the structure makes avoidable, or merge-queue costs dominating.

**v4, [Prototype plan v4](Prototype%20plan%20v4.md).** It narrowed the work to milestone M1: arms A, B and C on four changes. Arm A, the requirements and the acceptance suite were built under it. It was revised into this plan after the third review.
