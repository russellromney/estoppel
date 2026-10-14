# E1 results: authority boundary and closed-loop simulation

Run: `uv run python -m experiments.e1 --seeds 200`. Raw output goes to `results/e1.json`, which is not committed. The run is deterministic, so the same command reproduces these numbers.

Predictions were committed in `backlog/failure_corpus.md` (commit `1c8ae8e`) before any kernel code existed. They have not been edited since.

## Summary

- **17 of 18 predictions held.** The miss is KB06: it was predicted to go undetected, but a progress property caught it.
- **Hand corpus: 3 of 11 planner bugs are harmful but valid,** as predicted (PB02, PB04, PB16). The kernel accepts their plans, and only the planner property checks catch them. This number says little about real bugs, because the same author wrote the kernel, the bugs and the predictions. See "What this does not show".
- **No planner bug broke a safety invariant.** Over 200 seeds, none of the 11 planner bugs violated S1–S6. Containment held in this sample.
- **Every kernel bug was found by the simulator.** Six were caught as predicted. KB06 was caught by a progress property, contrary to its prediction.
- **The simulator is cheap.** 200 baseline seeds (12,000 requests, 44,905 steps) run in 1.7 s. The full E1 run takes about 80 s.
- **The kernel rejected 6.6% of baseline requests.** Every rejection comes from staleness. Most (4.0%) are grant expiry, and that rate depends on the simulated delays.
- **E1b (104 mutants of the v1 planners) changes the picture.**
  - 92% of the mutants that changed behaviour *fail closed*: the planner declines, crashes or emits a plan the kernel rejects. 6% are harmful but valid, and 1.6% are fully contained by the kernel.
  - None broke safety or progress.
  - 4 of the 7 E1b predictions held. The three share predictions were far off.

## Baseline

200 seeds, 60 requests each. With the v1 planners there were 0 safety violations and 0 progress violations.

Kernel rejections of first deliveries (duplicate commits excluded), out of 12,000 requests:

| Reason | Count | Share | Cause |
|---|---|---|---|
| `grant_expired` | 477 | 4.0% | More than `GRANT_TTL` (300 s) passed between snapshot and commit. 15% of simulated ticks are 300–1200 s and 5% are days. |
| `insufficient_stock` | 223 | 1.9% | Another order took the stock after the snapshot. |
| `order_state` | 90 | 0.75% | The order changed state after the snapshot, for example it expired before payment. |

Each of these is a real conflict or a timeout, not a valid plan rejected by mistake. Whether 4% grant expiry is "too many" cannot be judged here, because the delay distribution is made up. A design that validates only at commit, with no grant expiry, would avoid that 4%, but it was not tested.

## Planner bugs

**Kernel blocked** counts kernel rejections above baseline, by reason. A reason counts only when its excess is more than 3 standard deviations (Poisson) over baseline.

**Diverged accepted** counts plans the kernel accepted that differ from what the v1 reference planner produced for the same request and snapshot.

**Properties** counts failing cases out of 500 generated cases per property set.

| ID | Bug | Predicted | Observed | Kernel blocked | Diverged accepted | Properties |
|---|---|---|---|---|---|---|
| PB01 | ignores stock | kernel-reject | kernel-reject, property | insufficient_stock +2528 | 13 (benign, see below) | PO3 201 |
| PB02 | price 0 | property | property | none | 2977 | PO1 220 |
| PB03 | qty² in price | kernel-reject | kernel-reject, property | price_out_of_bounds +4826 | 0 | PO1 171 |
| PB04 | no refund window | property | property | none | 31 | RF1 19 |
| PB05 | invented grant | kernel-reject | kernel-reject, property | unknown_grant +1339 | 0 | RF1 341 |
| PB06 | half refund | kernel-reject | kernel-reject, property | amount_mismatch +559 | 0 | RF1 49 |
| PB08 | negative qty | kernel-reject | kernel-reject, property | bad_qty +4832 | 0 | PO1/PO2 171 |
| PB12 | `while` loop | static | static | – | – | – |
| PB13 | `import time` | static | static | – | – | – |
| PB14 | reads other tenants | structural | structural, property | – | 0 | ERR 457 |
| PB16 | always SKU A | property | property | none | 815 | PO2 162, PO4 75 |

Notes:

- **PB01's 13 accepted divergences are benign.** Each time, the reference planner saw too little stock in its snapshot and declined (`reject: out_of_stock`). Stock was freed before the commit, so the kernel accepted PB01's reservation against current stock. The obligation was violated (PO3), but no harm resulted. This is why the metric is called "diverged accepted" and not "harmful accepted".
- **PB01, PB03 and PB08 also show extra `grant_expired` rejections** (+217 to +247). Bad plans never reserve stock, so later requests hit `out_of_stock` less often, so more plans reach the kernel. The kernel checks grant expiry before content, so some bad plans are counted as expired. The cause is probably workload divergence, but this was not traced request by request.
- **PB05 was corrected after the first run.** The first version also lacked the refund-window check, so it had a second, unintended bug. That produced 6 accepted refunds outside the window in a 50-seed run. Now it carries only the bug in its description, and it has 0 accepted divergences.
- **Refunds outside the window are rare in the workload.** PB04 has only 31 harmful acceptances in 12,000 requests, because 5% of ticks are multi-day. A workload aimed at refunds would expose PB04 faster.
- **Property checks caught every non-static planner bug.** This is weak evidence: the same author wrote the checks and the bugs, knowing the bugs (S6 in the plan).

