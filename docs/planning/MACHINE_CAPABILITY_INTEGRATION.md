# Machine Capability Integration (Stage 4 — PLANNING-01D)

Status: **eligibility layer only**. No OR-Tools, no finite-capacity
scheduling, no UI. This document describes
`backend/planning/eligibility.py` and `backend/planning/routing.py` as they
exist after PLANNING-01D, and the boundary PLANNING-01E (the scheduler)
must respect.

## Eligibility architecture

PLANNING-01D adds one narrow capability: given an existing
`backend.domain.operation.Operation`, determine which registered machines
are engineering-feasible for it. The pipeline is:

```
Operation.operation_type
        |
        v
MachineCatalog.find_by_operation(operation_type)   <- existing Stage 3H code, unmodified
        |
        v
tuple(sorted(machine.machine_id for machine in candidates))
        |
        v
EligibilityResult(eligible_machine_ids=..., diagnostic_code=...)
```

`resolve_eligible_machines(operation, machine_catalog) -> EligibilityResult`
in `backend/planning/eligibility.py` is the whole of this pipeline. It adds
no new capability logic — it is an orchestration call into
`MachineCatalog.find_by_operation()`, wrapped in a deterministic, fail-closed
result object.

`backend/planning/routing.py`'s `resolve_routing_eligibility(routing,
operations, machine_catalog)` is a thin bridge that walks an existing
`Routing.ordered_operation_ids` (itself derived from a real `ProcessPlan` via
`Routing.from_process_plan()`, per PLANNING-01C — unchanged here), looks each
`operation_id` up in a caller-supplied `operations` mapping to get the real
`Operation`, and calls `resolve_eligible_machines()` for each, in routing
order. It does not calculate solver start times, does not perform
scheduling, and does not maintain its own Operation registry.

## Source-of-truth rule

The planning layer is **not** the source of truth for machine capability
and does not become one here. Source of truth remains:

* `backend.domain.machine.Machine` — the capability envelope itself.
* `backend.machines.catalog.MachineCatalog` — the registry and its
  `find_by_operation()` query.

`backend/planning/eligibility.py` contains **no** spindle-speed, power,
torque, feed-rate, or working-envelope logic of its own. It calls the
existing catalog query and nothing else. `test_real_machine_catalog_
actually_used` in `tests/unit/planning/test_eligibility.py` proves this by
registering a new machine into a live catalog mid-test and observing the
eligibility result change — it is reading live from the catalog, not from
any planning-local snapshot.

## Fail-closed behavior

* An `operation` that is not an actual `Operation` instance, or a
  `machine_catalog` that is not an actual `MachineCatalog` instance, is
  rejected with `PlanningError` — never silently coerced. This also means a
  "fake planning-local capability map" can never be substituted for the
  real catalog and still be accepted.
* Zero capable machines is an explicit, legitimate result
  (`EligibilityDiagnosticCode.NO_CAPABLE_MACHINE`, with
  `eligible_machine_ids == ()`), never silently widened to "every machine is
  eligible."
* A non-`Machine` record returned by the catalog raises
  `InvalidMachineRecordError` rather than being coerced or ignored. This is
  defense in depth: `MachineCatalog.register()` already enforces that only
  `Machine` instances are ever stored, so this path is unreachable through
  the real catalog today, but the check costs nothing and guards against a
  future or alternative catalog implementation that does not enforce the
  same guarantee.
* `resolve_routing_eligibility()` raises `UnknownOperationError` when a
  routing references an `operation_id` that is not a key in the supplied
  `operations` mapping — a reference-integrity failure, never silently
  skipped or treated as "no operations to check."

## Supported capability dimensions

| Dimension | Classification |
|---|---|
| Operation type (`Operation.operation_type` via `MachineCatalog.find_by_operation()`) | **USED_IN_01D** |
| Spindle speed range (`Machine.spindle_speed_min`/`max`, `backend.machines.validation.check_spindle_speed`) | AVAILABLE_BUT_NOT_USED |
| Spindle power (`Machine.spindle_power`, `check_power`) | AVAILABLE_BUT_NOT_USED |
| Spindle torque (`Machine.spindle_torque`, `check_torque`) | AVAILABLE_BUT_NOT_USED |
| Feed rate (`Machine.feed_rate_max`, `check_feed_rate`) | AVAILABLE_BUT_NOT_USED |
| Working envelope (`Machine.working_envelope`, `check_work_envelope_dimension`) | AVAILABLE_BUT_NOT_USED |
| Axis/configuration constraints beyond `axis_count` | NOT_AVAILABLE |
| Material/process constraints | NOT_AVAILABLE |

## Why only operation type is used

Every one of the "AVAILABLE_BUT_NOT_USED" checks in
`backend.machines.validation` (`check_spindle_speed`, `check_feed_rate`,
`check_power`, `check_torque`, `check_work_envelope_dimension`) requires an
explicit *requested value* supplied by the caller (`requested_rpm`,
`required_power`, etc.) — none of these values exist anywhere on
`Operation`, `ProcessPlanStep`, or `SchedulingOperation` today. They are
cutting-parameter values that would have to be derived from
`backend.domain.parameters.MachiningParameters` /
`backend.cutting_parameters.CuttingParameterRecord`, which in turn requires
machining-formula/cycle-time work. PLANNING-01D explicitly excludes that
(no cycle-time calculation, no machining-formula duplication), so those
dimensions remain "available but not used" rather than being invented here.
A future stage that adds cutting-parameter resolution can extend
`resolve_eligible_machines()` to also call these checks — using the exact
same `backend.machines.validation` functions, not a re-implementation.

"Axis/configuration constraints" beyond the plain `axis_count: int` field,
and any material/process compatibility beyond `operation_type`, have no
representation anywhere in the current `Machine` model, so they are
classified `NOT_AVAILABLE` rather than claimed.

## Deterministic ordering

`eligible_machine_ids` is always `tuple(sorted(...))` by `machine_id`,
computed independently of whatever ordering guarantee
`MachineCatalog.find_by_operation()` itself provides (which is already
sorted, but this module does not rely on that as an implementation detail
of another module).

## The `SchedulingOperation.eligible_machine_ids` field

PLANNING-01C's `SchedulingOperation.eligible_machine_ids` field is **not**
auto-populated by a factory/builder in this stage, and this module does not
build one. `EligibilityResult` is returned as a separate, standalone value
instead. Reasoning:

* Populating the field would require reconstructing a new
  `SchedulingOperation` (frozen dataclasses cannot be mutated in place),
  turning construction into an awkward two-phase process and creating two
  possible "sources of truth" for eligibility — the field's frozen,
  point-in-time snapshot, versus a live re-query of the catalog.
* Machine capability data can change after a `SchedulingOperation` is
  constructed (a machine is added, retired, or its capability record
  changes). A snapshot baked into a persisted planning entity would drift
  from the catalog silently. That directly conflicts with the architectural
  rule that the planning layer is not the source of truth for capability.
* Keeping eligibility as a freshly-computed, on-demand result means
  PLANNING-01E (the scheduler) always calls `resolve_eligible_machines()` /
  `resolve_routing_eligibility()` against the live catalog rather than
  trusting a potentially stale cached list.

`SchedulingOperation.eligible_machine_ids` remains what PLANNING-01C
defined it as: an optional, caller-supplied field (e.g. a caller's own
prior knowledge or override), not something this module reads, writes, or
depends on.

## ProcessPlan bridge

`resolve_routing_eligibility()` in `backend/planning/routing.py` walks
`Routing.ordered_operation_ids` (unchanged from PLANNING-01C — this module
does not re-derive ordering or precedence) and resolves eligibility for
each operation in that order, using a caller-supplied `operations` mapping
to go from `operation_id` to the real `Operation` instance. It preserves
operation identity, preserves the routing's own sequence, and does not
introduce a competing Operation registry.

## Scheduler boundary

Nothing in this stage assigns a machine to an operation, computes a start
or end time, or reasons about calendars, setup/changeover, or precedence
feasibility. `EligibilityResult` says only "these machines could run this
operation" — which one actually will, and when, is PLANNING-01E's job
entirely.

## What PLANNING-01D intentionally does NOT do

* No OR-Tools/Gurobi/PuLP solver adapter and no finite-capacity scheduling.
* No cycle-time or cutting-parameter derivation — `duration_estimate` (from
  PLANNING-01C) remains an explicit, caller-supplied value; nothing here
  computes one.
* No use of spindle speed, power, torque, feed rate, or working-envelope
  checks — see the capability-dimension table above.
* No UI.
* No factory/builder that populates
  `SchedulingOperation.eligible_machine_ids` — see that section above.
* No modification to `backend/domain/machine.py`,
  `backend/machines/catalog.py`, `backend/domain/operation.py`, or
  `backend/process_planning/**` — no compatibility defect was found in any
  of them during this stage.
