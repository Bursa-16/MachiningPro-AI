"""Tests for drilling engineering rules (Stage 3D).

Covers:
  - rule ID uniqueness (global across 3A/3B/3C/3D)
  - calculation rule evaluation
  - validation rule trigger/non-trigger
  - boundary behavior
  - deterministic repeatability
  - no mutation of inputs
  - missing inputs → INSUFFICIENT_DATA
"""

from __future__ import annotations

from decimal import Decimal

from backend.domain.enums import ResultStatus
from backend.domain.units import Quantity, Unit
from backend.machining.drilling_rules import (
    CylindricalHoleVolumeRule,
    DrillingDepthToDiameterRatioRule,
    DrillingFeedConsistencyRule,
    DrillingMachiningTimeRule,
    DrillingMRRRule,
    DrillingZeroDepthRule,
    EffectiveDrillingTravelRule,
    EffectiveTravelNotLessThanDepthRule,
    HoleCrossSectionalAreaRule,
    foundational_drilling_rules,
)

Q = Quantity.of


# ===================================================================
# Rule ID uniqueness
# ===================================================================

class TestRuleIDUniqueness:
    def test_all_drilling_ids_unique(self):
        rules = foundational_drilling_rules()
        ids = [r.rule_id for r in rules]
        assert len(ids) == len(set(ids)), f"duplicate IDs: {ids}"

    def test_no_overlap_with_stage_3a(self):
        from backend.machining.rules import foundational_machining_rules
        ids_3a = {r.rule_id for r in foundational_machining_rules()}
        ids_3d = {r.rule_id for r in foundational_drilling_rules()}
        assert ids_3a.isdisjoint(ids_3d)

    def test_no_overlap_with_stage_3b(self):
        from backend.machining.turning_rules import foundational_turning_rules
        ids_3b = {r.rule_id for r in foundational_turning_rules()}
        ids_3d = {r.rule_id for r in foundational_drilling_rules()}
        assert ids_3b.isdisjoint(ids_3d)

    def test_no_overlap_with_stage_3c(self):
        from backend.machining.milling_rules import foundational_milling_rules
        ids_3c = {r.rule_id for r in foundational_milling_rules()}
        ids_3d = {r.rule_id for r in foundational_drilling_rules()}
        assert ids_3c.isdisjoint(ids_3d)


# ===================================================================
# Calculation rules
# ===================================================================

class TestEffectiveDrillingTravelRule:
    def test_pass_depth_only(self):
        r = EffectiveDrillingTravelRule()
        result = r.evaluate({"hole_depth": Q("30", Unit.MM)})
        assert result.status is ResultStatus.PASS
        assert result.outputs["effective_travel"].value == Decimal("30")

    def test_pass_with_allowances(self):
        r = EffectiveDrillingTravelRule()
        result = r.evaluate({
            "hole_depth": Q("30", Unit.MM),
            "approach_allowance": Q("2", Unit.MM),
            "breakthrough_allowance": Q("3", Unit.MM),
        })
        assert result.outputs["effective_travel"].value == Decimal("35")

    def test_missing_depth(self):
        r = EffectiveDrillingTravelRule()
        result = r.evaluate({})
        assert result.status is ResultStatus.INSUFFICIENT_DATA


class TestDrillingMachiningTimeRule:
    def test_pass(self):
        r = DrillingMachiningTimeRule()
        result = r.evaluate({
            "spindle_speed": Q("1000", Unit.RPM),
            "feed_per_rev": Q("0.2", Unit.MM_REV),
            "hole_depth": Q("30", Unit.MM),
        })
        assert result.status is ResultStatus.PASS
        assert result.outputs["time"].value == Decimal("0.15")


class TestHoleCrossSectionalAreaRule:
    def test_pass(self):
        r = HoleCrossSectionalAreaRule()
        result = r.evaluate({"diameter": Q("10", Unit.MM)})
        assert result.status is ResultStatus.PASS
        assert "area" in result.outputs


class TestCylindricalHoleVolumeRule:
    def test_pass(self):
        r = CylindricalHoleVolumeRule()
        result = r.evaluate({"diameter": Q("10", Unit.MM), "depth": Q("30", Unit.MM)})
        assert result.status is ResultStatus.PASS
        assert result.outputs["volume"].unit is Unit.MM3


class TestDrillingMRRRule:
    def test_pass(self):
        r = DrillingMRRRule()
        result = r.evaluate({"diameter": Q("10", Unit.MM), "feed_rate": Q("200", Unit.MM_MIN)})
        assert result.status is ResultStatus.PASS
        assert result.outputs["mrr"].unit is Unit.MM3_MIN

    def test_missing_input(self):
        r = DrillingMRRRule()
        result = r.evaluate({"diameter": Q("10", Unit.MM)})
        assert result.status is ResultStatus.INSUFFICIENT_DATA


