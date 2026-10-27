"""Tests for route_domain — EPIC_04E Phase 2."""

import pytest

from backend.drawing_intelligence.route_domain import (
    CycleTimeClassification,
    CycleTimeComponent,
    CycleTimeContext,
    OverallRiskLevel,
    OverrideType,
    ParetoRoute,
    ProcessCapabilityConfidence,
    ProcessRouteCandidate,
    RiskCategory,
    RiskFlag,
    RiskSeverity,
    RouteAlternativeSet,
    RouteExplanation,
    RouteFeasibility,
    RouteFeasibilityStatus,
    RouteOperation,
    RouteOptimizationConfig,
    RouteRejection,
    RouteRejectionReason,
    RouteRisk,
    RouteScoreBreakdown,
    RouteSetup,
    RouteStatus,
)
from backend.domain.enums import OperationType


def _make_score(**kwargs):
    defaults = dict(
        technical_feasibility=10,
        requirement_coverage=10,
        process_capability=10,
        gdt_confidence=8,
        machine_compatibility=8,
        tool_compatibility=8,
        setup_efficiency=8,
        cycle_time=0,
        data_completeness=3,
        risk_penalty=0,
        strategy_bonus=0,
    )
    defaults.update(kwargs)
    return RouteScoreBreakdown(**defaults)


def _make_feasibility(status=RouteFeasibilityStatus.FEASIBLE):
    return RouteFeasibility(
        status=status,
        reason="ok",
        requirement_coverage=1.0,
        unresolved_items=(),
    )


def _make_explanation():
    return RouteExplanation(
        why_selected="top score",
        why_ranked_above_alternatives=(),
        gdt_tolerance_decisions=(),
        machine_selection_rationale=None,
        tool_selection_rationale=None,
        rejected_alternatives_summary=(),
        uncertain_data_items=(),
    )


def _make_candidate(route_id="R1", feasibility=None, score=None):
    feasibility = feasibility or _make_feasibility()
    score = score or _make_score()
    op = RouteOperation(
        op_id="OP1",
        sequence_no=1,
        operation_type=OperationType.DRILLING,
        sub_operation=None,
        setup_id="S1",
        feature_id="F1",
        tool_type_required=None,
        target_ra_um=None,
        target_it_grade=None,
        is_inspection=False,
        notes="",
    )
    setup = RouteSetup(
        setup_id="S1",
        sequence_no=1,
        label="Setup 1",
        feature_ids=("F1",),
        datum_reference=None,
        machine_type_required=None,
        accessibility_notes=(),
        operation_ids=("OP1",),
    )
    risk = RouteRisk(flags=(), overall_risk=OverallRiskLevel.LOW)
    return ProcessRouteCandidate(
        route_id=route_id,
        feature_id="F1",
        strategy="BALANCED",
        status=RouteStatus.DRAFT,
        feasibility=feasibility,
        setups=(setup,),
        operations=(op,),
        machine_candidates=(),
        tool_candidates=(),
        holder_candidates=(),
        parameter_context=None,
        cycle_time_context=None,
        risk=risk,
        score=score,
        confidence=ProcessCapabilityConfidence.LITERATURE_REFERENCE,
        explanation=_make_explanation(),
        rejection_reasons=(),
        unresolved_items=(),
        overrides_applied=(),
        traceability_fingerprint="abc123",
    )


class TestRouteScoreBreakdown:
    def test_total_clamps_at_100(self):
        s = _make_score(
            technical_feasibility=15,
            requirement_coverage=15,
            process_capability=15,
            gdt_confidence=10,
            machine_compatibility=10,
            tool_compatibility=10,
            setup_efficiency=10,
            cycle_time=5,
            data_completeness=5,
            risk_penalty=0,
            strategy_bonus=10,
        )
        assert s.total == 100

    def test_total_clamps_at_0(self):
        s = _make_score(
            technical_feasibility=0,
            requirement_coverage=0,
            process_capability=0,
            gdt_confidence=0,
            machine_compatibility=0,
            tool_compatibility=0,
            setup_efficiency=0,
            cycle_time=0,
            data_completeness=0,
            risk_penalty=-15,
            strategy_bonus=0,
        )
        assert s.total == 0

    def test_total_with_penalty(self):
        s = _make_score(
            technical_feasibility=10,
            requirement_coverage=10,
            process_capability=5,
            gdt_confidence=5,
            machine_compatibility=0,
            tool_compatibility=0,
            setup_efficiency=5,
            cycle_time=0,
            data_completeness=0,
            risk_penalty=-10,
            strategy_bonus=0,
        )
        assert s.total == 25


