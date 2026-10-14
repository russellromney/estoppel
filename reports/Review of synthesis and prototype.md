# Review of synthesis and prototype

**The synthesis is a substantial improvement, and its architecture is worth prototyping. Its guarantees need narrowing before they become implementation requirements.** The main progress is the combination of pure planners, a checked effect boundary, immutable candidates, and explicit activation. The main risk is treating these mechanisms as if they also settle product correctness, claim meaning, and concurrent evolution.

This review covers the new feedback in Claude session `2fdbc2c6-4b56-4f6f-8e5a-52d9de573255` and [Synthesis and prototype plan](<../reports/archive/Synthesis and prototype plan.md>). It proposes changes to the plan; it does not change that document or implement the prototype.

**Your feedback improved the direction in several concrete ways.**

- Prioritizing effects and determinism identified infrastructure that several other ideas can actually share.
- Keeping ordinary text files reduced adoption cost without giving up structured operations or item identity.
- Treating change kinds as consequential was right. The synthesis improves this further by making kinds checked operations.
- Questioning leases exposed the difference between coordinating development work and coordinating a change to active behavior.
- Questioning agent-written specifications, implementations, and tests exposed a correlated source of error. More artifacts do not necessarily provide more independent evidence.
- Treating compiler optimization as a separate track helped focus this experiment. Its results must then be described as results about integration and evidence reuse, not as a solution to compiled-language CI costs.

I would qualify three parts of your feedback. Transformations do not make representation and dependencies unimportant: replaying a rename still requires knowing which symbol each reference denotes. The old version remains a useful preservation oracle even if it contains bugs; its role depends on the claim being checked. And event sourcing does not inherently mean retaining every telemetry event at observability-platform prices. Your stronger objection is the complexity of state evolution, reconstruction, retention, and external effects.

**The synthesis also makes two fair corrections to my earlier report.** A tiny ledger can be a useful measurement instrument from the start. That is different from making a general ledger the first product. Also, moving verification search away from a shared gate can improve latency even without reducing total compute. Both quantities matter; the actual shared bottleneck must be measured.

Its best synthesis is the planner boundary. A pure planner producing a structured plan makes differential inspection much easier and gives deterministic simulation a clear insertion point. Separating candidate publication from activation is also useful. In-process dispatch is a sensible prototype choice and avoids assuming that every version boundary requires a network call.

**The most important correction is that purity does not imply low risk.**

S3 says that planner changes need usefulness evidence but no safety evidence. That is too strong. Consider a refund planner that produces the wrong recipient, an eligibility planner that gives every customer a large discount, or a response planner that includes another tenant’s information. The proposed action can be well typed and preserve a short list of database invariants while causing serious harm.

A kernel can protect a planner-independent invariant only if it has enough trusted context to check it and completely mediates the relevant effect. “The refunded total never exceeds the paid total” is useful, but it does not by itself establish who may request a refund, who receives it, or whether it should happen.

The narrower claim should be: **planner changes need not re-establish invariants that an unchanged, correctly mediating kernel enforces for every accepted plan.** Other safety and product properties remain obligations of the planner, policy, or their composition.

