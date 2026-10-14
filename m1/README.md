# M1: does writing software differently remove integration work?

This directory implements the current [Prototype plan](../../reports/Prototype%20plan.md).

One checkout service is built two ways. Both are taken through the same changes, made concurrently:

| Arm | Code | Gate |
|---|---|---|
| A | Conventional service | pytest + pytest-testmon |
| B | A small core that decides, with business rules as proposals the core checks | `newci` (the plan's change workflow): a boundary lint, a check of each change's declared kind, and claims that let a check skip when nothing it used has changed. Also measured with pytest-testmon, to separate the code's effect from the tool's. |

The scenario is three changes from the same base: two independent ones, combined, then one that interacts with them and crosses arm B's core. For each change and arm, the plan's section 4 lists the measures.

## Layout

```
REQUIREMENTS.md   what every arm must do (written before any arm)
spec.py           the shared service interface and requirement constants
world.py          shared clock and fake payment provider (faults, in-flight hooks)
acceptance/       held-out acceptance suite: run only by the audit, never by a gate
arm_a/            conventional implementation, its own tests, AGENTS.md and design notes
arm_b/            core/periphery implementation, its own tests, boundary lint, AGENTS.md and design notes
checks/           checks of the measuring tools themselves (planted bugs)
newci/            the change workflow arm B uses: definitions, kinds, claims, gate and combine
```

## Commands

Run these from `m1/`:

```bash
uv run pytest acceptance --arm a                                     # base requirements (or --arm b)
uv run pytest acceptance --arm a --features b2g1                     # after X
uv run pytest acceptance --arm a --features b2g1,category_windows    # after X and Y combine
uv run pytest acceptance --arm a --features b2g1,category_windows,coupons   # after Z
```

Feature tests for features not in force are skipped. `partial_refunds` is deferred.

To run an arm's own suite, run from the arm's directory:

```bash
cd arm_a && uv run pytest
cd arm_b && uv run python boundary.py && uv run pytest
```

The change workflow's own tests:

```bash
uv run pytest newci/tests
```

To check how strong the suites are, plant known bugs in a copy of an arm:

```bash
uv run python checks/planted_bugs.py a
uv run python checks/planted_bugs.py b
```

## Order of work, and why

1. `REQUIREMENTS.md`, `spec.py`, `world.py` and the acceptance suite are committed before any arm exists.
2. Arm A is written in idiomatic conventional style and committed. It is then reviewed for strawmanning before arm B exists.
3. Predictions were committed before arm B existed (`PREDICTIONS.md`).
4. Arm B, minimal. Then the change workflow and the scenario. See the plan's section 5.

Any change to the acceptance suite after step 1 is listed in `acceptance/CHANGES.md` with the reason.
