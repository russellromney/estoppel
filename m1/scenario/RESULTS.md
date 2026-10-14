# Scenario, step 1: combining X and Y

The change workflow was called `newci` when this ran. It has since been renamed estoppel; this record keeps the old names.

Run on 2026-10-14. This is the plan's step 4 ([Prototype plan](../../../reports/Prototype%20plan.md), section 5). The predictions are in [`../PREDICTIONS.md`](../PREDICTIONS.md), section 4. They were committed in `7f72ac5`, before any scenario change was written, and are not edited here.

- X is `b2g1`: every third unit of a SKU is free.
- Y is `category_windows`: the refund window depends on the product categories in the order.

[`run_xy.py`](run_xy.py) replays both changes in both arms, in throwaway git worktrees, with the commands an agent runs. The changes' files are in [`changes/`](changes/). I wrote them from the requirements; no agent was run. Raw results:
- [`results/xy.json`](results/xy.json): every command, with exit code, checks run, tiers and CPU time;
- [`results/xy-summary.md`](results/xy-summary.md): the same, as a table;
- [`results/xy-logs/`](results/xy-logs/): each command's output;
- [`results/xy-combine-b.json`](results/xy-combine-b.json): `newci combine`'s report.

The branches are kept: `scn/a-x`, `scn/a-y`, `scn/a-int`, `scn/b-x`, `scn/b-y` and `scn/b-int`. The base is `138f921`. It is the base claims commit `ccdba17` plus two fixes to newci that the run found (see "Fixes made during the run").

## Summary

- **Both combines merged cleanly, and both audits passed.** In the scenario's own steps, no gate passed where the audit failed. The probes below found cases where testmon did.
- **Arm A + testmon reran all 301 simulation checks (T3) at every step.** That is 93 to 100% of the suite's check time, for each change and again at the combine.
- **Arm B reran no T2 or T3 check at any step, with either gate.** Every run was under 1% of the suite's check time.
- **`newci combine` stopped at nothing, kept 447 claims and rechecked 6.** The 447 were 409 made on the base, 27 on X's branch and 11 on Y's. All 6 rechecks use both changes. It noted that X's binding `RULES` is used by 5 claims made on Y's branch.
- **testmon does not see edits to module-level values.** Three probes changed only a value: a config constant in each arm, and `RULES` in arm B. The full suite then failed 226, 9 and 1 checks. testmon ran 0 checks each time and exited 0. newci reran the affected checks and reported exactly the same failures.
- **On time, B + testmon is as good as B + newci here.** Both stay under 0.1 s of check time. newci's own overhead (about 1.1 s of CPU per gate, 3.0 s per combine) is larger than the check time it saves. This meets the first "what would change the plan" condition, on time. What newci adds at this scale is soundness and reuse, not speed. See "Against the predictions".

## The commands

| Who | Arm A | Arm B |
|---|---|---|
| Agent, per commit | `uv run pytest --testmon -q`<br>`git add -A && git commit -m "..."` | `uv run python ../newci gate --kind K`<br>`git add -A && git commit -m "..." -m "Newci-Kind: K"` |
| Integrator | `git merge --no-edit scn/a-x scn/a-y`<br>`uv run pytest --testmon -q` | `uv run python ../newci combine scn/b-x scn/b-y` |

In arm A, X and Y are one commit each. In arm B, X is a publish then an activate, and Y is a publish then a modify. `newci combine` checks each commit's kind, stops at definitions both sides changed, merges, rechecks, and commits the merge with its new claims. Its output, shortened:

