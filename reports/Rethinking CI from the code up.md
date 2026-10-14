# CI as a checker: writing software so verification stays cheap at agent speed

This is a follow-up to [Rethinking CI for agentic coding](Rethinking%20CI%20for%20agentic%20coding.md). That report's 15 directions all kept the same premises: code is text, a change is a diff, and correctness comes from re-running examples after the fact. Integration merges whole snapshots, and deployment ships a whole artifact. With those premises fixed, all you can do is choose which jobs run and when. This document drops them. It asks how software itself could be written so that CI and CD stop being a bottleneck when many agents change code at once.

Note on sources: this document is mostly design thinking. The classic papers and systems it cites (Parnas, Necula, Pnueli, Doyle, CALM, Unison, Darklang, Grove and others) are cited from memory, not re-fetched for this document. Figures about agent-era CI come from the earlier report's notes.

---

## 1. What CI is actually for

CI exists to rebuild information that the code does not carry. A change needs five things answered before anyone should trust it:

| # | Question | Where the answer lives today | What CI does to recover it |
|---|---|---|---|
| 1 | **Footprint**: what can this change affect? | Nowhere. It is implicit in imports, globals, reflection, config, the database and the network. | It guesses from build graphs and coverage, then re-runs a lot to be safe. |
| 2 | **Intent**: what is it supposed to do? | The PR description and the author's head. | Nothing. Tests encode *old* intent, so any intended change looks like a failure. |
| 3 | **Evidence**: why believe it does that, and nothing else? | Re-derived on each run. | It re-executes tests for every new combination of code. |
| 4 | **Assumptions**: what did it rely on that a concurrent change could break? | Nowhere. | It re-tests combinations: merge queues, rebase-and-rerun. |
| 5 | **Reversibility**: how cheap is it to undo? | It is expensive. Whole-artifact deploys, revert commits and one-way data migrations. | Because undoing is expensive, CI blocks hard before merge. |

**Re-execution is the universal fallback for missing information.** Each missing answer turns into compute or waiting. Targeting, sampling and scheduling only shave constant factors off that fallback.

A rough cost model makes the scaling problem plain:

```
CI cost ≈ (change rate) × (cost to re-derive trust per change)
        + (change rate)² × (probability two in-flight changes interact) × (cost to re-check the pair)
```

Agents raised the change rate 10–25x in about six months at the heaviest users. The first term grows linearly with it. Today the per-change cost scales with the size of the affected closure, which in a well-connected codebase grows with the codebase. The second term grows with the square of the rate. That is why merge queues collapse first.

A ground-up redesign has four goals, which I'll treat as laws:

1. **Per-change cost should scale with the size of the semantic change**, not the size of the codebase.
2. **Interaction cost should scale with the interactions that actually happen**, not with every pair of changes in flight.
3. **Evidence should be produced once and reused forever.** That requires results to be pure functions of content.
4. **Being wrong after merge should be cheap and precise to undo.** Then the gate before merge can be thin.

**Thesis: make code carry the five answers itself.** Then CI stops being a re-execution engine and becomes a *checker*. It checks certificates, keeps track of which claims are still justified, and watches production. Everything below is a way to move one of the five answers out of CI and into the code.

---

## 2. Agents change which practices are expensive

Many good practices were rejected because they cost too much human writing time. Agents bring writing cost close to zero. The costs that dominate now are verification compute, human attention, coordination between concurrent writers, and latency. So every practice rejected for being "too much effort to write" deserves a second look.

| Practice | Why teams skipped it | Agent-era cost to write | What it buys CI |
|---|---|---|---|
| Formal specs, contracts, refinement types, proofs | Slow, specialist work | Low for annotations and small proofs; specs still need human judgement | Checking instead of testing |
| Explicit types, imports and effects everywhere | Verbose | ~0 | Impact that can be computed exactly |
| Executable reference models | Two implementations to maintain | Low | A durable oracle that is independent of the implementation |
| Never break APIs; add new versions instead | Cruft, migration work | Low; agents do the migrations | Additions that cannot break anything |
| Codemods instead of hand edits | Writing a tool takes longer than doing the edit | ~0 | Changes that can be replayed and that commute |
| Dense assertions and invariants | Tedious | ~0 | Continuous verification in production |
| Writing down intent and assumptions per change | Paperwork | ~0 | Precise semantic conflict detection |
| Regenerating code from a spec rather than editing it | Generators were weak | Feasible now | Implementations become disposable |

What becomes expensive now is anything that needs a **human to decide what is wanted**, anything that **re-runs**, and anything that **serializes**. Design around those three.

Two metaphors carry most of the ideas below:

- **The codebase is a database with many fast, untrusted, concurrent writers.** Distributed systems have a toolkit for this: partition writes, make operations commute, validate optimistically, and keep certificates that are cheap to check.
- **An agent is a fast, untrusted compiler from intent to code.** Compiler correctness has a toolkit for this: translation validation, certifying compilers and proof-carrying code. You do not verify the compiler. You check each output.

