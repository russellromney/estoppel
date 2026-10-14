# Scenario, step 2: Z, combined with X+Y

Run on 2026-10-14. This is the plan's step 5 ([Prototype plan](../../../reports/Prototype%20plan.md), section 5). The predictions are in [`../PREDICTIONS.md`](../PREDICTIONS.md), section 5. They were committed in `e3d6eb2`, before any Z change was written, and are not edited here. Step 1 (X and Y) is in [`RESULTS.md`](RESULTS.md).

- Z is `coupons`: one code, `SAVE10`, takes 10% off. At most 3 redemptions are live at once, shared across customers. An expired order returns its redemption.
- Z's author does not know about X (`b2g1`). Whether the coupon applies before or after `b2g1` is the interaction.
- Z crosses arm B's core: the core had no budgets.

[`run.py`](run.py) replays X, Y and Z in both arms, in throwaway git worktrees, with the commands an agent runs. The changes and the two conflict resolutions are in [`changes/`](changes/). I wrote them from the requirements; no agent was run. Raw results:
- [`results/run.json`](results/run.json): every command, with exit code, checks run, tiers and CPU time;
- [`results/run-summary.md`](results/run-summary.md): the same, as a table, with lines changed and the files git could not merge;
- [`results/run-logs/`](results/run-logs/): each command's output;
- [`results/combine-b-xy.json`](results/combine-b-xy.json), [`results/combine-b-z-stop.json`](results/combine-b-z-stop.json) and [`results/combine-b-z.json`](results/combine-b-z.json): `estoppel combine`'s reports.

The base is `d15e842`: the X+Y base, renamed to estoppel, plus `combine --resolved` (`565f4a8`) and a fix found during this run (see "Fixes made during the run"). X and Y were replayed from it. The local branches `scn/a-*` and `scn/b-*` now hold this replay.

## Summary

- **X+Y replayed from the new base gives the same counts as step 1.** In arm A, testmon reran 323, 342 and 357 checks. In arm B, estoppel's combine kept 447 and rechecked 6.
- **Arm A + testmon reran 97.9% of the suite's check time for Z,** and 100% at the combine, with either testmon database.
- **Crossing arm B's core cost what was predicted.** Z's core commit reran 97.4% of the check time under estoppel: all T2, T3 and T4. Its other three commits reran 0.1 to 2.5%, with no T2 or T3.
- **`estoppel combine` stopped at `RULES`, and at nothing else, as predicted.** Both sides had added a rule to the same tuple. The real interaction, the order of stages, appeared only as a note after the stop: `STAGES`, changed by Z, is used by 51 claims made on the X+Y side.
- **After the joint decision, `combine --resolved` rechecked 55 and kept 431,** with no T2 or T3. 391 of the kept claims were made on Z's branch, including all the core simulation checks. On the same tree, testmon with main's database reran 444 checks, 100% of the check time.
- **testmon with Z's database reran 41 checks, as little as estoppel.** This meets a condition for changing the plan: a well-chosen testmon database gets the same reuse here. But the 41 left out 19 checks that use the merged `RULES` value, which testmon cannot see.
- **The stacking decision was written down in arm B and nowhere in arm A.** Both arms price three A with `SAVE10` at 1800 (after `b2g1`, not 1700). No check in either arm, or in the acceptance suite, fixes that number.
- **estoppel's own overhead is now as large as a full run.** The combine took 7.1 s of CPU over its two invocations. Arm B's whole suite takes 7.3 s of CPU without any tool. Its checks took 0.21 s.

## The commands

| Who | Arm A | Arm B |
|---|---|---|
| Agent, per commit | `uv run pytest --testmon -q`<br>`git add -A && git commit -m "..."` | `uv run python ../estoppel gate --kind K`<br>`git add -A && git commit -m "..." -m "Estoppel-Kind: K"` |
| Integrator | `git merge --no-edit scn/a-z` (exit 1: conflicts)<br>resolve<br>`git add -A && git commit --no-edit`<br>`uv run pytest --testmon -q` | `uv run python ../estoppel combine scn/b-z` (exit 3: stop)<br>`git merge --no-commit scn/b-z` (exit 1: conflicts)<br>resolve<br>`git add -A`<br>`uv run python ../estoppel combine scn/b-z --resolved --decision "..."` |

In arm A, Z is one commit. In arm B, Z is four: a core `modify`, a periphery `modify`, a `publish` of the rule, and an `activate` of it in a new `order` stage. Both integrators run from the X+Y integration branch.

