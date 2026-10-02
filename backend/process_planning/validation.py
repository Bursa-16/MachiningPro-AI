"""Deterministic process-plan validation (Stage 3J).

All validation functions return :class:`~backend.domain.result.EngineeringResult`
instances using the rule ID range R-2801 – R-2810.

Design
------
Stage 3J validation COMPOSES results from earlier stages:
  - Stage 3I DFM checks (geometry, process-feature compatibility)
  - Stage 3H machine capability checks
  - Stage 3G empirical data authority checks (via CuttingParameterRecord.is_authoritative)
  - Stage 3A–3F derived machining values

It does NOT duplicate any earlier-stage logic.

Fail-closed
-----------
Missing assignment     → INCOMPLETE  (data is absent — may be supplied later)
Failed DFM check       → INVALID     (physical violation)
Failed machine check   → INVALID     (capability violation)
Unverified empirical   → INCOMPLETE  (data exists but lacks authority)
Dependency cycle       → INVALID     (structural violation)
Duplicate step ID      → INVALID     (structural violation)
Duplicate sequence idx → INVALID     (structural violation)

Rule ID range: R-2801 – R-2810
"""

from __future__ import annotations

from collections import deque

from backend.cutting_parameters.models import CuttingParameterRecord
from backend.cutting_parameters.validation import is_usable_for_authority
from backend.domain.enums import ResultStatus
from backend.domain.feature import Feature
from backend.domain.machine import Machine
from backend.domain.result import (
    EngineeringResult,
    failure,
    insufficient_data,
    success,
)
from backend.domain.tool import Tool
from backend.domain.units import Quantity
from backend.process_planning.models import PlanStatus, ProcessPlanStep

__all__ = [
    "validate_step_ids",
    "validate_sequence_indexes",
    "validate_predecessors",
    "validate_acyclic",
    "validate_step_completeness",
    "validate_step_dfm",
    "validate_step_machine_capability",
    "validate_step_empirical_records",
    "aggregate_step_status",
    "aggregate_plan_status",
]

_VERSION = "1.0.0"


# ---------------------------------------------------------------------------
# R-2801 — Step ID uniqueness
# ---------------------------------------------------------------------------

def validate_step_ids(
    steps: tuple[ProcessPlanStep, ...],
) -> EngineeringResult:
    """R-2801: All step IDs within the plan must be unique."""
    rule_id = "R-2801"
    seen: set[str] = set()
    duplicates: list[str] = []
    for step in steps:
        if step.step_id in seen:
            duplicates.append(step.step_id)
        seen.add(step.step_id)
    if duplicates:
        return failure(
            result_id=f"{rule_id}.result",
            rule_id=rule_id,
            rule_version=_VERSION,
            violations=tuple(
                f"duplicate step_id: {sid!r}" for sid in duplicates
            ),
            summary=f"plan contains {len(duplicates)} duplicate step ID(s)",
        )
    return success(
        result_id=f"{rule_id}.result",
        rule_id=rule_id,
        rule_version=_VERSION,
        summary=f"all {len(steps)} step IDs are unique",
    )


# ---------------------------------------------------------------------------
# R-2802 — Sequence index uniqueness
# ---------------------------------------------------------------------------

def validate_sequence_indexes(
    steps: tuple[ProcessPlanStep, ...],
) -> EngineeringResult:
    """R-2802: All sequence_index values must be unique across steps."""
    rule_id = "R-2802"
    seen: set[int] = set()
    duplicates: list[int] = []
    for step in steps:
        if step.sequence_index in seen:
            duplicates.append(step.sequence_index)
        seen.add(step.sequence_index)
    if duplicates:
        return failure(
            result_id=f"{rule_id}.result",
            rule_id=rule_id,
            rule_version=_VERSION,
            violations=tuple(
                f"duplicate sequence_index: {idx}" for idx in duplicates
            ),
            summary=f"plan contains {len(duplicates)} duplicate sequence index(es)",
        )
    return success(
        result_id=f"{rule_id}.result",
        rule_id=rule_id,
        rule_version=_VERSION,
        summary=f"all {len(steps)} sequence indexes are unique",
    )