---

## 3. The ideas

There are 26 ideas in seven groups. Each one says how software would be **written** differently, what CI **becomes**, the **theory and precedent** it builds on, the **hard parts**, and the **smallest experiment** that would test it.

### Group A: make the footprint a static property of the code

#### 1. Use effects and capabilities as the impact type system

**Write it this way.**
- Keep a pure core.
- All I/O, time, randomness, database, network and global state goes through explicit capabilities or algebraic effects. Examples: Koka, Unison abilities, OCaml 5 effects, Effect-TS, Roc platforms, WASI components.
- In Rust, Go or TypeScript today, the same idea is the sans-I/O style. Pass capability structs, and ban ambient globals with lints.

**What CI becomes.**
- Impact analysis follows the types, and it is *sound*. A function can affect the world only through its return value and its declared effects.
- A test of a pure function is a pure function of two things: the hash of the code it can reach and its inputs. Its result can be cached forever and shared across every branch and agent.
- **One mechanism replaces five pieces of test infrastructure.** Mocks, record/replay, deterministic simulation and safe production shadowing are all "run the same code under a different effect handler". The test harness, replay engine, simulator and shadow sandbox become one thing.

**Theory and precedent.** Effect systems (Lucassen & Gifford 1988). Algebraic effects and handlers (Plotkin & Pretnar). Object capabilities (Miller 2006). Noninterference (Goguen & Meseguer 1982). Unison already caches pure test results by hash. Sans-I/O protocol libraries such as h11 and quinn-proto are the industrial version.

**Hard parts.**
- Effect polymorphism is awkward for humans to write. Agents don't care much.
- "Pure" code still has performance and memory behaviour.
- Calls into foreign code (FFI) and third-party libraries leak ambient authority.

**Smallest experiment.** Convert one service to a sans-I/O core plus effect handlers. Measure three things: the share of tests that become cacheable pure tests, the flake rate, and how precise impact analysis becomes compared with build-graph diffing.

#### 2. Depend on specs, not implementations

Parnas (1972) said modules should hide the design decisions most likely to change. Make that mechanical:

- Every module boundary has a spec: types, contracts and properties.
- Callers' verification depends only on that spec, never on the implementation.
- An implementation change that preserves the spec *stops impact at the boundary*. This is the behavioural version of interface-hash early cutoff in builds: an ABI jar stops recompilation, and a spec stops re-verification.
- Agents measure how often each part of the code changes and move boundaries so that the fastest-changing decisions are hidden behind specs.

**What CI becomes.** Verifying a change means re-checking the changed module against its spec. Only spec changes propagate to callers.

**Precedent.** Kotlin ABI jars and Bazel ijar, for compilation. Modular verification in Dafny and SPARK. Consumer-driven contracts (Pact).

**Hard parts.** Hyrum's law: callers come to depend on behaviour the spec doesn't promise. The fix is idea 10. A differential oracle at each boundary shows when observed behaviour changed beyond the spec. Then either the spec is extended or the change counts as a break.

#### 3. Store code as content-addressed, typed definitions, not text files

This is the Unison model, taken seriously:

- Each definition is stored under the hash of its elaborated, type-checked syntax tree.
- Names are pointers to hashes. Text is just one view of the code.
- A change adds new definitions and moves names. Nothing is overwritten.

**What CI becomes.**
- Each definition is type-checked, compiled and has its pure tests run **once, ever**, across all branches and agents.
- The cache is global by construction, so cache-key bugs cannot happen.
- Textual merge conflicts disappear. The only possible conflict is two agents pointing the same name at different hashes.
- Dependents keep pointing at the old hash until someone migrates them, so a change cannot break them at merge time.

**For compiled languages** this is the limit of compile caching. You store elaborated IR, so nothing is parsed, macro-expanded or type-checked twice anywhere.

**Agents don't need text.** They can work through a definition API with structural operations. Humans get a rendered view for review.

**Hard parts.**
- Ecosystem gravity: git, editors and code review all assume text.
- Large refactors produce many new hashes, and propagating them needs tooling.
- Runtime identity for things like serialized data.

**Smallest experiment.** Build a sidecar for an existing language. Hash items after type-checking; for Rust, rustc's stable hashes or rust-analyzer's item tree would do. Key test results on the hash of every item a test can reach. Then measure the cache hit rate across a week of concurrent agent branches.

#### 4. Write in a dialect tuned for the verifier, not the writer

Many language features trade the verifier's cost for the writer's convenience:
- global type inference;
- glob imports;
- macros and proc macros;
- implicit instance or trait resolution across crates;
- textual `#include`;
- generics instantiated across crate boundaries;
- reflection and dispatch by string;
- untyped configuration;
- monkeypatching.

Agents don't need that convenience. So write in a dialect that is verbose but *local*:

