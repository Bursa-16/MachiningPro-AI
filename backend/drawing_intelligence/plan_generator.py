"""Generated Process Plan Model and Handoff (EPIC_04 Phase 2).

Converts scored AlternativeRoutes + InspectionPlan → GeneratedProcessPlan,
which can be handed off to the existing ProcessPlanningEngine as a
ProcessPlanRequest.

Approval semantics:
  GeneratedProcessPlan.status is always DRAFT — never APPROVED.
  Engineers must explicitly approve before production use.

AUTO_GENERATED_PLAN_MARKED_APPROVED=NO
LLM_ALLOWED_TO_OVERRIDE_ENGINEERING_FACTS=NO
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from backend.domain.enums import OperationType
from backend.drawing_intelligence.feature_recognition import (
    FeatureRecognitionResult,
)
from backend.drawing_intelligence.inspection_foundation import InspectionPlan
from backend.drawing_intelligence.requirements import DrawingRequirementSet
from backend.drawing_intelligence.route_generator import (
    RouteGenerationResult,
    RouteGenerator,
)
from backend.drawing_intelligence.route_scoring import ScoredRoute, score_routes
from backend.drawing_intelligence.traceability import TraceabilityChain, TraceabilityLedger

__all__ = [
    "GeneratedPlanStatus",
    "GeneratedStep",
    "GeneratedProcessPlan",
    "PlanGenerator",
    "generate_plan",
]

_DISCLAIMER = (
    "This plan was AUTOMATICALLY GENERATED from drawing requirements and is "
    "DRAFT status. It is REFERENCE_ONLY — NOT engineering-validated, "
    "NOT approved for production use. An engineer must review and approve "
    "before manufacturing use. AUTO_GENERATED_PLAN_MARKED_APPROVED=NO."
)


class GeneratedPlanStatus(StrEnum):
    DRAFT = "DRAFT"                  # always the initial state
    PARTIAL = "PARTIAL"              # some features have no viable routes
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"  # cannot generate any routes


@dataclass(frozen=True, slots=True)
class GeneratedStep:
    """One step in the generated plan."""

    step_id: str
    sequence_number: int
    operation: OperationType
    feature_id: str | None
    route_id: str | None
    is_inspection: bool
    notes: str


@dataclass(frozen=True, slots=True)
class GeneratedProcessPlan:
    """Auto-generated process plan from drawing requirements.

    Status is always DRAFT — never APPROVED.
    AUTO_GENERATED_PLAN_MARKED_APPROVED=NO
    """

    plan_id: str
    source_id: str
    drawing_number: str | None
    revision: str | None
    status: GeneratedPlanStatus
    steps: tuple[GeneratedStep, ...]
    traceability: TraceabilityChain
    route_results: tuple[RouteGenerationResult, ...]
    best_routes: tuple[ScoredRoute, ...]
    generation_warnings: tuple[str, ...]
    disclaimer: str

    def __post_init__(self) -> None:
        # Enforce: auto-generated plans are never marked approved
        if self.status not in (
            GeneratedPlanStatus.DRAFT,
            GeneratedPlanStatus.PARTIAL,
            GeneratedPlanStatus.INSUFFICIENT_DATA,
        ):
            raise ValueError(
                "GeneratedProcessPlan.status must be DRAFT, PARTIAL, or "
                "INSUFFICIENT_DATA — AUTO_GENERATED_PLAN_MARKED_APPROVED=NO"
            )

    @property
    def step_count(self) -> int:
        return len(self.steps)

    def to_handoff_dict(self) -> dict:
        """Produce a structure compatible with ProcessPlanRequest for handoff.

        Returns a plain dict — the caller constructs the Pydantic model.
        All values are strings/numbers per ProcessPlanRequest field types.
        """
        steps = []
        for s in self.steps:
            steps.append({
                "step_id": s.step_id,
                "sequence_number": s.sequence_number,
                "operation": s.operation.value,
                "feature_id": s.feature_id,
                "machine_id": None,
                "cutting_tool_id": None,
                "cutting_speed_m_min": None,
                "tool_diameter_mm": None,
                "predecessor_step_ids": [],
                "cutting_path_length_mm": None,
                "rapid_distance_mm": None,
                "dwell_time_s": None,
                "tool_change_time_s": None,
            })
        return {
            "part_name": self.drawing_number or self.source_id,
            "material_iso_group": None,
            "operations": steps,
        }


class PlanGenerator:
    """Generates a complete GeneratedProcessPlan from a drawing's requirements."""

    def generate(
        self,
        req_set: DrawingRequirementSet,
        recognition: FeatureRecognitionResult,
        inspection_plan: InspectionPlan,
        part_id: str = "UNKNOWN",
    ) -> GeneratedProcessPlan:
        import hashlib
        plan_id = hashlib.sha256(
            f"{req_set.source_id}|{req_set.fingerprint}".encode()
        ).hexdigest()[:12]

        ledger = TraceabilityLedger(
            source_id=req_set.source_id,
            drawing_number=req_set.drawing_number,
            revision=req_set.revision,
        )

        route_gen = RouteGenerator()
        all_route_results: list[RouteGenerationResult] = []
        best_routes: list[ScoredRoute] = []
        steps: list[GeneratedStep] = []
        warnings: list[str] = []
        seq = 1

        for rf in recognition.features:
            rr = route_gen.generate(rf, req_set)
            all_route_results.append(rr)

            if not rr.has_routes:
                warnings.append(
                    f"No viable routes for feature {rf.feature.feature_id} "
                    f"({rf.feature.feature_type})"
                )
                # Emit a placeholder INSUFFICIENT_DATA step
                step_id = f"S-{seq:04d}"
                steps.append(GeneratedStep(
                    step_id=step_id,
                    sequence_number=seq,
                    operation=OperationType.OTHER,
                    feature_id=rf.feature.feature_id,
                    route_id=None,
                    is_inspection=False,
                    notes=(
                        f"INSUFFICIENT_DATA: no route for "
                        f"{rf.feature.feature_type}"
                    ),
                ))
                seq += 1
                continue

            # Select best route (first in scored list)
            scored = score_routes(list(rr.routes))
            best = scored[0]
            best_routes.append(best)

            for op in best.route.operations:
                step_id = f"S-{seq:04d}"
                steps.append(GeneratedStep(
                    step_id=step_id,
                    sequence_number=seq,
                    operation=op,
                    feature_id=rf.feature.feature_id,
                    route_id=best.route.route_id,
                    is_inspection=False,
                    notes=f"Route {best.route.route_id}: {best.route.route_description}",
                ))
                # Record traceability for each source req of this feature
                for req_id in rf.source_req_ids:
                    ledger.record(
                        req_id=req_id,
                        feature_id=rf.feature.feature_id,
                        step_id=step_id,
                        recognition_rule=rf.recognition_rule,
                        operation=op.value,
                    )
                seq += 1

        # Append inspection steps
        for ins in inspection_plan.steps:
            step_id = f"S-{seq:04d}"
            steps.append(GeneratedStep(
                step_id=step_id,
                sequence_number=seq,
                operation=OperationType.INSPECTION,
                feature_id=ins.feature_ref,
                route_id=None,
                is_inspection=True,
                notes=ins.rationale,
            ))
            if ins.requirement_ref:
                ledger.record(
                    req_id=ins.requirement_ref,
                    feature_id=ins.feature_ref or "INSPECTION",
                    step_id=step_id,
                    recognition_rule="INS",
                    operation=OperationType.INSPECTION.value,
                )
            seq += 1

        # Determine overall status
        has_insufficient = any(
            not rr.has_routes for rr in all_route_results
        )
        if not steps or all(
            not rr.has_routes for rr in all_route_results
        ):
            status = GeneratedPlanStatus.INSUFFICIENT_DATA
        elif has_insufficient:
            status = GeneratedPlanStatus.PARTIAL
        else:
            status = GeneratedPlanStatus.DRAFT

        return GeneratedProcessPlan(
            plan_id=plan_id,
            source_id=req_set.source_id,
            drawing_number=req_set.drawing_number,
            revision=req_set.revision,
            status=status,
            steps=tuple(steps),
            traceability=ledger.build(),
            route_results=tuple(all_route_results),
            best_routes=tuple(best_routes),
            generation_warnings=tuple(warnings),
            disclaimer=_DISCLAIMER,
        )


def generate_plan(
    req_set: DrawingRequirementSet,
    recognition: FeatureRecognitionResult,
    inspection_plan: InspectionPlan,
    part_id: str = "UNKNOWN",
) -> GeneratedProcessPlan:
    """Convenience function."""
    return PlanGenerator().generate(req_set, recognition, inspection_plan, part_id)
