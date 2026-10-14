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

## 4. The scenario: combining X and Y

This section was added on 2026-10-14, after arm B (`d43fe53`), the Y and Z requirements (`0b8e4f8`) and the change workflow (`4ad2b02`). No scenario change had been written yet. Sections 1 to 3 are unchanged. The held-out sample is deferred (plan section 6).

**Setup.** X is `b2g1` and Y is `category_windows`. Each is made from the same base, on its own branch and worktree. Then they are combined. Three gates are measured:

| Gate | What runs |
|---|---|
| A + testmon | Arm A, `pytest --testmon` |
| B + testmon | Arm B, `pytest --testmon`. This separates the code's effect from the tool's. |
| B + newci | Arm B, `newci gate` on branches and `newci combine` to combine |

On a branch, testmon starts from the base data and keeps its own data between commits. At the combine, testmon is measured twice:
- with the base data, which is what CI on main has before either change merges;
- with X's data, which is the best a single testmon database can do.

**Predictions.** "Existing" means checks that exist at the base.

| Step | A + testmon | B + testmon | B + newci |
|---|---|---|---|
| X | Reruns pricing T1, the place-order T2 tests, all 301 T3 and all 7 T4: close to the full suite's CPU time | Reruns no T2 and no T3 | **publish:** reruns no existing checks. **activate:** reruns 15 to 30 existing checks, none of them T2 or T3. |
| Y | Reruns at least 250 of the 301 T3 (most simulations refund), plus the refund T1, T2 and T4 tests | Reruns no T2 and no T3 | **publish:** reruns no existing checks. **modify:** reruns 5 to 15 existing checks, none of them T2 or T3. |
| Combine | git merges cleanly. With base data, testmon reruns at least 90% of the suite's CPU time. With X's data, at least 250 T3. | With base data, reruns no T2 and no T3 | **No stop.** It rechecks at most 15 checks, under 0.5 s of CPU: only checks that use both `RULES` and `refund_window_open`. It notes that X changed `RULES`, which Y's claims use. |

**Also predicted:**
- **Kinds.** X is declared publish, then activate. Y is declared publish, then modify. The tool accepts all four. Y cannot be an activate, because the refund policy is not a binding.
- **Lines changed.** Neither change touches arm B's core. In arm A, X changes `pricing.py` only, and Y changes `config.py` and `policies.py` only. Neither touches arm A's shared code.
- **Audit.** After the combine, both arms pass their full suites and `acceptance --features b2g1,category_windows`. A gate that passes when the audit fails is a soundness failure, and is reported as one.
- **Commands.** In both arms, an agent runs two commands per commit: the gate and `git commit`. Combining is one command in arm B (`newci combine`) and two in arm A (`git merge`, then testmon).

**What would change the plan:**
- **B + testmon reruns about as little as B + newci.** Then, at this scale, the code's structure does the work, and the claim ledger adds little over testmon.
- **B + newci rechecks much more than predicted at the combine.** Then footprints are coarser than they need to be.
- **A + testmon reruns little at the combine.** Then the premise that integration reruns most of the suite is weak for this codebase.

## 5. The scenario: Z, and combining it with X+Y

This section was added on 2026-10-14, after the X+Y results (`2329589`) and the rename to estoppel (`b80dc76`). No Z change had been written yet. Sections 1 to 4 are unchanged.

**Setup.**
- Z is `coupons` (`REQUIREMENTS.md` section 9): one code, `SAVE10`, takes 10% off. At most 3 redemptions are live at once, shared across customers. An expired order returns its redemption.
- The scenario is replayed from a new base: `b80dc76` plus the change to estoppel below. X and Y are replayed from it with the same change files and combined as before. Z is made from the same base, then combined with X+Y.
- The three gates are the same as in section 4, with estoppel in place of newci. At Z's combine, testmon is measured twice:
  - with the integration branch's data (X+Y combined), which is what CI on main has;
  - with Z's data.

**Expected shape of Z.** Its agent does not know about X.
- **Arm A:** one commit. It changes:
  - `config.py`: the code and its limit;
  - `validation.py`: the code;
  - `pricing.py`: the discount;
  - `models.py`: `coupon` on the order;
  - `store.py`: a count of live redemptions;
  - `service.py`: `place_order` takes the coupon, checks in the required order, and the view shows it;
  - `tests/simulation.py`: coupon orders and C1;
  - a new journeys file.