# ---------------------------------------------------------------------------
# R-2803 — Predecessor existence
# ---------------------------------------------------------------------------

def validate_predecessors(
    steps: tuple[ProcessPlanStep, ...],
) -> EngineeringResult:
    """R-2803: Every predecessor_step_id must reference a step that exists
    in the plan, and no step may declare itself as a predecessor.
    """
    rule_id = "R-2803"
    known_ids = {s.step_id for s in steps}
    violations: list[str] = []
    for step in steps:
        for pred_id in step.predecessor_step_ids:
            if pred_id == step.step_id:
                violations.append(
                    f"step {step.step_id!r} declares itself as a predecessor"
                )
            elif pred_id not in known_ids:
                violations.append(
                    f"step {step.step_id!r} references unknown predecessor "
                    f"{pred_id!r}"
                )
    if violations:
        return failure(
            result_id=f"{rule_id}.result",
            rule_id=rule_id,
            rule_version=_VERSION,
            violations=tuple(violations),
            summary=f"{len(violations)} predecessor reference(s) invalid",
        )
    return success(
        result_id=f"{rule_id}.result",
        rule_id=rule_id,
        rule_version=_VERSION,
        summary="all predecessor references are valid",
    )


# ---------------------------------------------------------------------------
# R-2804 — Acyclic dependency graph
# ---------------------------------------------------------------------------

def validate_acyclic(
    steps: tuple[ProcessPlanStep, ...],
) -> EngineeringResult:
    """R-2804: The predecessor dependency graph must be acyclic (DAG).

    Uses Kahn's algorithm (topological sort with in-degree queue).
    Assumes predecessor IDs have already been validated by R-2803.
    """
    rule_id = "R-2804"
    if not steps:
        return success(
            result_id=f"{rule_id}.result",
            rule_id=rule_id,
            rule_version=_VERSION,
            summary="empty plan — dependency graph is trivially acyclic",
        )

    # Build adjacency: successor → predecessors
    in_degree: dict[str, int] = {s.step_id: 0 for s in steps}
    adjacency: dict[str, list[str]] = {s.step_id: [] for s in steps}

    for step in steps:
        for pred_id in step.predecessor_step_ids:
            if pred_id in adjacency:  # guard against unknown (caught by R-2803)
                adjacency[pred_id].append(step.step_id)
                in_degree[step.step_id] += 1

    queue: deque[str] = deque(sid for sid, d in in_degree.items() if d == 0)
    processed = 0
    while queue:
        node = queue.popleft()
        processed += 1
        for successor in adjacency.get(node, []):
            in_degree[successor] -= 1
            if in_degree[successor] == 0:
                queue.append(successor)

    if processed != len(steps):
        cycle_members = [sid for sid, d in in_degree.items() if d > 0]
        return failure(
            result_id=f"{rule_id}.result",
            rule_id=rule_id,
            rule_version=_VERSION,
            violations=(
                f"circular dependency detected among steps: "
                f"{sorted(cycle_members)}",
            ),
            summary="dependency graph contains a cycle — plan is invalid",
        )

    return success(
        result_id=f"{rule_id}.result",
        rule_id=rule_id,
        rule_version=_VERSION,
        summary=f"dependency graph is acyclic ({len(steps)} steps)",
    )


# ---------------------------------------------------------------------------
# R-2805 — Step completeness (explicit assignments)
# ---------------------------------------------------------------------------

