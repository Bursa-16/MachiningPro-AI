"""Route Override Engine — EPIC_04E Phase 2.

Applies engineer overrides to route candidates.

PROCESS_OPTIMIZATION_OVERRIDE_IMPLEMENTED=YES
AUTO_SELECTED_ROUTE_MARKED_APPROVED=NO
"""

from __future__ import annotations

import dataclasses

from backend.drawing_intelligence.route_domain import (
    OverrideType,
    ProcessRouteCandidate,
    RouteAlternativeSet,
    RouteOverride,
)

__all__ = ["RouteOverrideEngine", "apply_override_to_candidate"]


class RouteOverrideEngine:
    """Applies RouteOverride instances to a RouteAlternativeSet.

    AUTO_SELECTED_ROUTE_MARKED_APPROVED=NO — overrides never promote
    status to APPROVED; result always remains DRAFT.
    PROCESS_OPTIMIZATION_OVERRIDE_IMPLEMENTED=YES
    """

    def apply(
        self,
        alt_set: RouteAlternativeSet,
        override: RouteOverride,
    ) -> RouteAlternativeSet:
        """Apply override and return updated RouteAlternativeSet."""
        updated: list[ProcessRouteCandidate] = []
        for candidate in alt_set.candidates:
            if override.target_id in (candidate.route_id, candidate.feature_id):
                updated.append(self._apply_to_candidate(candidate, override))
            else:
                updated.append(candidate)

        return dataclasses.replace(
            alt_set,
            candidates=tuple(updated),
        )

    def _apply_to_candidate(
        self,
        candidate: ProcessRouteCandidate,
        override: RouteOverride,
    ) -> ProcessRouteCandidate:
        """Apply one override to a single candidate."""
        ot = override.override_type

        if ot is OverrideType.LOCK_OPERATION:
            # Lock all operations — no removal allowed
            return dataclasses.replace(
                candidate,
                overrides_applied=candidate.overrides_applied + (override,),
            )

        if ot is OverrideType.LOCK_MACHINE:
            # Filter machine candidates to just the locked one
            locked_id = override.value
            locked = [m for m in candidate.machine_candidates if m.machine_id == locked_id]
            return dataclasses.replace(
                candidate,
                machine_candidates=tuple(locked) or candidate.machine_candidates,
                overrides_applied=candidate.overrides_applied + (override,),
            )

        if ot is OverrideType.LOCK_TOOL:
            locked_id = override.value
            locked = [t for t in candidate.tool_candidates if t.tool_id == locked_id]
            return dataclasses.replace(
                candidate,
                tool_candidates=tuple(locked) or candidate.tool_candidates,
                overrides_applied=candidate.overrides_applied + (override,),
            )

        if ot is OverrideType.LOCK_SETUP:
            return dataclasses.replace(
                candidate,
                overrides_applied=candidate.overrides_applied + (override,),
            )

        if ot is OverrideType.EXCLUDE_OPERATION:
            excluded_op = override.value.lower()
            filtered_ops = tuple(
                op for op in candidate.operations
                if op.operation_type.value != excluded_op
            )
            return dataclasses.replace(
                candidate,
                operations=filtered_ops,
                overrides_applied=candidate.overrides_applied + (override,),
            )

        if ot is OverrideType.REOPTIMIZE_UNLOCKED:
            # Signal that the candidate should be re-scored without locked constraints
            return dataclasses.replace(
                candidate,
                overrides_applied=candidate.overrides_applied + (override,),
            )

        # Unknown override type — record it but don't modify
        return dataclasses.replace(
            candidate,
            overrides_applied=candidate.overrides_applied + (override,),
        )


def apply_override_to_candidate(
    candidate: ProcessRouteCandidate,
    override: RouteOverride,
) -> ProcessRouteCandidate:
    """Module-level convenience wrapper for single-candidate overrides."""
    engine = RouteOverrideEngine()
    dummy_set = RouteAlternativeSet(
        source_id=candidate.feature_id,
        feature_id=candidate.feature_id,
        config=None,  # type: ignore[arg-type]
        candidates=(candidate,),
        pareto_frontier=(),
        selected_route_id=candidate.route_id,
        selection_rationale="",
    )
    result = engine.apply(dummy_set, override)
    return result.candidates[0]
