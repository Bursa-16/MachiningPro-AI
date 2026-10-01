# PLANNING-01E — Finite-Capacity Scheduler Foundation

Status: **the first finite-capacity scheduling orchestration layer, not the
final production APS feature set.** No UI, no MRP, no sequence-dependent
setup/changeover, no tool/fixture/material capacity constraints, no
resource calendars or maintenance windows, no rescheduling, and no frozen
horizon are implemented here.

## Architecture flow

```
Routing (+ caller-supplied Operation map, duration map, MachineCatalog)
    -> resolve_routing_eligibility()        backend.planning.routing      (PLANNING-01D)
    -> SolverOperation / SolverProblem       backend.planning.solver_models (PLANNING-01B)
    -> optimizer_adapter.solve() [or a       backend.planning.optimizer_adapter (PLANNING-01B)
       caller-injected solve_fn]
    -> independent post-solve validation     backend.planning.scheduler   (this ticket)
    -> ScheduleOperation / Schedule          backend.planning.models
    -> OptimizationResult                    backend.planning.models
```

`backend/planning/scheduler.py` is the only new production file. It does
not modify `models.py`, `solver_models.py`, `optimizer_adapter.py`,
`eligibility.py`, `routing.py`, or `__init__.py` — no compatibility defect
was found in any of them during discovery, so none were touched.

## Domain / eligibility / solver boundaries

- **Domain layer** (`models.py`, `backend.domain.*`): unchanged, solver-
  neutral, untouched by this ticket.
- **Eligibility** (`eligibility.py`, `routing.py`, PLANNING-01D): reused
  exactly as-is via `resolve_routing_eligibility(routing, operations, machine_catalog)`.
  The scheduler does not re-derive or duplicate eligibility logic — a zero-
  eligible-machine operation is caught because
  `SolverOperation.__post_init__` already rejects an empty
  `eligible_machine_ids` tuple (PLANNING-01B), not because `scheduler.py`
  re-implements that check.
- **Solver layer** (`solver_models.py`, `optimizer_adapter.py`,
  PLANNING-01B): reused exactly as-is. `scheduler.py` builds a
  `SolverProblem` from resolved eligibility + caller-supplied durations +
  `routing.precedence`, then calls a `solve_fn` (defaulting to
  `optimizer_adapter.solve`) — see "Solver isolation" below.
- **This ticket** (`scheduler.py`): the only new code. It translates
  between the domain/eligibility layer and the solver layer, independently
  re-validates whatever the solver returns, and translates a validated
  result into `Schedule`/`OptimizationResult`.

## Solver isolation

`scheduler.py` contains no `import ortools` / `from ortools import ...`
line (checked directly by `test_scheduler_module_does_not_import_ortools`,
which inspects the module's own source rather than trusting that no one
added one later). It imports `backend.planning.optimizer_adapter` as a
module (to reference `optimizer_adapter.solve` as the default `solve_fn`)
but never touches `ortools` itself.

### The `solve_fn` seam

`schedule_routing(..., solve_fn=optimizer_adapter.solve)` accepts any
callable matching `(SolverProblem, SolverConfig) -> SolverSolution`. Tests
that need to exercise a malformed or adversarial solver result (a missing
operation, a duplicate assignment, an ineligible or unregistered machine, a
duration mismatch, a precedence violation, a same-machine overlap) inject a
small fake function here instead of monkeypatching CP-SAT internals. This
is also how a future alternative solver backend would be wired in without
changing `scheduler.py` itself.

## Duration input policy

`durations: Mapping[operation_id, timedelta]` is caller-supplied and
**never calculated here** — no cutting-formula or machining-time
derivation happens in this stage (same boundary
`SchedulingOperation.duration_estimate` already documents in
PLANNING-01C). Every operation referenced by `routing` must have exactly
one entry; a missing entry raises `InvalidSolverProblemError` before any
solver problem is built. Positivity and whole-second-precision validation
is not duplicated here — it is enforced once, by
`SolverOperation.__post_init__` (PLANNING-01B), when the duration is used
to construct that operation's `SolverOperation`. An extra, unreferenced key
in `durations` is not an error (harmless caller convenience, not
ambiguity) — only a *missing* key for a routed operation is rejected.

## Horizon policy