def validate_step_completeness(
    step: ProcessPlanStep,
    require_tool: bool = True,
    require_machine: bool = True,
) -> EngineeringResult:
    """R-2805: Verify that the step has all required explicit assignments.

    Missing assignments produce INSUFFICIENT_DATA (the data may be supplied
    later; this is not a physical failure).

    Args:
        step:           The plan step to check.
        require_tool:   Whether a tool_id is mandatory for this step.
        require_machine: Whether a machine_id is mandatory for this step.
    """
    rule_id = "R-2805"
    missing: list[str] = []

    if step.feature_id is None:
        missing.append("feature_id")
    if step.operation_type is None:
        missing.append("operation_type")
    if require_tool and step.tool_id is None:
        missing.append("tool_id")
    if require_machine and step.machine_id is None:
        missing.append("machine_id")

    if missing:
        return insufficient_data(
            result_id=f"{rule_id}.result",
            rule_id=rule_id,
            rule_version=_VERSION,
            missing_inputs=tuple(missing),
            summary=(
                f"step {step.step_id!r} is missing required assignments: "
                f"{', '.join(missing)}"
            ),
        )
    return success(
        result_id=f"{rule_id}.result",
        rule_id=rule_id,
        rule_version=_VERSION,
        summary=f"step {step.step_id!r} has all required assignments",
    )


# ---------------------------------------------------------------------------
# R-2806 — DFM feasibility acceptance
# ---------------------------------------------------------------------------

def validate_step_dfm(
    step: ProcessPlanStep,
    feature: Feature,
    tool: Tool,
) -> EngineeringResult:
    """R-2806: Run Stage 3I DFM checks for this step and report the result.

    Composes Stage 3I process-feature compatibility and tool geometry
    checks.  Does NOT duplicate Stage 3I logic.

    Returns:
        PASS              — all DFM checks pass.
        FAIL              — at least one DFM check fails.
        INSUFFICIENT_DATA — required data for DFM unavailable.
    """
    from backend.dfm.validation import (
        aggregate_feasibility,
        check_corner_radius_tool,
        check_hole_tool_diameter,
        check_pocket_access,
        check_process_feature_compatibility,
        check_slot_width_tool,
    )
    from backend.domain.enums import FeatureType

    rule_id = "R-2806"

    checks: list[EngineeringResult] = []

    # Process–feature compatibility (always)
    if step.operation_type is not None:
        checks.append(
            check_process_feature_compatibility(feature, step.operation_type)
        )

    # Geometry checks by feature type
    if feature.feature_type is FeatureType.HOLE:
        checks.append(check_hole_tool_diameter(feature, tool))
    elif feature.feature_type is FeatureType.SLOT:
        checks.append(check_slot_width_tool(feature, tool))
    elif feature.feature_type is FeatureType.POCKET:
        checks.append(check_pocket_access(feature, tool))
        # Corner radius if available
        if "corner_radius" in feature.dimensions:
            checks.append(check_corner_radius_tool(feature, tool))

    if not checks:
        return insufficient_data(
            result_id=f"{rule_id}.result",
            rule_id=rule_id,
            rule_version=_VERSION,
            missing_inputs=("dfm_checks",),
            summary=f"no DFM checks could be performed for step {step.step_id!r}",
        )

    agg = aggregate_feasibility(tuple(checks))

    # Rewrap with R-2806 ID
    if agg.status is ResultStatus.PASS:
        return success(
            result_id=f"{rule_id}.result",
            rule_id=rule_id,
            rule_version=_VERSION,
            summary=f"DFM checks passed for step {step.step_id!r}",
        )
    if agg.status is ResultStatus.FAIL:
        return failure(
            result_id=f"{rule_id}.result",
            rule_id=rule_id,
            rule_version=_VERSION,
            violations=agg.violations,
            summary=f"DFM check(s) failed for step {step.step_id!r}",
        )
    # WARNING treated as INSUFFICIENT_DATA at plan level (no authoritative pass)
    return insufficient_data(
        result_id=f"{rule_id}.result",
        rule_id=rule_id,
        rule_version=_VERSION,
        missing_inputs=agg.missing_inputs or ("dfm_data",),
        summary=f"DFM data incomplete for step {step.step_id!r}",
    )