- explicit signatures and per-item imports;
- no glob imports;
- no proc macros in frequently changed crates, or macros pre-expanded and checked in;
- trait objects or explicit instantiation at crate boundaries, under a monomorphization budget;
- no reflection;
- configuration that is typed and part of the build graph.

Enforce all of it with lints.

**What CI becomes.**
- Impact can be computed from syntax alone.
- Static analysis has no blind spots for reflection or config.
- Compile units get smaller, and an edit triggers less recompilation.
- The "blind spots" list in the earlier report's impact certificate shrinks toward zero.

**Precedent.** Go's design rationale (2012) was explicitly about dependency fan-out. Zig is explicit by design. Google's C++ style rules restrict includes. Rust has done work on polymorphization.

**Hard parts.** Dynamic dispatch costs runtime performance. Library ecosystems lean on macros. Verbose code is harder for humans to skim.

#### 5. Make risk a type

**Write it this way.** Label data and code by how critical they are: money, authentication, personal data, durability. Propagate the labels with information-flow typing.

**What CI becomes.**
- For any change, the compiler finds the most critical flow the change touches.
- That determines the evidence required. For example, money paths need an equivalence proof or a reference-model check. UI copy needs a smoke render.
- Review and verification policy becomes a type rule, not a heuristic classifier or a CODEOWNERS file.

**Theory.** Information-flow control: Denning (1976), Jif and Myers' later work.

**Hard parts.** Labels tend to spread everywhere ("label creep"), and parts of the code need declassification.

**Smallest experiment.** Run a three-label taint analysis over a real codebase. Check how well the labels predict past incidents.

### Group B: make intent explicit and checkable

#### 6. Give each change a declared kind

Every change declares a kind, and each kind has its own cheap verifier.

| Kind | Meaning | How to verify it |
|---|---|---|
| **Refactor** | Behaviour is preserved | Check equivalence of old and new. Use proof where feasible; differential fuzzing on recorded and generated inputs as the cheap fallback. No existing tests need to run if equivalence is shown. |
| **Extension** | New behaviour only on inputs or entry points that were not reachable before | Show old behaviour is unchanged on the old domain (a *conservative extension*). Write new checks only for the new domain. |
| **Modification** | Behaviour changes on existing inputs | Check against a declared behavioural delta (idea 8). |
| **Dependency bump, config change, data migration** | — | Each has its own specialised verifier. |

Agents can cheaply split a mixed change into kind-pure steps, for example "refactor, then a three-line modification". That turns one expensive, ambiguous verification into a cheap equivalence check plus a small delta check.

**Theory and precedent.**
- Regression verification (Godlin & Strichman 2009): prove successive versions equivalent instead of testing them.
- Microsoft's SymDiff and differential assertion checking (Lahiri et al., 2012–2013).
- Relational Hoare logic (Benton 2004) and product programs (Barthe et al. 2011).

**Hard parts.**
- Program equivalence is undecidable in general. The fallback is probabilistic.
- A "refactor" often hides a performance change. Treat performance as its own claim (idea 13).

**This bet can be measured.** If most agent changes are refactors and extensions, which seems plausible but nobody has published data, then most CI work can be replaced by checks that need no tests at all.

#### 7. Store changes as transformations, not diffs

**Write it this way.** Store a change as the program that makes it, plus its intent: a codemod or semantic patch, with a small hand-written residual.

**What CI becomes.**
- **Rebasing means re-running the transformation on the new base**, not a three-way text merge.
- Example: "rename `X` to `Y`" and "add a call to `X`" conflict or silently break as text diffs. As transformations they commute, because replaying the rename also catches the new call.
- Verified transformations (rename, extract, inline, change a signature and update its call sites) are proven correct once, as transformations. Applying one needs only a well-formedness check.
- Only the residual needs behavioural verification.
- For LLM agents the residual can be kept as intent and re-derived when it conflicts with the new base ("rebase by re-derivation"). The re-derived residual is then re-verified.

**Theory and precedent.**
- Darcs patch theory, including its "replace" patches that commute with edits.
- Pijul, and categorical theories of patches (Mimram & Di Giusto 2013).
- Coccinelle semantic patches (used on the Linux kernel), Comby and OpenRewrite.
- Google's large-scale change tooling, Rosie.
- Correctness proofs for refactorings (Schäfer et al.).

**Hard parts.** A transformation may not apply cleanly on a new base. Re-derivation by an LLM is nondeterministic. Storage and review tools are built around diffs.

#### 8. Declare the behavioural delta, and use the old version as the oracle

**Write it this way.** A change states where behaviour is *meant* to differ. For example: "responses for currency=JPY now round to 0 decimals". The system runs the old and new versions on a corpus of recorded traffic and generated inputs. It then checks:

```
observed behavioural diff  ⊆  declared diff
```

The oracle is the previous version. Nobody writes or updates expected values by hand.

