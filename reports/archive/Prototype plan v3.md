# Prototype plan v3: a toolchain agents build with

> **Archived.** Superseded by [Prototype plan](../Prototype%20plan.md), which summarises this version in its section 9.

## 1. The correction

**We drifted from the question.** The question was how to change the way software is built so that CI stops being the bottleneck when many agents change code at once.

Phase 0 built an *application architecture* instead: a checkout app with a kernel, planners and a fault simulator. That covers a slice of ideas 1, 11 and 24. It never touched the parts that make CI slow:
- re-running checks for every change;
- re-testing combinations in a merge queue;
- waiting on reruns;
- humans reviewing the wrong things.

**v3 changes what the prototype is.** It has three parts:

| Part | What it is |
|---|---|
| **The product: `newci`** | A small toolchain that agents use while writing ordinary Python. It carries footprint, evidence, intent, assumptions and undo information with the code, so landing a change becomes a cheap check rather than a re-run. |
| **The lab** | It runs the *same* codebase and the *same* change streams through `newci` and through the best existing pipeline. It measures throughput, latency, compute and escaped defects under a fixed compute budget. |
| **The subject** | The codebase being changed. The Phase 0 checkout app, ported and grown, becomes the subject. It is no longer the thing under test. |

The yardstick is the cost model from the second report:

```
CI cost ≈ rate × per-change cost  +  rate² × P(changes interact) × pair cost
```

The aim is to cut both terms without letting more defects through.

---

## 2. What "explicitly better than what exists" means

**What exists, at its best, for a Python codebase:**
- coverage-based test selection (pytest-testmon style);
- a test-result cache keyed on file contents (the Bazel idea, at file or target granularity);
- a merge queue that batches, tests speculatively in parallel, and bisects failures (GitHub or Mergify style).

The baseline gets all three. It also gets the same deterministic codebase, so it does not pay for flaky tests that `newci` would avoid for free.

**Better means, with the same codebase, change streams and worker budget:**
- **Throughput:** more correct changes landed per hour at saturation.
- **Latency:** lower median and p90 time from "agent says ready" to "on main".
- **Compute:** less verification CPU per landed change.
- **Quality:** no more defects reaching main. A defect is judged by an audit that is not the gate itself (section 6.5).
- **Agent cost:** similar agent tokens and time per task. This is measured in live runs only.

The thresholds get pre-registered before the head-to-head runs (section 6.6). The lab must also report where `newci` ties or loses, not just where it wins.

---

## 3. A change's life with `newci`

This is the "life of a change" you asked for, rebuilt from the ideas you liked. Agents work in plain Python files, in their own git worktrees.

1. **Write code.** The agent edits files as usual. The code follows a dialect (section 4.1) that makes its footprint computable. Examples: explicit imports, effects passed in as capabilities, frozen pydantic models for data, and no mutable globals.
2. **Check, often.** `newci check` does four things:
   - finds which definitions changed;
   - finds which claims (tests, properties, simulations) can reach those definitions;
   - reuses every result already computed for the same code, by any agent;
   - runs only the rest.

   Failures say exactly why a claim was reopened, and how to replay it.
3. **Declare a kind and land.** The kind is one of `add`, `refactor`, `modify` or `gc`. The tool *checks* the kind:
   - an `add` may not change any existing definition;
   - a `refactor` must be shown equivalent;
   - a mixed change is rejected with a suggested split.
4. **Land without a queue.** The change's definition-level operations are replayed onto the current main. Then only the claims whose footprint overlaps changes that landed meanwhile are re-checked, and most of those are cache hits. Changes with disjoint footprints land in under a second.
5. **Human review where it matters.** Some changes need a human before they land:
   - changes to core definitions;
   - changes to what a claim checks;
   - modifications to code tagged money, auth or personal data.

   The human sees the code diff, which claims were reopened or carried over, and the code of any new or changed checks, not just a statement of intent. Additions and refactors in the periphery are sampled after landing.
