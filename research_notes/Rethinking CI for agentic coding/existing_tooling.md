# Existing tooling for faster, cheaper, less conflict-prone CI (with attention to agent-driven change volume)

Research date: 2026-10-13. Labels used below: **[vendor]** = vendor docs, marketing, or vendor-run case study. **[company eng]** = an operating company describing its own internal system (self-reported, not independently audited). **[peer-reviewed]** = academic or industry paper at a venue. **[third-party]** = independent blog, aggregator, or pricing site (quality varies). No independent benchmark compares the vendors in any category below. Almost every speedup number is vendor- or self-reported.

## 1. Test selection / test impact analysis (TIA)

### Takeaway
There are three ways to compute impact. (a) Static build-graph diffing: Bazel bazel-diff and target-determinator, Nx affected, Turborepo, Pants. It is deterministic and conservative, and only as safe as the graph is complete. (b) Per-test coverage maps: Datadog TIA. It is deterministic, but needs a baseline and has blind spots for non-code inputs. (c) ML on historical failures: Meta, Launchable/CloudBees Smart Tests, Develocity PTS. This is probabilistic. It roughly halves test cost, and the only published recall numbers come from Meta's 2019 paper: >95% of individual test failures and >99.9% of faulty changes. Vendors report time savings, not recall.

