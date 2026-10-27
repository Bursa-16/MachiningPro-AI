"""Route Explanation Engine — EPIC_04E Phase 2.

Generates human-readable explanation for why a route was selected,
ranked, and what uncertainties exist.

PROCESS_ROUTE_EXPLANATION_IMPLEMENTED=YES
BLACK_BOX_AI_SCORE_USED=NO
"""

from __future__ import annotations

from backend.drawing_intelligence.route_domain import (
    OverallRiskLevel,
    ProcessRouteCandidate,
    RouteExplanation,
)
from backend.drawing_intelligence.route_strategies import RouteStrategy

__all__ = ["RouteExplanationEngine", "explain_selection"]


class RouteExplanationEngine:
    """Builds RouteExplanation for a selected candidate.

    PROCESS_ROUTE_EXPLANATION_IMPLEMENTED=YES
    """

    def build(
        self,
        selected: ProcessRouteCandidate,
        alternatives: list[ProcessRouteCandidate],
        strategy: str,
    ) -> RouteExplanation:
        """Build a complete explanation for the selected route."""
        why_selected = self._why_selected(selected, strategy)
        why_ranked = self._why_ranked_above(selected, alternatives)
        gdt_decisions = self._gdt_decisions(selected)
        machine_rationale = self._machine_rationale(selected)
        tool_rationale = self._tool_rationale(selected)
        rejected_summary = self._rejected_summary(alternatives)
        uncertain = self._uncertain_items(selected)

        return RouteExplanation(
            why_selected=why_selected,
            why_ranked_above_alternatives=tuple(why_ranked),
            gdt_tolerance_decisions=tuple(gdt_decisions),
            machine_selection_rationale=machine_rationale,
            tool_selection_rationale=tool_rationale,
            rejected_alternatives_summary=tuple(rejected_summary),
            uncertain_data_items=tuple(uncertain),
        )

    def _why_selected(self, c: ProcessRouteCandidate, strategy: str) -> str:
        score = c.score.total
        feasibility = c.feasibility.status.value
        template_hint = c.route_id
        return (
            f"Route {template_hint} selected by {strategy} strategy "
            f"with score {score}/100 ({feasibility}). "
            f"Machine candidates: {len(c.machine_candidates)}, "
            f"tool candidates: {len(c.tool_candidates)}, "
            f"risk: {c.risk.overall_risk.value}."
        )

    def _why_ranked_above(
        self,
        selected: ProcessRouteCandidate,
        alternatives: list[ProcessRouteCandidate],
    ) -> list[str]:
        reasons: list[str] = []
        for alt in alternatives:
            if alt.route_id == selected.route_id:
                continue
            score_diff = selected.score.total - alt.score.total
            if score_diff > 0:
                reasons.append(
                    f"Ranked above {alt.route_id}: score {selected.score.total} "
                    f"vs {alt.score.total} (+{score_diff} pts)."
                )
            elif not alt.is_feasible and selected.is_feasible:
                reasons.append(
                    f"Ranked above {alt.route_id}: "
                    f"{alt.feasibility.status.value} route excluded."
                )
        return reasons

    def _gdt_decisions(self, c: ProcessRouteCandidate) -> list[str]:
        decisions: list[str] = []
        if c.score.gdt_confidence >= 8:
            decisions.append(
                "Route is rated GD&T-capable — selected for tight tolerance requirements."
            )
        elif c.score.gdt_confidence < 5:
            decisions.append(
                "Route is NOT rated for tight GD&T — verify capability before production use."
            )
        return decisions

    def _machine_rationale(self, c: ProcessRouteCandidate) -> str:
        if not c.machine_candidates:
            return (
                "No machine candidates found in catalog. "
                "Verify machine availability on shop floor."
            )
        top = c.machine_candidates[0]
        return (
            f"Top machine candidate: {top.manufacturer} {top.model} "
            f"(score {top.suitability_score}/100). "
            f"{len(c.machine_candidates)} candidate(s) total. REFERENCE_ONLY."
        )

    def _tool_rationale(self, c: ProcessRouteCandidate) -> str:
        if not c.tool_candidates:
            return (
                "No tool candidates found in catalog. "
                "Source appropriate tooling from a specialist."
            )
        top = c.tool_candidates[0]
        return (
            f"Top tool candidate: {top.manufacturer} {top.product_name} "
            f"(score {top.suitability_score}/100). "
            f"{len(c.tool_candidates)} candidate(s) total. REFERENCE_ONLY."
        )

    def _rejected_summary(self, alternatives: list[ProcessRouteCandidate]) -> list[str]:
        rejected = [a for a in alternatives if not a.is_feasible]
        return [
            f"REJECTED {a.route_id}: {a.feasibility.reason}"
            for a in rejected
        ]

    def _uncertain_items(self, c: ProcessRouteCandidate) -> list[str]:
        items: list[str] = list(c.unresolved_items)
        if c.risk.overall_risk in (OverallRiskLevel.HIGH, OverallRiskLevel.CRITICAL):
            items.append(
                f"Risk level is {c.risk.overall_risk.value} — "
                "review all risk flags before releasing to production."
            )
        if not c.parameter_context:
            items.append(
                "No cutting parameters in registry for this material/operation combination."
            )
        return items


def explain_selection(
    selected: ProcessRouteCandidate,
    alternatives: list[ProcessRouteCandidate],
    strategy: str = RouteStrategy.BALANCED,
) -> RouteExplanation:
    """Module-level convenience wrapper."""
    return RouteExplanationEngine().build(selected, alternatives, strategy)