# ---------------------------------------------------------------------------
# R-2807 — Machine capability acceptance
# ---------------------------------------------------------------------------

def validate_step_machine_capability(
    step: ProcessPlanStep,
    machine: Machine,
    requested_rpm: Quantity | None = None,
    requested_feed_rate: Quantity | None = None,
    required_power: Quantity | None = None,
    required_torque: Quantity | None = None,
) -> EngineeringResult:
    """R-2807: Run Stage 3H machine capability checks for this step.

    Only validates the quantities the caller explicitly supplies.
    Missing quantities → INSUFFICIENT_DATA.
    Any machine capability failure → FAIL.

    No duplication of Stage 3H rules.
    """
    from backend.dfm.validation import aggregate_feasibility, compose_machine_result
    from backend.machines.validation import (
        check_feed_rate,
        check_power,
        check_spindle_speed,
        check_torque,
    )

    rule_id = "R-2807"

    checks: list[EngineeringResult] = []

    if requested_rpm is not None:
        checks.append(compose_machine_result(check_spindle_speed(machine, requested_rpm)))
    if requested_feed_rate is not None:
        checks.append(compose_machine_result(check_feed_rate(machine, requested_feed_rate)))
    if required_power is not None:
        checks.append(compose_machine_result(check_power(machine, required_power)))
    if required_torque is not None:
        checks.append(compose_machine_result(check_torque(machine, required_torque)))

    if not checks:
        return insufficient_data(
            result_id=f"{rule_id}.result",
            rule_id=rule_id,
            rule_version=_VERSION,
            missing_inputs=("machine_capability_inputs",),
            summary=(
                f"no machine capability values supplied for step "
                f"{step.step_id!r}; cannot validate"
            ),
        )

    agg = aggregate_feasibility(tuple(checks))

    if agg.status is ResultStatus.PASS:
        return success(
            result_id=f"{rule_id}.result",
            rule_id=rule_id,
            rule_version=_VERSION,
            summary=f"machine capability checks passed for step {step.step_id!r}",
        )
    if agg.status is ResultStatus.FAIL:
        return failure(
            result_id=f"{rule_id}.result",
            rule_id=rule_id,
            rule_version=_VERSION,
            violations=agg.violations,
            summary=f"machine capability check(s) failed for step {step.step_id!r}",
        )
    return insufficient_data(
        result_id=f"{rule_id}.result",
        rule_id=rule_id,
        rule_version=_VERSION,
        missing_inputs=agg.missing_inputs or ("machine_capability_data",),
        summary=f"machine capability data incomplete for step {step.step_id!r}",
    )


# ---------------------------------------------------------------------------
# R-2808 — Empirical parameter record authority
# ---------------------------------------------------------------------------

def validate_step_empirical_records(
    step: ProcessPlanStep,
    records: tuple[CuttingParameterRecord, ...],
) -> EngineeringResult:
    """R-2808: Verify that all supplied empirical records are authoritative.

    Uses Stage 3G ``is_usable_for_authority()`` to check each record.
    Unverified or missing records produce INSUFFICIENT_DATA (the data
    may be replaced by verified records later).

    Args:
        step:    The plan step referencing these records.
        records: CuttingParameterRecord instances corresponding to
                 ``step.parameter_record_ids``.  Must not be empty when
                 empirical records are required.
    """
    rule_id = "R-2808"

    if not records:
        if step.parameter_record_ids:
            return insufficient_data(
                result_id=f"{rule_id}.result",
                rule_id=rule_id,
                rule_version=_VERSION,
                missing_inputs=tuple(step.parameter_record_ids),
                summary=(
                    f"step {step.step_id!r} references {len(step.parameter_record_ids)} "
                    "empirical record(s) but none were supplied for validation"
                ),
            )
        # No records required, none supplied — not a failure
        return success(
            result_id=f"{rule_id}.result",
            rule_id=rule_id,
            rule_version=_VERSION,
            summary=f"step {step.step_id!r} requires no empirical records",
        )

    non_authoritative: list[str] = []
    for record in records:
        if not is_usable_for_authority(record):
            non_authoritative.append(
                f"{record.record_id!r} (status: {record.evidence_status})"
            )

    if non_authoritative:
        return insufficient_data(
            result_id=f"{rule_id}.result",
            rule_id=rule_id,
            rule_version=_VERSION,
            missing_inputs=tuple(non_authoritative),
            summary=(
                f"step {step.step_id!r} has {len(non_authoritative)} "
                "non-authoritative empirical record(s)"
            ),
        )

    return success(
        result_id=f"{rule_id}.result",
        rule_id=rule_id,
        rule_version=_VERSION,
        summary=(
            f"all {len(records)} empirical record(s) for step "
            f"{step.step_id!r} are authoritative"
        ),
    )