`horizon_start` must be timezone-aware (checked directly; naive datetimes
are rejected before anything else runs). PLANNING-01E schedules in
continuous finite-capacity time starting at `horizon_start` — there is
**no** calendar, shift, or maintenance-window awareness yet (see
"Intentionally deferred" below). `horizon_end` is always exactly
`horizon_start + solution.makespan` — never an arbitrary or padded
constant.

## Machine eligibility enforcement

Every `SolverOperation` is built with `eligible_machine_ids` taken directly
from that operation's `EligibilityResult` (PLANNING-01D) — never widened,
never guessed. The independent post-solve validation (below) re-checks
every returned assignment against that same eligible set, so even a
solver/`solve_fn` result that assigns an *ineligible* machine (one that
exists in the catalog but doesn't support the operation's type) is
rejected, not silently accepted because "some machine" was assigned.

## Precedence enforcement

Precedence for each operation comes directly from `routing.precedence.get(operation_id, ())`
— not re-derived or reinterpreted. It flows into `SolverOperation.predecessor_operation_ids`,
which `SolverProblem` already validates for unknown references, self-
reference, and cycles (PLANNING-01B). The independent post-solve validation
additionally re-checks, for every `(predecessor, operation)` pair in
`routing.precedence`, that the returned `predecessor.end <= operation.start`
in the assignments actually returned — this is not redundant with CP-SAT's
own precedence constraint, because a `solve_fn` used in a test (or, in
principle, a future alternative solver) could disagree with what CP-SAT
would have enforced.

## No-overlap enforcement

Independently re-checked (see below) by grouping the returned assignments
by `machine_id`, sorting each group by `start`, and confirming no
assignment's `end` exceeds the next one's `start` on the same machine —
again, not redundant with CP-SAT's `AddNoOverlap`, because this check
verifies the *result*, not the *model*.

## Independent post-solve validation

**A solver reporting `OPTIMAL` or `FEASIBLE` is evidence, not proof.**
Before `scheduler.py` ever constructs a `Schedule`, `_validate_solver_solution`
re-checks, purely from the returned `SolverSolution` and the original
problem/eligibility/duration data (no trust placed in the solver's internal
correctness):

1. every operation appears exactly once (no duplicates, no missing, no
   unknown operation IDs — three separate checks)
2. every assigned machine is registered in `machine_catalog`
   (`machine_catalog.has(...)`) — an unknown-machine check
3. every assigned machine is in that operation's eligible set
4. every assignment's `start >= 0` — the scheduler-specific, load-bearing
   half of this check. The paired `end > start` check is also still
   performed here, but only as cheap defense-in-depth:
   `SolverAssignment.__post_init__` (PLANNING-01B) already guarantees
   `end > start` unconditionally for any constructed `SolverAssignment`,
   so that half of the check can never actually fire — only `start >= 0`
   does real work at this layer.
5. every assignment's duration (`end - start`) matches the requested
   duration exactly
6. every `routing.precedence` edge is satisfied by the actual returned
   times
7. no two assignments on the same machine overlap
8. whenever `solution.assignments` is non-empty, the solver reported a
   **non-null** `makespan`, and that `makespan` matches the actual maximum
   assignment `end`. A `FEASIBLE`/`OPTIMAL` (or incumbent-carrying
   `TIME_LIMIT`) result with real assignments but `makespan=None` is
   rejected explicitly here — it is never assumed impossible and never
   allowed to reach schedule construction.

Any violation raises `SchedulerResultValidationError` — `scheduler.py`
never constructs a `Schedule` (or an `OptimizationResult` claiming one)
from a result that fails this check, regardless of what status the solver
itself reported. This fail-closed behavior never relies on Python's
`assert` statement, which can be stripped entirely under `python -O`:
every one of the 8 checks above raises `SchedulerResultValidationError`
explicitly, and `schedule_routing` performs no `assert` on solver-provided
data before building a `Schedule`.

## Deterministic behavior

