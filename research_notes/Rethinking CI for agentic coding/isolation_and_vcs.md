# Isolation, environment, and source-control technologies that change CI for parallel agents

Research date: 2026-10-13. Source quality notes are inline. Several numbers come from vendor pages or aggregator blogs; those are flagged.

## 1. Sandbox snapshot/fork tech for agents and CI (Firecracker, Morph, Modal, E2B, Daytona, CodeSandbox, Fly, gVisor, CRIU, warm pools)

### Takeaway
Spinning up a VM or container for an agent or CI job now takes milliseconds to seconds, and the platforms have settled on one design: a microVM per agent, warm snapshots, and copy-on-write (CoW) memory forks. Forking a *running*, already-hydrated environment costs about 0.1–3 s per child, depending on the vendor. So the CI unit can be "fork a warm environment" rather than "build an environment."

### Cited Findings
- **Morph Cloud Infinibranch** (vendor claim): snapshots, branches, and restores whole VM environments in under 250 ms. It claims "near-zero overhead branching" and unlimited parallel branches, where a traditional VM clone needs a full copy of resources. — [Morph Cloud developers](https://cloud.morph.so/developers); [Morph docs blog](https://cloud.morph.so/docs/blog/developers)
- **Firecracker CoW fork (open-source forkd / Mitos projects, 2026)**: new KVM VMs map snapshot memory as `mmap(MAP_PRIVATE)` CoW, and CPU state restores in ~0.8 ms. They report 100 child microVMs forked from a warm parent in ~100 ms (101 ms) and a live branch of a running VM in ~150 ms. Snapshot-restore clones of warm agent sandboxes take ~28 ms. These are project self-reports, not independent benchmarks. — [forkd (codekk mirror)](https://p.codekk.com/detail/rust/deeplethe/forkd); [withone.ai on forkd](https://www.withone.ai/blog/forkd-firecracker-microvm-sandbox-one-cli/md); [mitos-run](https://huggingface.co/mitos-run)
- An industry trade blog of uncertain reliability says E2B, Blaxel, Modal, Vercel Sandboxes, and ClawRun are converging on "one agent, one kernel" microVM isolation. Its claim that sandboxing cuts security incidents by "~90%" is unsourced, so treat it as low confidence. — [agentmarketcap.ai, 2026-04-15](https://agentmarketcap.ai/blog/2026/04/15/clawrun-microvm-agent-isolation-production-fleet)
- **CodeSandbox** (now Together Code Sandbox; Together AI acquired it Dec 2024) runs Firecracker microVMs with memory snapshot and resume. It live-clones a running VM, or clones from a snapshot, in about 3 s using CoW. — [CodeSandbox SDK blog (mirror)](https://https-codesandbox_io.proxy.bugsmash.io/blog/joining-together-ai-introducing-codesandbox-sdk); [Ry Walker research on CodeSandbox SDK](https://rywalker.com/research/codesandbox-sdk); [Together docs](https://docs.together.ai/docs/code-execution)
- **Modal**:
  - Memory snapshots capture full container state, memory plus filesystem. Restoring is ~2.5x faster than a normal container start; for example, a Stable Diffusion function goes from ~13 s to ~3.5 s, and `import torch` restores at p50 ~1.05 s. — [Modal blog, 2025-01-28](https://modal.com/blog/mem-snapshots)
  - Sandbox memory snapshots can be restored into new Sandboxes as exact clones. Modal lists "branching Sandbox state to test different code changes independently" as a use case. — [Modal docs: sandbox memory snapshots](https://modal.com/docs/guide/sandbox-memory-snapshots); [Modal docs: sandbox snapshots](https://modal.com/docs/guide/sandbox-snapshots)
  - Feb 2026 added Directory Snapshots, which mount a captured directory into another Sandbox and are kept for 30 days after last use. Filesystem snapshots are stored as diffs and kept indefinitely. Named users include Ramp's "Inspect" background coding agent, Lovable, and RL at Meta. — [Modal blog, 2026-02-24](https://modal.com/blog/directory-snapshots-resumable-project-state-for-sandboxes)
  - An aggregator says Modal sandbox memory snapshots are experimental, expire after 7 days, and do not support GPU. — [Zylos research, 2026-09-23](https://zylos.ai/research/2026-09-23-agent-sandbox-snapshot-restore)
- **E2B / Daytona**:
  - Daytona creates sandboxes in under 90 ms using Docker containers on a shared kernel. E2B starts in ~150 ms using Firecracker microVMs, one kernel per session. These figures come from comparison pages by a competitor (Morph), so treat them as approximate. — [morphllm E2B vs Daytona (2026)](https://www.morphllm.com/comparisons/e2b-vs-daytona); [Ry Walker on Daytona](https://rywalker.com/research/daytona)
  - E2B pause costs about 4 s per GiB of RAM, and resume takes about 1 s. — [Zylos research, 2026-09-23](https://zylos.ai/research/2026-09-23-agent-sandbox-snapshot-restore)
- **Fly.io Machines**: suspend uses a Firecracker snapshot. Resume takes "a few hundred ms" versus ~2 s for a cold start, and Fly recommends suspend for machines with 2 GB RAM or less. — [Zylos research, 2026-09-23](https://zylos.ai/research/2026-09-23-agent-sandbox-snapshot-restore)
- **Persistence models across vendors** (Zylos aggregator):
  - Memory plus filesystem persistence: E2B, Modal, Fly.
  - Filesystem only: Daytona, Runloop, Vercel Sandbox, Cursor cloud agents.
  - Destroy on idle: OpenAI Code Interpreter after 20 min idle; OpenAI Agents hosted sandbox after 1 h.
  - Amazon Bedrock AgentCore: 900 s idle timeout, 8 h maximum lifetime, and no CPU billing during I/O wait. — [Zylos research, 2026-09-23](https://zylos.ai/research/2026-09-23-agent-sandbox-snapshot-restore)
- **Clone-correctness issues** (Zylos aggregator):
  - Firecracker supports VMGenID on x86_64 and aarch64, so clones can re-seed their RNGs; Linux 5.18+ has the `vmgenid` driver.
  - Firecracker v1.16.0 fixed a kvm-clock monotonic clock bug on Linux 5.16+.
  - CRIU can preserve TCP connections with `--tcp-established` / `TCP_REPAIR`.
  - gVisor has its own checkpoint/restore. — [Zylos research, 2026-09-23](https://zylos.ai/research/2026-09-23-agent-sandbox-snapshot-restore)
- **Storage-level snapshot/fork benchmark** (ComputeSDK, run weekly via GitHub Actions; last run Oct 9; 10 MB dataset; 100 iterations):
  - Tensorlake: snapshot 0.03 s, fork-from-snapshot 0.21 s, fork-from-live 0.25 s.
  - Tigris: snapshot 0.12 s, fork 0.08 s, fork-from-live 0.30 s.
  - Azure Blob: snapshot 1.09 s, fork 1.11 s, fork-from-live 2.17 s.
  - AWS S3, Archil, and Mosaic show 0% success. That probably means the feature is unsupported, not that the products are slow. — [ComputeSDK snapshot/fork benchmark](https://www.computesdk.com/benchmarks/storage/snapshot-fork)
- The "sandbox forking" pattern means each parallel agent run branches from a snapshot of an already-provisioned environment. Five variants then cost one setup plus five copies, not five setups. — [agentpatterns.ai: Sandbox Forking](https://agentpatterns.ai/patterns/agent-design/sandbox-forking/)

### Inferences
- Environment setup (dependency install, build cache warm-up, service boot) used to be the fixed cost of every CI job. CoW fork turns it into a one-time cost per base snapshot. A CI design can keep a "golden warm snapshot of main" (deps installed, build cache hot, test DB seeded), fork one child per agent change or test shard, and throw children away.
- Live fork (~150 ms – 3 s) makes it possible to fork an environment *mid-test*: run the expensive setup or fixture phase once, then branch to test N candidate changes or N fault scenarios. That is a CI version of the speculative-execution trees in section 6.
- The shared-kernel versus microVM choice is a security and isolation tradeoff. Daytona (containers) is ~90 ms; E2B (microVM) is ~150 ms. Untrusted agent code tilts toward microVMs, and the latency difference is now small.
- Snapshot cloning needs entropy and clock fixes (VMGenID, kvm-clock). Otherwise cloned test environments share RNG state, which is another source of flakiness or security bugs.

### Gaps
- No independent, cross-vendor benchmark of *live VM fork* latency found (Morph, Modal, E2B, CodeSandbox, forkd under one methodology). All VM-level numbers are vendor or project self-reports.
- No primary-source pricing per fork or per snapshot-GB was collected.
- gVisor and CRIU fork latencies for CI were not found in primary sources. No public data found on warm-pool sizing at large CI shops.

## 2. Deterministic simulation testing (Antithesis, FoundationDB, TigerBeetle VOPR, Polar Signals, WarpStream, Turso, madsim)

### Takeaway
Deterministic simulation testing (DST) makes every failure reproducible from a seed and compresses time: hours of simulation cover months of production. That turns flakiness from noise into a replayable bug report. It has spread from FoundationDB and TigerBeetle to a $105M-funded product (Antithesis) that runs whole docker-compose systems from CI.

### Cited Findings
- **Origin and core idea**:
  - DST was pioneered at FoundationDB around 2010. It is central to TigerBeetle's VOPR and to Antithesis's deterministic hypervisor (out of stealth in 2024). — [Antithesis DST resource](https://antithesis.com/resources/deterministic_simulation_testing/)
  - The whole cluster (nodes, network, disks) runs in one process where the only nondeterminism is a seeded PRNG. A failure reproduces by re-running the same 64-bit seed. — [mohakchugh DST explainer](https://mohakchugh.is-a.dev/blog/deterministic-simulation-testing)
- **WarpStream + Antithesis** (2024-03-12):
  - Scope: the entire SaaS (agents, control plane, Kafka clients, KV stores, Postgres, object storage), defined as docker-compose and triggered from GitHub Actions, which push images to the Antithesis registry.
  - Results: 6 wall-clock hours simulated 280 application hours. A metrics data race that 10,000+ hours of CI had missed was found within 233 s. A rare data-loss bug reproduced about once per wall-clock hour. Diminishing returns came at ~160 simulated hours. — [WarpStream blog](https://www.warpstream.com/blog/deterministic-simulation-testing-for-our-entire-saas); [Antithesis case study](https://antithesis.com/case_studies/warpstream/)
- **Antithesis funding**: $105M Series A led by Jane Street, announced 2025-12-03. Other investors include Amplify, Spark, Patrick Collison, Dwarkesh Patel, and Sholto Douglas. Customers named include Jane Street, Ethereum, and MongoDB. — [The Bridge](https://thebridge.jp/2025/12/antithesis-105m-series-a-jane-street-deterministic-simulation-testing); [Ventureburn](https://ventureburn.com/antithesis-series-a-105m/); [Sacra](https://sacra.com/c/antithesis/)
- **TigerBeetle "protocol-aware DST"** (2026-08-20):
  - VOPR checks safety invariants at three layers: strict serializability at the database, write-ahead-log agreement at consensus, and deterministic LSM structure at storage. It also checks liveness invariants, including recovery of blocks from cluster copies.
  - Replicas converge to byte-identical state. Scenarios that would take "months" in production take "minutes" in simulation. — [TigerBeetle blog](https://tigerbeetle.com/blog/2026-08-20-protocol-aware-dst); [VOPR docs](https://docs.tigerbeetle.com/about/vopr)
- **Turso** (SQLite rewrite in Rust, formerly Limbo):
  - Uses DST "from day one", with seeded reproducibility and fault injection, plus Antithesis. Antithesis found io_uring bugs under partial writes.
  - Offers $1,000 for any data-corruption bug its testing missed. — [Turso Limbo announcement](https://turso.tech/blog/introducing-limbo-a-complete-rewrite-of-sqlite-in-rust); [Turso announcement](https://turso.tech/blog/turso-the-next-evolution-of-sqlite)
- **Polar Signals**: first did DST in its Go database using a WASM runtime. When it rewrote in Rust, it modeled core components as explicit state machines instead of using a deterministic async runtime such as madsim. Talks at FOSDEM 2026 and QCon London Mar 2026. — [Polar Signals blog (2025-07-08)](https://www.polarsignals.com/blog/tags/testing); [QCon London 2026](https://qconlondon.com/presentation/mar2026/deterministic-simulation-testing-dst-journey-wasm-go-state-machines-rust); [FOSDEM 2026](https://fosdem.org/2026/schedule/event/rust-deterministic-simulation-testing)
- **Market**: most DST is built in-house (FoundationDB, TigerBeetle, WarpStream). Antithesis has little direct competition as a general-purpose product. — [Sacra on Antithesis](https://sacra.com/c/antithesis/)
- **Anthropic's Scion** (see section 5) was built with "hermetic simulations of infrastructure interactions" and fuzzing. The team calls it "among the most well-tested and well-defended codebases". — [Anthropic, 2026-10-13](https://www.anthropic.com/engineering/redesigning-source-control)

### Inferences
- In DST a failure is a seed, not a flake. CI can then file a reproducible artifact automatically, so an agent can bisect or fix it without "re-run until green."
- DST changes what a CI run is worth. A fixed test list gives the same answer every time. A seed-search budget (simulated hours per wall-clock hour) can be raised as code risk rises, and it keeps finding new states. WarpStream's diminishing returns at ~160 simulated hours suggest a per-change budget is feasible.
- Black-box DST (Antithesis hypervisor running docker-compose) needs no code changes. In-process DST (VOPR, Polar Signals, madsim) needs architecture changes such as injected time, I/O, and randomness. Agent-written code could be required to follow DST-friendly patterns from the start.

### Gaps
- No primary source found for madsim usage numbers or for FoundationDB's current simulation scale.
- No public Antithesis pricing found. No data found on DST adoption outside databases and infra (for example, web apps).
- TigerBeetle's CI fleet size and VOPR runtime were not stated in the 2026 post.

## 3. Record/replay and hermetic tests (rr, Pernosco, hermetic infra, service virtualization, Keploy/Speedscale, Testcontainers)

### Takeaway
Two families: execution recorders (rr, Pernosco) turn a flaky or failed CI run into a replayable trace, and traffic recorders (Keploy) turn real traffic into deterministic tests plus dependency mocks. Both cut the cost of nondeterminism and of external dependencies in CI.

### Cited Findings
- **rr**:
  - Records a Linux execution, including syscalls, signals, and thread scheduling, for exact replay.
  - `--chaos` randomizes scheduling and starves "victim" threads to expose races. — [rr chaos mode (O'Callahan)](https://robert.ocallahan.org/2016/02/introducing-rr-chaos-mode.html); [rr man page](https://linuxcommandlibrary.com/man/rr)
  - A CACM article describes the record/replay approach to catching failures. — [CACM 2020 "To Catch a Failure"](https://cacm.acm.org/magazines/2020/8/246364-to-catch-a-failure/abstract)
- **Pernosco + GitHub Actions**: setting `PERNOSCO_ENABLE: 1` on a workflow step makes Pernosco try to reproduce any failure under rr and attach a debugging session. `PERNOSCO_RR_RECORD_ARGS: --chaos` improves reproduction of flaky failures. — [Pernosco wiki: Debugging GitHub Actions failures](https://https-github_com.proxy.bugsmash.io/Pernosco/pernosco/wiki/Using-Pernosco-To-Debug-Github-Actions-Test-Failures)
- **Keploy**:
  - eBPF probes on socket syscalls (sendto/recvfrom/read/write) record live API traffic and dependency calls without code changes.
  - Decodes HTTP, Postgres wire protocol, MongoDB, Redis, gRPC, and Kafka into replayable tests and mocks.
  - Vendor claims ~1–3% recording overhead; runs locally, in CI, or on Kubernetes. — [Keploy docs](https://keploy.io/docs/concepts/what-is-keploy.md); [Keploy record-replay](https://keploy.io/record-replay-testing)
- **Google hermetic-testing context**: as of 2016, Google's monorepo held 86 TB, ~2B lines, and 9M files, with ~25,000 developers making ~16,000 changes/day plus ~24,000 automated commits/day. TAP runs tests across it. — [Potvin & Levenberg, CACM 2016 (PDF mirror)](https://edisciplinas.usp.br/pluginfile.php/7663796/mod_resource/content/2/ArtigoGoogleSingleRepositories.pdf); [Wikipedia: Piper](https://en.wikipedia.org/wiki/Piper_(source_control_system))

### Inferences
- With many agents, CI failure volume grows. Auto-capturing an rr/Pernosco trace (or a DST seed) on every failure gives the fixing agent a deterministic artifact instead of logs, which suits agent debugging.
- Traffic-recorded mocks make tests hermetic without hand-written doubles. That matters when agents change service boundaries faster than humans can update mocks. But recorded mocks go stale when the dependency's real behavior changes.

### Gaps
- No primary source fetched for Speedscale, Testcontainers adoption and latency, or Meta's hermetic test infra. These were not covered within the tool budget.
- No 2024–2026 public numbers found for Google TAP volume (tests/day, presubmit latency). The best public figures are the 2016 CACM numbers.
- No quantitative study found on rr/Pernosco reproduction rates for flaky CI failures.

## 4. Data/state branching and per-PR environments (Neon, Xata, PlanetScale, Dolt, CoW filesystems, Vercel, Signadot, Okteto, Uffizzi, Lyft)

### Takeaway
Two cheap isolation primitives now exist for stateful systems:
- **CoW database branching**: Neon branches in under a second regardless of size; Dolt adds diff and merge.
- **Request-level routing isolation**: Signadot and Lyft deploy only the changed services into a shared baseline and route by header. One vendor reports ~90% cost savings versus a full environment per PR.

Neither is perfect: a Columbia benchmark found no branchable database meets all agentic requirements.

### Cited Findings
- **Neon**:
  - Separates compute and storage. Branches are CoW over shared pages, so branching a 50 GB or a 1 GB database both take under a second.
  - Official GitHub Actions create a branch per PR and delete it on merge or close. — [Neon FAQ: fresh DB per PR](https://neon.com/faqs/postgres-services-github-actions-fresh-database-pull-requests); [Autonoma on Neon](https://getautonoma.com/blog/neon-database)
- **Neon acquisition** (secondary sources): Databricks bought Neon in May 2025 for ~$1B. Over 80% of databases provisioned on Neon were reportedly created by AI agents. — [Medium overview of Neon 2026](https://medium.com/@artikavate06/neon-postgres-in-2026-what-it-is-why-it-matters-and-whos-using-it-87f3cd94f3e3); [Autonoma](https://getautonoma.com/blog/neon-database)
- **Dolt**: SQL database with Git semantics (branch, diff, merge, push, pull). Added an MCP server in 2025, and since Nov 2025 has focused on "agents need branches" for changes to systems of record. — [DoltHub: Andy Pavlo agents need branches, 2026-01-12](https://www.dolthub.com/blog/2026-01-12-andy-pavlo-agents-need-branches)
- **BranchBench** (DAP Lab, Columbia; DoltHub write-up 2026-06-03):
  - Dolt branches much faster than Neon, and is the only system with first-class diff and merge.
  - Dolt's reads lag: typically 2–5x slower than Neon, with one query ~4,000x slower.
  - Conclusion: "No existing benchmarked offering meets all the requirements" for agentic workflows. This is DoltHub's own summary of third-party work. — [DoltHub BranchBench post](http://www.dolthub.com/blog/2026-06-03-branch-bench-database-benchmarking-for-agentic-workflows/)
- **Git4Data** (arXiv, Sept 2026): a research system for database-native version control for agents. Tables are versioned objects, with Git-style operations through SQL extensions. — [arXiv 2609.02106](https://arxiv.org/html/2609.02106v1)
- **Signadot**:
  - Sandboxes deploy only the changed services into an existing Kubernetes cluster and route requests by header through a service mesh. Unchanged services are shared.
  - Vendor cost model for 100 developers: ~$832K/yr for full per-PR namespaces versus ~$68K/yr for sandboxes (about 2 changed services each), a 92% reduction.
  - Customer claims (vendor-reported): Brex runs hundreds of pre-merge environments and saved ~$2M/yr. Bitso cut its change failure rate 83% while scaling with coding agents.
  - Signadot now markets "agent-native validation workflows" (Plans, Skills). — [Signadot guide](https://signadot.com/blog/a-comprehensive-guide-to-microservices-testing-environments-on-kubernetes); [Signadot vs other K8s testing](https://www.signadot.com/blog/why-signadot-outperforms-other-k8s-testing-solutions); [The New Stack](https://thenewstack.io/scale-microservices-testing-without-duplicating-environments/)
- **Lyft staging overrides** (launched 2021):
  - Each PR gets an "offloaded deployment" in shared staging that is not registered in service discovery. Routing-override metadata travels in request headers as protobuf-encoded OpenTracing baggage and is propagated across the mesh. An Envoy filter routes matching requests to the offloaded deployment.
  - Later work moved the override lookup to a central Envoy control plane keyed by a Context ID header. — [Lyft Eng Part 3](https://eng.lyft.com/scaling-productivity-on-microservices-at-lyft-part-3-extending-our-envoy-mesh-with-staging-fdaafafca82f); [Lyft control plane](https://eng.lyft.com/building-a-control-plane-for-lyfts-shared-development-environment-6a40266fcf5e); [InfoQ 2022](https://www.infoq.com/news/2022/03/scaling-testing-acceptance-lyft/)

### Inferences
- For many concurrent agent changes, request-routed sandboxes scale with the number of *changed services*, not the size of the system. That is what makes "an environment per agent change" affordable in microservices.
- Database CoW branches remove the shared-test-DB bottleneck and cross-test pollution. Dolt-style merge is the only option that lets an agent's *data* change (migrations, seed data) be reviewed and merged like code.
- Routing isolation does not isolate shared state such as databases and queues. Data isolation still needs DB branching or tenant-scoped data. These pieces stack rather than replace each other.

### Gaps
- No primary sources fetched for Xata, PlanetScale branching, Vercel previews, Okteto, or Uffizzi. Uffizzi's status (it reportedly wound down) is unverified.
- The Neon "80% agent-created" figure came only from secondary sources; no Neon or Databricks primary source was fetched.
- No primary data on CoW filesystems (ZFS, btrfs, overlayfs) for CI-scale cloning.

## 5. Source-control redesigns (Anthropic Scion, jj, Sapling/EdenFS/Mononoke, Pijul, Piper/CitC, VFS, semantic merge, agent-native VCS)

### Takeaway
Anthropic's Oct 13, 2026 post is the clearest data point. At 30,000+ merges/day, Git's offline-first design broke. Anthropic replaced it with Scion, a server-centric, content-addressed, changeset-log VCS with virtual sparse checkouts. Scion made CI checkouts 100x faster and cut infra footprint 200x. Anthropic dropped the global merge lock in favor of post-merge and pre-deploy testing plus agent conflict fixing. Elsewhere, two lines of work cut conflicts at high change rates:
- **First-class conflicts and patch commutation**: jj, Pijul.
- **Syntax-aware merging**: Mergiraf, Weave.

Both help with textual conflicts; neither solves semantic conflicts.

### Cited Findings — Anthropic "Redesigning source control" (2026-10-13)
All points in this subsection come from [Anthropic Engineering, "Redesigning source control"](https://www.anthropic.com/engineering/redesigning-source-control).
- **Authors**: Nick G. and the source control team.
- **Scale**:
  - Merges grew from ~2,500/day (May 2026) to 30,000+/day (Sept 2026), 12x in four months.
  - Main history is ~100 GB; compressed working copies exceed 25 GB.
  - CI does ~25M checkouts/day, which would be ">600 PB of git traffic per day" if fetched naively.
  - At peak Anthropic ran "several hundred internal git mirrors".
  - Quote: "source control became our biggest development bottleneck."
- **Diagnosis**: Git is decentralized and offline-first, but agents and CI jobs are always online.
- **Scion design principles**:
  1. Clients are always online.
  2. Client/server asymmetry: the server does history, merges, rebases, and blame.
  3. A full service API, so tools need no local repo.
  4. Horizontal scaling with no fully materialized copies (no packfiles, no repack/maintenance).
  5. Cheap, incremental, lock-free commits whose cost scales with change size.
  6. Optional sparse or virtualized working copies, plus writes via API without materializing files.
- **Data model**:
  - "Changesets" are write-ahead-log entries: deltas against the first parent, content-addressed pointers to compressed blobs, and ancestry and merge metadata.
  - This gives "no packfiles to accept, no locking or cross-server coordination, and no refs to move around."
  - Derived data (blame, path history, commit-graph skip lists) is computed from changesets, eagerly or lazily.
- **Fetch architecture**:
  - Three tiers: scion-daemon (node-local bounded cache, seeded from periodic snapshots), scion-cache (regional, in-memory), and scion-server (authoritative; Spanner or cloud storage).
  - Clients request specific immutable objects; sparse checkout simply never requests unwanted trees. There is no negotiation and no delta compression, and "any cache can answer it."
- **Results**:
  - Infra footprint is 200x smaller than the git mirrors (CPU and memory).
  - Cache hit rate is above 99% at each tier.
  - CI checkouts are 100x faster (seconds instead of minutes), freeing 25% of CI CPU capacity.
  - Claude rewrote the ingestion pipeline for 20x less memory and 4x more speed, and found an ancestry-query index optimization.
- **Effort**: 7 engineers over ~5 months (Jan–Sept 2026). They also built a code review tool ("Antique"), code search, and IAM. Claude "superfan" agents monitor each component.
- **CI implications**:
  - "A proper merge queue... doesn't make much sense at agent scale."
  - "What does CI even mean when hundreds or even thousands of changes can merge while tests are running?"
  - Anthropic dropped the global repository lock and invested in post-merge and pre-deploy automated testing. Concurrent changes can conflict, but "Claude can typically fix these conflicts faster than humans can even identify them."
  - The API makes "automated bisect and revert pipelines" practical.
- **Release and outlook**: Scion will not be released ("not a suitable replacement for git for general use"). Anthropic proposes Git ecosystem changes instead: new server architectures, standardized server-side RPCs across forges, and better negotiation plus sparse/shallow composition. It predicts this class of problem becomes common within 6–12 months.

### Cited Findings — other VCS work
- **Google Piper/CitC** (2016): Piper is built on Spanner. The repo was 86 TB, ~2B LOC, 9M files, with 16K human and 24K bot changes per day. CitC provides cloud-backed, overlay-style workspaces. — [CACM 2016 PDF mirror](https://edisciplinas.usp.br/pluginfile.php/7663796/mod_resource/content/2/ArtigoGoogleSingleRepositories.pdf); [Wikipedia: Piper](https://en.wikipedia.org/wiki/Piper_(source_control_system))
- **Meta Sapling** (open-sourced 2022-11-15):
  - Three parts: the Sapling client (Mercurial-derived), Mononoke (Rust server, built for "thousands of commits every hour across millions of files"), and EdenFS (a virtual filesystem that fetches lazily).
  - Serves Meta's repo of tens of millions of files, commits, and branches.
  - Sources: [Meta Engineering](https://engineering.fb.com/2022/11/15/open-source/sapling-source-control-scalable/); [Mononoke README](https://github.com/facebook/sapling/blob/main/eden/mononoke/README.md); [EdenFS overview](https://github.com/scramsby/sapling/blob/main/eden/fs/docs/Overview.md)
- **Jujutsu (jj)**:
  - Features: automatic working-copy commits, stable change IDs across rewrites, an operation log with undo, multiple workspaces, and "first-class conflicts" that live in commits and move through stacks.
  - Limits per the docs as of Sept 2026: no Git partial clone, worktrees, hooks, submodules, LFS, or .gitattributes.
  - A practitioner analysis (2026-07-22) argues jj "does not remove repository transfer". It recommends repo caches plus worktrees for repeated-download bottlenecks, and partial clone plus sparse checkout for path-bounded work. Semantic conflicts need task redesign, which no VCS can solve. — [wavect, 2026-07-22](https://wavect.io/blog/git-worktrees-vs-jujutsu-ai-coding-agents/)
- **Pijul**:
  - Based on a patch theory where independent changes commute. For any two changes, either they commute or one depends on the other.
  - Conflicts are the normal case, not a merge failure: they are stored in a conflict-tolerant "pristine" and computed after the fact. One resolution change fixes a conflict between two changes regardless of other concurrent changes. Conflicting changes commute in Pijul but not in Darcs. — [Why Pijul](https://pijul.org/manual/why_pijul); [Pijul manual](https://pijul.com/manual/print.html)
- **Mergiraf**:
  - Tries a line merge first and falls back to a tree-sitter CST plus GumTree matching. Supports 33 languages, Rust, GPLv3. Works as a Git merge driver and with jj. It removes move/edit conflicts.
  - On Linux kernel history it resolved 428 of 7,415 conflicted merges (~6%) fully, plus partial resolutions.
  - Known weaknesses: C macros, Rust `#[repr]` / derive ordering, doc comments. — [LWN, 2025-10-31](https://lwn.net/Articles/1042355)
  - MergirafSemi (arXiv 2608.11345) is a semistructured variant with a median of 44.7 ms versus 57.3 ms for Mergiraf. LastMerge (arXiv 2507.19687) is another language-agnostic structured merge tool. — [MergirafSemi](https://arxiv.org/pdf/2608.11345); [LastMerge](https://arxiv.org/pdf/2507.19687)
- **Weave (Ataraxy Labs, ~June 2026)**:
  - An entity-level semantic merge driver for Git and jj. It parses base, ours, and theirs with tree-sitter and matches entities (functions, classes, JSON keys) by name, type, and scope.
  - Includes a CRDT coordination crate and an MCP server whose ~14–15 tools let agents claim entities before editing, see who is touching what, and detect conflicts early.
  - Has a 31-scenario benchmark suite, but no head-to-head numbers were found.
  - Thesis: "Git's line-based merge model is the wrong unit of work for parallel coding agents." — [RuntimeWire, 2026-06-14](https://runtimewire.com/article/ataraxy-labs-weave-git-merge-driver); [Weave package](https://socket.dev/npm/package/@ataraxy-labs/weave); [HN thread](https://hn.nuxt.dev/item/47241976)
- **Agent-native VCS projects, 2026** (early stage, unverified claims):
  - Oak: virtual mounts instead of clones, a branch per agent session, server-side source of truth, export to Git. Its claims "need independent validation." — [Developers Digest, 2026-06-23](https://www.developersdigest.tech/blog/oak-agent-native-version-control)
  - AgentVC: local, MCP-native checkpoint, branch, and rollback of agent sessions underneath Git. — [GitHub nintechio/agentvc](https://github.com/nintechio/agentvc)
  - Git4Data: data versioning for agents. — [arXiv](https://arxiv.org/html/2609.02106v1)

### Inferences
- Agents hit the same VCS scaling walls Google and Meta hit (Piper/CitC, Mononoke/EdenFS), but in months instead of a decade. Server-side history and merge, virtual sparse checkouts, and content-addressed caches are the proven fix. Scion repeats that pattern and adds lock-free commits.
- For CI, the large win is not checkout speed alone. A server API (history, blame, merge, write-without-checkout) makes bisect, revert, and conflict-fix bots cheap, and that is what makes post-merge testing safe.
- How much conflict reduction is available:
  - Structural merge removes textual false conflicts, but only a modest share at kernel scale (~6% fully resolved by Mergiraf).
  - Entity claiming (Weave MCP) prevents conflicts *before* they happen, which may matter more for agent swarms.
  - First-class conflicts (jj, Pijul) stop conflicts from blocking: they can be committed, propagated, and fixed later by an agent. That fits Anthropic's "let agents fix conflicts after the fact" model.
- No VCS solves semantic conflicts, where two changes are each green but break together. These still need testing on the merged result, either speculative (section 6) or post-merge.

### Gaps
- No primary sources found for Google CitC or Piper updates after 2016, Microsoft's Git VFS/Scalar status, or 2025–2026 Mononoke throughput numbers.
- No primary source on SemanticMerge (Plastic SCM) or IntelliMerge results in this pass.
- Agent-native VCS startups: no funding, team, or benchmark data found for Oak. The list is likely incomplete.
- No quantitative evidence found on how often agent-generated parallel changes hit textual versus semantic conflicts.

## 6. Speculative execution of merges and "always-green main" at high commit rates (Google, Uber, Shopify)

### Takeaway
Classic always-green systems use speculative merge queues: they test predicted future states of main, batch, and use the build graph to find independent changes. They work at hundreds of changes per hour. Anthropic's 2026 experience at 30K+ merges/day suggests that serialized pre-merge gating breaks at agent scale. Testing then shifts to post-merge and pre-deploy, with automated bisect and revert.

### Cited Findings
- **Uber SubmitQueue/MergeQueue**:
  - Gates all landings to keep mainline green. It speculatively builds queued changes and lands only those whose CI passes.
  - Changes that touch no shared build targets are treated as independent and validated in parallel. — [Uber Eng: Bypassing large diffs in SubmitQueue](https://www.uber.com/en-AU/blog/bypassing-large-diffs-in-submitqueue/)
  - The ICSE-SEIP 2025 paper "CI at Scale: Lean, Green and Fast" adds a probabilistic success model and ML-predicted build times for prioritization. Across Go, iOS, and Android monorepos it cut CI resource use ~53%, CPU ~44%, and P95 wait ~37%. — [ICSE 2025 SEIP](https://conf.researchr.org/details/icse-2025/icse-2025-software-engineering-in-practice/4/CI-at-Scale-Lean-Green-and-Fast); [DevOps.com summary](https://devops.com/efficient-ci-at-scale-lessons-from-uber/)
  - The DPE Summit 2025 talk "Merge Queue at Uber Scale" cites "hundreds of changes per hour" and "thousands of engineers". — [DPE.org](https://dpe.org/sessions/dhruva-juloori/merge-queue-at-uber-scale/)
- **Shopify**: master must always be green so it is deployable. Shopify merged ~400 commits/day to its core monolith (at time of writing). The Shipit merge queue runs CI before merge, drops failing PRs, and controls batch size. Over 90% of core-app PRs used it. — [Shopify Eng: Successfully merging the work of 1000+ developers](https://shopify.engineering/successfully-merging-work-1000-developers); [Shopify Eng: Introducing the merge queue](https://shopify.engineering/introducing-the-merge-queue)
- **Merge-queue batching** is now a standard commercial feature (Graphite, Mergify, Harness). — [Graphite: merge queue batching](https://graphite.com/blog/merge-queue-batching); [Mergify docs: batches](https://docs.mergify.com/merge-queue/batches.md)
- **Google** (2016): 16K human plus 24K automated changes/day go through TAP on one trunk. — [CACM 2016 PDF](https://edisciplinas.usp.br/pluginfile.php/7663796/mod_resource/content/2/ArtigoGoogleSingleRepositories.pdf)
- **Anthropic** (2026): "A proper merge queue... doesn't make much sense at agent scale." Anthropic dropped the global repository lock for post-merge and pre-deploy testing and agent conflict fixing, enabled by API-driven bisect and revert. — [Anthropic, 2026-10-13](https://www.anthropic.com/engineering/redesigning-source-control)

### Inferences
- Rough throughput comparison: Shopify ~400/day, Uber hundreds/hour (thousands/day), Google ~40K/day with a mostly post-submit model. Anthropic's 30K+/day of agent merges is Google-scale volume, reached in months.
- The design shift: "keep main green pre-merge" becomes "keep *deploys* green." That means fast post-merge detection, culprit finding by automated bisect, automatic revert or fix, and pre-deploy gates.
- Speculation still helps but changes form. Instead of a linear queue of speculative builds, CI can:
  - use build-graph independence (Uber's target analysis) to avoid testing most combinations;
  - use cheap environment forks (section 1) to fan out speculative trees;
  - use DST seeds (section 2) and rr traces (section 3) so post-merge failures are reproducible and attributable without serializing merges.

### Gaps
- No primary 2024–2026 source on Google TAP's current presubmit/postsubmit split, culprit-finding latency, or green rate.
- No public data on how Anthropic measures main/deploy health or revert rates under the post-merge model; the article gives no numbers on this.
- The Shopify figures come from older posts; no 2024–2026 update found. GitHub merge queue scale numbers were not collected.
