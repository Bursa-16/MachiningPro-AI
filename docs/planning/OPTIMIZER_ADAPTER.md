# PLANNING-01B — OR-Tools CP-SAT Optimizer Adapter Foundation

Status: solver-adapter foundation only. **This is not yet the full
production scheduler.** No UI, no resource calendars, no setup matrix, no
tool/fixture/material constraints, no frozen horizon, no rescheduling, no
multi-objective optimization, and no fallback solver are implemented here —
those are later stages.

## Why CP-SAT

The planning domain (`backend/planning/models.py`) is finite-capacity
scheduling data with alternative-machine assignment, precedence, and a
non-overlap requirement per machine — a classic resource-constrained
project-scheduling / job-shop shape. OR-Tools CP-SAT is a constraint
programming solver purpose-built for exactly this class of problem
(interval variables, `AddNoOverlap`, alternative optional intervals), is
free of per-seat licensing (unlike Gurobi), and is more directly suited to
this combinatorial, precedence-heavy problem than a general MILP solver
(PuLP + an open MILP backend) would be for the same formulation. No
fallback solver (PuLP/Gurobi) is added in this stage — CP-SAT's adapter
architecture is proven first; a fallback is a later ticket only if actually
needed.

## Dependency

`pyproject.toml` adds:

```toml
"ortools>=9.10,<10",
```

as a runtime dependency (not `dev`), since the adapter is production code,
not a test-only tool. No `gurobipy`, no `pulp`.

## Adapter boundary

`backend/planning/optimizer_adapter.py` is the **only** module in
`backend/planning` allowed to import `ortools`. `backend/planning/models.py`
and `backend/planning/solver_models.py` remain solver-neutral — this is
enforced by tests (`test_solver_models_module_does_not_import_ortools`,
`test_planning_models_module_does_not_import_ortools`), which check for an
actual `import`/`from ortools` statement rather than just the substring
`"ortools"`, since both modules' docstrings legitimately *describe* this
boundary rule in prose.

```
Planning domain (SchedulingOperation, Routing, EligibilityResult, ...)
    -> caller converts to solver-neutral input (not implemented in this
       stage — left to the caller / a later scheduler stage)
    -> SolverProblem / SolverConfig      (backend.planning.solver_models)
    -> optimizer_adapter.solve(...)      (backend.planning.optimizer_adapter,
                                           the only ortools import point)
    -> SolverSolution                    (backend.planning.solver_models)
    -> planning scheduler (later stage)
```

`SolverOperation` is a deliberately narrow, new dataclass — it does not
reuse or duplicate `SchedulingOperation`. It carries only what the solver
needs: `operation_id`, `duration`, `eligible_machine_ids`,
`predecessor_operation_ids`.

## Solver-neutral input/output models

Defined in `backend/planning/solver_models.py`:

- `SolverConfig` — immutable: `time_limit_seconds`, `num_workers`,
  `random_seed`, `log_search_progress`. Defaults are deterministic
  (`num_workers=1`, fixed `random_seed=0`). Raising `num_workers` above 1
  enables CP-SAT's parallel portfolio search, which is not guaranteed
  deterministic — callers that need repeatable solves should keep the
  default.
- `SolverOperation` — `operation_id`, `duration: timedelta`,
  `eligible_machine_ids: tuple[str, ...]`, `predecessor_operation_ids: tuple[str, ...]`.
  Validated at construction (non-empty ID, positive whole-second duration,
  non-empty deduplicated eligible-machine set, no self-predecessor).
- `SolverProblem` — an immutable, validated collection of `SolverOperation`.
  Normalizes operation order to a deterministic sort by `operation_id`
  regardless of the order the caller supplied them in, rejects duplicate
  operation IDs and unknown-predecessor references, and runs an explicit
  cycle check (see below) before any model is built.
- `SolverAssignment` — `operation_id`, `machine_id`, `start: timedelta`,
  `end: timedelta`. No OR-Tools types.
- `SolverSolution` — `status: OptimizationStatus`, `assignments`,
  `makespan: timedelta | None`, `objective_value: Decimal | None`,
  `solve_time_seconds: float`. Assignments are sorted deterministically by
  `operation_id`.

## Time-unit policy

CP-SAT requires integer decision variables. This adapter standardizes on
integer **seconds**.

- `timedelta_to_solver_seconds(duration)` — rejects non-positive durations
  and any duration that is not an exact whole number of seconds. There is
  **no silent truncation**: a 500ms duration raises
  `InvalidSolverProblemError` rather than being rounded to 0 or 1 second.
  Sub-second scheduling precision is out of scope for PLANNING-01B; a later
  stage can widen the unit (e.g. to deciseconds) if that precision is
  actually needed.
- `solver_seconds_to_timedelta(seconds)` — rejects negative values and
  non-`int` values (including `bool`, which is an `int` subclass in
  Python).

## Deterministic mode

`SolverConfig` defaults to `num_workers=1` with a fixed `random_seed`. The
adapter sets `solver.parameters.num_search_workers`,
`.random_seed`, and `.max_time_in_seconds` directly from the config before
calling `Solve()`. `test_deterministic_repeated_solve` solves the same
`SolverProblem` three times under the default config and asserts identical
`status`, `makespan`, `objective_value`, and `assignments` every time.

## Status mapping

