"""Process planning: deterministic process-plan foundation (Stage 3J).

Stage 3J establishes the data contracts and validation layer for explicit,
traceable, human-reviewable process plans.  It composes results from all
prior stages:

* Stages 3A–3F: deterministic machining math (RPM, feed, MRR, time)
* Stage 3G: empirical cutting-parameter records (authority validation)
* Stage 3H: machine capability validation (RPM, feed, power, torque)
* Stage 3I: DFM / process-feasibility (geometry, process-feature compatibility)

Stage 3J does NOT generate, recommend, or select anything automatically.
All process decisions are explicit caller inputs.  Stage 3J validates them.

Exports
-------
:class:`PlanStatus`                — VALIDATED / INCOMPLETE / INVALID
:class:`ReviewStatus`              — NOT_REVIEWED / APPROVED / REJECTED
:class:`ProcessPlanStep`           — one explicit plan step (frozen)
:class:`ProcessPlan`               — ordered collection of steps (frozen)
:class:`ProcessPlanBuilder`        — deterministic builder
:func:`validate_step_ids`          — R-2801
:func:`validate_sequence_indexes`  — R-2802
:func:`validate_predecessors`      — R-2803
:func:`validate_acyclic`           — R-2804
:func:`validate_step_completeness` — R-2805
:func:`validate_step_dfm`          — R-2806
:func:`validate_step_machine_capability` — R-2807
:func:`validate_step_empirical_records`  — R-2808
:func:`aggregate_step_status`      — maps results to PlanStatus
:func:`aggregate_plan_status`      — R-2810
"""

from backend.process_planning.builder import ProcessPlanBuilder
from backend.process_planning.models import (
    PlanStatus,
    ProcessPlan,
    ProcessPlanStep,
    ReviewStatus,
)
from backend.process_planning.validation import (
    aggregate_plan_status,
    aggregate_step_status,
    validate_acyclic,
    validate_predecessors,
    validate_sequence_indexes,
    validate_step_completeness,
    validate_step_dfm,
    validate_step_empirical_records,
    validate_step_ids,
    validate_step_machine_capability,
)

__all__ = [
    "PlanStatus",
    "ProcessPlan",
    "ProcessPlanBuilder",
    "ProcessPlanStep",
    "ReviewStatus",
    "aggregate_plan_status",
    "aggregate_step_status",
    "validate_acyclic",
    "validate_predecessors",
    "validate_sequence_indexes",
    "validate_step_completeness",
    "validate_step_dfm",
    "validate_step_empirical_records",
    "validate_step_ids",
    "validate_step_machine_capability",
]
