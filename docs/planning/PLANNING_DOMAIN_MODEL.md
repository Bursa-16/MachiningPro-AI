# Planning Domain Model (Stage 4 — PLANNING-01C)

Status: **domain model only**. No scheduler, no solver adapter, no UI. This
document describes `backend/planning/models.py` as it exists after
PLANNING-01C, and the boundaries the next stages (per the PLANNING-01A
roadmap: PLANNING-01B/D/E/F/G/H/I) must respect.

## APS scope

This module lays the data foundation for future **finite-capacity, job/
operation-level scheduling** (Advanced Planning & Scheduling): which
operation runs on which specific machine, starting when, in what order,
respecting setup/changeover, calendars, and precedence. It answers the gap
identified by the governing audit, **PLANNING-01A** (OptiFactory Scheduling
Engine Audit + MachiningPro Integration Design): OptiFactory itself solves a
different, *aggregate* Sales & Operations Planning problem (period-level
make/sell/store quantities, machines treated as interchangeable capacity
pools) and has no job, operation, precedence, calendar, setup, or
rescheduling concept at all. Its code was **not** reused here — see
PLANNING-01A's own Phase 1–7 findings for the full comparison. Only its
architectural *evidence* (what a real APS problem needs) informed this
design.

## MRP boundary

Per PLANNING-01A Phase 10's recommendation, **APS comes first, MRP later**.
This module includes `MaterialRequirement` as a forward-compatible
placeholder (material_id, quantity, quantity_unit, required_by) but
implements **no BOM explosion, no inventory ledger, and no purchasing
logic**. A future MRP integration (PLANNING-01H) consumes
`MaterialRequirement` records as a feasibility gate on the schedule; it does
not require any change to this module's other entities.

## Entity relationships

```
Job ──1:N── WorkOrder ──references──> ProcessPlan (existing, by process_plan_id)
                │
                └─1:N── SchedulingOperation ──references──> Operation (existing, by operation_id)
                              │
                              ├── eligible_machine_ids ──references──> Machine (existing, via MachineCatalog)
                              ├── predecessor_operation_ids ──(self-referential within a WorkOrder's operations)
                              ├── ToolRequirement (references Tool, existing, by tool_id)
                              ├── FixtureRequirement (references an opaque fixture_id — no fixture
                              │                        catalog exists yet, per PLANNING-01A Phase 6)
                              └── MaterialRequirement (future MRP integration point)

Routing.from_process_plan(plan) ──derives from──> ProcessPlan.ordered_steps / predecessor_step_ids
                                                    (never a second independent routing truth)

ResourceCalendar ──1:N── AvailabilityWindow
                 └─1:N── MaintenanceWindow (per machine_id)

SetupMatrix (per machine_id) ──lookup(from_key, to_key)──> timedelta

Scenario ──references (by ID only)──> Job, WorkOrder, ResourceCalendar
         └── locked_operation_ids, frozen_horizon_end  (what-if / rescheduling config)

OptimizationResult ──references──> Scenario (by scenario_id)
                    └── schedule: Schedule | None  (see the status/schedule invariant below)

Schedule ──1:N── ScheduleOperation ──references──> SchedulingOperation (by operation_id), Machine (by machine_id)
```

## Existing MachiningPro entities reused (never duplicated)

| Existing entity | Module | How the planning layer references it |
|---|---|---|
| `Operation` | `backend.domain.operation` | `SchedulingOperation.operation_id` |
| `Machine` | `backend.domain.machine` | `SchedulingOperation.eligible_machine_ids`, `ScheduleOperation.machine_id`, `MaintenanceWindow.machine_id`, `SetupMatrix.machine_id` (all plain ID references — machine eligibility itself is computed by the existing `backend.machines.catalog.MachineCatalog.find_by_operation()`, not re-derived here) |
| `ProcessPlan` / `ProcessPlanStep` | `backend.process_planning.models` | `WorkOrder.process_plan_id`; `Routing.from_process_plan(plan, routing_id)` derives ordering/precedence directly from the plan rather than re-authoring it |
| `Tool` | `backend.domain.tool` | `ToolRequirement.tool_id` |

None of these were re-implemented, subclassed, or given a competing field
set. The planning layer only ever stores their *IDs* plus the
scheduling-specific state they do not carry (timing, machine assignment,
lock/frozen-horizon status).

## Timezone strategy

