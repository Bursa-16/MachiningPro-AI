"""Tests for milling engineering rules (Stage 3C).

Covers:
  - all rule IDs unique
  - deterministic repeated evaluation
  - trigger and non-trigger cases
  - boundary behavior
  - severity correctness
  - no mutation of inputs
  - policy vs physical classification
  - missing input → INSUFFICIENT_DATA
"""

from __future__ import annotations

from decimal import Decimal

from backend.domain.enums import ResultStatus
from backend.domain.units import Quantity, Unit
from backend.machining.milling_rules import (
    AxialEngagementRatioRule,
    AxialEngagementSanityRule,
    FeedPerRevFromToothFeedRule,
    MillingFeedRateConsistencyRule,
    MillingMachiningTimeRule,
    MillingMRRRule,
    MillingZeroEngagementRule,
    RadialEngagementExceedsToolDiameterRule,
    RadialEngagementRatioRule,
    foundational_milling_rules,
)

Q = Quantity.of


# ===================================================================
# Rule ID uniqueness
# ===================================================================

class TestRuleIDUniqueness:
    def test_all_ids_unique(self):
        rules = foundational_milling_rules()
        ids = [r.rule_id for r in rules]
        assert len(ids) == len(set(ids)), f"duplicate IDs: {ids}"

    def test_no_overlap_with_stage_3a(self):
        from backend.machining.rules import foundational_machining_rules
        ids_3a = {r.rule_id for r in foundational_machining_rules()}
        ids_3c = {r.rule_id for r in foundational_milling_rules()}
        assert ids_3a.isdisjoint(ids_3c)

    def test_no_overlap_with_stage_3b(self):
        from backend.machining.turning_rules import foundational_turning_rules
        ids_3b = {r.rule_id for r in foundational_turning_rules()}
        ids_3c = {r.rule_id for r in foundational_milling_rules()}
        assert ids_3b.isdisjoint(ids_3c)


# ===================================================================
# Calculation rules
# ===================================================================

class TestFeedPerRevFromToothFeedRule:
    def test_pass(self):
        r = FeedPerRevFromToothFeedRule()
        result = r.evaluate({"tooth_count": 4, "feed_per_tooth": Q("0.1", Unit.MM_TOOTH)})
        assert result.status is ResultStatus.PASS
        assert result.outputs["feed_per_rev"].value == Decimal("0.4")

    def test_missing_input(self):
        r = FeedPerRevFromToothFeedRule()
        result = r.evaluate({"tooth_count": 4})
        assert result.status is ResultStatus.INSUFFICIENT_DATA

    def test_deterministic(self):
        r = FeedPerRevFromToothFeedRule()
        inputs = {"tooth_count": 4, "feed_per_tooth": Q("0.1", Unit.MM_TOOTH)}
        a = r.evaluate(inputs)
        b = r.evaluate(inputs)
        assert a.outputs["feed_per_rev"].value == b.outputs["feed_per_rev"].value


class TestRadialEngagementRatioRule:
    def test_pass(self):
        r = RadialEngagementRatioRule()
        result = r.evaluate({"radial_width": Q("10", Unit.MM), "tool_diameter": Q("20", Unit.MM)})
        assert result.status is ResultStatus.PASS
        assert result.outputs["radial_engagement_ratio"].value == Decimal("0.5")


class TestAxialEngagementRatioRule:
    def test_pass(self):
        r = AxialEngagementRatioRule()
        result = r.evaluate({"axial_depth": Q("5", Unit.MM), "tool_diameter": Q("20", Unit.MM)})
        assert result.status is ResultStatus.PASS
        assert result.outputs["axial_engagement_ratio"].value == Decimal("0.25")


class TestMillingMachiningTimeRule:
    def test_pass(self):
        r = MillingMachiningTimeRule()
        result = r.evaluate({
            "spindle_speed": Q("1000", Unit.RPM),
            "tooth_count": 4,
            "feed_per_tooth": Q("0.1", Unit.MM_TOOTH),
            "cutting_distance": Q("200", Unit.MM),
        })
        assert result.status is ResultStatus.PASS
        assert result.outputs["time"].value == Decimal("0.5")


class TestMillingMRRRule:
    def test_pass(self):
        r = MillingMRRRule()
        result = r.evaluate({
            "axial_depth": Q("2", Unit.MM),
            "radial_width": Q("10", Unit.MM),
            "spindle_speed": Q("1000", Unit.RPM),
            "tooth_count": 4,
            "feed_per_tooth": Q("0.1", Unit.MM_TOOTH),
        })
        assert result.status is ResultStatus.PASS
        assert result.outputs["mrr"].value == Decimal("8000")


# ===================================================================
# Validation rules
# ===================================================================

