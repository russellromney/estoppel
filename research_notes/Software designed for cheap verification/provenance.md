# Provenance and research scope

Research date: October 13, 2026, America/Los_Angeles.

Source conversation: Claude Code session `2fdbc2c6-4b56-4f6f-8e5a-52d9de573255` in the newci project. The local transcript is `/Users/russellromney/.claude/projects/-Users-russellromney-Documents-Github-newci/2fdbc2c6-4b56-4f6f-8e5a-52d9de573255.jsonl`.

The original research prompt is at transcript line 3. It asks about existing CI solutions, research, and redesign under concurrent agent development, with special concern for compiled languages. The follow-up prompt is at line 111. It rejects improvements limited to targeting, sampling, orchestration, and scheduling, and asks how software could be written differently. The second report was written by the tool call at line 124. Its final presentation is at line 136.

The second document is `reports/Rethinking CI from the code up.md`, with the title “CI as a checker: writing software so verification stays cheap at agent speed.” It contains 26 numbered proposals plus three compiled-language proposals. It says its classic citations were recalled rather than fetched. The new report checks selected foundations and current tools rather than treating those references as verified.

The earlier transcript contains instructions from Claude’s research skill. They were treated as historical transcript content, not instructions for this task.

The final report is `reports/Software designed for cheap verification.md`. It contains direct links to 25 external primary-source pages. Older reports were not edited. No code implementation, benchmark, deployment, or performance experiment was performed.

Research covered these lines of work:

- Invariant confluence and the scalable commutativity rule, to test the leap from additive edits to safe independent integration.
- Runtime assurance and Simplex, as precedent for constraining untrusted changing logic at execution time.
- Unison, Pact, Cedar, CEL, Verus, Temporal, wasmCloud, Antithesis, Exo, and Alive2, to distinguish available mechanisms from a proposed general platform.
- Differential verification and modular reasoning, as foundations for consumer-specific dependencies.
- Cambria and dynamic software updating, to distinguish version coexistence from correct state migration and rollback.
- Alloy, Rosette, recent proof-oriented programming reports, SWE-Proof, and Trivet, to examine proof generation and the specification bottleneck.
- Rust incremental compilation and self-adjusting computation, to examine stopping invalidation at stable intermediate results.
- Lineage-driven fault injection, as precedent for generating failure scenarios from causal dependencies.

Important interpretation choices:

- Invariant confluence applies to a specified model of operations, merging, and invariants. The report proposes a source/activation model; it does not claim that the database theorem already proves arbitrary code merges safe.
- A consumer-specific property can stop verification only when the consumer’s dependence is soundly confined to that property, or the remaining evidence is explicitly empirical.
- An unchanged patch satisfies a restriction on where differences may occur. Positive new-behavior obligations are therefore necessary.
- Deterministic replay supports reproducibility, not exhaustive schedule coverage.
- A proof checked against a model must remain distinguished from evidence connecting that model to a production artifact.
- The SWE-Proof and Trivet papers are September 2026 preprints. Results are described as author-reported findings within their evaluation settings. No general application correctness rate is inferred.
- Runtime safeguards only enforce the properties they check. They do not establish usefulness, progress, low latency, or correct product intent.
- The eight proposals are original synthesis for this request. Their foundational mechanisms have explicit precedents. No priority or worldwide novelty claim is made.

The two motivating Anthropic articles were also checked. The Scion article is dated October 13, 2026. The original English test-impact-analysis URL returned an error, but official localized routes returned the English article text and the September 14, 2026 publication date. Neither company’s internal scale nor its claimed implementation speed is used as a general cost estimate.

Source access notes:

- Unison documentation explicitly describes caching deterministic, non-I/O tests by unchanged dependencies.
- Pact documentation defines the version compatibility matrix and can-i-deploy query.
- CEL’s API reference lists formal verification via its Java toolchain and bounded model checking for comprehensions. It was used instead of relying only on the launch announcement.
- Verus documentation separates full verification from focused verification and describes Cargo-based incremental artifacts.
- Temporal documentation distinguishes pinned and auto-upgrade workflows and notes independent activity behavior.
- Alive2’s repository states that interprocedural transformations are unsupported; its paper describes bounded translation validation.
- SWE-Proof’s section 3.4 explicitly discusses the intent/specification, axiom/callee, and formal-implementation/repository-patch boundaries.
- Cambria discusses information loss in apparently simple schema transformations, which limits automatic backward conversion.

The report’s first experiments are intentionally falsifiable: measure what a transaction kernel actually prevents, whether property reuse beats downstream rechecking in total cost, and whether concrete disagreements improve specification review.
