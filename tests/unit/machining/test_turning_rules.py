"""Stage 3B tests: turning EngineeringRule wrappers."""

from __future__ import annotations

from decimal import Decimal

from backend.core.rules import RuleRegistry
from backend.domain.result import ResultStatus
from backend.domain.units import Quantity, Unit
from backend.machining.turning_rules import (
    BoringFinalDiameterRule,
    BoringRadialStockRule,
    BoringRemovedVolumeRule,
    ExternalFinalDiameterRule,
    ExternalRadialStockRule,
    ExternalRemovedVolumeRule,
    FacingRemovedVolumeRule,
    FacingTimeRule,
    FacingTravelRule,
    LongitudinalTurningTimeRule,
    PassCountRule,
    TurningDirectMRRRule,
    TurningMRRFromVolumeTimeRule,
    foundational_turning_rules,
)


class TestExternalTurningRules:
    def test_radial_stock_rule_pass(self) -> None:
        rule = ExternalRadialStockRule()
        result = rule.evaluate({
            "initial_diameter": Quantity.of(50, Unit.MM),
            "final_diameter": Quantity.of(46, Unit.MM),
        })
        assert result.status is ResultStatus.PASS
        assert result.outputs["radial_stock"].value == Decimal("2")

    def test_final_diameter_rule_pass(self) -> None:
        rule = ExternalFinalDiameterRule()
        result = rule.evaluate({
            "initial_diameter": Quantity.of(50, Unit.MM),
            "radial_depth": Quantity.of(2, Unit.MM),
        })
        assert result.status is ResultStatus.PASS
        assert result.outputs["final_diameter"].value == Decimal("46")

    def test_radial_stock_rule_invalid_fails(self) -> None:
        rule = ExternalRadialStockRule()
        result = rule.evaluate({
            "initial_diameter": Quantity.of(46, Unit.MM),
            "final_diameter": Quantity.of(50, Unit.MM),
        })
        assert result.status is ResultStatus.FAIL

    def test_radial_stock_rule_missing_input(self) -> None:
        rule = ExternalRadialStockRule()
        result = rule.evaluate({"initial_diameter": Quantity.of(50, Unit.MM)})
        assert result.status is ResultStatus.INSUFFICIENT_DATA


class TestBoringRules:
    def test_boring_radial_stock_pass(self) -> None:
        rule = BoringRadialStockRule()
        result = rule.evaluate({
            "initial_diameter": Quantity.of(20, Unit.MM),
            "final_diameter": Quantity.of(24, Unit.MM),
        })
        assert result.status is ResultStatus.PASS
        assert result.outputs["radial_stock"].value == Decimal("2")

    def test_boring_final_diameter_pass(self) -> None:
        rule = BoringFinalDiameterRule()
        result = rule.evaluate({
            "initial_diameter": Quantity.of(20, Unit.MM),
            "radial_depth": Quantity.of(2, Unit.MM),
        })
        assert result.status is ResultStatus.PASS
        assert result.outputs["final_diameter"].value == Decimal("24")

    def test_boring_invalid_fails(self) -> None:
        rule = BoringRadialStockRule()
        result = rule.evaluate({
            "initial_diameter": Quantity.of(24, Unit.MM),
            "final_diameter": Quantity.of(20, Unit.MM),
        })
        assert result.status is ResultStatus.FAIL


class TestPassCountRule:
    def test_exact_division(self) -> None:
        rule = PassCountRule()
        result = rule.evaluate({
            "total_radial_stock": Quantity.of(6, Unit.MM),
            "max_radial_depth_per_pass": Quantity.of(2, Unit.MM),
        })
        assert result.status is ResultStatus.PASS
        assert result.outputs["pass_count"].value == Decimal("3")

    def test_remainder_ceils(self) -> None:
        rule = PassCountRule()
        result = rule.evaluate({
            "total_radial_stock": Quantity.of(5, Unit.MM),
            "max_radial_depth_per_pass": Quantity.of(2, Unit.MM),
        })
        assert result.status is ResultStatus.PASS
        assert result.outputs["pass_count"].value == Decimal("3")

    def test_zero_stock_zero_passes(self) -> None:
        rule = PassCountRule()
        result = rule.evaluate({
            "total_radial_stock": Quantity.of(0, Unit.MM),
            "max_radial_depth_per_pass": Quantity.of(2, Unit.MM),
        })
        assert result.status is ResultStatus.PASS
        assert result.outputs["pass_count"].value == Decimal("0")

    def test_max_depth_zero_rejected(self) -> None:
        rule = PassCountRule()
        result = rule.evaluate({
            "total_radial_stock": Quantity.of(5, Unit.MM),
            "max_radial_depth_per_pass": Quantity.of(0, Unit.MM),
        })
        assert result.status is ResultStatus.FAIL