- **Arm B:** four commits.
  1. `modify`, core. Budgets, kept like stock holds: an `OpenOrder` may draw one unit of named budgets, `commit` checks and draws them, `Release` returns them, and a charge keeps them. It comes with T2 tests and an extension of `core_sim.py`.
  2. `modify`, periphery:
     - `Context` gains the coupon;
     - the place-order workflow gains its checks;
     - the service and the view show the coupon;
     - `build` passes the budgets;
     - `config.py` gains the code and its limit.
  3. `publish`: the `SAVE10` rule, with T1 tests.
  4. `activate`:
     - a new `order` stage after `item` in `STAGES`, holding `SAVE10`;
     - `RULES` gains `SAVE10`;
     - the composition test's contexts gain the coupon;
     - a journeys file.

  The stage order is Z's own decision: the coupon applies to the price after item promotions.

**One change to estoppel, before the run.** `combine` can stop, but it cannot continue after a stop. It gains `--resolved --decision TEXT`, used after the agent has merged with git and resolved the named definitions. It then:
- checks that the resolution changed only those definitions;
- rechecks;
- commits, with the decision in the commit message.

So in arm B the decision is written down by construction. What is measured is whether the stop happens, and what it names.

**Predictions.** "Existing" means checks that exist at the base: 374 in arm A (301 of them T3), and 433 in arm B (40 T2, 302 T3).

| Step | A + testmon | B + testmon | B + estoppel |
|---|---|---|---|
| Z | Reruns all 301 T3 and all T4: at least 90% of the suite's check time | **Core commit:** reruns all T2 and T3. **The other three:** no T2 and no T3. | **Core `modify`:** reruns all T2, T3 and T4 and most of T1, at least 90% of check time. **Periphery `modify`:** 15 to 50 existing checks, no T2 or T3. **`publish`:** none. **`activate`:** 10 to 40, no T2 or T3. |
| Combine Z with X+Y | git stops on textual conflicts: in `config.py` (both sides append to it), and possibly in `pricing.py` and `test_pricing.py`. Nothing names the stacking order. After the resolution, testmon reruns at least 90% with either data. | **With the integration data:** reruns all T2 and T3, at least 90%, because main's data has not seen Z's core change. **With Z's data:** at most 10%, no T2 or T3. | **Stops** (exit 3) at `RULES` (binding), and at nothing else. It does not name `STAGES`, because only Z changed it. git also conflicts in `config.py`, which estoppel does not name: the two sides added different definitions. **After `--resolved`:** it notes that `STAGES`, changed by Z, is used by claims made on the X+Y side. It rechecks 30 to 90 checks, none T2 or T3, under 2 s of check time, and keeps at least 380. |

**Also predicted:**
- **Kinds.** The tool accepts all four of Z's declarations. The core change cannot be a publish, because it changes existing classes.
- **The stacking order.** Both arms end with `SAVE10` applied after `b2g1`: three A with `SAVE10` costs 1800, not 1700.
  - In arm A this follows from the order of calls in the code, and is written nowhere.
  - In arm B it is the order of `STAGES`, and the combine's decision records it.
- **Lines changed.** Z changes arm B's core: `facts.py`, `moves.py`, `commit.py` and `runtime.py`. In arm A it changes `service.py`, `store.py` and `models.py`.
- **Audit.** Both arms pass their full suites and `acceptance --features b2g1,category_windows,coupons`. The oracle does not price a coupon order with 3 or more units of a SKU while `b2g1` is in force, so the audit cannot check the stacking decision itself.
- **Probes.** These are the X+Y probes again, plus the redemption limit (3 changed to 1) in each arm's config. testmon reruns no check for the new probe. estoppel reruns the checks that fail.
- **X+Y, replayed from the new base,** gives the same counts as section 4's results, within a few checks.

**What would change the plan:**
- **The stop names only `RULES`.** This is the prediction. If so, the stop comes from two changes editing one registry: any two rule activations would stop there, whether or not they interact. The actual interaction, the stage order, appears only as a note. Bindings would then need identities per entry, and the stop should come from a binding that one side changed and the other side's claims use.
- **B + estoppel reruns T2 or T3 at the combine.** Then claims made on Z's branch are not reused as predicted.
- **B + testmon with Z's data reruns as little as estoppel at the combine.** Then a well-chosen testmon database gets the same reuse. The ledger's advantage would only be that nobody has to choose the database.
- **Z's core `modify` reruns less than half of the check time.** Then the core's checks are less coupled to its facts than assumed, and crossing the boundary is cheaper than this plan expects.
