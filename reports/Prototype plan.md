# Prototype plan

This is the current plan. It is revised in place. Earlier versions are in [`archive/`](archive/), and section 7 summarises them.

Last revised on 2026-10-14, after the fourth review. That review found that v5 spent most of its effort on the subject application and deferred the new way of making and combining changes. It also found that we had built a lot of experimental apparatus without showing the central experience once.

## 1. The goal and the bet

**Goal.** Many agents change code at once. Each useful change should need less repeated verification and less coordination than it does today.

**The bet.** Several ideas each give modest value, and together they may change the development workflow:

| Idea | What it tells us about a change |
|---|---|
| Explicit effects and a checked core/periphery boundary | What it *can* affect |
| Content identities for definitions, with their dependencies | What it *did* affect |
| A claim ledger: each established check, keyed by what it depends on | Which earlier conclusions still hold |
| Publishing separate from activation | Who is affected, and when |

The prototype tests the combination end to end at a small scale, before investing heavily in any single part. The checkout application is the subject. The prototype is the change workflow.

## 2. The milestone

> Two useful changes start from the same base, progress independently, and combine without redoing unrelated work. An interacting change is stopped at the specific binding or assumption that needs a joint decision. A change that crosses the core boundary shows what it costs.

This is shown with the actual commands an agent runs, in two arms:
- **Arm B:** the core/periphery application, with the new change workflow.
- **Arm A:** the conventional application (`3bed8ff`), with git and pytest-testmon. This is the baseline.

## 3. What gets built

### 3.1 Arm B, minimal

**Core.** It holds facts and the operations that change them:
- holds on stock: `hold`, `release` and `consume`;
- a money ledger with per-line amounts;
- authority grants for each request kind;
- provider effects with stable keys, and reconciliation;
- commit as the only path that changes state.

Order status is a view derived from facts.

**Periphery:**
- workflows that are pure functions from a request and a snapshot to a proposed plan;
- pricing as a pipeline of rules in declared stages, with stage order and stacking policies in `composition.py`;
- policies: the hold time and the refund window.

**Boundary lint.** Periphery code may not import core internals, read the clock or randomness, do I/O, or keep mutable module state.

**Tests:**
- periphery rules and workflows (T1);
- core operations with generated plans (T2);
- a seeded core simulation with faults (T3);
- journeys through the public interface (T4).

It must pass the base acceptance suite.

**Left out on purpose.** Budgets and quote conditions are not built. The coupon change (section 4) needs them, so it becomes the change that crosses the core boundary. The core is kept simple enough to change. Its long-term stability is something to learn about, not a precondition.

### 3.2 The change workflow, minimal

It is a script over ordinary Python files, with git underneath.

| Part | What it is |
|---|---|
| Definitions | Every top-level definition in arm B, hashed by its normalized syntax tree |
| Bindings | The entries where a consumer selects an implementation: the rule registry, the stages in `composition.py`, the workflow table and config. The tool knows which files hold bindings. |
| Operations | Each change is declared as `publish`, `activate` or `modify`, and the tool checks the declaration:<br>• `publish` adds definitions without changing any existing hash, so behaviour and existing claims are unchanged.<br>• `activate` changes only binding entries, and names them.<br>• `modify` is anything else. |
| Claim ledger | A file in the repo. Each claim records a check, the checker's hash, its footprint (the hashes of the definitions and bindings it used), the seed and the result. Claims are keyed by content, so any workspace can reuse them. |
| `combine` | Merges two changes from the same base. It reports the claims kept, the claims to recheck, and the **interacting bindings**: bindings that one change edited and that the other change's claims depend on. |

**Footprints** are recorded at definition granularity while each check runs. The boundary lint keeps them meaningful, since periphery code cannot reach core state except through plans. An occasional full run of the arm's suite and the acceptance suite audits whether the ledger skipped something it should have rerun.

**Not built:** a transformation engine, rename tracking, leases, an evidence database, deployment, and garbage collection of old versions. Each is added only when the scenario shows a need.

## 4. The scenario

Three changes are made from the same base commit, each in its own git worktree. A script plays the "agents", so this costs no API spend.

