# newci prototype

This prototype implements the plan in [`../reports/Synthesis and prototype plan.md`](../reports/Synthesis%20and%20prototype%20plan.md) (v2).

The toy domain is a checkout system covering reservations, payment and full refunds. It is split into two parts:

- **Kernel.** It issues narrowly authorized moves, checks every plan against current state, and is the only component that holds effects.
- **Planners.** These are pure functions, `propose(request, snapshot) -> plan`, written in a restricted subset of Python.

A closed-loop deterministic simulator runs the system under concurrency and injected faults.

## Layout

```
backlog/       pre-registered feature backlog and failure corpus (committed before code)
app/           kernel, effect model, restricted-planner loader, runtime, planners
sim/           deterministic closed-loop simulator and invariants
checks/        planner property checks (the planner's own obligations)
corpus/        planner and kernel bug variants for E1
experiments/   experiment runners
tests/         unit tests
```

## Commands

```bash
uv run pytest
uv run python -m experiments.e1
```