`estoppel combine`'s first output, shortened:

```
combine scn/b-z into scn/b-int (base d15e842)
declared kinds:
  scn/b-int c99d62b publish: ok (16 definitions added)
  scn/b-int 8b9d04c activate: ok (4 definitions added; bindings ...rules/__init__.py::RULES, ...)
  scn/b-int 94d9e04 publish: ok (11 definitions added; bindings config.py::CATEGORIES, ...)
  scn/b-int 70d4e18 modify: ok (5 definitions added; 2 code definitions changed)
  scn/b-z f1a6e10 modify: ok (8 definitions added; 8 code definitions changed; 10 checks changed)
  scn/b-z ecbc8fd modify: ok (31 definitions added; bindings config.py::COUPONS; 5 code definitions changed; 2 checks changed)
  scn/b-z f45239f publish: ok (22 definitions added)
  scn/b-z 7759dd8 activate: ok (5 definitions added; bindings composition.py::STAGES, rules/__init__.py::RULES, ...; 1 checks changed)
Stopped: these definitions were changed differently by more than one side. Each needs a joint decision:
  checkout/app/pricing/rules/__init__.py::RULES (binding): scn/b-int, scn/b-z
Merge the branches with git, resolve these definitions, stage the result, then rerun with --resolved --decision TEXT.
```

git then conflicted in `config.py` and `rules/__init__.py`. estoppel did not name `config.py`: there, the two sides added different definitions, which is not a joint decision. The resolution keeps both sides in both files, so `RULES = (B2G1, SAVE10)`.

The second output, shortened:

```
merge: resolved by hand; decision: Keep both rules. SAVE10 is in the order stage, which runs after the
  item stage, so it takes 10% off the price after b2g1's free units: three A with SAVE10 cost 1800, not
  1700. Agreed for X (b2g1) and Z (coupons).
claims kept: 431 (40 made on base, 391 made on scn/b-z)
to recheck: 55
    44 use checkout/app/pricing/rules/__init__.py::RULES, changed by scn/b-int, scn/b-z
    42 use checkout/app/pricing/composition.py::STAGES, changed by scn/b-z
    33 use checkout/app/pricing/types.py::Context, changed by scn/b-z
    23 use checkout/core/facts.py::Order, changed by scn/b-z
    ... (16 more definitions)
     9 use checkout/app/policies.py::refund_window_open, changed by scn/b-int
  note: binding checkout/app/pricing/composition.py::STAGES, changed by scn/b-z, is used by 51 claims made on another side
  note: binding checkout/app/pricing/rules/__init__.py::RULES, changed by scn/b-int, is used by 71 claims made on another side
  note: binding checkout/app/pricing/rules/__init__.py::RULES, changed by scn/b-z, is used by 51 claims made on another side
lint: ok
checks: 431 kept by valid claims; 55 ran; 0 failed
committed f1b8580
```

The merge commit's message holds the decision, under "Joint decision on `checkout/app/pricing/rules/__init__.py::RULES`".

## What reran

"Existing" means a check that exists at the base: 374 in arm A and 435 in arm B. "Share" is the rerun checks' share of the full suite's check time, timed by the audit run without tracing.

| Step | A + testmon | B + testmon | B + estoppel |
|---|---|---|---|
| Z (core `modify` in B) | 388 ran: T1 37, T2 41, T3 301, T4 9. Share 97.9% | 392 ran: T1 36, T2 46, T3 302, T4 8. Share 99.9% | 388 ran (382 existing, 6 new): T1 32, T2 46, T3 302, T4 8; 53 kept. Share 97.4% |
| Periphery `modify` | (one commit in arm A) | 46 ran, no T2 or T3 | 58 ran (45 existing, 13 new): T1 50, T4 8; 396 kept. Share 2.5% |
| `publish` | | 12 ran, all new | 12 ran, all new; 454 kept. Share 0.1% |
| `activate` | | 6 ran: T1 4, T4 2 | 33 ran (22 existing, 11 new): T1 23, T4 10; 435 kept. Share 2.5% |
| Combine, main's data | 395 ran: T3 301. Share 100% | 444 ran: T1 83, T2 46, T3 302, T4 13. Share 100% | 55 ran: T1 42, T4 13; 431 kept. Share 2.6% |
| Combine, Z's data | 368 ran: T3 301. Share 100% | 41 ran: T1 28, T4 13. Share 0.1% | — |

**CPU per command** (one run; repeated runs varied by about 20%):

