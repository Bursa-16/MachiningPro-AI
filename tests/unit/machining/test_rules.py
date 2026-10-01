"""Stage 3A tests: machining-math EngineeringRule wrappers."""

from __future__ import annotations

from decimal import Decimal

from backend.core.rules import RuleRegistry
from backend.domain.result import ResultStatus
from backend.domain.units import Quantity, Unit
from backend.machining.rules import (
    CuttingSpeedFromSpindleSpeedRule,
    FeedRateFromRpmFeedPerRevRule,
    FeedRateFromRpmToothFeedRule,
    MachiningTimeRule,
    MillingMaterialRemovalRateRule,
    PowerFromTorqueRule,
    SpindleSpeedFromCuttingSpeedRule,
    TorqueFromPowerRule,
    foundational_machining_rules,
)


class TestRuleIntegration:
    def test_spindle_speed_rule_pass(self) -> None:
        rule = SpindleSpeedFromCuttingSpeedRule()
        result = rule.evaluate({
            "cutting_speed": Quantity.of(100, Unit.M_MIN),
            "diameter": Quantity.of(10, Unit.MM),
        })
        assert result.status is ResultStatus.PASS
        assert result.outputs["spindle_speed"].unit is Unit.RPM

    def test_cutting_speed_rule_round_trip(self) -> None:
        rule = CuttingSpeedFromSpindleSpeedRule()
        result = rule.evaluate({
            "spindle_speed": Quantity.of(3183, Unit.RPM),
            "diameter": Quantity.of(10, Unit.MM),
        })
        assert result.status is ResultStatus.PASS
        assert result.outputs["cutting_speed"].unit is Unit.M_MIN

    def test_feed_rate_rule(self) -> None:
        rule = FeedRateFromRpmFeedPerRevRule()
        result = rule.evaluate({
            "spindle_speed": Quantity.of(1000, Unit.RPM),
            "feed_per_rev": Quantity.of(0.2, Unit.MM_REV),
        })
        assert result.status is ResultStatus.PASS
        assert result.outputs["feed_rate"].value == Decimal("200")
        assert result.outputs["feed_rate"].unit is Unit.MM_MIN

    def test_milling_feed_rule(self) -> None:
        rule = FeedRateFromRpmToothFeedRule()
        result = rule.evaluate({
            "spindle_speed": Quantity.of(2000, Unit.RPM),
            "tooth_count": 4,
            "feed_per_tooth": Quantity.of(0.1, Unit.MM_TOOTH),
        })
        assert result.status is ResultStatus.PASS
        assert result.outputs["feed_rate"].value == Decimal("800")

    def test_mrr_rule(self) -> None:
        rule = MillingMaterialRemovalRateRule()
        result = rule.evaluate({
            "axial_depth": Quantity.of(2, Unit.MM),
            "radial_width": Quantity.of(10, Unit.MM),
            "feed_rate": Quantity.of(200, Unit.MM_MIN),
        })
        assert result.status is ResultStatus.PASS
        assert result.outputs["mrr"].value == Decimal("4000")
        assert result.outputs["mrr"].unit is Unit.MM3_MIN

    def test_time_rule(self) -> None:
        rule = MachiningTimeRule()
        result = rule.evaluate({
            "distance": Quantity.of(100, Unit.MM),
            "feed_rate": Quantity.of(200, Unit.MM_MIN),
        })
        assert result.status is ResultStatus.PASS
        assert result.outputs["time"].value == Decimal("0.5")
        assert result.outputs["time"].unit is Unit.MIN

    def test_torque_from_power_rule(self) -> None:
        rule = TorqueFromPowerRule()
        result = rule.evaluate({
            "power": Quantity.of(10, Unit.KW),
            "spindle_speed": Quantity.of(1000, Unit.RPM),
        })
        assert result.status is ResultStatus.PASS
        assert result.outputs["torque"].unit is Unit.NM

    def test_power_from_torque_rule(self) -> None:
        rule = PowerFromTorqueRule()
        result = rule.evaluate({
            "torque": Quantity.of(50, Unit.NM),
            "spindle_speed": Quantity.of(1000, Unit.RPM),
        })
        assert result.status is ResultStatus.PASS
        assert result.outputs["power"].unit is Unit.KW

    def test_provenance_present(self) -> None:
        rule = SpindleSpeedFromCuttingSpeedRule()
        result = rule.evaluate({
            "cutting_speed": Quantity.of(100, Unit.M_MIN),
            "diameter": Quantity.of(10, Unit.MM),
        })
        assert result.provenance.source_type is not None
        assert result.rule_id == "R-2001"


class TestRuleFailClosed:
    def test_missing_input_insufficient_data(self) -> None:
        rule = SpindleSpeedFromCuttingSpeedRule()
        result = rule.evaluate({"cutting_speed": Quantity.of(100, Unit.M_MIN)})
        assert result.status is ResultStatus.INSUFFICIENT_DATA
        assert "diameter" in result.missing_inputs

    def test_wrong_unit_fails(self) -> None:
        rule = SpindleSpeedFromCuttingSpeedRule()
        result = rule.evaluate({
            "cutting_speed": Quantity.of(100, Unit.MM_MIN),
            "diameter": Quantity.of(10, Unit.MM),
        })
        assert result.status is ResultStatus.FAIL

    def test_zero_diameter_fails(self) -> None:
        rule = SpindleSpeedFromCuttingSpeedRule()
        result = rule.evaluate({
            "cutting_speed": Quantity.of(100, Unit.M_MIN),
            "diameter": Quantity.of(0, Unit.MM),
        })
        assert result.status is ResultStatus.FAIL

    def test_zero_rpm_torque_fails(self) -> None:
        rule = TorqueFromPowerRule()
        result = rule.evaluate({
            "power": Quantity.of(10, Unit.KW),
            "spindle_speed": Quantity.of(0, Unit.RPM),
        })
        assert result.status is ResultStatus.FAIL


class TestRuleRegistry:
    def test_all_machining_rules_registerable(self) -> None:
        registry = RuleRegistry()
        for rule in foundational_machining_rules():
            registry.register(rule)
        assert len(registry) == 13

    def test_machining_rule_ids_unique(self) -> None:
        ids = [r.rule_id for r in foundational_machining_rules()]
        assert len(ids) == len(set(ids))
