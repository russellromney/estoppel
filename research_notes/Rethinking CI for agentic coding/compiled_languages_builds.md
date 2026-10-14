# Compiled-language builds in CI: where compile cost goes and how to avoid redundant compile/test work

Research date: 2026-10-13. Sources are dated where possible. Vendor benchmarks are flagged.

## 1. Where does compile time go in CI for Rust/C++/Scala/Swift/Go?

### Takeaway
Compile cost in CI comes from four structural sources. (1) Repeated parsing of the same interface text: C++ headers, and Rust/Scala generic and inline code that each downstream crate re-instantiates. (2) Code generation (LLVM) for monomorphized generics, much of which the linker throws away. (3) Serial links of many large binaries, especially one test binary per Rust integration-test file. (4) Coarse invalidation: a body-only change in a Rust crate rebuilds every reverse dependency. In Rust's own survey, incremental rebuilds were the top complaint. A quarter of CI users called CI build time a significant blocker, and a third of those used no caching at all.

### Cited Findings
**Rust: survey and user-level data**
- Rust Compiler Performance Survey 2025 (published 2025-09-10): >3,700 responses. Average satisfaction was 6/10. 55% wait >10 s for an incremental rebuild after a small change. 45% of people who stopped using Rust cited compile times. — [Rust blog, 2025-09-10](https://blog.rust-lang.org/2025/09/10/rust-compiler-performance-survey-2025-results)
- Same survey, on CI: 1,495 respondents build Rust in CI. 25% call CI build performance a significant blocker. 36% of those with CI concerns use no caching. 42% of all respondents have tried no build-performance mechanism. Dropping debug info to `line-tables-only` cut build time by 2–30%, and disabling it entirely cut more. About 60% rarely or never use a debugger. More than 35% report IDE and Cargo competing for the build lock. — [Rust blog](https://blog.rust-lang.org/2025/09/10/rust-compiler-performance-survey-2025-results)
- The most popular config-level fix was an alternative linker (mold, LLD). LLD was announced as the default for `x86_64-unknown-linux-gnu`. — [Rust blog](https://blog.rust-lang.org/2025/09/10/rust-compiler-performance-survey-2025-results)

**Rust: front end vs back end, parallelism**
- In a serial rustc profile from the 2023 parallel front-end post, the front end took 10.2 s and the back end (LLVM codegen) took 6.2 s. With the parallel front end these dropped to 5.9 s and 5.3 s. — [Rust blog, 2023-11-09](https://blog.rust-lang.org/2023/11/09/parallel-rustc/)
- The back end splits a crate into codegen units (CGUs) that LLVM processes in parallel (release builds default to 16). The main rustc thread still lowers each CGU to LLVM IR serially, which creates a bottleneck. — [Rust blog, 2023-11-09](https://blog.rust-lang.org/2023/11/09/parallel-rustc/)
- Cargo's crate-level parallelism falls off as builds approach the leaves of the crate graph. In the ripgrep example there were 60 rustc processes, with parallelism shrinking toward the end even with pipelined (metadata-first) compilation. — [Rust blog, 2023-11-09](https://blog.rust-lang.org/2023/11/09/parallel-rustc/)
- With `-Z threads=8`, the parallel front end cut compile time by up to 50% on real code, with gains larger for dev builds than release builds. It increased memory use by up to 35%. — [Rust blog, 2023-11-09](https://blog.rust-lang.org/2023/11/09/parallel-rustc/)
- Monomorphization creates a specialized copy of each generic function per concrete type. Reducing it shrinks the code that codegen and the linker must process. Recommended fixes include an inner non-generic function, avoiding heavy proc-macro crates, and finding expensive proc macros. — [corrode.dev, "Slow Rust Builds?"](https://corrode.dev/blog/tips-for-faster-rust-compile-times/)
- Rust library crates generate code for their whole API, even when users call only a few entry points, and the linker discards the rest. The nightly `-Zhint-mostly-unused` flag (2025) defers codegen to the crates that use the code. Measured on AWS SDK crates: aws-sdk-lambda release build went from 57 s to 40 s, and aws-sdk-rds from 1m34s to 49 s. — [Inside Rust blog, 2025-07-15](https://blog.rust-lang.org/inside-rust/2025/07/15/call-for-testing-hint-mostly-unused)
- Coarse cross-crate invalidation: changing a comment, reordering `use` lines, adding a `dbg!` in a non-inlinable function, or reformatting rebuilds every reverse dependency of the crate. In C/C++, the header/implementation split means only the changed translation unit rebuilds, followed by a relink. — [Rust project goal "Relink, don't rebuild", 2025H2](https://goals.rust-lang.org/2025h2/relink-dont-rebuild.html)

**C++: headers and templates**
- In Chromium, many headers are re-parsed more than 35,000 times per build. With modules this could drop to about 10. — [Chromium docs/modules.md](https://chromium.googlesource.com/chromium/src.git/+show/HEAD/docs/modules.md)
- Chromium experiments with Clang header modules for libc++ (`use_libcxx_modules`). This is not recommended for general use. Implicit modules break remote execution because the build system does not know about the cached PCMs. Compiling `base` alone produced 19 flag combinations × ~700 PCMs ≈ 13,483 PCM files. — [Chromium docs/modules.md](https://chromium.googlesource.com/chromium/src.git/+show/HEAD/docs/modules.md)
- Google's 2007 instrumentation of a major C++ binary found textual `#include` expansion inflated compiler input about 2000×. Go's export-data import model cut fanout to about 40×. Go compilers read only exported type info from the imported package's object file, and the language enforces an acyclic import graph. — [Rob Pike, "Go at Google" (2012)](https://go.dev/talks/2012/splash.article)

**Linking**
- Link times on big C++ binaries (mold's own suite, Aug 2026, Threadripper 7980X, debug builds): Chromium 145 took 16.64 s with lld, 3.98 s with wild, and 1.65 s with mold. Clang 21 took 6.19 s, 3.71 s, and 1.34 s. Mold claims a median 4.9× speedup over lld and 1.9× over wild. These are vendor benchmarks. — [mold README](https://github.com/rui314/mold)
- Wild's own earlier benchmark, on a warm build of an ~80 MB non-PIE static binary: wild 363 ms, mold 457 ms, lld 905 ms. This conflicts with mold's suite, and each vendor picks its own workloads. — [Phoronix on Wild](https://www.phoronix.com/news/Wild-Linker)

**Swift (Xcode 26)**
- Xcode 26 makes explicitly built modules the default for Swift targets. They are required for the new compilation cache. As of Sept 2025, SPM dependencies were not cacheable. Not cacheable at all: Ld (linking), storyboards/XIBs, asset catalogs, script phases, and dSYM generation. — [Bitrise Xcode compilation cache FAQ](https://docs.bitrise.io/en/bitrise-build-cache/build-cache-for-xcode/xcode-compilation-cache-faq); [Tuist blog, 2025-10-22](https://canary.tuist.dev/blog/2025/10/22/xcode-cache)

### Inferences
- The common cause is that interface and implementation are not separated at the unit the build system caches. C++ re-parses headers. Rust's crate metadata includes generic and inline bodies, and its crate hash changes on any edit. In Scala, macros and inference make signatures depend on bodies. Go is fast largely because it was designed with small export data and no textual includes.
- In CI on ephemeral runners, these costs repeat on every job unless an artifact cache survives. Rust's survey shows that most users do not have one, which is why CI pain exceeds local pain.
- Linking is the stage that does not parallelize or cache well. It also repeats per test binary (see section 5).

### Gaps
- I found no recent public per-phase breakdown (parse/typeck/borrowck/LLVM/link) for a large company Rust monorepo. The data here comes from rustc's own examples and benchmark suite.
- I found no current (2025–26) full-build time for Chromium or LLVM with and without modules. The Chromium doc gives only the parse-count figures.
- I did not find Scala 3 or Kotlin K2 per-phase breakdowns with numbers.

## 2. Incremental compilation and compilation avoidance techniques

### Takeaway
The techniques range from intra-compiler fine-grained memoization (rustc red-green queries, salsa, Zig analysis units with in-place binary patching, Zinc name hashing) to inter-unit ABI cutoffs (Kotlin/Gradle classpath snapshots, GHC ABI hashes, Bazel ijar/Turbine header jars, Rust "relink, don't rebuild"). The key concept is early cutoff: if a recomputed output's hash matches the previous one, stop propagating. The Rust 2026 roadmap aims to apply it at the crate boundary, targeting 5–10× faster rebuilds for body-only changes.

### Cited Findings
**rustc query system / red-green**
- rustc incremental compilation tracks a DAG of queries. On rebuild, "try-mark-green" walks a query's recorded dependencies in order. If all are green, the cached result is reused without re-execution. Results are stored as fingerprints, so if a re-executed query produces the same hash, it turns green and dependents are not re-run. This is early cutoff. — [rustc-dev-guide: incremental compilation](https://rustc-dev-guide.rust-lang.org/queries/incremental-compilation.html)
- Rust 2026 roadmap item: redesign the incremental system to allow "shared bases across different invocations" and extend coverage to phases before HIR, such as name resolution. — [Rust goals 2026: Fast Builds roadmap](https://goals.rust-lang.org/2026/roadmap-fast-builds.html)
- Relink-don't-rebuild (RDR): detect purely internal changes and invoke only the linker for downstream crates, "cutting rebuild times by 5-10x for common changes." It is implemented behind an unstable `-Z public-api-hash`, which currently hashes all items in metadata. It is listed as a 2026 goal alongside the Wild linker, which is meant to support incremental linking. — [Rust goals 2025H2 RDR](https://goals.rust-lang.org/2025h2/relink-dont-rebuild.html); [Fast Builds roadmap 2026](https://goals.rust-lang.org/2026/roadmap-fast-builds.html)

**Zig**
- Zig's self-hosted compiler models dependencies as "analysis units" and tracks four properties: layout, type, value, and body. It detects changes at the function level and patches the output binary in place instead of relinking, so incremental debug rebuilds take milliseconds. Zig was designed to make this easy. The design does not track dependencies on runtime function bodies, and comptime execution adds constraints. Source: summary of Matthew Lugg's "incremental compilation internals" post, dated 2026-07-28 by the aggregator. I could not fetch the original (HTTP 403). — [zeli.app summary](https://zeli.app/en/story/49085666); original: mlugg.co.uk/posts/incremental-compilation-internals/
- An earlier Zig claim: in-place patching gave incremental builds of about 0.5 ms in the proof-of-concept. An April 2026 devlog extended incremental compilation work to the LLVM backend. — [search summary of Zig devlog / Mitchell Hashimoto](https://mitchellh.com/writing/zig-builds-getting-faster) (secondary)

**Kotlin / Gradle / JVM**
- Kotlin 1.7.0 introduced classpath snapshots. Each module stores a snapshot of its compile classpath, and the compiler diffs successive snapshots to find ABI changes. Method bodies and private members do not affect the ABI. If no dependency ABI changed, Gradle marks the module UP-TO-DATE without invoking the compiler. ABI extraction is cached through artifact transforms. Enabled with `kotlin.incremental.useClasspathSnapshot=true`. JetBrains published a chart but no numbers in the text. — [JetBrains Kotlin blog, 2022-07](https://blog.jetbrains.com/kotlin/2022/07/a-new-approach-to-incremental-compilation-in-kotlin/); [Gradle blog: Compilation avoidance](https://blog.gradle.org/compilation-avoidance)
- Bazel Java: Turbine builds a header jar (hjar) without method bodies, skipping type inference. Dependents compile against the hjar as soon as it exists. ijar strips class files to interface jars, so body-only changes do not invalidate dependents' cache keys. rules_kotlin has an equivalent ABI-jar compile-avoidance mode. — [Bazel ijar/Turbine commits](https://bazel.googlesource.com/bazel/+/fd196bf03f4301cc3fbfc307570637f4de71c82c); [rules_kotlin CompileAvoidance.md](https://pigweed.googlesource.com/third_party/github/bazelbuild/rules_kotlin/+show/HEAD/CompileAvoidance.md)

**Scala Zinc**
- Zinc's name hashing (the default since sbt 0.13) hashes, per class, every member of each name. A dependent class recompiles only if a name it uses changed hash. Zinc 1.4.0 added module-level build pipelining, where downstream subprojects start once upstream signatures are ready. sbt 2.0 adopts a Bazel-compatible cache. — [Lightbend: Zinc and incremental compilation](https://www.lightbend.com/blog/zinc-and-incremental-compilation); [Zinc v1.4.0 release](https://github.com/sbt/zinc/releases/tag/v1.4.0); [VirtusLab, Zinc-friendly code](https://medium.com/virtuslab/zinc-sbt-friendly-code-bff0adc6b007)

**GHC**
- GHC keeps an ABI hash per module interface. A change is necessary but not sufficient for recompiling dependents. For home-package modules, GHC checks whether the specific used entities changed. For external packages, a whole-module ABI change triggers recompilation. — [ghc-devs, 2022-08](https://mail.haskell.org/pipermail/ghc-devs/2022-August/020896.html); [Tweag blog on GHC recompilation, 2022-11-03](https://tweag.io/blog/2022-11-03-blog_recompilation/)

**Swift**
- Xcode 26 compilation caching computes a hermetic fingerprint per build action. It keeps an action cache (key→outputs) plus a content-addressable store, and exposes a gRPC remote-cache contract. Tuist measured on M4 Pro with Xcode 26.0.1 (Oct 2025): Wikipedia app 24% faster with local cache and 18% with remote; Pocket Casts 36% / 20%; Tuist CLI 77% / 53%; Mastodon 55% / 69%. Tuist sells a remote cache, so treat these as vendor numbers. — [Tuist blog, 2025-10-22](https://canary.tuist.dev/blog/2025/10/22/xcode-cache)
- Swift forums report slow incremental builds dominated by "planning swift module" with explicit modules. — [Swift forums](https://forums.swift.org/t/slow-incremental-builds-because-of-planning-swift-module/84803)

**C++**
- Modules and precompiled headers attack the repeated parsing directly (see section 1). Chromium uses Clang header modules rather than C++20 named modules, because they have had large wins inside Google. Implicit-module caches do not work with remote execution. — [Chromium docs/modules.md](https://chromium.googlesource.com/chromium/src.git/+show/HEAD/docs/modules.md)

**Theory**
- "Build Systems à la Carte" (Mokhov, Mitchell, Peyton Jones; ICFP'18, JFP 2020) splits build systems into a scheduler and a rebuilder. It names the key axes: static vs dynamic dependencies, local vs cloud, determinism, early cutoff, and the persisted trace type (verifying traces vs constructive traces, which enable cloud builds that download results). — [Mokhov blog](https://blogs.ncl.ac.uk/andreymokhov/build-systems-a-la-carte); [JFP paper PDF](https://www.microsoft.com/en-us/research/uploads/prod/2020/04/build-systems-jfp.pdf)

### Inferences
- Every effective approach stops propagation at an interface hash. The variation is only in granularity: query (rustc), function or declaration (Zig, Unison), name (Zinc), class ABI (Kotlin, ijar), or module ABI (GHC, RDR).
- Intra-compiler incremental state (rustc's `target/incremental`, Zig's cache) is local and path-sensitive. It does not help an ephemeral CI runner unless the state is restored, and it is not designed to be shared. ABI-level cutoffs work naturally with content-addressed remote caches because they shrink the cache key.
- The 2026 goal of "shared bases across invocations" in rustc points toward incremental state that many branches or agents could share. It is a roadmap item, not shipped.

### Gaps
- I could not verify Zig's current rebuild numbers on large real projects (e.g., Ghostty, the Zig compiler) from a primary source. The original mlugg post returned 403.
- I found no published RDR benchmark beyond the "5–10×" target.
- I found no numeric Kotlin/Gradle compile-avoidance results in the primary source.

## 3. Splitting crates and modules, interface/implementation separation, and hermetic caching

### Takeaway
Splitting code into many smaller units increases parallelism and cache hit rates, but only if dependents depend on a stable interface artifact (rmeta, hjar, ABI jar, .swiftmodule, header). Otherwise a leaf edit still cascades. Hermetic content-addressed caching (Bazel RBE, Xcode CAS, sbt 2) is where the large CI wins come from. Cargo's timestamp-based fingerprints and sccache's per-rustc-invocation caching often disappoint in CI.

### Cited Findings
- DFINITY (Internet Computer, ~600k lines of Rust, a few hundred packages, 2023): Cargo's cache was invalidated by timestamps, so comment edits or branch switches caused long rebuilds. Cargo cannot know which files tests read, so test caching must be conservative. sccache "saw no improvement" on CI. They moved to Bazel for sandboxing, remote caching, and distributed builds. — [mmapped.blog, "Scaling Rust builds with Bazel", 2023-03-20](https://mmapped.blog/posts/17-scaling-rust-builds-with-bazel)
- RustConf 2026 talk: a Rust monorepo with multiple workspaces cut CI from >2 h to <10 min using Bazel Remote Build Execution on self-hosted bare metal (Foresight Spatial Labs). I have only the abstract and no details. — [RustConf 2026 schedule](https://rustconf2026.sched.com/event/2KHtn/2-hours-to-10-minutes-building-rust-monorepos-at-scale-with-bazel-rbe)
- Canva reported 5–6× lower average CI build times after migrating to Bazel (search-summary claim, primary not fetched). — [Bazel users page](https://bazel.build/versions/7.7.1/community/users.md)
- Cargo pipelined compilation lets a dependent crate start once the upstream crate's metadata (rmeta) is emitted, without waiting for codegen. Parallelism still falls off at the end of a build (ripgrep example). — [Rust blog, 2023-11-09](https://blog.rust-lang.org/2023/11/09/parallel-rustc/)
- Rust's lack of a header/impl split means body-only edits rebuild reverse dependencies. RDR is the planned fix. — [Rust goals RDR](https://goals.rust-lang.org/2025h2/relink-dont-rebuild.html)
- Bazel Java/Kotlin: dependents compile against header/ABI jars, so they rebuild only on interface change. Turbine also passes enough transitive information that compiles can use direct dependencies only. — [Bazel Turbine commit](https://bazel.googlesource.com/bazel/+/fd196bf03f4301cc3fbfc307570637f4de71c82c); [rules_kotlin CompileAvoidance](https://pigweed.googlesource.com/third_party/github/bazelbuild/rules_kotlin/+show/HEAD/CompileAvoidance.md)
- Feature flags multiply the Rust build matrix, and `--all-features` can add an order of magnitude of compile work. Agents without guidance trigger full workspace rebuilds. Practitioner blog, 2026-03-31. — [Codex CLI for Rust teams](https://codex.danielvaughan.com/2026/03/31/codex-cli-rust-teams/)

### Inferences
- Costs of over-splitting (general engineering knowledge, not from a fetched source with numbers): more units mean more per-unit fixed overhead (rustc startup, metadata decode, extra rmeta and link steps), lost cross-crate inlining unless generics or `#[inline]` are used (which re-couples crates), and more test binaries to link (section 5). Splitting pays off when the split lines match the interface boundaries that change rarely.
- sccache's weak CI results are consistent with its design. It caches whole rustc invocations keyed on inputs that include paths, environment, and flags. Any non-hermeticity, and incremental mode (which sccache does not cache), lowers hit rates. Bazel's sandboxed, content-addressed actions fix this, at the cost of migrating off Cargo.

### Gaps
- I found no quantitative study of the optimal crate count or crate size versus CI time for Rust. Over-splitting costs above are not backed by a fetched numeric source.
- I found no primary-source numbers for Canva or other Bazel migrations in this session.

## 4. Content-addressed and fine-grained code, faster backends, hot patching, and linkers

### Takeaway
At the radical end, Unison content-addresses every definition. Compiled and typechecked results, and even pure test results, are cached forever and shared, so "no builds" exist. More practical options: faster debug backends (Cranelift today at about 5–15% end-to-end, TPDE claimed 10–20× faster than LLVM -O0), runtime hot patching (Dioxus subsecond, Zig in-place patching, Live++ for C++), and fast linkers (mold, wild).

### Cited Findings
- Unison identifies each definition by a SHA3-512 hash of its syntax tree and stores code as ASTs in a database. Parse and typecheck results are cached and never invalidated, and the cache is part of the codebase format, so once anyone has typechecked a definition no one does it again. Test results for pure code are cached too, so a deterministic test is not rerun if its dependencies are unchanged. Unison 1.0 shipped on 2025-11-25. — [Unison docs: The Big Idea](https://unison-lang.org/docs/the-big-idea); [byteiota on Unison 1.0](https://byteiota.com/unison-1-0-content-addressed-code-hits-production/)
- Cranelift backend for rustc (rustup component `rustc-codegen-cranelift-preview` on nightly). As of Feb 2026: Zed incremental builds with `line-tables-only` are 12% faster than LLVM. Single-crate speedups in the rustc suite range from negligible to ~30% (average 10–15%). On large projects (Zed, Tauri, hickory-dns), codegen time drops about 20%, which is only about 5% of total clean-build time. The 2026 goal targets 2× inside the backend, with $65k of funding. — [Rust goals 2026: improve cg_clif performance](https://goals.rust-lang.org/2026/improve-cg_clif-performance.html); [Fast Builds roadmap](https://goals.rust-lang.org/2026/roadmap-fast-builds.html)
- TPDE backend: the Rust 2026 roadmap says it compiles 10–20× faster than LLVM -O0 with similar code quality. It is experimental and its funding is TBD. — [Fast Builds roadmap 2026](https://goals.rust-lang.org/2026/roadmap-fast-builds.html)
- Dioxus subsecond (Dioxus 0.7, 2025): recompiles only the changed functions into a patch dylib, loads it into the running process, and redirects calls through a jump table, so state survives without a restart. Uses "ThinLinking" to speed dev builds. Works on web/WASM, desktop, iOS, and Android. Experimental, opt-in with `dx serve --hotpatch`. — [Dioxus 0.7 release](https://dioxuslabs.com/blog/release-070); [subsecond docs.rs](https://docs.rs/subsecond/)
- Linkers: see section 1 (mold 1.65 s vs lld 16.64 s on Chromium debug, a vendor benchmark). Wild aims to add incremental linking and is part of Rust's RDR plan. — [mold README](https://github.com/rui314/mold); [Fast Builds roadmap](https://goals.rust-lang.org/2026/roadmap-fast-builds.html)
- Zed proposed (RFC #37717) recommending and enabling Wild instead of mold on Linux for local builds. — [Zed commit mirror](https://git.secluded.site/zed/commit/10b99c6f55929a9f4a668fc4e81902b917e1c48a)
- Nix/Bazel content addressing: constructive traces (store the output keyed by input hashes) are what make cloud and shared caches possible, per Build Systems à la Carte. — [Mokhov et al., JFP 2020](https://www.microsoft.com/en-us/research/uploads/prod/2020/04/build-systems-jfp.pdf)

### Inferences
- Cranelift's numbers show the backend is not the main cost for many large Rust builds. Front end, metadata, and link time dominate, which is why RDR, the parallel front end, and linkers get roadmap priority.
- Hot patching (subsecond, Zig, Live++) targets the inner dev loop, not CI. CI produces fresh artifacts and must test them. For CI, the useful ideas from this space are function-level dependency tracking and content-addressed result caching (Unison-style test-result caching).
- Unison is the existence proof that "never compile the same definition twice, across all users" and "never re-run a pure test whose dependency hashes are unchanged" are achievable. Doing it requires abandoning file-and-name-based code identity.

### Gaps
- I did not fetch a primary source on Live++ (C++ hot reload) numbers, persistent compiler daemons (e.g., Gradle/Kotlin daemon, Bloop for Scala), or salsa internals in this session.
- I found no published CI-level measurement of Unison's shared cache.

## 5. Test binaries in compiled languages: nextest, linking many test binaries, sharding, test-impact analysis

### Takeaway
In Rust, each integration-test file is its own binary that links the whole library again. This multiplies link cost and serializes execution under `cargo test`. Merging tests into one binary (Cargo saw 3× faster test compilation and 5× smaller artifacts) and running with nextest (process per test, cross-binary parallelism, 1.4–3.4× faster runs in its own benchmarks) are the standard fixes. Coverage-based test selection for Rust and C++ exists (cargo-difftests, Ratchet) but is niche.

### Cited Findings
- Each file in `tests/` compiles to a separate binary that re-links the library, and `cargo test` runs binaries sequentially. When Cargo itself consolidated its integration tests into one crate, test-suite compile time fell 3× and on-disk artifacts shrank 5×. One of the author's projects went from 20 s to 13 s for the test run. — [matklad, "Delete Cargo Integration Tests", 2021-02-27](https://matklad.github.io/2021/02/27/delete-cargo-integration-tests.html)
- cargo-nextest runs each test in its own process and runs tests from many binaries in parallel. Its own benchmarks (Ryzen 9 7950X): omicron 444 s → 202 s (2.19×), meilisearch 57 s → 29 s (1.96×), tokio 24.3 s → 11.6 s (2.09×), crucible 3.38×, penumbra 1.37×, ring 1.39×. Note: the page lists the test date as 2026-07-09 but the toolchain as Rust 1.66.0 (Dec 2022), so the date is probably a page-build artifact and the numbers are older. — [nexte.st benchmarks](https://nexte.st/book/benchmarks)
- Nextest caveat: it lets straggling tests finish after a failure. In trees with fast unit tests and slow integration tests it can be slower than `cargo test`. When sccache or a Rust cache cuts compile time, test execution becomes a bigger share of end-to-end time. — [search summary of nexte.st "how it works"](https://nexte.st/book/how-it-works.html) (secondary summary)
- cargo-difftests uses LLVM coverage plus a diff since the last run to select affected Rust tests. cargo-impact layers confidence tiers on top. Ratchet (UT Austin, 2011) combined C++ static analysis and coverage for test selection. — [cargo-difftests](https://github.com/dnbln/cargo-difftests); [cargo-impact](https://awesome.ecosyste.ms/projects/github.com%2Fasmuelle%2Fcargo-impact); [Ratchet thesis](https://tdl-ir.tdl.org/handle/2152/ETD-UT-2011-05-3306)
- Datadog's Intelligent Test Runner maps each test to the files it touches using per-test coverage, then skips tests whose files did not change. — [Datadog docs](https://docs.datadoghq.com/intelligent_test_runner/how_it_works)
- Bazel test caching: because tests are hermetic actions with declared inputs, unchanged test targets are cache hits. Cargo cannot do this because it does not know what files tests read. — [mmapped.blog, 2023](https://mmapped.blog/posts/17-scaling-rust-builds-with-bazel)

### Inferences
- In compiled languages, the expensive part of "testing" is often building and linking the test binaries, not running them. Test-impact analysis that only skips execution saves less than in interpreted languages unless it also skips building the binaries.
- Coverage-based selection for Rust and C++ is harder because of inlining and monomorphization. Generic code shows up in coverage attributed to the instantiating crate. Rust coverage instrumentation also changes codegen, so a separate instrumented build is needed. (This inference is not from a fetched source.)
- For CI sharding: nextest's archive feature builds once and partitions tests across machines. Its process-per-test model makes the shards independent. (Feature known from nextest docs, not fetched this session.)

### Gaps
- I found no published numbers on test-impact-analysis savings for Rust or C++ codebases.
- I found no recent (2025–26) data on total link time across test binaries in large workspaces.

## 6. 2025–2026 efforts: finer-grained incrementality and sharing compile work across branches and agents

### Takeaway
Three tracks are active. (1) Compilers are moving toward finer and sharable incremental state: rustc's 2026 goals of shared incremental bases and RDR, and Zig's function-level incremental compilation with in-place patching. (2) Build caches are standardizing on CAS plus action cache with remote protocols: Xcode 26 gRPC CAS, sbt 2 Bazel-compatible cache, the Bazel REAPI ecosystem. (3) Vendors are pitching remote execution and shared caches for AI agents: BuildBuddy remote Bazel runners with warm snapshots (Mar 2026), Turborepo agent-aware caching (2026), and BuildFetch. I found no compiler that serves many concurrent branches as a shared persistent incremental service.

### Cited Findings
- Rust 2026 Fast Builds roadmap: stabilize the parallel front end, RDR (5–10× for body-only changes), Cranelift speedups, the experimental TPDE backend, the Wild linker for incremental linking, an incremental redesign for "shared bases across different invocations", and profile-driven fixes for trait resolution and type checking (2026–27). — [Rust goals 2026: Fast Builds](https://goals.rust-lang.org/2026/roadmap-fast-builds.html)
- BuildBuddy, 2026-03-02, "Remote Bazel with agents". Problems for agents: Bazel resource demands in constrained sandboxes; the analysis cache resetting between tasks on ephemeral runners; workspace locks blocking parallel builds; and RBE network latency as the main bottleneck. Their fix: remote runners colocated with cache and RBE servers (sub-ms latency), which mirror local git state including uncommitted changes. The runners are snapshotted and cloned after each build to keep the analysis cache warm. A cold restore takes "several minutes". — [BuildBuddy blog, 2026-03-02](https://www.buildbuddy.io/blog/remote-bazel-with-agents/)
- A vendor guide claims that without remote execution, 50 parallel agents doing fresh builds cost 50× the CPU and compile work, while with a shared cache, CI-populated entries serve everyone. This is a reasoning claim, not a measurement. — [VirtusLab Visdom guide: Remote execution (EngFlow)](https://visdom-maturity-matrix.virtuslab.com/guides/infrastructure/remote-execution-engflow)
- Turborepo 2.8/2.9 (2026) added agent-oriented features: shared worktree caches and scoped builds. Source is a practitioner blog. — [danielvaughan.com, 2026-04-12](https://codex.danielvaughan.com/2026/04/12/codex-cli-turborepo-agent-aware-builds/)
- BuildFetch Cache (2026) is compatible with Gradle and Bazel, with ccache/sccache/Go support "rolling out". This is a launch claim. — [search result: BuildFetch launch via LinkedIn](https://cy.linkedin.com/in/d-valuev)
- Xcode 26 (2025): content-addressed compilation cache with a gRPC remote-cache contract, so CI and developer machines can share Swift/Clang compile outputs. — [Tuist blog, 2025-10-22](https://canary.tuist.dev/blog/2025/10/22/xcode-cache)
- sbt 2.0 uses a Bazel-compatible cache. — [Zinc index / sbt 2 summary](https://index-dev.scala-lang.org/sbt/zinc)
- Rust survey: more than 35% hit IDE (rust-analyzer) vs Cargo build-lock contention. This is the same problem agents face when several processes share one `target/` dir. — [Rust blog, 2025-09-10](https://blog.rust-lang.org/2025/09/10/rust-compiler-performance-survey-2025-results)

### Inferences
- For many concurrent agent branches, the reusable layer today is the content-addressed action cache, which works per crate, per translation unit, or per class. Fine-grained in-compiler incremental state (rustc queries, Zig analysis units) is still per-workspace and per-path. The 2026 "shared bases" goal is the first rustc step toward sharing it.
- Agents' small, frequent edits are exactly the case RDR and ABI-based cutoffs help. Many agent edits change only function bodies, so with RDR plus an incremental linker (Wild), most downstream crates would be cache hits plus a relink.
- Persistent warm build servers (BuildBuddy snapshots, Gradle daemon, Bazel server) matter for agents because analysis and graph loading costs repeat on every ephemeral sandbox.

### Gaps
- I found no public "compiler-as-a-service" in production that holds persistent rustc or Swift incremental state shared across many branches or agents. Nor did I find rust-analyzer-style persistent servers used for CI builds.
- I found no measurements of cache hit rates across parallel agent sandboxes. Vendor claims are qualitative.
- I found no evidence of GHC, Kotlin, or Scala compiler teams publishing agent-specific incrementality work in 2025–26.