| Command | CPU s |
|---|---|
| Arm A, `pytest --testmon`, Z and its combine | 10.3 to 10.4 |
| Arm A, full suite without testmon | 4.3 |
| Arm B, Z's core commit: `estoppel gate` / `pytest --testmon` | 8.2 / 18.0 |
| Arm B, Z's other commits: `estoppel gate` / `pytest --testmon` | 1.2 to 1.3 / 0.5 to 0.8 |
| Arm B, `estoppel combine`: the stop, then `--resolved` | 2.75 + 4.36 |
| Arm B, combine: `pytest --testmon` with main's data / Z's data | 18.3 / 0.7 |
| Arm B, full suite without either | 7.3 |

On the core commit, estoppel's gate took less than half of testmon's CPU while running about the same checks. estoppel records footprints per definition with `sys.monitoring`. testmon traces every line, which makes each check about 2.5 times slower. On every cheap step, estoppel's fixed cost (the lint, the kind check and the definition indexes) is larger than the check time it saves.

**Why each estoppel step reran what it did:**
- **Core `modify`, 382 existing:** every check whose footprint includes a changed core definition (`Order`, `Snapshot`, `OpenOrder`, `State`, `_check_open`, `_open`, `_release` or `Runtime`). That is all 40 T2, all 302 T3 and all 8 T4. Of the 85 T1, the 32 that build core facts reran: workflows 22, status 7, policies 3. The 53 pricing and rule checks never touch the core, so they were kept. The 6 new checks are the budget tests.
- **Periphery `modify`, 45 existing:** the checks that use `Context`, the place-order workflow, `CheckoutService`, `build` or the conftest's `order_fact`: workflows 22, pricing 9, journeys 8, composition 3, policies 3.
- **`activate`, 22 existing:** the checks that use `RULES` or `STAGES`: pricing 9, journeys 8, composition 4, workflows 1. 7 of `SAVE10`'s own rule checks also reran. They pass their rules explicitly, but `quote`'s default argument `rules=RULES` puts `RULES` in every caller's footprint. Step 1 found the same with `b2g1`.
- **The combine, 55:** every claim from either side that was made against the other side's old version of something. None of the 55 is T2 or T3. The core checks have only one valid claim, made on Z's branch, because X+Y did not touch the core.

**Why no claim from the X+Y side was kept.** The 431 kept claims were made on the base (40) and on Z's branch (391), none on X+Y's. Every check X+Y added or reran uses something Z changed: `Context`, `order_fact`, `RULES` or `STAGES`. So all 18 checks that X and Y added were rechecked.

**Why testmon reran what it did.**
- **With main's data, 444.** That database has never run against Z's core, so every check that touches the core changed.
- **With Z's data, 41.** It has run against Z's core, but not against X's and Y's changes. 14 checks differ from estoppel's 55:

  | | Checks | Why |
  |---|---|---|
  | estoppel only | 19: pricing 9, `SAVE10` rule checks 7, composition 3 | They use the merged `RULES`. `rules/__init__.py` holds only values, so no line of it runs during a check, and testmon never links the check to it. |
  | testmon only | 5: workflows 4, policies 1 | They run `hold_until` or `hold_lapsed` in `policies.py`. Y changed that file, but not those functions. |

  The 3 composition checks include `test_every_rule_uses_a_declared_stage`. It checks the merged registry against the stages, which is exactly what the combine changed.

## The interaction: surfaced, or left silent

| | Arm A | Arm B |
|---|---|---|
| What stopped the combine | git: textual conflicts in `config.py`, `pricing.py` and `test_pricing.py`. X changed `order_total`; Z added `apply_coupon` next to it. | estoppel: `RULES`, which both sides changed. Then git, in `config.py` and `rules/__init__.py`. |
| Where the stacking order lives | `service.py`: `apply_coupon(order_total(...))`. Z wrote this without knowing about `b2g1`. It merged cleanly. | `STAGES`: the `order` stage, Z's own decision, after `item`. Named in a note after the stop, not in the stop. |
| Where the decision is recorded | Nowhere | The combine's commit message |
| A check that fixes 1800 | None | None |

In both arms, the stop came from two changes editing the same place. That is the same signal as a textual conflict. Any two rule activations would stop at `RULES` in arm B, whether or not they interact. The decision text says the right thing because I wrote it, knowing the interaction. The tool requires a decision but cannot judge its content. A fresh agent resolving `RULES` might write only "keep both rules".

