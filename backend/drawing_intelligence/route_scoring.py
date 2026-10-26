"""Route Scoring Engine (EPIC_04 Phase 2).

Scores AlternativeRoutes deterministically. Higher score = preferred route.

Scoring criteria (all deterministic, no AI):
  1. Completeness (does route achieve the Ra requirement?)         40 pts
  2. Operation count efficiency (fewer ops = higher score)        20 pts
  3. SEQ rule compliance                                          20 pts
  4. DFM compliance (avoids grinding when not needed)             10 pts
  5. Tool availability proxy (standard ops score higher)          10 pts

Total: 100 points maximum.

FABRICATED_CUTTING_PARAMETER=NO
LLM_ALLOWED_TO_OVERRIDE_ENGINEERING_FACTS=NO
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from backend.domain.enums import OperationType
from backend.drawing_intelligence.route_generator import AlternativeRoute
from backend.drawing_intelligence.sequence_rules import (
    SequenceRuleSeverity,
    check_sequence,
)

__all__ = [
    "RouteScore",
    "ScoredRoute",
    "RouteScorer",
    "score_routes",
]

# Operations that are considered "standard" (widely available, lower tooling cost)
_STANDARD_OPS: frozenset[OperationType] = frozenset({
    OperationType.TURNING,
    OperationType.FACING,
    OperationType.MILLING,
    OperationType.DRILLING,
    OperationType.TAPPING,
    OperationType.REAMING,
    OperationType.BORING,
    OperationType.DEBURRING,
})

_SPECIALTY_OPS: frozenset[OperationType] = frozenset({
    OperationType.GRINDING,
    OperationType.HONING,
    OperationType.LAPPING,
    OperationType.THREADING,
})


@dataclass(frozen=True, slots=True)
class RouteScore:
    """Decomposed score for one route."""

    completeness: int      # 0–40 pts: Ra requirement met
    efficiency: int        # 0–20 pts: fewer operations = higher
    seq_compliance: int    # 0–20 pts: sequence rule satisfaction
    dfm_compliance: int    # 0–10 pts: avoids over-engineering
    availability: int      # 0–10 pts: standard vs. specialty ops

    @property
    def total(self) -> int:
        return (
            self.completeness
            + self.efficiency
            + self.seq_compliance
            + self.dfm_compliance
            + self.availability
        )


@dataclass(frozen=True, slots=True)
class ScoredRoute:
    """Route with attached score."""

    route: AlternativeRoute
    score: RouteScore


class RouteScorer:
    """Scores a list of AlternativeRoutes and returns them ranked best-first."""

    def score_all(self, routes: list[AlternativeRoute]) -> list[ScoredRoute]:
        scored = [self._score(r) for r in routes]
        # Sort descending by total score, then by route_id for determinism
        scored.sort(key=lambda s: (-s.score.total, s.route.route_id))
        return scored

    def _score(self, route: AlternativeRoute) -> ScoredRoute:
        score = RouteScore(
            completeness=self._completeness(route),
            efficiency=self._efficiency(route),
            seq_compliance=self._seq_compliance(route),
            dfm_compliance=self._dfm_compliance(route),
            availability=self._availability(route),
        )
        return ScoredRoute(route=route, score=score)

    # ------------------------------------------------------------------ #
    # Individual criteria
    # ------------------------------------------------------------------ #

    def _completeness(self, route: AlternativeRoute) -> int:
        """40 pts if Ra requirement satisfied, else 0."""
        if route.required_ra_um is None:
            return 40  # no requirement = fully satisfied
        if route.achievable_ra_um <= route.required_ra_um:
            return 40
        return 0

    def _efficiency(self, route: AlternativeRoute) -> int:
        """20 pts for 1-op route; decrements by 5 per additional op; floor 0."""
        n_ops = len(route.operations)
        score = max(0, 20 - (n_ops - 1) * 5)
        return score

    def _seq_compliance(self, route: AlternativeRoute) -> int:
        """20 pts; deduct 10 per BLOCKING violation, 5 per ADVISORY violation."""
        results = check_sequence(
            list(route.operations), route.feature_type
        )
        score = 20
        for r in results:
            if not r.satisfied:
                if r.severity == SequenceRuleSeverity.BLOCKING:
                    score -= 10
                else:
                    score -= 5
        return max(0, score)

    def _dfm_compliance(self, route: AlternativeRoute) -> int:
        """10 pts; deduct 5 for each specialty op that could be avoided."""
        required_ra = route.required_ra_um
        score = 10
        for op in route.operations:
            if op in _SPECIALTY_OPS:
                # Penalty if specialty op isn't warranted by Ra requirement
                if required_ra is None or required_ra > Decimal("0.8"):
                    score -= 5
        return max(0, score)

    def _availability(self, route: AlternativeRoute) -> int:
        """10 pts; deduct 3 per specialty op (lower availability assumed)."""
        score = 10
        specialty_count = sum(
            1 for op in route.operations if op in _SPECIALTY_OPS
        )
        score -= specialty_count * 3
        return max(0, score)


def score_routes(routes: list[AlternativeRoute]) -> list[ScoredRoute]:
    """Convenience function: score and rank a list of routes."""
    return RouteScorer().score_all(routes)
