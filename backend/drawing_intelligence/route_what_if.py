"""Route What-If Engine — EPIC_04E Phase 2.

Supports strategy, machine, tool, and batch context what-if analysis.

PROCESS_ROUTE_WHAT_IF_IMPLEMENTED=YES
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.drawing_intelligence.route_domain import (
    RouteAlternativeSet,
    RouteOptimizationConfig,
)
from backend.drawing_intelligence.route_strategies import RouteStrategy

__all__ = [
    "WhatIfRequest",
    "WhatIfResult",
    "RouteWhatIfEngine",
]


@dataclass
class WhatIfRequest:
    """A single what-if scenario definition."""

    label: str                          # Human-readable label
    strategy: str | None = None        # Override strategy
    max_setups: int | None = None      # Override max setups
    include_pareto: bool = True


@dataclass
class WhatIfResult:
    """Result of one what-if scenario."""

    label: str
    strategy: str
    alternative_set: RouteAlternativeSet
    score_delta: int                    # vs baseline
    setup_delta: int                    # vs baseline
    feasible_count: int


class RouteWhatIfEngine:
    """Runs what-if scenarios by re-optimizing with altered parameters.

    PROCESS_ROUTE_WHAT_IF_IMPLEMENTED=YES
    """

    def run_batch(
        self,
        feature_req,
        scenarios: list[WhatIfRequest],
        baseline: RouteAlternativeSet,
        config: RouteOptimizationConfig | None = None,
    ) -> list[WhatIfResult]:
        """Run multiple what-if scenarios and compare to baseline."""
        from backend.drawing_intelligence.route_optimizer import RouteOptimizer

        optimizer = RouteOptimizer()
        results: list[WhatIfResult] = []

        baseline_score = _best_score(baseline)
        baseline_setups = _best_setups(baseline)

        for scenario in scenarios:
            strategy = scenario.strategy or RouteStrategy.BALANCED
            cfg = config or RouteOptimizationConfig()
            if scenario.max_setups:
                import dataclasses
                cfg = dataclasses.replace(cfg, max_setups=scenario.max_setups)
            cfg = dataclasses.replace(cfg, include_pareto=scenario.include_pareto)

            alt_set = optimizer.optimize_feature(feature_req, strategy=strategy, config=cfg)

            results.append(WhatIfResult(
                label=scenario.label,
                strategy=strategy,
                alternative_set=alt_set,
                score_delta=_best_score(alt_set) - baseline_score,
                setup_delta=_best_setups(alt_set) - baseline_setups,
                feasible_count=alt_set.feasible_count,
            ))

        return results


def _best_score(alt_set: RouteAlternativeSet) -> int:
    if not alt_set.candidates:
        return 0
    return max((c.score.total for c in alt_set.candidates if c.is_feasible), default=0)


def _best_setups(alt_set: RouteAlternativeSet) -> int:
    if not alt_set.candidates:
        return 0
    selected = next(
        (c for c in alt_set.candidates if c.route_id == alt_set.selected_route_id),
        None,
    )
    return selected.setup_count if selected else 1