```
combine scn/b-x, scn/b-y into scn/b-int (base 138f921)
declared kinds:
  scn/b-x ... publish: ok (16 definitions added)
  scn/b-x ... activate: ok (4 definitions added; bindings checkout/app/pricing/rules/__init__.py::RULES, ...::from checkout.app.pricing.rules.b2g1 import B2G1)
  scn/b-y ... publish: ok (11 definitions added; bindings checkout/app/config.py::CATEGORIES, checkout/app/config.py::CATEGORY_REFUND_WINDOWS)
  scn/b-y ... modify: ok (5 definitions added; 2 code definitions changed)
definitions changed by more than one side: none
merge: clean
claims kept: 447 (409 made on base, 27 made on scn/b-x, 11 made on scn/b-y)
to recheck: 6
     5 use checkout/app/pricing/rules/__init__.py::RULES, changed by scn/b-x
     4 use checkout/app/policies.py::from checkout.app.config import REFUND_WINDOW_SECONDS, changed by scn/b-y
     4 use checkout/app/policies.py::refund_window_open, changed by scn/b-y
  note: binding checkout/app/pricing/rules/__init__.py::RULES, changed by scn/b-x, is used by 5 claims made on another side
lint: ok
checks: 447 kept by valid claims; 6 ran; 0 failed
```

## What reran

"Existing" means a check that exists at the base. "Share" is the rerun checks' share of the full suite's check time. It uses each check's time from the audit run, which has no tracing. Under testmon, each check takes about 2.5 times longer.

| Step | A + testmon | B + testmon | B + newci |
|---|---|---|---|
| X publish | (one commit in arm A) | 9 ran, all new | 9 ran, all new; 435 kept |
| X (activate in B) | 323 ran: T1 11, T2 3, T3 301, T4 8. Share 100% | 1 ran (new) | 31 ran (21 existing, 10 new): T1 22, T4 9; 414 kept. Share 0.5% |
| Y publish | (one commit in arm A) | 25 ran (19 existing) | 6 ran, all new; 435 kept |
| Y (modify in B) | 342 ran: T1 14, T2 18, T3 301, T4 9. Share 93.5% | 27 ran | 10 ran (8 existing, 2 new); 433 kept |
| Combine, base data | 357 ran: T1 25, T2 21, T3 301, T4 10. Share 100% | 37 ran | 6 ran (3 existing, 3 new); 447 kept |
| Combine, X's data | 343 ran, T3 301. Share 93.5% | 28 ran | — |

**CPU per command** (one run; repeated runs varied by about 20%):

| Command | CPU s |
|---|---|
| Arm A, `pytest --testmon`, per step | 10.6 to 11.3 |
| Arm A, full suite without testmon | 4.6 |
| Arm B, `pytest --testmon`, per step | 0.5 to 0.6 |
| Arm B, `newci gate`, per step | 1.1 to 1.2 |
| Arm B, `newci combine` | 3.0 |
| Arm B, full suite without either | 6.3 |

In arm A, `pytest --testmon` costs more than running the whole suite without it. It reruns almost everything, and its tracing slows each check.

In arm B, a newci gate costs about 0.6 s more CPU than testmon. Most of that is the kind check: lint, a snapshot of `HEAD`, and indexing definitions on both sides. On its own, the refused activate (which runs no checks) took 0.45 s. `combine` builds ten definition indexes:
- three per branch, to check each commit's kind;
- then the base, both sides and the merge.

Caching them would cut this.

**Why each newci step reran what it did:**
- **X activate, 21 existing:** the checks whose footprint includes `RULES`: pricing 9, journeys 8, composition 3, workflows 1. The 10 new checks are X's own journey and the 9 rule checks from X's publish. Those 9 rule checks pass `rules=(B2G1,)` explicitly, so `RULES` cannot affect them. They reran because `quote`'s default argument is `rules=RULES`, which puts `RULES` in the footprint of every caller. It costs little here, but it is a general case: a default argument makes the binding part of every caller's footprint.
- **Y modify, 8 existing:** the checks that use `refund_window_open`: journeys 3, policies 2, workflows 3.
- **The combine, 6:** each side's claim was made against the other side's old version.
  - The 3 base journeys use both `RULES` and `refund_window_open`.
  - X's journey uses `refund_window_open`.
  - Y's 2 journeys use `RULES`.

