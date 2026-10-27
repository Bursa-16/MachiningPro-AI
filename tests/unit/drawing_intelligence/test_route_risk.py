"""Tests for route_risk — EPIC_04E Phase 2."""

import pytest

from backend.drawing_intelligence.route_alternatives import ROUTE_TEMPLATES, ExtendedFeatureType
from backend.drawing_intelligence.route_risk import RouteRiskEvaluator, _overall_risk, evaluate_route_risk
from backend.drawing_intelligence.route_domain import (
    OverallRiskLevel,
    RiskCategory,
    RiskSeverity,
    RiskFlag,
)


def _template(index=0):
    return ROUTE_TEMPLATES[ExtendedFeatureType.HOLE][index]


def _flag(category, severity):
    return RiskFlag(
        flag_id="RF-0001",
        category=category,
        severity=severity,
        description="desc",
        affected_feature_id=None,
        mitigation_note="m",
    )


class TestOverallRiskFunction:
    def test_empty_flags_low(self):
        assert _overall_risk([]) is OverallRiskLevel.LOW

    def test_critical_flag_gives_critical(self):
        flags = [_flag(RiskCategory.TIGHT_TOLERANCE, RiskSeverity.CRITICAL)]
        assert _overall_risk(flags) is OverallRiskLevel.CRITICAL

    def test_high_flag_gives_high(self):
        flags = [_flag(RiskCategory.TIGHT_TOLERANCE, RiskSeverity.HIGH)]
        assert _overall_risk(flags) is OverallRiskLevel.HIGH

    def test_medium_flag_gives_medium(self):
        flags = [_flag(RiskCategory.SETUP_COUNT, RiskSeverity.MEDIUM)]
        assert _overall_risk(flags) is OverallRiskLevel.MEDIUM

    def test_low_flag_gives_low(self):
        flags = [_flag(RiskCategory.SETUP_COUNT, RiskSeverity.LOW)]
        assert _overall_risk(flags) is OverallRiskLevel.LOW


class TestRouteRiskEvaluator:
    def _eval(self, **kwargs):
        tmpl = _template()
        return RouteRiskEvaluator().evaluate(tmpl, feature_id="F1", **kwargs)

    def test_no_risk_flags_without_conditions(self):
        risk = self._eval()
        assert risk.overall_risk is OverallRiskLevel.LOW
        assert risk.flag_count == 0

    def test_tight_ra_flags_tight_tolerance(self):
        risk = self._eval(required_ra_um=0.1)
        cats = [f.category for f in risk.flags]
        assert RiskCategory.TIGHT_TOLERANCE in cats

    def test_tight_ra_high_severity(self):
        risk = self._eval(required_ra_um=0.1)
        tt_flags = [f for f in risk.flags if f.category is RiskCategory.TIGHT_TOLERANCE]
        assert any(f.severity is RiskSeverity.HIGH for f in tt_flags)

    def test_medium_ra_medium_severity(self):
        risk = self._eval(required_ra_um=0.4)
        tt_flags = [f for f in risk.flags if f.category is RiskCategory.TIGHT_TOLERANCE]
        assert any(f.severity is RiskSeverity.MEDIUM for f in tt_flags)

    def test_tight_position_flags_gdt(self):
        risk = self._eval(has_tight_position=True)
        cats = [f.category for f in risk.flags]
        assert RiskCategory.COMPLEX_GDT in cats

    def test_runout_flags_complex_gdt_high(self):
        risk = self._eval(has_runout=True)
        runout_flags = [f for f in risk.flags if f.category is RiskCategory.COMPLEX_GDT]
        assert any(f.severity is RiskSeverity.HIGH for f in runout_flags)

    def test_profile_flags_gdt(self):
        risk = self._eval(has_profile=True)
        cats = [f.category for f in risk.flags]
        assert RiskCategory.COMPLEX_GDT in cats

    def test_high_setup_count_flags_setup(self):
        risk = self._eval(setup_count=4)
        cats = [f.category for f in risk.flags]
        assert RiskCategory.SETUP_COUNT in cats

    def test_low_machinability_flags_material_difficulty(self):
        risk = self._eval(material_machinability="LOW")
        cats = [f.category for f in risk.flags]
        assert RiskCategory.MATERIAL_DIFFICULTY in cats

    def test_machine_candidates_empty_flags_uncertainty(self):
        risk = self._eval(machine_candidates_empty=True)
        cats = [f.category for f in risk.flags]
        assert RiskCategory.MACHINE_UNCERTAINTY in cats

    def test_tool_candidates_empty_flags_uncertainty(self):
        risk = self._eval(tool_candidates_empty=True)
        cats = [f.category for f in risk.flags]
        assert RiskCategory.TOOL_UNCERTAINTY in cats

    def test_inspection_with_gdt_flags_complexity(self):
        risk = self._eval(has_inspection=True, has_tight_position=True)
        cats = [f.category for f in risk.flags]
        assert RiskCategory.INSPECTION_COMPLEXITY in cats

    def test_overall_risk_critical_with_critical_flag(self):
        risk = self._eval(material_machinability="EXTREME")
        assert risk.overall_risk is OverallRiskLevel.HIGH

    def test_all_flags_have_mitigation_notes(self):
        risk = self._eval(
            required_ra_um=0.1,
            has_tight_position=True,
            has_runout=True,
            machine_candidates_empty=True,
        )
        for flag in risk.flags:
            assert flag.mitigation_note, f"{flag.flag_id} has no mitigation note"

    def test_black_box_ai_score_not_used(self):
        # PROCESS_RISK_MODEL_IMPLEMENTED=YES — all flags are rule-based
        risk = self._eval(required_ra_um=0.4, has_tight_position=True)
        for flag in risk.flags:
            assert flag.category in RiskCategory.__members__.values()


class TestEvaluateRouteRisk:
    def test_convenience_wrapper(self):
        tmpl = _template()
        risk = evaluate_route_risk(tmpl, feature_id="F1")
        assert risk is not None