6. **System checks after landing.** Whole-system simulations can reach almost everything, so they would block almost every change. They therefore run continuously on main, not before landing. Everything is deterministic, so a failure is bisected exactly to one change, which is reverted automatically. The agent gets the failing seed.
7. **Clean up later.** Behaviour changes to widely used definitions are added as new versions (`price_v2`), and callers move over in small separate changes. A janitor runs `newci gc` to delete versions nothing reaches.

**What disappears:**
- the merge queue;
- re-running tests whose code did not change;
- flaky reruns;
- rebase conflicts between edits to different definitions in the same file;
- review of mechanical refactors.

**Example `check` output:**

```
$ newci check
lint     ok
changed  periphery/refunds.py::refund_policy                 modify
claims   212 reached · 205 reused · 6 reopened · 1 new
  FAIL   claims/refunds.py::refund_within_window   seed=3   0.04s
         reopened: periphery/refunds.py::refund_policy changed (a1f3→9c2e)
         replay:   newci replay claims/refunds.py::refund_within_window --seed 3
  pass   5 reopened, 1 new                                   0.31s
review   required: modify on risk:money (refund_policy)
```

**Example `land` output:**

```
$ newci land --kind refactor
kind     refactor verified: 2 definitions equivalent on 1,200 generated + 340 recorded inputs
claims   63 carried over by equivalence · 0 re-run
main     3 changes landed since base · footprint overlap: none
landed   c0007 in 0.4s
```

---

## 4. The `newci` design

### 4.1 The dialect (ideas 1, 4, 11)

These are ordinary Python rules, enforced by `newci lint` with messages that say what to do instead.

| Rule | Why |
|---|---|
| Explicit imports only. No `import *`. Modules contain only definitions and immutable constants. | The footprint can be computed from the source. |
| No `getattr`/`setattr`/`eval`/`exec`/`globals`, and no monkeypatching. | No hidden dependencies. |
| `core/` and `periphery/` may not import I/O, `time`, `random`, `os` or threading. Effects come in as a capability object. Only `effects/` touches the world. | Checks are pure functions of code, input and seed (ideas 1 and 11). The simulator is just another effect handler. |
| Data is frozen pydantic models. Public functions have type annotations. | Inputs can be generated for equivalence checks, and plans are validated at the core boundary. |
| Extension points are registered by decorator on each entry, never by editing a central list. | Adding a case is an `add`, not an edit to a shared file (idea 15). |
| Behaviour changes to definitions with many dependents become new versions (`f_v2`). | Add, don't replace; clean up later (ideas 15, 19 and 26). |

**Determinism is audited, not assumed.** The review showed that a syntax whitelist does not guarantee purity. So `newci` re-runs a random sample of claims under a different `PYTHONHASHSEED` and with a fresh process, and flags any claim whose result differs. A per-claim CPU budget bounds runaway checks.

The custom restricted-language loader from Phase 0 is retired. Agents write normal Python.

### 4.2 Definitions, hashes and footprints (ideas 3 and 4, keeping text files)

- **Definitions.** A definition is a top-level function, class or constant. Its hash is taken over its normalized syntax tree, with locations and docstrings removed.
- **Footprint.** A definition's footprint is the transitive set of definitions its body references. References are resolved through the explicit imports.
- **Other inputs.** Data files enter only through a declared `resource("path")` call, and are hashed into the footprint. The Python version and the lockfile are hashed into an environment key.
- **Files.** Files stay as they are. Several definitions per file is fine, because the tool works at definition level. This is your "without file proliferation" variant.

### 4.3 Claims and evidence (idea 12)

**A claim** is a check, written as a pytest test with an optional marker:
- `@claim` for an example;
- `@prop` for a Hypothesis property, run with a fixed seed;
- `@sim` for a deterministic simulation.