**Why this matters.** This removes the main way unit tests fail agents: tests that encode implementation details and must be rewritten on every change. There is no stored expected value to update. The expectation is "whatever main did, except where declared". Unexpected differences are either declared (a human reviews one sentence) or they are bugs.

**What CI becomes.**
- The thing humans review becomes the **declared delta**: short, about intent, and easy to judge.
- Code diffs become agent business.

**Theory and precedent.**
- Differential testing (McKeeman 1998).
- Hyperproperties and 2-safety (Clarkson & Schneider 2010). "New equals old except on D" is a relational property.
- Twitter's Diffy (2015) and GitHub's Scientist: production versions of "compare old and new".

**Hard parts.**
- Nondeterminism creates noise. Ideas 1 and 13 make this tractable.
- The corpus may miss rare inputs.
- A declared delta written in English must become a checkable predicate. An LLM can propose it, but a non-LLM evaluator must decide.
- Recorded traffic raises privacy issues.

**Smallest experiment.** Take one service with recorded traffic. Apply declared-delta checking to its last 200 merged changes. Measure false alarms and real catches against the existing test suite.

#### 9. Treat the spec as source, the agent as an untrusted compiler, and CI as a translation validator

**Write it this way.** The durable artifact is the spec: types, contracts, properties, and a small *executable reference model*. The implementation is derived and can be regenerated.

You cannot verify the agent. So validate each translation it produces. Translation validation (Pnueli, Siegel & Singerman 1998) does this for compilers: rather than proving the compiler correct, it checks each output against its input.

**In practice.**
- Keep a small executable model of each kernel component.
- Check every implementation against it with differential and property-based conformance tests.
- Humans own the models. Agents own implementations.
- Unit tests of implementation internals become agent scratch work and are never kept.

**Precedent.**
- AWS's ShardStore paper (SOSP 2021): executable reference models plus property-based conformance checking for an S3 storage node.
- The P language, used at AWS for S3's strong-consistency work.
- FoundationDB's simulation.
- Certifying compilers.
- The "whenwords" pattern from the earlier report: ship only a spec plus a conformance suite.

**Hard parts.**
- Kleppmann's point stands: writing the spec stays the bottleneck.
- Models are hard to write for code that is performance-sensitive, I/O-heavy or UI-heavy.
- The spec itself can be wrong.

### Group C: carry the evidence; check it instead of re-running

#### 10. Proof-carrying changes

Necula & Lee (1997): untrusted code ships with a proof, and the consumer checks it with a small, fast checker. Finding a proof is expensive and checking it is cheap. That is exactly the right asymmetry when the generators (agents) are cheap and parallel, and central verification is the bottleneck.

**What a change ships with.**
- type derivations (already true for typed languages);
- refinement-type or SMT certificates (Liquid Haskell, Verus for Rust, F*, Dafny);
- equivalence proofs (idea 6);
- conformance certificates (idea 9).

**What CI becomes.** CI *checks* evidence and never *searches* for it. The search runs in the agent's sandbox and is paid for by the producer.

