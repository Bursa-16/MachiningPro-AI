"""Route optimization strategy definitions and weight sets — EPIC_04E Phase 2.

Five deterministic strategies, each with a distinct weight set that
re-weights the RouteScoreBreakdown components.

ROUTE_STRATEGY_WEIGHTS_IMPLEMENTED=YES
ROUTE_STRATEGIES_IMPLEMENTED=YES
BLACK_BOX_AI_SCORE_USED=NO
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

__all__ = [
    "RouteStrategy",
    "StrategyWeights",
    "STRATEGY_WEIGHTS",
    "get_weights",
]


class RouteStrategy(StrEnum):
    """Named optimization strategies for process route generation."""

    BALANCED = "BALANCED"
    LOWEST_RISK = "LOWEST_RISK"
    MINIMUM_SETUP = "MINIMUM_SETUP"
    SHORTEST_CYCLE_TIME = "SHORTEST_CYCLE_TIME"
    HIGHEST_PROCESS_CAPABILITY = "HIGHEST_PROCESS_CAPABILITY"


@dataclass(frozen=True, slots=True)
class StrategyWeights:
    """Multiplier weights applied to RouteScoreBreakdown components.

    All weights are non-negative floats.  The score is computed as:
      component_raw * weight / default_weight  (clamped to component max).
    """

    strategy: RouteStrategy
    technical_feasibility: float
    requirement_coverage: float
    process_capability: float
    gdt_confidence: float
    machine_compatibility: float
    tool_compatibility: float
    setup_efficiency: float
    cycle_time: float
    data_completeness: float
    risk_weight: float          # multiplier on risk_penalty magnitude
    description: str


# Default (BALANCED) weights — all 1.0 means the raw score components apply as-is.
_BALANCED = StrategyWeights(
    strategy=RouteStrategy.BALANCED,
    technical_feasibility=1.0,
    requirement_coverage=1.0,
    process_capability=1.0,
    gdt_confidence=1.0,
    machine_compatibility=1.0,
    tool_compatibility=1.0,
    setup_efficiency=1.0,
    cycle_time=1.0,
    data_completeness=1.0,
    risk_weight=1.0,
    description=(
        "Balanced strategy — equal weighting across all scoring components. "
        "Suitable for general-purpose route selection."
    ),
)

_LOWEST_RISK = StrategyWeights(
    strategy=RouteStrategy.LOWEST_RISK,
    technical_feasibility=1.0,
    requirement_coverage=1.2,
    process_capability=1.3,
    gdt_confidence=1.5,
    machine_compatibility=1.0,
    tool_compatibility=1.0,
    setup_efficiency=0.5,
    cycle_time=0.3,
    data_completeness=1.2,
    risk_weight=2.5,             # risk penalties are 2.5× heavier
    description=(
        "Lowest-risk strategy — heavily penalises risk flags and GD&T uncertainty. "
        "Prefer proven processes over aggressive cycle-time reduction. "
        "Suitable for safety-critical or tight-tolerance parts."
    ),
)

_MINIMUM_SETUP = StrategyWeights(
    strategy=RouteStrategy.MINIMUM_SETUP,
    technical_feasibility=1.0,
    requirement_coverage=1.0,
    process_capability=1.0,
    gdt_confidence=1.0,
    machine_compatibility=1.2,
    tool_compatibility=1.0,
    setup_efficiency=2.5,        # setup count dominates
    cycle_time=0.8,
    data_completeness=0.8,
    risk_weight=0.8,
    description=(
        "Minimum-setup strategy — maximises setup consolidation. "
        "Prefers mill-turn or 5-axis routes that complete a feature in fewer setups. "
        "Suitable for low-batch / high-mix production."
    ),
)

_SHORTEST_CYCLE_TIME = StrategyWeights(
    strategy=RouteStrategy.SHORTEST_CYCLE_TIME,
    technical_feasibility=1.0,
    requirement_coverage=1.0,
    process_capability=0.8,
    gdt_confidence=0.8,
    machine_compatibility=1.2,
    tool_compatibility=1.2,
    setup_efficiency=1.0,
    cycle_time=3.0,              # cycle time component dominates
    data_completeness=0.6,
    risk_weight=0.7,
    description=(
        "Shortest-cycle-time strategy — heavily rewards low operation count and "
        "available cycle-time data. Only meaningful when cutting-path data is present. "
        "Suitable for high-volume production runs."
    ),
)

_HIGHEST_PROCESS_CAPABILITY = StrategyWeights(
    strategy=RouteStrategy.HIGHEST_PROCESS_CAPABILITY,
    technical_feasibility=1.2,
    requirement_coverage=1.5,
    process_capability=2.5,      # process capability dominates
    gdt_confidence=1.5,
    machine_compatibility=1.0,
    tool_compatibility=1.0,
    setup_efficiency=0.5,
    cycle_time=0.3,
    data_completeness=1.5,
    risk_weight=1.2,
    description=(
        "Highest-process-capability strategy — maximises Ra and IT-grade confidence. "
        "Prefers boring + honing over drilling-only, grinding over milling for finish. "
        "Suitable for precision / aerospace / medical parts."
    ),
)

STRATEGY_WEIGHTS: dict[RouteStrategy, StrategyWeights] = {
    RouteStrategy.BALANCED: _BALANCED,
    RouteStrategy.LOWEST_RISK: _LOWEST_RISK,
    RouteStrategy.MINIMUM_SETUP: _MINIMUM_SETUP,
    RouteStrategy.SHORTEST_CYCLE_TIME: _SHORTEST_CYCLE_TIME,
    RouteStrategy.HIGHEST_PROCESS_CAPABILITY: _HIGHEST_PROCESS_CAPABILITY,
}


def get_weights(strategy: RouteStrategy | str) -> StrategyWeights:
    key = RouteStrategy(strategy) if isinstance(strategy, str) else strategy
    return STRATEGY_WEIGHTS[key]
