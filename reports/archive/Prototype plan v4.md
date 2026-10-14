# Prototype plan v4: does writing software differently remove integration work?

> **Archived.** Superseded by [Prototype plan](../Prototype%20plan.md), which summarises this version in its section 9.

v4 replaces the phases of [plan v3](Prototype%20plan%20v3.md) with one narrow first milestone, M1. v3's design remains the longer-term direction. The parts v3 got wrong are listed below.

## 1. What changed from v3, after the second review

| v3 | v4 |
|---|---|
| The first comparison gave every pipeline the same specially structured code. Conventional code was a later arm. | **The programming model is the centre.** Arm A is conventional code with strong conventional CI, arm B is the new model with the *same* CI, and arm C is the new model with minimal `newci`. A vs B measures what the structure buys. B vs C measures what the tooling adds. |
| Core claims were described as holding over "every possible periphery output". | Each core guarantee is labelled by how it is supported: **structural** (the interface or runtime enforces it), **bounded-exhaustive** (every case within stated bounds is checked), or **sampled** (seeded tests). |
| System checks moved after landing, with automatic revert and "exact" bisection. | **Dropped from M1.** Every arm must meet the same release requirements before a change counts as done. Recovery after landing is a separate operating policy, which could be offered to the baseline too. Bisection does not always find a single, independently revertible culprit. |
| "Refactor verified" by sampled equivalence, then every claim carried over. | **Early cutoff on recorded calls instead.** See 4.4. A check's result is reused only when every call it actually made to changed code returns the same value. |
| Dependency completeness was implied by the dialect plus an audit. | **An explicit contract.** A small supported set of constructs is defined. Registry membership is a dependency. Unsupported code is rejected or always re-run. Every check run also compares its run-time call set with its static footprint. |
| Kill the project if a definition-level cache in the baseline erases the gain. | **Removed.** If the programming model makes dependencies reliable enough for *existing* CI to skip work safely, that answers the original question. The product might then be a programming model plus light tooling, not a new CI platform. The lab still reports where the gain comes from. |
| Then a moderate service, a 60–100-patch benchmark, landing without a queue, renames and rollback. | **All deferred** until M1 succeeds. |

## 2. The question M1 answers

> For a concrete feature and a few realistic changes, does writing the software in the proposed model remove specific verification obligations, safely? How much of the saving comes from the structure itself, which existing CI already exploits, and how much from new tooling?

M1 is a demonstration with exact accounting, not a prevalence estimate. It cannot say how often real changes have each shape, how it behaves at scale, or what happens under concurrency. Those come later (section 9).

## 3. Arms

| Arm | Application code | Verification gate |
|---|---|---|
| **A** | Conventional: a well-structured service with dependency-injected clock and payment client, business rules in helper functions, and tests at every tier | pytest + **pytest-testmon** (coverage-based test selection, a real tool, v2.2.0) |
| **B** | Proposed model: a core that holds all state and effects and validates every plan; pure planners for business rules; frozen pydantic plan types | The same: pytest + pytest-testmon |
| **C** | The same code as B | Minimal `newci` (section 6) |

**Release requirements are the same for every arm.**
- Every check that the arm's gate selects passes.
- An audit then runs the full suite plus a held-out acceptance suite, ignoring all selection and caching.
- A change counts as safely admitted only if the gate passed it *and* the audit agrees.

**Test tiers, defined the same way in both code bases:**

| Tier | What it tests | Typical cost |
|---|---|---|
| T1 | Business rules: pricing and refund eligibility (examples and properties) | ms |
| T2 | Core state transitions: reserve, expire, pay, refund | ms |
| T3 | Faults and concurrency: provider faults, duplicates and interleavings over seeded schedules | seconds; the CI-dominant tier, as integration tests usually are |
| T4 | End-to-end service paths through the shared service interface | tens of ms |

## 4. The core guarantee, stated honestly

**The architectural proposition** is that some guarantees can be checked independently of the business logic that changes. If so, changing that logic does not reopen them.

The core's safety properties are below. Sections 4.1–4.3 say how each kind of support applies to them.
- **No overselling.**
- **Conservation of stock.**
- **At most one charge per order, for the order price.**
- **Refunds ≤ charges.**
- **Money only to the payer.**
- **No charge after expiry.**