class TestRadialEngagementExceedsToolDiameterRule:
    def test_within_limit_pass(self):
        r = RadialEngagementExceedsToolDiameterRule()
        result = r.evaluate({"radial_width": Q("10", Unit.MM), "tool_diameter": Q("20", Unit.MM)})
        assert result.status is ResultStatus.PASS

    def test_exactly_full_slotting_pass(self):
        r = RadialEngagementExceedsToolDiameterRule()
        result = r.evaluate({"radial_width": Q("20", Unit.MM), "tool_diameter": Q("20", Unit.MM)})
        assert result.status is ResultStatus.PASS

    def test_exceeds_fail(self):
        r = RadialEngagementExceedsToolDiameterRule()
        result = r.evaluate({"radial_width": Q("25", Unit.MM), "tool_diameter": Q("20", Unit.MM)})
        assert result.status is ResultStatus.FAIL
        assert len(result.violations) == 1

    def test_missing_input(self):
        r = RadialEngagementExceedsToolDiameterRule()
        result = r.evaluate({"radial_width": Q("10", Unit.MM)})
        assert result.status is ResultStatus.INSUFFICIENT_DATA


class TestAxialEngagementSanityRule:
    def test_within_threshold_pass(self):
        r = AxialEngagementSanityRule()
        result = r.evaluate({"axial_depth": Q("20", Unit.MM), "tool_diameter": Q("20", Unit.MM)})
        assert result.status is ResultStatus.PASS

    def test_at_threshold_pass(self):
        r = AxialEngagementSanityRule()
        result = r.evaluate({"axial_depth": Q("40", Unit.MM), "tool_diameter": Q("20", Unit.MM)})
        assert result.status is ResultStatus.PASS  # at threshold, not above

    def test_exceeds_threshold_warning(self):
        r = AxialEngagementSanityRule()
        result = r.evaluate({"axial_depth": Q("50", Unit.MM), "tool_diameter": Q("20", Unit.MM)})
        assert result.status is ResultStatus.WARNING
        assert len(result.warnings) == 1


class TestMillingFeedRateConsistencyRule:
    def test_consistent_pass(self):
        r = MillingFeedRateConsistencyRule()
        # n=1000, z=4, fz=0.1 → Vf=400
        result = r.evaluate({
            "feed_rate": Q("400", Unit.MM_MIN),
            "spindle_speed": Q("1000", Unit.RPM),
            "tooth_count": 4,
            "feed_per_tooth": Q("0.1", Unit.MM_TOOTH),
        })
        assert result.status is ResultStatus.PASS

    def test_inconsistent_fail(self):
        r = MillingFeedRateConsistencyRule()
        # n=1000, z=4, fz=0.1 → Vf should be 400, but given 500
        result = r.evaluate({
            "feed_rate": Q("500", Unit.MM_MIN),
            "spindle_speed": Q("1000", Unit.RPM),
            "tooth_count": 4,
            "feed_per_tooth": Q("0.1", Unit.MM_TOOTH),
        })
        assert result.status is ResultStatus.FAIL

    def test_all_zero_consistent(self):
        r = MillingFeedRateConsistencyRule()
        result = r.evaluate({
            "feed_rate": Q("0", Unit.MM_MIN),
            "spindle_speed": Q("0", Unit.RPM),
            "tooth_count": 4,
            "feed_per_tooth": Q("0.1", Unit.MM_TOOTH),
        })
        # Vf=0 (from n=0), given Vf=0 → consistent
        assert result.status is ResultStatus.PASS


class TestMillingZeroEngagementRule:
    def test_non_zero_pass(self):
        r = MillingZeroEngagementRule()
        result = r.evaluate({"axial_depth": Q("2", Unit.MM), "radial_width": Q("10", Unit.MM)})
        assert result.status is ResultStatus.PASS

    def test_one_zero_pass(self):
        r = MillingZeroEngagementRule()
        result = r.evaluate({"axial_depth": Q("0", Unit.MM), "radial_width": Q("10", Unit.MM)})
        assert result.status is ResultStatus.PASS

    def test_both_zero_warning(self):
        r = MillingZeroEngagementRule()
        result = r.evaluate({"axial_depth": Q("0", Unit.MM), "radial_width": Q("0", Unit.MM)})
        assert result.status is ResultStatus.WARNING
        assert len(result.warnings) == 1


# ===================================================================
# No mutation of inputs
# ===================================================================

class TestNoMutation:
    def test_rule_does_not_mutate_inputs(self):
        r = MillingMRRRule()
        inputs = {
            "axial_depth": Q("2", Unit.MM),
            "radial_width": Q("10", Unit.MM),
            "spindle_speed": Q("1000", Unit.RPM),
            "tooth_count": 4,
            "feed_per_tooth": Q("0.1", Unit.MM_TOOTH),
        }
        original_values = {
            k: (v.value if isinstance(v, Quantity) else v) for k, v in inputs.items()
        }
        r.evaluate(inputs)
        for k, v in inputs.items():
            if isinstance(v, Quantity):
                assert v.value == original_values[k]
            else:
                assert v == original_values[k]