**Why testmon reran what it did in arm B.** testmon includes a file in a check's fingerprint only if a line of that file runs during the check (`create_fingerprint` in `testmon/process_code.py`). When it does, the file's module-level text is part of the fingerprint.
- Y's publish added imports and a function to `policies.py`, so testmon reran every check that runs a function there. That is 19 reruns where newci reran 0.
- X's activation changed only `rules/__init__.py`, which holds values and runs no line during a check, so testmon reran only the new journey. 21 existing checks depend on `RULES`. This is the blind spot shown by the probes below.

## Probes: edits that change only a value

These run on the combined tree after the audit, and are then undone.

| Probe | Edit | Full suite | testmon | newci |
|---|---|---|---|---|
| A config | `REFUND_WINDOW_SECONDS = 1` | 226 failed | 0 ran, exit 0 | (not used in arm A) |
| B config | `REFUND_WINDOW_SECONDS = 1` | 9 failed | 0 ran, exit 0 | 20 ran; the same 9 failed |
| B binding | `RULES = ()`, undoing X's activation | 1 failed | 0 ran, exit 0 | 1 ran and failed; 452 kept |

The values in `config.py` and `rules/__init__.py` are read at import, so no line of either file runs during a check. testmon never links a check to them. newci's footprint includes the values that the code which ran refers to.

In the binding probe, newci kept 452 claims, because setting `RULES` back to `()` makes the base claims valid again. Only X's new journey had no claim for that tree.

This matters for the baseline. A + testmon is unsound for edits to config values and registries, which are common. In this scenario no such edit happened in arm A: X and Y changed function bodies, which testmon sees. But B + testmon's 1 rerun at X's activation is this gap, not precision.

## Kinds

All four declared kinds were accepted. To test that Y cannot be an activate, the run also tries to gate Y's second commit as one. The gate refuses before running any check (exit 2):

```
change: activate: NOT activate (5 definitions added; 2 code definitions changed)
    changes checkout/app/policies.py::from checkout.app.config import REFUND_WINDOW_SECONDS, which is not a binding
    changes checkout/app/policies.py::refund_window_open, which is not a binding
    changes no existing binding
    declare it as modify, or split it
```

Y's publish added `CATEGORIES` and `CATEGORY_REFUND_WINDOWS` to `config.py`. Every name in `config.py` is a binding, so the gate lists them as bindings. The commit is still a publish, because it only adds.

## Lines changed

| Branch | Files |
|---|---|
| `scn/a-x` | `checkout/pricing.py` 7; tests 33 (`test_pricing.py`, new `test_journeys_b2g1.py`) |
| `scn/a-y` | `checkout/config.py` 5, `checkout/policies.py` 9; tests 52 (`test_policies.py`, new `test_journeys_category_windows.py`) |
| `scn/b-x` | `rules/b2g1.py` 12 (new), `rules/__init__.py` 3; tests 52 (two new files: `test_rule_b2g1.py`, `test_journeys_b2g1.py`); claims: 2 claim files, 27 footprints |
| `scn/b-y` | `config.py` 5, `policies.py` 9; tests 47 (two new files: `test_policies_category_windows.py`, `test_journeys_category_windows.py`); claims: 2 claim files, 11 footprints |
| `scn/b-int` | the merge adds 1 claim file and 6 footprints |

Neither change touched arm B's core or arm A's shared files (`service.py`, `store.py`, `models.py`, `gateway.py`).

## Audit

| Arm | Own suite | `acceptance --features b2g1,category_windows` |
|---|---|---|
| A | 387 passed | 107 passed |
| B | 453 passed | 107 passed |

## Against the predictions