### 4.1 Structural

- Plans are parsed into a pydantic tagged union. Any other shape is a controlled rejection, never a crash (review finding 2).
- Commit is the only path that changes state.
- Every move is checked against a grant and the current state.
- Periphery code cannot import effects, state or the clock. This is enforced in arm C and only partly in arm B (section 5, change C1y).

### 4.2 Bounded-exhaustive

`Kernel.commit` is checked against every state and every plan within a small scope:
- 2 SKUs, stock 0–2, up to 3 orders in any status;
- all grant kinds, including unknown and expired grant IDs;
- quantities from −1 to 3;
- prices at the boundary values.

Every invariant is checked after each commit. This is the "small-scope hypothesis" argument (Jackson, Alloy): most bugs show up in small cases. It covers a single commit, not interleavings or faults.

### 4.3 Sampled

T3 runs the closed-loop simulator with faults and interleavings over seeds, using *generated* plans rather than the real planners. That gives evidence under the generator's coverage, not proof.

**What follows from these three.** No core check calls a planner, so a periphery change cannot reopen any of them. Whether the core checks are *adequate* is a separate question. For single commits, 4.1 and 4.2 support it. For interleavings and faults it rests on sampling, as it does in arm A.

### 4.4 Early cutoff, the narrower replacement for "refactor verified"

1. While a check runs in C, record the call tree at definition boundaries in the subject code: function, arguments, then result or exception.
2. When definitions change, take each check that reached them and look at the *outermost* calls to changed definitions.
3. Re-evaluate only those calls with the new code, on the recorded arguments.
4. If every result, or exception, is equal, the check's execution outside those calls is identical. Its stored result therefore still holds.

