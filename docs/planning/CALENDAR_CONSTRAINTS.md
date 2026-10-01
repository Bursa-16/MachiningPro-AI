# PLANNING-01F — Calendar / Shift / Maintenance Constraints

Status: **PLANNING-01F adds finite-capacity calendar awareness to the
existing scheduler, but does NOT yet implement setup/changeover,
rescheduling, a frozen horizon, tool/fixture/operator/material capacity
constraints, or a UI.** This is backend planning logic only.

## Architecture

```
Routing (+ caller-supplied Operation map, duration map, MachineCatalog,
          optional machine_id -> ResourceCalendar map, optional horizon_end)
    -> resolve_routing_eligibility()          backend.planning.routing        (PLANNING-01D)
    -> resolve_machine_calendars()            backend.planning.calendar_constraints (this ticket,
       + to_solver_availability()                                              only when calendar-aware)
    -> SolverOperation / SolverProblem        backend.planning.solver_models  (PLANNING-01B, extended)
       (+ SolverAvailabilityWindow / machine_availability)
    -> optimizer_adapter.solve() [or a        backend.planning.optimizer_adapter (PLANNING-01B, extended)
       caller-injected solve_fn]
    -> independent post-solve validation      backend.planning.scheduler      (PLANNING-01E, extended)
    -> ScheduleOperation / Schedule           backend.planning.models
    -> OptimizationResult                     backend.planning.models
```

`backend/planning/calendar_constraints.py` is the one new production
module. `scheduler.py`, `solver_models.py`, and `optimizer_adapter.py` were
extended (not redesigned) to carry calendar data through the existing
pipeline. `models.py`, `eligibility.py`, `routing.py`, and `__init__.py`
were not touched — no compatibility defect was found in any of them during
discovery.

## Design principle: eligibility vs. calendar availability

Kept strictly separate, per the ticket:

* **Eligibility** (PLANNING-01D, unchanged): *"Can this machine
  technically perform this operation?"* — capability only (operation
  type, spindle range, etc.).
* **Calendar availability** (this ticket): *"When can this
  already-eligible machine actually perform work?"* — shifts,
  maintenance, the horizon itself.

`calendar_constraints.py` never widens or narrows an eligible-machine set
and never inspects `Operation`/`Machine` capability fields. It only turns
`ResourceCalendar` data into usable time windows for machines that
eligibility has already approved.

## `ResourceCalendar` shape (confirmed by reading the real current source)

`ResourceCalendar` is not itself tied to one `machine_id` — it only
carries a `calendar_id`. Its `availability_windows` are generic (no
`machine_id` field), but each `MaintenanceWindow` inside
`maintenance_windows` carries its own `machine_id`. This lets one calendar
object be shared as a shift template across several machines while still
carrying machine-specific maintenance entries. Policy, made explicit
rather than left implicit:

* When resolving availability for a specific `machine_id` against a given
  `ResourceCalendar`, **all** of that calendar's `availability_windows`
  apply (they are not machine-scoped).
* Only the `maintenance_windows` whose own `machine_id` matches the
  machine being resolved are subtracted. A maintenance entry naming a
  *different* machine in a shared calendar is simply not applied here —
  not an error, just not this machine's concern (see
  `test_maintenance_for_a_different_machine_in_a_shared_calendar_is_not_applied`).

## Horizon model

PLANNING-01F adds an optional `horizon_end` parameter to
`schedule_routing`. Calendar-awareness is **opt-in and all-or-nothing**:

* Passing neither `machine_calendars` nor `horizon_end` reproduces
  PLANNING-01E's original behavior exactly — unbounded continuous
  availability, no calendar resolution performed, byte-identical results.
  Every PLANNING-01E test still passes unmodified.
* Passing only one of the two is rejected
  (`InvalidSolverProblemError`) rather than left ambiguous.
* Passing both enables calendar-aware scheduling. `horizon_end` must be
  timezone-aware and strictly after `horizon_start`.

**Two different "horizon_end" concepts, deliberately kept distinct:** the
caller-supplied `horizon_end` bounds calendar normalization and the CP-SAT
search space. The returned `Schedule.horizon_end` is still computed as
`horizon_start + solution.makespan` (the *achieved* makespan), exactly as
PLANNING-01E already documented — a schedule's own horizon describes the
schedule's own span, not the full search window offered to the solver.

## Timezone policy