| Prediction (section 4) | Result | Holds |
|---|---|---|
| A, X: reruns pricing T1, place-order T2, all 301 T3 and all 7 T4, close to the full suite's CPU | T1 11, T2 3, T3 301, T4 8 (7 existing and 1 new). Share 100% | Yes |
| A, Y: at least 250 T3, plus the refund T1, T2 and T4 checks | T3 301, T1 14, T2 18, T4 9. Share 93.5% | Yes |
| A, combine: clean merge; with base data at least 90% of CPU; with X's data at least 250 T3 | Clean. 100% with base data; 301 T3 (93.5%) with X's data | Yes |
| B + testmon: no T2 or T3 at any step | None at any step | Yes, but see the probes: at the activation it ran too little |
| B + newci, X publish: no existing checks | 0 existing, 9 new | Yes |
| B + newci, X activate: 15 to 30 existing, no T2 or T3 | 21 existing, 10 new, no T2 or T3 | Yes |
| B + newci, Y publish: no existing checks | 0 existing, 6 new | Yes |
| B + newci, Y modify: 5 to 15 existing, no T2 or T3 | 8 existing, 2 new | Yes |
| B + newci, combine: no stop; at most 15 rechecks under 0.5 s of CPU; only checks using both `RULES` and `refund_window_open`; a note that X changed `RULES`, which Y's claims use | No stop. 6 rechecks, all using both. A note on `RULES` and 5 claims made on Y's branch. Check time 0.01 s, but the command itself took 3.0 s of CPU | Yes for the checks. The command's own cost was not predicted |
| Kinds: all four accepted; Y cannot be an activate | Accepted; the activate declaration is refused | Yes |
| Lines: no arm B core; arm A X in `pricing.py` only, Y in `config.py` and `policies.py` only | As predicted | Yes |
| Audit passes in both arms | Passes | Yes |
| Two commands per commit; combining is one command in B and two in A | As predicted | Yes |

**The "what would change the plan" conditions:**

1. **"B + testmon reruns about as little as B + newci."** On time, this is met. Both gates stay under 1% of the suite's check time at every step, and neither reruns T2 or T3. At this scale, arm B's structure removes the expensive reruns, and either tool is enough. newci's per-command overhead is larger than the check time it saves over testmon. By count, newci reran fewer checks at Y's publish (6 against 25) and at the combine (6 against 37 or 28), the same at X's publish, and more at the activation, where testmon ran too little. What newci adds here:
   - **Soundness on value edits.** It reran what the probes broke, where testmon ran nothing.
   - **Claims that travel with branches.** The combine reused 38 claims made on the two branches. testmon has one database, and the choice of database changes its result (37 or 28 reruns).
   - **Kinds.** The gate refused a mislabelled change.
2. **"B + newci rechecks much more than predicted at the combine."** Not met: 6, against a limit of 15.
3. **"A + testmon reruns little at the combine."** Not met: it reran all 301 T3, 100% of the suite's check time.

## Fixes made during the run

- **`newci combine` crashed whenever a claim needed rechecking.** A local variable shadowed the list of branches. Fixed in `df77607`, with a test where one side's claim is made stale by the other side.
- **A refused kind suggested the wrong kind.** Refusing Y as an activate said "declare publish", which would also be refused. It now names the narrowest kind the change qualifies as. Fixed in `138f921`.
- **testmon data was copied wrongly.** testmon writes SQLite in WAL mode, so a file copy of `.testmondata` missed its data. The first run therefore reported full reruns on every branch. The script now copies with SQLite's backup API. The numbers above are from runs after that fix.

Neither newci fix changes the claims' environment (`cli.py` and `kinds.py` are not part of the checker digest), so the base claims from `ccdba17` stay valid. X's publish kept all 435 of them.

## Caveats and what was not tested

- **One feature per journey file.** Both arms' `AGENTS.md` ask for a new journey file per feature, so concurrent changes do not edit `test_journeys.py`. Without that, both arms would get a textual conflict there. This favours neither arm.
- **Y is a modify in arm B, not an activate,** because the refund policy is not a binding. The kinds did not help Y.
- **The changes were written by me, not by agents.** They follow the requirements and each arm's `AGENTS.md`. Agent runs are deferred.
- **One machine.** CPU times vary by about 20% between runs. The rerun counts were identical in all six full runs made after the testmon data fix.
- **testmon's "kept" count is not reported.** testmon deselects only within the files it collects, so its deselected count is not the number of checks kept.
- **Not yet tested:** Z (coupons), which interacts with X and crosses arm B's core; F3; the held-out sample; agent runs; and a larger codebase, where newci's fixed overhead may matter less.