# ---------------------------------------------------------------------------
# Aggregate step status
# ---------------------------------------------------------------------------

def aggregate_step_status(
    check_results: tuple[EngineeringResult, ...],
) -> PlanStatus:
    """Convert a tuple of EngineeringResult instances to a PlanStatus.

    INVALID  — any FAIL result.
    INCOMPLETE — no FAIL, but at least one INSUFFICIENT_DATA.
    VALIDATED — all PASS (WARNING treated as INCOMPLETE for safety).
    """
    has_fail = any(r.status is ResultStatus.FAIL for r in check_results)
    has_incomplete = any(
        r.status in (ResultStatus.INSUFFICIENT_DATA, ResultStatus.WARNING)
        for r in check_results
    )
    if has_fail:
        return PlanStatus.INVALID
    if has_incomplete:
        return PlanStatus.INCOMPLETE
    return PlanStatus.VALIDATED


# ---------------------------------------------------------------------------
# R-2810 — Aggregate plan status
# ---------------------------------------------------------------------------

def aggregate_plan_status(
    steps: tuple[ProcessPlanStep, ...],
) -> tuple[PlanStatus, EngineeringResult]:
    """R-2810: Determine aggregate engineering status from step statuses.

    INVALID    — any step is INVALID.
    INCOMPLETE — no INVALID step, but at least one is INCOMPLETE.
    VALIDATED  — all steps are VALIDATED.

    Partial data CANNOT produce VALIDATED.

    Returns (PlanStatus, EngineeringResult).
    """
    rule_id = "R-2810"

    if not steps:
        result = insufficient_data(
            result_id=f"{rule_id}.result",
            rule_id=rule_id,
            rule_version=_VERSION,
            missing_inputs=("plan_steps",),
            summary="plan has no steps — cannot be VALIDATED",
        )
        return PlanStatus.INCOMPLETE, result

    invalid_ids = [s.step_id for s in steps if s.engineering_status is PlanStatus.INVALID]
    incomplete_ids = [
        s.step_id for s in steps if s.engineering_status is PlanStatus.INCOMPLETE
    ]

    if invalid_ids:
        result = failure(
            result_id=f"{rule_id}.result",
            rule_id=rule_id,
            rule_version=_VERSION,
            violations=tuple(
                f"step {sid!r} is INVALID" for sid in invalid_ids
            ),
            summary=f"plan has {len(invalid_ids)} INVALID step(s)",
        )
        return PlanStatus.INVALID, result

    if incomplete_ids:
        result = insufficient_data(
            result_id=f"{rule_id}.result",
            rule_id=rule_id,
            rule_version=_VERSION,
            missing_inputs=tuple(
                f"step {sid!r} is INCOMPLETE" for sid in incomplete_ids
            ),
            summary=f"plan has {len(incomplete_ids)} INCOMPLETE step(s)",
        )
        return PlanStatus.INCOMPLETE, result

    result = success(
        result_id=f"{rule_id}.result",
        rule_id=rule_id,
        rule_version=_VERSION,
        summary=f"all {len(steps)} step(s) are VALIDATED",
    )
    return PlanStatus.VALIDATED, result
