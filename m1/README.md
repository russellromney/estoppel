# M1: does writing software differently remove integration work?

This directory implements milestone M1 of [Prototype plan v4](../../reports/Prototype%20plan%20v4.md).

One checkout feature is built three ways:

| Arm | Code | Gate |
|---|---|---|
| A | Conventional service | pytest + pytest-testmon |
| B | Core and planners | pytest + pytest-testmon |
| C | Same code as B | minimal `newci` |

Each later change (C1, C1x, C1y, C2) is applied to every arm. The comparison counts which checks each gate runs, and an audit checks whether each gate's decision was safe.

## Layout

```
REQUIREMENTS.md   what every arm must do (written before any arm)
spec.py           the shared service interface and requirement constants
world.py          shared clock and fake payment provider (faults, in-flight hooks)
acceptance/       held-out acceptance suite: run only by the audit, never by a gate
arm_a/            conventional implementation, its own tests, AGENTS.md and design notes
checks/           checks of the measuring tools themselves (planted bugs)
```

## Commands

Run these from `m1/`:

```bash
uv run pytest acceptance --arm a                      # base requirements
uv run pytest acceptance --arm a --features b2g1      # after C1
uv run pytest acceptance --arm a --features partial_refunds   # after C2
```

To run an arm's own suite, run from the arm's directory:

```bash
cd arm_a && uv run pytest
```

To check how strong the suites are, plant known bugs in a copy of arm A:

```bash
uv run python checks/planted_bugs.py
```

## Order of work, and why

1. `REQUIREMENTS.md`, `spec.py`, `world.py` and the acceptance suite are committed before any arm exists.
2. Arm A is written in idiomatic conventional style and committed. It is then reviewed for strawmanning before arm B exists.
3. Predicted obligations for each change and arm are committed next.
4. Then arms B and C, the four changes, and the comparison.

Any change to the acceptance suite after step 1 is listed in `acceptance/CHANGES.md` with the reason.
