# Failure corpus (pre-registered)

This file was written and committed before any kernel code existed. Each case has a predicted detection layer:

| Layer | Meaning |
|---|---|
| `static` | Rejected when loading, by the restricted-subset validator. |
| `kernel-reject` | The kernel rejects the plan at commit time, and safety invariants still hold. |
| `structural` | The planner cannot express the harm. The snapshot or the move scope makes it impossible, so the planner errors or produces a plan that gets rejected. |
| `property` | The plan is harmful but valid. The kernel accepts it, and only the planner's own property checks catch it. |
| `dst-safety` | A closed-loop simulation run violates a safety invariant. |
| `dst-progress` | Progress properties fail after the system goes quiet. |
| `miss` | Expected to go undetected by Phase 0 mechanisms. |

## E1 corpus (Phase 0)

### Planner bugs

These are restricted-subset planners in `corpus/planner_bugs/`.

| ID | Bug | Predicted layer |
|---|---|---|
| PB01 | `place_order` ignores stock in the snapshot and always reserves | kernel-reject |
| PB02 | `place_order` prices every order at 0 (discount bug) | property (harmful but valid) |
| PB03 | `place_order` double-counts quantity in the price | kernel-reject (price exceeds list total) |
| PB04 | `refund` ignores the 30-day window | property (harmful but valid) |
| PB05 | `refund` invents a grant ID when the kernel offered none | kernel-reject |
| PB06 | `refund` refunds half the amount | kernel-reject (v0 requires the full amount) |
| PB08 | `place_order` emits a negative quantity | kernel-reject |
| PB12 | A planner contains a `while` loop | static |
| PB13 | A planner imports `time` | static |
| PB14 | `place_order` tries to read other customers' orders from the snapshot | structural |
| PB16 | `place_order` reserves SKU A whatever the customer requested | property (harmful but valid) |

### Kernel bugs

These are variant subclasses of the kernel in `corpus/kernel_bugs.py`.

| ID | Bug | Predicted layer |
|---|---|---|
| KB01 | Commit skips the stock check because "the planner already checked", so stale snapshots oversell | dst-safety |
| KB02 | Reconciliation retries unknown effects with a new operation ID and no lookup | dst-safety (double charge) |
| KB03 | A refund timeout is treated as a failure, so the order returns to paid | dst-safety (double refund) |
| KB04 | Expiry also expires orders that are mid-payment | dst-safety (charged order released) |
| KB05 | Grants are not consumed, so a duplicated commit applies twice | dst-safety |
| KB06 | Expiry is off by one tick period (it uses TTL+60) | miss (no timing property in Phase 0) |
| KB08 | A declined charge leaves the order stuck in `paying` | dst-progress |

**Prediction summary for E1.**
- Of the 11 planner bugs, 3 are harmful-but-valid. That is 27% that the kernel cannot contain.
- Of the 7 kernel bugs, 6 are found by closed-loop simulation and 1 is an expected miss.

## E1b mutation sample (added after E1, before any mutation code)

This section was written after the E1 hand-corpus results were seen, and before the mutation code existed. The hand corpus was written by the kernel's author, so it cannot answer whether *most* bugs are harmful but valid. Mutation analysis of the v1 planners gives a sample that the author did not choose bug by bug.

**Mutants.** Each mutant applies one operator at one site in one v1 planner (`place_order_v1`, `pay_v1`, `refund_v1`). These operators are applied at every site where they fit:

| Op | Change |
|---|---|
| M1 | Comparison: `<`↔`<=`, `>`↔`>=`, `==`↔`!=`, `in`↔`not in`, `is`↔`is not` |
| M2 | Arithmetic: `+`→`-`, `-`→`+`, `*`→`+` |
| M3 | Integer constant: n→n+1, and n→0 when n≠0 |
| M4 | String constant (not docstrings): s→s+"_x" |
| M5 | Boolean: `and`↔`or` |
| M6 | Negate an `if` test |
| M7 | Delete a guard: an `if` with no `else` whose body is a single `return` |
| M8 | Drop a `not` |

**Run.** Each mutant goes through these steps:

1. The restricted-subset validator.
2. Property checks (500 cases).
3. The closed-loop simulator, over 20 seeds, with the v1 planners as reference.

**What counts.** Only first deliveries count. A plan *diverges* when it differs from the reference plan, unless both plans decline. Each divergence is classed by outcome:

| Class | Meaning |
|---|---|
| `accepted` | The kernel accepted a plan that differs from the reference. If the reference declined only because its snapshot showed too little stock, the divergence is recorded as `stale` and treated as benign. |
| `lost` | The request failed (a planner decline, a crash, or a kernel rejection) where the reference acted. This is fail-closed: no wrong effect, but lost service. |
| `blocked` | The mutant acted where the reference declined, and the kernel rejected it. No harm. |

**Mutant class.** A mutant takes its worst class, in the order `accepted` > `lost` > `blocked`. A mutant with no divergence in the simulator is `silent`. Silent mutants are split by whether the property checks fail.

**Predictions.** These shares are of mutants that diverge in the simulator.

| Measure | Prediction |
|---|---|
| `accepted` (harmful but valid) | about 30% |
| `lost` (fail-closed) | about 50% |
| `blocked` (fully contained by the kernel) | about 20% |
| Fully contained by the kernel | under 50% |
| Mutants that break safety (S1–S6) | 0 |
| Mutants that break progress (P1–P4) | 0 |
| Diverging mutants failing at least one property check | 90% or more |

**Reading.** If fully contained is under 50%, the kernel does not contain most planner bugs. The safety claim can still hold if `accepted` mutants break no safety invariant. But planner changes would still need behavioural evidence for most bugs. That would weaken the claim that planner changes can rely on the kernel for most of their assurance.

## Cases required by the review (later phases)

| ID | Case | Phase |
|---|---|---|
| R01 | An invalid plan that the kernel rejects | 0 (PB01, PB03, PB05, PB06, PB08) |
| R02 | A harmful plan that satisfies the initial kernel invariants | 0 (PB02, PB04, PB16) |
| R03 | A useful feature that requires changing a shared invariant | 1 (F05, F09, F14) |
| R04 | Two binding updates to disjoint slots with conflicting read assumptions (write skew) | 3 |
| R05 | A feature that requires activating two versions together | 3 (e.g. F05: refund planner and refund move together) |
| R06 | A property whose interpretation changes while its top-level text stays the same (gross vs net "amount paid") | 2 (arrives with F04 or F05) |
| R07 | A wrong implementation and an independently written test that share the same misunderstanding | 2 |
| R08 | A legitimate test change that strengthens the contract | 2 |
| R09 | A remote effect that succeeds before its acknowledgement is lost | 0 (fault `lost_after`, exercised by KB02 and KB03) |
| R10 | An old workflow still running when its version appears unused | 3 |