## Kernel bugs

| ID | Bug | Predicted | Observed | Seeds detecting (of 200) | First violation |
|---|---|---|---|---|---|
| KB01 | commit skips stock check | dst-safety | dst-safety | 140 | seed 0: S1 stock[B] = −2 |
| KB02 | retry with new op_id | dst-safety | dst-safety | 107 | seed 2: S3 o4 charged twice |
| KB03 | refund timeout treated as failure | dst-safety | dst-safety, dst-progress | 17 safety, 15 progress | seed 35: S4 refunded 1600 > charged 800 |
| KB04 | expiry hits paying orders | dst-safety | dst-safety | 115 | seed 0: S6 expired but charged |
| KB05 | grants not consumed | dst-safety | dst-safety | 108 | seed 1: S2 conservation broken |
| KB06 | expiry at TTL+60 | miss | **dst-progress** | 64 | seed 0: P1 reserved past TTL |
| KB08 | decline leaves `paying` | dst-progress | dst-progress | 77 | seed 1: P3 stuck in paying |

**KB06: why the prediction was wrong.**
- The prediction said "no timing property in Phase 0". That was false when the invariants were written: P1 ("no reservation held past TTL after quiescence") is a timing property.
- The catch depends on how quiescence works. Each quiescence round ends with a tick of TTL+1 s. When an order is reserved less than 59 s before the last tick, the correct kernel expires it, but KB06 does not. P1 then sees an order reserved past TTL.
- If the quiescence tick were TTL+60 s or longer, P1 would miss KB06. The catch is real but fragile.
- KB06 never violates safety.
- The prediction stays as committed, and the mismatch counts against the predictions.

**Detection rate as a CI cost.** KB03 is the hardest kernel bug to find. It needs a refund timeout with `lost_after`, so it violates safety in about 1 seed in 12 (17 of 200). Catching it with 99% probability takes about 50 seeds, which is a few seconds.

## Against the E1 kill criterion

The plan says E1 weakens the idea if "most realistic bugs are harmful-but-valid plans, or the kernel rejects too many valid requests".

- **Harmful-but-valid share.**
  - It was 27% in the hand corpus.
  - It was 6% of the diverging mutants in E1b (12.5% without M4).
  - On both samples the criterion is not met: harmful-but-valid bugs are a minority.
  - Neither sample is "realistic bugs". Agent-written bugs are the missing sample. They cost API spend and need approval.
- **The kernel as bug detector.** The pre-registered E1b reading says the idea is weakened if the kernel fully contains under 50% of planner bugs. It fully contained 1.6%, so most planner bugs still need behavioural evidence. See the E1b discussion for what kind of evidence.
- **False rejections.** No rejections of a plan that was valid at commit time were seen, apart from grant expiry. Grant expiry is a policy cost (4% under the made-up delays), not a correctness fault.

## E1b: mutation sample of the v1 planners

**Setup.**
- Predictions were committed in `backlog/failure_corpus.md` (commit `eb000f8`) before any mutation code existed.
- Run: `uv run python -m experiments.e1b`. It uses 20 seeds per mutant and takes about 16 s.
- Results go to `results/e1b.json`.
- A rerun at 100 seeds put every mutant in the same class.

**Mutants.**
- There are 104 first-order mutants: `place_order_v1` 47, `pay_v1` 13 and `refund_v1` 44.
- The restricted-subset validator rejected none of them. Every mutant is a legal planner.
- 63 mutants diverged from v1 in the simulator. 41 never did.

### Predictions against results

| Measure (share of the 63 diverging mutants) | Predicted | Observed | Held |
|---|---|---|---|
| `accepted` (harmful but valid) | about 30% | 6.3% (4); 12.5% without M4 | no |
| `lost` (fail-closed) | about 50% | 92.1% (58); 84.4% without M4 | no |
| `blocked` (fully contained by the kernel) | about 20% | 1.6% (1); 3.1% without M4 | no |
| Fully contained by the kernel | under 50% | 1.6% | yes |
| Mutants that break safety (S1–S6) | 0 | 0 of 104 | yes |
| Mutants that break progress (P1–P4) | 0 | 0 of 104 | yes |
| Diverging mutants that fail a property check | 90% or more | 100% (63 of 63) | yes |

The direction was right but the shape was wrong. I expected a planner bug to make the planner act wrongly. Most mutants instead stop it acting at all.

M4 (misspelled string constants) makes up 63 of the 104 mutants. Nearly all M4 mutants crash on a missing key or emit a malformed plan, so the table also gives shares without M4.

### The four harmful-but-valid mutants

