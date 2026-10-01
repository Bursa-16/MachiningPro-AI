"""Tests for threading engineering rules (Stage 3E)."""

from __future__ import annotations

from decimal import Decimal

from backend.domain.enums import ResultStatus
from backend.domain.units import Quantity, Unit
from backend.machining.threading_rules import (
    EffectiveTravelNotLessThanThreadLengthRule,
    LeadFromPitchRule,
    PitchFromLeadRule,
    SingleStartLeadEqualsPitchRule,
    ThreadFeedConsistencyRule,
    ThreadFeedRateRule,
    ThreadingMachiningTimeRule,
    ThreadingRevolutionsRule,
    ZeroThreadLengthRule,
    foundational_threading_rules,
)

Q = Quantity.of


# ===================================================================
# Rule ID uniqueness
# ===================================================================

class TestRuleIDUniqueness:
    def test_all_threading_ids_unique(self):
        rules = foundational_threading_rules()
        ids = [r.rule_id for r in rules]
        assert len(ids) == len(set(ids))

    def test_no_overlap_with_3a(self):
        from backend.machining.rules import foundational_machining_rules
        ids_3a = {r.rule_id for r in foundational_machining_rules()}
        ids_3e = {r.rule_id for r in foundational_threading_rules()}
        assert ids_3a.isdisjoint(ids_3e)

    def test_no_overlap_with_3b(self):
        from backend.machining.turning_rules import foundational_turning_rules
        ids_3b = {r.rule_id for r in foundational_turning_rules()}
        ids_3e = {r.rule_id for r in foundational_threading_rules()}
        assert ids_3b.isdisjoint(ids_3e)

    def test_no_overlap_with_3c(self):
        from backend.machining.milling_rules import foundational_milling_rules
        ids_3c = {r.rule_id for r in foundational_milling_rules()}
        ids_3e = {r.rule_id for r in foundational_threading_rules()}
        assert ids_3c.isdisjoint(ids_3e)

    def test_no_overlap_with_3d(self):
        from backend.machining.drilling_rules import foundational_drilling_rules
        ids_3d = {r.rule_id for r in foundational_drilling_rules()}
        ids_3e = {r.rule_id for r in foundational_threading_rules()}
        assert ids_3d.isdisjoint(ids_3e)


# ===================================================================
# Calculation rules
# ===================================================================

class TestLeadFromPitchRule:
    def test_single_start(self):
        r = LeadFromPitchRule()
        result = r.evaluate({"pitch": Q("1.5", Unit.MM_REV)})
        assert result.status is ResultStatus.PASS
        assert result.outputs["lead"].value == Decimal("1.5")

    def test_multi_start(self):
        r = LeadFromPitchRule()
        result = r.evaluate({"pitch": Q("1.5", Unit.MM_REV), "number_of_starts": 3})
        assert result.outputs["lead"].value == Decimal("4.5")

    def test_missing_pitch(self):
        r = LeadFromPitchRule()
        result = r.evaluate({})
        assert result.status is ResultStatus.INSUFFICIENT_DATA


class TestPitchFromLeadRule:
    def test_pass(self):
        r = PitchFromLeadRule()
        result = r.evaluate({"lead": Q("4.5", Unit.MM_REV), "number_of_starts": 3})
        assert result.outputs["pitch"].value == Decimal("1.5")


class TestThreadFeedRateRule:
    def test_pass(self):
        r = ThreadFeedRateRule()
        result = r.evaluate({
            "spindle_speed": Q("500", Unit.RPM),
            "lead": Q("1.5", Unit.MM_REV),
        })
        assert result.status is ResultStatus.PASS
        assert result.outputs["feed_rate"].value == Decimal("750")


class TestThreadingMachiningTimeRule:
    def test_pass(self):
        r = ThreadingMachiningTimeRule()
        result = r.evaluate({
            "spindle_speed": Q("500", Unit.RPM),
            "lead": Q("1.5", Unit.MM_REV),
            "thread_length": Q("20", Unit.MM),
        })
        assert result.status is ResultStatus.PASS
        expected = Decimal("20") / Decimal("750")
        assert result.outputs["time"].value == expected


class TestThreadingRevolutionsRule:
    def test_pass(self):
        r = ThreadingRevolutionsRule()
        result = r.evaluate({
            "effective_travel": Q("30", Unit.MM),
            "lead": Q("1.5", Unit.MM_REV),
        })
        assert result.outputs["revolutions"].value == Decimal("20")


