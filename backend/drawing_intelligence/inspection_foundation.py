"""Inspection Plan Foundation (EPIC_04 Phase 2).

Inserts mandatory inspection steps for tight-tolerance and GD&T features.

Rules (deterministic):
  INS-R-001  Any GD&T requirement → insert INSPECTION step after last op
  INS-R-002  Surface finish Ra ≤ 1.6 µm → insert INSPECTION step
  INS-R-003  Thread requirement → insert INSPECTION step (go/no-go gauge)
  INS-R-004  Hole diameter tolerance tighter than IT8 → INSPECTION

AUTO_GENERATED_PLAN_MARKED_APPROVED=NO
UNKNOWN_REQUIREMENT_TREATED_AS_SATISFIED=NO
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from backend.domain.enums import FeatureType, OperationType
from backend.drawing_intelligence.requirements import DrawingRequirementSet

__all__ = [
    "InspectionStep",
    "InspectionMethod",
    "InspectionTrigger",
    "InspectionPlan",
    "InspectionPlanner",
    "build_inspection_plan",
]


class InspectionMethod(StrEnum):
    CMM = "CMM"                        # Coordinate Measuring Machine
    SURFACE_ROUGHNESS_TESTER = "SURFACE_ROUGHNESS_TESTER"
    GO_NO_GO_GAUGE = "GO_NO_GO_GAUGE"
    BORE_GAUGE = "BORE_GAUGE"
    VISUAL = "VISUAL"
    THREAD_GAUGE = "THREAD_GAUGE"
    UNKNOWN = "UNKNOWN"


class InspectionTrigger(StrEnum):
    GDT_REQUIREMENT = "GDT_REQUIREMENT"
    SURFACE_FINISH = "SURFACE_FINISH"
    THREAD_VERIFICATION = "THREAD_VERIFICATION"
    TIGHT_TOLERANCE = "TIGHT_TOLERANCE"
    GENERAL_QUALITY = "GENERAL_QUALITY"


@dataclass(frozen=True, slots=True)
class InspectionStep:
    """One mandatory inspection step inferred from drawing requirements."""

    step_id: str
    operation: OperationType
    method: InspectionMethod
    trigger: InspectionTrigger
    feature_ref: str | None          # feature_id this inspection covers
    requirement_ref: str | None      # req_id that triggered this inspection
    rationale: str
    insert_after_op: OperationType | None   # position hint; None = end of plan


@dataclass(frozen=True, slots=True)
class InspectionPlan:
    """Collection of mandatory inspection steps for a drawing."""

    source_id: str
    steps: tuple[InspectionStep, ...]
    generation_warnings: tuple[str, ...]

    @property
    def has_cmm(self) -> bool:
        return any(s.method == InspectionMethod.CMM for s in self.steps)

    @property
    def step_count(self) -> int:
        return len(self.steps)


class InspectionPlanner:
    """Derives mandatory inspection steps from a DrawingRequirementSet."""

    def plan(self, req_set: DrawingRequirementSet) -> InspectionPlan:
        steps: list[InspectionStep] = []
        warnings: list[str] = []
        idx = 0

        # INS-R-001: GD&T requirements → CMM inspection
        for geom in req_set.geometric:
            steps.append(InspectionStep(
                step_id=f"INS-{idx:04d}",
                operation=OperationType.INSPECTION,
                method=InspectionMethod.CMM,
                trigger=InspectionTrigger.GDT_REQUIREMENT,
                feature_ref=geom.feature_ref,
                requirement_ref=geom.req_id,
                rationale=(
                    f"GD&T {geom.fcf.characteristic.value} "
                    f"({geom.fcf.tolerance_value} {geom.fcf.tolerance_unit}) "
                    "requires CMM verification"
                ),
                insert_after_op=None,
            ))
            idx += 1

        # INS-R-002: Surface finish Ra ≤ 1.6 µm → roughness tester
        for sf in req_set.surface_finish:
            if sf.ra_um is not None and sf.ra_um <= Decimal("1.6"):
                steps.append(InspectionStep(
                    step_id=f"INS-{idx:04d}",
                    operation=OperationType.INSPECTION,
                    method=InspectionMethod.SURFACE_ROUGHNESS_TESTER,
                    trigger=InspectionTrigger.SURFACE_FINISH,
                    feature_ref=sf.feature_ref,
                    requirement_ref=sf.req_id,
                    rationale=(
                        f"Ra {sf.ra_um} µm requires surface roughness measurement"
                    ),
                    insert_after_op=None,
                ))
                idx += 1

        # INS-R-003: Thread requirements → thread gauge
        for thread in req_set.threads:
            steps.append(InspectionStep(
                step_id=f"INS-{idx:04d}",
                operation=OperationType.INSPECTION,
                method=InspectionMethod.THREAD_GAUGE,
                trigger=InspectionTrigger.THREAD_VERIFICATION,
                feature_ref=None,
                requirement_ref=thread.req_id,
                rationale=(
                    f"Thread {thread.designation or 'unknown'} requires "
                    "go/no-go gauge verification"
                ),
                insert_after_op=OperationType.TAPPING,
            ))
            idx += 1

        # INS-R-004: Tight-tolerance holes → bore gauge
        for dim in req_set.dimensional:
            if "diameter" not in dim.dimension_type.lower():
                continue
            if dim.tolerance_upper is None:
                continue
            tol = abs(dim.tolerance_upper)
            if tol < Decimal("0.025"):  # tighter than IT8 for ~25mm bore
                steps.append(InspectionStep(
                    step_id=f"INS-{idx:04d}",
                    operation=OperationType.INSPECTION,
                    method=InspectionMethod.BORE_GAUGE,
                    trigger=InspectionTrigger.TIGHT_TOLERANCE,
                    feature_ref=None,
                    requirement_ref=dim.req_id,
                    rationale=(
                        f"Tight hole tolerance ±{tol} mm requires bore gauge "
                        "or CMM measurement"
                    ),
                    insert_after_op=OperationType.REAMING,
                ))
                idx += 1

        return InspectionPlan(
            source_id=req_set.source_id,
            steps=tuple(steps),
            generation_warnings=tuple(warnings),
        )


def build_inspection_plan(req_set: DrawingRequirementSet) -> InspectionPlan:
    """Convenience function."""
    return InspectionPlanner().plan(req_set)
