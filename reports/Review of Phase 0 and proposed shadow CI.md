# Review of Phase 0 and proposed shadow CI

**The project has made real progress, but the distinctive CI hypothesis is still untested.** Phase 0 provides a useful application model and a reproducible fault simulator. It does not yet establish that the planner boundary is enforced as claimed, that evidence can be safely reused, or that concurrent changes can become active with less verification work.

I would keep the architecture and simulator, repair a few foundational gaps, and then build a small experiment that processes actual code changes through competing gates. I would defer broad feature expansion until that experiment exists.

**Scope and evidence.** I reviewed the recent Claude conversation through its October 14, 06:32 UTC response proposing plan v3, the v2 plan, and the prototype at commit `24b431c6d129e564699153fd5dc7a46f7c62f0ab`. The prototype working tree was clean. I read the runtime, kernel, restricted loader, provider, simulator, invariants, property checks, experiment runners, mutation generator, tests, and pre-registered workload. I did not change the prototype.

I independently ran:

- `uv run pytest -q`: 28 passed, in 1.23 seconds.
- E1's underlying runners: 200 seeds for the baseline and each executable bug variant. The reported outcomes reproduced.
- E1b's underlying runners: all 104 mutants at 20 seeds. The reported classes reproduced: 58 lost, 41 silent, 1 blocked, 4 accepted.
- Eight focused probes outside the corpus, described below. Their code and output are saved in [review evidence](<../research_notes/Prototype review at 24b431c/probe_results.json>).

The benchmark reruns called the existing functions directly so they would not overwrite Claude's raw result files. E1 took about 26 seconds here and E1b about 16 seconds; these are local timings, not a CI performance comparison. I did not repeat E1b at 100 seeds, run paid agents, or test a production service.

**My assessment of the current maturity is:**

| Area | Rating | Reason |
|---|---|---|
| Design direction | Strong | Explicit effects, checked proposals, and versioned obligations are useful foundations. The CI benefit depends on how those boundaries are used. |
| Proposed v3 experiment | Promising, with revisions | It moves toward the original throughput question. Its oracle, skipping rule, and baseline still need correction. |
| Phase 0 implementation | Useful experimental scaffold | Small, readable, reproducible, and easy to inspect. Several enforced properties are currently broader than the code supports. |
| Evidence for cheaper CI at agent scale | Not yet measured | There is no change-admission pipeline, evidence cache, activation transaction, merge queue comparison, or concurrent development workload. |

**The latest conversation is a productive course correction.** Your question about what the prototype actually proves was well aimed. Claude responded by distinguishing mechanism tests from evidence about the original goal. It also identified the absence of a size parameter, work accounting, conventional comparison, and change contention. Those are the right omissions to notice.

Claude has also handled experimental reporting well. It preserved incorrect predictions, disclosed changes made after seeing results, acknowledged correlated specifications and tests, and qualified its mutation sample. The code and results are substantially more candid than a typical favorable demo. Keep that reporting discipline.

There are nevertheless three claims in the newest response I would change immediately:

- The restricted language is not yet pure and terminating by construction. The probes below show ordinary accepted programs that violate both claims.
- Running the full suite is a reference gate, not ground truth. It can share omissions with the proposed cheaper gate.
- “Closed-loop simulation reruns only on kernel changes” is a hypothesis that is too broad as a general admission rule. Planner changes can affect properties outside the kernel's invariant set.

**What Phase 0 actually establishes.** The code implements a functional decision layer and a validating command handler, plus a simulated external service. A request receives a snapshot and grants. The planner returns a dictionary. The kernel validates selected constraints, mutates its in-memory state, and records effects. The simulator interleaves planning, commits, delivery, responses, reconciliation, and time advancement.

That is a coherent mechanism. Separating provider records from local state makes the effect checks more useful than checking local counters alone. Splitting planning from commit exposes stale-snapshot errors. Explicit unknown outcomes and stable effect IDs catch useful retry mistakes.

The single-threaded simulator is not inherently a weakness. It models logical concurrency through controlled interleavings. The important assumption is that each modeled atomic step, especially `Kernel.commit`, corresponds to an atomic operation in a later implementation. Real threads would not automatically make this a better experiment.