The note on `STAGES` is the true signal, but it is not distinguished from noise. At X+Y's combine, the same kind of note said that `RULES`, changed by X, is used by 5 claims made on Y's branch, and those changes do not interact. Both notes have the same shape: a binding changed by one side, in the footprint of the other side's claims. The rule the plan suggests, stopping at "a binding that one side changed and the other side's claims use", would also have stopped X+Y. Footprints alone cannot separate the two cases.

The recheck passed because no check exercises both features: X's checks have no coupon, and Z's checks buy at most 2 units of a SKU. The acceptance oracle also avoids such carts. So the interaction lies in a region of inputs that no check covers, in either arm.

## Probes: edits that change only a value

These ran on the combined tree after the audit, with testmon's database from the combine. Each edit was then undone.

| Probe | Edit | Full suite | testmon | estoppel |
|---|---|---|---|---|
| A config | `REFUND_WINDOW_SECONDS = 1` | 215 failed | 0 ran, exit 0 | (not used in arm A) |
| A coupons | `COUPONS = {"SAVE10": 1}` | 1 failed | 0 ran, exit 0 | (not used in arm A) |
| B config | `REFUND_WINDOW_SECONDS = 1` | 9 failed | 0 ran, exit 0 | 20 ran; the same 9 failed |
| B binding | `RULES = ()` | 2 failed | 0 ran, exit 0 | 44 ran; the same 2 failed |
| B coupons | `COUPONS = MappingProxyType({"SAVE10": 1})` | 1 failed | 0 ran, exit 0 | 23 ran; the same 1 failed |

As in step 1, testmon never reran a check for a value-only edit, and estoppel reran a set that contained every failure.

**One check added after the run.** It tests a plausible bad resolution: `RULES = (B2G1,)`, keeping X's side of the conflict and dropping `SAVE10`. On the combined tree:
- testmon with Z's data: 41 ran, 1 failed;
- estoppel: 44 ran, 1 failed;
- the full suite: 1 failed.

The failure was the same in all three: Z's coupon journey. testmon caught it because that journey reran anyway: it runs code in `policies.py`, which Y changed. So I do not claim that testmon would have missed this bad resolution. It ran the right check for another reason.

## Kinds

All eight declared kinds were accepted, X's and Y's included. The run also gated Z's two `modify` commits as `activate`. Both were refused before any check ran (exit 2). The core one:

```
change: activate: NOT activate (8 definitions added; 8 code definitions changed; 10 checks changed)
    changes checkout/core/commit.py::State, which is not a binding
    ... (7 more core definitions)
    changes no existing binding
    declare it as modify, or split it
```

Z's `activate` also changed one check (the composition test's contexts) and added a journey file. The kind check allows check changes under any kind. It constrains only code definitions.

## Lines changed

| Branch | Files (lines added + removed) |
|---|---|
| `scn/a-z` | rules and policies: `config.py` 3, `pricing.py` 5, `validation.py` 5. Shared: `service.py` 21, `store.py` 7, `models.py` 1. Tests 97: `test_place_order.py`, `test_pricing.py`, `test_validation.py`, `simulation.py`, new `test_journeys_coupons.py` |
| `scn/b-z` | Core 35: `commit.py` 14, `facts.py` 9, `runtime.py` 8, `moves.py` 4. Core tests 98: `test_core_commit.py`, `test_core_exhaustive.py`, `core_support.py`, `core_sim.py`. Periphery 85: new `coupons.py` 23 and `rules/save10.py` 28, `workflows.py` 12, and 7 more files with 1 to 4 lines each. Tests 135: new `test_coupons.py`, `test_rule_save10.py` and `test_journeys_coupons.py`, `conftest.py`, `test_composition.py`. Claims: 154 files (4 claim files, 150 footprints) |

Z's resolutions: arm A changed `config.py`, `pricing.py` and `test_pricing.py`; arm B changed `config.py` and `rules/__init__.py`. In both arms, the resolution keeps both sides.

## Audit

| Arm | Own suite | `acceptance --features b2g1,category_windows,coupons` |
|---|---|---|
| A | 409 passed | 128 passed |
| B | 486 passed | 128 passed |

After the run I also priced three A with `SAVE10` on both combined trees: 1800 in each, against 2000 without the coupon.

## Against the predictions

