"""Manufacturing plan validation rules.

FABRICATED_CHARACTERISTIC=NO
FABRICATED_PROCESS_PARAMETER=NO
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import StrEnum

from backend.manufacturing_plan.characteristic import CharacteristicCriticality
from backend.manufacturing_plan.models import (
    ManufacturingPlan,
    ManufacturingPlanStatus,
    OpenItem,
    OpenItemCategory,
    OpenItemSeverity,
    OpenItemStatus,
    ReleaseGateStatus,
)


class ValidationCode(StrEnum):
    V001 = "V001"
    V002 = "V002"
    V003 = "V003"
    V004 = "V004"
    V005 = "V005"
    V006 = "V006"
    V007 = "V007"


@dataclass
class ValidationFinding:
    code: ValidationCode
    severity: OpenItemSeverity
    message: str
    field: str | None = None
    related_id: str | None = None


@dataclass
class ValidationResult:
    plan_id: str
    passed: bool
    findings: list[ValidationFinding] = field(default_factory=list)
    blocking_count: int = 0
    review_required_count: int = 0
    advisory_count: int = 0

    def add(self, finding: ValidationFinding) -> None:
        self.findings.append(finding)
        if finding.severity == OpenItemSeverity.BLOCKING:
            self.blocking_count += 1
            self.passed = False
        elif finding.severity == OpenItemSeverity.REVIEW_REQUIRED:
            self.review_required_count += 1
        else:
            self.advisory_count += 1


def validate_manufacturing_plan(plan: ManufacturingPlan) -> ValidationResult:
    """Run V-001 through V-007 validation rules. Returns ValidationResult."""
    result = ValidationResult(plan_id=plan.plan_id, passed=True)

    _v001_draft_guard(plan, result)
    _v002_has_operations(plan, result)
    _v003_key_chars_inspected(plan, result)
    _v004_blocking_open_items(plan, result)
    _v005_release_gate_coherence(plan, result)
    _v006_completeness_floor(plan, result)
    _v007_fingerprint_present(plan, result)

    return result


def validate_plan(plan: ManufacturingPlan) -> list[OpenItem]:
    """Legacy/test-compatible entry-point: validate and return open items list.

    Checks:
    V-001: CRITICAL/KEY chars without inspection coverage → BLOCKING
    V-002: operations without machine → REVIEW_REQUIRED
    V-003: operations without tool → REVIEW_REQUIRED
    V-004: duplicate op_numbers → BLOCKING
    V-005: low completeness → REVIEW_REQUIRED
    """
    items: list[OpenItem] = []

    # V-001: critical/key chars not covered by inspection
    if plan.inspection_plan:
        covered = {r.char_id for r in plan.inspection_plan.rows if r.status == "COVERED"}
    else:
        covered = set()

    for char in plan.characteristics:
        if char.criticality in (
            CharacteristicCriticality.CRITICAL,
            CharacteristicCriticality.KEY_CHARACTERISTIC,
        ):
            if char.characteristic_id not in covered:
                items.append(OpenItem(
                    item_id=str(uuid.uuid4()),
                    category=OpenItemCategory.MISSING_INSPECTION,
                    severity=OpenItemSeverity.BLOCKING,
                    description=f"V-001: CRITICAL/KEY char '{char.label}' has no inspection coverage",
                    related_char_id=char.characteristic_id,
                    resolution_hint="Assign inspection method and stage",
                ))

    # V-002: machine assignment
    for op in plan.operations:
        if "INSPECT" in op.operation_type.upper():
            continue
        if not op.machine_id:
            items.append(OpenItem(
                item_id=str(uuid.uuid4()),
                category=OpenItemCategory.MISSING_MACHINE,
                severity=OpenItemSeverity.REVIEW_REQUIRED,
                description=f"V-002: No machine assigned for op {op.op_number} ({op.operation_type})",
                related_step_id=op.op_id,
                resolution_hint="Assign machine from machine catalog",
            ))

    # V-003: tool assignment
    for op in plan.operations:
        if "INSPECT" in op.operation_type.upper():
            continue
        if not op.tool_id:
            items.append(OpenItem(
                item_id=str(uuid.uuid4()),
                category=OpenItemCategory.MISSING_TOOL,
                severity=OpenItemSeverity.REVIEW_REQUIRED,
                description=f"V-003: No tool assigned for op {op.op_number} ({op.operation_type})",
                related_step_id=op.op_id,
                resolution_hint="Assign cutting tool from tool catalog",
            ))

    # V-004: duplicate op numbers
    seen: dict[int, str] = {}
    for op in plan.operations:
        if op.op_number in seen:
            items.append(OpenItem(
                item_id=str(uuid.uuid4()),
                category=OpenItemCategory.REVIEW_REQUIRED,
                severity=OpenItemSeverity.BLOCKING,
                description=f"V-004: Duplicate op_number {op.op_number}",
                related_step_id=op.op_id,
                resolution_hint="Ensure unique operation sequence numbers",
            ))
        else:
            seen[op.op_number] = op.op_id

    # V-005: completeness
    score = plan.completeness.overall_completeness
    if score < 0.50:
        items.append(OpenItem(
            item_id=str(uuid.uuid4()),
            category=OpenItemCategory.REVIEW_REQUIRED,
            severity=OpenItemSeverity.REVIEW_REQUIRED,
            description=f"V-005: Plan completeness {score:.0%} — INCOMPLETE",
            resolution_hint="Complete missing machine/tool/parameter assignments",
        ))
    elif score < 0.80:
        items.append(OpenItem(
            item_id=str(uuid.uuid4()),
            category=OpenItemCategory.REVIEW_REQUIRED,
            severity=OpenItemSeverity.ADVISORY,
            description=f"V-005: Plan completeness {score:.0%} — PARTIALLY_COMPLETE",
            resolution_hint="Complete remaining assignments",
        ))

    return items


def _v001_draft_guard(plan: ManufacturingPlan, result: ValidationResult) -> None:
    """V-001: AUTO_GENERATED_PLAN_MARKED_APPROVED must be False."""
    if plan.AUTO_GENERATED_PLAN_MARKED_APPROVED:
        result.add(ValidationFinding(
            code=ValidationCode.V001,
            severity=OpenItemSeverity.BLOCKING,
            message="AUTO_GENERATED_PLAN_MARKED_APPROVED=True is not permitted",
            field="AUTO_GENERATED_PLAN_MARKED_APPROVED",
        ))
    if plan.status == ManufacturingPlanStatus.APPROVED and plan.AUTO_GENERATED_PLAN_MARKED_APPROVED:
        result.add(ValidationFinding(
            code=ValidationCode.V001,
            severity=OpenItemSeverity.BLOCKING,
            message="Plan cannot be APPROVED with AUTO_GENERATED_PLAN_MARKED_APPROVED=True",
            field="status",
        ))


def _v002_has_operations(plan: ManufacturingPlan, result: ValidationResult) -> None:
    """V-002: Manufacturing plan must have at least one operation."""
    if not plan.operations:
        result.add(ValidationFinding(
            code=ValidationCode.V002,
            severity=OpenItemSeverity.REVIEW_REQUIRED,
            message="Plan has no operations — route may be empty or unresolved",
            field="operations",
        ))


def _v003_key_chars_inspected(plan: ManufacturingPlan, result: ValidationResult) -> None:
    """V-003: KEY/CRITICAL characteristics must have inspection coverage."""
    covered: set[str] = set()
    if plan.inspection_plan:
        covered = {r.char_id for r in plan.inspection_plan.rows if r.status == "COVERED"}
    for char in plan.characteristics:
        if char.criticality in (
            CharacteristicCriticality.KEY_CHARACTERISTIC,
            CharacteristicCriticality.CRITICAL,
        ):
            if char.characteristic_id not in covered:
                result.add(ValidationFinding(
                    code=ValidationCode.V003,
                    severity=OpenItemSeverity.BLOCKING,
                    message=f"CRITICAL/KEY characteristic '{char.label}' has no inspection coverage",
                    field="inspection_plan",
                    related_id=char.characteristic_id,
                ))


def _v004_blocking_open_items(plan: ManufacturingPlan, result: ValidationResult) -> None:
    """V-004: BLOCKING open items block release gate."""
    blocking = [
        i for i in plan.open_items
        if i.severity == OpenItemSeverity.BLOCKING and i.status == OpenItemStatus.OPEN
    ]
    for item in blocking:
        result.add(ValidationFinding(
            code=ValidationCode.V004,
            severity=OpenItemSeverity.BLOCKING,
            message=f"Blocking open item: {item.description}",
            field="open_items",
            related_id=item.item_id,
        ))


def _v005_release_gate_coherence(plan: ManufacturingPlan, result: ValidationResult) -> None:
    """V-005: Release gate must be coherent with completeness and open items."""
    if plan.release_gate == ReleaseGateStatus.READY_FOR_ENGINEERING_REVIEW:
        if plan.completeness.overall_completeness < 0.50:
            result.add(ValidationFinding(
                code=ValidationCode.V005,
                severity=OpenItemSeverity.REVIEW_REQUIRED,
                message=(
                    f"Release gate is READY but completeness is "
                    f"{plan.completeness.overall_completeness:.0%} — review required"
                ),
                field="release_gate",
            ))


def _v006_completeness_floor(plan: ManufacturingPlan, result: ValidationResult) -> None:
    """V-006: Overall completeness advisory at low values."""
    score = plan.completeness.overall_completeness
    if score < 0.50:
        result.add(ValidationFinding(
            code=ValidationCode.V006,
            severity=OpenItemSeverity.ADVISORY,
            message=f"Plan completeness {score:.0%} — plan is INCOMPLETE",
            field="completeness.overall_completeness",
        ))
    elif score < 0.80:
        result.add(ValidationFinding(
            code=ValidationCode.V006,
            severity=OpenItemSeverity.ADVISORY,
            message=f"Plan completeness {score:.0%} — plan is PARTIALLY_COMPLETE",
            field="completeness.overall_completeness",
        ))


def _v007_fingerprint_present(plan: ManufacturingPlan, result: ValidationResult) -> None:
    """V-007: Traceability fingerprint must be set."""
    if not plan.traceability_fingerprint:
        result.add(ValidationFinding(
            code=ValidationCode.V007,
            severity=OpenItemSeverity.ADVISORY,
            message="No traceability fingerprint — plan was not built via standard builder",
            field="traceability_fingerprint",
        ))
