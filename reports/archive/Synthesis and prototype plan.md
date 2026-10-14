# Synthesis and prototype plan (v2)

> **Archived.** Superseded by [Prototype plan](../Prototype%20plan.md), which summarises this version in its section 9.

This document draws on four inputs:
- [Rethinking CI from the code up](../Rethinking%20CI%20from%20the%20code%20up.md) (26 ideas).
- Your feedback on those ideas.
- [Software designed for cheap verification](../Software%20designed%20for%20cheap%20verification.md) (the other agent's review).
- [Review of synthesis and prototype](../Review%20of%20synthesis%20and%20prototype.md) (its review of v1 of this document).

**What changed from v1.** These corrections come from the review:
- **S3:** pure code is not automatically low risk, so the core is now built on *authorized moves*.
- **S5:** claims, evidence and acceptance are now separate records, and evidence has several dimensions instead of one ladder.
- **S1/S8:** activation is now a semantic transaction with read sets, joint bundles and pinned configurations.
- **S7:** plan diffs are only a first filter. The real check is a closed-loop simulation with an explicit model of external effects.

The prototype is smaller, its evaluation is harder, and its workload is fixed in advance.

Source note: SWE-Proof (arXiv 2609.21190, v2) and Trivet (arXiv 2609.19583) were checked and match their descriptions. The 56% audit figure for SWE-Proof is from v2.

"Proofs Promptly" (Ioannidis, Swamy et al., Microsoft Research, PACMPL ICFP 2026, [doi 10.1145/3828709](https://doi.org/10.1145/3828709)) was read from the PDF and matches the other agent's description:
- Agents did the specification, implementation, proofs and proof repair. Humans described problems, reviewed the specifications the agents generated, and sometimes supplied a key invariant.
- Three case studies took about 1 month with agents, against an estimated 6 months by hand.
- They used about 3.9B tokens, roughly $3.4k of API spend.

That spend matters for cost accounting. Searching for proofs is not free, even when checking them is cheap.

---

## 1. The design in seven claims

### S1. Publish immutable candidates freely; make activation a semantic transaction

**Publishing.** Adding an immutable candidate keyed by its content creates no conflict about what the system does. Nothing calls it yet. Name registration, policy acceptance and garbage collection still need ordinary coordination, but they are cheap and local.

**Activation** is the only step that changes what the system does. It is a transaction:
- **Read set.** The bindings and guarantees it relied on, including *absence* predicates such as "no other handler owns this route".
- **Write set.** The bindings it changes.
- **Joint bundles.** Bindings that must move together, for example when A2 requires B2 and B2 requires A2.
- **Established guarantees.** The guarantees that hold in the resulting configuration.

The read set is validated atomically at commit. This blocks write skew: two activations that write disjoint slots while each depends on the old value of the other's slot. A rejection names the specific assumption that failed, so the agent fixes that part instead of rebasing blindly.

**Pinning.** Each request or workflow pins a configuration snapshot, including policy and schema versions. A mid-request activation can then never produce a combination that was not checked.

**How this answers your CALM concern.** "Existing meaning" is the current configuration. Coordination is needed only where activations' read and write sets overlap, or where they share an aggregate constraint such as pool capacity or route uniqueness. Leases are one way to enforce this, optimistic validation is another, and both apply to bindings, not to code.

"Add, don't replace; clean up later" is the normal path:

```
publish → activate (transaction) → retire
```

### S2. A change kind is a checked operation; the operation log records why a change was valid

Text files stay. Items are parsed and hashed, and each has two identities:
- a **name** (`refund@2`, a slot, a call site), used for bindings;
- a **content hash**, used for evidence.

A change is a sequence of operations, and its text diff is derived from them. Each kind of operation carries a fixed obligation. Representation still matters: replaying a rename requires knowing which symbol each reference resolves to.

**No gate-shopping.** If a refactor fails its equivalence check, it does not become acceptable by being relabelled a modification. A modification needs an authorized requirement change behind it.

The operation log records the context in which each change was valid: its activation read set and the guarantees it relied on. That tells you what must be re-established when the context changes.

### S3. The kernel enforces a stated set of invariants, and planners combine authorized moves

The change in this version is that a pure planner can still do harm. Examples:
- a refund to the wrong recipient;
- a 100% discount;
- a response that includes another tenant's data.

Each of these can satisfy a short list of database invariants.

**The narrow claim.** Planner changes need not re-establish the invariants that an unchanged kernel enforces on every accepted plan, provided the kernel correctly mediates the relevant effect. Every other safety and product property remains an obligation of the planner, the policy, or their combination.

**Authorized moves.** These shrink what a planner can get wrong:
- The kernel issues narrow tokens scoped to a request. For example, a refund token is bound to the original payer, a maximum amount, an expiry and an operation ID.
- A planner can choose among and arrange those moves. It cannot invent authority.
- At commit, the kernel re-checks each token against *current* state, not the planner's snapshot, and consumes it.
- Snapshots are scoped to the requesting tenant.

**Capability reachability measures delegated authority, not risk.** A planner can still steer a privileged component into doing harm (the confused-deputy problem). Choosing a valid move at the wrong time is still a product bug.

**The main empirical question** is whether useful features leave the kernel alone. If most features change shared invariants, the plan language or state meaning, the architecture only moves the bottleneck into the kernel. The prototype measures this first (S8).

### S4. The old version is a preservation oracle, scoped to what each change kind claims

The old version is useful even when it has bugs. Its role depends on what is being claimed:

| Change kind | Old version as oracle | Required evidence |
|---|---|---|
| Refactor | Valid everywhere ("same as before, bugs included") | Equivalence with the old version |
| Extension | Valid on the old input domain | Preservation on old inputs, plus positive properties for new inputs |
| Authorized modification or fix | Valid only outside the declared region | Preservation outside the region, plus a positive property inside it that also fails on the old version (this rules out no-op fixes) |

### S5. Claim, evidence and acceptance are separate records

```text
claim:      subject, property, interpretation, domain, assumptions
evidence:   claim, method, checker, model, explored cases, result, provenance
acceptance: obligations, acceptable evidence, review requirements, policy version
```

- **Interpretation is a first-class dependency.** "Amount paid" can silently change from gross to net while the property text stays the same. The field mappings, units, helpers and observation adapters that the property's code uses all get identities. When any of them changes, the claim is re-opened.
- **A changed checker** changes how much the evidence can be trusted or where it applies. It does not change what the claim means.
- **A changed property** creates a new obligation. Old evidence does not become historically false.
- **Evidence has dimensions, not a ranking.** For each piece of evidence, record:
  - the property it checks;
  - the input and schedule coverage it achieved;
  - its bounds;
  - how the model connects to the implementation;
  - the assumptions it trusts.
- **Acceptance policies match evidence to failure modes.** A seed count alone is never an assurance level. A proof over the wrong model can miss what one end-to-end example catches.

### S6. Separate duties for evidence (this is a hypothesis)

- The ledger records who wrote each property and what they could see.
- A clean-room agent writes positive properties for new behaviour. It does not see the implementation diff, but it keeps public contracts, existing intended behaviour and domain evidence.
- Two agents can still share a mistake about the domain, so whether this workflow helps is something to test.
- Any change to a verification contract is flagged and then classified as strengthen, weaken, replace, extend, or representation-only. A changed contract is not presumed to be a weakening.

### S7. Plan diffs are a cheap first filter; closed-loop simulation is the real check

Diffing the plans two pure planners produce for the same request and snapshot is cheap and easy to review. It is not enough, because one plan changes the state the next request sees. The real check is a closed-loop simulation:

```
generate request → plan → validate and commit → deliver effect or failure → update state → continue
```

It runs under seeded schedules, stale snapshots, changes to authorization before commit, and version changes while work is pending.

**External effects follow an explicit model:**
- Each effect is pending, completed, failed, or unknown.
- Each operation has a stable ID, and the provider deduplicates by it.
- Reconciliation queries the provider.
- Ground-truth invariants are checked against the provider's ledger, not a local counter.

**Safety and progress are checked separately.** "Reservations expire" and "unknown effects resolve" are progress properties, checked after the system goes quiet, under stated assumptions about time and recovery.

A log of committed plans is not a reconstructible event log. Reconstruction would also need effect results, rejections, version identities and the transition semantics in force at the time. No claim beyond that is made.

### S8. Measure where obligations pile up

For every useful feature, record which of these it changed:
- only a planner;
- a consumer contract;
- delegated authority (moves or tokens);
- the shared kernel (invariants, plan language, state meaning).

Also record the consumers affected and the human decisions required. This is the decisive measurement. The results also guide later decomposition: a rule that changes repeatedly may deserve its own policy module, and a deeply shared invariant may legitimately stay coordinated.

---

## 2. How your feedback maps onto v2

| Your view | Where it lands in v2 |
|---|---|
| Effects and determinism enable everything else (1, 11) | The closed-loop simulator (S7) is the shared foundation. |
| Shadow execution may be too complex (21) | Plan diffs are the cheap filter. Closed-loop simulation runs the real behaviour. |
| Content addressing should keep text files (3); a verifier-tuned dialect (4) | S2. Planners are written in an enforced restricted subset of Python. |
| Change kinds (6); transformations rather than diffs (7) | S2, including the no-gate-shopping rule. |
| Claim ledger (12); its claims must keep a consistent meaning | S5: claims, evidence and acceptance are separate records, with interpretation as a dependency. |
| CALM, and "add, don't replace; clean up later" (15, 19) | S1. Publishing is immutable. Activation is a transaction. Old versions are retired later. |
| Leases create bottlenecks (18) | S1. Coordinate only where read/write sets overlap or aggregate constraints apply. |
| Per-definition deploy is inefficient (20) | In-process dispatch is pinned per request. Shipping a new native candidate still needs a build, so this tests activation semantics, not independent deployment. |
| Event sourcing is too hard (22) | Not attempted. The plan log is labelled as not reconstructible. |
| Core vs periphery (24), plus risk (5) | S3: authorized moves, delegated authority as the measure, and kernel churn as the key metric. |
| Versioned internal dependencies (26) | Falls out of S1. |
| Doubt that the old version can be the oracle (8, 21) | S4: it is a preservation oracle, scoped to what each change kind claims. |
| Group G (build and compile speed) is classic | Out of scope. Results here concern integration and reuse of evidence, not compile cost. |
| Humans should review more than intent and spec | Section 3. |

---

## 3. A change's life, and what humans review

1. **Author.** The agent works in a warm sandbox and expresses its change as operations (S2).
2. **Gather evidence.** Each operation kind has its obligations: equivalence for refactors; preservation plus positive properties for extensions and fixes (S4); closed-loop simulation for anything touching the kernel or delegated authority (S7). Each result is stored as an evidence record (S5).
3. **Publish.** The candidate is immutable and nothing calls it yet.
4. **Activate.** A transaction with a read set, a write set, bundles and aggregate constraints. The configuration is pinned for running work (S1).
5. **Run.** The kernel re-checks authorized moves against current state. External effects follow the explicit model.
6. **Retire.** Remove versions that have no bindings and no pinned work. The number of live versions is tracked.

**When humans review.** Review is triggered by changes to protected guarantees, delegated authority, verification contracts, and evidence quality. It is not triggered by "touches a path that depends on the core", which would cover almost everything. Concretely:
- **Kernel changes** (invariants, plan language, state meaning): the full diff, the operation log and the evidence.
- **Changes to delegated authority** (new move types, wider token scopes).
- **Changes to verification contracts**, with their classification.
- **Authorizing requirement changes** that permit modifications.
- **Behaviour samples**: plan diffs and traces from simulation runs for changed planners.
- **Periodic evidence-quality reports**: how often evidence catches injected mutants, and how often operations were rejected for a wrong kind.
- **Periphery code**: sampled audits, not review of every diff.

---

## 4. Prototype

### Goal

Find out whether there is a substantial class of useful changes that preserve shared guarantees, stay cheap to check, and don't simply move work into the kernel, a reviewer, or production. The headline metrics are:
- time until correct behaviour is active;
- total work per useful change, including sandbox, simulation and review time;
- defects that escape.

### Scope

- **Flows:** reservations, payment and full refunds. That means one provider (the kernel, through its moves) and two consumer flows (ordering and refunds), plus one external effect stub: a payment provider with idempotency keys and injected faults.
- **Harness:** Python.
- **Planners:** a restricted subset of Python, enforced by a whitelist over the syntax tree plus restricted builtins.
  - No imports.
  - No `while` loops and no recursion, so planners always terminate.
  - No access to names starting with an underscore.
  - No try/except.
  - Snapshots are frozen.
  - *This is honest confinement for a cooperative experiment. It is not a security sandbox.*

### Fixing the workload in advance

The feature backlog and failure corpus are written and committed *before* the kernel exists:
- Each feature records whether it is predicted to change the kernel.
- Development and held-out halves are chosen by a recorded seed.
- The git history is the record that this came first.

### Evaluation ladder

Each configuration adds one mechanism, so its benefit can be measured on its own. All use the same features, failure corpus and compute accounting.

| # | Configuration | What it shows |
|---|---|---|
| 1 | Conventional app + full test suite | The baseline |
| 1b | Conventional app + test selection by changed items | The strongest conventional baseline |
| 2 | Planner/kernel app + the same conventional CI | What the application architecture contributes |
| 3 | 2 + typed obligations and reuse of evidence | What the verification system adds |
| 4 | 3 + concurrent transactional activation | What version composition adds, and what it costs |

### Failure corpus

These are the review's required cases, plus E1-style bug injection:
- An invalid plan that the kernel rejects.
- A harmful plan that satisfies the initial kernel invariants.
- A useful feature that requires changing a shared invariant.
- Two binding updates to different slots whose read assumptions conflict (write skew).
- A feature that needs two versions activated together.
- A property whose interpretation changes while its text stays the same.
- A wrong implementation and an independently generated test that share the same misunderstanding.
- A legitimate test change that strengthens the contract.
- A remote effect that succeeds and then loses its acknowledgement.
- An old workflow still running while its version looks unused.

### Experiments

| # | Phase | Experiment | The idea is weakened if… |
|---|---|---|---|
| E1 | 0 | Authority boundary + closed-loop simulation over the planner and kernel bug corpus | Most realistic bugs are harmful-but-valid plans, or the kernel rejects too many valid requests |
| E-K | 1 | Implement the development-half backlog in configurations 1 and 2; measure where obligations pile up (S8) | Most useful features change the kernel or delegated authority |
| E2 | 2 | Operation kinds and evidence reuse (configuration 3) across a scripted stream of changes, including fixes and no-op fixes | Refactors and extensions are rare, or checking a kind costs as much as a full run |
| E4 | 2 | Claim meaning: change the body, property, interpretation adapter, checker, environment and kernel in turn | Evidence goes stale without being re-opened, or too much is invalidated |
| E3 | 3 | Concurrent activation (configuration 4): write skew, joint bundles, an aggregate pool limit, pinned in-flight work | Constraints collapse into a global lock |
| E5 | 4 | Review placement, using matched cases with the order of presentation varied | The structured view hides defects that the raw diff shows |

Scripted change streams test the mechanisms. Real agent runs come later and cost API spend, so they need your approval first. Without proofs, any equivalence result here is empirical compatibility evidence, and it is labelled that way.

### Phases

0. Fix the backlog and corpus in advance. Build the kernel with authorized moves, the restricted planners, the effect model, the closed-loop simulator, and run **E1**.
1. Build the conventional baseline (1, 1b). Implement the development-half features in configurations 1 and 2. Run **E-K**.
2. Build item hashing, the claim/evidence/acceptance ledger, and operations with kinds. Run **E2** and **E4**.
3. Build activation transactions and concurrency. Run **E3**.
4. Run the review experiment, **E5**.

### Out of scope

- Build and compile optimization.
- Event sourcing.
- Deploying each definition separately.
- Proofs.
- Consumer-specific contracts beyond the two flows.
