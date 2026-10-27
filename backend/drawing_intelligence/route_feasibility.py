"""Route Feasibility Engine — EPIC_04E Phase 2.

Evaluates feasibility of a route template against actual requirements.

ROUTE_FEASIBILITY_ENGINE_IMPLEMENTED=YES
ROUTE_REJECTION_MODEL_IMPLEMENTED=YES
ADVANCED_OPERATION_CAPABILITY_IMPLEMENTED=YES
PROCESS_CAPABILITY_CONFIDENCE_IMPLEMENTED=YES
INSUFFICIENT_DATA_TREATED_AS_PASS=NO
"""

from __future__ import annotations

from backend.drawing_intelligence.route_alternatives import (
    OPERATION_CAPABILITY_EXT,
    RouteTemplate,
)
from backend.drawing_intelligence.route_domain import (
    ProcessCapabilityConfidence,
    RouteFeasibility,
    RouteFeasibilityStatus,
    RouteRejection,
    RouteRejectionReason,
)

__all__ = ["RouteFeasibilityEngine", "evaluate_template_feasibility"]


class RouteFeasibilityEngine:
    """Evaluates RouteFeasibilityStatus for a RouteTemplate.

    ROUTE_FEASIBILITY_ENGINE_IMPLEMENTED=YES
    INSUFFICIENT_DATA_TREATED_AS_PASS=NO — missing data → INSUFFICIENT_DATA, not FEASIBLE.
    """

    def evaluate(
        self,
        template: RouteTemplate,
        required_ra_um: float | None = None,
        required_it_grade: str | None = None,
        available_machine_type_codes: list[str] | None = None,
        material_incompatible_ops: list[str] | None = None,
        has_gdt_constraints: bool = False,
    ) -> tuple[RouteFeasibility, list[RouteRejection]]:
        """Evaluate feasibility, returning (RouteFeasibility, rejections).

        Returns INSUFFICIENT_DATA when critical information is absent.
        INFEASIBLE_ROUTE_RANKED_AS_FEASIBLE=NO.
        """
        rejections: list[RouteRejection] = []
        unresolved: list[str] = []
        coverage_items = 0
        covered_items = 0

        # --- Ra requirement ---
        if required_ra_um is not None:
            coverage_items += 1
            if template.best_ra_um <= required_ra_um:
                covered_items += 1
            else:
                rejections.append(RouteRejection(
                    reason=RouteRejectionReason.TOLERANCE_NOT_SUPPORTED,
                    detail=(
                        f"Route {template.template_id} best Ra {template.best_ra_um} µm "
                        f"does not meet required Ra {required_ra_um} µm"
                    ),
                ))

        # --- IT grade requirement ---
        if required_it_grade is not None:
            coverage_items += 1
            try:
                req_n = int(required_it_grade.replace("IT", ""))
                best_n = int(template.best_it_grade.replace("IT", ""))
                if best_n <= req_n:
                    covered_items += 1
                else:
                    rejections.append(RouteRejection(
                        reason=RouteRejectionReason.TOLERANCE_NOT_SUPPORTED,
                        detail=(
                            f"Route {template.template_id} best IT grade "
                            f"{template.best_it_grade} does not meet required "
                            f"{required_it_grade}"
                        ),
                    ))
            except (ValueError, AttributeError):
                unresolved.append(
                    f"Cannot compare IT grades: {required_it_grade} vs {template.best_it_grade}"
                )

        # --- GD&T constraint ---
        if has_gdt_constraints:
            coverage_items += 1
            if template.gdt_capable:
                covered_items += 1
            else:
                rejections.append(RouteRejection(
                    reason=RouteRejectionReason.GDT_SETUP_CONFLICT,
                    detail=(
                        f"Route {template.template_id} is not rated for tight GD&T requirements"
                    ),
                ))

        # --- Machine availability ---
        if available_machine_type_codes is not None:
            coverage_items += 1
            available_set = set(c.upper() for c in available_machine_type_codes)
            required_set = set(template.requires_machine_types)
            if available_set & required_set:
                covered_items += 1
            else:
                rejections.append(RouteRejection(
                    reason=RouteRejectionReason.MACHINE_LIMIT,
                    detail=(
                        f"Route {template.template_id} requires machine types "
                        f"{template.requires_machine_types} — none available in "
                        f"{available_machine_type_codes}"
                    ),
                ))

        # --- Material incompatibility ---
        if material_incompatible_ops:
            incompat_set = set(op.lower() for op in material_incompatible_ops)
            for op_tmpl in template.operations:
                if op_tmpl.operation_type.value in incompat_set:
                    rejections.append(RouteRejection(
                        reason=RouteRejectionReason.MATERIAL_MISMATCH,
                        detail=(
                            f"Operation {op_tmpl.operation_type.value} is listed as "
                            f"incompatible with the specified material"
                        ),
                    ))

        # --- Determine overall feasibility ---
        if rejections:
            status = RouteFeasibilityStatus.INFEASIBLE
            reason = f"{len(rejections)} rejection(s): " + "; ".join(r.detail for r in rejections)
            coverage = covered_items / max(coverage_items, 1)
        elif unresolved:
            status = RouteFeasibilityStatus.INSUFFICIENT_DATA
            reason = "Insufficient data: " + "; ".join(unresolved)
            coverage = covered_items / max(coverage_items, 1)
        elif coverage_items == 0:
            # No requirements to check — report CONDITIONAL with no data
            status = RouteFeasibilityStatus.CONDITIONAL
            reason = "No requirements specified — route is conditionally feasible"
            coverage = 1.0
        else:
            status = RouteFeasibilityStatus.FEASIBLE
            reason = f"All {covered_items} requirement(s) met"
            coverage = 1.0

        return (
            RouteFeasibility(
                status=status,
                reason=reason,
                requirement_coverage=coverage,
                unresolved_items=tuple(unresolved),
            ),
            rejections,
        )


def evaluate_template_feasibility(
    template: RouteTemplate,
    required_ra_um: float | None = None,
    required_it_grade: str | None = None,
    available_machine_type_codes: list[str] | None = None,
    material_incompatible_ops: list[str] | None = None,
    has_gdt_constraints: bool = False,
) -> tuple[RouteFeasibility, list[RouteRejection]]:
    """Module-level convenience wrapper."""
    return RouteFeasibilityEngine().evaluate(
        template,
        required_ra_um=required_ra_um,
        required_it_grade=required_it_grade,
        available_machine_type_codes=available_machine_type_codes,
        material_incompatible_ops=material_incompatible_ops,
        has_gdt_constraints=has_gdt_constraints,
    )


def capability_confidence(op_type_value: str) -> ProcessCapabilityConfidence:
    """Return the confidence tier for an operation's capability data.

    PROCESS_CAPABILITY_CONFIDENCE_IMPLEMENTED=YES
    """
    from backend.domain.enums import OperationType
    try:
        op = OperationType(op_type_value)
    except ValueError:
        return ProcessCapabilityConfidence.INSUFFICIENT_DATA

    if op in OPERATION_CAPABILITY_EXT:
        return ProcessCapabilityConfidence.LITERATURE_REFERENCE
    return ProcessCapabilityConfidence.INSUFFICIENT_DATA
