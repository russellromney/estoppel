# Academic and Industrial Research on Faster, More Effective CI and Regression Testing (incl. CI under AI-agent changes)

Scope note: notes compiled 2026-10-13. Numbers marked "verified" were read from the source (abstract or full text) in this session. Numbers marked "(recalled)" come from well-known paper abstracts but were not re-fetched here; the report writer should treat them as lower confidence or re-check before quoting.

---

## 1. Regression test selection (RTS): Ekstazi, STARTS, HyRTS, granularity, static vs dynamic, safety; ML/LLM-based RTS

### Takeaway
Classic RTS research converged on a pragmatic result: coarse-grained (file/class-level) dependency tracking beats fine-grained (method/statement) tracking on end-to-end time, because analysis overhead dominates; dynamic RTS (Ekstazi) is the safety/precision reference, and static class-level RTS (STARTS) is nearly as good but can be unsafe under reflection. LLM-based RTS proper is still thin; most 2024–2026 LLM work targets test generation and prioritization rather than safe selection.

### Cited Findings
- Ekstazi (Gligoric, Eloussi, Marinov, ISSTA 2015): dynamic, file-level dependency tracking. On 615 revisions of 32 open-source projects (~5M LOC), it cut end-to-end testing time by 32% on average and 54% for longer-running suites vs. rerunning everything, despite selecting more tests than finer-grained techniques (verified) — [Ekstazi abstract](https://users.ece.utexas.edu/~gligoric/papers/abstracts/GligoricETAL15Ekstazi.txt)
- Key Ekstazi lesson: coarser granularity (files) gave lower end-to-end time than prior method/statement-level techniques even though it selects more tests, because collection and analysis overhead is lower (verified) — [Ekstazi abstract](https://users.ece.utexas.edu/~gligoric/papers/abstracts/GligoricETAL15Ekstazi.txt)
- Ekstazi was ported to C# (Ekstazi#, 2017), showing the file-dependency approach works on .NET (verified existence) — [Ekstazi# abstract](https://users.ece.utexas.edu/~gligoric/papers/abstracts/VasicETAL17EkstaziSharp.txt)
- STARTS / static RTS (Legunsen et al., FSE 2016; tool at ASE 2017): static class-level RTS over a class-dependency graph. One evaluation reports ~40.5% average testing-time savings vs. retest-all. STARTS selects more tests than Ekstazi, and Ekstazi had significantly fewer safety/precision violations (verified via search summary of follow-up comparison studies) — [search summary / HAW thesis](https://reposit.haw-hamburg.de/bitstream/20.500.12738/16796/1/BA_Reducing%20Testing%20Costs%20by%20Applying%20Regression%20Test%20Selection.pdf); [ASE 2022 journal-first: "An empirical comparison of four Java-based regression test selection techniques"](https://conf.researchr.org/details/ase-2022/ase-2022-journal-first-papers/18/An-empirical-comparison-of-four-Java-based-regression-test-selection-techniques)
- (recalled) Legunsen et al. FSE 2016 found static class-level RTS comparable to Ekstazi in end-to-end time, static method-level RTS imprecise and slow, and static RTS can be unsafe when reflection creates dependencies invisible to the static graph — [Gligoric PhD thesis covers this lineage](https://users.ece.utexas.edu/~gligoric/papers/Gligoric15PhD.pdf)
- (recalled) HyRTS (Lingming Zhang, ICSE 2018) is a hybrid that tracks dependencies at method level for changed methods and file level elsewhere, reporting fewer tests selected than Ekstazi at similar overhead. No numbers verified this session.
- Recent LLM-adjacent selection/prioritization work: a risk-based test-case prioritization approach fine-tunes an LLM to predict per-function fault-proneness from software metrics, then ranks tests by static reachability to risky functions (2025) — [ECU: Risk-Based TCP Using LLMs](https://thescholarship.ecu.edu/items/9aa654d1-2c36-4968-87a3-4ac3f5e28a04/full)
- LLM work in regression testing is mostly generation, not selection: TestWeaver (arXiv 2508.01255, 2025) adds lightweight program analysis / execution context to LLM regression-test generation; "Evaluating LLM-Based Regression Test Generation" (arXiv 2501.11086); DiffTestGen (arXiv 2607.16024, 2026) generates change-directed tests to expose behavioral differences between versions — [TestWeaver](https://arxiv.org/abs/2508.01255v1); [Evaluating LLM regression test gen](https://arxiv.org/pdf/2501.11086); [DiffTestGen](https://arxiv.org/pdf/2607.16024)

### Inferences
- For a CI product, file/target-level dynamic dependency tracking (Ekstazi-style, or build-graph-level like Bazel) is the proven safe baseline. Finer granularity rarely pays off end-to-end.
- Static RTS is the cheaper option but has known unsafety (reflection, dynamic dispatch, config/resources). Any "safe" claim must name these escape hatches.
- "LLM-based RTS" as a safety-preserving technique is not established in the literature. LLMs show up as ranking/risk signals or as generators of change-targeted tests (DiffTestGen, Meta JiT catching, section 6).

### Gaps
- No verified numbers for HyRTS this session.
- Did not find strong peer-reviewed results on RTS for multi-language/polyglot monorepos or distributed systems (beyond build-system-level selection at Google/Meta). Found no LLM-based RTS paper with a safety evaluation.

---

## 2. Predictive test selection (Meta), Google TAP, test prioritization, change-impact analysis

### Takeaway
At industrial scale, the winning approach is not safe RTS but learned, probabilistic selection over the build graph's transitive test set: Meta's predictive test selection runs about a third of transitively affected tests and still reports >99.9% of faulty changes, halving infra cost. Google's TAP work moved from "test everything affected" to statistical models of which targets transition, and explicitly avoids "rerun recent failures" because those are mostly flakes.

### Cited Findings
- Meta Predictive Test Selection (Machalica, Samylkin, Porth, Chandra; ICSE-SEIP 2019; arXiv 1810.05286): a model trained on historical test outcomes picks a subset of tests per change. It catches >99.9% of faulty changes (and >95% of individual test failures, recalled) while running about one third of the tests that transitively depend on modified code, cutting total testing infrastructure cost by 2x (verified) — [arXiv 1810.05286](https://ar5iv.arxiv.org/html/1810.05286); [Meta engineering blog](https://engineering.fb.com/2018/11/21/developer-tools/predictive-test-selection/)
- Google "Taming Google-Scale Continuous Testing" (Memon, Gao, Nguyen, Dhanda, Nickell, Siemborski, Micco; ICSE-SEIP 2017): Google could not test each change individually despite huge resources, so feedback lag grew. They (1) control test workload without hurting quality and (2) distill results to developers. Because flaky tests cannot all be removed, they rejected heuristics like "rerun tests that failed recently" (would mostly rerun flakes), and instead modeled factors behind PASSED→FAILED and FAILED→PASSED transitions (verified) — [paper PDF](https://web.eecs.umich.edu/~xwangsd/courses/w23/readings/googletest.pdf); [abstract](https://www.cs.umd.edu/~atif/pubs/Memon_2017_TGC_3103112.3103143-abstract.html)
- Follow-up: "Assessing Transition-based Test Selection Algorithms at Google" (Leong et al., ICSE-SEIP 2019) evaluated selection algorithms on TAP data (recalled; not fetched).
- Change-impact by fault localization + history: Fonte (ICSE 2023) ranks candidate bug-inducing commits by fault-localization suspiciousness of the code they modified, needing only test coverage. It ranks the actual BIC in the top 5 for 87% of studied real batch-testing failures and cuts BIC inspection cost by 32% on average; scores can drive weighted bisection (verified) — [Fonte arXiv 2212.06376](https://arxiv.org/pdf/2212.06376)
- Follow-up (2025) combines fault localization with code-change history to identify bug-inducing commits — [arXiv 2502.12922](https://arxiv.org/pdf/2502.12922)

### Inferences
- The industrial pattern is: build graph gives the safe superset (transitive dependents), then an ML model trims it, with a later full/"post-submit" run as a safety net. Selection is probabilistic, and safety is restored by later stages plus culprit finding.
- Under agent-generated changes, historical-outcome models may drift: agents change code in different places and patterns than humans, so training data from human diffs may not transfer. No paper measured this.

### Gaps
- Did not retrieve specific TAP numbers (daily test volume, % skipped). Did not find 2024–2026 peer-reviewed follow-ups from Meta on predictive selection.
- Semantic-diff-based change-impact analysis (call graph + data-flow) for CI selection at scale: no 2022–2026 industrial paper found this session.

---

## 3. CI at scale: Uber SubmitQueue, Google culprit finding, batching math, Meta diff-time testing, Microsoft CloudBuild

### Takeaway
The large-scale CI literature treats "keep main green" as a queueing and probabilistic-inference problem: speculate on likely-to-pass changes (Uber), batch changes and bisect on failure (Chrome/Ericsson batching studies), and use Bayesian, flake-aware search to find culprits (Google). Batching can cut machine use by 72–91% at the same feedback time on real data.

### Cited Findings
- Uber SubmitQueue ("Keeping master green at scale", Ananthanarayanan et al., EuroSys 2019): guarantees an always-green main by ensuring all build steps pass for every commit point. It speculatively runs CI in parallel on predicted outcomes of pending changes, and uses conflict analysis between changes to prune the speculation tree so independent changes build concurrently. In production >1 year at publication, thousands of daily commits to monorepos (verified via summaries) — [Morning Paper summary](https://blog.acolyer.org/2019/04); [Uber blog: bypassing large diffs in SubmitQueue](https://www.uber.com/en-US/blog/bypassing-large-diffs-in-submitqueue/)
- Uber later reported CI cost reductions from SubmitQueue-related work — [Uber blog: Slashing CI costs at Uber](https://www.uber.com/en-UG/blog/slashing-ci-costs-at-uber); [DevOps.com summary](https://devops.com/efficient-ci-at-scale-lessons-from-uber/)
- Google Flake Aware Culprit Finding (Henderson, Dorward, Nickell, Johnston, Kondareddy; ICST 2023): Bayesian inference + noisy binary search using priors on which changes likely contain the bug. Evaluated on 13,000+ test breakages at Google vs. traditional deflaked bisection; more accurate than bisection (verified) — [Google Research](https://research.google/pubs/flake-aware-culprit-finding/); [ICST 2023 entry](https://conf.researchr.org/details/icst-2023/icst-2023-industry/46/Flake-Aware-Culprit-Finding); [PDF](https://hackthology.com/pdfs/icst-2023.pdf)
- Batching math (Fallahzadeh, Bavand, Rigby; "Accelerating Continuous Integration with Parallel Batch Testing", 2023, arXiv 2308.13129, ICSE 2024 per DOI): on 276M test outcomes from Chrome and Ericsson. ConstantBatching (size 4) used up to 72% fewer machines at the same average feedback time with up to 75% execution reduction. DynamicBatching (size adapts to queue) used up to 91% fewer machines, up to 99% execution reduction. TestCaseBatching (new builds join batches before tests run) used up to 81% fewer machines, up to 67% execution reduction. Relations between parallelism, machines and feedback time are non-linear. Culprit-finding baselines include Dorfman and bisection, with BatchStop4 reported as the top performer (verified) — [arXiv 2308.13129](https://arxiv.org/abs/2308.13129)
- Selective bisection debugging (Saha & Gligoric, FASE 2017) combines RTS with bisection to cut culprit-finding cost (verified existence) — [abstract](https://users.ece.utexas.edu/~gligoric/papers/abstracts/SahaGligoric17SelectiveBisectionDebugging.txt)
- (recalled) Microsoft CloudBuild (Esfahani et al., ICSE-SEIP 2016): distributed, cached build service used across large Microsoft product groups, with reported multi-x speedups. Not fetched this session.

### Inferences
- Batching math gets much better when failure rates are low. If agent PRs fail CI more often (section 5), batch size must shrink or batching benefits collapse, since each failed batch triggers bisection. Dynamic batching that adapts to observed failure rate is the relevant design.
- Speculation trees (SubmitQueue) need accurate pass-probability estimates. Agent-authored changes are a new population for those models.

### Gaps
- Could not verify a 2024 Google culprit-finding follow-up paper; only ICST 2023 confirmed. No verified numbers for Meta diff-time testing (Sapienz/diff-time infra) or CloudBuild in this session.

---

## 4. Flaky tests: iDFlakies, FlakeFlagger, Google/Microsoft studies, cost

### Takeaway
Flakiness is the main source of noise that breaks every CI optimization above (selection, batching, culprit finding). Google rejected "rerun recent failures" because of it; Google's culprit finder had to be redesigned to be flake-aware. Agent-generated tests are a new likely source of flakiness, but no study measured that yet.

### Cited Findings
- Google TAP could not rely on "rerun tests that failed recently" because it would mostly rerun flaky tests; it is "impossible to weed out all flaky tests" (verified) — [Memon et al. 2017 PDF](https://web.eecs.umich.edu/~xwangsd/courses/w23/readings/googletest.pdf)
- Google's culprit finding needed explicit flake modelling (noisy binary search) because flaky tests make reruns costly and mislead bisection (verified) — [Flake Aware Culprit Finding](https://research.google/pubs/flake-aware-culprit-finding/)
- (recalled) Google testing blog (Micco, 2016): ~1.5% of test runs reported a flaky result and ~16% of tests showed some flakiness — [Google Testing Blog, John Micco posts](https://testing.googleblog.com/search/label/John%20Micco)
- Microsoft "Root Causing Flaky Tests in a Large-Scale Industrial Setting" (Lam et al., ISSTA 2019, RootFinder): logs and analyzes flaky test executions in Microsoft's CloudBuild-scale setting to localize root causes — [Microsoft Research](https://www.microsoft.com/en-us/research/publication/root-causing-flaky-tests-in-a-large-scale-industrial-setting/); [PDF](https://cs.gmu.edu/~winglam/publications/2019/LamETAL19RootFinder.pdf)
- (recalled) iDFlakies (Lam et al., ICST 2019): framework + dataset; reran test suites in different orders, found 422 flaky tests in 82 of 683 Java projects, about half order-dependent. FlakeFlagger (Alshammari et al., ICSE 2021): predicted flakiness from test features after rerunning tests thousands of times. Luo et al. (FSE 2014) classic root-cause taxonomy (async wait, concurrency, test order). Not fetched this session.
- Industry: Atlassian describes a scalable flaky-test detection and management tool — [Atlassian engineering blog](https://www.atlassian.com/blog/atlassian-engineering/taming-test-flakiness-how-we-built-a-scalable-tool-to-detect-and-manage-flaky-tests)

### Inferences
- Any CI that runs fewer tests per change (selection) or groups changes (batching) amplifies the cost of each flaky failure. Flake detection/quarantine is a prerequisite, not an add-on.
- Agents that "fix" failing CI may silence or delete flaky tests rather than fix them. Worth tracking as a metric.

### Gaps
- Did not re-verify iDFlakies/FlakeFlagger figures or dollar-cost estimates of flakiness. No study found of flakiness rates in agent-written tests.

---

## 5. Build systems research: Build Systems à la Carte, early cutoff, incremental computation, distributed builds

### Takeaway
Theory gives a clear vocabulary: a build system is a scheduler (topological, restarting, suspending) plus a rebuilder (dirty bit, verifying traces, constructive traces). Early cutoff and constructive traces (shared caches) are what make CI incremental and cacheable; these map directly onto Bazel/Buck-style remote caching. Not re-verified this session (well-known foundational work).

### Cited Findings
- (recalled) "Build Systems à la Carte" (Mokhov, Mitchell, Peyton Jones; ICFP 2018; extended JFP 2020): models Make, Shake, Bazel, CloudBuild, Excel etc. as combinations of a scheduler and a rebuilder; defines minimality and early cutoff (stop rebuilding when an output is unchanged); shows cloud builds need constructive traces — [Microsoft Research publication page](https://www.microsoft.com/en-us/research/publication/build-systems-la-carte/)
- (recalled) Incremental computation lineage: self-adjusting computation (Acar et al., 2000s), Adapton (Hammer et al., PLDI 2014, demand-driven incremental computation), and salsa (query-based incremental framework used by rust-analyzer) apply the same dependency-tracking + early-cutoff ideas inside programs. No sources fetched this session.
- CloudBuild is listed in Build Systems à la Carte as an industrial cloud build system; RootFinder (Microsoft, 2019) studied flakiness at that scale — [RootFinder](https://www.microsoft.com/en-us/research/publication/root-causing-flaky-tests-in-a-large-scale-industrial-setting/)

### Inferences
- Test results can be treated as build outputs with constructive traces: if the hash of a test's full input closure is unchanged, the cached result is valid. This is RTS done by the build system, and it is safe only if all inputs are declared (hermeticity).
- Early cutoff is especially valuable for agent changes that churn files without changing compiled outputs (formatting, comments, docs).

### Gaps
- No verified 2022–2026 build-systems research papers fetched; foundational claims above are from memory and should be checked.

---

## 6. Empirical studies 2025–2026 of AI-agent pull requests (AIDev, CI failures, tests in agent PRs, SWE-bench test adequacy)

### Takeaway
A burst of MSR 2026 papers on the AIDev dataset shows: agent PRs merge at a fairly high rate in popular repos (~71%), but CI failure is a strong rejection signal (each extra failing check-run lowers merge odds ~15%); test inclusion in agent PRs rose from 31% to 52% during 2025; CI workflow success varies sharply by agent (65% to 94%). SWE-bench work shows test suites accept many wrong patches (7.8% to ~30% depending on measure), so "tests pass" is a weak oracle for agent changes.

### Cited Findings
- AIDev dataset: ~932,791 PRs by autonomous coding agents across ~61k repos; curated "AIDev-pop" subset of 33,596 PRs in repos with >100 stars: OpenAI Codex 21,799, Copilot 4,970, Devin 4,827, Cursor 1,541, Claude Code 459 (verified) — [AIDev on Hugging Face](https://huggingface.co/datasets/hao-li/AIDev); [Haque et al. MSR 2026 PDF](https://ranger.uta.edu/~csallner/papers/Haque26Empirical.pdf)
- "Where Do AI Coding Agents Fail?" (MSR 2026 Mining Challenge; arXiv 2601.15195): 33k agent PRs from five agents. 71.48% merged overall. Every additional failed CI check-run decreases merge odds by ~15%. Non-merged PRs are larger, touch more files, and often fail CI; docs/CI/build tasks merge best, performance and bug-fix tasks worst. Qualitative analysis of 600 PRs: rejection reasons include no reviewer engagement, duplicate PRs, unwanted features, agent misalignment (verified) — [arXiv 2601.15195](https://arxiv.org/abs/2601.15195); [MSR 2026 entry](https://2026.msrconf.org/details/msr-2026-mining-challenge/19/Where-Do-AI-Coding-Agents-Fail-An-Empirical-Study-of-Failed-Agentic-Pull-Requests-in)
- Per-agent merge rates by task type (search summary of the same line of work): Claude Code builds 0.88, docs 0.75, CI 0.57, test 0.50, refactor 0.50; Copilot lowest, test 0.37 and feature 0.38. For OpenAI Codex, failures dominated by test case failures (54.9%) — [arXiv 2601.15195 HTML](https://arxiv.org/html/2601.15195); [arXiv 2602.00164 (fix-related unmerged agent PRs)](https://arxiv.org/html/2602.00164v1). Note: these per-agent figures came from a search summary; exact source paper for the 54.9% should be double-checked.
- "An Empirical Study of Tests in Agentic Pull Requests" (Haque, Ingale, Csallner; MSR 2026): test inclusion rate (PR touches ≥1 test file) rose from 31% to 52% across agents over Jan–Jul 2025; Devin flat at ~1/3. Test PRs are larger and take longer to close (more human intervention), but merge rates are largely similar to non-test PRs. Codex test PRs rarely get follow-up test edits (4%); Devin often does (59%, 32% edited more than once); Claude, Cursor, Copilot in between (33–49% modified, 15–24% multiple times). Test inclusion correlates with task type (p<0.05, moderate effect) (verified from full text) — [PDF](https://ranger.uta.edu/~csallner/papers/Haque26Empirical.pdf)
- "When AI Agents Touch CI/CD Configurations" (arXiv 2601.17413, 2026): CI/CD config files are 3.25% of agent changes (Devin 4.83%, Codex 2.01%); 96.77% of those target GitHub Actions (verified via search summary) — [arXiv 2601.17413](https://arxiv.org/html/2601.17413v1)
- "Reliability of AI Bots Footprints in GitHub Actions CI/CD Workflows" (arXiv 2604.18334, 2026): per-agent GitHub Actions workflow success rates span 29 points, from 64.86% (Claude) to 94.44% (Codex); Copilot has 7.53x higher odds of workflow success than Claude and 4.05x higher than Devin (verified via search summary) — [arXiv 2604.18334](https://arxiv.org/pdf/2604.18334)
- Other AIDev-based studies: security in agent PRs (arXiv 2601.00477), how agents modify code (arXiv 2601.17581: agent PRs smaller and more localized than human PRs, with more variability for Claude Code and Codex), AI-to-AI code review (arXiv 2608.21311), rejection of agent fixes (arXiv 2606.13468) — [2601.00477](https://arxiv.org/pdf/2601.00477); [2601.17581](https://arxiv.org/html/2601.17581); [2608.21311](https://arxiv.org/html/2608.21311v1); [2606.13468](https://arxiv.org/html/2606.13468)
- SWE-bench test adequacy, "Are 'Solved Issues' in SWE-bench Really Solved Correctly?" (Wang et al., ICSE 2026; arXiv 2503.15223): PatchDiff differential patch testing. 7.8% of patches counted correct while failing the full developer test suite; 29.6% of plausible patches behave differently from the ground-truth patch (verified) — [arXiv 2503.15223](https://arxiv.org/html/2503.15223v2); [ICSE 2026 entry](https://conf.researchr.org/details/icse-2026/icse-2026-research-track/59/Are-Solved-Issues-in-SWE-bench-Really-Solved-Correctly-An-Empirical-Study)
- UTBoost (ACL 2025; arXiv 2506.09289): LLM-augmented tests found 170 erroneous patches in SWE-bench Lite and 92 in SWE-bench Verified that passed the original tests (verified) — [arXiv 2506.09289](https://arxiv.org/pdf/2506.09289)
- SWE-ABS (arXiv 2603.00520, 2026): synthesizes plausible-but-wrong mutant patches, then generates adversarial tests that kill them. Strengthens 50.2% of instances (25.1x prior work) and rejects 19.78% of previously passing patches (verified) — [arXiv 2603.00520](https://arxiv.org/html/2603.00520v1)
- (recalled) SWE-bench+ (Aleithan et al., arXiv 2410.06992, 2024): reported solution leakage in ~32.67% and weak tests in ~31.08% of "resolved" instances. Not fetched this session.

### Inferences
- For agent changes, CI's "pass" signal is necessary but weakly sufficient: 20–30% of test-passing agent patches can be behaviorally wrong on benchmark tasks. CI for agents needs stronger oracles (differential testing vs. a reference, mutation-based adequacy, change-targeted test generation).
- CI failure rate differs by agent (65–94% workflow success), so per-author (per-agent) priors for speculation, batching and selection are justified.
- Agents increasingly include tests (52% by mid-2025), but some agents rarely revise them; test presence is not test adequacy.

### Gaps
- No study found that measures CI compute cost per agent PR, CI retry loops by agents, or flake rates of agent-written tests.
- Most studies are AIDev snapshots from early-to-mid 2025; agent behavior has likely changed since. Claude Code sample in AIDev-pop is small (459 PRs).

---

## 7. LLM-based test generation and oracles (TestGen-LLM, ACH, JiT catching), and test adequacy for agent changes

### Takeaway
Meta's line of work is the clearest industrial evidence: LLM-generated tests that are filtered by build/pass/coverage gates get accepted (73% in two deployments), mutation-guided generation targets specific risks, and 2026's "Just-in-Time catching" generates tests per diff to catch bugs before landing, with LLM assessors cutting human review load by 70%. True-positive yield is still low (8 of 41 reported catches).

### Cited Findings
- (recalled) TestGen-LLM (Alshahwan et al., Meta, FSE 2024 industry; arXiv 2402.09171): on Instagram/Facebook, 75% of generated tests built, 57% passed reliably, 25% increased coverage; improved 11.5% of classes it was applied to; 73% of recommendations accepted by engineers — [arXiv 2402.09171](https://arxiv.org/abs/2402.09171)
- ACH, "Mutation-Guided LLM-based Test Generation at Meta" (FSE 2025 industry; arXiv 2501.12862): generates few, targeted mutants (faults relevant to a concern such as privacy) and tests that kill them. Applied to 10,795 Android Kotlin classes in 7 platforms: 9,095 mutants, 571 privacy-hardening tests. LLM equivalent-mutant detector precision 0.79 / recall 0.47, rising to 0.95 / 0.96 with simple preprocessing. Engineers accepted 73% of tests in Messenger and WhatsApp test-a-thons; 36% judged privacy-relevant (verified) — [arXiv 2501.12862](https://www.arxiv.org/abs/2501.12862); [FSE 2025 entry](https://conf.researchr.org/details/fse-2025/fse-2025-industry-papers/16/Mutation-Guided-LLM-based-Test-Generation-at-Meta); [Meta engineering blog, Sep 2025](https://engineering.fb.com/2025/09/30/security/llms-are-the-key-to-mutation-testing-and-better-compliance/)
- "Harden and Catch for Just-in-Time Assured LLM-Based Software Testing" (Harman et al., arXiv 2504.16472, FSE 2025 keynote paper): defines hardening tests (protect against future regressions) vs. catching tests (catch faults in the change under review), and poses the JiTTest challenge: generate tests just in time to catch faults before they land (verified) — [arXiv 2504.16472](https://arxiv.org/pdf/2504.16472v1)
- "Just-in-Time Catching Test Generation at Meta" (Becker, ..., Harman et al.; arXiv 2601.22832, Jan 2026): for backend systems of hundreds of millions of LOC. Over 22,126 generated tests, code-change-aware generation produced 4x more candidate catches than hardening tests and 20x more than coincidentally failing tests. Rule-based + LLM assessors cut human review load by 70%. 41 candidate catches reported to engineers; 8 confirmed true positives, 4 of which would have caused serious failures. Accepted code changes had significantly more false positives; rejected changes had significantly more true positives (verified) — [arXiv 2601.22832](https://arxiv.org/abs/2601.22832)
- Adversarial/mutant-based strengthening of acceptance tests for agent patches (SWE-ABS) rejects ~20% of previously passing patches (verified) — [arXiv 2603.00520](https://arxiv.org/html/2603.00520v1)

### Inferences
- A strong pattern for CI under agent changes: (1) generate change-targeted "catching" tests per diff, (2) filter with build/flakiness/assessor gates, (3) surface only high-confidence failures. Meta's numbers suggest the filter is the hard part (8/41 true positives after a 70% review-load cut).
- Mutation-guided adequacy (ACH, SWE-ABS) is the most concrete answer in the literature to "are the agent's tests adequate?"

### Gaps
- No verified data on cost (LLM tokens, compute) per generated test or per diff in Meta's systems. Few open-source replications of JiT catching.

---

## 8. Speculative/optimistic merging, semantic merge conflict detection, merge conflict prediction

### Takeaway
Merge research splits into (a) speculative merging/awareness tools that merge in the background to detect conflicts early, (b) semantic conflict detection via generated tests that compare behavior across base/left/right/merge, and (c) prediction of conflicts from change metadata. LLMs are now used to generate the behavior-comparing tests; ensembles beat single models but not yet clearly beat traditional generators.

### Cited Findings
- Semantic conflict detection via automated behavior change detection (Chalmers et al.; SAM-style test generation across merge scenario versions) — [Chalmers publication](https://research.chalmers.se/en/publication/528234)
- LLM-based semantic conflict detection (2025): integrating a Code Llama 70B test generator into SMAT; follow-up work found LLMs (Llama, Qwen best) can detect semantic conflicts; no single model beat traditional tools, but combining multiple models did better, finding 3 extra conflicts missed by SAM (200% more unique conflicts than the single-model approach) (verified via search summary) — [JSERD: Assessing the Effectiveness of LLMs in Detecting Semantic Conflicts](https://journals-sol.sbc.org.br/index.php/jserd/article/view/7565); [arXiv 2507.06762](https://arxiv.org/abs/2507.06762v1)
- SubmitQueue's conflict analysis between pending changes is a production form of optimistic merging: independent changes are built concurrently; dependent ones are speculated in a tree (verified) — [Morning Paper summary](https://blog.acolyer.org/2019/04)
- (recalled) Speculative merging/awareness: Crystal (Brun et al., FSE 2011) and Palantír continuously merge collaborators' work in the background to warn of textual/build/test conflicts early; merge-conflict prediction from change features (e.g., Owhadi-Kareshk et al., ESEM 2019). Not fetched this session.

### Inferences
- With many agents working in parallel on one repo, the rate of concurrent changes rises and semantic (not textual) conflicts become the main risk. Speculative merge + behavior-diff testing (SAM/SMAT-style) is the research-backed approach; SubmitQueue-style conflict analysis can bound the compute.

### Gaps
- Found no 2024–2026 study measuring merge-conflict or semantic-conflict rates among concurrent agent PRs. Did not verify Crystal or conflict-prediction numbers.

---

## Cross-cutting open problems (from the above)
- Drift of learned selection/speculation models when the author population shifts from humans to agents (no study found).
- Weak oracles: 7.8%–29.6% of SWE-bench "passing" patches are wrong or behave differently ([PatchDiff](https://arxiv.org/html/2503.15223v2)); change-targeted test generation exists but has low true-positive yield ([Meta JiT](https://arxiv.org/abs/2601.22832)).
- Flakiness interacts badly with every CI optimization ([Google TAP](https://web.eecs.umich.edu/~xwangsd/courses/w23/readings/googletest.pdf), [flake-aware culprit finding](https://research.google/pubs/flake-aware-culprit-finding/)); agent-written test flakiness is unmeasured.
- Batching gains depend on low failure rates ([Fallahzadeh et al.](https://arxiv.org/abs/2308.13129)); agent PR failure rates vary widely by agent ([arXiv 2604.18334](https://arxiv.org/pdf/2604.18334)).