**Why this is sound.** It holds under purity and determinism, provided arguments and results are immutable values compared deeply. This is the early-cutoff idea from incremental build systems ("Build Systems à la Carte", Mokhov et al. 2018; Salsa's backdating in rust-analyzer), applied to individual check runs.

**It needs no declared kind,** and it gives agents two useful signals:
- Labelled `refactor`, but some recorded call now returns something different: the change is not a refactor, and the tool says which call.
- Labelled `modify`, but every recorded call returns the same: "no existing check observes your change; add one". That is a test-adequacy signal.

**The arm-A contrast.** In conventional code, functions do I/O, so recorded results miss effects and this cutoff would be unsound. The programming model is what makes the mechanism legitimate.

## 5. The changes, with obligations pre-registered

Every change is a real patch in each arm.

| ID | Change | What it is for |
|---|---|---|
| C0 | Base: reserve, pay, full refund within 30 days of the *provider's* charge time (review finding 4), and expiry | The feature written in both styles |
| C1 | "Buy two, get one free" pricing (backlog F11) | A periphery change whose structure should remove an obligation |
| C1x | C1 with a pricing bug: the free item is applied per order line, so the order is underpriced | A closely related unsafe change that the cheap gate must reject for the right reason |
| C1y | C1, but the planner reads the wall clock for a "happy hour" rule, or keeps state in a module-level dict | A change that breaks the *assumption* the savings depend on |
| C2 | Partial refunds (F05): refund "up to" the remaining amount, with a refunded-amount state | A change that crosses the boundary and still needs coordination |

**Predicted obligations.** These are committed before any arm is built.

| Change | Arm A (testmon) | Arm B (testmon) | Arm C (`newci`) |
|---|---|---|---|
| C1 | T1, T2 and T4 for ordering, plus **all of T3**: the fault and concurrency tests call `place_order`, which calls pricing | T1 pricing and T4 for ordering. **No T2 or T3**, because core checks use generated plans. | Like B, but T4 runs whose recorded pricing calls are unchanged (single-item orders) are reused by early cutoff |
| C1x | Everything selected for C1. T1 fails, so the change is rejected. | T1 property fails, so rejected without running T3 | Same as B, with the failing call named |
| C1y | Runs as C1, and may pass | **testmon selects no T3,** so the skip rests on an assumption nobody checked. The audit shows whether anything escaped. With import-linter added, the wall-clock import is caught but the module-level state is not. | **Rejected by lint** (ambient clock or mutable module state in the periphery), and the message says which rule |
| C2 | Everything touching refunds, including all of T3 | Everything touching refunds, including T3, plus the bounded-exhaustive core check | Same as B, plus **human review required** (core change, risk:money) and the core and planner changes landing together. It may cost *more* than A. |

**Measures per change and arm:**
- checks run, and CPU seconds;
- which named obligations were reopened (T1–T4, the core bounded check);
- whether human review was triggered;
- whether the gate and the audit agree.

## 6. The minimal tooling: only enough to run M1

**For arms A and B:**
- pytest with `pytest-testmon`, run from a baseline database built on C0, then applying each change.
- `import-linter` as an optional extra in arm B, to show what existing layering tools catch.

**Arm C, minimal `newci`, has these parts:**
- **A lint for the supported subset**, with a reason for every rejection:
  - module-level functions and frozen pydantic models;
  - explicit imports;
  - no decorators except `@registry.entry`;
  - no I/O, clock, randomness or mutable module state in `core/` pure helpers or `periphery/`.
- **Static footprints** per definition. A registry's membership is its own dependency, so adding an entry reopens the checks that enumerate that registry.
- **A run-time footprint check.** Each check run records the set of definitions it called. If anything falls outside the static footprint, the run is flagged and that check is always re-run from then on.
- **Call recording and early cutoff,** as in 4.4.
- **An evidence store** in SQLite, keyed by footprint hash, environment and seed.
- **`newci check`,** whose output says what was reused, what was reopened and why, plus a replay command for each failure.

**Not built in M1:**
- merging or landing without a queue;
- rename operations;
- recovery after landing or automatic revert;
- the moderate service;
- the 60–100-patch benchmark;
- a multi-agent scheduler.

**What carries over from Phase 0, and the fixes for the first review:**
- Arm B reuses the kernel, effect model and simulator, with plans as pydantic types.
- The restricted loader is dropped, because it did not guarantee purity or termination (finding 1). Arm C's lint takes its place for M1.
- Malformed plans become controlled rejections (finding 2).
- Requests carry an idempotency key, so replanning cannot create a second order (finding 3).
- Refund windows start at the provider's charge time (finding 4).
- Version pinning is out of scope for M1 (finding 5).
- The E1 and E1b code stays in the repository as history and is not extended.

## 7. The agent workflow, written out for all three arms

M1 includes a short `AGENTS.md` for each arm, and the exact terminal session for each change:

| Arm | What the agent does |
|---|---|
| A | Edit, `pytest --testmon`, fix, push. CI reruns the selection, then the change is merged. |
| B | The same commands. The difference is where the agent puts the code: rules in planners, effects only in the core. |
| C | Edit, `newci check` (lint, footprint, reuse, early cutoff, explanations), fix, `newci land --kind …`. Landing in M1 is a local commit after the checks. |

## 8. Success, and what would redirect the work

**M1 succeeds if:**
1. For C1, B and C skip T3 and T2 that A must run.
2. That skip is justified by the structural and bounded-exhaustive support in section 4, and the audit finds no escape.
3. C1x is rejected by cheap checks in B and C, for the right reason.
4. C1y is rejected by C. Whether B's skip was unsafe is shown, not hidden.
5. C2 visibly requires coordination and review in C, with its cost reported even if it is higher than A's.
6. The B-versus-C difference is reported separately from A-versus-B.

**Redirect if:**
- B and C do not skip work that A must do for C1.
- The skip turns out to depend on an unenforced assumption that the C tooling cannot check.
- Early cutoff produces an unsound reuse that the audit catches.

**Bias controls:**
- **Requirements and acceptance suite first.** They are written before either implementation and drive both arms through one service interface.
- **Arm A before arm B.** Arm A is written first, in idiomatic style, and committed before B. You could ask the reviewing agent to check A for strawmanning before results are run.
- **Predictions committed first.** The section 5 predictions are committed before arms B and C exist.

## 9. After M1, in order, if it succeeds

1. **Concurrency in miniature.** Two periphery changes and one core change in flight at once. Which joint obligations exist in each arm, and which merge-queue work does B or C avoid?
2. **A change stream.** First scripted, then agent-generated (with spend approval), to measure the mix: how often changes are periphery-only, and the cost-weighted savings.
3. **The v3 machinery, only where the stream shows it pays.** That means definition-operation replay, landing without a queue, review routing, and a larger subject.