Capability reachability is therefore an authority measure, not a complete risk measure. The analysis also needs to capture which consequential decisions a function can influence through its outputs. This resembles the classic confused-deputy problem: a less privileged party can induce a more privileged component to act. [Capability Myths Demolished](https://erights.org/talks/myths/index.html).

This is also a correction to how my own transaction-kernel proposal could be read. It works for explicitly enforced classes of invalid actions. It does not make the changing part of the application generally safe.

**The kernel may become the new source of coupling.**

The design assumes a small, stable kernel and a rapidly changing periphery. Whether that division survives real feature work is an empirical question.

Suppose the next feature adds partial refunds. The next permits split shipments. Another introduces credit, reservations across warehouses, or a different tenant authorization model. These may require changing the kernel’s invariants, the plan language, or the meaning of an existing state. All planners that rely on those guarantees may then need new evidence.

The central measurement should be the share of useful behavior changes that leave shared invariants and the kernel unchanged. Track how often a task changes those rules, how many consumers are affected, and how much review those changes require. A toy workload consisting mostly of alternative implementations of fixed rules would make the architecture look better than it is.

The human-review policy needs the same scrutiny. “Review activations that touch core-dependent paths” could cover nearly every useful action. Define review triggers by changes to protected guarantees, delegated authority, and evidence quality. Otherwise the proposal rebuilds a global gate around a human.

**A claim, an evidence record, and an acceptance policy should be separate objects.**

S5 usefully rejects a single green/red status, but its proposed tuple mixes the proposition with the method that tested it. I would separate them:

```text
claim:      subject, property, interpretation, domain, assumptions
evidence:   claim, method, checker, model, explored cases, result, provenance
acceptance: obligations, acceptable evidence, review requirements, policy version
```

A checker upgrade usually changes the trust or applicability of evidence, not what “refund total does not exceed amount paid” means. Likewise, changing a property does not make old evidence historically false. It creates a new obligation whose relationship to the old one must be determined.

Hashing records identity. It does not guarantee that a property is bound to the right program behavior. The unchanged phrase “amount paid” can be misinterpreted after a field changes from gross to net. A helper, unit convention, state abstraction, or observation adapter can change what executable property code checks. Those dependencies and mappings need explicit identity too.

The evidence ladder should become a set of dimensions rather than a total ranking. A proof of a weak property over the wrong model may miss a bug that one end-to-end example exposes. Ten thousand deterministic schedules can explore the same irrelevant part of a system. For a fixed claim and sound semantic model, methods can sometimes be ordered by coverage or guarantee; across different claims and assumptions, they are often complementary.

Record the property, input and schedule coverage, bounds, model-to-implementation connection, and trusted assumptions. Require evidence suited to the failure mode. Do not treat a number of seeds as an assurance level on its own.

**Immutable publication is useful, but S1 overstates what it establishes.**

A set of unused immutable objects keyed by content can grow without semantic conflict. Publishing under that model is an excellent primitive. It does not automatically make unique name registration, policy acceptance, garbage collection, and all surrounding infrastructure coordination-free.

More importantly, activation must bind the complete relevant configuration. If a request calls version A1 and then dynamically looks up whichever B is latest, a mid-request activation can produce a combination that was never checked. The prototype should pin an activation snapshot for each request or workflow, including relevant policy and schema versions.

Checking only the binding being written is insufficient. Two activations can write disjoint slots while each depends on the old value of the other slot. This is analogous to write skew in databases. Activation needs read dependencies and predicate checks, including absence conditions, validated atomically with the update. A lease is one mechanism; optimistic transaction validation is another. [PostgreSQL’s explanation of serializable isolation](https://www.postgresql.org/docs/15/transaction-iso.html).

Some features also require multiple bindings to move together. If A2 requires B2 and B2 requires A2, neither individual activation is acceptable. Include a joint activation operation for a small compatible bundle. This is compatible with local coordination; it does not require every application change to share one global lock.

**Separation of duties helps, but a clean-room agent is not an independent oracle.**

Hiding the implementation diff reduces one source of anchoring. Two agents can still share the same ambiguous task, mistaken domain assumption, incomplete contract, or model failure. The clean-room agent should retain access to the relevant public contracts, existing intended behavior, and domain evidence. Otherwise the procedure can remove useful information along with bias.

The proposed clean-room workflow is a hypothesis to test. SWE-Proof supports the importance of faithful specifications; it does not establish that this particular workflow fixes specification errors. The synthesis’s 56% audit-pass figure matches the current v2 abstract. My earlier reading used v1, which reported a different aggregate. Pinning the paper version matters. [SWE-Proof v2](https://arxiv.org/abs/2609.21190v2).

Also, editing a test alongside code is not synonymous with weakening a property. A change may strengthen a condition, replace an incorrect expectation, extend the tested domain, or change only representation. Flag changes to the verification contract for review, then classify their effect. Do not make legitimate specification evolution appear inherently suspect.

Finally, a failed refactor check should not become acceptable merely because an agent relabels the change as a modification. Changing the permitted behavior requires an authorized requirement change or an already authorized modification. The operation vocabulary must not become a way to choose an easier gate.

**Plan diffs simplify one-step comparison; they do not replace execution semantics.**

The same request and snapshot are excellent inputs for comparing pure planners. But the new plan may create a different next state. Subsequent requests may then differ, even if every recorded historical request looked reasonable in isolation.

The simulator should run closed loops: generate requests, run a planner, validate and execute its plan, deliver effects or failures, update state, and continue. Compare the behaviors or invariants of those evolving runs. Also test stale snapshots, changes in authorization before commit, and version changes while work is pending.

External effects need particular care. The kernel cannot generally atomically commit a local row and obtain an unambiguous response from a remote payment service. A timeout can occur after the payment succeeded. The prototype needs an explicit pending/completed/unknown effect model, stable operation identities, and a recovery rule. “No double refunds” should be tested against that model rather than only against a local counter.

The listed property “reservations expire” is also a progress property: something eventually happens. It needs assumptions about time advancement, scheduling, and recovery. A gate can preserve state invariants indefinitely by refusing to make progress, so safety and progress need separate checks.

A log of proposed or committed plans is not automatically a reconstructible event log. Reconstruction may also need effect results, rejected outcomes, version identities, and the state transition semantics used at the time. Keep the prototype’s claims narrow until this is explicit.

**The Python prototype is reasonable if its enforcement claim is honest.**

Parsing Python syntax is easy relative to soundly identifying everything an arbitrary Python function depends on. Globals, decorators, dynamic dispatch, imports, and mutations complicate both hashing and purity analysis. An AST library does not solve that problem by itself.

Use Python to build the harness. For the first planner language, either enforce a deliberately restricted subset or interpret a small typed expression language whose permitted operations have no ambient I/O. Ordinary Python functions with import lints are useful for a cooperative experiment, but they do not establish a general confinement guarantee. Python’s own documentation similarly distinguishes auditing from sandbox enforcement. [PEP 578](https://peps.python.org/pep-0578/).

There is also a limit to the in-process deployment experiment. Putting all candidate versions in one compiled artifact and flipping bindings avoids RPC overhead, but adding a new native candidate can still require a new build and artifact rollout. That is fine for testing activation semantics. It is not yet an independent per-definition deployment mechanism.

**Three new design ideas follow from these gaps.**

**First, planners could assemble narrowly authorized moves.** The kernel could issue a token tied to a customer, order, maximum amount, expiry, and operation identity. A pure planner can arrange or choose among such moves but cannot invent authority. At execution, the kernel checks the token against current state and consumes any one-use entitlement.

For example, a refund proposal could be constrained to the original payment recipient and an explicit remaining amount. The plan expresses the permitted operation and its guard, rather than supplying arbitrary low-level writes. This reduces the space of dangerous but structurally valid plans. It also makes the planner’s delegated authority measurable. Choosing an authorized move at the wrong time can still be a product bug, so this narrows obligations rather than eliminating them.

**Second, activation should be a semantic transaction.** Each activation declares which guarantees and bindings it read, which bindings it changes, and which guarantees the resulting configuration establishes. Validate those assumptions at commit. Pin the resulting configuration for running work. Return a precise failed assumption when activation is rejected, so the agent repairs the relevant part instead of rebasing blindly.

This gives the operation log a stronger purpose: it describes why a change was valid in a particular context and what must be re-established when the context changes. Text transformations alone do not carry that information.

**Third, measure where new obligations accumulate.** For each useful feature, record whether it changes only a planner, changes a consumer contract, changes delegated authority, or changes the shared kernel. Record the affected consumers and the required human decisions. This reveals whether the architecture creates durable independence or continually pushes feature work into its most expensive shared component.

That measurement can guide future decomposition. A repeatedly changing rule might deserve its own policy module and verification boundary. A deeply shared invariant might legitimately remain coordinated. The architecture can evolve from observed verification costs rather than a fixed initial distinction between core and periphery.

**I would make the prototype smaller and the evaluation harder.** Start with reservations and refunds, one provider with two consumers, one external-effect stub, and a small planner language. Add the following mechanisms in separate steps so their benefits can be distinguished:

| Configuration | What it isolates |
|---|---|
| Conventional application with a full suite | Initial comparison |
| Planner/kernel application with the same conventional CI policy | Benefit of the application architecture |
| Same planner/kernel application with typed obligations and evidence reuse | Additional benefit of the verification system |
| Same system with concurrent transactional activation | Additional benefit and cost of version composition |

Use an item-selection baseline too, as the synthesis already proposes. Keep the intended features, failure corpus, and compute accounting comparable. Measure time to a correct active behavior, not time to publish an unused candidate.

The test corpus should deliberately include:

- An invalid plan that the kernel correctly rejects.
- A harmful plan that satisfies the initial kernel invariants.
- A useful feature that requires changing a shared invariant.
- Two disjoint binding updates with conflicting read assumptions.
- A feature that requires joint activation of two versions.
- A property whose interpretation changes while its top-level text remains unchanged.
- A wrong implementation and independently generated test that share the same misunderstanding.
- A legitimate test change that strengthens the contract.
- A remote effect that succeeds before its acknowledgment is lost.
- An old workflow still running when its version appears otherwise unused.

Use separate development and held-out cases. In the review experiment, do not show the same change to the same person twice in different formats and attribute the second result solely to the interface; use matched cases and vary presentation order.

Scripted change streams are a good start for testing mechanisms. They cannot establish performance under real agent behavior. Likewise, excluding proofs is reasonable, but then the output is empirical compatibility evidence, not a demonstrated system of sound semantic equivalence.

**I would proceed after revising S3, S5, and activation semantics.** The design is now concrete enough to expose its own limits. The most valuable result would be finding a substantial class of useful changes that preserve shared guarantees, remain cheap to check, and do not merely move work into a kernel, a reviewer, or production.