### Cited Findings
- **Meta predictive test selection (ICSE-SEIP 2019) [peer-reviewed]:** A model is trained on historical test outcomes with "basic machine learning techniques" and selects a subset of tests per change. In production it cut total testing infrastructure cost by about 2x. It still reported >95% of individual test failures and >99.9% of faulty changes. It explicitly models flakiness. Motivation: a monorepo where running all potentially impacted tests on every change was infeasible. — [arXiv 1810.05286](https://ar5iv.arxiv.org/html/1810.05286); [ICSE 2019 listing](https://2019.icse-conferences.org/details/icse-2019-Software-Engineering-in-Practice/22/Predictive-Test-Selection)
- **Launchable → CloudBees Smart Tests [vendor]:** CloudBees acquired Launchable in 2024 and rebranded it Smart Tests. An ML model predicts which tests are likely to fail for a change. It runs that subset and orders it by failure probability. Claims: testing "30–50% faster"; customers report a "35–70% reduction in CI runtime." — [CloudBees: how Smart Tests works](https://www.cloudbees.com/blog/how-cloudbees-smart-tests-works); [CloudBees acquires Launchable](https://www.cloudbees.com/blog/cloudbees-acquires-launchable-to-enable-development-teams-to-iterate-faster); [DevOps.com](https://devops.com/cloudbees-delivers-on-ai-promise-to-improve-application-testing/)
- **Develocity (Gradle) Predictive Test Selection [vendor]:** An ML model uses code-change snapshots, test history, and flaky-test data. It combines per-project learning with training on "millions of test executions across many projects." Claims: "35–70% of test time for most builds" saved, "up to 70%," and some materials say up to 90%. A model update reported "49% fewer missed test failures" than the previous version, which implies a measurable miss rate, but no absolute recall is published. Supports Gradle and Maven test tasks. — [Gradle PTS product page](https://gradle.com/develocity/product/predictive-test-selection/); [Develocity 2023.4 blog](https://gradle.com/blog/develocity-2023.4-boosts-toolchain-reliability-and-test-performance-scalability/); [PTS user manual](https://docs.gradle.com/develocity/predictive-test-selection)
- **Datadog Test Impact Analysis (formerly Intelligent Test Runner) [vendor]:**
  - Collects per-test (or per-suite) code coverage.
  - Skips a test only when "Datadog has a record of the test passing in a commit where the covered and tracked files are identical to the current commit."
  - Searches past test runs across relevant commits, not just the last diff.
  - Runs everything when "tracked files" change (for example config), when no prior passing baseline exists, or when the prior run failed.
  - Supports source-level "unskippable" annotations.
  - Datadog positions this as deterministic versus ML approaches that "might miss tests that were relevant."
  — [Datadog TIA how it works](https://docs.datadoghq.com/tests/test_impact_analysis/how_it_works/); [TIA overview](https://docs.datadoghq.com/tests/test_impact_analysis/)
- **bazel-diff / target-determinator [open source]:** bazel-diff hashes every target from its rule, its attributes, and the hashes of its inputs (a Merkle tree) at two Git revisions. It diffs the hashes to emit impacted targets. It has been used on repos with tens of thousands of targets. target-determinator (bazel-contrib) compares *configured*-target information across revisions. Aspect also has a "cache diff" approach. A practitioner guide warns that selective CI is safe only if path→target mapping is complete across all configurations, and that it must "fall back conservatively" otherwise. — [VirtusLab Bazel book 6.5.2](https://bazel.virtuslab.com/book/6~5~2/); [VirtusLab 6.5.4](https://bazel.virtuslab.com/book/6~5~4/); [Aspect: selective testing with cache diff](https://aspect.build/blog/selective-testing-with-cache-diff.md)
- **Nx affected / Turborepo [vendor docs + third-party]:** `nx affected` maps changed files to projects. It then walks the project graph (including code-level imports) to the dependents. Task results are cached by hashing inputs: source, config, dependencies, runtime values, args. Turborepo hashes each task's inputs (code, deps, env) similarly. A third-party comparison says Nx detects dependencies at the import level while Turborepo works at the package.json level. — [Nx mental model](https://nx.dev/docs/concepts/mental-model); [pkgpulse Turborepo vs Nx 2026](https://www.pkgpulse.com/guides/turborepo-vs-nx-monorepo-2026) [third-party]
- **Google TAP [peer-reviewed / company eng]:** On an average day (2017 paper), TAP tested more than 13K projects, with 800K builds and 150M test runs, over a ~2B LOC monorepo. Running all impacted tests presubmit is infeasible, so comprehensive testing is batched *postsubmit*, and automated culprit finders bisect breakages ("What Breaks Google?", 2023). TAP Postsubmit is developing scheduling that ranks targets by predicted failure likelihood. Google has also published "Speculative Testing at Google with Transition Prediction" and "Flake Aware Culprit Finding" (ICST 2023). — [Google testing ICSE-SEIP'17 PDF](https://huang.isis.vanderbilt.edu/cs8395-f23/paper/google-testing-icse-seip-17.pdf); [What Breaks Google?](https://research.google/pubs/what-breaks-google/); [Speculative Testing with Transition Prediction](https://research.google/pubs/speculative-testing-at-google-with-transition-prediction/)
- **Chromium CQ path-filtered builders [company eng]:** `location_regexp` makes a trybot run only for changes under specific directories. This is a coarse, hand-maintained form of target determination. — [Chromium CQ docs](https://chromium.googlesource.com/chromium/src/+/main/docs/infra/cq.md)

### Inferences
- Graph-based selection gives no recall number because it is (in principle) exact. Its failure mode is an incomplete graph: undeclared inputs, env, config, or cross-language edges. ML selection gives a cost/recall dial. Coverage-based selection sits between the two, and is weak on non-code inputs and on tests whose coverage changes.
- Meta's 2019 numbers (2x cost cut, 99.9% of faulty changes caught) are still the only peer-reviewed safety figure. Vendor claims of 35–70% time savings are in the same range as Meta's 2x. The two tiers can stack: graph selection first, then ML ranking within the selected set.
- For agent-generated volume, selection reduces cost per change but not the number of changes. A deterministic graph method also gives agents a cheap, explainable "what do I need to run" answer.

### Gaps
- Pants and Buck2 target-determination mechanics were not fetched. Both use build-graph dependency inference; no specific numbers were found.
- No independent (non-vendor) evaluation of Launchable, Develocity PTS, or Datadog TIA recall or safety was found.
- No recall/miss-rate figure was found for any 2024–2026 commercial product.

## 2. Build caching and remote execution

### Takeaway
Content-addressed action caching plus remote execution (Bazel REAPI: BuildBuddy, EngFlow, NativeLink; Buck2; Gradle build cache; Nx Cloud / Turborepo remote cache; sccache) is the most mature lever. Reported results are 2–15x build speedups and hundreds of CI hours per day saved. Almost all of these are vendor case studies.

### Cited Findings
- **EngFlow case studies [vendor]:**
  - Envoy Mobile: presubmit went from 2h to 20 min (headline "up to 10x").
  - Sibros: 3h to 27 min (6x).
  - Brave Chromium builds: 2h to under 15 min (8x).
  - Shift Chromium: 2–8x, and up to 15x with a warm cache.
  — [EngFlow case studies](https://www.engflow.com/caseStudies); [Envoy Mobile](https://www.casestudies.com/company/engflow/case-study/envoy-mobile-builds-10x-faster-with-engflow); [Brave](https://www.casestudies.com/company/engflow/case-study/brave-speeds-chromium-builds-8x-with-engflow); [Shift](https://www.casestudies.com/company/engflow/case-study/shift-speeds-chromium-builds-15x-with-engflow)
- **Remote cache hit rate:** a VirtusLab maturity matrix treats >80% remote cache hit rate as "advanced" build infrastructure. This is a heuristic, not a measured industry average. — [VirtusLab Visdom: remote execution (EngFlow)](https://visdom-maturity-matrix.virtuslab.com/guides/infrastructure/remote-execution-engflow)
- **Buck2 [company eng]:** Meta's internal tests showed Buck2 completing builds 2x as fast as Buck1. It is designed around remote execution and virtual file systems (2023). — [Meta engineering: Buck2](https://engineering.fb.com/2023/04/06/open-source/buck2-open-source-large-scale-build-system/)
- **Gradle / Develocity build cache [vendor case studies]:**
  - LinkedIn saves more than 800 hours/day in CI and local builds across more than 4,500 services.
  - Spring saved ~27 days of CI wall-clock time in one week.
  - Spring Boot CI got 3–4x faster.
  - Revolut cut build times 75%.
  - The Kotlin compiler saves an average of 20 min/build from the remote cache.
  — [Gradle LinkedIn story](https://gradle.com/customers/story/linkedin/); [Spring Boot journey](https://gradle.com/blog/from-hour-long-builds-to-streamlined-productivity-the-spring-boot-journey/); [Revolut PDF](https://gradle.com/wp-content/uploads/2023/09/Revolut-TechValidate-Case-Study.pptx-2.pdf)
- **sccache [company eng, 2016]:** Mozilla's compiler cache (rewritten in Rust) has local disk and cloud storage backends. Mozilla described it as "extremely successful" in automation. The quantified gain cited was a ~40% (Linux) and ~20% (macOS) reduction in configure-script time. — [Ted Mielczarek, Mozilla blog](https://blog.mozilla.org/ted/2016/11/21/sccache-mozillas-distributed-compiler-cache-now-written-in-rust/)
- **Nx Cloud [vendor]:** Remote cache plus distributed task execution. Nx Cloud assigns individual tasks to agent machines dynamically, instead of the user splitting jobs by hand. — [Nx CI intro](https://nx.dev/ci/intro); [Nx Cloud getting started](https://nx.dev/ci/getting-started/intro)
- **Docker layer caching on runners:** see section 5 (Blacksmith sticky disks, Depot remote BuildKit).

### Inferences
- Caching helps agent workloads in particular: many agent PRs touch small areas of the same base commits, so most actions should hit the cache. Hit rate depends on hermeticity and on how far apart agent branch bases are.
- Remote execution moves the bottleneck from runner count to a shared action-execution pool. That pool can absorb bursts of many concurrent PRs better than per-PR VMs.

### Gaps
- No public BuildBuddy or NativeLink case study with hit rates was found in this pass.
- Nx Cloud / Turborepo remote cache hit-rate statistics were not found.
- No independent cross-vendor RBE benchmark was found.

## 3. Merge queues and batching

### Takeaway
Every merge queue tests "main + PRs ahead of me" before merging. They differ on five points: speculative parallel depth, batching, bisection on failure, multiple queues partitioned by affected targets, and flake tolerance. Uber's SubmitQueue (speculation tree + ML + conflict analysis) is the most sophisticated published system: −53% CI resources and −37% P95 wait in 2024–2025. GitHub's native queue is a single queue with limited batching and failure isolation. Trunk, Aviator, Mergify, and Graphite sell the missing pieces.

### Cited Findings
- **Uber SubmitQueue (blog June 23, 2025; deployed 2024) [company eng]:**
  - Scale: 4,500+ engineers, six monorepos, tens of thousands of changes per month.
  - The Enumerator builds a *speculation tree* of all possible builds for pending changes.
  - Conflict analysis based on target analysis prunes the tree so independent changes build concurrently.
  - "Bypassing Large Diffs" lets small changes land ahead of a slow, large blocking change when their build result is identical either way.
  - Build-time prediction uses NGBoost (normal distributions) to estimate the probability that a younger change finishes first.
  - A speculation threshold gates which builds run.
  - 21-week results: build-to-change ratio −45% (Go), −48% (iOS), −64% (Android); CPU hours −45/−35/−52%; P95 wait −45/−33/−32%. Headline: 53% less CI resource, 37% faster waits.
  - The prior state had 40–65% of builds "prematurely ended" (wasted speculation).
  - The blog does not describe batching or bisection.
  — [Uber: Slashing CI Costs at Uber](https://www.uber.com/us/en/blog/slashing-ci-costs-at-uber/)
- **GitHub merge queue [vendor docs via third-party]:**
  - "Build concurrency" (1–100) caps concurrent `merge_group` runs.
  - "Merge limits" set how many PRs are grouped per run.
  - On failure, the failing PR is removed and groups are rebuilt.
  - "Only merge non-failing pull requests" mitigates batching risk when concurrency > 1.
  - Trunk (a competitor, Sep 3, 2025) lists limitations: a single queue for all PRs regardless of relatedness, each PR tested twice (branch and merge group), weak failure visibility, and the concurrency cap of 100.
  — [Paradime GitHub merge queue guide](https://docs.paradime.io/guides/working-with-git/github-merge-queue); [Trunk: Outgrowing GitHub merge queue](https://trunk.io/blog/outgrowing-github-merge-queue) [vendor/competitor]
- **GitLab merge trains [vendor docs]:**
  - Each MR's pipeline runs on target + all MRs ahead of it, in parallel.
  - On failure, that MR is removed and every later pipeline is cancelled and restarted without it.
  - Maximum 20 parallel pipelines per train.
  - There is no batching or affected-target partitioning in the docs.
  — [GitLab merge trains docs (16.11 archive)](https://archives.docs.gitlab.com/16.11/ee/ci/pipelines/merge_trains.html)
- **Trunk Merge Queue [vendor]:**
  - Parallel queues ("lanes") inferred dynamically from impacted targets, with no configuration.
  - Batching (example: three 10-min tests become one, "70%" savings).
  - Automatic bisection of failed batches.
  - Optimistic merging: if a later speculative check that includes an earlier PR passes, merge both.
  - "Pending failure depth" holds a failed PR in the queue while successors test, as anti-flake protection.
  - Four priority levels.
  — [Trunk anti-flake protection](https://docs.trunk.io/merge-queue/concepts-and-optimizations/anti-flake-protection); [Trunk parallel queues](https://docs.trunk.io/merge-queue/concepts-and-optimizations/parallel-queues); [Trunk blog](https://trunk.io/blog/outgrowing-github-merge-queue)
- **Aviator MergeQueue [vendor]:**
  - Parallel mode runs speculative CI.
  - Batching via `batch_size` and `batch_max_wait_minutes`.
  - "Affected targets" create dynamic queues, described as "thousands of parallel queues" in monorepos, each validating an independent set of checks.
  - Marketing claims Notion and Figma ship "1,000+ PRs a day" with it. This is unverified.
  — [Aviator batching docs](https://docs.aviator.co/mergequeue/concepts/batching); [Aviator affected targets](https://docs.aviator.co/mergequeue/concepts/affected-targets); [Aviator parallel mode](https://docs.aviator.co/mergequeue/concepts/parallel-mode); [tooldirectory.ai Aviator listing](https://tooldirectory.ai/tools/aviator) [third-party]
- **Graphite merge queue [vendor]:** Stack-aware. Optimizations: fast-forward merge (run CI on all PRs in a stack in parallel), parallel CI across stacks, and batching of stacks. Claims "1.5x faster merges" on average and up to 2.5x. — [Graphite merge queue optimizations](https://www.graphite.com/docs/merge-queue-optimizations); [Graphite: first stack-aware merge queue](https://graphite.com/blog/the-first-stack-aware-merge-queue)
- **Chromium CQ [company eng]:**
  - Dry run (CQ+1) reports only; full run (CQ+2) submits if there are no new regressions.
  - Passing dry-run tryjobs are reused at submit time, within a commit-distance window (e.g., 800 commits) or 24h by default.
  - Experimental builders run on a percentage of CQ attempts and do not block.
  - Retry ladder: retry failed shards with the patch, then recompile and retest *without* the patch. The CL fails only if tests fail with the patch and pass without it.
  - Targets: median trybot cycle under 40 min, p90 about 1h.
  - About 20,000 unique flaky tests; without retries "pretty much no CL would ever pass the CQ."
  — [Chromium CQ docs](https://chromium.googlesource.com/chromium/src/+/main/docs/infra/cq.md)
- **Google presubmit/postsubmit split [peer-reviewed]:** Presubmit gives fast, partial validation. Comprehensive testing is batched postsubmit, with automated culprit finding (bisection), now flake-aware. — [What Breaks Google?](https://research.google/pubs/what-breaks-google/)
- **Mergify "State of Merge Queues 2026" (published July 27, 2026) [vendor data, 153K merges / 160 orgs analyzed, from 200K+ / 477 orgs]:**
  - Broken-main rate: 5.1% private, 1.1% open source. It rises with team size: 0.77% (2–5 engineers) up to 12.5% (40+ engineers).
  - Queue wait, private: median 8 min, p90 63 min, p99 19h53m.
  - Batching is rare: used on 6% of private merges, average batch 4, max 16. Failed private batches average ~5.8 PRs.
  - Throughput, private: median 3.1 merges per active day, p99 32.
  — [Mergify State of Merge Queues 2026](https://mergify.com/reports/state-of-merge-queues-2026)
- **bors/homu (Rust) "rollups":** No source was fetched in this pass. See Gaps.

### Inferences
- The techniques that scale with change rate are (1) partitioning by affected targets (queues per independent subgraph), (2) speculation pruned by conflict analysis and probability, (3) batching with bisection, and (4) flake tolerance through optimistic merge or retry-without-patch. Uber shows that pruning and ML prioritization can roughly halve compute.
- Batching is rarely used in practice (6% of merges per Mergify). The likely reason is that batch failures plus bisection are costly when flake rates are high. Agent volume raises the payoff from batching but also the flake exposure.
- The Mergify data shows broken-main rates rising sharply with team size (concurrency). Many concurrent agents act like a very large team, which suggests the 40+ engineer failure regime is the relevant one.

### Gaps
- bors/homu rollup mechanics and the Rust project's newer bors rewrite were not researched in this pass.
- No public description was found of Mergify's speculative-check internals beyond the report data.
- The GitHub merge queue's maximum group size and its exact bisection behaviour were not confirmed from GitHub's own docs (third-party sources only).

## 4. Flaky test management

### Takeaway
Flakes are the main tax on queues and batching. Large orgs report that 13–21% of failures, or of master-build breaks, are flaky. Tools combine detection (in-build retries, statistical or Bayesian scoring over history), quarantine (ignore results, ticket the owner), and queue-level tolerance.

### Cited Findings
- **Atlassian Flakinator (Dec 8, 2025) [company eng]:**
  - Two detection methods: in-build retries that stop at the first pass/fail flip (81% detection for some products), and Bayesian scoring (0–1) over a moving window using duration variance, environment, result patterns, and retry frequency.
  - Quarantine flow: CODEOWNERS identifies the owner, a Jira ticket is created with a deadline, Slack notifies the team, and the test is reintroduced after a health period.
  - Scale: 350M+ test executions/day, 22,000+ builds recovered and 7,000 unique flaky tests in one quarter.
  - Impact: flakes caused 21% of Jira Frontend master-build failures and ~15% of Jira Backend failures, and wasted 150K+ developer hours/year.
  - Cites Microsoft (13% of failures flaky) and Google (16% of failures flaky).
  — [Atlassian: Taming test flakiness](https://www.atlassian.com/blog/atlassian-engineering/taming-test-flakiness-how-we-built-a-scalable-tool-to-detect-and-manage-flaky-tests)
- **Google:** often cited as "16% of 4.2M tests show some flakiness; 84% of pass→fail transitions are flaky." This came via a third-party statistics roundup; the original Google Testing Blog source was not fetched. — [Quashbugs flaky test statistics 2026](https://quashbugs.com/blog/flaky-test-statistics) [third-party]
- **Bitrise:** share of teams experiencing flakiness rose from 10% (2022) to 26% (2025). Via the same third-party roundup. — [Quashbugs](https://quashbugs.com/blog/flaky-test-statistics) [third-party]
- **Chromium:** about 20,000 unique flaky tests. The CQ handles them with retry-with-patch, then retry-without-patch. — [Chromium CQ docs](https://chromium.googlesource.com/chromium/src/+/main/docs/infra/cq.md)
- **Trunk Flaky Tests [vendor]:** Classifies tests as Healthy, Flaky, or Broken from CI results. Quarantine makes CI ignore a test's pass/fail. Only Flaky tests, not Broken ones, can be quarantined. Dashboards rank by PRs impacted. — [Trunk: managing detected flaky tests](https://docs.trunk.io/flaky-tests/management/managing-detected-flaky-tests); [Trunk Flaky Tests out of beta](https://trunk.io/blog/trunk-flaky-tests-is-out-of-beta)
- **Queue-level flake tolerance:** Trunk's optimistic merging and pending-failure depth (section 3). Google's flake-aware culprit finding (ICST 2023). — [Trunk anti-flake](https://docs.trunk.io/merge-queue/concepts-and-optimizations/anti-flake-protection); [What Breaks Google?](https://research.google/pubs/what-breaks-google/)
- **Nx 2026 roadmap [vendor]:** "LLM-based flaky task detection" is planned. — [Nx 2026 roadmap](https://nx.dev/blog/nx-2026-roadmap)

### Inferences
- Flake rate multiplies with batch size and speculative depth: a batch of N fails spuriously with probability ~1−(1−p)^N. Reliable flake quarantine is therefore a precondition for batching agent-generated changes.
- Agents that automatically "fix" CI failures risk chasing flakes. Flake classification has to come before any agent remediation loop.

### Gaps
- BuildPulse and Datadog flaky-test management mechanics were not fetched.
- The original Google primary sources for the 16%/84% figures were not fetched.

## 5. Compute: faster runners, ephemeral VMs, snapshotting, Docker layer caching, cost trends

### Takeaway
Third-party GitHub Actions runners compete on faster CPUs (bare metal, gaming-class cores), co-located NVMe caches ("sticky disks"), and price. They list about $0.0036–0.004/min for 2 vCPU against GitHub's $0.006. GitHub cut hosted-runner prices up to 39% on Jan 1, 2026. It announced, then postponed, a $0.002/min fee on self-hosted runners.

### Cited Findings
- **GitHub pricing:** hosted-runner prices reduced by up to 39% on Jan 1, 2026. A planned $0.002/min platform fee for self-hosted runners on private repos, from March 2026, was announced, then *postponed* on Dec 15, 2025 "to re-evaluate." Public-repo workflows remain free. — [GitHub: 2026 pricing changes for Actions](https://resources.github.com/actions/2026-pricing-changes-for-github-actions/); [IT Brief](https://itbrief.news/story/github-cuts-actions-runner-prices-adds-new-usage-fee); [WarpBuild analysis](https://warpbuild.com/blog/github-actions-price-change) [vendor/competitor]
- **Runner list prices, 2 vCPU Linux x86 [third-party aggregator, 2026]:**

  | Provider | List price | Notes |
  |---|---|---|
  | Depot | $0.004/min | plans include 2,000–20,000 minutes |
  | Namespace | $0.0036/min | |
  | Blacksmith | $0.004/min | ARM $0.0025; 3,000 free minutes/month |
  | GitHub hosted | $0.006/min | |

  The same source reports managed providers raising per-minute costs and cutting free tiers after GitHub's March 2026 changes. — [cicdpipelinecost.com Depot vs Namespace vs Blacksmith](https://cicdpipelinecost.com/depot-vs-namespace-vs-blacksmith); [Blacksmith pricing](https://cicdpipelinecost.com/blacksmith-pricing); [Tenki runner showdown 2026](https://tenki.cloud/blog/github-actions-runner-showdown-2026) [vendor-adjacent]
- **Blacksmith [vendor]:** Docker layer caches on NVMe "sticky disks" co-located with runners and shared across a repo's org, which avoids network download of the cache. Claims "up to 40x faster Docker builds," "2x faster runtime," and "up to 67%" lower cost on bare metal. It contrasts this with Depot's remote BuildKit, which centralizes the cache but adds network hops. — [Blacksmith: Docker layer caching](https://info.blacksmith.sh/task/blog/github-actions-docker-layer-caching-automatic); [Blacksmith shared Docker layer cache](https://info.blacksmith.sh/task/blog/github-actions-shared-docker-layer-cache)
- **Depot [vendor]:** GitHub Actions runners plus remote BuildKit builders with a persistent shared layer cache. — [Depot GitHub Actions docs](https://depot.dev/docs/github-actions/overview)

### Inferences
- Runner price per minute is now a commodity (about $0.004). Differentiation is moving to warm state: persistent disks, caches, and pre-warmed dependencies. That matters more for agents, which run many short jobs where cold start dominates.
- Under per-minute billing, agent volume scales cost linearly with runs. Selection, caching, and queue pruning are the levers that cut minutes. Runner choice cuts price per minute by ~1.5x at most at list price.

### Gaps
- WarpBuild, Ubicloud, Buildkite hosted agents, and Namespace snapshot/"cache volumes" mechanics were not fetched.
- No independent benchmark of runner speed was found; all speed claims are vendor claims.
- No source was found for VM/microVM snapshot-restore of full runner state (e.g., Firecracker-based) as a product feature with numbers.

## 6. Stacked diffs and CI load

### Takeaway
Stacking (Graphite, Sapling, ghstack, jj) produces smaller PRs but *more* CI runs: more PRs, plus re-runs on every restack or rebase. Tools mitigate this by skipping CI on mid-stack PRs and testing or merging the stack as a unit.

### Cited Findings
- **Graphite [vendor]:** extra CI runs come "due to the additional PRs created, and due to behind-the-scenes rebasing to keep stacked branches up to date."
  - Orgs with fewer than 10 people stacking are "unlikely to see any difference."
  - The CI optimizer API returns skip/no-skip per PR. Users configure how many bottom-of-stack PRs run CI and whether the top runs.
  - It never skips if the API fails or the PR is in the merge queue.
  - Merging a stack together can cut runs "by a factor of stack height."
  — [Graphite: stacking and CI](https://graphite.com/docs/stacking-and-ci); [Graphite CI optimizer](https://graphite.dev/blog/ci-optimizer)
- **Mergify Stacks** is a competing stacked-PR feature. — [Mergify Stacks vs Graphite](https://docs.mergify.com/stacks/compare/graphite/)

### Inferences
- Agents naturally produce chains of dependent changes. Without stack-aware CI skipping, restacks multiply CI cost by roughly stack height times the number of rebases.

### Gaps
- Sapling, ghstack, and jj CI-integration behaviour was not researched. These are client-side tools; CI load depends on the server or queue integration.
- Reports that Graphite was acquired by Cursor (late 2025) were not verified in this pass.

## 7. Built or launched for agent-generated change volume (2025–2026)

### Takeaway
Measured data shows PR volume rising fast. Mergify reports AI-assisted PRs at ~14% of private merges and *lower* broken-main rates for them. An arXiv study finds concurrent agent PRs conflict at 20–42%. Products launched in response are mostly (a) AI "self-healing CI" that fixes failures, and (b) merge queues repositioned for throughput. No widely adopted CI primitive designed specifically for agent concurrency was found.

### Cited Findings
- **Volume:** One source says GitHub monthly merged PRs grew from 25M (Jan 2023) to 90M+ (Jun 2026), and that agents open about 17M PRs/month. This comes from a blog aggregator; the primary GitHub data source was not verified. — [bex.co: 17M robot PRs a month (Sep 8, 2026)](https://bex.co/blog/2026/09/08/ai-coding-agents-open-source-maintainership) [third-party]
- **Mergify State of Merge Queues 2026 (July 27, 2026) [vendor data]:**
  - AI-assisted share: ~14.4% of private and ~7.6% of OSS merges. This is a floor, because detection relies on commit signatures, mainly Claude Code.
  - Broken-main rate: 1.9% for AI-assisted vs 4.4% for non-AI. This is observational, held within the same repos and across PR-size bands. AI PRs averaged 137 changed lines vs 84.
  — [Mergify report](https://mergify.com/reports/state-of-merge-queues-2026)
- **Concurrency and conflicts (arXiv 2607.04697, July 7, 2026) [preprint]:**
  - Dataset: AIDev-pop, 33,596 agent PRs in 2,807 repos (Codex, Copilot, Devin, Cursor, Claude Code).
  - 79.4% of agent PRs were concurrent with other PRs.
  - Textual conflict rate: 19.8% for same-agent concurrent pairs, 41.7% for cross-agent pairs. 84.4% of conflicted files were source code; ~42% of conflicts were structural.
  - The CI-waste implication is the authors' hypothesis, not a measurement.
  — [Xu et al., arXiv 2607.04697](https://arxiv.org/html/2607.04697v2)
- **Microsoft:** an AI agent study reportedly found +24% PR volume, but AI PRs took ~20% longer to merge after first human review. This was reported via search-result summaries; the primary study was not fetched. — [CodeRabbit blog](https://www.coderabbit.ai/blog/the-pull-request-lives-on-ai-gave-it-a-bigger-job) [third-party, unverified]
- **Nx Self-Healing CI (June 23, 2025) [vendor]:**
  - On task failure, an AI agent reads logs, uses the Nx project graph to find the root cause, proposes a fix, and *re-runs the failed tasks to validate it*.
  - After human approval, it commits to the PR.
  - 2026 roadmap: LLM-based flaky task detection, composing multiple fixes, tweaking near-miss fixes.
  — [Nx: Self-healing CI](https://21.nx.dev/blog/nx-self-healing-ci); [Nx 2026 roadmap](https://nx.dev/blog/nx-2026-roadmap)
- **Agent CI loops:** Google Jules and similar agents receive the CI error on PRs they opened, fix, and re-push. A third-party guide estimates agent self-correction loops "may execute 5–10 validation cycles per task." That figure is an estimate, not a measurement. — [Bunnyshell: agentic development infra](https://www.bunnyshell.com/guides/agentic-development/) [third-party]; [levelop.dev agents ranking](https://levelop.dev/blog/the-best-ai-coding-agents-in-2026-a-practical-ranking-for-working-developers) [third-party]
- **Merge-queue vendors' positioning:** Aviator markets merge queue + review routing + stacked PRs + "AI verification" explicitly against AI-driven PR growth. Mergify bundles merge queue, CI insights, and test intelligence. — [tooldirectory.ai Aviator](https://tooldirectory.ai/tools/aviator) [third-party]; [Mergify comparison](https://mergify.com/compare-mergify) [vendor]
- **Commentary:** "The Merge Queue Is the New Bottleneck" (Jul 2, 2026) argues that high-AI-adoption teams merge ~2x as many PRs with little delivery improvement, because CI and queue capacity were sized for human rates. This is opinion. — [TianPan.co](https://tianpan.co/blog/2026-07-02-the-merge-queue-is-the-new-bottleneck) [third-party opinion]

### Inferences
- Current "agent-era" launches mostly add *more* CI runs (self-healing re-runs, agent retry loops). They do not reduce runs per change. The cost-reducing primitives are older techniques now being repositioned for throughput: Uber-style speculation pruning, affected-target queues, selection, caching.
- Conflict rates of 20–42% among concurrent agent PRs mean that much speculative CI on agent branches validates states that will never merge. Conflict-aware scheduling (Uber's conflict analysis, Trunk/Aviator target lanes) applies directly here.
- Mergify's lower broken-main rate for AI-assisted PRs suggests the problem is volume and contention more than quality. That is one observational vendor dataset and needs corroboration.

### Gaps
- No primary-source announcement was found for a GitHub-native merge queue or Actions feature built specifically for agent volume in 2025–2026. GitHub's Copilot coding agent and Agents tab exist, but nothing in this pass showed CI-capacity features.
- Agent-specific features from Trunk, Graphite, Buildkite, or Depot (e.g., agent sandboxes, per-agent CI quotas) were not confirmed.
- No measured data was found on CI minutes consumed per agent task or per agent PR.
