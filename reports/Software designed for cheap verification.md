# Software designed for cheap verification

October 13, 2026

**The most promising direction is to make the cost of changing software depend on which guarantees change.** That requires changing how programs express dependencies, perform effects, and evolve their state. A faster CI service helps, but the larger opportunity is an architecture in which many edits cannot invalidate most existing guarantees.

Claude’s [second report](</Users/russellromney/Documents/Github/newci/reports/Rethinking CI from the code up.md>) makes a useful move toward this goal. The prompt behind it explicitly asked how software could be written differently, after rejecting another round of CI targeting and scheduling ideas. Its strongest contributions are behavioral boundaries, explicit effects, and treating an agent as an untrusted producer of code and evidence. Its biggest weakness is moving too quickly from a useful analogy to an unconditional guarantee.

My extension is to separate four events: **publishing code, activating a version, migrating state, and committing an effect**. They need different evidence. Once these are separate, there are several ways to avoid making every code edit pass a global integration gate. The proposals below are design hypotheses built from the cited work. They are not claims that these combinations are already proven or commercially available.

**Four parts of Claude’s report deserve serious investment.**

- **Behavioral boundaries that stop invalidation**, ideas 2 and 17. A caller should depend on a narrow guarantee, such as “this operation returns a valid reservation,” rather than every detail of the callee. The difficult work is making that dependency real and enforced. This is more consequential than shrinking test targets.
- **One explicit interface to the outside world**, ideas 1, 11, and 21. If time, storage, network calls, and randomness pass through controlled interfaces, the same business logic can run against production, a simulator, or a recorded environment. This improves what can be checked, not just how fast checks run.
- **The agent as an untrusted compiler**, ideas 9 and 10. Let an agent search for an implementation and justification. Keep the acceptance mechanism narrower and independently checkable. The useful asymmetry is cheap checking relative to search; moving expensive search into an agent’s sandbox does not itself reduce total cost.
- **Evolution as an explicit operation**, ideas 19–22 and 26. Keeping versions side by side can separate writing a feature from exposing it. But a real evolution mechanism must describe state, running work, and external effects. A function pointer is only one part of it.

The claim ledger in idea 12 could organize all this. It does not create these guarantees. I would build a ledger around an effective verification mechanism, after demonstrating reuse, rather than make the ledger the first product.

**Several corrections change the design materially.**