# ===================================================================
# Validation rules
# ===================================================================

class TestThreadFeedConsistencyRule:
    def test_consistent_pass(self):
        r = ThreadFeedConsistencyRule()
        result = r.evaluate({
            "feed_rate": Q("750", Unit.MM_MIN),
            "spindle_speed": Q("500", Unit.RPM),
            "lead": Q("1.5", Unit.MM_REV),
        })
        assert result.status is ResultStatus.PASS

    def test_inconsistent_fail(self):
        r = ThreadFeedConsistencyRule()
        result = r.evaluate({
            "feed_rate": Q("900", Unit.MM_MIN),
            "spindle_speed": Q("500", Unit.RPM),
            "lead": Q("1.5", Unit.MM_REV),
        })
        assert result.status is ResultStatus.FAIL

    def test_all_zero(self):
        r = ThreadFeedConsistencyRule()
        result = r.evaluate({
            "feed_rate": Q("0", Unit.MM_MIN),
            "spindle_speed": Q("0", Unit.RPM),
            "lead": Q("1.5", Unit.MM_REV),
        })
        assert result.status is ResultStatus.PASS


class TestEffectiveTravelRule:
    def test_travel_equals_length(self):
        r = EffectiveTravelNotLessThanThreadLengthRule()
        result = r.evaluate({
            "thread_length": Q("20", Unit.MM),
            "effective_travel": Q("20", Unit.MM),
        })
        assert result.status is ResultStatus.PASS

    def test_travel_exceeds(self):
        r = EffectiveTravelNotLessThanThreadLengthRule()
        result = r.evaluate({
            "thread_length": Q("20", Unit.MM),
            "effective_travel": Q("23", Unit.MM),
        })
        assert result.status is ResultStatus.PASS

    def test_travel_less_than_length(self):
        r = EffectiveTravelNotLessThanThreadLengthRule()
        result = r.evaluate({
            "thread_length": Q("20", Unit.MM),
            "effective_travel": Q("15", Unit.MM),
        })
        assert result.status is ResultStatus.FAIL


class TestSingleStartLeadEqualsPitchRule:
    def test_single_start_equal(self):
        r = SingleStartLeadEqualsPitchRule()
        result = r.evaluate({
            "pitch": Q("1.5", Unit.MM_REV),
            "lead": Q("1.5", Unit.MM_REV),
            "number_of_starts": 1,
        })
        assert result.status is ResultStatus.PASS

    def test_single_start_mismatch(self):
        r = SingleStartLeadEqualsPitchRule()
        result = r.evaluate({
            "pitch": Q("1.5", Unit.MM_REV),
            "lead": Q("3.0", Unit.MM_REV),
            "number_of_starts": 1,
        })
        assert result.status is ResultStatus.FAIL

    def test_multi_start_skips(self):
        r = SingleStartLeadEqualsPitchRule()
        result = r.evaluate({
            "pitch": Q("1.5", Unit.MM_REV),
            "lead": Q("4.5", Unit.MM_REV),
            "number_of_starts": 3,
        })
        assert result.status is ResultStatus.PASS  # rule not applicable


class TestZeroThreadLengthRule:
    def test_positive_pass(self):
        r = ZeroThreadLengthRule()
        result = r.evaluate({"thread_length": Q("20", Unit.MM)})
        assert result.status is ResultStatus.PASS

    def test_zero_warning(self):
        r = ZeroThreadLengthRule()
        result = r.evaluate({"thread_length": Q("0", Unit.MM)})
        assert result.status is ResultStatus.WARNING


# ===================================================================
# Determinism / no mutation
# ===================================================================

class TestDeterminism:
    def test_repeat(self):
        r = ThreadFeedRateRule()
        inputs = {"spindle_speed": Q("500", Unit.RPM), "lead": Q("1.5", Unit.MM_REV)}
        a = r.evaluate(inputs)
        b = r.evaluate(inputs)
        assert a.outputs["feed_rate"].value == b.outputs["feed_rate"].value


class TestNoMutation:
    def test_inputs_unchanged(self):
        r = ThreadingMachiningTimeRule()
        inputs = {
            "spindle_speed": Q("500", Unit.RPM),
            "lead": Q("1.5", Unit.MM_REV),
            "thread_length": Q("20", Unit.MM),
        }
        orig = {k: v.value for k, v in inputs.items()}
        r.evaluate(inputs)
        for k, v in inputs.items():
            assert v.value == orig[k]