| Change | Feature | Expected shape in arm B |
|---|---|---|
| X | Buy two, get one free (`b2g1`, already in `REQUIREMENTS.md`) | Publish a rule, then activate it in the item stage. Periphery only. |
| Y | Refund window varies by product category (backlog F03, dev split) | A policy and config change. Independent of X. |
| Z | Coupon codes with a shared redemption budget (backlog F01, extended) | It interacts with X: does the coupon stack with `b2g1`, and in what order? It also crosses the core, because budgets do not exist yet. |

**Order:**
1. Make X and Y in parallel and combine them.
2. Make Z from the original base, and combine it with X+Y.

**Both arms.** Arm A does the same three changes as git branches, merged and gated by testmon. Requirements and acceptance tests for Y and Z are written before either arm implements them. They are written as product requests, without the interaction decisions.

**Predictions.** These are committed to `proto/m1/PREDICTIONS.md` before the scenario runs.

| Step | Arm A (git + testmon) | Arm B (workflow) |
|---|---|---|
| Combine X and Y | The merge is clean. testmon on main reruns every test affected by either change, including those that already passed on the branches. | X's and Y's claims are kept: their footprints are unchanged by the merge. Nothing reruns except claims that span both changes. |
| Combine Z with X+Y | Likely a clean or trivial merge in `pricing.py`. Whether the coupon applies before or after `b2g1` stays implicit in code order. | `combine` names `composition.STAGES` as an interacting binding. X's pricing claims are invalidated, and the stacking decision must be written down. |
| Z's core change | Shared files change. Most of T2 to T4 reruns. | Core claims are invalidated, so core T2 and T3 rerun. This is the measured cost of crossing the boundary. |

**What we learn, depending on the result:**
- **Identifying dependencies is hard or unsound.** Invest in language restrictions or structural editing.
- **Useful evidence survives changes but is regenerated anyway.** Invest in the claim ledger.
- **Independent work still waits on shared integration.** Invest in activation and version management.
- **Ordinary features keep escaping the boundary.** Improve the programming model.
- **Arm B neither reruns less on combine nor surfaces the X/Z decision.** Then the combination buys nothing here, and the bet needs rethinking.

**Measures, for every step and both arms:**
- the commands run;
- checks rerun, by count and CPU seconds;
- claims kept;
- interaction decisions surfaced, or left silent;
- lines changed in the core or shared files, and in the periphery;
- whether the audit agrees after each combine.

## 5. Steps, with one stopping point

1. **Arm B, minimal** (3.1). Commit it separately so it can be reviewed at any time.
2. **Requirements and acceptance tests for Y and Z**, without the interaction decisions.
3. **The change workflow** (3.2).
4. **Predictions,** committed. Then **combine X and Y** in both arms.
   - **Stop and show it:** the commands, what reran, and what was kept.
   - Done on 2026-10-14. The results are in `proto/m1/scenario/RESULTS.md`, and they meet the first condition for changing the plan, on time. That needs a decision before step 5.
5. **Z,** and its combination with X+Y, in both arms.
6. **Write-up,** and a choice of which part deserves more investment (section 4).

## 6. Deferred

- **The held-out feature sample and the core-stability study** (v5). The predictions committed in `066a74a` stay on record, unedited.
- **F3:** item-level partial refunds of discounted orders.
- **A study with fresh agents.** It costs API spend and needs approval.
- **A larger subject codebase.**

## 7. History

**v2, [Synthesis and prototype plan](archive/Synthesis%20and%20prototype%20plan.md).** Its central combination is close to this plan:
- content identities;
- operations with checked kinds;
- immutable publication with explicit activation;
- preserved claims;
- coordination only where activations interact.

It produced Phase 0: a kernel that validates plans from restricted planners, an explicit effect model and a simulator. The main finding was that the kernel bounds *safety* but not *harm*: the harmful bugs were business rules inside its bounds.

**v3, [Prototype plan v3](archive/Prototype%20plan%20v3.md).** A full `newci` toolchain. It was set aside because it was large and postponed the central experiment. Section 3.2 builds the smallest slice of it that the scenario needs.

**v4, [Prototype plan v4](archive/Prototype%20plan%20v4.md).** It narrowed the work to M1: arms A, B and C on four changes. The requirements, the acceptance suite and arm A were built under it.

**v5, [Prototype plan v5](archive/Prototype%20plan%20v5.md).** After the third review, it made core stability and rule composition the central questions, through a feature sequence and a held-out sample. The fourth review found that this made the subject application the whole project. This plan keeps v5's boundary and composition design, and makes the change workflow the prototype again.