| Mutant | Effect | Caught by |
|---|---|---|
| `place_order` price `*`→`+` | Charges price+qty instead of price×qty. Orders with qty ≥ 2 are underpriced and accepted. Orders with qty 1 are overpriced and rejected (`price_out_of_bounds`). | PO1; the happy-path example |
| `place_order` `wanted.get(sku, 0)`→`get(sku, 1)` | Reserves and charges one extra unit of each SKU. | PO2, PO4; the happy-path example |
| `refund` negate the window check | Refunds only orders *outside* the 30-day window. | RF1, RF2; the happy-path example |
| `refund` delete the window check | Refunds any paid order (the same bug as PB04). | RF1 only |

**Why the kernel accepts them.** Each is a business-rule error inside the kernel's bounds:
- the kernel bounds price to `0 ≤ price ≤ list total`;
- it checks that reserved items exist and are in stock, not that they match the request;
- it checks a refund's amount and grant, not the refund window.

### Where the kernel acted

The kernel rejected at least one action in 10 of the 63 diverging mutants:

- **It prevented harm in three mutants.**
  - `wanted[sku] + qty` → `- qty` produced negative quantities. These would have minted stock, but the kernel rejected them as `bad_qty`.
  - Price `*`→`+` overcharged single-unit orders, which the kernel rejected as `price_out_of_bounds`.
  - Deleting the stock guard (the only `blocked` mutant) oversold, which the kernel rejected as `insufficient_stock`.
- **It rejected malformed plans in six mutants.** These misspelled `grant`, `items`, `price` or `amount` in the plan. Without the kernel's validation they would have failed somewhere less clear.
- **The extra-unit mutant** was rejected for insufficient stock on some requests.

### Post hoc: a single example test

This check was not pre-registered. Each mutant was run on one hand-written happy-path case per request kind: two SKUs ordered, a reserved order paid, and a paid order refunded after one day.

| Mutant class | Fail the example |
|---|---|
| `lost` | 56 of 58 |
| `accepted` | 3 of 4 |
| `blocked` | 0 of 1 |
| `silent` | 0 of 41 |

Two `lost` mutants pass it, and both are boundary changes:
- stock `<` → `<=`, which declines when stock exactly equals the request;
- the window check `now - paid_at` → `now + paid_at`, which declines refunds once simulated time passes about 30 days.

One `accepted` mutant passes it: deleting the refund-window check. Only the property check RF1 and divergence from v1 catch it.

### What E1b suggests

These points are interpretation, not pre-registered findings.

1. **The kernel is a safety backstop, not a bug detector.**
   - 115 planner bugs (11 by hand, 104 mutants) were run, and none broke safety or progress. That bounded blast radius is what could let planner changes ship with lighter gates.
   - The kernel does not remove the need for behavioural evidence: it fully contained 1 of 63 diverging mutants.
2. **Behavioural evidence for planners splits in two.**
   - Fail-closed bugs are loud. One example per request kind catches 56 of 58.
   - The dangerous bugs are business rules inside the kernel's bounds (price, quantity, window). These need properties, or an oracle such as the previous version.
3. **Divergence from the previous version is a strong signal only for some change kinds.**
   - It flagged all 63 diverging mutants, by construction. It is the only check besides RF1 that catches the deleted window guard.
   - This is the old-version oracle you were sceptical of. For a fix, divergence is the point, not a defect. It is evidence for a refactor or extension kind, not for a fix.
4. **Tightening the kernel turns accepted bugs into blocked ones, but makes the kernel churn.**
   - "Reserve exactly the requested items" would block PB16 and the extra-unit mutant.
   - "Kernel computes the price" would block both pricing bugs.
   - Each such check moves a business rule into the kernel. That is the cost E-K measures (S8).

### E1b limits

- **Mutants are not real bugs.** Mutation scores correlate with real-fault detection, but the mix of mutants (63% M4 here) is not the mix of real bugs.
- **The shares depend on the workload.** The simulator sends mostly valid requests. Item validation is never stressed, so mutants of it are silent in the simulator and are caught only by property checks (7 of 41 silent mutants fail one).
- **The shares depend on how the v1 planners are written.** For example, deleting the refund status check is silent, because the window check then crashes on `paid_at = None` for unpaid orders, and the reference declines those anyway.
- **`lost` is approximate.** It assumes the reference plan would have been accepted. Some of those reference plans were stale and would also have been rejected.
- **The example test was not pre-registered.** It was written after the results were seen.

## What this does not show

- **The bugs are not real agent-written bugs.** The corpus was written by hand, by the same author as the kernel and the property checks.
- **Concurrency is simulated.** It is single-threaded interleaving chosen by a seeded random generator. There are no real threads or processes.
- **The payment provider is a stub.** Faults are drawn independently at fixed rates.
- **The checks are not independent.** Property checks are not independent evidence (S6).
- **Refund behaviour is barely exercised.** Partial refunds are out of scope in v0, and refunds outside the window are rare in the workload.
- **Valid-at-commit was not measured.** E1 does not check whether a plan rejected for grant expiry would still have been valid at commit time.