1. **Adding code is not enough to make changes independent.** Two additions can register the same route, consume the same capacity, or change method resolution. Even disjoint routes can compete for the same connection pool. Claude includes a conservative-extension condition, but establishing it is the main problem. Open registries remove textual contention while potentially increasing semantic interaction.

   A closer theoretical fit than a direct appeal to CALM is **invariant confluence**: whether independently valid reachable states remain valid when merged, for specified operations and invariants. It gives a precise question to ask about a code or activation model; applying it to arbitrary source code is additional work. [Bailis et al., Coordination Avoidance in Database Systems](https://www.vldb.org/pvldb/vol8/p185-bailis.pdf).

2. **An agent-written assumption list cannot justify skipping integration checks.** It may omit a dependency, especially an assumption about absence: no other matching route, no other producer of an event, no second holder of an entitlement. Database systems track predicate dependencies for this reason. A useful manifest must come from enforced interfaces, a proof derivation, or conservative analysis. Agent prose can suggest entries. [PostgreSQL transaction isolation](https://www.postgresql.org/docs/14/transaction-iso.html).

3. **A permitted difference is not a required improvement.** Claude’s condition, “observed difference is a subset of declared difference,” accepts a patch that does nothing. It can also permit arbitrary wrong behavior inside the allowed region. A change needs both a preservation condition outside that region and a positive specification inside it. The old version is useful for regression comparison; it cannot be the sole oracle for fixing its own bug.

4. **Determinism makes executions repeatable; it does not make one execution sufficient.** Different controlled schedules can still reveal different failures. External dependencies must be represented faithfully. Likewise, reusable evidence must bind the runtime, compiler, configuration, and environment model that matter to the claim. Content hashing cannot repair an incomplete dependency model. [Antithesis on deterministic simulation](https://antithesis.com/docs/resources/deterministic_simulation_testing/).

5. **Code rollback does not imply state rollback.** Switching an old function back on may expose it to newly written data it cannot interpret. An event log can rebuild a projection, but cannot unsend a notification or undo every business action. Reversibility needs its own conditions.

6. **Proofs and tests are different kinds of evidence.** A proof under explicit assumptions can support a universal statement. A replay corpus supports a statement about observed executions. A signed test result establishes provenance, not universal correctness. The ledger must preserve these differences instead of turning everything into “verified.”

7. **Cheap authorship does not make additional code free.** More versions, annotations, models, and adapters create storage, maintenance, verification, and comprehension work. Nor does a component become low risk because it is called “glue.” Authorization, retry behavior, and transaction ordering often live in glue. I would retire tests based on which guarantees replace them, not based on which architectural layer they cover.

**A surprising amount of the proposed machinery already exists in narrower forms.** These are the most relevant places to reuse work.

| Existing system | What it already provides | Where it fits and where it stops |
|---|---|---|
| [Unison](https://www.unison-lang.org/docs/tour/_big-technical-idea/) | Definitions identified by syntax-tree hashes; caching of pure computations and tests | The closest existing realization of Claude’s code-identity proposal. Adopting its language and codebase model is a substantial choice. Hashes do not establish correctness of external behavior. |
| [Pact Broker](https://docs.pact.io/pact_broker/can_i_deploy) | A matrix of consumer/provider verification results and a deployment compatibility query | Already a useful, limited evidence ledger. It addresses recorded contracts between versions; it does not establish arbitrary whole-system invariants. |
| [Cedar](https://arxiv.org/abs/2407.01688) | An executable formal model, proofs about that model, differential testing against production code, and tests for unmodeled parts | A concrete template for combining a small semantic core with an efficient implementation. The production implementation is not thereby wholly proved equivalent. |
| [CEL verifier](https://cel.dev/reference/api-reference) | Equivalence, satisfiability, validity, witnesses, and counterexamples for expressions and policies; bounded checking for comprehensions | Particularly relevant when changing application policy can be expressed in a restricted language. The bounds and supported semantics matter. It is not a verifier for arbitrary application code. |
| [Verus](https://verus-lang.github.io/verus/guide/cargo_verus.html) | Rust verification integrated with Cargo, including incremental artifacts and dependency re-verification | A practical route to selected verified components. Its current Cargo workflow does not establish the proposed global cache of all item-level proofs. |
| [Antithesis](https://antithesis.com/docs/introduction/how_antithesis_works/) | Controlled execution, state-space exploration, assertions, and reproducible failures | A strong existing option for interaction bugs. The environment and properties still need to be modeled; simulation remains a search problem. |
| [Temporal Worker Versioning](https://docs.temporal.io/worker-versioning) | Explicit control over which worker version handles a workflow, including pinned workflows | Solves an important part of coexistence for long-running work. It does not make arbitrary activities or schema changes reversible. |
| [wasmCloud interfaces](https://wasmcloud.com/docs/overview/interfaces/) | Explicit typed imports and exports using WebAssembly Interface Type definitions | A substrate for separately built components and mediated capabilities. Interface shape alone does not specify transaction semantics or performance. |
| [Exo](https://exo-lang.dev/) | Optimization through a scheduling language whose transformations preserve the computation within its model | A concrete example of making the allowed editing process carry correctness. Its domain is high-performance kernels. |
| [Alive2](https://github.com/AliveToolkit/alive2/blob/master/README.md) | Translation validation for LLVM transformations | Useful evidence that checking transformations can be practical. It has bounded guarantees and does not support interprocedural transformations. |

For an existing service fleet, Pact plus controlled replay may address a large share of the immediate problem. For a policy-heavy application, CEL or Cedar may remove more uncertainty by changing the representation of the logic. For a new language/runtime experiment, Unison is the first serious comparison. These are different adoption paths, not a shopping list to combine indiscriminately.

**Recent work strengthens the opportunity while exposing the specification problem.** The August 2026 ICFP experience report *Proofs Promptly* describes agents producing machine-checked code and repairing proofs. Human work remained concentrated in reviewing specifications and supplying important invariants. That is evidence of a useful division of labor, not evidence that specifications are now free. [ICFP paper summary](https://icfp26.sigplan.org/details/icfp-2026-icfp-papers/37/Proofs-Promptly-An-Experience-Report-on-Proof-Oriented-Programming-with-AI-Agents).

The September 2026 SWE-Proof preprint reports that giving agents correct formal specifications helped, while asking them to construct their own specifications did not improve its end-to-end resolution baseline. Crucially, its paper also separates proofs of modeled code from the partly empirical checks connecting that model to actual repository code and intent. This supports investing in the specification boundary, without treating its benchmark as a proof that arbitrary repositories can now be verified. [SWE-Proof](https://arxiv.org/html/2609.21190v1).

Also in September, Trivet combined generated proof scaffolds, LLM search, and Lean checking for LLVM transformations. The authors report resolving 147 of 148 cases in their evaluation. That is a narrow and promising result: a constrained semantic domain makes the producer/checker split concrete. It is not an application-wide equivalence engine. [Trivet preprint](https://arxiv.org/abs/2609.19583).

**The following eight directions change either the program representation or the meaning of accepting a change.** Their value is in the specific combinations and experiments, not in claiming that contracts, interpreters, or formal verification are new.

**1. Make evolving code propose state changes to a stable transaction kernel.**

Today a handler usually decides what should happen and directly causes it. Instead, write the changing part as a function that produces a typed plan:

```text
propose(request, state_snapshot) -> plan
check_and_commit(current_state, plan) -> receipt | rejection
```

For an inventory system, a plan might request a reservation, identify the stock records it read, and supply a customer entitlement. The kernel checks the plan’s read predicates against current state, including relevant absence conditions. It checks stock, entitlement, uniqueness, and allowed transitions, then commits atomically with that validation. The planner has no direct database or network write authority. Other external actions go through a mediated executor with explicit retry and deduplication semantics.

This changes the verification obligation. A new planner can be wrong about which valid action is best, but the kernel can prevent the classes of invalid actions it enforces. Some pre-merge checks can then concentrate on product behavior, progress, and efficiency. A proof about the kernel applies to many future planners because those planners cannot bypass it.

The theoretical relative is runtime assurance: Simplex separates a more capable controller from a trusted mechanism that keeps the system within an acceptable envelope. My proposed application is a software transaction boundary, with concrete plans and receipts replacing opaque handler side effects. [CMU’s Simplex architecture](https://sei.cmu.edu/library/an-architectural-description-of-the-simplex-architecture/).

The important extra step is to keep **safety and usefulness separate**. A planner that rejects every request can preserve stock perfectly and still be useless. Availability, acceptable rejection rates, and required successful cases need separate checks. The kernel also becomes trusted infrastructure and a possible throughput bottleneck; its checks must partition where the invariants permit.

First experiment: rewrite one reservation or entitlement workflow this way. Inject invalid plans, stale reads, duplicate requests, and retries. Measure how many defect classes the kernel blocks, valid requests it rejects, and runtime cost. This is feasible without inventing a language.

**2. Let consumers depend on specific observable properties.**

A function signature is often too weak, while dependence on an entire implementation is too strong. Give each consumer an explicit description of what it can observe and requires.

Suppose three consumers call a catalog service. One needs only the set of product IDs. Another requires ranked order. A third needs exact displayed prices. A ranking change should invalidate the ranking obligation, while the set-preservation obligation might remain valid. The evidence system could reuse the latter after checking a small relation between the old and new provider.

This extends Claude’s “depend on specs” idea by making the boundary **consumer-specific** and by carrying evidence across changed code identities. Ordinary content caching asks whether the implementation is unchanged. This asks whether the property a particular consumer relies on is unchanged.

The relation must be enforced. If a consumer declares that order is irrelevant but can inspect list order freely, the claim is fragile. A set-valued interface, a restricted accessor, or a modular proof can make the dependency truthful. State and effects also count as observations; comparing return values alone is inadequate.

Differential verification supplies a foundation for relations between versions. SymDiff supports relational specifications and procedure summaries, rather than only identical outputs. The proposed work is turning such relations into durable dependency edges that ordinary development tools can use. [Microsoft’s SymDiff](https://www.microsoft.com/en-us/research/project/symdiff-differential-program-verifier/).

First experiment: choose a small provider with consumers that need different guarantees. Express two or three distinct properties. Replay implementation changes and count how often a cheap property-preservation check prevents downstream verification. Compare total analysis cost as well as saved test time.

**3. Publish candidates freely and activate only compatible configurations.**

Treat accepted source as a library of candidate versions. A deployment selects a coherent configuration from that library. Publishing a candidate need not immediately change the meaning of every dependent. Activation is an explicit state transition with its own invariants.

This is more precise than asserting that all additions commute. Adding an unused definition can be harmless. Binding a route, selecting a policy, or starting a worker changes the active system. Those operations need rules about shared state, uniqueness, and resources.

For example, three independently added workers each demand 40 connections from a pool of 100. Every pair fits; all three do not. A pairwise compatibility matrix is insufficient. The activation model must check aggregate constraints, or allocate enforceable capacity rights that cannot be spent twice. Likewise, “no other handler owns this route” is a dependency on a predicate over the configuration, not just a hash of an existing function.

Pact supplies a useful practical starting point for version compatibility. Invariant confluence supplies a theoretical question about which activation operations could proceed independently. The proposed extension is a configuration model that includes n-way constraints, absence dependencies, state versions, and resource rights.

The runtime must bind a request or workflow to a compatible version set. Looking up “latest” independently at each call would reintroduce unverified mixtures. Shared state remains a compatibility boundary even when code is pinned.

First experiment: model the routes, schema versions, and resource demands of one application. Replay concurrent feature additions. Compare file conflicts, pairwise compatibility, and full configuration constraints. If the constraints simply collapse into a global lock, the architecture has not bought independence.

**4. Make a change include an executable law for state evolution.**

A release should describe not only its new code but how old state and ongoing work relate to it. For behavior that is meant to remain unchanged, ask whether these two paths agree on the observations that matter:

```text
old state --old operation--> old next state --migrate--> new representation
old state --migrate--> new state --corresponding new operation--> new next state
```

For intentionally changed behavior, replace agreement with the declared new relation. This makes migration part of the behavioral specification. An unchanged operation should not produce a different business outcome merely because migration happened earlier.

The subtle requirement is **rollback after new writes**, not just `down(up(old_state)) = old_state`. A perfectly reversible conversion can become irreversible as soon as the new version creates a state the old version cannot represent. For example, an old `paid: boolean` field cannot faithfully express every state in a new partial-payment model.

A version could therefore declare a rollback domain: states in which the old implementation remains usable, operations that preserve that domain, and operations that leave it. The runtime can keep a rollout inside that domain until promotion, retain supplementary information, or mark the precise point after which recovery needs a forward repair. This turns “reversible deploy” into an explicit, checkable property.

Cambria provides bidirectional schema transformations and also documents where conversions lose information. Dynamic software updating research such as Kitsune makes update points and state transformation explicit. My extension is to package behavioral correspondence and the rollback domain with every stateful change, then generate upgrade/write/downgrade scenarios from them. [Cambria](https://www.inkandswitch.com/cambria/), [Kitsune](https://www.cs.umd.edu/~mwh/papers/kitsune.pdf).

First experiment: take several historical schema changes. Test rollback immediately after migration and again after sequences of valid new-version writes. The difference between those results measures how misleading ordinary rollback checks can be. Prove small migration laws where tractable and label sequence testing as bounded evidence.

**5. Give agents an editing language whose operations preserve known guarantees.**

Claude proposes recording transformations rather than text diffs. Push that further: make the allowed authoring operations determine the proof obligations before code is produced.

An application might expose operations such as adding a disjoint policy case, replacing a computation with an equivalent one, introducing a separately versioned field, or moving a consumer to a provider that satisfies its observation contract. Each operation has machine-checked side conditions. Applying it produces both code and a derivation of which guarantees survive.

This differs from asking a solver to rediscover equivalence after an arbitrary rewrite. The construction history supplies the argument. It also differs from ordinary codemods: a syntax transformation with a reassuring name is insufficient. Its semantic conditions must be checked, including name resolution, effects, arithmetic behavior, and the supported environment.

Exo is an instructive precedent: authors choose optimization schedules while the language checks the transformations. CEL’s verification tools offer another useful building block for policy operations. The broader proposal is to build small authoring languages around a team’s frequent kinds of change. A recurring business-policy edit might become a constrained operation over a policy model, with generated implementation code. [Exo](https://exo-lang.dev/), [CEL API reference](https://cel.dev/reference/api-reference).

There must be an escape path for changes outside the vocabulary. Such changes acquire additional verification obligations. Otherwise the language either prevents useful work or quietly admits arbitrary code and loses its advantage.

First experiment: choose one repeated change family, such as access policies or validation rules. Implement a few checked operations. Compare arbitrary generated patches with operation-based authoring on correctness, solver effort, and time to accepted change. Count how often developers need the escape path. A grammar that handles only trivial edits is not enough.

**6. Help humans specify intent by showing them concrete disagreements.**

“Humans own the spec” is a reasonable boundary but a weak interface. Reviewing a long formal contract can be as hard as reviewing code.

Build a tool that looks for a program or outcome that satisfies the proposed contract while violating a plausible reading of the task. Present the human with the smallest concrete example that distinguishes the readings. For a refund feature, that might be: “After a partial refund, is a second refund allowed, and what remaining amount is refundable?”

The human makes a product decision. The tool turns that choice into a reviewed constraint and searches again. It can also remove a proposed clause and show the newly permitted behavior, making the value of each clause visible. The output is a small body of explicit commitments, examples, and unresolved cases.

The building blocks exist. Alloy searches for instances and counterexamples within declared scopes. Rosette supports solver-aided verification and synthesis. SWE-Proof also attacks specifications with candidate implementations. The proposed extension is a persistent human review interface driven by disagreements, linked to the properties that implementations and consumers rely on. [Alloy specification](https://alloytools.org/spec.html), [Rosette](https://emina.github.io/rosette/).

This cannot mechanically recover a user’s unstated desires. A finite sequence of choices is not a complete specification. Its value is making ambiguity cheap to expose and preserving decisions in a form future agents cannot silently reinterpret.

First experiment: choose ambiguous real feature requests. Compare ordinary prose review with review through generated distinguishing examples. Measure disagreements discovered, reviewer time, and defects found by a separately held evaluation set. This targets the bottleneck that stronger proof checkers alone do not remove.

**7. Optimize architecture for the cost of future verification.**

Claude’s churn-aware module splitting is useful. I would optimize a more specific objective: how much evidence a likely future change invalidates, and how hard that evidence is to rebuild.

Imagine a shared `Money` module containing parsing, display, tax rules, and settlement invariants. Editing a display rule may unnecessarily invalidate proofs about settlement. The better split is not necessarily smaller files. It may be a narrow data type, separate observation interfaces, and an explicit rule that formatting has no authority to alter monetary state.

A tool could record which definitions, assumptions, and resource models each proof or check actually used. Agents could then propose structural changes and evaluate them by replaying held-out changes. A rough design objective is:

```text
expected verification work
  = sum over likely changes of
      probability(change) × cost(evidence invalidated by change)
```

Runtime cost, compatibility burden, and human clarity remain constraints. A design that makes verification fast by moving all risk into production has not improved the system. Nor should an optimizer simply overfit the repository’s last month of changes.

Rust’s incremental compiler already demonstrates an important principle: changed inputs do not always imply changed derived results, so propagation can stop after checking an intermediate result. The proposed step is to make application boundaries and authoring choices serve the same purpose for behavioral evidence. [Rust compiler guide](https://rustc-dev-guide.rust-lang.org/queries/incremental-compilation.html).

One unusual consequence is that selective duplication may be worthwhile. Two consumers can use independent small implementations behind the same stable contract if this reduces harmful coupling. The duplicated implementations still need maintenance, and shared security fixes must propagate. This is an economic choice to measure, not a general argument against reuse.

First experiment: compare the current structure with two proposed boundary changes on historical edits, then evaluate on a later time window. Include proof search, checking, build time, test execution, and maintenance. Use the result as feedback to the authoring agent, so it learns to choose implementations whose future changes remain cheap to validate.

**8. Store causal explanations of successful executions, then challenge them.**

A production trace records what happened. For changed code, that is often insufficient. Suppose the old version read a customer record and then wrote an order. The new version writes first, then reads a derived status. Feeding it the old recorded answers can create an impossible world and falsely suggest equivalence.

Write effect interfaces so they record dependencies: which state version a read observed, which write produced a value, which response acknowledged which request, and which ordering constraints matter. A simulator can then generate alternative valid worlds, rather than blindly replay a sequence of responses. New effect requests must receive a modeled answer, be executed in an isolated environment, or make the replay inconclusive.

There is a strong precedent in lineage-driven fault injection. MOLLY uses the dependencies behind successful outcomes to search for combinations of failures that could defeat them. The proposed extension is to make application effect boundaries emit enough causal structure to compare software versions and challenge their claimed assumptions. [MOLLY paper](https://people.ucsc.edu/~palvaro/molly.pdf).

This makes the durable regression asset a small causal scenario: the input, the critical dependency or schedule, and the property that failed. It can survive a refactor more naturally than a test tied to internal calls. It also gives the agent a concrete explanation to repair.

Instrumentation and model fidelity are the hard parts. Recording every low-level event may cost more than the testing it saves. Start at a business boundary, such as reservation followed by payment, where dependencies have clear meanings.

First experiment: compare naive response replay with a small stateful simulator on changes that reorder reads, writes, and retries. Deliberately include a bug that passes only under impossible replayed responses. Measure whether causal scenarios remain useful after implementation refactors.

**A coherent implementation would have three distinct acceptance boundaries.** Candidate publication checks the artifact and its attached evidence. Activation checks the chosen combination of versions and its state-transition conditions. Runtime execution checks the effects that must preserve protected invariants.

```mermaid
flowchart LR
    A[Agent creates candidate] --> B[Check artifact and evidence]
    B --> C[Store candidate version]
    C --> D[Check activation and migration]
    D --> E[Run selected version]
    E --> F[Propose state change]
    F --> G[Validate and commit effect]
    G --> H[Receipt and causal evidence]
```

These checks need not all be centralized. They should partition along the invariants they enforce. A shared invariant can still require coordination. The goal is to make that coordination explicit and narrow enough that unrelated development proceeds independently.

Consider two agents working on checkout. One adds a discount rule. Another changes the reservation algorithm. Their code can be published independently. The discount candidate must preserve specified limits and implement its new eligibility rule. The reservation candidate must satisfy the inventory contract. Activation checks their shared price and reservation assumptions. At execution time, the transaction kernel rejects an attempt to oversell. A causal scenario explores a payment timeout after inventory reservation. Each mechanism answers a different question.

This architecture does not make an application correct merely by installing a framework. Its advantage is that the guarantees become reusable across future changes. It is most attractive where business state transitions and permitted effects can be stated narrowly. Visual design, open-ended content quality, highly coupled numerical software, and distributed timing may need different acceptance mechanisms.

**For compiled languages, I would separate two bets.** Sharing more compiler work across branches is an infrastructure project. Making fewer changes require general-purpose compilation is a representation choice. Frequently changing policy can sometimes become a separately validated expression or plan executed by a stable native runtime. That avoids rebuilding the surrounding optimized application for each policy edit. CEL is one concrete place to explore this for expressions; arbitrary systems code will not fit that model.

The shared compiler proposal still deserves investigation, but item hashing alone is insufficient. A reusable result must bind all relevant semantic inputs, including compiler version, target, features, generated inputs, and dependencies. Rust already has query-level incremental compilation; turning this into dependable cross-machine, cross-branch reuse is a different engineering problem. I would not repeat the earlier report’s broad claim that nobody does this without a much more focused survey. [Rust incremental compilation](https://rustc-dev-guide.rust-lang.org/queries/incremental-compilation.html).

A fast interpreter or development backend can shorten the feedback loop, but evidence about it does not automatically certify an optimized release artifact. Keep an explicit connection between what was checked and what ships, through an appropriate compiler trust model, translation validation, or checks on the release build. Separating fast feedback from expensive optimization is useful; silently treating their behavior as identical is not.

**I would run three experiments before building a general platform.**

| Experiment | What it would establish | What would weaken the idea |
|---|---|---|
| A checked transaction kernel for one workflow | How much correctness can be guaranteed independently of changing planners | Most important defects involve properties the kernel cannot enforce, or its cost and rejection rate are unacceptable |
| Consumer-specific guarantees for one provider | Whether behavior-preservation checks retain evidence across real implementation changes | Deriving and checking the relations costs as much as downstream verification, or consumers cannot be confined to their declared observations |
| Review through distinguishing examples | Whether human intent can become clearer with less review effort | Examples mainly restate obvious cases, miss consequential ambiguity, or take more time than ordinary review |

For all three, evaluate known historical failures and injected interaction bugs. Include overlapping changes, changes that omit the requested behavior, state written by a new version, and three-way resource conflicts. Split development cases from evaluation cases so the proposed system is not judged only on examples it was built to handle.

Measure total machine work, elapsed time to a deployable change, human review time, and escaped defects. Include agent proof search and runtime checking. Reporting only central CI minutes would hide work moved elsewhere. The source-control scale in Anthropic’s report is a useful motivating case, but its unusually high internal token budget is not a general economic baseline. [Anthropic’s Scion report](https://www.anthropic.com/engineering/redesigning-source-control).

**My first bet is the checked transaction boundary.** It changes which future bugs the application can express, and a team can prototype it in an ordinary language. My longer-term bet is consumer-specific behavioral dependencies: they could let verification stop at the same kind of stable boundary that already helps incremental compilation. The most important human-facing bet is specification review through concrete disagreements.

The deepest extension to Claude’s thesis is that code should carry not only claims about itself, but also **limits on what future changes and executions are allowed to invalidate**. CI becomes cheaper when those limits are enforced by the way software is written and run.
