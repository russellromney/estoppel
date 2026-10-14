# M1: does writing software differently remove integration work?

This directory implements the current [Prototype plan](../../reports/Prototype%20plan.md).

One checkout service is built two ways. Both are taken through the same changes, made concurrently:

| Arm | Code | Gate |
|---|---|---|
| A | Conventional service | pytest + pytest-testmon |
| B | A small core that decides, with business rules as proposals the core checks | A boundary lint, plus pytest + pytest-testmon; later, the minimal change workflow from the plan |

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
```

## Commands

Run these from `m1/`:

```bash
uv run pytest acceptance --arm a                      # base requirements (or --arm b)
uv run pytest acceptance --arm a --features b2g1      # after C1
uv run pytest acceptance --arm a --features partial_refunds   # after C2
```

To run an arm's own suite, run from the arm's directory:

```bash
cd arm_a && uv run pytest
cd arm_b && uv run python boundary.py && uv run pytest
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