**Evidence** is keyed by `hash(claim footprint) + environment + seed`. The claim's footprint includes everything the check reaches, both the code under test and the check's own helpers. This has three consequences:
- **Reuse.** A result is reused exactly when nothing it could depend on has changed, on any branch and from any agent.
- **Free reuse for additions.** An `add` changes no existing footprint, so no existing claim reopens. Reuse falls out of the hashing; kinds add *policy* on top.
- **Bounded meaning.** A claim's meaning is anchored by the hash of its *checker*: the test code, its generators, and any interpretation helpers it uses, such as "`paid_at` means when the provider charged". If any of these change, it is a different claim. The change is labelled a contract change and goes to a human.

  Hashing cannot tell whether the English meaning stayed the same. But it guarantees that no claim silently changes what it checks. This is the mechanical part of your "consistent meaning" concern. The human part is reviewing checker diffs.

**The evidence store** is a single SQLite database shared by all worktrees. In the lab it stands in for a remote cache. Each record holds:
- the result and its cost;
- the seed;
- the code identity it was checked against;
- who produced it;
- a replay command.

**Sound reuse depends on complete footprints.** That is tested directly:
- an audit re-runs every claim on main heads, ignoring the cache;
- any disagreement counts as an unsound reuse.

### 4.4 Change kinds (idea 6, with the old version scoped)

| Kind | Allowed | Verifier | What happens to existing claims |
|---|---|---|---|
| `add` | New definitions, new claims, new registry entries | No existing definition's hash changes | None reopen, except claims that enumerate a registry |
| `refactor` | Changes to existing definitions | Old and new versions of each changed definition are compared on generated inputs and on inputs recorded at that definition during earlier evidence runs | Reopened claims are *carried over* by the equivalence evidence instead of re-run |
| `modify` | Behaviour changes | All reopened claims re-run. Failing claims must be fixed or changed, and changing one is a contract change. | Re-run |
| `gc` | Deleting definitions | Nothing live reaches them | Claims about the deleted code retire |

**On using the old version as an oracle.** You were sceptical of it, rightly. Here it is used only for `refactor`, where the claim is "behaves the same as before", not "is correct". Correctness claims carried over are exactly as good as they were before. A fix or a feature is a `modify` and never relies on the old version.

**The payoff of `refactor`** comes from widely used definitions. A refactor of a shared helper reached by 200 claims, including slow simulations, is checked by one local equivalence test in milliseconds, instead of 200 re-runs.

**Equivalence checking can miss.** Behaviour-changing "refactors" are a seeded case in the change streams, so the lab measures the miss rate.

### 4.5 Changes as operations; landing without a queue (ideas 7, 15, 18)

**A change is stored as operations on definitions:** add, replace, delete, and rename. A rename is recorded as `newci rename`, so replaying it also rewrites references in code added concurrently. That is the report's "rename X vs. add a call to X" case.

**Landing:**
1. Replay the operations onto the current main. Two changes conflict only if they changed the same definition, or one uses a name the other removed.
2. For every claim whose footprint overlaps definitions changed on main since the base, or changed by this change, compute its new key on the merged tree. Run the keys that have no stored result. *These runs are exactly the semantic interaction checks between concurrent changes.*
3. Commit if the blocking claims pass.
4. Hold a lock only for the final key comparison and commit. If main moved again in the meantime, repeat for the new difference.

**Leases** (idea 18) are optional and advisory, at definition granularity. The default is optimistic validation, which has no central bottleneck. The lab measures conflict rates first. Leases are worth adding only if hotspots waste a lot of work.

### 4.6 Core and periphery: claims that survive periphery churn (ideas 24 and 5)

This is where Phase 0's architecture earns its place in a CI design.