| Prediction (section 5) | Result | Holds |
|---|---|---|
| A, Z: all 301 T3 and all T4, at least 90% of check time | T3 301, T4 9; 97.9% | Yes |
| B + testmon, Z: core commit reruns all T2 and T3; the other three no T2 or T3 | 46 T2 and 302 T3; then none | Yes |
| B + estoppel, core `modify`: all T2, T3, T4 and most of T1, at least 90% | All T2, T3 and T4; 32 of 85 T1; 97.4% | Yes on time. No on T1: the pricing checks were kept |
| B + estoppel, periphery `modify`: 15 to 50 existing, no T2 or T3 | 45 existing, none | Yes |
| B + estoppel, `publish`: none | 0 existing, 12 new | Yes |
| B + estoppel, `activate`: 10 to 40, no T2 or T3 | 22 existing, none | Yes |
| A, combine: conflicts in `config.py`, possibly `pricing.py` and `test_pricing.py`; nothing names the stacking; at least 90% with either data | Those three files; nothing names it; 100% with either | Yes |
| B + testmon, combine: all T2 and T3 with main's data; at most 10% and no T2 or T3 with Z's | 100%; 0.1% | Yes |
| B + estoppel, combine: stops at `RULES` only; git also conflicts in `config.py`; after `--resolved`, a note on `STAGES`; 30 to 90 rechecks, no T2 or T3, under 2 s; at least 380 kept | All as predicted: 55 rechecks, 0.21 s, 431 kept | Yes |
| Kinds: all accepted; the core change cannot be a publish | Accepted; both `modify` commits refused as `activate` (not tried as `publish`) | Yes |
| Stacking: 1800 in both arms; implicit in A, recorded in B | As predicted | Yes |
| Lines: Z changes B's core and A's shared files | B core 35; A shared 29 | Yes |
| Audit passes; the oracle cannot check the stacking | Passes; it cannot | Yes |
| Probes: testmon reruns nothing for the coupon limit; estoppel reruns the failing checks | As predicted | Yes |
| X+Y replay matches step 1 within a few checks | Identical counts | Yes |

Base counts: arm B has 435 checks, not the 433 the predictions state. The T2 and T3 counts were right.

**The "what would change the plan" conditions:**

1. **"The stop names only `RULES`."** Met, as predicted. The stop comes from two changes editing one registry; the stage order appears only as a note. The plan's suggested fix, stopping at a binding that one side changed and the other side's claims use, would also stop X+Y, which does not interact (see "The interaction"). Identities per entry would not change that: anything that iterates a registry uses all of its entries.
2. **"B + estoppel reruns T2 or T3 at the combine."** Not met. It reran none, and reused 391 claims made on Z's branch.
3. **"B + testmon with Z's data reruns as little as estoppel at the combine."** Met: 41 against 55, 0.1% against 2.6%. A testmon database chosen from the branch with the expensive change gets the same reuse here. What estoppel adds:
   - nobody has to choose the database: with main's database, testmon reran 100%;
   - it reruns the checks that use changed values, which testmon cannot see;
   - it merges evidence from both sides, where testmon has one database.
4. **"Z's core `modify` reruns less than half of the check time."** Not met: 97.4%. Crossing the core costs a near-full run, once. In arm A every change costs that.

## Fixes made during the run

- **`combine` wrote no report when it stopped.** The first replay crashed reading `combine-b-z-stop.json`. `combine` now writes its report at every exit, with a test (`d15e842`). `cli.py` is not part of the checker digest, so the base claims stayed valid: Z's first gate kept 53 of them and the X+Y gates kept all 435.

`combine --resolved` (`565f4a8`) was written before the run, as section 5 of the predictions says.

## Caveats and what was not tested

- **The changes and the decision text were written by me, not by agents.** I knew the interaction when writing the decision. Agent runs are deferred.
- **Nothing tests the stacking decision.** Neither arm has a check that prices a coupon order with 3 or more units of a SKU under `b2g1`, and neither does the oracle. A later change could flip 1800 to 1700 in either arm and pass every gate.
- **A wrong resolution of the stage order was not tried.** If a resolution moved `SAVE10` into the `item` stage, that would change Z's rule definition, which is not joint. `--resolved` should refuse it (exit 5). estoppel's own tests cover that refusal; this scenario does not.
- **The coupon limit is weakly tested in both arms.** Changing it from 3 to 1 failed one check in each arm.
- **Claims files are large.** Z's branch added 154 files to `.estoppel/`, about 16,000 lines in total. They would need packing in a real repository.
- **One machine, one full replay.** CPU times vary by about 20% between runs. The X+Y rerun counts matched step 1's exactly.
- **Not yet tested:** agent runs, F3, the held-out sample, a larger codebase, and estoppel's performance. Its fixed cost has not been optimized.
