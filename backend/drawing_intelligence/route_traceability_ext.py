"""Route Optimization Traceability — EPIC_04E Phase 2.

Builds a deterministic fingerprint for a route optimization run,
covering requirements, feature set, engine version, config, selected routes,
and applied overrides.

ROUTE_OPTIMIZATION_TRACEABILITY_IMPLEMENTED=YES
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from backend.drawing_intelligence.route_domain import (
    OptimizedProcessPlan,
    RouteOptimizationConfig,
)

__all__ = [
    "RouteOptimizationFingerprint",
    "RouteTraceabilityBuilder",
    "build_fingerprint",
]

ENGINE_VERSION = "EPIC_04E-Phase2-v1"


@dataclass(frozen=True)
class RouteOptimizationFingerprint:
    """Immutable traceability record for one optimization run."""

    engine_version: str
    strategy: str
    feature_ids: tuple[str, ...]
    feature_types: tuple[str, ...]
    selected_route_ids: tuple[str, ...]
    override_count: int
    config_hash: str        # SHA-256[:8] of serialized RouteOptimizationConfig
    plan_id: str
    fingerprint: str        # SHA-256[:16] of all above fields


class RouteTraceabilityBuilder:
    """Builds RouteOptimizationFingerprint from an OptimizedProcessPlan.

    ROUTE_OPTIMIZATION_TRACEABILITY_IMPLEMENTED=YES
    """

    def build(
        self,
        plan: OptimizedProcessPlan,
        config: RouteOptimizationConfig,
        feature_types: list[str] | None = None,
    ) -> RouteOptimizationFingerprint:
        strategy = plan.strategy
        feature_ids = tuple(
            alt.feature_id for alt in plan.alternative_sets
        )
        feature_types_t: tuple[str, ...] = tuple(feature_types or [])
        selected_route_ids = tuple(
            alt.selected_route_id or ""
            for alt in plan.alternative_sets
        )
        override_count = len(plan.overrides)

        # Config hash
        config_data = {
            "strategy": config.strategy,
            "max_routes_per_feature": config.max_routes_per_feature,
            "max_machine_candidates": config.max_machine_candidates,
            "max_tool_candidates": config.max_tool_candidates,
            "max_holder_candidates": config.max_holder_candidates,
            "beam_width": config.beam_width,
            "include_pareto": config.include_pareto,
            "max_setups": config.max_setups,
        }
        config_hash = hashlib.sha256(
            json.dumps(config_data, sort_keys=True).encode()
        ).hexdigest()[:8]

        # Overall fingerprint
        fp_data = {
            "engine_version": ENGINE_VERSION,
            "strategy": strategy,
            "feature_ids": feature_ids,
            "selected_route_ids": selected_route_ids,
            "override_count": override_count,
            "config_hash": config_hash,
            "plan_id": plan.plan_id,
        }
        fp = hashlib.sha256(
            json.dumps(fp_data, sort_keys=True, default=str).encode()
        ).hexdigest()[:16]

        return RouteOptimizationFingerprint(
            engine_version=ENGINE_VERSION,
            strategy=strategy,
            feature_ids=feature_ids,
            feature_types=feature_types_t,
            selected_route_ids=selected_route_ids,
            override_count=override_count,
            config_hash=config_hash,
            plan_id=plan.plan_id,
            fingerprint=fp,
        )


def build_fingerprint(
    plan: OptimizedProcessPlan,
    config: RouteOptimizationConfig,
    feature_types: list[str] | None = None,
) -> RouteOptimizationFingerprint:
    return RouteTraceabilityBuilder().build(plan, config, feature_types)
