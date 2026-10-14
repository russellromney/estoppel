# estoppel

Writing code has become cheap. Verifying it has not. When many coding agents change the same codebase at once, CI becomes the bottleneck: it gets slower, more expensive, flakier and harder to trust as change volume grows. More runners and smarter test selection only delay the problem.

estoppel is a research project. It aims to develop coding methods, testing practices and verification tools that stop CI and testing from being the bottleneck in agentic coding. The question it starts from is not "how do we run CI faster?" but "how should software be written so that most changes need little new verification, and the verification that does run can be trusted?"

The name comes from the legal doctrine: once something has been established, a party cannot later contradict it. Here, a check that passed stays established, as a recorded claim, until something it actually depended on changes.

## The bet

Several ideas each give modest value. Together they may change the development workflow:

| Idea | What it tells us about a change |
|---|---|
| Explicit effects and a checked core/periphery boundary | What it *can* affect |
| Content identities for definitions, with their dependencies | What it *did* affect |
| A claim ledger: each established check, keyed by what it depends on | Which earlier conclusions still hold |
| Publishing code separately from activating it | Who is affected, and when |

The aim is that the cost of a change depends on which guarantees it touches, not on how many other changes are happening.

## Status

This is an early research prototype, not a usable tool. The current milestone, M1, builds one small checkout service two ways and puts both through the same concurrent changes:
- **Arm A:** a conventional service, gated by git and pytest-testmon;
- **Arm B:** a small core that decides, with business rules as proposals the core checks, gated by estoppel's change workflow.

The first scenario has run: two independent features made in parallel from the same base, then combined. Results are in [`proto/m1/scenario/RESULTS.md`](proto/m1/scenario/RESULTS.md). In short:
- In arm A, testmon reran 93 to 100% of the suite's check time for each change, and again at the combine.
- In arm B, neither gate reran the expensive checks. estoppel's combine kept 447 claims from the base and both branches, and rechecked 6.
- testmon misses edits to module-level values such as config constants. estoppel caught them.
- At this small scale, arm B's code structure does most of the work. estoppel's own overhead is larger than the test time it saves.

Next is a change that interacts with an earlier one and crosses arm B's core. The living plan is [`reports/Prototype plan.md`](reports/Prototype%20plan.md).

## Layout

```
reports/          research reports, reviews, and the living plan (older plans in reports/archive/)
research_notes/   the notes and evidence behind the reports
proto/            the prototypes
  m1/             current work: the two arms, the acceptance suite, estoppel and the scenario
  app/ sim/ ...   Phase 0: a kernel for checked plans and a fault-injecting simulator
```

The reports, in the order they were written:
- [Rethinking CI for agentic coding](reports/Rethinking%20CI%20for%20agentic%20coding.md): how CI breaks under agent volume, what teams do today, and the research on test selection, integration and isolation.
- [Rethinking CI from the code up](reports/Rethinking%20CI%20from%20the%20code%20up.md): how software itself could be written so that verification stays cheap.
- [Software designed for cheap verification](reports/Software%20designed%20for%20cheap%20verification.md): a review that separates publishing code, activating it, migrating state and committing effects.
- [Review of synthesis and prototype](reports/Review%20of%20synthesis%20and%20prototype.md) and [Review of Phase 0 and proposed shadow CI](reports/Review%20of%20Phase%200%20and%20proposed%20shadow%20CI.md): reviews of the plans and of the first prototype.
- [Prototype plan](reports/Prototype%20plan.md): the current plan.

## Running it

It needs Python 3.12 or later and [uv](https://docs.astral.sh/uv/).

```bash
cd proto && uv sync
cd m1 && uv run pytest estoppel/tests                       # estoppel's own tests
cd arm_b && uv run python ../estoppel gate                  # arm B's gate: lint, then checks without a valid claim
```

[`proto/m1/README.md`](proto/m1/README.md) has the other commands: each arm's suite, the acceptance suite, and the scenario replay.