Every datetime this ticket touches must be timezone-aware — this was
already true of `AvailabilityWindow`/`MaintenanceWindow`/`ResourceCalendar`
(PLANNING-01C) and of `horizon_start` (PLANNING-01E); `horizon_end` is
held to the same standard. A naive `horizon_start`/`horizon_end` is
rejected by `_require_tz_aware` before anything else runs. A naive
`AvailabilityWindow`/`MaintenanceWindow` datetime can never actually reach
`calendar_constraints.py` in the first place — those types already reject
a naive datetime at construction (PLANNING-01C), so there is no redundant
re-check for that case; the only reachable naive-datetime path in this
module is `horizon_start`/`horizon_end` themselves.

**Comparisons are by absolute instant, not by tzinfo object identity
(PLANNING-01F REVIEW FIX R1 note; no behavior change).** Every comparison
and subtraction in this module (`<=`, `<`, `-`) uses Python's native
`datetime` operators, which for two timezone-aware values compare/subtract
by absolute UTC instant regardless of which `tzinfo` object each side
carries or what offset it displays. A calendar window expressed in
`+02:00` and a horizon expressed in UTC are handled correctly against each
other without any explicit normalization step, because they are never
compared as anything other than absolute instants. This was verified
directly (a window given in a non-UTC offset produces the same normalized
result and the same solver-relative offsets as the UTC-equivalent window
would) — documented here for precision, not because any behavior needed
to change.

## Availability normalization

`normalize_machine_availability(calendar, machine_id, horizon_start,
horizon_end)` produces a deterministic, non-overlapping, horizon-clipped
tuple of `AvailabilityWindow` (the existing PLANNING-01C domain type —
reused, not reinvented) for one machine:

1. Clip every `availability_windows` entry to `[horizon_start,
   horizon_end)`; discard entries that clip to zero length or fall
   entirely outside the horizon (`test_availability_partially_outside_horizon_is_clipped`,
   `test_availability_entirely_outside_horizon_is_discarded`).
2. Merge overlapping *and touching* windows into maximal contiguous
   spans. Two windows that merely touch (`a.end == b.start`) are merged
   too — there is no real gap between them, so this is semantics-
   preserving, not a lossy simplification
   (`test_adjacent_touching_windows_merge_into_one`).
3. Subtract every `maintenance_windows` entry whose own `machine_id`
   matches, clipped to the horizon the same way (a maintenance window
   entirely outside the horizon is ignored;
   `test_maintenance_outside_horizon_is_ignored`,
   `test_maintenance_straddling_horizon_boundary_is_clipped`).
4. Sort deterministically by `(start, end)`.

**Reachability note, discovered while implementing this, not assumed
beforehand:** `ResourceCalendar.__post_init__` already rejects two
*availability* windows that overlap each other (PLANNING-01C's own
invariant), and clipping to the horizon is monotonic (it can only shrink
or discard a window, never grow one). So step 2's "overlap" handling can
never actually be exercised through the one real caller
(`normalize_machine_availability`) against a real `ResourceCalendar` —
only the "touching" case is reachable in practice. The general merge
algorithm still handles true overlap correctly, verified directly against
the private helper rather than through a real calendar
(`test_overlapping_availability_windows_merge`); this matters only if a
future caller ever builds windows some other way.

## No-calendar policy

An eligible machine with no entry in the caller-supplied
`machine_id -> ResourceCalendar` mapping is **continuously available for
the entire `[horizon_start, horizon_end)` window** — not unavailable, not
an error. This is the recommended policy the ticket asked for, made
explicit and tested directly
(`test_no_calendar_entry_is_continuously_available`,
`test_resolve_machine_calendars_covers_every_requested_machine`).

## No operation splitting (non-preemption)

An operation is atomic. It either fits entirely inside one single
availability window on one machine, or that machine cannot be used for
it — never split across two windows or two shifts
(`test_6_operation_cannot_span_closed_gap`). This is enforced inside the
CP-SAT model itself (see "Solver constraint mapping" below), not merely
checked after the fact.

## Solver constraint mapping

`SolverProblem` gained an optional `machine_availability: Mapping[str,
tuple[SolverAvailabilityWindow, ...]]` field (default: empty mapping,
meaning fully calendar-unaware — byte-identical to PLANNING-01B/01E).
`SolverAvailabilityWindow(start_offset, end_offset)` is solver-relative
(integer seconds from `horizon_start`), immutable, validated, contains no
`datetime` and no OR-Tools types.

Inside `optimizer_adapter.solve()`, for each (operation, eligible machine)
pair that has a `machine_availability` entry:

* Windows shorter than the operation's duration are filtered out first
  (non-preemption: the operation could never fit there regardless of
  where it starts).