class TestProcessRouteCandidate:
    def test_is_feasible_feasible_status(self):
        c = _make_candidate(feasibility=_make_feasibility(RouteFeasibilityStatus.FEASIBLE))
        assert c.is_feasible is True

    def test_is_feasible_conditional(self):
        c = _make_candidate(feasibility=_make_feasibility(RouteFeasibilityStatus.CONDITIONAL))
        assert c.is_feasible is True

    def test_is_feasible_infeasible(self):
        c = _make_candidate(feasibility=_make_feasibility(RouteFeasibilityStatus.INFEASIBLE))
        assert c.is_feasible is False

    def test_is_feasible_insufficient_data(self):
        c = _make_candidate(feasibility=_make_feasibility(RouteFeasibilityStatus.INSUFFICIENT_DATA))
        assert c.is_feasible is False

    def test_op_count_excludes_inspection(self):
        op_normal = RouteOperation(
            op_id="OP1", sequence_no=1,
            operation_type=OperationType.DRILLING, sub_operation=None,
            setup_id="S1", feature_id="F1", tool_type_required=None,
            target_ra_um=None, target_it_grade=None, is_inspection=False, notes="",
        )
        op_inspect = RouteOperation(
            op_id="INS1", sequence_no=2,
            operation_type=OperationType.INSPECTION, sub_operation=None,
            setup_id="S1", feature_id="F1", tool_type_required=None,
            target_ra_um=None, target_it_grade=None, is_inspection=True, notes="",
        )
        setup = RouteSetup(
            setup_id="S1", sequence_no=1, label="Setup 1",
            feature_ids=("F1",), datum_reference=None, machine_type_required=None,
            accessibility_notes=(), operation_ids=("OP1", "INS1"),
        )
        c = ProcessRouteCandidate(
            route_id="R1", feature_id="F1", strategy="BALANCED",
            status=RouteStatus.DRAFT,
            feasibility=_make_feasibility(),
            setups=(setup,), operations=(op_normal, op_inspect),
            machine_candidates=(), tool_candidates=(), holder_candidates=(),
            parameter_context=None, cycle_time_context=None,
            risk=RouteRisk(flags=(), overall_risk=OverallRiskLevel.LOW),
            score=_make_score(), confidence=ProcessCapabilityConfidence.LITERATURE_REFERENCE,
            explanation=_make_explanation(),
            rejection_reasons=(), unresolved_items=(),
            overrides_applied=(), traceability_fingerprint="fp",
        )
        assert c.op_count == 1
        assert c.setup_count == 1

    def test_status_is_draft_not_approved(self):
        c = _make_candidate()
        assert c.status is RouteStatus.DRAFT
        assert c.status != "APPROVED"

    def test_frozen(self):
        c = _make_candidate()
        with pytest.raises((AttributeError, TypeError)):
            c.route_id = "X"  # type: ignore[misc]


class TestRouteRisk:
    def test_flag_count(self):
        flag = RiskFlag(
            flag_id="RF-0001",
            category=RiskCategory.TIGHT_TOLERANCE,
            severity=RiskSeverity.HIGH,
            description="desc",
            affected_feature_id=None,
            mitigation_note="fix",
        )
        risk = RouteRisk(flags=(flag,), overall_risk=OverallRiskLevel.HIGH)
        assert risk.flag_count == 1

    def test_critical_count(self):
        crit = RiskFlag("RF-0001", RiskCategory.MACHINE_UNCERTAINTY, RiskSeverity.CRITICAL, "d", None, "m")
        high = RiskFlag("RF-0002", RiskCategory.TOOL_UNCERTAINTY, RiskSeverity.HIGH, "d", None, "m")
        risk = RouteRisk(flags=(crit, high), overall_risk=OverallRiskLevel.CRITICAL)
        assert risk.critical_count == 1
        assert risk.high_count == 1


class TestCycleTimeContext:
    def test_total_none_when_unknown(self):
        ctx = CycleTimeContext(
            components=(
                CycleTimeComponent("cutting", None, CycleTimeClassification.UNKNOWN, "no path"),
            ),
            total_s=None,
            is_partial=True,
            classification=CycleTimeClassification.UNKNOWN,
        )
        assert ctx.total_s is None
        assert ctx.is_partial is True

    def test_fabricated_cycle_time_flag(self):
        # FABRICATED_CYCLE_TIME=NO invariant: total_s must be None when path unknown
        ctx = CycleTimeContext(
            components=(
                CycleTimeComponent("cutting", None, CycleTimeClassification.UNKNOWN, "no path"),
            ),
            total_s=None,
            is_partial=True,
            classification=CycleTimeClassification.UNKNOWN,
        )
        assert ctx.total_s is None  # FABRICATED_CYCLE_TIME=NO


class TestRouteAlternativeSet:
    def test_feasible_count(self):
        c1 = _make_candidate("R1", feasibility=_make_feasibility(RouteFeasibilityStatus.FEASIBLE))
        c2 = _make_candidate("R2", feasibility=_make_feasibility(RouteFeasibilityStatus.INFEASIBLE))
        config = RouteOptimizationConfig()
        alt = RouteAlternativeSet(
            source_id="F1", feature_id="F1", config=config,
            candidates=(c1, c2), pareto_frontier=(),
            selected_route_id="R1", selection_rationale="top",
        )
        assert alt.feasible_count == 1


class TestRouteOptimizationConfig:
    def test_defaults(self):
        cfg = RouteOptimizationConfig()
        assert cfg.max_routes_per_feature == 5
        assert cfg.include_pareto is True
        assert cfg.max_setups == 6
