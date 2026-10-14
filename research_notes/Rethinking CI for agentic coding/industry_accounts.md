# Industry accounts: CI as the bottleneck for AI coding agents (2025–2026)

Research date: 2026-10-13. Sources are labeled by type:
- **[ENG]** first-hand engineering account from the company that did the work
- **[ENG-2nd]** first-hand account reached through a secondary write-up (interview, newsletter, aggregator); treat details with care
- **[VENDOR]** vendor report or marketing from a company selling CI/merge/test tooling
- **[RESEARCH]** academic or survey research
- **[PRESS]** press or blog commentary

## 1. What the two Anthropic articles say

### Takeaway
Anthropic says agent output (8x code per engineer per quarter, ~80% Claude-authored) pushed CI jobs up 25x in six months and merges up ~12x in four months (2,500/day in May 2026 to 30,000+/day in September 2026). Its fixes were (a) a horizontally scaled, stateless test-impact-analysis (TIA) service and (b) Scion, an in-house server-centric version control system with API-first queries and tiered object caches. It also dropped the idea of a global-lock pre-merge queue in favor of post-merge and pre-deploy testing, letting Claude fix the resulting conflicts.

### Cited Findings

**Article A: "Agentic coding is straining CI. Here's how we scaled test impact analysis at Anthropic"** [ENG]. Sachin Malhotra, published 2026-09-14 (JSON-LD datePublished). [Source](https://claude.com/resources/articles/agentic-coding-is-straining-ci-heres-how-we-scaled-test-impact-analysis-at-anthropic)

*Problem framing and numbers*
- Subtitle (paraphrased): CI job volume grew 25x in six months, and the test selection service was patched three times before a lasting fix. — [Source](https://claude.com/resources/articles/agentic-coding-is-straining-ci-heres-how-we-scaled-test-impact-analysis-at-anthropic)
- Paraphrased: Anthropic engineers ship on average 8x as much code per quarter as in 2021–2025. Claude writes about 80% of it, and also does much of the PR review and approval. — [Source](https://claude.com/resources/articles/agentic-coding-is-straining-ci-heres-how-we-scaled-test-impact-analysis-at-anthropic)
- Framing: writing code is no longer the constraint, "and once PR review gets accelerated, CI starts feeling the pressure." — [Source](https://claude.com/resources/articles/agentic-coding-is-straining-ci-heres-how-we-scaled-test-impact-analysis-at-anthropic)
- Paraphrased: tests across the codebase grew 10x with only a few more engineers, giving a 25x rise in CI jobs over six months. The author notes that not every test runs on every PR. — [Source](https://claude.com/resources/articles/agentic-coding-is-straining-ci-heres-how-we-scaled-test-impact-analysis-at-anthropic)
- Run-all-tests does not scale (paraphrased): many organizations still run every test on every change. That works for a while, then gates become long, expensive and untrustworthy. — [Source](https://claude.com/resources/articles/agentic-coding-is-straining-ci-heres-how-we-scaled-test-impact-analysis-at-anthropic)
- Agents need test selection more than humans do (paraphrased): a human can tell which failures are unrelated, but an agent needs more context. Given a specific set of valid tests, agents self-verify and iterate better. — [Source](https://claude.com/resources/articles/agentic-coding-is-straining-ci-heres-how-we-scaled-test-impact-analysis-at-anthropic)
- PR shape changed: Claude prefers smaller PRs, so there are more CI jobs per day. Agents raise the baseline load by pushing at night and on weekends, but load stays bursty because humans still drive and approve many PRs (paraphrased). — [Source](https://claude.com/resources/articles/agentic-coding-is-straining-ci-heres-how-we-scaled-test-impact-analysis-at-anthropic)

*Original TIA design*
- A deterministic test selection service chooses tests per change "based on past performance and package relevance." Two parts: a **listener** that records test results from every CI run, and a **selector** that reads result history and picks tests for open PRs. — [Source](https://claude.com/resources/articles/agentic-coding-is-straining-ci-heres-how-we-scaled-test-impact-analysis-at-anthropic)
- v0 ran as a single process because "keeping a running history per test meant a single writer needed to apply the results", so it could not shard horizontally. — [Source](https://claude.com/resources/articles/agentic-coding-is-straining-ci-heres-how-we-scaled-test-impact-analysis-at-anthropic)
- Failure mode is listener lag: 20 minutes of lag can leave tens of thousands of test updates unapplied to the selector (paraphrased). Effects: a bad change merges and a test fails for everyone, causing duplicate investigations; a flaking dependency causes "flaky reds" that block merges; a fixed or new test does not run until the listener catches up, which risks regressions. — [Source](https://claude.com/resources/articles/agentic-coding-is-straining-ci-heres-how-we-scaled-test-impact-analysis-at-anthropic)

*Three patches with shrinking lifetimes*
- Oct 2025: the team was paged two days in a row, so it doubled the cores. That lasted 70 days. — [Source](https://claude.com/resources/articles/agentic-coding-is-straining-ci-heres-how-we-scaled-test-impact-analysis-at-anthropic)
- Feb 2026: per-package sharding ("a single writer per package"), with code generated by Claude. That lasted 29 days. — [Source](https://claude.com/resources/articles/agentic-coding-is-straining-ci-heres-how-we-scaled-test-impact-analysis-at-anthropic)
- Mar 2026: the process hit its memory limit "by mid-afternoon on most weekdays". Swapping the memory allocator did nothing. The team would not memory-profile a loaded singleton. Daily restarts lasted "less than a day", and the service fell further behind each time. When it fell more than an hour behind, which happened several times, many job results were never recorded. — [Source](https://claude.com/resources/articles/agentic-coding-is-straining-ci-heres-how-we-scaled-test-impact-analysis-at-anthropic)
- Effect of the lost results: the selector used stale data. "Mostly this translated into us running tests that were already super flaky or widespread-failing." The author says this did not mean untested code reached production. — [Source](https://claude.com/resources/articles/agentic-coding-is-straining-ci-heres-how-we-scaled-test-impact-analysis-at-anthropic)
- Organizational friction (paraphrased): ownership was unclear, nobody wanted another piece of infrastructure, and the CI team had other priorities. — [Source](https://claude.com/resources/articles/agentic-coding-is-straining-ci-heres-how-we-scaled-test-impact-analysis-at-anthropic)
- A long-running Claude Tag session monitored the service. It pinged the author whenever listener lag passed 50,000 jobs, and it "often argued for an overhaul" before the team agreed to one. — [Source](https://claude.com/resources/articles/agentic-coding-is-straining-ci-heres-how-we-scaled-test-impact-analysis-at-anthropic)

*Redesign*
- The team added an in-memory data store. Stateless listener workers append any result to a journal. A small consumer process rolls the journal into per-test history "every few seconds". The selector queries that history. "more expensive to run, but it is much easier to scale and memory profile than a shaky singleton." — [Source](https://claude.com/resources/articles/agentic-coding-is-straining-ci-heres-how-we-scaled-test-impact-analysis-at-anthropic)
- One engineer did the project in three weeks; the author estimates it would have taken about a quarter a year earlier (paraphrased). Claude tuned the journal size and worker count "largely autonomously". The backlog chart of queued, unprocessed job-result events went flat after cutover. Before, it built up most days and grew week over week. — [Source](https://claude.com/resources/articles/agentic-coding-is-straining-ci-heres-how-we-scaled-test-impact-analysis-at-anthropic)

*Conclusions and advice*
- The common scaling tricks (bigger machines, parallelizing, restarts) are not the lesson: "each of these techniques bought a fraction of the time they did a year ago," while a full redesign "also takes a fraction of the time." — [Source](https://claude.com/resources/articles/agentic-coding-is-straining-ci-heres-how-we-scaled-test-impact-analysis-at-anthropic)
- "assume your architecture will be at a 25x load within two quarters"; "account for 10-20x the perceived scale in your v0 designs as long your budget allows for it." — [Source](https://claude.com/resources/articles/agentic-coding-is-straining-ci-heres-how-we-scaled-test-impact-analysis-at-anthropic)
- Instrument services as "Claude's eyes and ears", and in particular "ensure that the same number of CI jobs coming in equals the same going out." Keep state out of the process. Avoid single-instance critical services. Prediction: "horizontally scaled test selection architecture will become industry standard." — [Source](https://claude.com/resources/articles/agentic-coding-is-straining-ci-heres-how-we-scaled-test-impact-analysis-at-anthropic)

**Article B: "Redesigning source control at Anthropic"** [ENG]. Nick G. and the source control team, published 2026-10-13. [Source](https://www.anthropic.com/engineering/redesigning-source-control)

*Problem framing and numbers*
- "The bottleneck, now, is all of the developer infrastructure built for human scale: source control, builds, and CI." — [Source](https://www.anthropic.com/engineering/redesigning-source-control)
- Merged changes per day went from about 2,500 in May 2026 to over 30,000 in September: ~12x in about four months. The authors argue that demand for merging code is effectively unlimited, so removing one bottleneck immediately raises the amount of code produced (paraphrased). — [Source](https://www.anthropic.com/engineering/redesigning-source-control)
- Monorepo scale: main-branch history "almost 100 GB"; compressed working copy "over 25 GB"; roughly 25 million checkouts per day for CI alone, not counting developer environments, agent sandboxes and research jobs. Fetched naively, that would exceed 600 PB of git traffic per day (paraphrased). — [Source](https://www.anthropic.com/engineering/redesigning-source-control)
- Earlier mitigations: shallow clones, sparse checkouts, promisor remotes, git mirrors, and blob-storage snapshots ("seeds"). "At our peak, we operated several hundred internal git mirrors." Seeds drifted from the tip of main, and diff and blame on partial clones got harder to keep working. — [Source](https://www.anthropic.com/engineering/redesigning-source-control)
- Key insight: the company used git as a centralized system, and "nearly all of our clients were agents and jobs that are online by definition." — [Source](https://www.anthropic.com/engineering/redesigning-source-control)

*Design principles of Scion (prior art cited: Google Piper, Meta Sapling)*
- Clients are always online. The design is asymmetric: the server computes history, blame, commits, merges, and rebases, while the client holds a bounded object cache and the working copy. All client queries are also exposed as an API, "so in many cases jobs don't need a local repository at all". Automated bisect and revert pipelines "wouldn't be practical at scale without" this. — [Source](https://www.anthropic.com/engineering/redesigning-source-control)
- Everything scales horizontally: "no fully materialized copy of the repo anywhere, even on the server", and there are no packfiles, so no repo maintenance is needed. Commit cost "has to scale with the size of the change, not the overall size of the repo". Refs are discouraged except main and release branches, because shared global state is a scaling risk. — [Source](https://www.anthropic.com/engineering/redesigning-source-control)
- The working copy is optional and sparse by design. A CI job that needs the diff to its merge base can ask the server. Many writes skip checkout entirely. Checkouts can be sparse or virtualized (files materialize on demand). — [Source](https://www.anthropic.com/engineering/redesigning-source-control)

*Architecture*
- Unit of work is the "changeset", a write-ahead-log entry. It lists the files changed against the first parent, with content-addressed pointers to compressed blobs. There is no locking or cross-server coordination. Moving a ref is a compare-and-swap on one Spanner row. — [Source](https://www.anthropic.com/engineering/redesigning-source-control)
- "Derived data" (blame, path history, commit-graph skip lists, copy detection, path search indices) is defined recursively from parent values. It can be computed eagerly or lazily, and it is invisible to clients. — [Source](https://www.anthropic.com/engineering/redesigning-source-control)
- Fetch protocol: the client asks only for the trees and blobs it wants, rather than telling the server what it has. Requests are for immutable objects, so any cache can answer them. Tiers: scion-daemon (one per node, starts from a periodic snapshot), regional scion-cache (streams objects from memory in on-disk format, with no delta compression), and scion-server (reads Spanner and cloud storage). All tiers use identical RPCs, and tiering is strictly enforced to isolate failure domains. — [Source](https://www.anthropic.com/engineering/redesigning-source-control)

*Results*
- Each tier has a cache hit rate above 99%. The footprint is "200x smaller than our previous git mirroring infrastructure in terms of CPU and memory". CI and research checkouts are "two orders of magnitude faster (in seconds rather than minutes)". "CI alone realized a 25% CPU capacity win." — [Source](https://www.anthropic.com/engineering/redesigning-source-control)
- A team of 7 built Scion, the Antique code-review tool, code search, source-control IAM, and new landing tooling, and migrated in five months "while the volume of code merged per day increased by 10x". A Claude Mythos Preview rewrite of the git-to-Scion ingestion pipeline used "20x less memory and was 4x faster". — [Source](https://www.anthropic.com/engineering/redesigning-source-control)

*CI and merge-queue conclusions*
- Paraphrased: a classic merge queue does not fit agent scale, since hundreds or thousands of changes can merge while tests run. They could not replicate a global repository lock on the merge queue, so they invested in post-merge and pre-deploy automated testing instead. Concurrent changes can conflict, but Claude usually fixes the conflicts faster than humans can spot them. — [Source](https://www.anthropic.com/engineering/redesigning-source-control)
- Review changes: the code review tool can "express complex semantic constraints on approvals" (for example, comment-only changes versus sensitive logic). Team members "examine the intent of the change as opposed to reading every line of code." The team uses Claude "superfans" in Slack, including an "Antique merge queue superfan", to watch telemetry. — [Source](https://www.anthropic.com/engineering/redesigning-source-control)
- Limits: Scion is "by no means a suitable replacement for git for general use". It requires its own review, code search, and CI. Anthropic's token spend "far exceeds what any other business would realistically want to spend." Anthropic expects "this class of problems will become more commonplace over the next six to 12 months" and suggests git forges add server-side RPCs and better-composing sparse and shallow features. — [Source](https://www.anthropic.com/engineering/redesigning-source-control)

**Related Anthropic post: "AI CI/CD on-call"** [ENG]. Sachin Malhotra, 2026-08-18. Claude Tag acts as the CI/CD on-call first responder. It publishes a first analysis within about 15 minutes, with a median of 14 minutes to the first evidence-grounded analysis and a fastest root cause of 4 minutes. The post repeats the "8x as much code per quarter" figure. — [Source](https://claude.com/resources/articles/ai-ci-cd-on-call)

### Inferences
- The two articles together describe one pipeline under load at three layers: test selection (TIA), checkout and source control (Scion), and merge gating (merge queue abandoned for post-merge testing). Each layer failed for the same reason: state or coordination that was single-writer or global.
- There is a small internal inconsistency. The Scion post gives ~12x (2,500 to 30,000+/day, May–Sep) and also "10x" for the build period. The TIA post gives 25x CI jobs over six months, which is a different metric. These numbers should not be merged into one growth figure.
- Anthropic's results depend on a token budget and engineering capacity that it says are atypical. Other companies' accounts (below) show 2x–10x growth rather than 25x.

### Gaps
- Neither Anthropic post gives CI spend in dollars, queue wait times, flaky-test rates, test-selection ratio (tests selected per PR), or missed-failure (escape) rate for TIA.
- The Scion post does not quantify the post-merge conflict or breakage rate after the merge queue was dropped.
- I could not retrieve Hacker News threads on either post. The Algolia API calls failed, and the Scion post is dated today.

## 2. Metrics companies report (PR/commit volume, CI load, queue times, conflicts, flakiness, time-to-merge)

### Takeaway
First-hand company numbers cluster around ~10x CI or pipeline load within ~6 months at the most agent-heavy firms: Anthropic 25x CI jobs, OpenAI "roughly 10x" on some systems, Anthropic 12x merges/day. Agent share of merged PRs is 25–80% at several firms. Platform-level data (GitHub) shows commits growing ~14x year over year and Actions minutes doubling. Few companies publish queue-time, flake-rate, or CI-dollar figures.

### Cited Findings

**Company first-hand (engineering)**
- **Anthropic:** 8x code per engineer per quarter, 80% Claude-authored, tests 10x, CI jobs 25x in six months. Listener lag was considered a page-worthy problem at >50,000 jobs. — [Source](https://claude.com/resources/articles/agentic-coding-is-straining-ci-heres-how-we-scaled-test-impact-analysis-at-anthropic). Merges went from 2,500/day (May 2026) to 30,000+/day (Sep 2026), with ~25M CI checkouts/day. — [Source](https://www.anthropic.com/engineering/redesigning-source-control)
- **OpenAI** [ENG-2nd, Pragmatic Engineer, 2026-09-15]: VP Eng Applied Infra Venkat Venkataramani said PRs per engineer are rising like a hockey stick and every stage of build-test-deploy carries far more load, about 10x on some systems. Growth that takes two or three years elsewhere took about six months at OpenAI (paraphrased). — [Source](https://newsletter.pragmaticengineer.com/p/openai-software-factory)
- **OpenAI Codex team** [ENG-2nd]: CI takes about 15–20 minutes. Codex is told to open PRs immediately and skip most local tests, because CI runs them on Mac, Linux, and Windows. The "Harness engineering" experiment reported ~1,500 PRs from 3 engineers (3.5 PRs/engineer/day). — [Source](https://newsletter.pragmaticengineer.com/i/215812293/solving-load-challenges) (search-result snippets; the openai.com/index/harness-engineering primary returned HTTP 403 to me, so I could not verify it directly)
- **Linear** [ENG, Mufeez Amjad, 2026-09-21]: the test suite "nearly quadrupled" since January, with "roughly 2,000 tests a week" added. Without the optimizations, PR wait would have reached about 11 minutes. Actual PR wait went from "more than 6 minutes to just over 5". Runner time per test was cut roughly in half. — [Source](https://linear.app/now/ci-bottleneck-reworked). Press coverage says agents now write most of Linear's tests and credits CTO Tuomas Artman with ordering the overhaul. — [Source](https://runtimewire.com/article/linear-reworks-ci-ai-coding-verification-bottleneck)
- **Stripe** [ENG, Alistair Gray, 2026-02-19]: "Over 1,300 Stripe pull requests…merged each week are completely minion-produced", against a test battery of "over three million" tests. — [Source](https://stripe.dev/blog/minions-stripes-one-shot-end-to-end-coding-agents-part-2)
- **Uber** [ENG-2nd, AI Engineer talk by Uday Kiran Medisetty and Adam Huda, 2026-08-21]: "more than 70% of Uber's PRs are now opened by local or cloud agents"; "2× lines of code per engineer year over year"; "250+ automated migrations covering 9 million lines of code"; CI capacity is named as a constraint. — [Source (summary of talk)](https://openclawdatabase.com/news/videos/2026-08-21-uber-agentic-sdlc-software-factory/index.md); [Video](https://youtube.com/watch?v=17-YSUHo6Lk)
- **Shopify** [ENG-2nd via Port aggregator, citing Shopify Engineering posts of 2026-05-28 and 2026-07-29]: in a 30-day window, "1 in 8 of all merged pull requests carries River as a coauthor", with 59,918 agent sessions and 3,536 River-coauthored PRs merged. Shopify does not track AI-authored LOC or PR counts as success metrics. PR reversion rate "has remained roughly the same". — [Source](https://software-factories.port.io/shopify)
- **Ramp** [ENG-2nd via InfoQ, 2026-01-23]: the internal agent Inspect accounts for about 30% of merged PRs in the frontend and backend repos. — [Source](https://infoq.com/news/2026/01/ramp-coding-agent-platform/); primary: [Ramp Builders](https://builders.ramp.com/post/why-we-built-our-background-agent)
- **Vercel** [ENG-2nd, 2026-08-12 report]: ai-sdk-factory authored 25–35% of weekly merged PRs to main in the AI SDK repo. Factory backports are over half of weekly merges to the v6 line. Every merge still needs human approval. — [Source](https://www.plushcap.com/content/vercel/blog/vercel-building-a-software-factory-for-ai-sdk)
- **Block** [ENG, Bradley Axen, 2026-10-08]: "In any given migration, we might merge a thousand pull requests orchestrated by Fable." Merges to main and deploys stay human-controlled, and "Two humans have to approve the deploy." — [Source](https://claude.com/resources/articles/how-block-orchestrates-claude-fable-across-thousands-of-pull-requests)
- **Cursor** [PRESS/aggregator]: "More than 35% of the PRs merged at Cursor's own engineering team are now written by autonomous cloud agents." I did not verify this against a Cursor primary source. — [Source](https://www.buildfastwithai.com/blogs/cursor-cloud-agents-development-environments-2026)
- **Atlassian** [ENG, 2026-04-29, not AI-specific]: Bitbucket merge queues landed 30,000 PRs. The Jira repo does 300+ merges/day with concurrency 14. Semantic merge-conflict failures fell from "7–10%" to "nearly zero", and incidents from semantic conflicts fell from "3–5 / week" to rare. Jira build time went from 40 to 35 min. — [Source](https://www.atlassian.com/blog/bitbucket/merge-queues-how-we-ship-faster-with-fewer-incidents)

**Platform-level (GitHub)**
- GitHub COO Kyle Daigle (2026-04-04): 1B commits in 2025, now 275M/week (on pace for ~14B in 2026). Actions went from 500M min/week (2023) to 1B/week (2025) to 2.1B minutes in the current week. — [Source](https://feeds.simonwillison.net/2026/Apr/4/kyle-daigle/) (cites [Daigle on X](https://twitter.com/kdaigle/status/2040164759836778878))
- Agent-initiated PRs on GitHub went from ~4M (Sep 2025) to 17M+ (Mar 2026). This comes from a secondary report of Daigle remarks and is unverified. — [Source](https://longportapp.cn/news/281947223)
- Octoverse 2025 (2025-10-28): 518.7M PRs merged (+29% YoY), nearly 1B commits (+25.1%), and "over one million pull requests" authored by the Copilot coding agent between May and Sep 2025. — [Source](https://github.blog/news-insights/octoverse/octoverse-a-new-developer-joins-github-every-second-as-ai-leads-typescript-to-1/)
- GitHub capacity stress, August 2026: an Aug 6 outage of about 9 hours hit Actions and the Copilot coding agent. Aug 17 peaked at a 56% front-door failure rate. GitHub moved "a third of Actions jobs" to spare capacity. A quote attributed to GitHub reads: "Our shared infrastructure services have not kept up with our month-over-month actions growth and peak load." — [Source](https://devops.com/githubs-august-outages-show-growth-is-outpacing-infrastructure/) (devops.com, 2026-09-11; it does not link GitHub's primary report)

**Merge conflicts (research)**
- In 33,596 agent-authored PRs across 2,807 repos, 40.2% of repos had agent PR pairs with exact temporal overlap, and those pairs made up 79.4% of agent PRs. Replaying 716 three-way merges gave conflict rates of 19.8% intra-agent and 41.7% cross-agent. — [Source (summary)](https://codex.danielvaughan.com/2026/07/28/agent-pr-merge-conflicts-concurrent-coding-agents-codex-cli-worktree-isolation-coordination-defence/); paper: [arXiv 2607.04697](https://arxiv.org/abs/2607.04697) (I did not read the paper directly)

### Inferences
- Agent share of merged PRs is now a commonly reported metric: Uber >70%, Anthropic ~80% of code, Cursor ~35%, Vercel AI SDK 25–35%, Ramp ~30%, Shopify 1 in 8. CI cost and queue-time metrics are rarely disclosed. Linear is the clearest exception.
- Growth in test count is an independent driver of CI load: Anthropic tests 10x, Linear ~4x. Agents write tests as well as code, so CI cost grows faster than PR count alone would suggest.

### Gaps
- No company in this set disclosed CI dollar spend growth or flaky-test rates attributable to agents.
- I found no first-hand time-to-merge or queue-wait data except Linear's PR wait. Anthropic, OpenAI, and Stripe give load multipliers only.
- I found no primary engineering posts on CI load from Meta, Google, Cognition, Factory, Replit, Airbnb, Spotify, Coinbase, Figma, or Notion. Meta coverage is limited to press on MetaCode adoption ([Computerworld](https://www.computerworld.com/article/4157175/meta-moves-fast-toward-a-world-where-ai-builds-the-software.html)), with no CI numbers.

## 3. Failure modes described

### Takeaway
Reported failure modes are: (1) stateful CI services such as test selection falling behind; (2) checkout and clone load on source control; (3) merge queues that cannot serialize agent-rate merges; (4) concurrent agent PRs conflicting; (5) flaky or stale-selected tests blocking merges; (6) review time rising as PR volume grows; (7) main-branch stability falling. Claims that teams are deleting unit tests because they slow agents did not hold up to verification.

### Cited Findings
- **Stateful CI service lag (Anthropic):** listener lag leads to stale selection. The results are bad merges breaking tests for everyone, "flaky reds" blocking merges, and new or fixed tests not running. Quick fixes lasted 70 days, then 29, then under 1 day. — [Source](https://claude.com/resources/articles/agentic-coding-is-straining-ci-heres-how-we-scaled-test-impact-analysis-at-anthropic)
- **Source control and checkout load (Anthropic):** several hundred git mirrors, seeds drifting from main, and history operations breaking on partial clones. — [Source](https://www.anthropic.com/engineering/redesigning-source-control)
- **Merge queue collapse (Anthropic):** the team could not replicate "a global repository lock on the merge queue" at agent scale, and accepts post-merge conflicts that Claude repairs. — [Source](https://www.anthropic.com/engineering/redesigning-source-control)
- **Merge queue collapse (Mitchell Hashimoto, Pragmatic Engineer, 2026-02-25):** the episode summary says "Agents cause so much churn that merge queues become untenable, branches proliferate, and repos balloon." — [Source](https://newsletter.pragmaticengineer.com/p/mitchell-hashimoto). Mergify paraphrases him as saying queues "buckle once AI agents write the code at 100x the churn". — [Source](https://mergify.com/blog/merge-queues-and-ai-coding-agents)
- **Concurrent agent conflicts (research):** cross-agent PR pairs conflict 41.7% of the time, against 19.8% for intra-agent pairs. 84.4% of conflicts involve source files. — [Source](https://codex.danielvaughan.com/2026/07/28/agent-pr-merge-conflicts-concurrent-coding-agents-codex-cli-worktree-isolation-coordination-defence/)
- **Unbounded CI retry loops (Stripe):** CI runs cost tokens, compute and time, and the authors see diminishing returns from letting an LLM run indefinitely many rounds (paraphrased). — [Source](https://stripe.dev/blog/minions-stripes-one-shot-end-to-end-coding-agents-part-2)
- **Agent CI load at peak hours (Uber):** maintenance agents are scheduled for Sunday to avoid "avoidable load on CI infrastructure" and to keep "Monday's review queue human-sized". — [Source](https://openclawdatabase.com/news/videos/2026-08-21-uber-agentic-sdlc-software-factory/index.md)
- **Agents breaking system constraints (Anthropic):** engineers often had to tell Claude "no". In one case, systems tried to brute-force the merge time by linearly reading the commit log. Adversarial review can be "myopic" and lead to over-engineering. — [Source](https://www.anthropic.com/engineering/redesigning-source-control)
- **Mobile release gates (OpenAI):** app store review takes "hours or days", which does not keep pace with agent velocity. — [Source](https://newsletter.pragmaticengineer.com/p/openai-software-factory)
- **Platform saturation (GitHub):** capacity-driven outages hit Actions and the Copilot coding agent in August 2026. — [Source](https://devops.com/githubs-august-outages-show-growth-is-outpacing-infrastructure/)
- **Main-branch instability (CircleCI data):** the main-branch success rate was 70.8%, "the lowest in over five years". Median recovery was 72 min, up 13%. — [Source](https://circleci.com/blog/five-takeaways-2026-software-delivery-report)
- **Unit-test deletion and "unit tests hinder agents":** I found only commentary (for example, claims that agents delete test files to make suites pass, and a claimed 811,883-line unit-test deletion PR). I could not verify the deletion claim. My search for the PR found nothing. — [Source (commentary)](https://smartscope.blog/en/blog/ai-generated-unit-tests-really-necessary-gpt-6-2026/)

### Inferences
- The flaky-test problem is amplified rather than new. Anthropic says agents, unlike humans, cannot easily tell which failures are irrelevant, so noise in test selection turns directly into wasted agent iterations.
- Linear chose to bound agent-written tests with guardrails (opt-in isolation rules in agent skills) rather than delete them.

### Gaps
- I found no first-hand engineering post reporting that a team deleted unit tests because they blocked agent refactors.
- I found no published merge-queue throughput figures, such as queue depth or ejection rate under agent load, from any company.

## 4. What each company changed

### Takeaway
Fixes fall into five groups: (a) run fewer tests (TIA, selective tests, capped CI rounds); (b) make each CI job cheaper (faster checkout, tooling swaps, sharding, base images, faster runners); (c) shift checks left into the agent's inner loop; (d) rethink merge gating (abandon global-lock queues, use batching/bisecting queues, or post-merge testing); (e) re-route review by risk, with agents watching CI. Anthropic is the only company that replaced source control.

### Cited Findings
- **Anthropic:** a stateless, horizontally scaled TIA service (journal in an in-memory store, roll-up consumer, selector) — [Source](https://claude.com/resources/articles/agentic-coding-is-straining-ci-heres-how-we-scaled-test-impact-analysis-at-anthropic). Also Scion VCS with an API-first design, sparse and virtual checkouts, and tiered caches; post-merge and pre-deploy testing in place of a global merge queue; the Antique review tool with semantic approval rules; and Claude "superfans" for each component — [Source](https://www.anthropic.com/engineering/redesigning-source-control). Claude Tag serves as CI/CD on-call — [Source](https://claude.com/resources/articles/ai-ci-cd-on-call)
- **Linear (2026-09-21):** "No rewrite, no new platform". Changes: third-party runners ("34% faster on average"); tsgo (`tsc` -73%); Oxlint and AST-based rules (API lint -68%, full lint -55%); sparse blobless checkouts; a custom checkout action with retries; change-detection job from 94s to 20s; Node and Postgres client in the base image; selective pnpm installs (44–73s down to 16–18s); dropped `node_modules` cache because rebuilding was faster (7.5s vs 28s); schema snapshots in place of migration replay (DB setup from ~12s to 1–2s); 7 checks consolidated into 2 jobs ("roughly 87,000 runner-minutes per month" saved); split test files; opt-in `isolate: false` vitest project; 8 shards, up from 3–4 (slowest shard from 5.25 to 4.33 min); agent skills updated so generated tests follow shared-state rules. — [Source](https://linear.app/now/ci-bottleneck-reworked)
- **Stripe (2026-02-19):** pre-push hooks with cached lint ("well under a second"). CI runs "all relevant tests" from a 3M+ suite. Autofixes are applied automatically. Failures without an autofix go back to an agent node. The run is capped at two CI rounds, then sent to a human. — [Source](https://stripe.dev/blog/minions-stripes-one-shot-end-to-end-coding-agents-part-2)
- **OpenAI:** risk-based PR routing (low-risk changes can be auto-approved by agents), several specialized agent reviewers, agents that "babysit" PRs until green, and a perf harness that sends risky PRs to an A/B synthetics framework. — [Source](https://newsletter.pragmaticengineer.com/p/openai-software-factory)
- **Uber:** agents "stop at a draft PR and do not push to CI". Outer-loop checks moved into the agent's inner loop, so the agent fixes what it finds before a human or CI sees it (paraphrased). Many CI failures get fixed automatically. Maintenance runs are scheduled for Sundays. — [Source](https://openclawdatabase.com/news/videos/2026-08-21-uber-agentic-sdlc-software-factory/index.md)
- **Block:** humans keep control of merges to main and deploys, with dual human approval and mandatory security checks before human review. — [Source](https://claude.com/resources/articles/how-block-orchestrates-claude-fable-across-thousands-of-pull-requests)
- **Shopify:** tracks PR reversion rate, not agent PR counts. — [Source](https://software-factories.port.io/shopify)
- **GitHub (platform):** routed a third of Actions jobs to spare capacity and cut ~1M QPS of DB load through a MySQL primary migration (as reported, not from a primary source). — [Source](https://devops.com/githubs-august-outages-show-growth-is-outpacing-infrastructure/)
- **Cursor:** launched Cursor Origin (early beta 2026-08-17), agent-native git hosting with PRs and cloud agents. Origin-hosted repos use Depot or Buildkite for CI. — [Source (secondary)](https://developer.tenten.co/cursor-origin-agent-native-code-hosting); [Cursor Origin](https://cursor.com/origin). Cursor acquired Graphite (stacked PRs and a stack-aware merge queue) in Dec 2025 — [Source](https://research.contrary.com/company/graphite)

**Vendor positioning [VENDOR]. These are claims, not engineering accounts.**
- **Mergify (2026-07-13):** batching ("Ten passing changes do not need ten CI runs"), bisecting failed batches, parallel queues for independent scopes, and test classification as healthy, flaky, or broken for agents. The post gives no customer data. — [Source](https://mergify.com/blog/merge-queues-and-ai-coding-agents)
- **Trunk:** quarantines known flakes inside queue runs, and plans to dispatch an AI agent to fix flaky tests. — [Source](https://trunk.io/roadmap); [Source](https://trunk.io/trunk-vs-aviator)
- **Graphite:** claims "74% faster merge times at Ramp" and "7 hours saved per engineer per week at Asana". — [Source](https://graphite.com/blog/the-first-stack-aware-merge-queue)

### Inferences
- The fixes split by scale. Mid-sized product companies (Linear, Stripe, Uber) cut per-job cost and moved checks into the agent loop. The highest-volume company (Anthropic) changed the architecture: dropping pre-merge serialization and replacing source control.
- "Cap CI rounds" (Stripe) and "don't push to CI until draft is done" (Uber) treat CI as a scarce resource that agents must earn access to. Anthropic instead treats CI as infrastructure to scale.

### Gaps
- I found no company post on remote build caching or Bazel/remote execution motivated by agents. BazelCon 2025 had only a BoF titled "AI Breaks Everything: Is Your Build Infrastructure Ready?" — [Source](https://blog.bazel.build/2025/12/08/bazelcon-recap.html)
- No company reported before/after numbers for batching merge queues under agent load.

## 5. Industry surveys and vendor reports quantifying CI growth

### Takeaway
Large datasets agree that AI raises raw activity (workflows, PRs, commits, LOC) but not delivered software. Review and validation absorb the gains, and main-branch stability has declined. CircleCI is a vendor with a product interest in this conclusion. DORA, Faros, and the Harvard/Jellyfish paper are more independent.

### Cited Findings
- **CircleCI 2026 State of Software Delivery [VENDOR data, 2026-02-18; 28,738,317 workflows, Sep 2025]:** average daily workflow runs +59% YoY ("the biggest throughput increase the company has ever seen"). Top 5% +97%, median +4%, bottom quartile flat. Median feature-branch throughput +15% but main-branch -7%. Top 10% feature branch ~+50% but main only +1%. Main success rate 70.8% ("lowest in over five years"; benchmark 90%). Median recovery 72 min (+13%). Mid-size companies take ~3 hours to recover. — [Source](https://circleci.com/blog/five-takeaways-2026-software-delivery-report)
- **CircleCI Q2 2026 Pulse [VENDOR, 2026-07-08]:** main success rate 76.7%. Feature-branch throughput +7.7% YoY while main was flat. Top 5% run 15.6 main workflows/day against a median of ~1.7 (9x gap). The top 20 orgs average ~2,165 main workflows/day (+72%). Merge Efficiency Ratio: median 3.9, top 5% 2.6, top 20 1.3. Claims $700K+/yr savings for a 50-dev team from inner-loop validation (marketing estimate). — [Source](https://circleci.com/blog/five-takeaways-2026-q2-pulse/)
- **DORA 2025 State of AI-assisted Software Development [RESEARCH, Google, Sep 2025]:** AI adoption is now positively associated with throughput, but "AI adoption not only fails to fix instability, it is currently associated with increasing instability." AI is described as an "amplifier". — [Source](https://www.infoq.com/news/2025/09/dora-state-of-ai-in-dev-2025); [Source](https://redmonk.com/rstephens/2025/12/18/dora2025/)
- **GitHub Octoverse 2025 [VENDOR platform data, 2025-10-28]:** 518.7M PRs merged (+29%), ~1B commits (+25.1%), 1M+ Copilot coding agent PRs (May–Sep 2025). — [Source](https://github.blog/news-insights/octoverse/octoverse-a-new-developer-joins-github-every-second-as-ai-leads-typescript-to-1/)
- **Faros AI "AI Productivity Paradox" [VENDOR telemetry, Jul 2025; 10,000+ devs, 1,255 teams]:** high-AI-adoption teams complete 21% more tasks and merge 98% more PRs, but PR review time is +91%, PR size +154%, and bugs/dev +9%. There is no company-level improvement. — [Source](https://www.faros.ai/ai-productivity-paradox)
- **Harvard job-market paper, Chen & Stratton, "Artificial Intelligence in the Firm: Bottlenecks in Software Production" [RESEARCH, version dated 2026-08-04; Jellyfish data, ~300M events, 725,938 workers, 718 firms, Jan 2021–Mar 2026]:** after agent adoption, LOC +30%, commits +20%, PRs +23%, PR review time +49%, and no statistically significant rise in finished tasks. — [Source (press summary)](https://fourweekmba.com/ai-coding-agents-add-30-more-code-not-more-finished-work/); [Source (German press)](https://borncity.com/news/harvard-studie-zu-ki-agenten-pull-requests-brauchen-49-prozent-laenger/) (I did not read the paper directly)
- **Research on agent PR conflicts:** see Section 2 ([arXiv 2607.04697](https://arxiv.org/abs/2607.04697)).

### Inferences
- The CircleCI pattern of feature-branch activity rising while main-branch throughput stays flat or falls fits the company accounts. CI on branches absorbs agent volume, but integration into main does not speed up. Note that CircleCI benefits commercially from this framing.
- Survey data mostly covers human-plus-assistant teams in 2025. The company accounts (Anthropic, OpenAI) describe agent-dominated loads in 2026 that are an order of magnitude higher.

### Gaps
- I found no vendor report that quantifies CI spend in dollars or compute minutes attributable to agents. GitHub's Actions-minutes figure is the closest proxy and is not split by agent versus human.
- I did not find GitHub Octoverse 2026 (not yet located; may not be published), a DORA 2026 report, Graphite/LinearB agent-specific CI benchmarks, or Buildkite/Harness/Datadog reports with agent-attributed CI growth.
- An NBER paper "Writing Code vs. Shipping Code: Productivity Effects Across Generations of AI Coding Tools" (w35275) appeared in search results but I did not read it. — [Source](https://www.nber.org/index.php/papers/w35275)
