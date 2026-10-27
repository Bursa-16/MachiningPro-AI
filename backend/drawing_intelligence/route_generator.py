"""Alternative Process Route Generator (EPIC_04 Phase 2).

Generates alternative manufacturing process routes for each recognized
feature, based on the Operation Capability Library and drawing requirements.

Routes are deterministic — no AI inference. Each route is a strictly ordered
list of operations consistent with:
  - Feature type → capable operations (FEATURE_OPERATION_MATRIX)
  - Surface finish requirements (Ra capability filter)
  - Mandatory sequence rules (SEQ-DR-xxx)
  - Thread prerequisites (drill before tap)

LLM_REQUIRED_FOR_ROUTE_GENERATION=NO
FABRICATED_PROCESS_CAPABILITY=NO
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from backend.domain.enums import FeatureType, OperationType
from backend.drawing_intelligence.feature_recognition import RecognizedFeature
from backend.drawing_intelligence.operation_capability import (
    CAPABILITY_LIBRARY,
    FEATURE_OPERATION_MATRIX,
)
from backend.drawing_intelligence.requirements import (
    DrawingRequirementSet,
    GdtCharacteristic,
    GdtModifier,
)
from backend.drawing_intelligence.sequence_rules import insert_mandatory_predecessors

# R-RT-GDT thresholds
_TIGHT_POSITION_MM = Decimal("0.1")
_VERY_TIGHT_POSITION_MM = Decimal("0.05")
_TIGHT_PERPENDICULARITY_MM = Decimal("0.05")

__all__ = [
    "AlternativeRoute",
    "RouteRejection",
    "RouteGenerationResult",
    "RouteGenerator",
    "generate_routes",
]


class RouteRejectionReason(StrEnum):
    CAPABILITY_GAP = "CAPABILITY_GAP"       # No op meets Ra requirement
    FEATURE_UNSUPPORTED = "FEATURE_UNSUPPORTED"  # No ops in matrix for feature
    SEQUENCE_VIOLATION = "SEQUENCE_VIOLATION"   # Could not satisfy SEQ rules


@dataclass(frozen=True, slots=True)
class RouteRejection:
    """Records why a candidate route was rejected."""

    route_id: str
    reason: RouteRejectionReason
    detail: str


@dataclass(frozen=True, slots=True)
class AlternativeRoute:
    """A single feasible process route for one recognized feature."""

    route_id: str
    feature_id: str
    feature_type: FeatureType
    operations: tuple[OperationType, ...]
    required_ra_um: Decimal | None        # from drawing; None if not specified
    achievable_ra_um: Decimal             # best Ra the route can achieve
    requires_grinding: bool
    route_description: str


@dataclass(frozen=True, slots=True)
class RouteGenerationResult:
    """All routes generated for one recognized feature."""

    feature_id: str
    feature_type: FeatureType
    routes: tuple[AlternativeRoute, ...]
    rejections: tuple[RouteRejection, ...]
    warnings: tuple[str, ...]

    @property
    def has_routes(self) -> bool:
        return len(self.routes) > 0


class RouteGenerator:
    """Generates alternative process routes for a recognized feature.

    For each capable operation (from FEATURE_OPERATION_MATRIX):
      1. Assemble a candidate operation sequence.
      2. Apply mandatory sequence corrections (SEQ-DR-xxx BLOCKING rules).
      3. Check Ra capability — reject if no op meets the requirement.
      4. Emit a valid AlternativeRoute or a RouteRejection.
    """

    def generate(
        self,
        rf: RecognizedFeature,
        req_set: DrawingRequirementSet,
    ) -> RouteGenerationResult:
        feature = rf.feature
        ft = feature.feature_type
        routes: list[AlternativeRoute] = []
        rejections: list[RouteRejection] = []
        warnings: list[str] = []

        # Find surface finish requirement for this feature
        required_ra = self._find_ra(req_set, rf)

        primary_ops = FEATURE_OPERATION_MATRIX.get(ft, [])
        if not primary_ops:
            rejections.append(RouteRejection(
                route_id=f"{feature.feature_id}-R0",
                reason=RouteRejectionReason.FEATURE_UNSUPPORTED,
                detail=f"No operations defined for feature type {ft}",
            ))
            return RouteGenerationResult(
                feature_id=feature.feature_id,
                feature_type=ft,
                routes=(),
                rejections=tuple(rejections),
                warnings=tuple(warnings),
            )

        # Generate routes: minimal (1 op), standard (first + finish), extended
        candidates: list[list[OperationType]] = []

        if ft == FeatureType.HOLE:
            candidates = self._hole_routes(required_ra)
        elif ft == FeatureType.THREAD:
            candidates = self._thread_routes()
        elif ft in (FeatureType.SLOT, FeatureType.POCKET, FeatureType.PLANAR_FACE):
            candidates = self._milling_routes(required_ra)
        elif ft == FeatureType.CYLINDRICAL_SURFACE:
            candidates = self._turning_routes(required_ra)
        elif ft in (FeatureType.CHAMFER, FeatureType.FILLET, FeatureType.GROOVE):
            candidates = self._finishing_routes(ft)
        else:
            # Fallback: single-op routes for all capable operations
            candidates = [[op] for op in primary_ops]

        route_idx = 0
        for ops in candidates:
            route_id = f"{feature.feature_id}-R{route_idx}"
            # Apply mandatory predecessor insertion
            fixed_ops = insert_mandatory_predecessors(ops, ft)
            # Check Ra capability
            best_ra = self._best_ra(fixed_ops)
            if required_ra is not None and best_ra > required_ra:
                rejections.append(RouteRejection(
                    route_id=route_id,
                    reason=RouteRejectionReason.CAPABILITY_GAP,
                    detail=(
                        f"Route {fixed_ops} achieves Ra {best_ra} µm but "
                        f"drawing requires Ra ≤ {required_ra} µm"
                    ),
                ))
                route_idx += 1
                continue

            requires_grinding = any(
                op == OperationType.GRINDING for op in fixed_ops
            )
            routes.append(AlternativeRoute(
                route_id=route_id,
                feature_id=feature.feature_id,
                feature_type=ft,
                operations=tuple(fixed_ops),
                required_ra_um=required_ra,
                achievable_ra_um=best_ra,
                requires_grinding=requires_grinding,
                route_description=self._describe(fixed_ops, ft),
            ))
            route_idx += 1

        # Apply GD&T-aware route warnings (R-RT-GDT-001 through R-RT-GDT-007)
        gdt_warnings = self._gdt_route_warnings(rf, req_set)
        warnings.extend(gdt_warnings)

        return RouteGenerationResult(
            feature_id=feature.feature_id,
            feature_type=ft,
            routes=tuple(routes),
            rejections=tuple(rejections),
            warnings=tuple(warnings),
        )

    # ------------------------------------------------------------------ #
    # GD&T routing rules (R-RT-GDT-001 through R-RT-GDT-007)
    # ------------------------------------------------------------------ #

    def _gdt_route_warnings(
        self,
        rf: RecognizedFeature,
        req_set: DrawingRequirementSet,
    ) -> list[str]:
        """Return route-level GD&T warnings for R-RT-GDT-001 through R-RT-GDT-007."""
        warnings: list[str] = []
        feature_id = rf.feature.feature_id

        for geom in req_set.geometric:
            if geom.feature_ref is not None and geom.feature_ref != feature_id:
                continue
            fcf = geom.fcf
            char = fcf.characteristic
            tol = fcf.tolerance_value

            # R-RT-GDT-001: Tight position — prefer boring/reaming over drilling
            if char == GdtCharacteristic.POSITION and tol <= _TIGHT_POSITION_MM:
                if tol <= _VERY_TIGHT_POSITION_MM:
                    warnings.append(
                        f"R-RT-GDT-001 [{geom.req_id}]: POSITION ⌀{tol} mm — "
                        "very tight; prefer boring + reaming; jig boring may be required"
                    )
                else:
                    warnings.append(
                        f"R-RT-GDT-001 [{geom.req_id}]: POSITION ⌀{tol} mm — "
                        "tight; prefer boring over drilling for final pass"
                    )

            # R-RT-GDT-002: Tight perpendicularity — add finish grinding/honing
            elif char == GdtCharacteristic.PERPENDICULARITY and tol <= _TIGHT_PERPENDICULARITY_MM:
                warnings.append(
                    f"R-RT-GDT-002 [{geom.req_id}]: PERPENDICULARITY {tol} mm — "
                    "add surface grinding or precision boring in final setup"
                )

            # R-RT-GDT-003: Cylindricity — add grinding to cylindrical routes
            elif char == GdtCharacteristic.CYLINDRICITY:
                warnings.append(
                    f"R-RT-GDT-003 [{geom.req_id}]: CYLINDRICITY {tol} mm — "
                    "route should include cylindrical grinding (OD or ID)"
                )

            # R-RT-GDT-004: Runout — same-setup constraint
            elif char in (GdtCharacteristic.CIRCULAR_RUNOUT, GdtCharacteristic.TOTAL_RUNOUT):
                warnings.append(
                    f"R-RT-GDT-004 [{geom.req_id}]: {char.value} {tol} mm — "
                    "all runout-controlled surfaces must be machined in one chucking"
                )

            # R-RT-GDT-005: Profile of a surface — finishing step
            elif char == GdtCharacteristic.PROFILE_OF_A_SURFACE:
                warnings.append(
                    f"R-RT-GDT-005 [{geom.req_id}]: PROFILE_OF_A_SURFACE {tol} mm — "
                    "include surface finishing (grinding or lapping) in final route step"
                )

            # R-RT-GDT-006: MMC/LMC modifier — inspection note
            if fcf.modifier in (GdtModifier.MMC, GdtModifier.LMC):
                warnings.append(
                    f"R-RT-GDT-006 [{geom.req_id}]: {fcf.modifier.value} modifier — "
                    "100% size inspection required before GD&T conformance check"
                )

        return warnings

    # ------------------------------------------------------------------ #
    # Feature-specific route templates
    # ------------------------------------------------------------------ #

    def _hole_routes(
        self, required_ra: Decimal | None
    ) -> list[list[OperationType]]:
        routes = [
            [OperationType.DRILLING],                                      # basic
            [OperationType.DRILLING, OperationType.REAMING],               # standard
            [OperationType.DRILLING, OperationType.BORING],                # boring
        ]
        # Add honing route when very tight surface finish required
        if required_ra is not None and required_ra <= Decimal("0.8"):
            routes.append([
                OperationType.DRILLING,
                OperationType.BORING,
                OperationType.HONING,
            ])
        return routes

    def _thread_routes(self) -> list[list[OperationType]]:
        return [
            [OperationType.DRILLING, OperationType.TAPPING],
            [OperationType.DRILLING, OperationType.THREADING],
        ]

    def _milling_routes(
        self, required_ra: Decimal | None
    ) -> list[list[OperationType]]:
        routes: list[list[OperationType]] = [
            [OperationType.MILLING],
        ]
        if required_ra is not None and required_ra <= Decimal("0.8"):
            routes.append([OperationType.MILLING, OperationType.GRINDING])
        return routes

    def _turning_routes(
        self, required_ra: Decimal | None
    ) -> list[list[OperationType]]:
        routes: list[list[OperationType]] = [
            [OperationType.TURNING],
        ]
        if required_ra is not None and required_ra <= Decimal("0.8"):
            routes.append([OperationType.TURNING, OperationType.GRINDING])
        if required_ra is not None and required_ra <= Decimal("0.4"):
            routes.append([
                OperationType.TURNING,
                OperationType.GRINDING,
                OperationType.LAPPING,
            ])
        return routes

    def _finishing_routes(
        self, ft: FeatureType
    ) -> list[list[OperationType]]:
        if ft == FeatureType.GROOVE:
            return [
                [OperationType.TURNING],
                [OperationType.MILLING],
            ]
        if ft == FeatureType.CHAMFER:
            return [
                [OperationType.TURNING],
                [OperationType.MILLING],
                [OperationType.DEBURRING],
            ]
        # FILLET
        return [
            [OperationType.TURNING],
            [OperationType.MILLING],
        ]

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _best_ra(self, ops: list[OperationType]) -> Decimal:
        """Return the best (lowest) Ra achievable in the route."""
        best = Decimal("999")
        for op in ops:
            cap = CAPABILITY_LIBRARY.get(op)
            if cap is not None and cap.ra_achievable_um < best:
                best = cap.ra_achievable_um
        return best

    def _find_ra(
        self,
        req_set: DrawingRequirementSet,
        rf: RecognizedFeature,
    ) -> Decimal | None:
        """Find the Ra requirement for this feature from surface finish reqs."""
        for sf in req_set.surface_finish:
            if sf.feature_ref is None or sf.feature_ref in rf.source_req_ids:
                if sf.ra_um is not None:
                    return sf.ra_um
        return None

    def _describe(
        self, ops: list[OperationType], ft: FeatureType
    ) -> str:
        op_names = " → ".join(op.value for op in ops)
        return f"{ft.value}: {op_names}"


def generate_routes(
    rf: RecognizedFeature,
    req_set: DrawingRequirementSet,
) -> RouteGenerationResult:
    """Convenience function."""
    return RouteGenerator().generate(rf, req_set)