- **Core claims are quantified over every possible periphery output.** The core (kernel, money, inventory, order states, effects) checks every plan the periphery returns. The plan is parsed as a pydantic tagged union, which fixes review finding 2. A core safety claim such as "no overselling, no double charge, refunds ≤ charges" is checked by simulation with *generated* plans of every shape, not with the real planners.
- **So periphery changes never reopen core safety claims.** The footprint of a core safety claim contains only the core and the plan generator, so no periphery change can reopen it. Core simulations re-run only when the core changes.
- **Business rules are periphery claims.** Examples: the refund window, pricing, and "eligible requests complete". They have periphery footprints. E1b showed that the harmful planner bugs live here.
- **Service-level properties span everything.** They run after landing (step 6 of the change's life).

This answers the review's objection that "simulation only on kernel changes" was too broad. Each claim's scope comes from its footprint, not from the layer it sits in.

**Risk tags** (`risk:money`, `risk:auth`, `risk:pii`) are declared on core and periphery definitions. Each tag spreads to every definition that reaches the tagged one. The tags drive review routing and the evidence each change must carry.

### 4.7 Human review routing

| Change | Human before landing? | What the human sees |
|---|---|---|
| Any change to a core definition | Yes | Full diff, reopened claims, results |
| A contract change (a claim's checker changed or was removed) | Yes | The checker diff, and which code the claim covers |
| `modify` reaching risk-tagged code | Yes | Diff, reopened claims, new claims' code |
| `add` or `refactor` in the periphery | No; a sample is reviewed after landing | Same packet |
| `gc` | No | — |

The lab measures review load as a proxy: definitions and lines routed to humans per landed change. Whether humans catch more with this routing (the old E5) comes later.

---

## 5. How this maps to your feedback

| Idea | Your view | Where it is in v3 |
|---|---|---|
| 1 + 11 | Makes the others trivially testable; obvious place to plug in simulation | Dialect effects rule, determinism audit, `@sim` claims, exact bisection |
| 3 + 4 | Interesting; keep text files | Definition-level hashing over normal files; the dialect |
| 7 | What 3 and 4 really become | Changes stored as definition operations; rebase by replay; rename operation |
| 6 | Huge | Checked kinds with their own verifiers; no relabelling to pass |
| 12 | Exactly the reframe; the hard part is consistent claim meaning | Evidence keyed by footprint; meaning anchored by the checker hash; contract changes go to humans |
| 15 / 19 | Add, don't replace; clean up later | `add` kind, registry extension points, versions, `gc` |
| 18 | Good, but creates bottlenecks | Optional definition-level leases; optimistic landing by default; measure first |
| 24 + 5 | Fantastic; core ≠ periphery | Core claims quantified over periphery outputs; risk tags drive routing |
| 26 | Yes | Versioned definitions now; versioned modules later |
| 8 / 21 | The old version may be wrong | Used only to check that a refactor preserves behaviour, never as a correctness oracle |
| Review | Humans should review more than intent | Humans see code and checker diffs where risk is concentrated |
| 20, 21, 22 | Hard, expensive, or useful only in some cases | Out of scope. They are deploy-time ideas, and this prototype is about the path to main. |
| Group G | Classic build optimization | Out of scope |

---

## 6. The lab: proving it is better

### 6.1 The subject codebase

The Phase 0 checkout app is ported into the dialect and grown to a moderate service:

| Layer | Contents |
|---|---|
| Core | Money, inventory ledger, order state machine, payment effects, plan validation |
| Periphery | Catalog, cart, pricing, promotions, tax, refund policy, shipping rules, notifications, loyalty, reporting |

It needs the coupling the review asked for:
- shared helpers, such as money rounding and tax;
- shared state (inventory);
- an aggregate limit (a promotion budget);
- cross-module contracts;
- cases where three changes conflict although no two do.

The test suite should look like a real one: fast examples, medium properties, slow integration and system simulations. Its *full* run should be large compared with a typical change, so CI is a real bottleneck at 4–8 concurrent agents.

The review's other findings become subject requirements:
- **Request idempotency:** the business request, the attempt grant and the external effect have separate identities.
- **Two kinds of time:** when the provider charged is separate from when the kernel learned about it.
- **Pinned versions:** runs are pinned by content hash, not by name.

### 6.2 Baselines

| Arm | Pipeline |
|---|---|
| **B-full** | Full suite per change, then a merge queue that batches, tests speculatively in parallel, and bisects failures |
| **B-strong** | Coverage-based selection per change, a test cache keyed on file contents, and the same merge queue |
| **newci** | As described above |

Every arm runs on the same dialect codebase.

A separate, later arm runs on *conventional* code (without the dialect). It measures what the dialect itself costs agents and what it buys. It is kept apart so that the pipeline comparison stays clean.

### 6.3 Ablations

Mechanisms are added to `newci` one at a time, so each one's contribution is visible:
1. Definition-level shared cache, still behind a queue.
2. Landing without a queue.
3. Checked kinds (refactors carried over by equivalence; additions skip coordination).
4. Core claims quantified over periphery outputs.
5. A system tier after landing, with exact bisection and revert.

If the gains come mostly from step 1, then `newci` is "a better Bazel cache". That would be worth knowing.

### 6.4 Change streams

| Stream | Source | Cost | Shows |
|---|---|---|---|
| S1: scripted | 60–100 real patches written and committed before the gates are built | No API spend | Mechanisms, adversarial cases, the head-to-head |
| S2: agent-generated | Agents work through a task backlog against base snapshots. The patches are recorded, then replayed through every arm. | API spend | A realistic change mix without author bias |
| S3: live | N agents work concurrently, each through its arm's workflow | API spend | Agent usability, rejection and fix loops, real timing |

S1 includes the review's adversarial cases:
- a hidden dependency through a data file;
- a change to an interpretation helper (the payment-time case);
- a "refactor" that changes behaviour;
- two changes that are each fine but incompatible together;
- a three-way conflict;
- two changes that together break a shared promotion budget;
- a rename landing while another change adds a call to the old name;
- a planner change that breaks a business rule but no core invariant.

Each case comes with its pre-registered expected outcome.

### 6.5 Measurement

- **Real checks, deterministic results.** Every check any arm needs is actually executed. Its CPU cost is measured, and the result is stored by code identity. Results are deterministic, so one execution serves every arm. Each arm's own count includes every execution *it* would have performed.
- **A virtual clock.** Each arm's decisions (what to run, batching, landing order, bisection) are replayed on a virtual clock with W workers, using the measured costs. That gives throughput and latency under a fixed budget without running every arm in real time on this machine. A short live run checks that the virtual clock matches reality.
- **Escapes.** Every main state each arm produced is audited with three things:
  - the full suite, ignoring the cache;
  - a held-out acceptance suite, written from the requirements by a separate author who never sees the implementation, with ambiguous cases reviewed by you;
  - the seeded defects.

  The audit gives defects reaching main, how long they stayed, and unsound cache reuses. As the review says, the full suite is a *reference gate*, not ground truth. The held-out suite is there to catch what both share.
- **Work units, alongside times.** CPU-seconds of checks, checks run, checks reused, checks carried over by equivalence, landing waits, lines routed to review, and, in S2/S3, agent tokens.
- **The size and coupling sweep.** The subject is grown in steps by adding real coupled modules, not copies. Each step reports how work per change grows, for each arm.

### 6.6 Pre-registered criteria (proposed numbers, set before the head-to-head)

At N = 8 concurrent agents and a fixed W = 4 workers, against B-strong:

| | Criterion | Target |
|---|---|---|
| C1 | Landed correct changes per hour at saturation | ≥ 2× |
| C2 | Median and p90 time from ready to landed | ≤ 0.5× |
| C3 | Verification CPU per landed change | ≤ 0.5× |
| C4 | Defects reaching main (audit); unsound cache reuses | ≤ baseline; 0 unexplained |
| C5 | Agent tokens and wall time per task (S3 only) | ≤ 1.25× B-strong on conventional code |

**Kill criteria.**
- `newci` loses to B-strong on C1–C3 at N = 8. **Or**
- It wins only by letting more defects reach main. **Or**
- Most of the gain disappears once B-strong gets a shared cache at definition level, which would make it a caching result, not a redesign result.

---

## 7. Phases and milestones

All phases before P4 have no API spend.

**P1: Tool core on the existing app.**
- Build: the dialect linter, definition hashing and footprints, claim keys, the evidence store, and `check` with explanations.
- Port the checkout app into the dialect, fixing review findings 1–4 along the way.
- Test the mechanics adversarially: a hidden dependency, mutable module state, set ordering, an interpretation change.

**Milestone M1, the review's suggested test:**
- one real change lands with demonstrably less work than B-strong;
- then a closely related unsafe change is correctly rejected by the same cheap gate, with the right reason given.

**P2: Kinds, operations and landing.**
- Build: the `add`/`refactor`/`modify`/`gc` verifiers, carrying claims over by equivalence, operation replay with rename, landing without a queue, the system tier after landing with exact bisection and revert, and review routing.

**Milestone M2:** all S1 adversarial cases behave as pre-registered.

**P3: Lab and head-to-head on S1.**
- Grow the subject, and pre-register the S1 stream and the criteria.
- Build B-full, B-strong and the virtual-clock scheduler, then run the ablations and the size sweep.

**Milestone M3:** a first answer on C1–C4, with a clear note of where `newci` ties or loses.

**P4: Agents, only with your approval for spend.**
- S2 (recorded patches, replayed) first, then S3 (live).
- This also tests whether agents can follow the dialect, as measured by C5.
- I would estimate the cost before asking. Expect low hundreds of dollars, not thousands.

**After P4,** the held-out half of the feature backlog serves as a generality check. Mechanisms and decision rules are frozen first.

---

## 8. What happens to Phase 0

| Phase 0 piece | v3 role |
|---|---|
| Kernel, planners, effects, provider stub | Become the subject's core and periphery, ported to the dialect with pydantic plan types |
| Closed-loop simulator | Becomes the `@sim` claim runner and the core safety claims with generated plans |
| Restricted loader | Retired; replaced by the dialect linter and the determinism audit |
| E1 / E1b results | Kept as mechanism notes. E1b shapes section 4.6: business rules are periphery claims. |
| Review findings 1–5 | Fixed during the P1 port (5 is pinning by content hash) |
| The divergence and "blocked beyond baseline" metrics | Dropped. v3 measures outcomes against the audit instead. |

---

## 9. Risks and limits

- **Python is the hard case for static footprints.** The dialect plus the audit is the bet. If unsound reuse shows up often, the fix is stricter rules or footprints recorded at run time, and the lab will show which.
- **System-level properties do not shrink.** Running them after landing trades blocking time for time that bad changes spend on main. The lab measures both sides. It does not hide the trade.
- **Kernel churn still matters.** The v2 backlog predicted that 10 of 16 features touch the core. Definition-level footprints keep a core change from reopening unrelated core claims, but core changes still go to humans. If they dominate, review becomes the bottleneck. That will show up in the review-load measure.
- **A lab subject is not a large monorepo.** The size sweep gives slopes, not absolute numbers at Google scale.
- **Out of scope:** deploy-time ideas (20, 21, 22), compiler and build optimization (group G), and measuring whether humans catch more in review.

---

## 10. Decisions for you

1. **Spend for P4.** Approve later, with an estimate, or keep the prototype script-only.
2. **Subject size.** A moderate service (around 10 modules, with a full suite in minutes) is my default. Alternatively, port an open-source Python project, which is more realistic but costs more to put into the dialect.
3. **The C1–C5 thresholds.** Adjust them before they are pre-registered.
4. **The held-out acceptance suite.** Who writes it: a separate agent (spend), me before I see the implementations (weaker), or you.