`schedule_routing` takes no non-deterministic input of its own except one:
the wall-clock `created_at` timestamp defaults to "now" when omitted. Every
other input (the routing, operations, durations, machine catalog, solver
config) is caller-supplied and, given the same values plus the same
explicit `created_at`, `SolverConfig(num_workers=1, random_seed=<fixed>)`
(PLANNING-01B's own deterministic default) makes the underlying solve
itself deterministic. `test_deterministic_repeated_scheduling` calls
`schedule_routing` three times with identical inputs (including an explicit
`created_at`) and asserts the returned `Schedule` is exactly equal every
time.

## Solver status handling

| `SolverSolution.status` | Result |
| --- | --- |
| `OPTIMAL` | Validated, `Schedule` constructed, `OptimizationResult.schedule` is set. |
| `FEASIBLE` | Same as `OPTIMAL` — a feasible incumbent exists; not proven optimal, still validated and returned. |
| `INFEASIBLE` | `OptimizationResult.schedule = None`. Never fabricated. |
| `ERROR` | `OptimizationResult.schedule = None`. Never fabricated. |
| `TIME_LIMIT` **with** `solution.assignments` non-empty | Same validated path as `OPTIMAL`/`FEASIBLE`. |
| `TIME_LIMIT` **with** `solution.assignments` empty | `OptimizationResult.schedule = None`. |

**Precision note, as this ticket asked for:** under PLANNING-01B's current
adapter, `TIME_LIMIT` (mapped from `cp_model.UNKNOWN`) *always* carries
empty `assignments` — CP-SAT itself reports `FEASIBLE`, not `UNKNOWN`,
whenever it has found an incumbent, regardless of why it stopped searching.
So in practice, `TIME_LIMIT` here always resolves to `schedule=None` today.
`scheduler.py` still branches on `solution.assignments` rather than
hardcoding "`TIME_LIMIT` always means no schedule," so it does the right
thing automatically if a future adapter version's `TIME_LIMIT` ever does
carry a best-found incumbent — `test_time_limit_with_incumbent_is_validated_and_scheduled`
exercises exactly that (currently hypothetical) path via an injected
`solve_fn`.

## Result type: reused, not duplicated

This ticket does not introduce a new `SchedulerResult` type.
`backend.planning.models.OptimizationResult` already encodes exactly the
right invariant for this stage — `INFEASIBLE`/`ERROR` must not carry a
schedule, `OPTIMAL`/`FEASIBLE` must — and already exists in the domain
layer for a future solver stage to populate. `schedule_routing` returns
`OptimizationResult` directly. `objective_values` carries
`{"makespan_seconds": Decimal(...)}` when a schedule is produced,
`solve_time` is the solver's wall-clock time as a `timedelta`, and
`diagnostics` carries a short note when no schedule was produced.

`schedule_id`, `result_id`, and `scenario_id` are caller-supplied, not
invented — this layer does not add an ID-generation scheme (e.g. UUIDs),
which would also have undermined determinism.

## Fail-closed behavior

| Condition | Exception |
| --- | --- |
| `routing` is not a `Routing` | `PlanningError` (from `resolve_routing_eligibility`) |
| routed operation missing from `operations` | `UnknownOperationError` |
| `operations` entry's own ID disagrees with its key | `OperationIdentityMismatchError` |
| routed operation missing from `durations` | `InvalidSolverProblemError` |
| non-positive / lossy-sub-second duration | `InvalidSolverProblemError` (from `SolverOperation`) |
| zero eligible machines for an operation | `InvalidSolverProblemError` (from `SolverOperation`) |
| precedence cycle | `PrecedenceCycleError` (from `SolverProblem`) |
| malformed/adversarial solver result (any of the 8 post-solve checks) | `SchedulerResultValidationError` |

Nothing here is silently dropped, widened, defaulted, or coerced.

## Raw solver type isolation

`OptimizationResult`/`Schedule`/`ScheduleOperation` carry only domain types
(`str`, `datetime`, `timedelta`, `Decimal`, `OptimizationStatus`) — never a
`CpModel`/`CpSolver`/`IntVar`/`IntervalVar`/`BoolVar`, and never even a raw
`SolverAssignment`/`SolverSolution` (those are translated, not passed
through). Verified directly by `test_no_raw_ortools_types_in_result`.

## Intentionally deferred (later stages)

Resource calendars and maintenance windows (`ResourceCalendar` exists in
the domain model but is **not enforced** here — PLANNING-01E schedules in
continuous time starting at `horizon_start` only), sequence-dependent
setup/changeover (`SetupMatrix` exists but is **not integrated** here),
tool/fixture/material capacity constraints, rescheduling, a frozen horizon,
MRP, and any UI. None of these are claimed as supported by this ticket.