**Incrementality comes for free.**
- Modular proofs depend only on the specs of the code they call, so a change re-checks only proofs whose spec dependencies changed.
- Dafny already caches verification results at fine granularity (Leino & Wüstholz 2015).
- When a proof breaks, repairing it (Ringer's proof repair work) is an agent task.

**Hard parts.**
- SMT proofs are not always small or quick to check.
- Solver nondeterminism makes some proofs pass or fail unpredictably. The Mariposa study (2023) measured this proof instability. The fix is to emit checkable certificates, not "the solver said yes once".
- Proofs cover only what was specified.

#### 11. Make code deterministic by construction

**Write it this way.** The runtime is deterministic. Time, randomness, thread scheduling and I/O ordering all enter through effects with seeds.

**What follows.** Any check's result becomes a pure function of the code hash, the input hash and the seed. Then:
- **Flaky tests cannot exist.** A failure is a seed you can replay.
- **Results can be cached and shared** across branches and agents.
- **Evidence from an untrusted agent sandbox can be spot-checked.** Replay a random sample instead of re-running everything. Determinism turns "trust" into an audit.
- **Finding the culprit is exact bisection**, with no Bayesian model of flakiness.
- **Production incidents replay locally** from a recorded seed and input log.

**Precedent.** FoundationDB and TigerBeetle simulation. Antithesis, which makes things deterministic at the hypervisor level. Temporal's deterministic workflow replay. The Elm architecture. Meta's Hermit deterministic container (2022).

**Hard parts.** High-performance multithreaded code. Third-party libraries. Determinism at the hypervisor level is heavy. Language-level determinism is cheaper but invasive.

#### 12. Run CI as a truth maintenance system, not a pipeline

**The reframe.** The repository holds a set of **claims**, for example:
- "`settle()` satisfies spec S";
- "service A is compatible with B v3";
- "p99 latency < 50 ms on bench X";
- "no personal data flows to logs".

Each claim has a **justification**: its evidence, plus the hashes of everything it depended on. When a change lands:
1. It retracts the justifications whose dependencies it changed.
2. The system re-justifies only those, cheapest strategy first: proof check, then cached result, then equivalence, then test, then human.
3. Main is never simply "green". It is a ledger of which claims hold right now, and how strongly.
4. Deployment asks one question: are the claims this deploy depends on justified?

**Theory.**
- Doyle's truth maintenance system (1979).
- de Kleer's assumption-based TMS (1986). An ATMS tracks *sets of assumptions* (contexts). That lets one structure reason about many concurrent branches at once, which is exactly the many-agents case.
- "Build Systems à la Carte" is the special case where every claim is "artifact X is up to date".

**Why this matters.** This is the substrate the other ideas plug into. It replaces the *pipeline* as CI's core abstraction. Proofs, cached results, equivalence checks, conformance checks, shadow-traffic evidence and human approvals all become justifications of the same kind, with dependencies attached.

**Hard parts.**
- Capturing dependencies completely. It is sound only with ideas 1 and 3, or with hermetic sandboxing.
- Claims multiply.
- Showing all this to humans in a usable way.

#### 13. Treat performance and resources as claims with their own evidence

**Write it this way.** Performance regressions are what slip through behaviour-focused verification, and agents produce them often. Make performance claims explicit:
- Complexity bounds as annotations, which resource-analysis type systems can check (RAML, Hoffmann et al.).
- Allocation and latency budgets per entry point, checked on a deterministic benchmark harness (instruction counts rather than wall-clock time, to remove noise).
- Each claim's dependencies are the code hashes of the hot path.

**What CI becomes.** A change that touches no hot path does not re-run benchmarks. One that touches a hot path re-checks only that entry point's budget.

### Group D: let concurrent changes proceed without coordination

#### 14. Assumption manifests: record each change's semantic read set

**Write it this way.** Agents can cheaply list what they relied on. For example:
- "assumes `parseDate` returns UTC";
- "assumes `orders.total` excludes tax";
- "assumes `UserId` is never reused".

Each assumption is recorded as a checkable predicate tied to definitions: a type, a contract, a property, or at minimum a precise statement attached to a hash.

**Why it works.** In database terms, the manifest is the change's *read set* and the diff is its *write set*. At commit, the check is: did any concurrently committed change's writes falsify my reads?
- **If not**, my evidence still holds on the merged result, and the combination needs no re-test.
- **If so**, that is the semantic conflict, found precisely and explained in plain words.

**Theory and precedent.**
- Optimistic concurrency control (Kung & Robinson 1981) and serializability theory.
- SafeMerge (Sousa, Dillig & Lahiri, OOPSLA 2018), which verifies that a three-way merge has no semantic conflict.
- Weave's entity claims from the earlier report are a coarse version.

**Bonus.** The assumptions list is also the best thing for humans to review, and the best seed for generating tests.

**Hard parts.**
- Agents will miss some assumptions, so manifests are incomplete. Even incomplete ones catch the assumptions most often broken. Keep a sampled interaction test as a backstop.
- Checking assumptions has its own cost.

#### 15. Apply CALM to codebases: make most changes monotone

**The theory.** The CALM theorem (Hellerstein 2010; Ameloot et al. 2011; Hellerstein & Alvaro, CACM 2020) says that programs whose outputs only grow as their inputs grow (monotone programs) can run without coordination.

**The analogy.**
- A code change that **only adds** commutes with every other such change. Examples: new definitions, a new case at an open extension point, new routes, new tests. The condition is that it cannot change the meaning of existing code.
- Changes that are **not monotone** need coordination: modify, delete, rename, change a spec.

**Write it so most work is monotone.**
- Use open extension points instead of central switch statements, registries and lists. Examples: distributed slices (`linkme`, `inventory` in Rust), plugin tables, open variants, extensible records.
- Never break an API; add instead (idea 19).
- Put new behaviour behind new names.
- Treat deletion as a separate garbage-collection phase, run on a schedule by a janitor agent that holds exclusive rights.

**What CI becomes.**
- Monotone changes skip the queue and are verified in isolation. Checking that an addition is conservative is itself a check that can be done.
- The scarce coordination capacity is kept for the non-monotone minority.

**Hard parts.** "Cannot change existing meaning" must actually be enforced, and language design decides whether it can be:
- Rust's orphan rule helps.
- Haskell orphan instances, Python import side effects, C++ argument-dependent lookup and overload resolution, and Ruby reopening classes all break monotonicity.

A language designed for concurrent agents should make *every addition provably conservative*.

I think this is the freshest framing in this document, and it is worth a proper write-up on its own.

#### 16. Edit code as structure, with conflicts as typed values

**The precedent.**
- Grove (Adams, Omar et al., POPL 2025) is a calculus for collaborative structure editing. Its edits commute (CRDT-style), and conflicts are represented as typed structures in the program rather than as textual markers.
- Hazel's typed holes (Omar et al., POPL 2017 and 2019) keep every intermediate program well-typed and runnable.

**What this enables.**
- Code is always checkable, even in the middle of a conflict. A conflict is a hole the type checker understands.
- The rest of the program can still be verified, and even run, around the hole.
- Agents resolve conflicts using the hole's expected type as the spec.

**What CI becomes.** "Can't build: merge conflict" stops existing. Verification works around localized holes.

**Hard parts.** This is research-stage work, and it needs storage that is native to structure (idea 3).

#### 17. Coordinate on contracts first; compose with assume-guarantee reasoning

**Write it this way.**
- Agents don't coordinate on code. They coordinate on interfaces.
- An interface change is a small, coordinated, reviewed event: proposal, then the consumers' agents acknowledge, then it lands.
- Behind an interface, writes are either exclusive to one agent at a time or open to everyone under idea 14.

**What CI becomes.**
- The system is correct by composition. Each component guarantees its contract, assuming its dependencies meet theirs.
- Global integration test suites shrink to a thin set of end-to-end smoke checks, run after merge.

**Theory.** Rely-guarantee reasoning (Jones 1983), assume-guarantee compositional verification, consumer-driven contracts.

**Hard parts.** Some properties don't compose: performance under contention, distributed timing, resource exhaustion. Those still need system-level simulation (idea 11) and load checks, run after merge.

#### 18. Partition write ownership dynamically

**Write it this way.** Assign each in-flight agent task a *lease* on the definitions or modules it will change. The lease is predicted from the task description and the impact analysis. Overlapping leases are scheduled one after the other or split into separate tasks, before any code is written.

**Why this is different from the earlier report's scheduling idea.** The lease is a first-class part of how code is written. The agent cannot write outside its lease without renegotiating, so its read and write sets are bounded up front. That makes ideas 14 and 15 cheaper and more accurate.

### Group E: make being wrong cheap, so the gate before merge can be thin

#### 19. Grow by accretion only, with versioned names

**The principle.** Rich Hickey's "Spec-ulation" (2016): never break; only accrete.
- The old and new versions of a function live side by side (`f` and `f2`, or by hash in Unison).
- Callers migrate explicitly, one call site at a time, each as its own small change.
- Dead versions are garbage-collected later.
- Elm enforces semantic versioning mechanically from API diffs.

**What CI becomes.**
- A change that adds `f2` cannot break anything. It is a conservative extension (idea 15).
- The risky step is moving call sites. Each move is small, local and reversible, and can be guarded by comparing old and new at runtime (idea 21).
- Breakage is prevented by construction instead of being discovered at merge.

**Cost.** Cruft, duplicated code and more names. Agents absorb this cheaply, and a janitor agent cleans up.

#### 20. Deploy and revoke individual definitions

**Write it this way.** Deploy individual definitions or handlers, not whole artifacts.

**Precedent.**
- Darklang's "deployless" model (2019): every edit is live immediately behind a feature flag.
- Erlang hot code loading.
- Unison Cloud deploys by hash.
- Per-function deploy on edge platforms.

**What CD becomes.**
- With content addressing, revoking a change means pointing a name back at its previous hash. That takes milliseconds, with no rebuild, no revert commit and no redeploy of unrelated code.
- CD becomes a pointer update.
- Because revocation is cheap and precise, the gate before merge can be set by risk. Verification continues after deploy.

**Hard parts.**
- State and schema (see idea 22).
- Definitions must stay consistent with each other. Treat a release as a consistent snapshot of pointers.
- Compiled native code loses link-time optimization across definitions. Use tiered compilation or JIT.

#### 21. Shadow execution as the main oracle, with effects sandboxed and driven by traces

**Write it this way.** Effects are explicit (idea 1), so the runtime can run the candidate version alongside the current one on live traffic.
- The candidate's effects are *captured by a handler, not performed*.
- Its writes are recorded, not applied.
- Its external calls are answered from the primary's recorded responses.
- Compare outputs and effect logs against the declared delta (idea 8).

Darklang's trace-driven development already used real request traces as the substrate for development and testing.

**What CI becomes.**
- CI becomes continuous and grounded in production.
- The test suite is "all traffic since the last change". It is free and always matches real usage.
- No one maintains these tests, and coverage follows what users actually do.

**Hard parts.**
- Privacy and compliance.
- Capturing effects in non-idempotent flows.
- The cost of running everything twice. Sample it.
- Rare paths need synthetic traffic, so combine this with reference models (idea 9) and property-based generation.

#### 22. Event-sourced systems: production history is the test suite

**Write it this way.** Store state as an immutable event log plus pure, deterministic projections. Precedents include Datomic, stream processing on Kafka, and event sourcing generally.

**How each step changes.**
- **Changing business logic** means writing a new projection.
- **Testing** means replaying the real log, or a sampled window of it, through the old and new projections and diffing the resulting state. This is exact, deterministic and grounded in real data.
- **Deploying** means building the new projection alongside the old one, letting it catch up, then switching reads.
- **Rolling back** means switching reads back.
- **Schema evolution** uses bidirectional lenses so that versions coexist (Cambria, Ink & Switch 2020).

**Why it matters.** Data migrations are the main irreversible step in CD today. This makes them reversible.

**Hard parts.**
- Evolving the event schema itself.
- Replay cost for long histories; use snapshots plus incremental replay.
- Projections must be pure.
- Deletion rules such as GDPR erasure.

#### 23. Dense runtime invariants as continuous verification

**Write it this way.**
- Assertions everywhere, run in production, failing safe when violated (TigerBeetle style).
- Contracts in the design-by-contract sense, evaluated in production on a sample of calls.
- Invariants mined from traces (Daikon, Ernst et al. 2001) become candidate contracts.

**What CI becomes.**
- A change that violates a learned invariant on shadow traffic is flagged with an exact explanation: "`balance >= 0` held on 40M calls; your version violates it for refunds".
- A violation automatically revokes the responsible version (idea 20).
- A large share of "testing" moves from examples before merge to always-on checks against real inputs.

### Group F: structure the codebase around verification

#### 24. Two-speed codebase: a verified kernel and a disposable periphery

**Write it this way.**
- **Kernel:** small and slow-changing. Specs, models and core invariants live here. It is owned by humans and heavily verified with proofs and models.
- **Periphery:** glue code, UI and integrations that agents change constantly. It can be regenerated from spec. It is verified only by conformance to kernel contracts and by old-versus-new comparison (ideas 8 and 21).
- **Policy:** periphery code has no durable unit tests. If it breaks, regenerate it.

**What this fixes.** This is the principled answer to "unit tests are getting in the way". Durable tests exist only at the kernel boundary. Tests that encode implementation details are agent scratch work and are never kept.

#### 25. Align the units

Today seven units all differ:
- the task unit (a ticket);
- the edit unit (files);
- the compile unit (a crate or target);
- the test unit;
- the deploy unit (an artifact);
- the ownership unit (a team);
- the rollback unit (a commit or deploy).

Each mismatch forces extra work. You compile more than you changed, test more than you compiled, deploy more than you tested, and roll back more than broke.

**Write it this way.** Design *cells*. One task touches one cell. A cell compiles, verifies, deploys and rolls back on its own, behind a typed contract. For compiled languages, the WebAssembly Component Model with WIT interfaces already gives you:
- separate compilation;
- imports typed as capabilities;
- linking at the interface level, so generics are not instantiated across cell boundaries.

**What CI becomes.** The cost per change scales with the size of a cell, not the size of the repo.

#### 26. Version internal dependencies, with agents upgrading continuously (the opposite of live-at-head)

**Why live-at-head hurts now.** In a live-at-head monorepo (Google's model), every change is integrated with all of its dependents at once. So every change can break everyone, which forces global CI.

**What agents make possible.** Agents make upgrade work cheap, so version boundaries can come back *inside* the monorepo:
- Dependents pin a version of each internal library.
- A library change creates "upgrade available" tasks.
- Each dependent's upgrade is its own small change, verified locally.
- Breakage is spread out in time and confined to one place.

**Trade-offs.** Version skew and diamond dependencies. Bound them: keep at most two versions live, and have bots enforce an upgrade deadline.

### Group G: compiled languages specifically

Compiled languages hurt most because *building* test binaries often costs more than running them. So these ideas target derivation work, not test selection.

- **G1. The compiler as a persistent, shared database of facts, not a batch job over text.**
  - Store elaborated items by content hash (idea 3), and have every agent sandbox query the same store.
  - Compiling a branch then means compiling its delta.
  - Rust's query system and salsa already model compilation as a database. What's missing is making it persistent, shared across machines and branches, and keyed by content rather than file paths and timestamps.
  - The earlier research found nobody running this today. It is the clearest gap for compiled languages.
- **G2. Separate "is it correct?" from "is it fast?".**
  - Most CI questions are correctness questions, and those need neither optimized machine code nor a full link.
  - Answer them with checks (types, borrow checker, proofs) and a fast execution tier: an interpreter (Miri-style), a fast backend (Cranelift or TPDE), or hot-patching into a persistent test process (Zig incremental, Dioxus subsecond).
  - Run optimizing code generation only for release artifacts and for performance claims (idea 13).
- **G3. Design for compile locality.**
  - Set monomorphization budgets at crate boundaries.
  - Put interface crates that hold only types and traits between implementations, so implementation edits never propagate.
  - Keep proc macros out of crates that change often.
  - Split crates by how often they change, not by domain.
  - Build one test binary per crate, not one per test file. Cargo's own switch to this gave about 3x faster test compiles.

---

## 4. A change's life, end to end

Here is how one change moves through a system that combines these ideas:

1. **Intent.** A task arrives. The agent takes a lease on the cells it expects to touch (idea 18).
2. **Authoring in a sandbox forked from a warm main.**
   - The agent writes the change as transformations plus a residual (idea 7).
   - It splits the change into kind-pure steps (idea 6).
   - It records an assumption manifest (idea 14) and a declared behavioural delta (idea 8).
3. **Evidence, produced by the author and paid for by the author.**
   - Type checks run against a shared fact store (G1).
   - Refactor steps get an equivalence proof or differential check.
   - Modification steps are checked for observed diff ⊆ declared diff on replayed traces.
   - Kernel changes get conformance against the reference model, or proofs.
   - Everything is deterministic, so every result is a replayable seed (idea 11).
4. **Submission.** The central checker:
   - checks certificates and spot-replays a sample of the sandbox results (seconds);
   - checks the read set against concurrent writes (milliseconds);
   - lets monotone changes through without coordination (idea 15);
   - updates the claim ledger (idea 12).
5. **Merge.** Name pointers move. There is no queue and no "rerun CI".
6. **Deploy.** The new definitions go live in shadow mode (ideas 20 and 21). Once enough traffic matches the declared delta, they are promoted. Otherwise they are revoked automatically in milliseconds.
7. **Humans review three things:** intent declarations, kernel and spec changes, and the claim ledger for high-risk paths. Agents handle code diffs.

What disappears: pipelines, merge queues, flaky reruns, revert commits, and most hand-written expected values.

---

## 5. What happens to tests

Example-based tests split three ways:

- **Durable:** conformance and contract checks at kernel boundaries, properties, reference models, and invariants.
- **Ephemeral:** scratch tests agents write in their sandboxes and throw away when the change lands.
- **Replaced:**
  - Regression tests are replaced by the old version as oracle (ideas 8 and 21).
  - Integration tests are replaced by assume-guarantee reasoning plus shadow traffic (ideas 17 and 21).
  - Flaky tests cannot exist under determinism by construction (idea 11).

So teams deleting unit tests are right that tests tied to implementation details are the wrong thing to keep. They are wrong to replace them with nothing. Each should be replaced by something stronger and cheaper to maintain.

---

## 6. Honest objections

- **The spec bottleneck (Kleppmann).** Humans still have to say what they want. *Mitigation:* using the old version as the oracle means only *deltas* need specifying, never whole behaviour.
- **Hyrum's law.** Behaviour beyond the spec gets depended on. Old-versus-new comparison makes it visible rather than hiding it.
- **Ecosystem gravity.** The most radical ideas (3, 16, 20) need new languages, runtimes or storage. Most ideas have an incremental form: lints, sidecars, conventions.
- **Runtime cost.** Effects, dynamic dispatch, interpretation and running everything twice all cost compute. This trades verification compute for runtime compute. Nobody has measured the trade.
- **Brittle proofs and solvers.** Use certificates, not solver verdicts.
- **Privacy of production traces.** Recorded traffic needs redaction, synthesis or in-region replay.
- **Correlated blind spots.** When agents verify agents, they share failure modes. Knight & Leveson (1986) showed that independently written versions still fail together. So **LLMs propose, small sound checkers decide**. No LLM verdict should be a gate.
- **Properties that emerge only from the whole system.** Contention, distributed timing and resource exhaustion don't compose. Deterministic simulation and load checks still run, after merge.
- **Adoption.** No one will adopt 26 ideas at once. The question is which two or three carry the rest.

---

## 7. Where to start

The ideas rest on three bets. Each can be tested cheaply on a real repository's history before building anything.

1. **Most agent changes are refactors or additions.**
   - *Experiment:* classify about 1,000 recently merged agent changes as refactor, extension or modification, and as monotone or not.
   - Count how many touched central files (registries, routers, `mod.rs`, lists) that could become open extension points.
   - *Decision:* if refactors plus monotone changes exceed roughly 60%, declared change kinds, CALM-style concurrency and accretion (ideas 6, 15 and 19) pay off a lot.
2. **Assumption manifests catch semantic conflicts that tests only catch late.**
   - *Experiment:* replay a stretch of concurrent agent work and have agents emit manifests.
   - Compare the conflicts they predict with actual post-merge breakages and reverts.
3. **The old version is a good enough oracle.**
   - *Experiment:* take one service with recorded traffic and apply declared-delta comparison to its last N changes.
   - Measure false alarms, real catches, and catches the existing test suite missed.

If those hold, the substrate to build is a **claim ledger** (idea 12): content-addressed claims with justifications, plus an API agents submit evidence to. Merging would follow a read-set/write-set rule (ideas 14 and 15) instead of a queue. It can start as a sidecar on git and existing test runners, using item-level hashing for one language (idea 3 in sidecar form). Over time it can grow toward the more radical parts: effect-typed code, deploys per definition, and shadow execution as the default oracle.

**The thesis in one sentence:** stop running CI to rebuild what the code failed to say. Write code that states its footprint, intent, evidence, assumptions and undo path, and CI becomes a cheap checker plus a ledger of claims.