| CP-SAT status         | `OptimizationStatus` | Notes |
| ---------------------- | --------------------- | ----- |
| `cp_model.OPTIMAL`     | `OPTIMAL`             | proven optimal |
| `cp_model.FEASIBLE`    | `FEASIBLE`            | a feasible incumbent exists; optimality not proven (this includes a time-limited solve that *did* find a solution — CP-SAT itself reports `FEASIBLE`, not `UNKNOWN`, in that case) |
| `cp_model.INFEASIBLE`  | `INFEASIBLE`          | proven infeasible |
| `cp_model.MODEL_INVALID` | `ERROR`             | malformed model |
| `cp_model.UNKNOWN`     | `TIME_LIMIT`          | solver terminated with **no** feasible solution found and infeasibility not proven — see below |

`cp_model.UNKNOWN` is mapped to `TIME_LIMIT` only as this adapter's
interpretation of "no proven feasible solution before solver termination."
It is **never** mapped to `FEASIBLE` or `OPTIMAL` — CP-SAT itself already
distinguishes "found a solution" from "found nothing yet," and this adapter
preserves that distinction rather than optimistically upgrading it. An
unrecognized status integer (e.g. from a future OR-Tools release) raises
`SolverExecutionError` rather than being guessed at.

`map_cp_sat_status()` is exported and tested directly
(`test_status_mapping_explicit`, `test_status_mapping_rejects_unknown_value`).

## Machine assignment model

For each operation, one `NewOptionalIntervalVar` is created per entry in
`eligible_machine_ids`, gated by a per-(operation, machine) `BoolVar`.
`AddExactlyOne` over those booleans forces exactly one eligible machine to
be selected — never zero, never more than one, and never a machine outside
`eligible_machine_ids` (there is no variable for an ineligible machine, so
CP-SAT structurally cannot assign one).

## `AddNoOverlap` behavior

All optional intervals sharing the same `machine_id` (across every
operation eligible for that machine) are collected into one list and passed
to a single `AddNoOverlap` call for that machine. Only intervals whose
presence boolean is true are enforced by CP-SAT's semantics, so an
operation not assigned to a given machine does not constrain that machine's
timeline.

## Precedence handling

For every `(predecessor, operation)` pair, `end[predecessor] <= start[operation]`
is added directly as a linear constraint on the shared `start`/`end`
integer variables — independent of which machine either operation is
ultimately assigned to.

### Cycle validation

The precedence graph is validated for cycles by an explicit, deterministic
DFS (white/gray/black coloring, visiting operations and their predecessor
lists in sorted-ID order) inside `SolverProblem.__post_init__`, **before**
any CP-SAT model is built. A cycle raises `PrecedenceCycleError`. This
adapter does not rely on CP-SAT to expose a cycle indirectly via
`INFEASIBLE`, since that would conflate "the input graph is malformed" with
"the schedule is genuinely infeasible for capacity reasons."

## Makespan objective

A single `makespan` integer variable is tied to every operation's `end` via
`AddMaxEquality`, and `model.Minimize(makespan)` is the sole objective. No
tardiness, setup, or utilization objective is introduced in this stage.

## Horizon

The scheduling horizon is derived as the sum of every operation's duration
in seconds (`SolverProblem.horizon_seconds`) — a safe upper bound, since
even a fully serial schedule with no parallelism at all finishes within
that many seconds. No arbitrary hardcoded constant is used.

## Fail-closed validation

Rejected before any model is built (all via `InvalidSolverProblemError`
unless noted):

- empty `SolverProblem` (zero operations)
- duplicate `operation_id`
- non-positive or lossily sub-second duration
- an operation with zero eligible machines
- duplicate eligible machine IDs on one operation
- a predecessor referencing an unknown `operation_id`
- a self-predecessor
- a precedence cycle (`PrecedenceCycleError`, a distinct subclass)
- an invalid `SolverConfig` (non-positive time limit, `num_workers < 1`,
  non-int `random_seed`, non-bool `log_search_progress`)

An unexpected failure while building or solving the model (as opposed to a
structural input defect caught above) raises `SolverExecutionError`, with
the original exception preserved via `raise ... from exc`.

## Raw solver type isolation

`SolverSolution`/`SolverAssignment` never carry a `CpModel`, `CpSolver`,
`IntVar`, `IntervalVar`, or `BoolVar`. `test_result_contains_no_raw_ortools_types`
checks every field's runtime type module does not start with `"ortools"`.

## Intentionally deferred (later stages)

Resource calendars, the setup matrix, tool/fixture/material constraints, a
frozen horizon, rescheduling, multi-objective optimization (tardiness,
setup, utilization), a fallback solver (PuLP/Gurobi), the production
scheduler itself, and any UI.

## Provenance note on this document

This design and its adapter/test/exception code were produced against the
actual `backend/planning/{models,eligibility,routing,exceptions,__init__}.py`
and `pyproject.toml` fetched from the public repository
`Bursa-16/MachiningPro-AI` at commit `deeb36bca23e801bccbb5d40dd226150ab2247e4`
(verified to match `main`'s tip for at least one fetched file at review
time). The adapter, `solver_models.py`, the exceptions addition, and the
test suite were exercised with real `pytest`/`ruff` runs inside an isolated
sandbox reconstructed from those fetched files plus their verified
transitive dependencies (`backend/domain/{base,exceptions,enums,units}.py`)
— **not** inside the full original repository, which was never directly
accessible in this session. See the accompanying report for exactly which
checks were run for real versus which (e.g. `git diff --check` against the
real git history, the full `tests/unit` suite, the known
`test_population.py` defect) could not be executed without that access.