However, application-request concurrency is different from concurrent code changes. The current simulator exercises the first. It does not exercise the second. The distinctive contribution remains to be built: making application boundaries carry reusable verification obligations and safely compose concurrent changes.

**Finding 1: the planner language does not enforce purity, deterministic results, or termination. Priority: high.**

[restricted.py](<../proto/app/restricted.py#L78>) accepts mutable module-level literal “constants.” A planner can mutate one using allowed methods:

```python
STATE = []
def propose(request, snapshot):
    STATE.append(1)
    return {"op": "reject", "reason": str(len(STATE))}
```

The loader accepts this. Two calls with identical inputs return reasons `1` and `2`. Freezing request snapshots does not freeze the planner's retained environment.

The language also accepts a loop over a list that grows during iteration:

```python
def propose(request, snapshot):
    xs = [1]
    for x in xs:
        xs.append(x)
    return {"op": "reject"}
```

The bounded `range` implementation is irrelevant to this loop. The review harness stopped it after 10,001 line events to avoid unbounded execution.

Finally, allowed set iteration can change output across processes. A planner returning `str(tuple({'A','B','C','D'}))` produced four different orders under four `PYTHONHASHSEED` settings. The existing cross-hash-seed test establishes stability for the current baseline planner, not for the accepted language.

These are not arguments for building a security sandbox. They are direct failures of the properties on which deterministic checking and future evidence reuse depend. Reusing the same loaded planner across property checks and simulation seeds also means mutable planner state could contaminate those experiments.

**Change:** narrow the accepted values and operations, freeze or prohibit mutable module constants, address nondeterministic collections, and enforce an execution budget. Test these language properties with deliberately constructed counterexamples. If unrestricted Python execution makes enforcement cumbersome, use a small interpreter or an existing restricted language. Do not describe a syntax whitelist as a termination argument. A Python line budget alone also cannot bound expensive native builtin operations.

**Finding 2: a legal planner can crash the kernel through its output. Priority: high.**

This planner passes the restricted loader:

```python
def propose(request, snapshot):
    return {"op": {}}
```

At [kernel.py:161](<../proto/app/kernel.py#L161>), lookup of the dictionary-valued operation raises `TypeError: unhashable type: 'dict'`. Running it through `dst.run(0, ...)` reports an exception in `step_commit`. Similar malformed grant and item values need total validation as well.

This is an availability and interface-containment failure. It is not a demonstration of inventory corruption. The simulator currently places all kernel exceptions in its safety-failure bucket, so the report should distinguish those categories.

**Change:** parse plans into a strict, tagged command type before any mutation. Your Pydantic preference fits this boundary well. Validation should produce a controlled rejection for every invalid shape. Internal dataclasses can remain; converting all internal state models would not address the main problem. Preserve internal programming errors as visible failures rather than hiding them with a broad catch around the kernel.

Add plan-shape generation to the boundary tests. The current mutations mostly misspell existing string constants; they do not explore the wider set of values the language can return.

**Finding 3: single-use grants do not make requests idempotent. Priority: high before adding replanning or retries.**

Calling `Runtime.plan` twice for the same `place_order` request issues two grants and two order IDs. Both commits succeed. In the probe, one request for one unit created two orders and reduced stock from six to four. All current safety invariants passed.

The reason is visible in [kernel.py:113](<../proto/app/kernel.py#L113>): snapshots allocate fresh authority and fresh order identities. The simulator duplicates an already computed plan at [dst.py:145](<../proto/sim/dst.py#L145>), so its duplicate-delivery test does not cover re-entering the planning stage.

The current duplicate-plan mechanism works for its narrow case. The missing case is a client retry or replanning attempt for the same business request.

**Change:** distinguish three identities: the business request, the grant for an attempt, and the external effect. Bind retries to one business result, detect reuse of an ID with a different payload, and model duplicate arrivals and repeated snapshots. This does not require a production database yet; the in-memory model can first establish the contract.

**Finding 4: the meaning of payment time is implicitly chosen by the implementation. Priority: clarify and test.**

[Kernel.complete](<../proto/app/kernel.py#L264>) sets `paid_at` to the local time when a response or reconciliation is processed. The provider does not record when the charge took effect.

In the probe, the provider charged at time zero, acknowledgment was delayed by 40 days, and `paid_at` became day 40. The planner then allowed a refund under its “within 30 days of payment” rule. The current invariants accepted that sequence.

If the intended rule starts the window at provider execution, this is a correctness bug. If it starts at local confirmation, the requirement and field should say that. The experiment cannot choose between those interpretations by comparing the implementation to checks that use the same field.

**Change:** model occurrence time and observation time separately, decide which anchors the rule, and test lost or delayed responses around the deadline. This is a concrete instance of the claim-interpretation problem the design is supposed to solve.

**Finding 5: version pinning is currently a placeholder, not enforced execution identity.**

[Runtime.pinned_config](<../proto/app/runtime.py#L46>) records a name and hash. [Runtime.plan](<../proto/app/runtime.py#L66>) discards the hash and executes whichever object is currently stored under the name. Replacing that entry after pinning executes the replacement.

Phase 0 explicitly has one configuration, so this is not a failure of an already implemented activation protocol. It is a constraint for the next phase: version objects must be immutable and execution must resolve the pinned identity. Include the kernel, interpretation adapters, and relevant schema/policy compatibility in the model, not just planner source names.

Old code also continues to encounter changing shared state. Keep schema fixed initially, and require a defined drain or revalidation rule for incompatible kernel changes. A pinned code configuration does not make old state representations or permissions remain valid.

**The experimental measurements need two corrections.**

First, [divergence](<../proto/sim/dst.py#L276>) classifies an accepted plan as benign `stale` whenever the reference rejected for lack of stock. It does not check the accepted price, items, or other behavior. The probe classified a zero-price reservation as `stale`. This does not show that the reported four accepted mutants are wrong; it shows that the classifier cannot support its broader interpretation.

Similarly, `lost` assumes the reference plan would have succeeded, although it is never validated against the same commit-time state. Claude already disclosed that approximation. A separate side-effect-free validator, or a cloned state, can make the counterfactual explicit.

Second, [blocked_beyond_baseline](<../proto/experiments/e1.py#L92>) uses excess rejection counts and a Poisson-style threshold. The workloads change in response to each variant's behavior. More rejections can mean more eligible requests were generated, not that a corresponding set of bad plans was blocked. The report already notices this for grant expiry. Treat the count as descriptive until there is an event-level attribution method; the “three sigma” label does not establish causality.

Record distinct outcomes: invariant preserved, invalid command rejected, request completed correctly, request incorrectly refused, valid but incorrect effect, timeout, and checker/runtime failure. Avoid squeezing safety and useful service into one “fully contained” percentage.

**How I read E1 and E1b.** The reruns reproduce the numbers. The baseline gives 44,905 steps, zero safety or progress failures, and the reported 477 expired grants, 223 stock conflicts, and 90 order-state conflicts. E1b reproduces all four outcome classes and the smoke-test counts.

The strongest findings are that the simulator detects the selected effect/state-machine bugs, that property checks detect business-rule faults in these planners, and that cheap example tests catch many simple mutations. These are useful facts about this implementation and sample.

The percentages do not estimate the prevalence of real agent errors. Sixty-three of 104 mutations are string changes, including protocol keys and rejection text. Excluding M4 helps reveal sensitivity to that choice, but it does not make the remaining sample representative. Production code with typed command constructors would produce a different distribution before execution even begins.

The statement “only 1.6% fully contained” also mixes two questions. A rejected harmful command may successfully preserve safety while failing to fulfill a legitimate request. That supports the protection boundary while confirming the need for behavior checks. The original goal is reduced verification cost at an acceptable defect rate, not a particular share of mutants assigned to one outcome class.

There is one further limitation in the progress oracle: a planner that refuses all work can satisfy the current housekeeping properties. “No order remains stuck in paying” is different from “eligible requests eventually complete.” The experiment needs service outcomes as well as cleanup outcomes.

**What I would change in the proposed plan v3.**

**1. Call the full suite a reference gate.** Agreement with it tests whether an optimization preserves that gate's decisions. It does not establish product correctness. The malformed-plan and duplicate-request probes illustrate omissions in the current corpus; the payment-time example illustrates a shared interpretation problem.

Maintain an additional acceptance set based on explicit behavioral requirements and failure histories. Review ambiguous scenarios with a human. An independently prompted agent may help write checks, but its separation is not itself evidence of correctness. For a genuinely exhaustive oracle, specify finite input/state/schedule bounds and enumerate them; “run everything” is otherwise an imprecise phrase.

**2. Replace the layer-based skipping rule with obligation-based reuse.** A planner-only change can preserve stock conservation while changing refund eligibility, completion behavior, response data, or timing-sensitive behavior. The unchanged kernel's evidence may remain applicable to its enforced invariants. Other properties can require targeted simulation or new integration evidence.

The gate should record which obligations remain established, which assumptions changed, and which checks are required. Initially those obligations can be explicit and few. A general proof system is not required to test the mechanism, but the assumptions must be visible.

**3. Make the experiment apply actual source changes.** Scripted streams are a good first step and avoid agent spending. They should publish real candidate code, compute identities, execute the selected checks, attempt actual binding updates, and detect seeded incompatible combinations. A queue simulation in which the author assigns “cheap” and “conflicting” labels would mostly restate its assumptions.

**4. Use a fair conventional comparison.** Retain the v2 separation between architectural benefit and verification-system benefit. Compare a conventional app and the planner/kernel app under conventional checks; then compare alternative gates on the same planner/kernel app. Include test selection and ordinary result caching where applicable. A merge queue should batch work and permit preparation concurrently, rather than being modeled as unnecessarily serial.

**5. Vary coupling, not just codebase size.** Copying independent planners can manufacture favorable scaling against a full-suite baseline. Include shared contracts, shared state, aggregate resource constraints, and three-way conflicts that pairwise checks miss. Report where the new system wins, ties, or must coordinate just as much as the baseline.

**6. Make the premise cost-weighted.** It is too strong to say that most changes must be cheap or the design cannot matter. A minority of changes may account for most expensive checks or queue delays. Measure verification work and blocked time saved, against new authoring, runtime, and review costs. Kernel churn is a useful diagnostic, not the final verdict.

**A concrete next experiment.** I would run a small sequence before implementing the entire feature backlog:

1. Repair the planner boundary and request retry model. Add the focused probes to the regression corpus, with clear classifications of what each establishes.
2. Choose a few real changes: a behavior-preserving planner refactor, an authorized pricing feature, and a partial-refund change that alters a shared contract. Keep unchanged consumers in the workload so reuse has something meaningful to preserve.
3. Run each through conventional full checks, conventional selected checks, and an explicit obligation-based gate. Store claim, evidence, assumptions, checked code identity, and gate decisions.
4. Introduce an unnoticed dependency change, an interpretation-adapter change, and an incompatible combination. Verify that reused evidence is rejected for the right reason.
5. Add two, four, and eight concurrent change streams, including a joint activation and a shared limit. Revalidate against the exact active configuration at commit.
6. Score both gate agreement and independent behavioral acceptance. Measure actual executed work, wait time, and correct activations under a fixed resource budget.

The backlog remains useful for a subsequent generality check. Do not tune the kernel using its held-out half. The held-out run should be explicitly scheduled after the mechanisms and decision rules are frozen.

**What to add, remove, change, and rethink.**

| Action | Recommendation |
|---|---|
| Add | Strict request/plan boundaries, execution limits, request-level idempotency, dependency capture, and tests that deliberately challenge cached evidence. |
| Add | A durable run manifest containing code hashes, checker/configuration identity, seeds, work counts, and minimal failing traces. |
| Remove from current claims | “Pure and terminating by construction,” universal deterministic execution, and full-suite-as-ground-truth language. |
| Defer | A broad checkout feature build, a general ledger platform, a production sandbox, and replacing internal dataclasses solely for consistency. |
| Change | Outcome classification, counterfactual validation, and the ordering of the next experiment. |
| Rethink | Measuring success by mutant containment share or kernel-change frequency alone. Measure safe verification reuse and time to correct active behavior. |

**The most useful new design insight is to give reuse a failure explanation.** When a change is rejected, return the particular obligation whose assumptions no longer hold: a changed interpretation, a missing dependency, a wider authorized move, or an incompatible active consumer. This makes the ledger operationally useful to agents. It also gives the benchmark a precise unit of work: which obligations were retained, reopened, discharged, or blocked.

That would connect the prototype to the original ambition. The present code is a good starting laboratory. The next success should be a real change admitted with demonstrably less work, followed by a closely related unsafe change that the same cheap gate correctly rejects.