# ===================================================================
# Validation rules
# ===================================================================

class TestDrillingFeedConsistencyRule:
    def test_consistent_pass(self):
        r = DrillingFeedConsistencyRule()
        # n=1000, f=0.2 → Vf=200
        result = r.evaluate({
            "feed_rate": Q("200", Unit.MM_MIN),
            "spindle_speed": Q("1000", Unit.RPM),
            "feed_per_rev": Q("0.2", Unit.MM_REV),
        })
        assert result.status is ResultStatus.PASS

    def test_inconsistent_fail(self):
        r = DrillingFeedConsistencyRule()
        result = r.evaluate({
            "feed_rate": Q("300", Unit.MM_MIN),
            "spindle_speed": Q("1000", Unit.RPM),
            "feed_per_rev": Q("0.2", Unit.MM_REV),
        })
        assert result.status is ResultStatus.FAIL

    def test_all_zero_consistent(self):
        r = DrillingFeedConsistencyRule()
        result = r.evaluate({
            "feed_rate": Q("0", Unit.MM_MIN),
            "spindle_speed": Q("0", Unit.RPM),
            "feed_per_rev": Q("0.2", Unit.MM_REV),
        })
        assert result.status is ResultStatus.PASS


class TestEffectiveTravelNotLessThanDepthRule:
    def test_travel_equals_depth_pass(self):
        r = EffectiveTravelNotLessThanDepthRule()
        result = r.evaluate({
            "hole_depth": Q("30", Unit.MM),
            "effective_travel": Q("30", Unit.MM),
        })
        assert result.status is ResultStatus.PASS

    def test_travel_exceeds_depth_pass(self):
        r = EffectiveTravelNotLessThanDepthRule()
        result = r.evaluate({
            "hole_depth": Q("30", Unit.MM),
            "effective_travel": Q("35", Unit.MM),
        })
        assert result.status is ResultStatus.PASS

    def test_travel_less_than_depth_fail(self):
        r = EffectiveTravelNotLessThanDepthRule()
        result = r.evaluate({
            "hole_depth": Q("30", Unit.MM),
            "effective_travel": Q("25", Unit.MM),
        })
        assert result.status is ResultStatus.FAIL


class TestDrillingZeroDepthRule:
    def test_positive_depth_pass(self):
        r = DrillingZeroDepthRule()
        result = r.evaluate({"hole_depth": Q("30", Unit.MM)})
        assert result.status is ResultStatus.PASS

    def test_zero_depth_warning(self):
        r = DrillingZeroDepthRule()
        result = r.evaluate({"hole_depth": Q("0", Unit.MM)})
        assert result.status is ResultStatus.WARNING


class TestDrillingDepthToDiameterRatioRule:
    def test_within_threshold_pass(self):
        r = DrillingDepthToDiameterRatioRule()
        # 30/10 = 3 < 10
        result = r.evaluate({"hole_depth": Q("30", Unit.MM), "diameter": Q("10", Unit.MM)})
        assert result.status is ResultStatus.PASS

    def test_at_threshold_pass(self):
        r = DrillingDepthToDiameterRatioRule()
        # 100/10 = 10, at threshold (not above)
        result = r.evaluate({"hole_depth": Q("100", Unit.MM), "diameter": Q("10", Unit.MM)})
        assert result.status is ResultStatus.PASS

    def test_exceeds_threshold_warning(self):
        r = DrillingDepthToDiameterRatioRule()
        # 110/10 = 11 > 10
        result = r.evaluate({"hole_depth": Q("110", Unit.MM), "diameter": Q("10", Unit.MM)})
        assert result.status is ResultStatus.WARNING
        assert len(result.warnings) == 1


# ===================================================================
# Deterministic repeatability
# ===================================================================

class TestDeterministicRules:
    def test_repeat_evaluation(self):
        r = DrillingMRRRule()
        inputs = {"diameter": Q("10", Unit.MM), "feed_rate": Q("200", Unit.MM_MIN)}
        a = r.evaluate(inputs)
        b = r.evaluate(inputs)
        assert a.outputs["mrr"].value == b.outputs["mrr"].value


# ===================================================================
# No mutation
# ===================================================================

class TestNoMutation:
    def test_rule_does_not_mutate_inputs(self):
        r = DrillingMRRRule()
        inputs = {"diameter": Q("10", Unit.MM), "feed_rate": Q("200", Unit.MM_MIN)}
        orig_d = inputs["diameter"].value
        orig_vf = inputs["feed_rate"].value
        r.evaluate(inputs)
        assert inputs["diameter"].value == orig_d
        assert inputs["feed_rate"].value == orig_vf
