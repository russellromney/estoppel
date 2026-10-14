# newci prototype

Phase 0 (this directory's `app/`, `sim/` and `experiments/`) implements the archived [v2 plan](../reports/archive/Synthesis%20and%20prototype%20plan.md).

Current work is in [`m1/`](m1/README.md) and follows the [Prototype plan](../reports/Prototype%20plan.md).

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
uv run python -m experiments.e1     # hand-written bug corpus
uv run python -m experiments.e1b    # mutation sample of the v1 planners
```

Results: [`experiments/E1_results.md`](experiments/E1_results.md).