class TestVolumeRules:
    def test_external_removed_volume_pass(self) -> None:
        rule = ExternalRemovedVolumeRule()
        result = rule.evaluate({
            "initial_diameter": Quantity.of(50, Unit.MM),
            "final_diameter": Quantity.of(46, Unit.MM),
            "axial_length": Quantity.of(100, Unit.MM),
        })
        assert result.status is ResultStatus.PASS
        assert result.outputs["removed_volume"].unit is Unit.MM3

    def test_boring_removed_volume_pass(self) -> None:
        rule = BoringRemovedVolumeRule()
        result = rule.evaluate({
            "initial_diameter": Quantity.of(20, Unit.MM),
            "final_diameter": Quantity.of(24, Unit.MM),
            "axial_length": Quantity.of(50, Unit.MM),
        })
        assert result.status is ResultStatus.PASS
        assert result.outputs["removed_volume"].unit is Unit.MM3


class TestTurningTimeMRRRules:
    def test_longitudinal_time_pass(self) -> None:
        rule = LongitudinalTurningTimeRule()
        result = rule.evaluate({
            "spindle_speed": Quantity.of(1000, Unit.RPM),
            "feed_per_rev": Quantity.of(0.2, Unit.MM_REV),
            "machining_length": Quantity.of(100, Unit.MM),
        })
        assert result.status is ResultStatus.PASS
        assert result.outputs["time"].value == Decimal("0.5")

    def test_turning_mrr_volume_time_pass(self) -> None:
        rule = TurningMRRFromVolumeTimeRule()
        result = rule.evaluate({
            "removed_volume": Quantity.of(1000, Unit.MM3),
            "machining_time": Quantity.of(2, Unit.MIN),
        })
        assert result.status is ResultStatus.PASS
        assert result.outputs["mrr"].value == Decimal("500")
        assert result.outputs["mrr"].unit is Unit.MM3_MIN

    def test_turning_direct_mrr_pass(self) -> None:
        rule = TurningDirectMRRRule()
        result = rule.evaluate({
            "initial_diameter": Quantity.of(50, Unit.MM),
            "final_diameter": Quantity.of(46, Unit.MM),
            "feed_rate": Quantity.of(200, Unit.MM_MIN),
        })
        assert result.status is ResultStatus.PASS
        assert result.outputs["mrr"].unit is Unit.MM3_MIN

    def test_time_rule_zero_rpm_fails(self) -> None:
        rule = LongitudinalTurningTimeRule()
        result = rule.evaluate({
            "spindle_speed": Quantity.of(0, Unit.RPM),
            "feed_per_rev": Quantity.of(0.2, Unit.MM_REV),
            "machining_length": Quantity.of(100, Unit.MM),
        })
        assert result.status is ResultStatus.FAIL


class TestFacingRules:
    def test_facing_travel_pass(self) -> None:
        rule = FacingTravelRule()
        result = rule.evaluate({
            "outer_diameter": Quantity.of(100, Unit.MM),
            "inner_diameter": Quantity.of(0, Unit.MM),
        })
        assert result.status is ResultStatus.PASS
        assert result.outputs["facing_travel"].value == Decimal("50")

    def test_facing_travel_with_allowances(self) -> None:
        rule = FacingTravelRule()
        result = rule.evaluate({
            "outer_diameter": Quantity.of(100, Unit.MM),
            "inner_diameter": Quantity.of(40, Unit.MM),
            "approach_allowance": Quantity.of(1, Unit.MM),
            "overtravel_allowance": Quantity.of(1, Unit.MM),
        })
        assert result.status is ResultStatus.PASS
        assert result.outputs["facing_travel"].value == Decimal("32")

    def test_facing_time_pass(self) -> None:
        rule = FacingTimeRule()
        result = rule.evaluate({
            "spindle_speed": Quantity.of(500, Unit.RPM),
            "feed_per_rev": Quantity.of(0.1, Unit.MM_REV),
            "radial_travel": Quantity.of(50, Unit.MM),
        })
        assert result.status is ResultStatus.PASS
        assert result.outputs["time"].unit is Unit.MIN

    def test_facing_volume_pass(self) -> None:
        rule = FacingRemovedVolumeRule()
        result = rule.evaluate({
            "outer_diameter": Quantity.of(100, Unit.MM),
            "inner_diameter": Quantity.of(40, Unit.MM),
            "face_depth": Quantity.of(2, Unit.MM),
        })
        assert result.status is ResultStatus.PASS
        assert result.outputs["removed_volume"].unit is Unit.MM3


class TestRuleRegistry:
    def test_all_turning_rules_registerable(self) -> None:
        registry = RuleRegistry()
        for rule in foundational_turning_rules():
            registry.register(rule)
        assert len(registry) == 14

    def test_turning_rule_ids_unique(self) -> None:
        ids = [r.rule_id for r in foundational_turning_rules()]
        assert len(ids) == len(set(ids))

    def test_turning_rule_ids_do_not_collide_with_stage_3a(self) -> None:
        from backend.machining.rules import foundational_machining_rules
        s3a_ids = {r.rule_id for r in foundational_machining_rules()}
        s3b_ids = {r.rule_id for r in foundational_turning_rules()}
        assert s3a_ids.isdisjoint(s3b_ids)
