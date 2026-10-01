"""Production planning / APS domain-model foundation (Stage 4 — PLANNING-01C).

This package defines the immutable planning domain layer only. It does NOT
implement a scheduler or an OR-Tools/solver adapter (those are later stages,
PLANNING-01E/01B per the PLANNING-01A roadmap) and does NOT implement any
UI. See ``docs/planning/PLANNING_DOMAIN_MODEL.md`` for full scope, the
MRP/APS boundary, and what is intentionally not implemented yet.

Exports
-------
Enums:      :class:`JobPriority`, :class:`MissingTransitionPolicy`,
            :class:`ScheduleOperationStatus`, :class:`OptimizationStatus`
Entities:   :class:`Job`, :class:`WorkOrder`, :class:`SchedulingOperation`,
            :class:`Routing`, :class:`AvailabilityWindow`,
            :class:`MaintenanceWindow`, :class:`ResourceCalendar`,
            :class:`SetupMatrix`, :class:`ToolRequirement`,
            :class:`FixtureRequirement`, :class:`MaterialRequirement`,
            :class:`ScheduleOperation`, :class:`Schedule`, :class:`Scenario`,
            :class:`OptimizationResult`
Exceptions: :class:`PlanningError`, :class:`UnknownSetupTransitionError`,
            :class:`UnknownOperationError`, :class:`InvalidMachineRecordError`,
            :class:`OperationIdentityMismatchError`

Stage 4 — PLANNING-01D adds the machine-eligibility layer:
Eligibility: :class:`EligibilityDiagnosticCode`, :class:`EligibilityResult`,
            :func:`resolve_eligible_machines`,
            :func:`resolve_routing_eligibility`
"""

from backend.planning.eligibility import (
    EligibilityDiagnosticCode,
    EligibilityResult,
    resolve_eligible_machines,
)
from backend.planning.exceptions import (
    InvalidMachineRecordError,
    OperationIdentityMismatchError,
    PlanningError,
    UnknownOperationError,
    UnknownSetupTransitionError,
)
from backend.planning.models import (
    AvailabilityWindow,
    FixtureRequirement,
    Job,
    JobPriority,
    MaintenanceWindow,
    MaterialRequirement,
    MissingTransitionPolicy,
    OptimizationResult,
    OptimizationStatus,
    ResourceCalendar,
    Routing,
    Scenario,
    Schedule,
    ScheduleOperation,
    ScheduleOperationStatus,
    SchedulingOperation,
    SetupMatrix,
    ToolRequirement,
    WorkOrder,
)
from backend.planning.routing import resolve_routing_eligibility

__all__ = [
    "AvailabilityWindow",
    "EligibilityDiagnosticCode",
    "EligibilityResult",
    "FixtureRequirement",
    "InvalidMachineRecordError",
    "Job",
    "JobPriority",
    "MaintenanceWindow",
    "MaterialRequirement",
    "MissingTransitionPolicy",
    "OperationIdentityMismatchError",
    "OptimizationResult",
    "OptimizationStatus",
    "PlanningError",
    "ResourceCalendar",
    "Routing",
    "Schedule",
    "ScheduleOperation",
    "ScheduleOperationStatus",
    "SchedulingOperation",
    "Scenario",
    "SetupMatrix",
    "ToolRequirement",
    "UnknownOperationError",
    "UnknownSetupTransitionError",
    "WorkOrder",
    "resolve_eligible_machines",
    "resolve_routing_eligibility",
]