Every stored timestamp across this module (`Job.release_date`/`due_date`,
`AvailabilityWindow.start`/`end`, `MaintenanceWindow.start`/`end`,
`ScheduleOperation` timestamps, `Schedule.horizon_start`/`horizon_end`/
`created_at`, `Scenario.frozen_horizon_end`, `ToolRequirement`/
`FixtureRequirement`/`MaterialRequirement` date fields) **must be a
timezone-aware `datetime`**. A naive datetime is rejected with
`ValidationError` at construction — there is no silent UTC-assumption
fallback. `ResourceCalendar.timezone` separately carries an IANA zone name
(validated against `zoneinfo`, e.g. `"Europe/Istanbul"`), used to interpret
that calendar's own shift/holiday semantics for display and any future
recurrence-rule expansion — it does not change how already-stored instants
compare to each other (comparisons are always instant-vs-instant,
independent of any calendar's display timezone).

## Unit strategy

Durations use `datetime.timedelta` exclusively — never a bare float
("hours") field. This mirrors the existing "no ambiguous bare numbers"
discipline `backend.domain.units.Quantity` already enforces for engineering
values. Where a value already has a canonical unit in
`backend.domain.units.Unit`, that `Quantity` type is the right choice (not
used directly by this module's fields, since none of them are that kind of
engineering quantity); `MaterialRequirement.quantity` uses `Decimal` with an
explicit, separate `quantity_unit: str` field because material-quantity
units (kg, pcs, m of bar stock, ...) have no canonical entry in `Unit` yet —
leaving that unit implicit would itself be exactly the ambiguity this
policy exists to prevent.

## Setup-matrix missing-transition policy

`SetupMatrix.lookup(from_setup_key, to_setup_key)` is an **exact-match
lookup only**. A missing entry is never inferred — not even a same-key
"no changeover" default. The chosen, deterministic policy is one of:

- **`MissingTransitionPolicy.NOT_ALLOWED`** (the default): raises
  `UnknownSetupTransitionError`. A matrix using this policy must not carry a
  `default_duration` (enforced at construction — a configured fallback that
  can never be reached would itself be a silent inconsistency).
- **`MissingTransitionPolicy.DEFAULT_FALLBACK`**: returns the matrix's
  explicitly configured `default_duration`. A matrix using this policy
  **must** set `default_duration` (enforced at construction).

## Invariants enforced by this module

- All frozen/immutable — every entity is `@dataclass(frozen=True, slots=True)`.
- Fail-closed validation — every entity's `__post_init__` rejects empty IDs,
  non-positive quantities/durations, naive datetimes, and reversed/zero-
  length intervals via `ValidationError`.
- No duplicate IDs inside an aggregate — `Routing.ordered_operation_ids`,
  `Schedule.operations` (by `operation_id`), and `Scenario`'s ID-tuple
  fields (`job_ids`, `work_order_ids`, `calendar_ids`,
  `locked_operation_ids`) all reject duplicates.
- No unknown local references — `Routing.precedence` rejects a predecessor
  ID that isn't also in `ordered_operation_ids`; `SchedulingOperation`
  rejects a self-referential predecessor.
- Deterministic ordering — `ResourceCalendar.availability_windows`/
  `maintenance_windows`, `SchedulingOperation.eligible_machine_ids`, and
  `Schedule.operations` are all stored sorted, regardless of construction
  order.
- `ResourceCalendar` rejects overlapping/duplicate `availability_windows`
  within one calendar, but explicitly *allows* `maintenance_windows` to
  overlap `availability_windows` (that is their purpose) while still
  rejecting exact-duplicate maintenance entries.
- `Schedule` rejects any operation whose interval falls outside its own
  `horizon_start`/`horizon_end`.
- `OptimizationResult` enforces that `INFEASIBLE`/`ERROR` results never
  carry a `schedule`, and `OPTIMAL`/`FEASIBLE` results always do —
  `TIME_LIMIT` may carry a best-found schedule or none. This is a
  mechanical self-consistency check only; it cannot and does not verify
  that a solver's `OPTIMAL` claim is actually optimal — that remains the
  solver stage's responsibility, not yet built.
- `Scenario.objective_configuration` accepts only JSON-safe primitive
  values (`str`/`int`/`float`/`bool`/`None`) — a solver object can never be
  smuggled through this field, keeping the module solver-neutral by
  construction as well as by import policy.
- No IDs are database-generated — every identifier is caller-supplied and
  validated as a non-empty string; nothing here talks to a database or
  generates a primary key.

## What is intentionally NOT implemented yet

- `Schedule` validates only structural/domain consistency: no duplicate
  `operation_id` entries, deterministic ordering, and every operation's
  interval falling inside `horizon_start`/`horizon_end`. It does **not**
  yet validate same-machine operation overlap (machine non-overlap
  feasibility) or cross-operation precedence feasibility. This is an
  intentional architecture separation, not a missing accidental check —
  those are solver/scheduling *feasibility* constraints, and are deferred
  to **PLANNING-01E — Finite-Capacity Scheduler / Constraint Validation**,
  which is also where they belong once locked operations, calendars, and
  setup/changeover all need to be reasoned about together. Do not assume
  `Schedule` already prevents double-booking a machine.
- No scheduler and no OR-Tools/Gurobi/PuLP solver adapter
  (`backend/planning/models.py` imports none of them, by design —
  PLANNING-01B/E).
- No duration *calculation* — `SchedulingOperation.duration_estimate` is an
  explicit caller-supplied `timedelta`; deriving it from
  `backend.machining` formulas/cutting parameters is deliberately deferred.
- No recurrence engine for `ResourceCalendar` (recurring weekly shifts,
  holiday rule expansion) — only explicit, already-expanded
  `AvailabilityWindow`/`MaintenanceWindow` instants.
- No inventory logic for `ToolRequirement`/`FixtureRequirement` (available
  quantity on hand, reservation, consumption).
- No fixture catalog — `FixtureRequirement.fixture_id` is an opaque
  identifier; MachiningPro has no fixture catalog today (PLANNING-01A,
  Phase 6), so none is invented here.
- No BOM explosion or purchasing logic for `MaterialRequirement`.
- No UI (Gantt, planning dashboard, etc.) — PLANNING-01F.
- No rescheduling *logic* — `Scenario.locked_operation_ids`/
  `frozen_horizon_end` are structural fields only; nothing yet consumes
  them to actually freeze part of a schedule during a re-solve
  (PLANNING-01G).