* If **no** window on that machine is even long enough, that machine is
  excluded from the operation's candidate pool entirely — not
  constrained to an always-false choice, simply never offered. This
  keeps the model small and turns "no machine can do this" into a clean,
  provable CP-SAT `INFEASIBLE` rather than a constraint CP-SAT has to
  discover is always false.
* Otherwise, one boolean "window chosen" variable is created per usable
  window, tied via `OnlyEnforceIf` to `start >= window.start_offset` and
  `end <= window.end_offset`; exactly one window is chosen if and only if
  that machine is chosen for the operation
  (`sum(window_vars) == machine_presence`).
* If *every* eligible machine ends up excluded for an operation, the
  model is forced globally infeasible via two contradictory constraints
  on a fresh variable (`model.Add(x == 1)` / `model.Add(x == 0)`) rather
  than calling `AddExactlyOne([])` (unsupported) or silently dropping the
  operation.
* A machine with **no** entry in `machine_availability` at all (as
  opposed to a present-but-empty tuple) is treated as fully
  calendar-unaware for that operation — this is exactly what keeps
  PLANNING-01B/01E's original model-building code path byte-for-byte
  unchanged when `machine_availability` is empty.

**Horizon bound fix (a real, necessary correction, not a style choice —
corrected again in PLANNING-01F REVIEW FIX R1, see below):** the
pre-existing `SolverProblem.horizon_seconds` property (sum of every
operation's duration) is a safe variable-domain upper bound only when no
calendar windows are in play. A calendar window can legitimately extend
far later than the sum of durations (e.g. a shift on a later day), so
`optimizer_adapter.solve()` needs a wider bound whenever calendar
constraints are in play.

**PLANNING-01F REVIEW FIX R1 — the bound must be a sum, not a max.** The
originally-shipped formula,
`max(problem.horizon_seconds, problem.max_machine_availability_end_seconds)`,
is **not sufficient** in general. The independent review that followed
PLANNING-01F's initial delivery found and confirmed a false-`INFEASIBLE`
case: a machine with **no** entry in `problem.machine_availability` at all
(fully calendar-unaware in the sense described above) is bounded only by
`horizon_seconds`, not by any window's `end_offset` — but if that machine's
operation is chained, by precedence, after a *different* operation that a
calendar window forces to run as late as
`max_machine_availability_end_seconds`, the successor's true required
completion time is `max_machine_availability_end_seconds` **plus** its own
share of `horizon_seconds`, not whichever of the two is larger. `max(...)`
silently truncated the CP-SAT variable domain in that case and produced a
false `INFEASIBLE` for a schedule that was actually solvable. The fix:

```
horizon = problem.horizon_seconds + problem.max_machine_availability_end_seconds
```

a sum, not a max. This is intentionally a looser bound than the tightest
possible one (it does not need to be tight, only sufficient) — it stays a
correct upper bound because the true worst case is "some operation is
pushed all the way to the latest point any calendar window could ever
place anything, and then up to the full remaining duration-sum of all
work is serialized after it." When `max_machine_availability_end_seconds`
is `0` (a fully calendar-unaware problem — the default, empty
`machine_availability` mapping), this reduces to exactly
`horizon_seconds`, so PLANNING-01B/01E's original behavior is unchanged
bit-for-bit.

**Why this was not caught by PLANNING-01F's own test suite:** every
PLANNING-01F test that goes through the public `schedule_routing()` API
happens not to trigger it, because `_build_solver_problem` /
`calendar_constraints.resolve_machine_calendars` always resolve **every**
eligible machine referenced by any operation into an explicit
`machine_availability` entry whenever calendar-awareness is enabled at
all (a "calendar-unaware" machine gets the documented continuous-
availability default, itself bounded to the caller's own `horizon_end` —
never a fully absent/unbounded entry). The vulnerable mixed state — some
machines with explicit calendar windows, others with no entry at all in
the same `SolverProblem` — is therefore unreachable through
`schedule_routing()` today, but it is an explicitly documented, allowed
`SolverProblem` construction (see `SolverProblem`'s own docstring: it
does not require full machine coverage), reachable by any direct caller
of `optimizer_adapter.solve()`/`SolverProblem`, including the test suite
and any future scheduler-layer change. The regression test added for this
fix (`test_scheduler.py`) therefore exercises `SolverProblem` and
`optimizer_adapter.solve()` directly — real domain objects, the real
CP-SAT adapter, no fake solver — rather than through `schedule_routing()`,
since that is the layer where the defect actually lives and is
observable.

## Post-solve validation

PLANNING-01E's `_validate_solver_solution` already independently
re-verifies a solver result (duplicate/missing/unknown operations,
machine registration, eligibility membership, timing, duration,
precedence, no-overlap, makespan consistency) before trusting it. This
ticket adds exactly one more check, gated on calendar-aware mode: every
assignment's **absolute** `[start, end)` (`horizon_start + offset`) must
lie entirely inside one of that machine's *normalized* availability
windows (the same windows used to build the solver model, threaded
through rather than re-derived).

This single check subsumes three of the ticket's named concerns at once,
by construction rather than by coincidence: a normalized window is
already maintenance-subtracted and horizon-clipped, so "inside a
normalized window" already means "not overlapping maintenance" and "not
outside the horizon" — there is nothing left for a separate check to
catch that this one would miss. Verified directly with two adversarial
`solve_fn` tests: one assignment placed entirely outside the raw calendar
(`test_23_post_solve_validation_rejects_assignment_outside_availability`),
and one placed inside the raw availability window but squarely inside a
maintenance-carved gap
(`test_24_post_solve_validation_rejects_maintenance_overlap`) — the
second specifically proves the check catches a maintenance overlap, not
merely a generic mismatch.

## Infeasibility semantics

A `SolverProblem` where every eligible machine is excluded for some
operation (no window fits) makes CP-SAT itself report `INFEASIBLE` — no
manual pre-check duplicates this. `OptimizationResult.schedule` is
`None` whenever `status` is `INFEASIBLE`, exactly as the domain model's
own invariant already requires; no calendar-aware code path ever
fabricates a schedule (`test_17_operation_longer_than_every_window_is_infeasible`,
`test_22_all_eligible_machines_unavailable_is_infeasible_not_fabricated`).

## Determinism

Calendar-aware scheduling has exactly the same determinism story as
PLANNING-01E: given the same routing, operations, durations, catalog,
calendars, horizon, and an explicit `created_at`, with
`SolverConfig(num_workers=1, random_seed=<fixed>)`, three repeated calls
produce an identical `Schedule`
(`test_25_deterministic_repeated_scheduling_with_calendars`).

## Fail-closed behavior

| Condition | Exception |
| --- | --- |
| naive `horizon_start` / `horizon_end` | `InvalidSolverProblemError` |
| `horizon_end` not strictly after `horizon_start` | `InvalidSolverProblemError` |
| only one of `machine_calendars` / `horizon_end` supplied | `InvalidSolverProblemError` |
| `machine_calendars` is not a `Mapping` | `InvalidCalendarError` |
| `machine_calendars` key not registered in `machine_catalog` | `InvalidCalendarError` |
| `machine_calendars` value is not a `ResourceCalendar` | `InvalidCalendarError` |
| malformed availability/maintenance window | impossible to construct — `AvailabilityWindow`/`MaintenanceWindow` already reject this at construction (PLANNING-01C) |
| operation duration longer than every usable window on a machine | that machine excluded from the candidate pool; `INFEASIBLE` if this happens to every eligible machine |
| solver assignment outside availability, or overlapping maintenance | `SchedulerResultValidationError` (post-solve) |

Nothing here is silently repaired, widened, or defaulted.

## Test coverage

`tests/unit/planning/test_calendar_constraints.py` (25 tests): pure unit
tests of `normalize_machine_availability`, `resolve_machine_calendars`,
and `to_solver_availability` — clipping, merging, maintenance
subtraction, the no-calendar policy, fail-closed mapping validation, and
the worked example from the ticket reproduced exactly.

`tests/unit/planning/test_scheduler.py` (20 new tests, on top of
PLANNING-01E's original 32, all of which still pass unmodified): full
`schedule_routing` integration against the real CP-SAT adapter for every
numbered scenario in the ticket (continuous-availability parity, single
and multi-shift placement, shift-boundary containment, the closed-gap
non-preemption case, maintenance avoidance, infeasibility cases,
precedence/non-overlap regression checks under calendars, alternative-
machine selection, and calendar-aware determinism), plus two adversarial
`solve_fn` tests targeting the post-solve validation layer specifically.

## Deferred scope

Not implemented by this ticket: sequence-dependent setup/changeover
(`SetupMatrix` exists but is not integrated), tool/fixture/operator/
material capacity constraints, rescheduling, a frozen horizon, MRP, and
any UI (Gantt, planner dashboard, calendar editor, shift editor,
maintenance UI). None of these are claimed as supported here.
